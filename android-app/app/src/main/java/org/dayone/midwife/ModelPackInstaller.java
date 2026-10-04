package org.dayone.midwife;

import org.json.*;
import java.io.*;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

/** Streaming, pinned-manifest ZIP import. Failed imports never replace installed models. */
public final class ModelPackInstaller {
    public static final Object LOCK=new Object();
    public static final String MANIFEST_SHA256="647b08a32d9e70af6e3d564f56d8c974345b1b0d321d37d9843fe7018c13d2bf";
    private static final String LIVE="sanad-models-v1",STAGE="sanad-models-import",OLD="sanad-models-backup";
    public interface Progress {void update(long done,long total);}
    private ModelPackInstaller(){}
    static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    static File safe(File root,String name)throws IOException {
        if(name.isEmpty()||name.startsWith("/")||name.contains("\\"))throw new IOException("Unsafe ZIP path");
        for(String part:name.split("/",-1))if(part.isEmpty()||part.equals(".")||part.equals(".."))throw new IOException("Unsafe ZIP path");
        File f=new File(root,name).getCanonicalFile();if(!f.getPath().startsWith(root.getCanonicalPath()+File.separator))throw new IOException("Unsafe ZIP path");return f;
    }
    private static void remove(File f)throws IOException {
        if(Files.isSymbolicLink(f.toPath())){Files.delete(f.toPath());return;}
        if(!f.exists())return;
        if(f.isDirectory()){File[] children=f.listFiles();if(children==null)throw new IOException("Cannot read import directory");for(File child:children)remove(child);}
        if(!f.delete())throw new IOException("Cannot clean model import files");
    }
    public static void recover(File files)throws IOException {
        synchronized(LOCK){File live=new File(files,LIVE),old=new File(files,OLD);if(!live.exists()&&old.exists()&&!old.renameTo(live))throw new IOException("Cannot restore previous model pack");}
    }
    public static void install(File files,InputStream input,Progress progress)throws Exception {install(files,input,MANIFEST_SHA256,progress);}
    static void install(File files,InputStream input,String trustedManifest,Progress progress)throws Exception {
        synchronized(LOCK){
            recover(files);File stage=new File(files,STAGE),live=new File(files,LIVE),old=new File(files,OLD);
            remove(stage);remove(old);if(!stage.mkdir())throw new IOException("Cannot create model import directory");
            boolean promoted=false;
            try(ZipInputStream zip=new ZipInputStream(new BufferedInputStream(input,1024*1024))){
                ZipEntry first=zip.getNextEntry();if(first==null||!first.getName().equals("manifest.json")||first.isDirectory())throw new IOException("Choose the Sanad model-pack ZIP, not training checkpoints.");
                ByteArrayOutputStream manifestBytes=new ByteArrayOutputStream();byte[] buffer=new byte[1024*1024];int n;
                while((n=zip.read(buffer))!=-1){if(manifestBytes.size()+n>1024*1024)throw new IOException("Manifest too large");manifestBytes.write(buffer,0,n);}
                byte[] raw=manifestBytes.toByteArray();if(!hex(MessageDigest.getInstance("SHA-256").digest(raw)).equals(trustedManifest))throw new IOException("This model pack does not match this version of Sanad.");
                JSONObject manifest=new JSONObject(new String(raw,java.nio.charset.StandardCharsets.UTF_8));
                if(manifest.getInt("version")!=1||!manifest.getString("scope").equals("all_eight_forms"))throw new IOException("Unsupported model pack");
                JSONObject expected=manifest.getJSONObject("files");if(expected.length()>256)throw new IOException("Too many model files");long total=0,done=0;
                for(Iterator<String> it=expected.keys();it.hasNext();){String name=it.next();safe(stage,name);long size=expected.getJSONObject(name).getLong("bytes");if(size<0||size>2L*1024*1024*1024)throw new IOException("Invalid model size");total+=size;}
                if(total>4L*1024*1024*1024)throw new IOException("Model pack too large");
                if(files.getUsableSpace()<total+64L*1024*1024)throw new IOException("Not enough storage. Free at least 3.1 GB, then try again.");
                Set<String> seen=new HashSet<>();progress.update(0,total);ZipEntry entry;
                while((entry=zip.getNextEntry())!=null){
                    String name=entry.getName();File dest=safe(stage,name);
                    if(entry.isDirectory()||!expected.has(name)||!seen.add(name))throw new IOException("Unexpected or duplicate model file: "+name);
                    JSONObject info=expected.getJSONObject(name);long limit=info.getLong("bytes"),written=0;MessageDigest hash=MessageDigest.getInstance("SHA-256");
                    if(!dest.getParentFile().isDirectory()&&!dest.getParentFile().mkdirs())throw new IOException("Cannot create model folder");
                    try(FileOutputStream out=new FileOutputStream(dest)){
                        while((n=zip.read(buffer))!=-1){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Import cancelled");written+=n;if(written>limit)throw new IOException("Model file larger than expected");out.write(buffer,0,n);hash.update(buffer,0,n);done+=n;progress.update(done,total);}
                        out.getFD().sync();
                    }
                    if(written!=limit||!hex(hash.digest()).equals(info.getString("sha256")))throw new IOException("Damaged model file: "+name);
                }
                if(seen.size()!=expected.length())throw new IOException("Model pack is incomplete");
                try(FileOutputStream out=new FileOutputStream(new File(stage,"manifest.json"))){out.write(raw);out.getFD().sync();}
                if(live.exists()&&!live.renameTo(old))throw new IOException("Cannot preserve installed models");
                if(!stage.renameTo(live)){recover(files);throw new IOException("Cannot activate imported models");}
                promoted=true;
                // A leftover backup is safe to clean on the next import if removal is interrupted.
                try{remove(old);}catch(IOException ignored){}
            }finally{if(!promoted){remove(stage);recover(files);}}
        }
    }
}
