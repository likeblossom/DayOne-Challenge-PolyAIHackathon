package org.dayone.midwife;

import java.util.*;

/** Locate a printed rectangle before measuring its interior, never its border. */
public final class CheckboxReader {
    private CheckboxReader() {}
    public static final class Result {
        public Boolean value;
        public double ink, outlineScore;
        public int left, top, right, bottom;
        public boolean located;
    }
    private static final class Run {
        int left,right,y;
        Run(int left,int right,int y){this.left=left;this.right=right;this.y=y;}
    }
    public static Result read(int[] pixels,int width,int height,double expectedWidth,double expectedHeight) {
        Result result=new Result();
        if(width<8||height<8||pixels.length!=width*height)return result;
        int[] histogram=new int[256],gray=new int[pixels.length];
        for(int i=0;i<pixels.length;i++) {
            int p=pixels[i];int g=(int)Math.round(.299*(p>>16&255)+.587*(p>>8&255)+.114*(p&255));
            gray[i]=g;histogram[g]++;
        }
        int median=0,seen=0;while(median<255&&(seen+=histogram[median])<pixels.length/2)median++;
        int threshold=Math.min(150,median-35);
        if(threshold<35)return result;
        boolean[] dark=new boolean[pixels.length];for(int i=0;i<gray.length;i++)dark[i]=gray[i]<threshold;
        List<Run> runs=new ArrayList<>();
        for(int y=1;y<height-1;y++) {
            int start=-1;
            for(int x=0;x<=width;x++) {
                boolean ink=x<width&&(dark[y*width+x]||dark[(y-1)*width+x]||dark[(y+1)*width+x]);
                if(ink&&start<0)start=x;
                if(!ink&&start>=0) {
                    int length=x-start;
                    if(length>=expectedWidth*.65&&length<=expectedWidth*1.65)runs.add(new Run(start,x-1,y));
                    start=-1;
                }
            }
        }
        double best=-Double.MAX_VALUE;
        for(Run top:runs)for(Run bottom:runs) {
            int h=bottom.y-top.y;
            if(h<expectedHeight*.65||h>expectedHeight*1.65)continue;
            if(Math.abs(top.left-bottom.left)>Math.max(3,expectedWidth*.18)
                    ||Math.abs(top.right-bottom.right)>Math.max(3,expectedWidth*.18))continue;
            int left=(top.left+bottom.left)/2,right=(top.right+bottom.right)/2;
            double center=(left+right)/2.;int tolerance=Math.max(3,(int)Math.ceil(expectedWidth*.25));
            // A tick or cross can protrude beyond the printed top/bottom edge.
            // Snap each side to a persistent vertical border, not the pen overhang.
            left=edge(dark,width,height,left,tolerance,top.y,bottom.y,center-expectedWidth/2);
            right=edge(dark,width,height,right,tolerance,top.y,bottom.y,center+expectedWidth/2);
            int w=right-left;
            if(w<expectedWidth*.65||w>expectedWidth*1.65)continue;
            if(left<2||right>=width-2||top.y<2||bottom.y>=height-2)continue;
            double ls=vertical(dark,width,height,left,top.y,bottom.y),rs=vertical(dark,width,height,right,top.y,bottom.y);
            if(Math.min(ls,rs)<.70)continue;
            double centerDistance=Math.hypot(((left+right)/2.-(width-1)/2.)/expectedWidth,
                    ((top.y+bottom.y)/2.-(height-1)/2.)/expectedHeight);
            if(centerDistance>.85)continue;
            double shape=Math.abs(w/expectedWidth-1)+Math.abs(h/expectedHeight-1);
            double score=(ls+rs)/2-centerDistance*.2-shape*.15;
            if(score>best) {
                best=score;result.located=true;result.left=left;result.right=right;
                result.top=top.y;result.bottom=bottom.y;result.outlineScore=(ls+rs)/2;
            }
        }
        if(!result.located)return result;
        int dx=Math.max(3,(int)Math.ceil((result.right-result.left)*.22));
        int dy=Math.max(3,(int)Math.ceil((result.bottom-result.top)*.22));
        int count=0,total=0;
        for(int y=result.top+dy;y<=result.bottom-dy;y++)for(int x=result.left+dx;x<=result.right-dx;x++) {
            total++;if(dark[y*width+x])count++;
        }
        if(total<9){result.located=false;return result;}
        result.ink=(double)count/total;
        // A one-pixel pen cross can cover less than 19% of the interior.
        // This threshold applies only after a complete printed outline is located;
        // isolated specks and the uncertainty band remain below acceptance.
        result.value=result.ink>.07?Boolean.TRUE:result.ink<.04?Boolean.FALSE:null;
        return result;
    }
    private static double vertical(boolean[] dark,int width,int height,int x,int top,int bottom) {
        int count=0;
        for(int y=top;y<=bottom;y++) {
            boolean found=false;for(int dx=-1;dx<=1;dx++)if(x+dx>=0&&x+dx<width&&dark[y*width+x+dx])found=true;
            if(found)count++;
        }
        return (double)count/(bottom-top+1);
    }
    private static int edge(boolean[] dark,int width,int height,int x,int tolerance,int top,int bottom,double preferred) {
        int best=x;double score=-1;
        for(int candidate=Math.max(1,x-tolerance);candidate<=Math.min(width-2,x+tolerance);candidate++) {
            double value=vertical(dark,width,height,candidate,top,bottom)-Math.abs(candidate-preferred)*.005;
            if(value>score){score=value;best=candidate;}
        }
        return best;
    }
}
