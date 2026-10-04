package org.dayone.midwife;
import org.junit.Test;
import org.json.*;
import static org.junit.Assert.*;
public final class MobileRoutingTest {
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
