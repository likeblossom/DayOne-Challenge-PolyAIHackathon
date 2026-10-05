package org.dayone.midwife;

import android.test.AndroidTestCase;
import org.dayone.midwife.model.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;

/** Runs on Android to exercise real Keystore, files, schema assets, and connectivity. */
public final class WorkflowTest extends AndroidTestCase {
    private EncryptedStore store;
    private File dir;
    @Override protected void setUp() throws Exception {
        super.setUp(); dir=new File(getContext().getFilesDir(),"test-vault-"+UUID.randomUUID());
        store=new EncryptedStore(getContext(),dir.getName());
    }
    @Override protected void tearDown() throws Exception {
        File[] files=dir.listFiles(); if(files!=null) for(File f:files) f.delete(); dir.delete(); super.tearDown();
    }
    public void testAllEightMocksValidateAndUseDistinctClasses() throws Exception {
        SchemaCatalog catalog=new SchemaCatalog(getContext()); Set<Class<?>> classes=new HashSet<>();
        for(String id:catalog.forms.keySet()) {
            PresetForm form=new MockFormParser(catalog).parse(new byte[0],id);
            classes.add(form.getClass()); catalog.validate(id,form.toJson());
            JSONObject copy=form.toJson(); copy.put("injected_identifier","not allowed");
            assertFalse(form.toJson().has("injected_identifier"));
            assertTrue(SchemaCatalog.rows(catalog.schema(id).getJSONObject("fields"),form.toJson()).stream().anyMatch(SchemaCatalog.Row::needsReview));
        }
        assertEquals(8,classes.size());
    }
    public void testEveryFieldInAllEightFormsHasAClinicalReviewSection()throws Exception{
        SchemaCatalog catalog=new SchemaCatalog(getContext());
        for(String id:catalog.forms.keySet()){
            JSONObject values=new MockFormParser(catalog).parse(new byte[0],id).toJson();
            for(SchemaCatalog.Row row:SchemaCatalog.rows(catalog.schema(id).getJSONObject("fields"),values))
                assertFalse(id+" / "+row.path,ReviewSections.title(id,row.path).equals("Additional information"));
        }
    }
    public void testOversizedSectionsSplitIntoBoundedNamedSubsections()throws Exception{
        SchemaCatalog catalog=new SchemaCatalog(getContext());
        for(String id:catalog.forms.keySet()){
            JSONObject values=new MockFormParser(catalog).parse(new byte[0],id).toJson();LinkedHashMap<String,List<SchemaCatalog.Row>> parents=new LinkedHashMap<>();
            for(SchemaCatalog.Row row:SchemaCatalog.rows(catalog.schema(id).getJSONObject("fields"),values))parents.computeIfAbsent(ReviewSections.title(id,row.path),k->new ArrayList<>()).add(row);
            for(Map.Entry<String,List<SchemaCatalog.Row>> parent:parents.entrySet())if(parent.getValue().size()>8){LinkedHashMap<String,List<SchemaCatalog.Row>> children=ReviewSections.subsections(id,parent.getKey(),parent.getValue());
                assertTrue(children.size()>1);for(Map.Entry<String,List<SchemaCatalog.Row>> child:children.entrySet()){assertFalse(child.getKey().trim().isEmpty());assertTrue(child.getKey(),child.getValue().size()<=8);}
                assertEquals(ReviewSections.minimumConfidencePercent(parent.getValue()),ReviewSections.minimumSubsectionConfidence(children));
            }
        }
    }
    public void testTypedFieldsAndNestedArrays() throws Exception {
        SchemaCatalog catalog=new SchemaCatalog(getContext());
        CurrentPregnancyForm form=(CurrentPregnancyForm)new MockFormParser(catalog).parse(new byte[0],"current_pregnancy");
        assertEquals(1,form.visits.size()); assertEquals(118.,form.visits.get(0).systolic_bp_mmhg.value,0.001);
        assertNotNull(form.last_menstrual_period_date.value);
        try { form.visits.clear(); fail("Typed array must be immutable"); } catch(UnsupportedOperationException expected) {}
    }
    public void testSchemaRejectsWrongTypesEnumsDatesAndIdentifiers() throws Exception {
        SchemaCatalog catalog=new SchemaCatalog(getContext()); JSONObject fields=SchemaCatalog.blank(catalog.schema("late_postnatal_newborn").getJSONObject("fields"));
        fields.put("weight_g",SchemaCatalog.envelope("bad",.99)); reject(catalog,fields);
        fields.put("weight_g",SchemaCatalog.envelope(4200.,.99)); fields.put("feeding_method",SchemaCatalog.envelope("INVALID",.99)); reject(catalog,fields);
        fields.put("feeding_method",SchemaCatalog.envelope("MIXED",.99)); fields.put("consultation_date",SchemaCatalog.envelope("2026-02-30",.99)); reject(catalog,fields);
        fields.put("consultation_date",SchemaCatalog.envelope("2026-10-04",.99)); fields.put("patient_name",SchemaCatalog.envelope("test",.99)); reject(catalog,fields);
        fields.remove("patient_name"); catalog.validate("late_postnatal_newborn",fields);
    }
    private void reject(SchemaCatalog catalog,JSONObject fields) throws Exception {
        try { catalog.validate("late_postnatal_newborn",fields); fail("Should reject invalid input"); } catch(IllegalArgumentException expected) {}
    }
    public void testEncryptedPersistenceAndTamperDetection() throws Exception {
        byte[] secret="synthetic registry original image".getBytes(StandardCharsets.UTF_8);
        store.write("photo.enc",secret);
        byte[] disk=Files.readAllBytes(new File(dir,"photo.enc").toPath());
        assertFalse(new String(disk,StandardCharsets.UTF_8).contains("synthetic registry"));
        EncryptedStore reopened=new EncryptedStore(getContext(),dir.getName()); assertTrue(Arrays.equals(secret,reopened.read("photo.enc")));
        disk[disk.length-1]^=1; Files.write(new File(dir,"photo.enc").toPath(),disk);
        try { reopened.read("photo.enc"); fail("Tampered ciphertext must fail closed"); } catch(javax.crypto.AEADBadTagException expected) {}
    }
    public void testRecordDeletionAlsoRemovesEncryptedImage()throws Exception{
        String id=UUID.randomUUID().toString(),image=id+".image.enc";store.write(image,new byte[]{1,2,3});
        JSONObject record=new JSONObject().put("id",id).put("image_file",image).put("captured_at",java.time.Instant.now().toString());store.save(record);
        assertTrue(store.deleteRecord(id));assertFalse(store.deleteRecord(id));
        try{store.get(id);fail("Deleted record remained");}catch(JSONException expected){}
        try{store.read(image);fail("Deleted image remained");}catch(FileNotFoundException expected){}
    }
    public void testOfflineQueueRestartAndIdempotentSync() throws Exception {
        JSONObject r=record("REGISTERED");store.save(r);
        EncryptedStore reopened=new EncryptedStore(getContext(),dir.getName());
        assertEquals("REGISTERED",reopened.records().get(0).getString("state"));
        final int[] uploads={0};
        RecordSink sink=item -> {uploads[0]++;item.put("pc_receipt",new JSONObject().put("committed",true));};
        assertEquals(1,SyncEngine.sync(getContext(),reopened,sink));
        assertEquals(0,SyncEngine.sync(getContext(),reopened,sink));
        assertEquals(1,uploads[0]);assertEquals("SYNCED",reopened.get(r.getString("id")).getString("state"));
    }
    public void testSyncFailureRetainsRecordAndRetrySucceeds() throws Exception {
        JSONObject r=record("REGISTERED");store.save(r);
        try {SyncEngine.sync(getContext(),store,item -> {throw new IOException("Disconnected USB");});fail();}catch(IOException expected){}
        assertEquals("SYNC_FAILED",store.get(r.getString("id")).getString("state"));
        assertEquals(1,SyncEngine.sync(getContext(),store,item -> item.put("pc_receipt",new JSONObject().put("committed",true))));
    }
    public void testUnconfirmedDraftNeverSyncs() throws Exception {
        JSONObject r=record("NEEDS_REVIEW");r.remove("confirmed_at");store.save(r);
        assertEquals(0,SyncEngine.sync(getContext(),store,item -> fail("Draft uploaded")));
    }
    public void testLegacySimulatedSyncTransfersToRealSink()throws Exception {
        JSONObject r=record("SYNCED");store.save(r);assertTrue(SyncEngine.pending(r));
        assertEquals(1,SyncEngine.sync(getContext(),store,item -> item.put("pc_receipt",new JSONObject().put("committed",true))));
        assertFalse(SyncEngine.pending(store.get(r.getString("id"))));
    }
    private JSONObject record(String state) throws Exception {
        JSONObject record=new JSONObject().put("id",UUID.randomUUID().toString()).put("captured_at",java.time.Instant.now().toString()).put("fields",new JSONObject()).put("confirmed_at",java.time.Instant.now().toString());
        EncryptedStore.state(record,state); return record;
    }
}
