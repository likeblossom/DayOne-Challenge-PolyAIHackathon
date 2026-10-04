package org.dayone.midwife;

import android.graphics.*;
import androidx.exifinterface.media.ExifInterface;
import java.io.*;
import java.nio.*;
import org.json.*;

/** Bounded page decoding; crops are created just-in-time, not retained as a batch. */
public final class MobileImages {
    private MobileImages() {}
    public static Bitmap decode(byte[] bytes) throws Exception {
        BitmapFactory.Options opts=new BitmapFactory.Options();opts.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);
        if(opts.outWidth<=0||opts.outHeight<=0)throw new IOException("Image could not be decoded");
        opts.inSampleSize=1;while(Math.max(opts.outWidth,opts.outHeight)/opts.inSampleSize>2600)opts.inSampleSize*=2;
        opts.inJustDecodeBounds=false;opts.inPreferredConfig=Bitmap.Config.ARGB_8888;
        Bitmap image=BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);if(image==null)throw new IOException("Image decode failed");
        int orientation=new ExifInterface(new ByteArrayInputStream(bytes)).getAttributeInt(ExifInterface.TAG_ORIENTATION,ExifInterface.ORIENTATION_NORMAL);
        Matrix m=new Matrix();
        switch(orientation) {
            case 2:m.setScale(-1,1);break;case 3:m.setRotate(180);break;case 4:m.setScale(1,-1);break;
            case 5:m.setRotate(90);m.postScale(-1,1);break;case 6:m.setRotate(90);break;
            case 7:m.setRotate(-90);m.postScale(-1,1);break;case 8:m.setRotate(-90);break;
        }
        if(!m.isIdentity()){Bitmap rotated=Bitmap.createBitmap(image,0,0,image.getWidth(),image.getHeight(),m,true);if(rotated!=image)image.recycle();image=rotated;}
        return image;
    }
    public static Bitmap fit(Bitmap source,int width,int height,int color) {
        Bitmap out=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);Canvas c=new Canvas(out);c.drawColor(color);
        float scale=Math.min((float)width/source.getWidth(),(float)height/source.getHeight());
        int w=Math.round(source.getWidth()*scale),h=Math.round(source.getHeight()*scale);
        c.drawBitmap(source,null,new Rect((width-w)/2,(height-h)/2,(width-w)/2+w,(height-h)/2+h),new Paint(Paint.FILTER_BITMAP_FLAG));return out;
    }
    public static FloatBuffer tensor(Bitmap image,int width,int height,double[] mean,double[] std) {
        Bitmap scaled=Bitmap.createScaledBitmap(image,width,height,true);
        FloatBuffer out=ByteBuffer.allocateDirect(3*width*height*4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        int[] row=new int[width];int plane=width*height;
        for(int y=0;y<height;y++){scaled.getPixels(row,0,width,0,y,width,1);for(int x=0;x<width;x++){
            int p=row[x],offset=y*width+x;out.put(offset,(float)(((p>>16&255)/255.-mean[0])/std[0]));out.put(plane+offset,(float)(((p>>8&255)/255.-mean[1])/std[1]));out.put(2*plane+offset,(float)(((p&255)/255.-mean[2])/std[2]));
        }}
        if(scaled!=image)scaled.recycle();return out;
    }
    public static double[] vector(JSONArray a) throws JSONException {double[] v=new double[a.length()];for(int i=0;i<v.length;i++)v[i]=a.getDouble(i);return v;}
    public static float[][] points(JSONArray a) throws JSONException {float[][] p=new float[a.length()][2];for(int i=0;i<p.length;i++){p[i][0]=(float)a.getJSONArray(i).getDouble(0);p[i][1]=(float)a.getJSONArray(i).getDouble(1);}return p;}
    public static double[] frame(float[][] p) {
        double cx=0,cy=0,best=-1,ux=1,uy=0,w=1,h=1;
        for(int i=0;i<4;i++){cx+=p[i][0]/4.;cy+=p[i][1]/4.;double dx=p[(i+1)%4][0]-p[i][0],dy=p[(i+1)%4][1]-p[i][1],len=Math.hypot(dx,dy),horizontal=Math.abs(dx)/Math.max(len,1e-6);
            if(horizontal>best){best=horizontal;w=len;h=Math.hypot(p[(i+2)%4][0]-p[(i+1)%4][0],p[(i+2)%4][1]-p[(i+1)%4][1]);ux=dx/Math.max(len,1e-6);uy=dy/Math.max(len,1e-6);}}
        if(ux<0){ux=-ux;uy=-uy;}return new double[]{cx,cy,ux,uy,w,h};
    }
    public static float[][] world(JSONArray region,float[][] anchor) throws JSONException {
        float[][] points=points(region);double[] f=frame(anchor);
        for(float[] p:points){double x=p[0]*f[4],y=p[1]*f[5];p[0]=(float)(f[0]+x*f[2]-y*f[3]);p[1]=(float)(f[1]+x*f[3]+y*f[2]);}return points;
    }
    public static Bitmap crop(Bitmap page,float[][] points,double pad) {
        double[] f=frame(points);double w=f[4]+Math.max(4,f[5]*.15)*2,h=f[5]+Math.max(3,f[5]*pad)*2;
        int width=Math.max(8,Math.min((int)Math.round(w),page.getWidth()*2)),height=Math.max(8,Math.min((int)Math.round(h),page.getHeight()*2));
        float[] src=new float[8];int[] xs={-1,1,1,-1},ys={-1,-1,1,1};for(int i=0;i<4;i++){src[i*2]=(float)(f[0]+xs[i]*w/2*f[2]-ys[i]*h/2*f[3]);src[i*2+1]=(float)(f[1]+xs[i]*w/2*f[3]+ys[i]*h/2*f[2]);}
        Matrix matrix=new Matrix();matrix.setPolyToPoly(src,0,new float[]{0,0,width-1,0,width-1,height-1,0,height-1},0,4);
        Bitmap out=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(out);canvas.drawColor(Color.WHITE);canvas.drawBitmap(page,matrix,new Paint(Paint.FILTER_BITMAP_FLAG));return out;
    }
    public static Boolean mark(Bitmap image) {
        int count=0,total=0;for(int y=(int)(image.getHeight()*.3);y<Math.max((int)(image.getHeight()*.7),(int)(image.getHeight()*.3)+1);y++)for(int x=(int)(image.getWidth()*.3);x<Math.max((int)(image.getWidth()*.7),(int)(image.getWidth()*.3)+1);x++){
            int c=image.getPixel(x,y);double gray=.299*(c>>16&255)+.587*(c>>8&255)+.114*(c&255);if(gray<140)count++;total++;
        }double ink=(double)count/Math.max(1,total);return ink>.19?Boolean.TRUE:ink<.06?Boolean.FALSE:null;
    }
}
