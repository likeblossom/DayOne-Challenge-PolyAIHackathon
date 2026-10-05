package org.dayone.midwife;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import org.dayone.midwife.model.PresetForm;
import org.json.JSONObject;
import java.util.*;
import java.util.concurrent.*;

/** A user-started, serial OCR queue that does not depend on an Activity's lifetime. */
public final class OcrService extends Service {
    private static final String CHANNEL="sanad-ocr";
    private static final int NOTIFICATION=71;
    private static final Map<String,String> progress=new ConcurrentHashMap<>();
    private final Set<String> pending=new HashSet<>(); // Main thread only.
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Handler main=new Handler(Looper.getMainLooper());
    private PowerManager.WakeLock wakeLock;
    private int latestStart;
    private volatile boolean stopping;

    public static void enqueue(Context context,String id) {
        context.startForegroundService(new Intent(context,OcrService.class).putExtra("record_id",id));
    }
    public static String progress(String id) { return progress.getOrDefault(id,"Preparing your page…"); }
    @Override public void onCreate() {
        super.onCreate();
        getSystemService(NotificationManager.class).createNotificationChannel(
                new NotificationChannel(CHANNEL,"Page recognition",NotificationManager.IMPORTANCE_LOW));
        wakeLock=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"Sanad:OCR");
        wakeLock.setReferenceCounted(false);
    }
    private Notification notification(String message) {
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_launcher)
                .setContentTitle("Sanad").setContentText(message).setContentIntent(open)
                .setVisibility(Notification.VISIBILITY_PRIVATE).setOnlyAlertOnce(true).setOngoing(true)
                .setProgress(0,0,true).build();
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        latestStart=startId;
        if(Build.VERSION.SDK_INT>=29)startForeground(NOTIFICATION,notification("Reading your page…"),ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        else startForeground(NOTIFICATION,notification("Reading your page…"));
        String id=intent==null?null:intent.getStringExtra("record_id");
        if(id!=null&&pending.add(id))worker.execute(() -> process(id));
        if(pending.isEmpty()){stopForeground(STOP_FOREGROUND_REMOVE);stopSelfResult(startId);}
        // Captures are persisted. After process death the next app open resumes them.
        return START_NOT_STICKY;
    }
    private void process(String id) {
        EncryptedStore store=new EncryptedStore(this);
        try {
            if(stopping)return;
            wakeLock.acquire(60*60*1000L);
            JSONObject record=store.get(id);
            synchronized(EncryptedStore.LOCK) {
                record=store.get(id);
                String state=record.optString("state");
                if(!state.equals("CAPTURED")&&!state.equals("PENDING_AI")&&!state.equals("PROCESSING_FAILED"))return;
                EncryptedStore.state(record,"PENDING_AI");store.save(record);
            }
            SchemaCatalog catalog=new SchemaCatalog(this);
            OnDeviceFormParser parser=new OnDeviceFormParser(this,catalog,(done,total) -> {
                String text=total>0?"Reading fields · "+done+"/"+total:"Finding fields…";
                progress.put(id,text);
                if(Build.VERSION.SDK_INT<33||checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED)
                    getSystemService(NotificationManager.class).notify(NOTIFICATION,notification(text));
            });
            byte[] bytes=record.has("image_file")?store.read(record.getString("image_file")):new byte[0];
            if(bytes.length==0&&!record.optBoolean("mock"))
                throw new java.io.IOException("The saved photo is missing or empty. Retake the page or enter it manually.");
            PresetForm form=bytes.length==0?new MockFormParser(catalog).parse(bytes,record.getString("form_id")):parser.parse(bytes,record.getString("form_id"));
            catalog.validate(form.formId,form.toJson());
            synchronized(EncryptedStore.LOCK) {
                if(store.get(id).optString("state").equals("SUPERSEDED"))return;
                record.remove("processing_error");record.put("mock",bytes.length==0).put("form_id",form.formId)
                        .put("fields",form.toJson()).put("extraction_metadata",form.extractionMetadata());
                EncryptedStore.state(record,"AI_PROCESSED");EncryptedStore.state(record,"NEEDS_REVIEW");store.save(record);
            }
        } catch(Exception error) {
            try {
                synchronized(EncryptedStore.LOCK) {
                    JSONObject record=store.get(id);
                    if(!record.optString("state").equals("SUPERSEDED")) {
                        record.put("processing_error",error.getMessage()==null?"OCR failed; capture retained.":error.getMessage());
                        EncryptedStore.state(record,"PROCESSING_FAILED");store.save(record);
                    }
                }
            } catch(Exception storageError) { android.util.Log.e("Sanad","Could not persist OCR failure",storageError); }
        } finally {
            progress.remove(id);
            if(wakeLock.isHeld())wakeLock.release();
            main.post(() -> {pending.remove(id);if(pending.isEmpty()){stopForeground(STOP_FOREGROUND_REMOVE);stopSelfResult(latestStart);}});
        }
    }
    @Override public void onTimeout(int startId,int fgsType) {stopSelf();}
    @Override public void onDestroy() {
        stopping=true;worker.shutdownNow();progress.clear();
        if(wakeLock.isHeld())wakeLock.release();super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) {return null;}
}
