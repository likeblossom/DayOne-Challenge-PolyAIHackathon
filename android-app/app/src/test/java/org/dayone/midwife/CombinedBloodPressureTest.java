package org.dayone.midwife;
import org.junit.Test;
import org.json.*;
import static org.junit.Assert.*;

public class CombinedBloodPressureTest {
    private MobileGrammar grammar()throws Exception {
        JSONObject rule=new JSONObject("{\"type\":\"double\",\"unit\":\"mmHg\",\"unit_aliases\":{\"mmHg\":1},\"unit_policy\":{\"ocr_substitutions\":{}},\"ocr_sanity_range\":[20,300]}");
        return new MobileGrammar(new JSONObject().put("rules",new JSONObject().put("visits[].systolic_bp_mmhg",rule).put("visits[].diastolic_bp_mmhg",rule))
                .put("unknown",new JSONArray()).put("not_applicable",new JSONArray()));
    }
    private JSONObject fields(String raw)throws Exception {
        JSONObject source=grammar().parse("visits[2].systolic_bp_mmhg",raw,.9).put("ocr",new JSONObject().put("text",raw).put("warnings",new JSONArray()));
        return new JSONObject().put("visits[2].systolic_bp_mmhg",source).put("visits[2].diastolic_bp_mmhg",MobileGrammar.field(null,0));
    }
    @Test public void explicitPairPopulatesBothFieldsWithoutInventingDigits()throws Exception {
        JSONObject fields=fields("١٠٤/٧٤ mmHg");CombinedBloodPressure.apply(fields,grammar());
        assertEquals(104,fields.getJSONObject("visits[2].systolic_bp_mmhg").getDouble("value"),0);
        assertEquals(74,fields.getJSONObject("visits[2].diastolic_bp_mmhg").getDouble("value"),0);
        assertEquals("KNOWN",fields.getJSONObject("visits[2].diastolic_bp_mmhg").getString("status"));
        assertEquals("١٠٤/٧٤ mmHg",fields.getJSONObject("visits[2].diastolic_bp_mmhg").getString("raw_text"));
    }
    @Test public void splitPairPreservesExactCropEvidence()throws Exception {
        JSONObject fields=fields("104/74");
        fields.getJSONObject("visits[2].systolic_bp_mmhg").put("crop_horizontal_pad",.5)
                .put("localization",new JSONObject().put("anchor_confidence",.9));
        CombinedBloodPressure.apply(fields,grammar());
        for(String key:new String[]{"visits[2].systolic_bp_mmhg","visits[2].diastolic_bp_mmhg"}) {
            assertEquals(.5,fields.getJSONObject(key).getDouble("crop_horizontal_pad"),0);
            assertEquals(.9,fields.getJSONObject(key).getJSONObject("localization").getDouble("anchor_confidence"),0);
        }
    }
    @Test public void malformedPairAndConflictingIndependentValueAreNotOverwritten()throws Exception {
        JSONObject fields=fields("104/?4");CombinedBloodPressure.apply(fields,grammar());assertTrue(fields.getJSONObject("visits[2].diastolic_bp_mmhg").isNull("value"));
        fields=fields("104/74");fields.put("visits[2].diastolic_bp_mmhg",MobileGrammar.field(80,.9));
        CombinedBloodPressure.apply(fields,grammar());assertEquals(80,fields.getJSONObject("visits[2].diastolic_bp_mmhg").getDouble("value"),0);
        assertTrue(fields.getJSONObject("visits[2].diastolic_bp_mmhg").getJSONArray("issues").toString().contains("BP_PAIR_CONFLICT"));
    }
    @Test public void shortNumbersAreNotMultipliedAndReversedPairIsFlagged()throws Exception {
        JSONObject fields=fields("12/8");CombinedBloodPressure.apply(fields,grammar());assertEquals(12,fields.getJSONObject("visits[2].systolic_bp_mmhg").getDouble("value"),0);
        assertEquals("NEEDS_REVIEW",fields.getJSONObject("visits[2].systolic_bp_mmhg").getString("status"));
        fields=fields("70/110");CombinedBloodPressure.apply(fields,grammar());MobileRelations.apply(fields);
        assertTrue(fields.getJSONObject("visits[2].systolic_bp_mmhg").getJSONArray("issues").toString().contains("BP_ORDER_CONFLICT"));
    }
}
