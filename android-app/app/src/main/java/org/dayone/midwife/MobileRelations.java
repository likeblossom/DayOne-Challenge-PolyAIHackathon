package org.dayone.midwife;
import org.json.*;
import java.util.*;

/** Cross-field checks flag conflicts; they never invent or overwrite a value. */
public final class MobileRelations {
    private static Object get(JSONObject f,String k){JSONObject v=f.optJSONObject(k);return v==null||v.isNull("value")?null:v.opt("value");}
    private static void issue(JSONObject f,String k,String code)throws Exception{if(f.has(k))MobileGrammar.issue(f.getJSONObject(k),code);}
    private static boolean present(Object v){return v!=null&&!Arrays.asList("","None","Néant","لا يوجد").contains(v);}
    private static boolean has(Object value,Object expected)throws Exception{if(value instanceof JSONArray){JSONArray a=(JSONArray)value;for(int i=0;i<a.length();i++)if(expected.equals(a.get(i)))return true;return false;}return expected.equals(value);}
    private static void ordered(JSONObject f,String a,String b,String code)throws Exception{Object x=get(f,a),y=get(f,b);boolean bad=x instanceof Number&&y instanceof Number?((Number)x).doubleValue()>((Number)y).doubleValue():x instanceof String&&y instanceof String&&((String)x).compareTo((String)y)>0;if(bad){issue(f,a,code);issue(f,b,code);}}
    public static void apply(JSONObject f)throws Exception{
        Set<String> prefixes=new HashSet<>();prefixes.add("");for(Iterator<String> it=f.keys();it.hasNext();){String k=it.next();if(k.contains("."))prefixes.add(k.substring(0,k.lastIndexOf('.')+1));}
        for(String p:prefixes){Object a=get(f,p+"systolic_bp_mmhg"),b=get(f,p+"diastolic_bp_mmhg");if(a instanceof Number&&b instanceof Number&&((Number)a).doubleValue()<=((Number)b).doubleValue()){issue(f,p+"systolic_bp_mmhg","BP_ORDER_CONFLICT");issue(f,p+"diastolic_bp_mmhg","BP_ORDER_CONFLICT");}}
        ordered(f,"parity","gravidity","PARITY_EXCEEDS_GRAVIDITY");
        Object living=get(f,"living_children"),parity=get(f,"parity");if(living instanceof Number&&parity instanceof Number&&((Number)living).doubleValue()>((Number)parity).doubleValue())issue(f,"living_children","REVIEW_MULTIPLE_BIRTHS_OR_COUNT_MISMATCH");
        for(String[] p:new String[][]{{"last_menstrual_period_date","expected_delivery_date"},{"expected_delivery_date","post_term_date"},{"delivery_date","consultation_date"},{"consultation_date","follow_up_date"},{"consultation_date","next_appointment_date"}})ordered(f,p[0],p[1],"DATE_ORDER_CONFLICT");
        for(String p:prefixes)if(p.startsWith("visits["))for(String k:new String[]{"appointment_date","attendance_date"}){Object v=get(f,p+k),lmp=get(f,"last_menstrual_period_date");if(v instanceof String&&lmp instanceof String&&((String)v).compareTo((String)lmp)<0)issue(f,p+k,"VISIT_BEFORE_LMP");}
        Object[][] conditions={{"other_risk_factor","risk_factors","OTHER"},{"other_facility_type","facility_type","OTHER"},{"other_complication","complication_types","OTHER"},{"cesarean_scar_condition","cesarean_performed",true},{"other_family_planning_method","family_planning_method","OTHER"},{"referral_facility","transferred",true},{"other_danger_sign","danger_signs","OTHER"},{"other_trauma_or_malformation","trauma_or_malformations","OTHER"},{"rubella_vaccination_date","rubella_vaccinated",true},{"hepatitis_b_vaccination_date","hepatitis_b_vaccinated",true}};
        for(Object[] c:conditions){Object parent=get(f,(String)c[1]);if(parent!=null&&!has(parent,c[2])){
            if(present(get(f,(String)c[0])))issue(f,(String)c[0],"CONDITIONAL_FIELD_CONFLICT");
            else {
                JSONObject child=f.optJSONObject((String)c[0]),p=f.optJSONObject((String)c[1]);
                if(child!=null&&p!=null&&"KNOWN".equals(p.optString("status"))&&child.optJSONArray("issues").length()==1&&"NO_HANDWRITING_MATCH_NOT_PROOF_OF_BLANK".equals(child.getJSONArray("issues").getString(0)))
                    child.put("status","NOT_APPLICABLE").put("issues",new JSONArray()).put("confidence",p.optDouble("confidence")).put("source","schema_condition_not_met").put("condition_field",c[1]);
            }
        }}
        Object mode=get(f,"delivery_mode");if(mode!=null&&!Arrays.asList("PLANNED_CESAREAN","EMERGENCY_CESAREAN").contains(mode)&&present(get(f,"cesarean_indication")))issue(f,"cesarean_indication","NON_CESAREAN_INDICATION_CONFLICT");
        Object instrument=get(f,"instrument");if(mode!=null&&!"INSTRUMENTAL_VAGINAL".equals(mode)&&instrument!=null&&!"NONE".equals(instrument))issue(f,"instrument","NON_INSTRUMENTAL_DELIVERY_CONFLICT");
        if("HOME".equals(get(f,"delivery_setting"))&&get(f,"facility_type")!=null&&!"NOT_APPLICABLE".equals(get(f,"facility_type")))issue(f,"facility_type","HOME_FACILITY_CONFLICT");
        if(Boolean.FALSE.equals(get(f,"high_risk_pregnancy"))&&get(f,"risk_factors") instanceof JSONArray&&((JSONArray)get(f,"risk_factors")).length()>0)issue(f,"risk_factors","RISK_CHECKBOX_CONFLICT");
        if(Boolean.FALSE.equals(get(f,"wants_family_planning"))&&get(f,"family_planning_method")!=null&&!"NONE".equals(get(f,"family_planning_method")))issue(f,"family_planning_method","FAMILY_PLANNING_CONFLICT");
        if(Boolean.TRUE.equals(get(f,"wants_family_planning"))&&present(get(f,"reason_declined_family_planning")))issue(f,"reason_declined_family_planning","FAMILY_PLANNING_REASON_CONFLICT");
        for(Iterator<String> it=f.keys();it.hasNext();){String k=it.next();Object v=get(f,k);if(k.endsWith("birth_weight_g")&&v instanceof Number&&((Number)v).doubleValue()>10000)issue(f,k,"VERIFY_NEWBORN_WEIGHT_UNIT");if(v instanceof JSONArray){JSONArray a=(JSONArray)v;if(a.length()>1&&has(a,"NORMAL"))issue(f,k,"NORMAL_WITH_ABNORMAL_OPTIONS");if(a.length()>1&&has(a,"NONE"))issue(f,k,"NONE_WITH_OTHER_OPTIONS");if(has(a,"ODORLESS")&&has(a,"FOUL_SMELLING"))issue(f,k,"CONTRADICTORY_LOCHIA_ODOR");}}
        if(Boolean.FALSE.equals(get(f,"complications_present")))for(String k:new String[]{"complication_types","complication_timing"}){Object v=get(f,k);if(v!=null&&(!(v instanceof JSONArray)||((JSONArray)v).length()>0))issue(f,k,"COMPLICATION_CHECKBOX_CONFLICT");}
        for(String p:prefixes)if(p.startsWith("previous_pregnancy_anomalies[")&&get(f,p+"nature")!=null&&!"OTHER".equals(get(f,p+"nature"))&&present(get(f,p+"other_description")))issue(f,p+"other_description","NON_OTHER_DESCRIPTION_CONFLICT");
    }
}
