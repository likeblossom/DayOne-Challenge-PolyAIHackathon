package org.dayone.midwife;
import org.dayone.midwife.model.PresetForm;

/** Runs off the UI thread. A real adapter identifies formId and returns the same field envelopes. */
public interface FormParser {
    PresetForm parse(byte[] originalImage, String demoFormId) throws Exception;
}
