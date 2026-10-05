package org.dayone.midwife;

import org.junit.Test;
import static org.junit.Assert.*;

public class BilinearResamplerTest {
    @Test public void downsampleMatchesPillowRgbBilinear() {
        int[] pixels=new int[35];
        for(int i=0;i<pixels.length;i++)pixels[i]=0xff000000 | ((i*73)%256)<<16 | ((i*31+5)%256)<<8 | ((i*127+11)%256);
        assertArrayEquals(new int[]{0xff7c9168,0xff8f5a69,0xff767d91,0xff97a9b1,0xff8d95ad,0xff7440b2},
                BilinearResampler.resize(pixels,7,5,3,2));
    }
    @Test public void upsampleMatchesPillowRgbBilinear() {
        assertArrayEquals(new int[]{0xff00ff0c,0xff80807e,0xffff00f0,0xff04c736,0xff6c7d82,0xffd332cd,
                        0xff0d568a,0xff457689,0xff7c9686,0xff111eb4,0xff31738c,0xff50c863},
                BilinearResampler.resize(new int[]{0xff00ff0c,0xffff00f0,0xff111eb4,0xff50c863},2,2,3,4));
    }
    @Test public void identityPreservesPixels() {
        int[] pixels={0xff000000,0xffabcdef};
        assertArrayEquals(pixels,BilinearResampler.resize(pixels,2,1,2,1));
    }
    @Test public void constantSurvivesLargeReduction() {
        int[] pixels=new int[2600*7];java.util.Arrays.fill(pixels,0xff8143fe);
        assertArrayEquals(new int[]{0xff8143fe},BilinearResampler.resize(pixels,2600,7,1,1));
    }
}
