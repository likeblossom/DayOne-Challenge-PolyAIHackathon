package org.dayone.midwife;

import android.test.AndroidTestCase;
import org.json.JSONObject;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Explicit deployment test: exercises the same streaming importer as Settings. */
public final class ModelPackImportTest extends AndroidTestCase {
    public void testExplicitLivePackImportPreservesVault()throws Exception {
        File files=getContext().getFilesDir(),benchmark=new File(files,"benchmark");
        JSONObject request=OnDeviceModels.json(new File(benchmark,"install-request.json"));
        assertEquals("install-live-model-pack",request.getString("operation"));
        assertEquals(ModelPackInstaller.MANIFEST_SHA256,request.getString("manifest_sha256"));
        File zip=new File(benchmark,"model-pack.zip");assertTrue("Stage the ZIP before requesting import",zip.isFile());
        Map<String,String> before=snapshot(new File(files,"vault"));
        long start=android.os.SystemClock.elapsedRealtime();long[] progress={0,0};
        try(InputStream input=new FileInputStream(zip)) {
            ModelPackInstaller.install(files,input,(done,total)->{progress[0]=done;progress[1]=total;});
        }
        assertTrue(ModelPackInstaller.isCurrentManifest(files));
        assertEquals(progress[1],progress[0]);assertTrue(progress[0]>0);
        new OnDeviceModels(getContext()).verify();
        assertEquals("Model import must not modify saved records or photos",before,snapshot(new File(files,"vault")));
        JSONObject report=new JSONObject().put("status","ok").put("run_id",request.getString("run_id")).put("manifest_sha256",ModelPackInstaller.MANIFEST_SHA256)
                .put("bytes",progress[0]).put("vault_files_unchanged",before.size())
                .put("elapsed_ms",android.os.SystemClock.elapsedRealtime()-start);
        try(FileWriter writer=new FileWriter(new File(benchmark,"install-result.json"))){writer.write(report.toString(2));}
    }
    private static Map<String,String> snapshot(File root)throws Exception {
        Map<String,String> result=new TreeMap<>();snapshot(root,"",result);return result;
    }
    private static void snapshot(File file,String path,Map<String,String> result)throws Exception {
        if(!file.exists())return;
        if(file.isDirectory()) {
            File[] children=file.listFiles();if(children==null)throw new IOException("Cannot inspect saved records");
            for(File child:children)snapshot(child,path+"/"+child.getName(),result);
        } else {
            MessageDigest hash=MessageDigest.getInstance("SHA-256");byte[] buffer=new byte[65536];
            try(InputStream input=new FileInputStream(file)){int n;while((n=input.read(buffer))!=-1)hash.update(buffer,0,n);}
            result.put(path,ModelPackInstaller.hex(hash.digest()));
        }
    }
}
