package org.dayone.midwife;

import android.test.AndroidTestCase;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.nio.file.Files;
import java.util.UUID;

/** The only real-vault fixture is uniquely named, never submitted, and removed in finally. */
public final class OcrServiceTest extends AndroidTestCase {
    public void testMissingCaptureNeverBecomesSampleData()throws Exception {
        EncryptedStore store=new EncryptedStore(getContext());
        String id="service-test-"+UUID.randomUUID();
        JSONObject record=new JSONObject().put("id",id).put("document_id",id)
                .put("patient_code","SYNTHETIC-TEST").put("mock",false)
                .put("form_id","pregnancy_postpartum_monitoring")
                .put("captured_at",java.time.Instant.now().toString());
        EncryptedStore.state(record,"CAPTURED");
        try {
            store.save(record);OcrService.enqueue(getContext(),id);
            long deadline=SystemClock.elapsedRealtime()+15_000;JSONObject output;
            do {
                Thread.sleep(100);output=store.get(id);
            }while(!output.optString("state").equals("PROCESSING_FAILED")&&SystemClock.elapsedRealtime()<deadline);
            assertEquals("PROCESSING_FAILED",output.getString("state"));
            assertFalse(output.optBoolean("mock"));assertFalse(output.has("fields"));
            assertTrue(output.getString("processing_error").contains("photo"));
        }finally{
            getContext().stopService(new android.content.Intent(getContext(),OcrService.class));
            synchronized(EncryptedStore.LOCK){JSONObject db=store.json("records.enc");db.remove(id);store.json("records.enc",db);}
        }
    }
    public void testRealPageSurvivesWithoutActivityAndDuplicateEnqueue()throws Exception {
        EncryptedStore store=new EncryptedStore(getContext());
        File fixtureDir=new File(getContext().getFilesDir(),"benchmark");
        JSONObject fixture=OnDeviceModels.json(new File(fixtureDir,"service_fixture.json"));
        byte[] input=Files.readAllBytes(new File(fixtureDir,"service_fixture.png").toPath());
        assertEquals("Wrong service-test image",fixture.getString("sha256"),ModelPackInstaller.hex(java.security.MessageDigest.getInstance("SHA-256").digest(input)));
        String expectedForm=fixture.getString("form_id");
        String id="service-test-"+UUID.randomUUID(),image=id+".image.enc";
        JSONObject record=new JSONObject().put("id",id).put("document_id",id).put("patient_code","SYNTHETIC-TEST")
                .put("form_id",expectedForm).put("captured_at",java.time.Instant.now().toString())
                .put("image_file",image);
        EncryptedStore.state(record,"CAPTURED");
        try {
            store.write(image,input);
            store.save(record);
            OcrService.enqueue(getContext(),id);OcrService.enqueue(getContext(),id);
            long deadline=SystemClock.elapsedRealtime()+180_000;
            JSONObject output;
            do {
                Thread.sleep(500);output=store.get(id);
                if(output.optString("state").equals("PROCESSING_FAILED"))fail(output.optString("processing_error"));
            } while(!output.optString("state").equals("NEEDS_REVIEW")&&SystemClock.elapsedRealtime()<deadline);
            assertEquals("NEEDS_REVIEW",output.getString("state"));
            assertEquals(expectedForm,output.getString("form_id"));
            assertFalse(output.optBoolean("mock"));assertTrue(output.getJSONObject("fields").length()>0);
            assertFalse(output.has("confirmed_at"));
            int starts=0;for(int i=0;i<output.getJSONArray("lifecycle").length();i++)
                if(output.getJSONArray("lifecycle").getJSONObject(i).getString("state").equals("PENDING_AI"))starts++;
            assertEquals("Duplicate enqueue must not repeat OCR",1,starts);
            int lifecycleSize=output.getJSONArray("lifecycle").length();
            Thread.sleep(500);OcrService.enqueue(getContext(),id);Thread.sleep(1500);
            assertEquals("A late duplicate must not overwrite completed results",lifecycleSize,store.get(id).getJSONArray("lifecycle").length());
        } finally {
            // Never remove fixtures while the worker is still using them.
            getContext().stopService(new android.content.Intent(getContext(),OcrService.class));
            long deadline=SystemClock.elapsedRealtime()+15_000;
            while(!OcrService.progress(id).equals("Preparing your page…")&&SystemClock.elapsedRealtime()<deadline)Thread.sleep(100);
            synchronized(EncryptedStore.LOCK) {
                JSONObject db=store.json("records.enc");db.remove(id);store.json("records.enc",db);
                Files.deleteIfExists(new File(getContext().getFilesDir(),"vault/"+image).toPath());
            }
        }
    }
}
