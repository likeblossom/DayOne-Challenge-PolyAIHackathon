package org.dayone.midwife;
import org.junit.*;
import org.junit.rules.TemporaryFolder;
import org.json.*;
import java.io.*;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.zip.*;
import static org.junit.Assert.*;

public class ModelPackInstallerTest {
    @Rule public TemporaryFolder temp=new TemporaryFolder();
    private byte[] manifest(byte[] contents)throws Exception{return new JSONObject().put("version",1).put("scope","all_eight_forms").put("files",new JSONObject().put("reader/model.onnx",new JSONObject().put("bytes",contents.length).put("sha256",hash(contents)))).toString().getBytes("UTF-8");}
    private String hash(byte[] b)throws Exception{return ModelPackInstaller.hex(MessageDigest.getInstance("SHA-256").digest(b));}
    private byte[] zip(byte[] manifest,String name,byte[] data)throws Exception{ByteArrayOutputStream b=new ByteArrayOutputStream();try(ZipOutputStream z=new ZipOutputStream(b)){z.putNextEntry(new ZipEntry("manifest.json"));z.write(manifest);z.closeEntry();if(name!=null){z.putNextEntry(new ZipEntry(name));z.write(data);z.closeEntry();}}return b.toByteArray();}
    private void reject(String name,byte[] actual,boolean wrongManifest)throws Exception {
        File root=temp.newFolder();File old=new File(root,"sanad-models-v1");assertTrue(old.mkdir());Files.write(new File(old,"keep").toPath(),new byte[]{9});
        byte[] m=manifest(new byte[]{1,2,3});try{ModelPackInstaller.install(root,new ByteArrayInputStream(zip(m,name,actual)),wrongManifest?"bad":hash(m),(a,b)->{});fail("Accepted invalid pack");}catch(IOException expected){}
        assertArrayEquals(new byte[]{9},Files.readAllBytes(new File(old,"keep").toPath()));assertFalse(new File(root,"sanad-models-import").exists());
    }
    @Test public void importsAndReplacesAtomically()throws Exception {File root=temp.newFolder();byte[] data={1,2,3},m=manifest(data);for(int i=0;i<2;i++)ModelPackInstaller.install(root,new ByteArrayInputStream(zip(m,"reader/model.onnx",data)),hash(m),(a,b)->{});assertArrayEquals(data,Files.readAllBytes(new File(root,"sanad-models-v1/reader/model.onnx").toPath()));assertFalse(new File(root,"sanad-models-backup").exists());}
    @Test public void rejectsCorruption()throws Exception{reject("reader/model.onnx",new byte[]{3,2,1},false);}
    @Test public void rejectsOversizedEntry()throws Exception{reject("reader/model.onnx",new byte[]{1,2,3,4},false);}
    @Test public void rejectsMissingFile()throws Exception{reject(null,new byte[0],false);}
    @Test public void rejectsTraversal()throws Exception{reject("../escaped",new byte[]{1,2,3},false);}
    @Test public void rejectsAbsolutePath()throws Exception{reject("/escaped",new byte[]{1,2,3},false);}
    @Test public void rejectsUnknownManifest()throws Exception{reject("reader/model.onnx",new byte[]{1,2,3},true);}
    @Test public void restoresInterruptedPromotion()throws Exception{File root=temp.newFolder();File old=new File(root,"sanad-models-backup");assertTrue(old.mkdir());Files.write(new File(old,"keep").toPath(),new byte[]{9});ModelPackInstaller.recover(root);assertTrue(new File(root,"sanad-models-v1/keep").exists());}
}
