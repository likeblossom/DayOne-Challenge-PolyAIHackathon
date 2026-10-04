package org.dayone.midwife;
import android.app.job.*;
import java.util.concurrent.*;

public final class SyncJobService extends JobService {
    private ExecutorService executor;
    @Override public boolean onStartJob(JobParameters params) {
        ExecutorService current=Executors.newSingleThreadExecutor(); executor=current;
        current.submit(() -> {
            boolean retry=false;
            try {
                EncryptedStore store=new EncryptedStore(this);
                if(SyncEngine.probe(this))SyncEngine.sync(this,store,new UsbDatabaseSink(this));
                for (org.json.JSONObject r:store.records()) if(SyncEngine.pending(r)) retry=true;
            } catch(Exception e) { retry=true; }
            jobFinished(params,retry); current.shutdown();
        });
        return true;
    }
    @Override public boolean onStopJob(JobParameters params) { if(executor!=null) executor.shutdownNow(); return true; }
}
