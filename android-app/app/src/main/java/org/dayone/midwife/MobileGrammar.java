package org.dayone.midwife;

import org.json.*;
import java.text.Normalizer;
import java.time.LocalDate;
import java.util.*;
import java.util.regex.*;

/** Schema-scoped rules with an explicit, uncalibrated acceptance threshold. */
public final class MobileGrammar {
    private final JSONObject config,rules;
    public MobileGrammar(JSONObject config)throws Exception{this.config=config;rules=config.getJSONObject("rules");}
    public static String normalize(String raw){StringBuilder s=new StringBuilder();for(char c:Normalizer.normalize(raw,Normalizer.Form.NFKC).toCharArray()){int d=Character.digit(c,10);s.append(d>=0?(char)('0'+d):c);}return s.toString().replace('٫','.').replace("٬","").replace("\u200f","").replace("\u200e","").trim().replaceAll("\\s+"," ");}
    public static String fold(String raw){return Normalizer.normalize(normalize(raw).toLowerCase(Locale.ROOT),Normalizer.Form.NFKD).replaceAll("\\p{M}","");}
    private static String unit(String raw){return normalize(raw).toLowerCase(Locale.ROOT).replaceAll("[ .]+$","").replaceAll("\\s+","").replace('μ','u').replace('µ','u').replace('×','x').replace('⁄','/');}
    public static final double ACCEPT_CONFIDENCE=.70;
    public static JSONObject field(Object value,double confidence)throws JSONException{return review(new JSONObject().put("value",value==null?JSONObject.NULL:value).put("status","NEEDS_REVIEW").put("confidence",Double.isFinite(confidence)?Math.max(0,Math.min(1,confidence)):0).put("issues",new JSONArray()).put("confidence_calibrated",false));}
    public static JSONObject review(JSONObject field)throws JSONException{
        String status=field.optString("status");if(status.equals("ILLEGIBLE"))return field;
        boolean explicitMissing=status.equals("UNKNOWN")||status.equals("NOT_APPLICABLE")||status.equals("NOT_PROVIDED");
        boolean valid=field.optJSONArray("issues").length()==0&&field.optDouble("confidence")>=ACCEPT_CONFIDENCE;
        field.put("status",valid&&(!field.isNull("value")||explicitMissing)?(explicitMissing?status:"KNOWN"):"NEEDS_REVIEW");return field;
    }
    public static void issue(JSONObject field,String issue)throws JSONException{field.getJSONArray("issues").put(issue);field.put("status","NEEDS_REVIEW");}
    private static boolean contains(JSONArray array,String text)throws JSONException{for(int i=0;i<array.length();i++)if(fold(array.getString(i)).equals(fold(text)))return true;return false;}
    public JSONObject parse(String key,String raw,double confidence)throws Exception {
        JSONObject out=field(null,confidence),rule=rules.getJSONObject(key.replaceAll("\\[\\d+\\]","[]"));String text=normalize(raw),type=rule.getString("type");out.put("raw_text",raw);
        if(text.isEmpty()){issue(out,"NO_OCR_TEXT");out.put("status","ILLEGIBLE");return out;}
        if(contains(config.getJSONArray("unknown"),text)){out.put("status","UNKNOWN");return review(out);}
        if(contains(config.getJSONArray("not_applicable"),text)){out.put("status","NOT_APPLICABLE");return review(out);}
        if(type.equals("double")||type.equals("integer"))numeric(out,text,rule);
        else if(type.equals("date")){String date=parseDate(text);if(date==null)issue(out,"INVALID_OR_AMBIGUOUS_DATE");else out.put("value",date);}
        else if(type.equals("boolean")){String v=fold(text.replaceFirst("^[123]\\s*[:.)-]\\s*",""));if(Arrays.asList("yes","oui","true","1","نعم","checked","x").contains(v))out.put("value",true);else if(Arrays.asList("no","non","false","0","لا","unchecked").contains(v))out.put("value",false);else issue(out,"UNRECOGNIZED_BOOLEAN");}
        else if(type.equals("enum")||type.equals("array")){
            JSONArray allowed=type.equals("array")?rule.getJSONObject("items").getJSONArray("values"):rule.getJSONArray("values"),values=new JSONArray();
            for(String part:text.split(type.equals("array")?"[,;،]":"(?!)")){String f=fold(part.replace('_',' ')),found=null;for(int i=0;i<allowed.length();i++)if(f.equals(fold(allowed.getString(i).replace('_',' '))))found=allowed.getString(i);JSONObject aliases=config.getJSONObject("aliases");for(Iterator<String> it=aliases.keys();it.hasNext();){String a=it.next();if(f.equals(fold(a))&&contains(allowed,aliases.getString(a)))found=aliases.getString(a);}if(found!=null)values.put(found);else issue(out,"UNRECOGNIZED_OPTION");}
            if(type.equals("array"))out.put("value",values);else if(values.length()==1)out.put("value",values.get(0));
        }else{out.put("value",text);if(text.length()>rule.optInt("max_length",500))issue(out,"TEXT_TOO_LONG");if(rule.has("pattern")&&!Pattern.matches(rule.getString("pattern"),text))issue(out,"INVALID_FIELD_PATTERN");if(text.indexOf('\ufffd')>=0)issue(out,"CORRUPTED_TEXT");}
        return review(out);
    }
    private static void numeric(JSONObject out,String text,JSONObject rule)throws Exception {
        Map<String,Double> aliases=new HashMap<>();JSONObject aa=rule.getJSONObject("unit_aliases");for(Iterator<String> it=aa.keys();it.hasNext();){String k=it.next();aliases.put(unit(k),aa.getDouble(k));}
        JSONObject corrections=rule.getJSONObject("unit_policy").getJSONObject("ocr_substitutions");Map<String,String> fixes=new HashMap<>();for(Iterator<String> it=corrections.keys();it.hasNext();){String k=it.next();fixes.put(unit(k),unit(corrections.getString(k)));}
        text=text.replaceAll("(?<=\\d)[ \\u00a0](?=\\d{3}(?:\\D|$))","");String num="([+-]?\\d+(?:[.,]\\d+)?)";
        Matcher m=Pattern.compile(num+"\\s+(.+)").matcher(text);boolean separated=m.matches()&&(aliases.containsKey(unit(m.group(2)))||fixes.containsKey(unit(m.group(2))));
        if(!separated){m=Pattern.compile(num+"\\s*(.*)").matcher(text);if(!m.matches()){issue(out,"INVALID_NUMERIC_SYNTAX");return;}}
        String suffix=unit(m.group(2)),expected=rule.optString("unit","");double value=Double.parseDouble(m.group(1).replace(',','.')),factor=1;String source="SCHEMA";
        if(!suffix.isEmpty()){
            if(aliases.containsKey(suffix)){factor=aliases.get(suffix);source="EXPLICIT";}
            else if(fixes.containsKey(suffix)){factor=aliases.get(fixes.get(suffix));source="SCHEMA_CORRECTED";out.put("corrections",new JSONArray().put(new JSONObject().put("from_text",m.group(2)).put("to_text",fixes.get(suffix)).put("requires_confirmation",true)));issue(out,"INFERRED_UNIT_REQUIRES_REVIEW");}
            else{issue(out,"UNKNOWN_OR_WRONG_UNIT");return;}
        }
        value*=factor;if(!Double.isFinite(value)){issue(out,"INVALID_NUMBER");return;}
        out.put("value",value).put("unit",expected).put("unit_source",source).put("source_unit",m.group(2)).put("grammar_version","mobile-field-units-v1");
        JSONArray range=rule.getJSONArray("ocr_sanity_range");if(value<range.getDouble(0)||value>range.getDouble(1))issue(out,"OUTSIDE_OCR_SANITY_RANGE");
        if(typeInteger(rule)&&value!=Math.rint(value))issue(out,"INTEGER_REQUIRED");
        // Never turn a bare 51789 into 5178. Preserve digits and flag the range.
    }
    private static boolean typeInteger(JSONObject rule){return rule.optString("type").equals("integer");}
    public static String parseDate(String raw){
        String text=fold(raw);Matcher m=Pattern.compile("(\\d{1,4})\\s*([/.-])\\s*(\\d{1,2})\\s*\\2\\s*(\\d{1,4})").matcher(text);
        int day,month,year;
        if(m.matches()){
            int a=Integer.parseInt(m.group(1)),b=Integer.parseInt(m.group(3)),c=Integer.parseInt(m.group(4));if(m.group(1).length()==4){year=a;month=b;day=c;}else{if(m.group(4).length()!=4)return null;year=c;day=a;month=b;if(month>12&&day<=12){month=a;day=b;}}
        }else{
            String[] months={"january janvier يناير jan","february fevrier فبراير feb fev","march mars مارس mar","april avril ابريل apr avr","may mai مايو","june juin يونيو jun","july juillet يوليو jul juil","august aout اغسطس aug","september septembre سبتمبر sep sept","october octobre اكتوبر oct","november novembre نوفمبر nov","december decembre ديسمبر dec"};
            text=text.replaceAll("(?<=\\d)(st|nd|rd|th|er)\\b","").replace(',',' ').trim();String[] tokens=text.split("\\s+");if(tokens.length!=3)return null;month=0;List<Integer> nums=new ArrayList<>();for(String token:tokens){boolean found=false;for(int i=0;i<months.length;i++)if(Arrays.asList(months[i].split(" ")).contains(token.replaceAll("\\.$",""))){if(month!=0)return null;month=i+1;found=true;break;}if(!found){try{nums.add(Integer.parseInt(token));}catch(NumberFormatException e){return null;}}}if(month==0||nums.size()!=2)return null;day=nums.get(0);year=nums.get(1);
        }
        try{return year>=1900&&year<=2100?LocalDate.of(year,month,day).toString():null;}catch(Exception e){return null;}
    }
}
