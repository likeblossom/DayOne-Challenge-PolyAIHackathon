package org.dayone.midwife;

/** Diagnostic-only experiment; deliberately not shipped in the Android parser. */
public final class BlankEvidence {
    public static final String VERSION="uniform_rgb_2_no_trim_v1";
    private BlankEvidence() {}
    public static boolean empty(int[] pixels,int width,int height) {
        if(width<16||height<16||pixels.length!=width*height)return false;
        // Do not strip rules here: a clipped thin digit can resemble a border.
        // Blank confirmation requires the complete observed region to be uniform.
        int[][] histogram=new int[3][256];int count=width*height;
        for(int y=0;y<height;y++)for(int x=0;x<width;x++) {
            int p=pixels[y*width+x];histogram[0][p>>16&255]++;histogram[1][p>>8&255]++;histogram[2][p&255]++;
        }
        int[] median=new int[3];
        for(int c=0;c<3;c++){int n=0;while(median[c]<255&&(n+=histogram[c][median[c]])<count/2)median[c]++;}
        if(.299*median[0]+.587*median[1]+.114*median[2]<170)return false;
        for(int y=0;y<height;y++)for(int x=0;x<width;x++) {
            int p=pixels[y*width+x];
            if(Math.abs((p>>16&255)-median[0])>2||Math.abs((p>>8&255)-median[1])>2||Math.abs((p&255)-median[2])>2)return false;
        }
        return true;
    }
}
