package org.dayone.midwife.model;

import org.json.JSONObject;
import java.util.function.Function;

/** Immutable extraction evidence. Human verification never inflates model confidence. */
public final class FieldValue<T> {
    public enum Status { KNOWN, UNKNOWN, NOT_PROVIDED, ILLEGIBLE, NOT_APPLICABLE, NEEDS_REVIEW }
    public final T value;
    public final Status status;
    public final double confidence;
    public final boolean humanReviewed;
    public FieldValue(JSONObject json, Function<Object, T> convert) {
        value = json.isNull("value") ? null : convert.apply(json.opt("value"));
        status = Status.valueOf(json.optString("status", "NOT_PROVIDED"));
        confidence = json.optDouble("confidence", 0);
        humanReviewed = json.optBoolean("human_reviewed", false);
        if (!Double.isFinite(confidence) || confidence < 0 || confidence > 1) throw new IllegalArgumentException("Invalid confidence");
    }
}
