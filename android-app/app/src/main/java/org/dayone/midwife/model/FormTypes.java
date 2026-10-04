package org.dayone.midwife.model;
import org.json.JSONObject;
public final class FormTypes {
    private FormTypes() {}
    public static PresetForm create(String id, JSONObject fields) {
        switch (id) {
            case "pregnancy_postpartum_monitoring": return new PregnancyPostpartumMonitoringForm(fields);
            case "identification_and_history": return new IdentificationAndHistoryForm(fields);
            case "current_pregnancy": return new CurrentPregnancyForm(fields);
            case "labor_and_delivery": return new LaborAndDeliveryForm(fields);
            case "early_postpartum_mother": return new EarlyPostpartumMotherForm(fields);
            case "early_postnatal_newborn": return new EarlyPostnatalNewbornForm(fields);
            case "late_postpartum_mother": return new LatePostpartumMotherForm(fields);
            case "late_postnatal_newborn": return new LatePostnatalNewbornForm(fields);
            default: throw new IllegalArgumentException("Unsupported form: " + id);
        }
    }
}
