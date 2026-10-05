package org.dayone.midwife;

import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

public class CheckboxReaderTest {
    private int[] box(int offset,boolean marked) {
        int[] p=new int[60*60];Arrays.fill(p,0xffefbed0);
        for(int y=18;y<=40;y++)for(int x=18+offset;x<=40+offset;x++)
            if(x<=19+offset||x>=39+offset||y<=19||y>=39
                    ||marked&&(Math.abs(x-offset-y)<2||Math.abs(x-offset+y-58)<2))p[y*60+x]=0xff202020;
        return p;
    }
    @Test public void shiftedBordersAreNotTicks() {
        for(int offset=-8;offset<=8;offset++) {
            CheckboxReader.Result r=CheckboxReader.read(box(offset,false),60,60,23,23);
            assertTrue("offset="+offset,r.located);assertEquals(Boolean.FALSE,r.value);assertEquals(0,r.ink,0);
        }
    }
    @Test public void crossesRemainCheckedWhenShifted() {
        for(int offset=-8;offset<=8;offset++)assertEquals(Boolean.TRUE,CheckboxReader.read(box(offset,true),60,60,23,23).value);
    }
    @Test public void thinPenCrossInsideLocatedOutlineIsChecked() {
        int[] pixels=box(0,false);
        for(int y=21;y<=37;y++) {
            pixels[y*60+y]=0xff202020;
            pixels[y*60+58-y]=0xff202020;
        }
        CheckboxReader.Result result=CheckboxReader.read(pixels,60,60,23,23);
        assertTrue(result.located);assertTrue(result.ink>.07&&result.ink<.19);
        assertEquals(Boolean.TRUE,result.value);
    }
    @Test public void isolatedSpeckInsideEmptyBoxIsNotATick() {
        int[] pixels=box(0,false);pixels[29*60+29]=0xff202020;
        assertEquals(Boolean.FALSE,CheckboxReader.read(pixels,60,60,23,23).value);
    }
    @Test public void absentOrCutOffOutlineIsNotProofOfBlank() {
        int[] p=new int[60*60];Arrays.fill(p,0xffffffff);
        assertNull(CheckboxReader.read(p,60,60,23,23).value);
        assertNull(CheckboxReader.read(box(19,false),60,60,23,23).value);
    }
}
