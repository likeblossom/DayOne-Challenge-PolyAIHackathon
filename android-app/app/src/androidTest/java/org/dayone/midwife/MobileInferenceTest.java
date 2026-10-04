package org.dayone.midwife;

import android.test.AndroidTestCase;
import android.graphics.*;
import org.dayone.midwife.model.PresetForm;
import org.json.*;
import java.io.*;
import java.nio.file.Files;

/** Explicit real-model tests. Install pack + specimen fixtures before selecting this class. */
public final class MobileInferenceTest extends AndroidTestCase {
    public void testDemoCandidate()throws Exception {
        File fixture=new File(getContext().getFilesDir(),"demo-candidate.png");assertTrue(fixture.isFile());
        SchemaCatalog catalog=new SchemaCatalog(getContext());PresetForm result=new OnDeviceFormParser(getContext(),catalog).parse(Files.readAllBytes(fixture.toPath()),"ignored");
        JSONObject output=new JSONObject().put("form_id",result.formId).put("fields",result.toJson()).put("metadata",result.extractionMetadata());
        try(FileWriter writer=new FileWriter(new File(getContext().getFilesDir(),"demo-candidate-result.json"))){writer.write(output.toString(2));}
        catalog.validate(result.formId,result.toJson());
    }
    public void testNumericRecordId()throws Exception {
        OnDeviceModels models=new OnDeviceModels(getContext());models.verify();
        Bitmap crop=BitmapFactory.decodeFile(new File(getContext().getFilesDir(),"record-id-diagnostic/android-crop.png").getPath());assertNotNull(crop);
        try(MobileOcr reader=new MobileOcr(models,"numeric")){assertEquals("2026-823-001",reader.read(crop).getString("text"));}finally{crop.recycle();}
        assertTrue(MobileRouting.numeric("record_code","string"));
    }
    /** Read-only diagnostic, restricted to the supplied form-01 specimen by SHA-256. */
    public void testExportSpecimenRecordId()throws Exception {
        EncryptedStore store=new EncryptedStore(getContext());JSONObject selected=null;byte[] image=null;
        for(JSONObject record:store.records()) {
            if(!record.has("image_file")||!record.has("fields"))continue;
            byte[] bytes=store.read(record.getString("image_file"));
            byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder hex=new StringBuilder();
            for(byte b:hash)hex.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
            if(hex.toString().equals("4434209ee4bca0d638a1b396f8cf7bbaa3435fd7c67a67a454d4f814c8a34db7")){selected=record;image=bytes;}
        }
        assertNotNull("No completed record matching the form-01 specimen",selected);
        JSONObject field=selected.getJSONObject("fields").getJSONObject("record_code");
        File folder=new File(getContext().getFilesDir(),"record-id-diagnostic");folder.mkdirs();
        try(FileWriter writer=new FileWriter(new File(folder,"field.json"))){writer.write(field.toString(2));}
        Bitmap page=MobileImages.decode(image),crop=MobileImages.crop(page,MobileImages.points(field.getJSONArray("crop_quad")),.12);
        try(FileOutputStream out=new FileOutputStream(new File(folder,"android-crop.png"))){crop.compress(Bitmap.CompressFormat.PNG,100,out);}
        java.nio.FloatBuffer pixels=MobileImages.tensor(crop,384,384,new double[]{.5,.5,.5},new double[]{.5,.5,.5});
        java.nio.ByteBuffer raw=java.nio.ByteBuffer.allocate(pixels.capacity()*4).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        for(int i=0;i<pixels.capacity();i++)raw.putFloat(pixels.get(i));
        try(FileOutputStream out=new FileOutputStream(new File(folder,"android-pixels.f32"))){out.write(raw.array());}
        crop.recycle();page.recycle();
    }
    public void testAllForms()throws Exception {
        SchemaCatalog catalog=new SchemaCatalog(getContext());OnDeviceFormParser parser=new OnDeviceFormParser(getContext(),catalog);
        String[] ids={"pregnancy_postpartum_monitoring","identification_and_history","current_pregnancy","labor_and_delivery","early_postpartum_mother","early_postnatal_newborn","late_postpartum_mother","late_postnatal_newborn"};
        for(int i=0;i<ids.length;i++){
            String name=String.format(java.util.Locale.ROOT,"mobile-test-form%02d",i+1);File fixture=new File(getContext().getFilesDir(),name+".png");assertTrue("Install eight-form fixtures first",fixture.isFile());
            PresetForm result=parser.parse(Files.readAllBytes(fixture.toPath()),"ignored");assertEquals(ids[i],result.formId);catalog.validate(result.formId,result.toJson());
            JSONObject output=new JSONObject().put("form_id",result.formId).put("fields",result.toJson()).put("metadata",result.extractionMetadata());
            try(FileWriter writer=new FileWriter(new File(getContext().getFilesDir(),name+"-result.json"))){writer.write(output.toString(2));}
        }
    }
    public void testNumericReader()throws Exception {
        OnDeviceModels models=new OnDeviceModels(getContext());models.verify();
        File fixture=new File(getContext().getFilesDir(),"mobile-test-numeric.png");assertTrue("Push numeric fixture first",fixture.isFile());
        Bitmap image=BitmapFactory.decodeFile(fixture.getPath());JSONObject prediction;
        try(MobileOcr reader=new MobileOcr(models,"numeric")){prediction=reader.read(image);}finally{image.recycle();}
        try(FileWriter writer=new FileWriter(new File(getContext().getFilesDir(),"mobile-test-numeric-result.json"))){writer.write(prediction.toString(2));}
        assertEquals("3485 g",prediction.getString("text").replaceAll("\\s+"," "));
    }
    public void testFullPhoto()throws Exception {
        File fixture=new File(getContext().getFilesDir(),"mobile-test-form06.png");assertTrue("Push form-06 fixture first",fixture.isFile());
        SchemaCatalog catalog=new SchemaCatalog(getContext());PresetForm result=new OnDeviceFormParser(getContext(),catalog).parse(Files.readAllBytes(fixture.toPath()),"ignored");
        assertEquals("early_postnatal_newborn",result.formId);catalog.validate(result.formId,result.toJson());
        JSONObject output=new JSONObject().put("form_id",result.formId).put("fields",result.toJson()).put("metadata",result.extractionMetadata());
        try(FileWriter writer=new FileWriter(new File(getContext().getFilesDir(),"mobile-test-form06-result.json"))){writer.write(output.toString(2));}
        assertTrue(result.toJson().getJSONObject("weight_g").has("confidence"));assertTrue(result.toJson().getJSONObject("weight_g").has("status"));
        assertTrue("Real OCR should produce candidates",result.toJson().getJSONObject("weight_g").has("raw_candidates"));
    }
}
