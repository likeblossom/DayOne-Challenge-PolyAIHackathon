package org.dayone.midwife;
import org.dayone.midwife.model.*;
import org.json.*;
import java.util.*;

/** Deterministic synthetic evidence; never inspects pixels or loads a model. */
public final class MockFormParser implements FormParser {
    private final SchemaCatalog catalog;
    public MockFormParser(SchemaCatalog catalog) { this.catalog=catalog; }
    @Override public PresetForm parse(byte[] image, String demoFormId) throws Exception {
        Thread.sleep(1700);
        JSONObject data=populate(catalog.schema(demoFormId).getJSONObject("fields"), new int[]{0});
        catalog.validate(demoFormId, data);
        return FormTypes.create(demoFormId, data);
    }
    private JSONObject populate(JSONObject specs, int[] count) throws JSONException {
        JSONObject data=new JSONObject();
        for (Iterator<String> it=specs.keys();it.hasNext();) {
            String key=it.next(); JSONObject spec=specs.getJSONObject(key); String type=spec.getString("type");
            Object value;
            if (type.equals("object")) value=populate(spec.getJSONObject("fields"), count);
            else if (type.equals("array")) {
                JSONArray array=new JSONArray();
                if (spec.getJSONObject("items").getString("type").equals("object")) array.put(populate(spec.getJSONObject("items").getJSONObject("fields"), count));
                value=array;
            } else {
                Object sample=sample(key, spec);
                int index=count[0]++;
                value=SchemaCatalog.envelope(sample, index == 0 || index % 7 == 2 ? .68 : .96);
            }
            data.put(key,value);
        }
        return data;
    }
    private Object sample(String key, JSONObject spec) throws JSONException {
        switch (key) {
            case "age_years": return 28.; case "age_days": return 42.;
            case "temperature_c": return 36.8; case "weight_g": return 4200.; case "birth_weight_g": case "newborn_weight_g": return 3200.;
            case "weight_kg": return 64.5; case "length_cm": return 54.; case "height_cm": return 162.;
            case "head_circumference_cm": return 36.; case "systolic_bp_mmhg": return 118.; case "diastolic_bp_mmhg": return 76.;
            case "pulse_bpm": return 78.; case "fetal_heart_rate_bpm": return 140.; case "gestational_age_weeks": return 28.;
            case "fundal_height_cm": return 27.; case "hemoglobin_g_dl": return 11.8; case "platelets_per_ul": return 240000.; case "blood_glucose_g_l": return .9;
            case "gravidity": return 2; case "parity": case "living_children": case "delivery_number": case "count": case "tetanus_vaccination_dose": return 1;
            case "education_level": return "Secondary"; case "examiner_role": return "Midwife";
            case "vaccination_status": return "Recorded on paper"; case "record_code": return "DEMO-7K4P";
        }
        switch (spec.getString("type")) {
            case "date": return key.contains("follow_up") || key.contains("next_") ? "2026-10-18" : "2026-10-04";
            case "boolean": return false;
            case "enum": return spec.getJSONArray("values").get(0);
            default: return null;
        }
    }
}
