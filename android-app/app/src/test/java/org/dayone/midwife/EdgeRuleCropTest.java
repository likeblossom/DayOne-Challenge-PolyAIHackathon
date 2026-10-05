package org.dayone.midwife;
import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

public class EdgeRuleCropTest {
    @Test public void tableEdgesAreRemovedWithoutDeletingTheDigitOne() {
        int w=50,h=40;int[] pixels=new int[w*h];Arrays.fill(pixels,0xffefbed0);
        for(int y=0;y<h;y++)pixels[y*w+2]=0xff111111;
        for(int x=0;x<w;x++)pixels[36*w+x]=0xff111111;
        for(int y=6;y<31;y++)pixels[y*w+10]=0xff111111;
        int[] b=EdgeRuleCrop.bounds(pixels,w,h);
        assertTrue(b[0]>2&&b[0]<10);assertTrue(b[3]<36&&b[3]>30);
    }
    @Test public void isolatedOnesAndMinusSignsAreKept() {
        int w=50,h=40;int[] pixels=new int[w*h];Arrays.fill(pixels,0xffffffff);
        for(int y=4;y<h-4;y++)pixels[y*w+5]=0xff111111;
        for(int x=5;x<w-5;x++)pixels[32*w+x]=0xff111111;
        assertArrayEquals(new int[]{0,0,w,h},EdgeRuleCrop.bounds(pixels,w,h));
    }
    @Test public void tinyImagesRemainUnchanged() {
        assertArrayEquals(new int[]{0,0,5,5},EdgeRuleCrop.bounds(new int[25],5,5));
    }
}
