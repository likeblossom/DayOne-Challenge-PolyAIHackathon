package org.dayone.midwife;

import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public final class RecordLibraryTest {
    private static JSONObject field(Object value)throws Exception{return new JSONObject().put("value",value).put("status","KNOWN").put("confidence",.9);}

    @Test public void extractedIdentifierBecomesTitle()throws Exception{
        JSONObject record=new JSONObject().put("captured_at","2026-10-05T16:30:00Z").put("fields",new JSONObject()
            .put("record_code",field("  2026-823-001  ")));
        assertEquals("2026-823-001",RecordLibrary.title(record));
    }
    @Test public void patientNameHasPriorityAcrossNestedFields()throws Exception{
        JSONObject nested=new JSONObject().put("record_code",field("R-1")).put("patient_name",field("Amina El Idrissi"));
        JSONObject record=new JSONObject().put("captured_at","2026-10-05T16:30:00Z").put("fields",new JSONObject().put("identity",nested));
        assertEquals("Amina El Idrissi",RecordLibrary.title(record));
    }
    @Test public void absentIdentifierFallsBackToDateAndTime()throws Exception{
        JSONObject record=new JSONObject().put("captured_at","2026-10-05T16:30:00Z").put("fields",new JSONObject().put("weight_g",field(3200)));
        assertTrue(RecordLibrary.title(record).matches("\\d{4}-\\d{2}-\\d{2} \\d{2}-\\d{2}"));
        assertFalse(RecordLibrary.weekKey(record).isEmpty());assertFalse(RecordLibrary.dayLabel(record).isEmpty());
    }
}
