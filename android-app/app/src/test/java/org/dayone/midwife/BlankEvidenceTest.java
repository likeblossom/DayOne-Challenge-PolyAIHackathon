package org.dayone.midwife;
import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;
public class BlankEvidenceTest {
    @Test public void uniformPaperIsEmptyButAnEdgeStrokeIsUncertain() {
        int[] p=new int[100*40];Arrays.fill(p,0xfff5b9cd);
        assertTrue(BlankEvidence.empty(p,100,40));
        for(int y=0;y<40;y++)p[y*100+2]=0xff222222;
        assertFalse(BlankEvidence.empty(p,100,40));
    }
    @Test public void evenOneColoredPixelOrFaintStrokePreventsBlank() {
        int[] p=new int[100*40];Arrays.fill(p,0xfff5b9cd);p[2050]=0xffaaaade;
        assertFalse(BlankEvidence.empty(p,100,40));
        Arrays.fill(p,0xffeeeeee);for(int y=10;y<30;y++)p[y*100+50]=0xffcdcdcd;
        assertFalse(BlankEvidence.empty(p,100,40));
    }
    @Test public void darkOrTinyCropsAreUncertain() {
        int[] p=new int[100*40];Arrays.fill(p,0xff777777);assertFalse(BlankEvidence.empty(p,100,40));
        assertFalse(BlankEvidence.empty(new int[9],3,3));
    }
    @Test public void veryLowContrastWritingIsNotReportedAsMissing() {
        int[] p=new int[100*40];Arrays.fill(p,0xffffffff);
        for(int y=10;y<30;y++)p[y*100+50]=0xfff7f7f7;
        assertFalse(BlankEvidence.empty(p,100,40));
    }
}
