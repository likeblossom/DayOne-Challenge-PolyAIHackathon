package org.dayone.midwife;

import org.json.JSONObject;
import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;

public final class ReviewSectionsTest {
    @Test public void formOneUsesClinicalHeadings(){
        assertEquals("Identification",ReviewSections.title("pregnancy_postpartum_monitoring","Record code"));
        assertEquals("Pregnancy risks",ReviewSections.title("pregnancy_postpartum_monitoring","Risk factors 1"));
    }
    @Test public void everyFormHasExpectedSections(){
        assertEquals("Preventive care",ReviewSections.title("identification_and_history","Rubella vaccinated"));
        assertEquals("Prenatal visits",ReviewSections.title("current_pregnancy","Visits 4 / Weight kg"));
        assertEquals("Newborn",ReviewSections.title("labor_and_delivery","Birth weight g"));
        assertEquals("Family planning",ReviewSections.title("late_postpartum_mother","Family planning method"));
        assertEquals("Clinical assessment",ReviewSections.title("early_postnatal_newborn","Danger signs 1"));
    }
    @Test public void minimumConfidenceIgnoresTrueBlankFields()throws Exception{
        JSONObject blank=SchemaCatalog.envelope(null,0),high=SchemaCatalog.envelope("A",.91),low=SchemaCatalog.envelope("B",.74);
        List<SchemaCatalog.Row> rows=Arrays.asList(new SchemaCatalog.Row("A","A",blank),new SchemaCatalog.Row("B","B",high),new SchemaCatalog.Row("C","C",low));
        assertEquals(74,ReviewSections.minimumConfidencePercent(rows));
        assertEquals(-1,ReviewSections.minimumConfidencePercent(Collections.singletonList(new SchemaCatalog.Row("A","A",blank))));
    }
    @Test public void longPrenatalVisitGetsNamedSubsections()throws Exception{
        List<SchemaCatalog.Row> rows=Arrays.asList(
            new SchemaCatalog.Row("Visits 2 / Weight kg","Weight",SchemaCatalog.envelope(63,.88)),
            new SchemaCatalog.Row("Visits 2 / Hiv result","HIV",SchemaCatalog.envelope("NEGATIVE",.76)),
            new SchemaCatalog.Row("Visits 2 / Fundal height cm","Fundal",SchemaCatalog.envelope(24,.93)));
        LinkedHashMap<String,List<SchemaCatalog.Row>> sections=ReviewSections.subsections("current_pregnancy","Prenatal visits",rows);
        assertTrue(sections.containsKey("Visit 2 · Measurements"));
        assertTrue(sections.containsKey("Visit 2 · Infection screening"));
        assertTrue(sections.containsKey("Visit 2 · Obstetric examination"));
        assertEquals(76,ReviewSections.minimumSubsectionConfidence(sections));
    }
}
