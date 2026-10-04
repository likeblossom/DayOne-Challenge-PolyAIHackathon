package org.dayone.midwife;
import org.json.JSONObject;

/** Implement this with an idempotent backend upload when a real database is available. */
public interface RecordSink {
    void upload(JSONObject record) throws Exception;
}
