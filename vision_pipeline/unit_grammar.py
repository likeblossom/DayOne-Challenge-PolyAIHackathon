"""Schema-scoped unit reading; never globally replace digit-like letters.

Typographic normalization is lossless. OCR substitutions are explicit allowlists,
recorded as inferred units and always require review. A bare number is never
shortened automatically just because a shorter candidate fits a sanity range.
"""
import math
import re
import unicodedata

VERSION='field-units-v1'
NUMBER=r'[+-]?\d+(?:[.,]\d+)?'

def unit_key(text):
    text=unicodedata.normalize('NFKC',text).casefold().strip().rstrip(' .')
    # Greek mu and micro sign describe the same SI prefix in these explicit units.
    return re.sub(r'\s+','',text).replace('μ','u').replace('µ','u').replace('×','x').replace('⁄','/')

# Keyed by schema target unit; replacement must also be an accepted explicit unit.
# Valid but incompatible units (L, mg, Fahrenheit, etc.) are NOT fuzzy-corrected.
OCR_UNIT_ALIASES={
 'g':{'9':'g','q':'g','k9':'kg','kq':'kg'},
 'kg':{'k9':'kg','kq':'kg','9':'g','q':'g'},
 'cm':{'crn':'cm','rnrn':'mm'},
 'mmHg':{'mmh9':'mmhg','mmhq':'mmhg','mrnhg':'mmhg','cmh9':'cmhg'},
 '°C':{'°l':'°c','°|':'°c','°0':'°c','°o':'°c','0c':'°c','oc':'°c'},
 'bpm':{'bprn':'bpm','b/rnin':'b/min','/rnin':'/min'},
 'g/dL':{'9/dl':'g/dl','q/dl':'g/dl','g/d1':'g/dl','g/d|':'g/dl','g/1':'g/l','g/|':'g/l'},
 'g/L':{'9/l':'g/l','q/l':'g/l','g/1':'g/l','g/|':'g/l','mg/d1':'mg/dl','mg/d|':'mg/dl','mmol/1':'mmol/l','mmol/|':'mmol/l'},
 'per uL':{'/u1':'/ul','/u|':'/ul','x10^3/u1':'x10^3/ul','10^9/1':'10^9/l'},
 'days':{'jour5':'jours','iour':'jour','iours':'jours','day5':'days'},
 'weeks':{'sern':'sem','sema1nes':'semaines','week5':'weeks'},
 'years':{'an5':'ans','year5':'years'},
}

def policy(unit,aliases):
    corrections=OCR_UNIT_ALIASES.get(unit,{})
    assert unit is None or unit in OCR_UNIT_ALIASES,unit
    assert all(unit_key(v) in {unit_key(k) for k in aliases} for v in corrections.values())
    return dict(expected_unit=unit,unitless_field=unit is None,
                missing_unit='Use declared schema unit; source=SCHEMA, not an observed OCR unit.' if unit else 'Count: numeric value only; unit suffixes rejected.',
                typography='Case, whitespace, micro-sign variants and multiplication-sign variants.',
                ocr_substitutions=corrections,substitution_action='Record correction and NEEDS_REVIEW; never silently accept.',
                fused_digit_policy='A trailing 9 in an out-of-range bare mass may suggest g; preserve original value and require manual confirmation.',
                incompatible_units='Reject unknown/incompatible units; no unrestricted edit-distance matching.',
                numeric_edits='Never drop or substitute numeric digits automatically.',version=VERSION)

