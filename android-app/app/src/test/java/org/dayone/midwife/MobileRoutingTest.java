package org.dayone.midwife;
import org.junit.Test;
import org.json.*;
import static org.junit.Assert.*;
public final class MobileRoutingTest {
    @Test public void artifactsAndWrongScriptAreRejectedButRepeatedDigitsAreValid()throws Exception {
        assertTrue(MobileRouting.outputWarnings("#### ١",false,"arabic").toString().contains("OCR_GENERATION_ARTIFACT"));
        assertTrue(MobileRouting.outputWarnings("RAS",false,"arabic").toString().contains("OCR_SCRIPT_MISMATCH"));
        assertTrue(MobileRouting.outputWarnings("...",false,"latin").toString().contains("OCR_NO_ALPHANUMERIC_CONTENT"));
        assertTrue(MobileRouting.outputWarnings("test test test test",false,"latin").toString().contains("OCR_REPETITION"));
        assertEquals(0,MobileRouting.outputWarnings("11111111",false,"numeric").length());
        assertEquals(0,MobileRouting.outputWarnings("36.7 °C",false,"numeric").length());
        assertEquals(0,MobileRouting.outputWarnings("أحمد",false,"arabic").length());
    }
    @Test public void highScoringArtifactCannotBlockCleanFallback()throws Exception {
        JSONObject latin=new JSONObject().put("model","latin").put("text","RAS").put("token_confidence",.91).put("warnings",new JSONArray());
        JSONObject artifact=new JSONObject().put("model","arabic").put("text","#### ١").put("token_confidence",.99).put("warnings",new JSONArray().put("OCR_GENERATION_ARTIFACT"));
        JSONObject winner=MobileGrammar.field("RAS",.91).put("ocr",latin);
        assertTrue(MobileRouting.resolvedByReaders(winner,new JSONArray().put(latin).put(artifact)));
    }
    @Test public void dualReadersMustHaveClearWinner()throws Exception {
        JSONObject latin=new JSONObject().put("model","latin").put("text","DR Bni Ahmed").put("token_confidence",.81);
        JSONObject arabic=new JSONObject().put("model","arabic").put("text","نص").put("token_confidence",.51);
        JSONObject winner=MobileGrammar.field("DR Bni Ahmed",.81).put("ocr",latin);JSONArray attempts=new JSONArray().put(latin).put(arabic);
        assertTrue(MobileRouting.resolvedByReaders(winner,attempts));
        arabic.put("token_confidence",.72);assertFalse(MobileRouting.resolvedByReaders(winner,attempts));
        arabic.put("token_confidence",.51);MobileGrammar.issue(winner,"INVALID_FIELD_PATTERN");assertFalse(MobileRouting.resolvedByReaders(winner,attempts));
    }
    @Test public void recordCodesUseNumericWithoutChangingStorageType(){assertTrue(MobileRouting.numeric("record_code","string"));assertTrue(MobileRouting.numeric("weight_g","double"));assertFalse(MobileRouting.numeric("region","string"));assertFalse(MobileRouting.numeric("consultation_date","date"));}
}
