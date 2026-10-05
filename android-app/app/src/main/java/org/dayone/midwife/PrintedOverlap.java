package org.dayone.midwife;

/** Convex printed-label containment, independent of page rotation or scale. */
public final class PrintedOverlap {
    private PrintedOverlap() {}
    public static boolean contains(float[][] quad,double x,double y) {
        if(quad==null||quad.length!=4)return false;
        double direction=0,area=0;
        for(int i=0;i<4;i++) {
            float[] a=quad[i],b=quad[(i+1)%4];
            if(a.length!=2||b.length!=2)return false;
            double cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);
            if(!Double.isFinite(cross))return false;
            if(Math.abs(cross)>1e-6){if(direction*cross<0)return false;direction=cross;}
            area+=a[0]*(double)b[1]-b[0]*(double)a[1];
        }
        return Math.abs(area)>1e-6;
    }
}
