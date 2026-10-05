package org.dayone.midwife;

import org.json.*;
import java.util.*;
import java.util.regex.*;

/** Split an explicitly written pressure pair; never infer a missing digit or unit. */
final class CombinedBloodPressure {
    private static final Pattern PAIR=Pattern.compile("^(\\d{1,3}(?:[.,]\\d+)?)\\s*/\\s*(\\d{1,3}(?:[.,]\\d+)?)\\s*(mm\\s*hg|cm\\s*hg|kpa)?$",Pattern.CASE_INSENSITIVE);
    static void apply(JSONObject fields,MobileGrammar grammar)throws Exception {
        List<String> systolicKeys=new ArrayList<>();
        for(Iterator<String> it=fields.keys();it.hasNext();) {String key=it.next();if(key.equals("systolic_bp_mmhg")||key.endsWith(".systolic_bp_mmhg"))systolicKeys.add(key);}
        for(String systolic:systolicKeys) {
            String diastolic=systolic.substring(0,systolic.length()-"systolic_bp_mmhg".length())+"diastolic_bp_mmhg";
            if(!fields.has(diastolic))continue;
            for(String sourceKey:new String[]{systolic,diastolic}) {
                JSONObject source=fields.getJSONObject(sourceKey);
                Matcher match=PAIR.matcher(MobileGrammar.normalize(source.optString("raw_text","")));
                if(!match.matches()||!source.has("ocr"))continue;
                JSONObject ocr=source.getJSONObject("ocr");
                if(ocr.optBoolean("generation_limit")||(ocr.optJSONArray("warnings")!=null&&ocr.getJSONArray("warnings").length()>0))continue;
                String suffix=match.group(3)==null?"":" "+match.group(3);
                JSONObject sys=grammar.parse(systolic,match.group(1)+suffix,source.optDouble("confidence"));
                JSONObject dia=grammar.parse(diastolic,match.group(2)+suffix,source.optDouble("confidence"));
                if(sys.isNull("value")||dia.isNull("value"))continue;
                boolean conflict=false;
                for(String key:new String[]{systolic,diastolic}) {
                    JSONObject current=fields.getJSONObject(key),replacement=key.equals(systolic)?sys:dia;
                    if(!current.isNull("value")&&(!(current.opt("value") instanceof Number)||Math.abs(current.getDouble("value")-replacement.getDouble("value"))>1e-6))conflict=true;
                }
                if(conflict) {
                    MobileGrammar.issue(fields.getJSONObject(systolic),"BP_PAIR_CONFLICT");
                    MobileGrammar.issue(fields.getJSONObject(diastolic),"BP_PAIR_CONFLICT");break;
                }
                for(String key:new String[]{systolic,diastolic}) {
                    JSONObject value=key.equals(systolic)?sys:dia;
                    value.put("raw_text",source.getString("raw_text")).put("source","explicit_blood_pressure_pair")
                            .put("source_field",sourceKey).put("ocr",ocr);
                    for(String evidence:new String[]{"crop_quad","crop_horizontal_pad","localization","raw_candidates"})if(source.has(evidence))value.put(evidence,source.get(evidence));
                    // Preserve independent uncertainty, excluding errors caused solely by treating A/B as one number.
                    JSONArray issues=source.optJSONArray("issues");
                    if(issues!=null)for(int i=0;i<issues.length();i++) {
                        String issue=issues.getString(i);
                        if(!issue.equals("UNKNOWN_OR_WRONG_UNIT")&&!issue.equals("INVALID_NUMERIC_SYNTAX"))MobileGrammar.issue(value,issue);
                    }
                    MobileGrammar.review(value);fields.put(key,value);
                }
                break;
            }
        }
    }
}
