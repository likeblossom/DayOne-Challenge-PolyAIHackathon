package org.dayone.midwife.model;

import org.json.*;
import java.util.*;
import java.util.function.Function;

public abstract class PresetForm {
    public final String formId;
    private final JSONObject fields;
    private JSONObject extractionMetadata = new JSONObject();
    protected PresetForm(String id, JSONObject fields) {
        formId = id;
        this.fields = copy(fields);
    }
    public JSONObject toJson() { return copy(fields); }
    public JSONObject extractionMetadata() { return copy(extractionMetadata); }
    public void setExtractionMetadata(JSONObject value) { extractionMetadata=copy(value); }
    private static JSONObject copy(JSONObject json) {
        try { return new JSONObject(json.toString()); }
        catch (JSONException e) { throw new IllegalArgumentException(e); }
    }
    protected static JSONObject object(JSONObject data, String key) {
        JSONObject value = data.optJSONObject(key);
        return value == null ? new JSONObject() : value;
    }
    protected static <T> FieldValue<T> field(JSONObject data, String key, Function<Object,T> convert) {
        return new FieldValue<>(object(data, key), convert);
    }
    protected static <T> List<T> list(JSONObject data, String key, Function<JSONObject,T> convert) {
        List<T> values = new ArrayList<>();
        JSONArray array = data.optJSONArray(key);
        if (array != null) for (int i=0; i<array.length(); i++) values.add(convert.apply(array.optJSONObject(i)));
        return Collections.unmodifiableList(values);
    }
}
