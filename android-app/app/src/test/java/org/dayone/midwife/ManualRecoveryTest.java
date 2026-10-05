package org.dayone.midwife;
import org.junit.Test;
import org.json.*;
import static org.junit.Assert.*;

public class ManualRecoveryTest {
    private JSONObject schema()throws Exception {return new JSONObject("{\"fields\":{\"pulse_bpm\":{\"type\":\"integer\"}}}");}
    @Test public void chosenFormReplacesPlaceholderWithoutLosingCaptureOrChangingOriginal()throws Exception {
        JSONObject original=new JSONObject().put("id","fixture").put("state","PROCESSING_FAILED")
                .put("form_id","late_postnatal_newborn").put("image_file","fixture.image.enc")
                .put("document_id","document").put("patient_code","random-code").put("processing_error","timeout");
        JSONObject result=ManualRecovery.prepare(original,"early_postpartum_mother",schema());
        assertEquals("early_postpartum_mother",result.getString("form_id"));
        assertEquals("fixture.image.enc",result.getString("image_file"));
        assertEquals("document",result.getString("document_id"));assertEquals("random-code",result.getString("patient_code"));
        assertEquals("MANUAL_REVIEW_REQUIRED",result.getString("state"));assertTrue(result.getBoolean("manual"));assertFalse(result.getBoolean("mock"));
        assertTrue(result.getJSONObject("fields").getJSONObject("pulse_bpm").isNull("value"));
        assertEquals("late_postnatal_newborn",original.getString("form_id"));assertFalse(original.has("fields"));
    }
    @Test public void completedOrSupersededRecordsCannotBeResetByStaleDialog()throws Exception {
        for(String state:new String[]{"NEEDS_REVIEW","REGISTERED","SYNCED","SUPERSEDED","PENDING_AI"}) {
            JSONObject record=new JSONObject().put("state",state);
            try{ManualRecovery.prepare(record,"early_postpartum_mother",schema());fail("Reset "+state);}catch(IllegalStateException expected){}
            assertEquals(state,record.getString("state"));
        }
    }
}
