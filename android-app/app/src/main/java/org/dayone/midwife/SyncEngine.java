package org.dayone.midwife;
import android.app.job.*;
import android.content.*;
import org.json.JSONObject;

public final class SyncEngine {
    private SyncEngine() {}
    private static final Object SYNC_LOCK=new Object();
    private static volatile boolean reachable=false;
    private static volatile long checkedAt=0;
    public static boolean online(Context c){return reachable&&android.os.SystemClock.elapsedRealtime()-checkedAt<15000;}
    public static boolean probe(Context c){reachable=new UsbDatabaseSink(c).reachable();checkedAt=android.os.SystemClock.elapsedRealtime();return reachable;}
    public static boolean pending(JSONObject r){String s=r.optString("state");return s.equals("REGISTERED")||s.equals("SYNC_FAILED")||(s.equals("SYNCED")&&!r.has("pc_receipt"));}
    public static void schedule(Context c){
        JobScheduler scheduler=c.getSystemService(JobScheduler.class);
        if(scheduler.getPendingJob(21)!=null)return;
        scheduler.schedule(new JobInfo.Builder(21,new ComponentName(c,SyncJobService.class)).setMinimumLatency(5000).setPersisted(true).setBackoffCriteria(30000,JobInfo.BACKOFF_POLICY_EXPONENTIAL).build());
    }
    public static int sync(Context c,EncryptedStore store,RecordSink sink)throws Exception {
        synchronized(SYNC_LOCK){
            int count=0;
            for(JSONObject record:store.records()){
                if(Thread.currentThread().isInterrupted())break;
                if(!pending(record)||record.optString("confirmed_at").isEmpty())continue;
                try {
                    sink.upload(record);
                    EncryptedStore.state(record,"SYNCED");record.put("synced_at",java.time.Instant.now().toString());record.remove("sync_error");store.save(record);count++;
                } catch(Exception e){reachable=false;EncryptedStore.state(record,"SYNC_FAILED");record.put("sync_error","USB database unavailable; saved locally for retry.");store.save(record);throw e;}
            }
            return count;
        }
    }
}
