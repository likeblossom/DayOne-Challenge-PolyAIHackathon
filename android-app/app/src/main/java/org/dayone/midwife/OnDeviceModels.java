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
        directory=new File(context.getFilesDir(), "sanad-models-v1");
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
        if(!file("manifest.json").isFile())throw new IOException("Install the Sanad model pack first ("+directory+"). Photo OCR is unavailable; manual entry remains available.");
        JSONObject manifest=json("manifest.json");if(manifest.getInt("version")!=1)throw new IOException("Unsupported model pack");
        if(!file("routing.json").isFile())throw new IOException("Install the eight-form Sanad model pack; this older pack contains only form 06.");
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
            options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.BASIC_OPT);
            options.setCPUArenaAllocator(false);options.setMemoryPatternOptimization(false);
            return environment.createSession(file(relative).getPath(),options);
        }
    }
}
