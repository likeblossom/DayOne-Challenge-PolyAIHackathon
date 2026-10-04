package org.dayone.midwife;
import org.junit.Test;
import org.json.*;
import static org.junit.Assert.*;

public class MobileRulesTest {
    @Test public void reviewThresholdPreservesScoresAndRealIssues()throws Exception {
        assertEquals("NEEDS_REVIEW",MobileGrammar.field("text",.699).getString("status"));
        assertEquals("KNOWN",MobileGrammar.field("text",.70).getString("status"));
        JSONObject valid=MobileGrammar.field("text",.96);assertEquals(.96,valid.getDouble("confidence"),0);
        MobileGrammar.issue(valid,"INVALID_FIELD_PATTERN");MobileGrammar.review(valid);
        assertEquals("NEEDS_REVIEW",valid.getString("status"));assertEquals(.96,valid.getDouble("confidence"),0);
        assertEquals("NEEDS_REVIEW",MobileGrammar.field(null,.99).getString("status"));
        assertEquals("NEEDS_REVIEW",MobileGrammar.field("text",Double.NaN).getString("status"));
    }
    @Test public void emptySelectionsRequireObservedOptionsAndConditionalEvidence()throws Exception {
        JSONObject selection=MobileGrammar.field(new JSONArray(),.70).put("selection_observed",true);
        JSONObject schema=new JSONObject("{\"risk_factors\":{\"type\":\"array\",\"items\":{\"type\":\"enum\",\"values\":[\"OTHER\"]}}}");
        JSONObject child=MobileGrammar.field(null,0);MobileGrammar.issue(child,"NO_HANDWRITING_MATCH_NOT_PROOF_OF_BLANK");
        JSONObject flat=new JSONObject().put("risk_factors",selection).put("other_risk_factor",child);
        assertEquals(0,MobileStructure.build(schema,flat).getJSONArray("risk_factors").length());
        MobileRelations.apply(flat);assertEquals("NOT_APPLICABLE",child.getString("status"));
        selection.put("selection_observed",false);assertEquals(1,MobileStructure.build(schema,flat).getJSONArray("risk_factors").length());
        JSONObject low=MobileGrammar.field(new JSONArray(),.2).put("selection_observed",false),missing=MobileGrammar.field(null,0);MobileGrammar.issue(missing,"NO_HANDWRITING_MATCH_NOT_PROOF_OF_BLANK");
        MobileRelations.apply(new JSONObject().put("risk_factors",low).put("other_risk_factor",missing));assertEquals("NEEDS_REVIEW",missing.getString("status"));
    }
    @Test public void allEightSchemasKeepNestedFieldEnvelopes()throws Exception {
        java.nio.file.Path root=java.nio.file.Paths.get(System.getProperty("user.dir"));while(!java.nio.file.Files.isDirectory(root.resolve("data/form_structures")))root=root.getParent();
        int forms=0;try(java.nio.file.DirectoryStream<java.nio.file.Path> files=java.nio.file.Files.newDirectoryStream(root.resolve("data/form_structures"),"*.schema.json")){
            for(java.nio.file.Path file:files){JSONObject schema=new JSONObject(new String(java.nio.file.Files.readAllBytes(file),java.nio.charset.StandardCharsets.UTF_8));String form=file.getFileName().toString().replace(".schema.json","");JSONObject bindings=new JSONObject(new String(java.nio.file.Files.readAllBytes(root.resolve("data/processed/all_forms/"+form+"/spec.json")),java.nio.charset.StandardCharsets.UTF_8)).getJSONObject("bindings"),flat=new JSONObject();
                for(java.util.Iterator<String> it=bindings.keys();it.hasNext();){String key=it.next();JSONObject b=bindings.getJSONObject(key),f=MobileGrammar.field(b.opt("fixed"),.6);f.put("raw_text","evidence");flat.put(key,f);}
                JSONObject nested=MobileStructure.build(schema.getJSONObject("fields"),flat);SchemaCatalog.validateValue(new JSONObject().put("type","object").put("fields",schema.getJSONObject("fields")),nested,form);
                if(form.startsWith("03")){assertEquals(9,nested.getJSONArray("visits").length());assertEquals("evidence",nested.getJSONArray("visits").getJSONObject(8).getJSONObject("weight_kg").getString("raw_text"));}
                forms++;
            }
        }assertEquals(8,forms);
    }
    @Test public void nestedBooleansAndRelations()throws Exception {
        JSONObject cfg=new JSONObject().put("rules",new JSONObject().put("visits[].follow_up_contacted",new JSONObject().put("type","boolean"))).put("unknown",new JSONArray()).put("not_applicable",new JSONArray());
        assertEquals(true,new MobileGrammar(cfg).parse("visits[8].follow_up_contacted","Oui",.9).getBoolean("value"));
        assertEquals(false,new MobileGrammar(cfg).parse("visits[0].follow_up_contacted","لا",.9).getBoolean("value"));
        JSONObject fields=new JSONObject().put("visits[8].systolic_bp_mmhg",MobileGrammar.field(60,.8)).put("visits[8].diastolic_bp_mmhg",MobileGrammar.field(90,.8));MobileRelations.apply(fields);
        assertTrue(fields.getJSONObject("visits[8].systolic_bp_mmhg").getJSONArray("issues").toString().contains("BP_ORDER_CONFLICT"));
        MobileRelations.apply(new JSONObject());
    }
    @Test public void numericRulesAcrossAllFormsKeepUnitsAndRejectUnknownUnits()throws Exception {
        java.nio.file.Path root=java.nio.file.Paths.get(System.getProperty("user.dir"));while(!java.nio.file.Files.isDirectory(root.resolve("data/form_structures")))root=root.getParent();
        JSONObject forms=new JSONObject(new String(java.nio.file.Files.readAllBytes(root.resolve("vision_pipeline/reports/field_rules.json")),java.nio.charset.StandardCharsets.UTF_8));int checked=0;
        for(java.util.Iterator<String> fit=forms.keys();fit.hasNext();){JSONObject rules=forms.getJSONObject(fit.next());JSONObject cfg=new JSONObject().put("rules",rules).put("unknown",new JSONArray()).put("not_applicable",new JSONArray());MobileGrammar grammar=new MobileGrammar(cfg);
            for(java.util.Iterator<String> it=rules.keys();it.hasNext();){String key=it.next();JSONObject rule=rules.getJSONObject(key);String type=rule.getString("type");if(!type.equals("double")&&!type.equals("integer"))continue;
                JSONArray range=rule.getJSONArray("ocr_sanity_range");double n=Math.floor((range.getDouble(0)+range.getDouble(1))/2);String text=String.format(java.util.Locale.ROOT,"%.0f",n);String instantiated=key.replace("[]","[2]");
                JSONObject parsed=grammar.parse(instantiated,text,.9);assertEquals(key,n,parsed.getDouble("value"),0);assertEquals("KNOWN",parsed.getString("status"));
                if(rule.has("unit")&&!rule.isNull("unit"))assertEquals(key,n,grammar.parse(instantiated,text+" "+rule.getString("unit"),.9).getDouble("value"),0);
                assertTrue(key,grammar.parse(instantiated,text+" unsupported_unit",.9).isNull("value"));checked++;
            }
        }assertEquals(42,checked);
    }
    @Test public void numericDigitsAreNeverStripped()throws Exception {
        JSONObject rule=new JSONObject("{\"type\":\"double\",\"unit\":\"g\",\"unit_aliases\":{\"g\":1,\"kg\":1000},\"unit_policy\":{\"ocr_substitutions\":{\"9\":\"g\"}},\"ocr_sanity_range\":[200,20000]}");
        JSONObject cfg=new JSONObject().put("rules",new JSONObject().put("weight_g",rule)).put("unknown",new JSONArray()).put("not_applicable",new JSONArray());
        MobileGrammar grammar=new MobileGrammar(cfg);JSONObject normal=grammar.parse("weight_g","5178 g",.96),ambiguous=grammar.parse("weight_g","51789",.96),unit=grammar.parse("weight_g","5178 9",.96);
        assertEquals(5178,normal.getDouble("value"),0);assertEquals(51789,ambiguous.getDouble("value"),0);assertTrue(ambiguous.getJSONArray("issues").toString().contains("OUTSIDE"));
        assertEquals(5178,unit.getDouble("value"),0);assertEquals("SCHEMA_CORRECTED",unit.getString("unit_source"));assertEquals("NEEDS_REVIEW",unit.getString("status"));
        assertTrue(grammar.parse("weight_g","5178 L",.9).isNull("value"));
    }
    @Test public void datesNeedARealCalendarAndFullYear(){
        assertEquals("2025-02-13",MobileGrammar.parseDate("02/13/2025"));
        assertEquals("2025-12-01",MobileGrammar.parseDate("1st December 2025"));
        assertEquals("2025-12-01",MobileGrammar.parseDate("1 décembre 2025"));
        assertEquals("2025-12-01",MobileGrammar.parseDate("١ ديسمبر ٢٠٢٥"));
        assertNull(MobileGrammar.parseDate("01/01/12"));assertNull(MobileGrammar.parseDate("31/02/2025"));assertNull(MobileGrammar.parseDate("1st December"));
    }
    @Test public void assignmentIsOneToOne(){
        assertArrayEquals(new int[]{1,0},MobileVision.hungarian(new double[][]{{.2,.3,2.5,2.5},{.1,5,2.5,2.5}}));
        assertArrayEquals(new int[]{0},MobileVision.hungarian(new double[][]{{2.5}}));
    }
    @Test public void tableGeometryUsesBothDetectedAnchors()throws Exception {
        MobileVision.Box row=new MobileVision.Box(),col=new MobileVision.Box();row.confidence=.9;col.confidence=.8;
        row.quad=rotated(new float[][]{{10,200},{80,200},{80,215},{10,215}});col.quad=rotated(new float[][]{{240,20},{270,20},{270,30},{240,30}});
        JSONObject unit=new JSONObject().put("anchor","row").put("column_anchor","col").put("relative_region",new JSONArray("[[2.785714286,-.5],[3.357142857,-.5],[3.357142857,.5],[2.785714286,.5]]")).put("column_relative_region",new JSONArray("[[-.5,17.5],[.833333333,17.5],[.833333333,19],[-.5,19]]"));
        java.util.Map<String,MobileVision.Box> anchors=new java.util.HashMap<>();anchors.put("row",row);anchors.put("col",col);
        MobileVision.Box found=MobileVision.unitAnchor(unit,anchors);float[][] actual=MobileImages.world(unit.getJSONArray("relative_region"),found.quad),expected=rotated(new float[][]{{240,200},{280,200},{280,215},{240,215}});
        for(int i=0;i<4;i++)assertArrayEquals(expected[i],actual[i],.001f);assertEquals(.8,found.confidence,0);
        anchors.remove("col");assertNull(MobileVision.unitAnchor(unit,anchors));
    }
    private static float[][] rotated(float[][] points){double a=Math.toRadians(22);for(float[] p:points){double x=p[0],y=p[1];p[0]=(float)((x*Math.cos(a)-y*Math.sin(a))*.8+43);p[1]=(float)((x*Math.sin(a)+y*Math.cos(a))*.8+72);}return points;}
    @Test public void valuesStatusesAndConfidenceSurvive()throws Exception {
        JSONObject field=MobileGrammar.field(36.8,.68);assertEquals("NEEDS_REVIEW",field.getString("status"));assertEquals(.68,field.getDouble("confidence"),0);assertEquals(36.8,field.getDouble("value"),0);
        assertEquals("37.2",MobileGrammar.normalize("٣٧٫٢"));
    }
}
