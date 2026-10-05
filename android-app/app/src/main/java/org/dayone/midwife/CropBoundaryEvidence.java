package org.dayone.midwife;

/** Flags possible clipped ink, not blankness or character identity. */
public final class CropBoundaryEvidence {
    private CropBoundaryEvidence() {}
    public static boolean touchesSide(int[] pixels,int width,int height) {
        if(width<12||height<12||pixels.length!=width*height)return false;
        int[] box=EdgeRuleCrop.bounds(pixels,width,height);
        int w=box[2]-box[0],h=box[3]-box[1];
        if(w<8||h<8)return false;
        int[] histogram=new int[256];
        for(int y=box[1];y<box[3];y++)for(int x=box[0];x<box[2];x++)histogram[gray(pixels[y*width+x])]++;
        int median=0,count=0;while(median<255&&(count+=histogram[median])<w*h/2)median++;
        int threshold=Math.min(170,median-35),border=Math.max(2,h/5),ink=0;
        for(int y=box[1]+border;y<box[3]-border;y++)for(int dx=0;dx<2;dx++) {
            if(gray(pixels[y*width+box[0]+dx])<threshold)ink++;
            if(gray(pixels[y*width+box[2]-1-dx])<threshold)ink++;
        }
        return ink>=2;
    }
    private static int gray(int pixel){return (int)Math.round(.299*(pixel>>16&255)+.587*(pixel>>8&255)+.114*(pixel&255));}
}
