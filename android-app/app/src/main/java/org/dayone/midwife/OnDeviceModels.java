package org.dayone.midwife;

import android.content.Context;
import ai.onnxruntime.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Explicit model pack, never downloaded automatically. Checkpoints are not APK assets. */
public final class OnDeviceModels {
    public final File directory;
    public final OrtEnvironment environment=OrtEnvironment.getEnvironment();
    public OnDeviceModels(Context context) {
        this(context,"sanad-models-v1");
    }
    OnDeviceModels(Context context,String name) {
        if(!name.equals("sanad-models-v1")&&!(BuildConfig.DEBUG&&name.matches("benchmark-models-[A-Za-z0-9_-]+")))throw new IllegalArgumentException("Invalid model directory");
        directory=new File(context.getFilesDir(),name);
    }
    public static JSONObject json(File path) throws Exception {
        try(InputStream in=new FileInputStream(path);ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);
            return new JSONObject(out.toString(StandardCharsets.UTF_8.name()));
        }
    }
    public JSONObject json(String path) throws Exception {return json(file(path));}
    public File file(String path) throws IOException {
        File f=new File(directory,path).getCanonicalFile();
        if(!f.getPath().startsWith(directory.getCanonicalPath()+File.separator))throw new IOException("Unsafe model path");
        return f;
    }
    public void verify() throws Exception {
        ModelPackInstaller.recover(directory.getParentFile());
        if(!file("manifest.json").isFile())throw new IOException("Import the Sanad model pack in Settings. Manual entry remains available.");
        if(directory.getName().equals("sanad-models-v1")&&!ModelPackInstaller.isCurrentManifest(directory.getParentFile()))throw new IOException("Import the model pack for this version of Sanad. Your saved records are unchanged.");
        JSONObject manifest=json("manifest.json");if(manifest.getInt("version")!=1)throw new IOException("Unsupported model pack");
        if(!file("routing.json").isFile())throw new IOException("Import the eight-form Sanad model pack; the installed pack is obsolete.");
        JSONObject files=manifest.getJSONObject("files");byte[] buffer=new byte[1024*1024];
        for(Iterator<String> it=files.keys();it.hasNext();) {
            String name=it.next();File f=file(name);JSONObject info=files.getJSONObject(name);
            if(!f.isFile() || f.length()!=info.getLong("bytes"))throw new IOException("Missing/incomplete model: "+name);
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            try(InputStream in=new FileInputStream(f)){int n;while((n=in.read(buffer))!=-1)digest.update(buffer,0,n);}
            StringBuilder hex=new StringBuilder();for(byte b:digest.digest())hex.append(String.format(Locale.ROOT,"%02x",b&255));
            if(!hex.toString().equals(info.getString("sha256")))throw new IOException("Model checksum mismatch: "+name);
        }
    }
    public OrtSession open(String relative) throws Exception {
        try(OrtSession.SessionOptions options=new OrtSession.SessionOptions()) {
            options.setIntraOpNumThreads(2);options.setInterOpNumThreads(1);
            JSONObject runtime=json("manifest.json").optJSONObject("runtime");
            String optimization=runtime==null?"basic":runtime.optString("optimization","basic");
            if(optimization.equals("basic"))options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.BASIC_OPT);
            else if(optimization.equals("extended"))options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.EXTENDED_OPT);
            else if(optimization.equals("all"))options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);
            else throw new IOException("Unsupported runtime optimization");
            options.setCPUArenaAllocator(false);options.setMemoryPatternOptimization(false);
            return environment.createSession(file(relative).getPath(),options);
        }
    }
}
