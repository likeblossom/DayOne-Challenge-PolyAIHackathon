package org.dayone.midwife;

import android.test.AndroidTestCase;
import android.os.Debug;
import android.os.SystemClock;
import org.dayone.midwife.model.PresetForm;
import org.json.JSONObject;
import java.io.*;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;

/** Real-model benchmark isolated from the encrypted user-record store. */
public final class BenchmarkTest extends AndroidTestCase {
    public void testClassifier() throws Exception {
        File folder = new File(getContext().getFilesDir(), "benchmark");
        JSONObject request = OnDeviceModels.json(new File(folder, "request.json"));
        android.graphics.Bitmap page = MobileImages.decode(checkedImage(folder,request));
        OnDeviceModels models = new OnDeviceModels(getContext(),request.optString("model_directory","sanad-models-v1"));
        int size = models.json("forms.json").getInt("size");
        android.graphics.Bitmap input = MobileImages.fitAntialiased(page, size, size, android.graphics.Color.WHITE);
        try (OutputStream out = new FileOutputStream(new File(folder, "classifier.png"))) {
            input.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
        }
        try (MobileVision.Classifier classifier = new MobileVision.Classifier(models, "forms")) {
            MobileVision.Prediction prediction = classifier.predict(page);
            JSONObject result = new JSONObject().put("case_id", request.getString("case_id"))
                    .put("run_id",request.getString("run_id"))
                    .put("status", "ok").put("label", prediction.label).put("confidence", prediction.confidence);
            try (FileWriter writer = new FileWriter(new File(folder, "result.json"))) {
                writer.write(result.toString(2));
            }
        } finally { input.recycle(); page.recycle(); }
    }
    public void testCase() throws Exception {
        File folder = new File(getContext().getFilesDir(), "benchmark");
        JSONObject request = new JSONObject(new String(Files.readAllBytes(
                new File(folder, "request.json").toPath()), StandardCharsets.UTF_8));
        JSONObject result = new JSONObject().put("case_id", request.getString("case_id"))
                .put("run_id",request.getString("run_id"));
        long start = SystemClock.elapsedRealtime();
        Throwable failure = null;
        try {
            SchemaCatalog catalog = new SchemaCatalog(getContext());
            OnDeviceModels models=new OnDeviceModels(getContext(),request.optString("model_directory","sanad-models-v1"));
            PresetForm form = new OnDeviceFormParser(catalog,models,(done,total)->{}).parse(
                    checkedImage(folder,request), "ignored");
            catalog.validate(form.formId, form.toJson());
            result.put("status", "ok").put("form_id", form.formId)
                    .put("fields", form.toJson()).put("metadata", form.extractionMetadata());
            if(request.optBoolean("capture_crops")) {
                android.graphics.Bitmap page=MobileImages.decode(Files.readAllBytes(new File(folder,"input.png").toPath()));
                try {
                    File crops=new File(folder,"crops/"+request.getString("case_id")+"/"+request.getString("run_id"));
                    if(!crops.isDirectory()&&!crops.mkdirs())throw new IOException("Cannot create crop evidence folder");
                    dumpCrops(form.toJson(),"",page,crops,models);
                    JSONObject marks=form.extractionMetadata().optJSONObject("mark_observations");
                    if(marks!=null)for(java.util.Iterator<String> it=marks.keys();it.hasNext();) {
                        String key=it.next();JSONObject observation=marks.getJSONObject(key);
                        if(!observation.has("quad"))continue;
                        android.graphics.Bitmap crop=MobileImages.crop(page,MobileImages.points(observation.getJSONArray("quad")),0);
                        try{saveBitmap(crop,new File(crops,"mark_"+key.replaceAll("[^A-Za-z0-9_-]","_")+".png"));}finally{crop.recycle();}
                    }
                } finally { page.recycle(); }
            }
        } catch (Throwable error) {
            failure = error;
            StringWriter stack = new StringWriter();
            error.printStackTrace(new PrintWriter(stack));
            result.put("status", "error").put("error", stack.toString())
                    .put("error_type",error.getClass().getSimpleName()).put("error_message",String.valueOf(error.getMessage()));
        } finally {
            result.put("elapsed_ms", SystemClock.elapsedRealtime() - start)
                    .put("final_pss_kb", Debug.getPss());
            try (FileWriter writer = new FileWriter(new File(folder, "result.json"))) {
                writer.write(result.toString(2));
            }
        }
        if (failure != null) fail(failure.toString());
    }
    private static byte[] checkedImage(File folder,JSONObject request)throws Exception {
        byte[] bytes=Files.readAllBytes(new File(folder,"input.png").toPath());
        byte[] digest=java.security.MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder hex=new StringBuilder();for(byte b:digest)hex.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        if(!hex.toString().equals(request.getString("sha256")))throw new IOException("Benchmark image checksum mismatch");
        return bytes;
    }
    private void dumpCrops(Object node,String path,android.graphics.Bitmap page,File folder,OnDeviceModels models)throws Exception {
        if(node instanceof org.json.JSONArray) {
            org.json.JSONArray array=(org.json.JSONArray)node;
            for(int i=0;i<array.length();i++)dumpCrops(array.get(i),path+"["+i+"]",page,folder,models);
        } else if(node instanceof JSONObject) {
            JSONObject object=(JSONObject)node;
            if(object.has("crop_quad")) {
                String name=path.replaceAll("[^A-Za-z0-9_-]","_");
                android.graphics.Bitmap crop=MobileImages.crop(page,MobileImages.points(object.getJSONArray("crop_quad")),.12,object.optDouble("crop_horizontal_pad",.15));
                try {
                    saveBitmap(crop,new File(folder,name+".png"));
                    org.json.JSONArray candidates=object.getJSONArray("raw_candidates");
                    for(int i=0;i<candidates.length();i++) {
                        String route=candidates.getJSONObject(i).getString("model");
                        JSONObject config=models.json(route+"/reader.json");
                        android.graphics.Bitmap input=MobileOcr.prepareInput(crop,config);
                        try { saveBitmap(input,new File(folder,name+"_"+route+"_input.png")); }
                        finally { if(input!=crop)input.recycle(); }
                    }
                } finally { crop.recycle(); }
            } else if(!object.has("status")) {
                for(java.util.Iterator<String> it=object.keys();it.hasNext();) {
                    String key=it.next();dumpCrops(object.get(key),path.isEmpty()?key:path+"."+key,page,folder,models);
                }
            }
        }
    }
    private static void saveBitmap(android.graphics.Bitmap image,File target)throws IOException {
        try(OutputStream output=new FileOutputStream(target)) {
            if(!image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,output))throw new IOException("PNG encoding failed");
        }
    }
}
