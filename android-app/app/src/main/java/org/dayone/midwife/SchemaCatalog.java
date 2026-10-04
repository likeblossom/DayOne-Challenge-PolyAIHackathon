package org.dayone.midwife;

import android.content.Context;
import org.json.*;
import org.dayone.midwife.model.FieldValue;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.*;

/** The schema drives rendering, editing, validation, and the mock. */
public final class SchemaCatalog {
    public final LinkedHashMap<String, JSONObject> forms = new LinkedHashMap<>();
    public SchemaCatalog(Context context) throws Exception {
        String[] names = context.getAssets().list("forms");
        Arrays.sort(names);
        for (String name : names) try (java.io.InputStream in = context.getAssets().open("forms/" + name)) {
            java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
            byte[] buffer = new byte[8192]; int count;
            while ((count = in.read(buffer)) != -1) bytes.write(buffer, 0, count);
            JSONObject schema = new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8));
            forms.put(schema.getString("form_id"), schema);
        }
    }
    public JSONObject schema(String id) { return forms.get(id); }
    public String title(String id) { return schema(id).optString("title_en"); }
    public static String label(String key) {
        String s = key.replace('_', ' ');
        return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }
    public static JSONObject envelope(Object value, double confidence) throws JSONException {
        return new JSONObject().put("value", value == null ? JSONObject.NULL : value)
            .put("status", value == null ? "NOT_PROVIDED" : confidence < MobileGrammar.ACCEPT_CONFIDENCE ? "NEEDS_REVIEW" : "KNOWN")
            .put("confidence", value == null ? 0 : confidence);
    }
    public static Object empty(JSONObject spec) throws JSONException {
        switch (spec.getString("type")) {
            case "object": return blank(spec.getJSONObject("fields"));
            case "array": return new JSONArray();
            default: return envelope(null, 0);
        }
    }
    public static JSONObject blank(JSONObject fields) throws JSONException {
        JSONObject data = new JSONObject();
        for (Iterator<String> it = fields.keys(); it.hasNext();) { String key = it.next(); data.put(key, empty(fields.getJSONObject(key))); }
        return data;
    }
    public void validate(String id, JSONObject data) throws JSONException {
        if (!forms.containsKey(id)) throw new IllegalArgumentException("Unknown form type");
        validateFields(schema(id).getJSONObject("fields"), data, "");
    }
    private static void validateFields(JSONObject specs, JSONObject values, String path) throws JSONException {
        for (Iterator<String> it = values.keys(); it.hasNext();) {
            String key = it.next();
            if (!specs.has(key)) throw new IllegalArgumentException("Unsupported field: " + path + key);
        }
        for (Iterator<String> it = specs.keys(); it.hasNext();) {
            String key = it.next();
            validateValue(specs.getJSONObject(key), values.get(key), path + label(key));
        }
    }
    public static void validateValue(JSONObject spec, Object value, String path) throws JSONException {
        String type = spec.getString("type");
        if (type.equals("object")) { validateFields(spec.getJSONObject("fields"), (JSONObject) value, path + " / "); return; }
        if (type.equals("array")) {
            JSONArray array = (JSONArray) value;
            if (array.length() > spec.optInt("maximum_items", 100)) throw new IllegalArgumentException(path + ": too many entries");
            for (int i=0; i<array.length(); i++) validateValue(spec.getJSONObject("items"), array.get(i), path + " " + (i+1));
            return;
        }
        JSONObject field = (JSONObject) value;
        FieldValue.Status status = FieldValue.Status.valueOf(field.getString("status"));
        double confidence = field.getDouble("confidence");
        if (!Double.isFinite(confidence) || confidence < 0 || confidence > 1) throw new IllegalArgumentException(path + ": invalid confidence");
        if (field.isNull("value")) {
            if (status == FieldValue.Status.KNOWN) throw new IllegalArgumentException(path + ": enter a value or choose a missing-data status");
            return;
        }
        if (status == FieldValue.Status.NOT_PROVIDED || status == FieldValue.Status.NOT_APPLICABLE || status == FieldValue.Status.ILLEGIBLE || status == FieldValue.Status.UNKNOWN)
            throw new IllegalArgumentException(path + ": clear the value for this status");
        Object raw = field.get("value");
        if (type.equals("double") || type.equals("integer")) {
            if (!(raw instanceof Number)) throw new IllegalArgumentException(path + ": enter a number");
            double n = ((Number) raw).doubleValue();
            if (!Double.isFinite(n) || (type.equals("integer") && n != Math.rint(n))) throw new IllegalArgumentException(path + ": invalid number");
            if (n < spec.optDouble("minimum", -Double.MAX_VALUE) || n > spec.optDouble("maximum", Double.MAX_VALUE)) throw new IllegalArgumentException(path + ": outside allowed range");
        } else if (type.equals("boolean")) {
            if (!(raw instanceof Boolean)) throw new IllegalArgumentException(path + ": choose true or false");
        } else {
            if (!(raw instanceof String)) throw new IllegalArgumentException(path + ": enter text");
            if (type.equals("date")) try { LocalDate.parse((String)raw); } catch (Exception e) { throw new IllegalArgumentException(path + ": use a valid YYYY-MM-DD date"); }
            if (type.equals("enum")) {
                JSONArray allowed = spec.getJSONArray("values"); boolean found = false;
                for (int i=0; i<allowed.length(); i++) if (raw.equals(allowed.get(i))) found = true;
                if (!found) throw new IllegalArgumentException(path + ": choose an allowed value");
            }
        }
    }
    public static final class Row {
        public final String path, label;
        public final JSONObject field;
        Row(String path, String label, JSONObject field) { this.path=path; this.label=label; this.field=field; }
        public boolean needsReview() { return !field.optBoolean("human_reviewed") && (field.optString("status").equals("NEEDS_REVIEW") || field.optString("status").equals("ILLEGIBLE") || (!field.isNull("value") && field.optDouble("confidence") < MobileGrammar.ACCEPT_CONFIDENCE)); }
    }
    public static List<Row> rows(JSONObject specs, JSONObject data) throws JSONException {
        List<Row> result = new ArrayList<>();
        walk(specs, data, "", result); return result;
    }
    private static void walk(JSONObject specs, JSONObject data, String prefix, List<Row> rows) throws JSONException {
        for (Iterator<String> it = specs.keys(); it.hasNext();) {
            String key=it.next(); JSONObject spec=specs.getJSONObject(key);
            String path=prefix + label(key); Object value=data.get(key);
            if (spec.getString("type").equals("object")) walk(spec.getJSONObject("fields"), (JSONObject)value, path + " / ", rows);
            else if (spec.getString("type").equals("array")) {
                JSONArray array=(JSONArray)value;
                if (array.length()==0) rows.add(new Row(path, path + " · no entries", envelope(null, 0)));
                for (int i=0;i<array.length();i++) {
                    if (spec.getJSONObject("items").getString("type").equals("object")) walk(spec.getJSONObject("items").getJSONObject("fields"), array.getJSONObject(i), path + " " + (i+1) + " / ", rows);
                    else rows.add(new Row(path, path + " " + (i+1), array.getJSONObject(i)));
                }
            } else rows.add(new Row(path, path + (spec.has("unit") ? " (" + spec.getString("unit") + ")" : ""), (JSONObject)value));
        }
    }
}
