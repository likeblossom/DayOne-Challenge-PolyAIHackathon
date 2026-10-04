package org.dayone.midwife;
import android.test.AndroidTestCase;
import org.json.*;

/** Explicit live USB test; uploads one clearly labelled synthetic smoke record. */
public final class UsbSyncTest extends AndroidTestCase {
    public void testUsbCommitAndDuplicate()throws Exception {
        assertTrue("PC server and adb reverse required",new UsbDatabaseSink(getContext()).checkConnection());
        JSONObject record=new JSONObject().put("id","sanad-usb-smoke-v1").put("form_id","pregnancy_postpartum_monitoring").put("patient_code","USB-TEST-NOT-A-PATIENT").put("confirmed_at","2026-10-04T12:00:00Z").put("state","REGISTERED").put("test_record",true)
            .put("fields",new JSONObject().put("record_code",new JSONObject().put("value","2026-823-001").put("status","KNOWN").put("confidence",1).put("human_reviewed",true)));
        UsbDatabaseSink sink=new UsbDatabaseSink(getContext());sink.upload(record);assertTrue(record.getJSONObject("pc_receipt").getBoolean("committed"));sink.upload(record);
    }
    public void testDisconnectedUsbKeepsOffline()throws Exception {
        assertFalse("Remove adb reverse before running this test",SyncEngine.probe(getContext()));
    }
}
