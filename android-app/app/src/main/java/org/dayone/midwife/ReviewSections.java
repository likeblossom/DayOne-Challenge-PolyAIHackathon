package org.dayone.midwife;

import java.util.*;

/** Clinical section labels for the schema-driven review screen. */
public final class ReviewSections {
    private static final Map<String,List<Section>> FORMS=new HashMap<>();
    static {
        add("pregnancy_postpartum_monitoring",
            section("Identification","record_code","region","province","health_facility_name","health_facility_type","coverage_mode"),
            section("Pregnancy risks","high_risk_pregnancy","risk_factors","other_risk_factor"));
        add("identification_and_history",
            section("Identification","age_years","education_level","occupation","spouse_occupation","consanguinity","desired_pregnancy"),
            section("Medical history","family_history","woman_history"),
            section("Pregnancy history","previous_pregnancy_anomalies","previous_deliveries","gravidity","parity","living_children"),
            section("Preventive care","tetanus_vaccination_dose","rubella_vaccinated","rubella_vaccination_date","hepatitis_b_vaccinated","hepatitis_b_vaccination_date","cervical_smear_or_via_result"));
        add("current_pregnancy",
            section("Pregnancy dates","last_menstrual_period_date","expected_delivery_date","post_term_date"),
            section("Maternal profile","height_cm","blood_group","rhesus_factor"),
            section("Prenatal visits","visits"));
        add("labor_and_delivery",
            section("Delivery setting","delivery_setting","facility_type","other_facility_type","qualified_attendant_present","other_attendant"),
            section("Delivery","delivery_date","delivery_mode","instrument","episiotomy","cesarean_indication"),
            section("Complications","complications_present","complication_timing","complication_types","other_complication"),
            section("Newborn","newborn_status","newborn_sex","birth_weight_g","head_circumference_cm","newborn_abnormality","gestational_age_weeks"));
        Section[] mother={
            section("Visit and vital signs","visit_timing","consultation_date","temperature_c","systolic_bp_mmhg","diastolic_bp_mmhg","pulse_bpm","weight_kg"),
            section("Maternal examination","conjunctiva_condition","uterine_globe_present","lochia","perineum_condition","sphincter_condition","cesarean_performed","cesarean_scar_condition","breast_condition","calf_findings"),
            section("Treatment and follow-up","complications","medications_taken","iron_prescribed","vitamin_a_prescribed","other_treatment","next_appointment_date"),
            section("Family planning","wants_family_planning","family_planning_method","other_family_planning_method","contraception_prescribed","family_planning_referral","reason_declined_family_planning")};
        add("early_postpartum_mother",mother);add("late_postpartum_mother",mother);
        Section[] newborn={
            section("Visit and measurements","consultation_date","age_days","temperature_c","weight_g","length_cm","head_circumference_cm"),
            section("Growth and feeding","premature","small_for_gestational_age","feeding_method","breastfeeding_evaluation"),
            section("Clinical assessment","danger_signs","other_danger_sign","trauma_or_malformations","other_trauma_or_malformation","complications_or_malformations"),
            section("Preventive care","vaccination_status","vaccines_given_today","vitamin_d_supplementation"),
            section("Decision and referral","examiner_role","decision","treatment","transferred","referral_facility"),
            section("Counselling and follow-up","exclusive_breastfeeding_advice_given","keep_warm_advice_given","return_warning_signs_advice_given","follow_up_date")};
        add("early_postnatal_newborn",newborn);add("late_postnatal_newborn",newborn);
    }
    private ReviewSections(){}
    private static Section section(String title,String...keys){Set<String> labels=new HashSet<>();for(String key:keys)labels.add(SchemaCatalog.label(key));return new Section(title,labels);}
    private static void add(String form,Section...sections){FORMS.put(form,Arrays.asList(sections));}
    public static String title(String form,String path){String root=path.contains(" / ")?path.substring(0,path.indexOf(" / ")):path;root=root.replaceFirst(" \\d+$","");for(Section section:FORMS.getOrDefault(form,Collections.emptyList()))if(section.labels.contains(root))return section.title;return "Additional information";}
    public static LinkedHashMap<String,List<SchemaCatalog.Row>> subsections(String form,String parent,List<SchemaCatalog.Row> rows){
        LinkedHashMap<String,List<SchemaCatalog.Row>> result=new LinkedHashMap<>();Map<String,Integer> counts=new HashMap<>();
        for(SchemaCatalog.Row row:rows){String base=subsection(form,parent,row.path);int count=counts.getOrDefault(base,0);String title=base+(count>=8?" · "+(count/8+1):"");result.computeIfAbsent(title,k->new ArrayList<>()).add(row);counts.put(base,count+1);}
        return result;
    }
    static String subsection(String form,String parent,String path){
        String[] parts=path.split(" / ");String root=parts[0],plainRoot=root.replaceFirst(" \\d+$","");String leaf=parts[parts.length-1];
        if(form.equals("current_pregnancy")&&parent.equals("Prenatal visits")){
            String visit=root.replaceFirst("^Visits", "Visit");
            if(oneOf(leaf,"Period","Appointment date","Attendance date","Follow up contacted","Gestational age weeks"))return visit+" · Timing";
            if(oneOf(leaf,"Weight kg","Systolic bp mmhg","Diastolic bp mmhg"))return visit+" · Measurements";
            if(oneOf(leaf,"Skeletal abnormalities","Conjunctiva condition","Breast exam","Edema","Active fetal movements"))return visit+" · Clinical examination";
            if(oneOf(leaf,"Fundal height cm","Fetal heart rate bpm","Speculum exam","Cervix condition","Fetal presentation","Pelvis exam"))return visit+" · Obstetric examination";
            if(oneOf(leaf,"Glycosuria","Albuminuria"))return visit+" · Urinalysis";
            if(oneOf(leaf,"Rubella result","Toxoplasmosis result","Syphilis result","Hepatitis b surface antigen result","Hiv result"))return visit+" · Infection screening";
            if(oneOf(leaf,"Hemoglobin g dl","Platelets per ul","Blood glucose g l","Irregular antibody screen result"))return visit+" · Blood tests";
            return visit+" · Care plan";
        }
        if(form.equals("identification_and_history")){
            if(parent.equals("Medical history")){
                if(path.startsWith("Family history / Woman family"))return "Woman’s family history";
                if(path.startsWith("Family history / Spouse family"))return "Spouse’s family history";
                return "Woman’s medical history";
            }
            if(parent.equals("Pregnancy history")){
                if(root.startsWith("Previous pregnancy anomalies "))return root.replace("Previous pregnancy anomalies","Pregnancy anomaly");
                if(root.startsWith("Previous deliveries "))return root.replace("Previous deliveries","Previous delivery");
                return "Pregnancy summary";
            }
        }
        if(form.equals("pregnancy_postpartum_monitoring")&&parent.equals("Pregnancy risks")){
            if(plainRoot.equals("Risk factors"))return "Recorded risk factors";
            if(plainRoot.equals("Other risk factor"))return "Other risk information";
            return "Risk status";
        }
        if((form.equals("early_postpartum_mother")||form.equals("late_postpartum_mother"))){
            if(parent.equals("Maternal examination")){
                if(oneOf(plainRoot,"Uterine globe present","Lochia","Perineum condition","Sphincter condition"))return "Uterine and perineal examination";
                if(oneOf(plainRoot,"Cesarean performed","Cesarean scar condition"))return "Cesarean assessment";
                return "General examination";
            }
            if(parent.equals("Treatment and follow-up")){
                if(plainRoot.equals("Complications"))return "Complications";
                if(plainRoot.equals("Next appointment date"))return "Follow-up";
                return "Medication and supplements";
            }
            if(parent.equals("Family planning")){
                if(oneOf(plainRoot,"Wants family planning","Reason declined family planning"))return "Preferences";
                if(oneOf(plainRoot,"Family planning referral"))return "Referral";
                return "Contraception method";
            }
        }
        if((form.equals("early_postnatal_newborn")||form.equals("late_postnatal_newborn"))){
            if(parent.equals("Clinical assessment")){
                if(plainRoot.equals("Danger signs"))return "Danger signs";
                if(oneOf(plainRoot,"Trauma or malformations","Other trauma or malformation"))return "Trauma and malformations";
                return "Complications";
            }
            if(parent.equals("Decision and referral")){
                if(oneOf(plainRoot,"Transferred","Referral facility"))return "Transfer and referral";
                return "Clinical decision";
            }
            if(parent.equals("Counselling and follow-up"))return plainRoot.equals("Follow up date")?"Follow-up":"Parent counselling";
        }
        if(form.equals("labor_and_delivery")&&parent.equals("Complications")){
            if(plainRoot.equals("Complication timing"))return "Timing";
            if(plainRoot.equals("Complication types"))return "Types";
            return "Complication details";
        }
        return parts.length>1?root:parent+" details";
    }
    private static boolean oneOf(String value,String...values){for(String candidate:values)if(value.equals(candidate))return true;return false;}
    public static int minimumConfidencePercent(List<SchemaCatalog.Row> rows){int minimum=101;for(SchemaCatalog.Row row:rows){double confidence=row.field.optDouble("confidence",0);if(!row.field.isNull("value")||confidence>0)minimum=Math.min(minimum,(int)Math.round(confidence*100));}return minimum==101?-1:minimum;}
    public static int minimumSubsectionConfidence(Map<String,List<SchemaCatalog.Row>> subsections){int minimum=101;for(List<SchemaCatalog.Row> rows:subsections.values()){int score=minimumConfidencePercent(rows);if(score>=0)minimum=Math.min(minimum,score);}return minimum==101?-1:minimum;}
    private static final class Section {final String title;final Set<String> labels;Section(String title,Set<String> labels){this.title=title;this.labels=labels;}}
}
