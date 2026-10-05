package org.dayone.midwife;

import org.json.*;

/** Explicit form selection after failed recognition; keeps the original capture. */
final class ManualRecovery {
    private ManualRecovery() {}
    static JSONObject prepare(JSONObject original,String formId,JSONObject schema)throws Exception {
        if(!original.optString("state").equals("PROCESSING_FAILED"))throw new IllegalStateException("This page has changed. Reopen its current results.");
        JSONObject record=new JSONObject(original.toString());
        record.put("manual",true).put("mock",false).put("form_id",formId)
                .put("fields",SchemaCatalog.blank(schema.getJSONObject("fields")));
        EncryptedStore.state(record,"MANUAL_REVIEW_REQUIRED");
        return record;
    }
}
