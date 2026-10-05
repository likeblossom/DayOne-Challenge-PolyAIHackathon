package org.dayone.midwife;

/** Trim only edge-adjacent straight rules that span the complete crop. */
public final class EdgeRuleCrop {
    private EdgeRuleCrop() {}
    /** Bounds are left/top inclusive and right/bottom exclusive. */
    public static int[] bounds(int[] pixels,int width,int height) {
        int[] full={0,0,width,height};if(width<12||height<12||pixels.length!=width*height)return full;
        int[] gray=new int[pixels.length],histogram=new int[256];
        for(int i=0;i<pixels.length;i++){int p=pixels[i];gray[i]=(int)Math.round(.299*(p>>16&255)+.587*(p>>8&255)+.114*(p&255));histogram[gray[i]]++;}
        int median=0,count=0;while(median<255&&(count+=histogram[median])<pixels.length/2)median++;
        int threshold=Math.min(150,median-35);if(threshold<35)return full;
        int left=0,right=width,top=0,bottom=height;
        for(int x=0;x<width/4;x++)if(vertical(gray,width,height,x,threshold))left=x+2;
        for(int x=width-1;x>=width-width/4;x--)if(vertical(gray,width,height,x,threshold))right=x-1;
        for(int y=0;y<height/4;y++)if(horizontal(gray,width,height,y,threshold))top=y+2;
        for(int y=height-1;y>=height-height/4;y--)if(horizontal(gray,width,height,y,threshold))bottom=y-1;
        if(right-left<8||bottom-top<8)return full;
        return new int[]{left,top,right,bottom};
    }
    private static boolean vertical(int[] gray,int width,int height,int x,int threshold) {
        int count=0;boolean start=false,end=false;
        for(int y=0;y<height;y++) {
            boolean ink=false;for(int dx=-1;dx<=1;dx++)if(x+dx>=0&&x+dx<width&&gray[y*width+x+dx]<threshold)ink=true;
            if(ink){count++;if(y<2)start=true;if(y>=height-2)end=true;}
        }
        return start&&end&&count>=height*.92;
    }
    private static boolean horizontal(int[] gray,int width,int height,int y,int threshold) {
        int count=0;boolean start=false,end=false;
        for(int x=0;x<width;x++) {
            boolean ink=false;for(int dy=-1;dy<=1;dy++)if(y+dy>=0&&y+dy<height&&gray[(y+dy)*width+x]<threshold)ink=true;
            if(ink){count++;if(x<2)start=true;if(x>=width-2)end=true;}
        }
        return start&&end&&count>=width*.92;
    }
}
