package org.dayone.midwife;

import android.content.Context;
import android.security.keystore.*;
import android.util.AtomicFile;
import org.json.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.*;

/** AES-GCM files, a non-exportable Android Keystore key, and atomic replacement. */
public final class EncryptedStore {
    static final Object LOCK = new Object();
    private final File directory;
    public EncryptedStore(Context context) {
        this(context, "vault");
    }
    EncryptedStore(Context context, String namespace) {
        directory=new File(context.getFilesDir(), namespace);
        if (!directory.exists() && !directory.mkdirs()) throw new IllegalStateException("Cannot create encrypted storage");
    }
    private SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        String alias="dayone-local-v1";
        if (!store.containsAlias(alias)) {
            KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(alias,null);
    }
    public void write(String name, byte[] bytes) throws Exception {
        synchronized (LOCK) {
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,key());
            cipher.updateAAD(name.getBytes(StandardCharsets.UTF_8));
            byte[] encrypted=cipher.doFinal(bytes);
            AtomicFile file=new AtomicFile(new File(directory,name)); FileOutputStream out=null;
            try { out=file.startWrite(); out.write(cipher.getIV()); out.write(encrypted); file.finishWrite(out); }
            catch (Exception e) { if(out!=null) file.failWrite(out); throw e; }
        }
    }
    public byte[] read(String name) throws Exception {
        synchronized (LOCK) {
            AtomicFile file=new AtomicFile(new File(directory,name));
            byte[] bytes=file.readFully();
            if (bytes.length<28) throw new IOException("Encrypted file is incomplete");
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Arrays.copyOf(bytes,12)));
            cipher.updateAAD(name.getBytes(StandardCharsets.UTF_8));
            return cipher.doFinal(bytes,12,bytes.length-12);
        }
    }
    public JSONObject json(String name) throws Exception {
        synchronized (LOCK) {
            AtomicFile file=new AtomicFile(new File(directory,name));
            if (!file.getBaseFile().exists() && !new File(directory,name+".bak").exists()) return new JSONObject();
            return new JSONObject(new String(read(name), StandardCharsets.UTF_8));
        }
    }
    public void json(String name, JSONObject data) throws Exception { write(name, data.toString().getBytes(StandardCharsets.UTF_8)); }
    public List<JSONObject> records() throws Exception {
        synchronized (LOCK) {
            JSONObject db=json("records.enc"); List<JSONObject> result=new ArrayList<>();
            for (Iterator<String> it=db.keys();it.hasNext();) result.add(db.getJSONObject(it.next()));
            result.sort(Comparator.comparing(r -> r.optString("captured_at")));
            return result;
        }
    }
    public void save(JSONObject record) throws Exception {
        synchronized (LOCK) {
            JSONObject db=json("records.enc"); db.put(record.getString("id"),record); json("records.enc",db);
        }
    }
    public JSONObject get(String id) throws Exception { synchronized (LOCK) { return json("records.enc").getJSONObject(id); } }
    public static void state(JSONObject record, String state) throws JSONException {
        JSONArray history=record.optJSONArray("lifecycle"); if(history==null) history=new JSONArray();
        history.put(new JSONObject().put("state",state).put("at",java.time.Instant.now().toString()));
        record.put("state",state).put("lifecycle",history);
    }
}
