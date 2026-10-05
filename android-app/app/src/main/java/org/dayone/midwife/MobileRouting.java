package org.dayone.midwife;
import org.json.*;
public final class MobileRouting {
    private MobileRouting(){}
    public static boolean numeric(String key,String type){return key.equals("record_code")||type.equals("double")||type.equals("integer");}
    public static JSONArray outputWarnings(String text,boolean generationLimit,String route) {
        JSONArray warnings=new JSONArray();
        if(generationLimit)warnings.put("OCR_GENERATION_LIMIT");
        if(text.codePoints().noneMatch(Character::isLetterOrDigit))warnings.put("OCR_NO_ALPHANUMERIC_CONTENT");
        if(java.util.regex.Pattern.compile("(\\p{L}{2,})(?:\\s+\\1){3,}").matcher(text).find())warnings.put("OCR_REPETITION");
        if(text.contains("##")||text.contains("[MISSING_PAGE")||text.contains("![")||text.contains("***"))warnings.put("OCR_GENERATION_ARTIFACT");
        if(text.indexOf('\ufffd')>=0)warnings.put("OCR_CORRUPTED_TEXT");
        boolean opposite=text.codePoints().filter(Character::isLetter).anyMatch(cp ->
                Character.UnicodeScript.of(cp)==(route.equals("arabic")?Character.UnicodeScript.LATIN:Character.UnicodeScript.ARABIC));
        if((route.equals("arabic")||route.equals("latin"))&&opposite)warnings.put("OCR_SCRIPT_MISMATCH");
        return warnings;
    }
    /** Uncalibrated fallback heuristic: require a clear reader winner, not just a valid string. */
    public static boolean resolvedByReaders(JSONObject winner,JSONArray attempts)throws JSONException {
        if(winner.isNull("value")||winner.getJSONArray("issues").length()!=0||attempts.length()<2)return false;
        JSONObject ocr=winner.getJSONObject("ocr");String model=ocr.getString("model"),text=ocr.getString("text");
        double score=ocr.getDouble("token_confidence"),runner=0;boolean letters=false;
        if(!model.equals("latin")&&!model.equals("arabic"))return false;
        for(int i=0;i<text.length();i++)if(Character.isLetter(text.charAt(i))){letters=true;Character.UnicodeScript script=Character.UnicodeScript.of(text.charAt(i));if(script!=(model.equals("latin")?Character.UnicodeScript.LATIN:Character.UnicodeScript.ARABIC))return false;}
        for(int i=0;i<attempts.length();i++){JSONObject a=attempts.getJSONObject(i);if(!a.getString("model").equals(model)&&(a.optJSONArray("warnings")==null||a.getJSONArray("warnings").length()==0))runner=Math.max(runner,a.getDouble("token_confidence"));}
        return letters&&score>=MobileGrammar.ACCEPT_CONFIDENCE&&runner<MobileGrammar.ACCEPT_CONFIDENCE&&score-runner>=.20;
    }
}
