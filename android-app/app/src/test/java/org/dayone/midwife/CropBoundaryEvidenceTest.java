package org.dayone.midwife;
import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

public class CropBoundaryEvidenceTest {
    private int[] page(){int[] pixels=new int[60*40];Arrays.fill(pixels,0xffffc2d2);return pixels;}
    @Test public void sideClippedStrokeIsFlagged(){int[] p=page();p[20*60]=p[21*60]=0xff223388;assertTrue(CropBoundaryEvidence.touchesSide(p,60,40));}
    @Test public void completeWritingIsNotFlagged(){int[] p=page();for(int y=8;y<32;y++)p[y*60+20]=0xff223388;assertFalse(CropBoundaryEvidence.touchesSide(p,60,40));}
    @Test public void straightBorderDoesNotTriggerExpansion(){int[] p=page();for(int y=0;y<40;y++)p[y*60]=0xff111111;assertFalse(CropBoundaryEvidence.touchesSide(p,60,40));}
    @Test public void isolatedEdgeSpeckDoesNotTriggerExpansion(){int[] p=page();p[20*60]=0xff111111;assertFalse(CropBoundaryEvidence.touchesSide(p,60,40));}
}
