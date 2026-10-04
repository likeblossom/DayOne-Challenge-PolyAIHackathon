package org.dayone.midwife;
import org.json.*;
public final class MobileRouting {
    private MobileRouting(){}
    public static boolean numeric(String key,String type){return key.equals("record_code")||type.equals("double")||type.equals("integer");}
    /** Uncalibrated fallback heuristic: require a clear reader winner, not just a valid string. */
    public static boolean resolvedByReaders(JSONObject winner,JSONArray attempts)throws JSONException {
        if(winner.isNull("value")||winner.getJSONArray("issues").length()!=0||attempts.length()<2)return false;
        JSONObject ocr=winner.getJSONObject("ocr");String model=ocr.getString("model"),text=ocr.getString("text");
        double score=ocr.getDouble("token_confidence"),runner=0;boolean letters=false;
        if(!model.equals("latin")&&!model.equals("arabic"))return false;
        for(int i=0;i<text.length();i++)if(Character.isLetter(text.charAt(i))){letters=true;Character.UnicodeScript script=Character.UnicodeScript.of(text.charAt(i));if(script!=(model.equals("latin")?Character.UnicodeScript.LATIN:Character.UnicodeScript.ARABIC))return false;}
        for(int i=0;i<attempts.length();i++){JSONObject a=attempts.getJSONObject(i);if(!a.getString("model").equals(model))runner=Math.max(runner,a.getDouble("token_confidence"));}
        return letters&&score>=MobileGrammar.ACCEPT_CONFIDENCE&&runner<MobileGrammar.ACCEPT_CONFIDENCE&&score-runner>=.20;
    }
}