def parse_numeric(text,rule,key):
    issues=[];changes=[];corrections=[];alternatives=[];value=None;source_value=None;unit=None;unit_source='UNRESOLVED';source_unit=None
    expected=rule.get('unit');aliases={unit_key(k):(k,v) for k,v in rule['unit_aliases'].items()}
    corrections_map={unit_key(k):unit_key(v) for k,v in rule['unit_policy']['ocr_substitutions'].items()}
    leaf=key.split('.')[-1];number=text;lo,hi=rule['ocr_sanity_range']
    if leaf in ['systolic_bp_mmhg','diastolic_bp_mmhg']:
        pair=re.fullmatch(r'('+NUMBER+r')\s*[/\\]\s*('+NUMBER+r')(.*)',number)
        if pair:
            number=pair[1 if leaf.startswith('systolic') else 2]+' '+pair[3];changes.append('BP_PAIR_COMPONENT')
        elif leaf.startswith('systolic') and number.endswith('/'):
            number=number[:-1];changes.append('TRAILING_BP_SEPARATOR')
    grouped=re.sub(r'(?<=\d)[ \u00a0](?=\d{3}(?:\D|$))','',number)
    if grouped!=number:changes.append('THOUSANDS_GROUPING')
    number=grouped
    # A digit-looking unit is allowed only AFTER an explicit whitespace boundary.
    separated=re.fullmatch(r'('+NUMBER+r')\s+(.+)',number)
    if separated and unit_key(separated[2]) in aliases.keys()|corrections_map.keys():m=separated
    else:m=re.fullmatch(r'('+NUMBER+r')\s*(.*)',number)
    if not m:
        issues.append('INVALID_NUMERIC_SYNTAX: no digit stripping or concatenation permitted')
    else:
        raw_unit=m[2].strip();token=unit_key(raw_unit);factor=None
        if token and token not in aliases and token not in corrections_map and any(c.isdigit() for c in token):
            issues.append('INVALID_NUMERIC_SYNTAX: unknown numeric suffix; no digit stripping permitted')
        else:
            source_value=float(m[1].replace(',','.'));value=source_value;source_unit=raw_unit or None
            if not token:
                factor=1.;unit=expected;unit_source='SCHEMA' if expected else 'UNITLESS'
            elif token in aliases:
                alias,factor=aliases[token];unit=expected;unit_source='EXPLICIT'
                changes.append('EXPLICIT_UNIT: '+alias)
                if raw_unit!=alias:changes.append('UNIT_TYPOGRAPHY: '+raw_unit+' -> '+alias)
            elif token in corrections_map:
                target=corrections_map[token];alias,factor=aliases[target];unit=expected;unit_source='SCHEMA_CORRECTED'
                corrections.append(dict(kind='UNIT_OCR_SUBSTITUTION',from_text=raw_unit,to_text=alias,expected_unit=expected,reason='Allowlisted unit-glyph confusion within this schema field',requires_confirmation=True))
                changes.append('UNIT_OCR_CORRECTION: '+raw_unit+' -> '+alias)
                issues.append('INFERRED_UNIT_REQUIRES_REVIEW')
            else:issues.append('UNKNOWN_OR_WRONG_UNIT: '+raw_unit)
            if factor is not None:
                value*=factor
                if factor!=1:changes.append('UNIT_CONVERSION: '+str(factor)+' -> '+str(expected))
            if not math.isfinite(value) or not lo<=value<=hi:
                issues.append(f'OUTSIDE_OCR_SANITY_RANGE: {lo}..{hi}; confirm original image')
                # Suggest, never apply, a fused g->9 reading. This is a hypothesis,
                # not evidence that a medically implausible number must be a typo.
                if expected in ['g','kg'] and not token and re.fullmatch(r'\d{2,}9',m[1]):
                    mass=float(m[1][:-1])*aliases[unit_key('g')][1]
                    if lo<=mass<=hi:
                        alternatives.append(dict(value=int(mass) if mass.is_integer() else mass,unit=expected,source_interpretation=m[1][:-1]+' g',reason='Final 9 could be a fused g; original digit remains unchanged',requires_confirmation=True))
                        issues.append('AMBIGUOUS_FUSED_DIGIT_OR_UNIT')
            if rule['type']=='integer' and math.isfinite(value) and not value.is_integer():issues.append('INTEGER_REQUIRED')
            if math.isfinite(value) and value.is_integer():value=int(value)
    quantity=None
    if value is not None and not math.isfinite(value):value=None
    if source_value is not None and not math.isfinite(source_value):source_value=None
    if value is not None and unit_source!='UNRESOLVED':quantity=str(value)+(' '+unit if unit else '')
    return dict(value=value,issues=issues,normalizations=changes,unit=unit,expected_unit=expected,unit_source=unit_source,source_unit=source_unit,source_value=source_value,normalized_quantity=quantity,corrections=corrections,numeric_alternatives=alternatives,grammar_version=VERSION)

def evidence(parsed):
    """Public field-level metadata; raw candidates remain the complete audit trail."""
    return {k:parsed[k] for k in ['unit','expected_unit','unit_source','source_unit','source_value','normalized_quantity','corrections','numeric_alternatives','grammar_version'] if k in parsed}
