package org.dayone.midwife;
import android.content.Context;
import android.graphics.*;
import android.view.*;

/** In-app inspection of the encrypted original; pinch, drag and double-tap. */
public final class ZoomPageView extends View {
    private final Bitmap page;private final Paint paint=new Paint(Paint.FILTER_BITMAP_FLAG);
    private final ScaleGestureDetector pinch;private final GestureDetector gestures;
    private float scale=1,base=1,x=0,y=0;
    public ZoomPageView(Context c,Bitmap bitmap){
        super(c);page=bitmap;setContentDescription("Original page. Pinch to zoom, drag to pan, double tap to reset.");
        pinch=new ScaleGestureDetector(c,new ScaleGestureDetector.SimpleOnScaleGestureListener(){@Override public boolean onScale(ScaleGestureDetector d){zoom(d.getScaleFactor(),d.getFocusX(),d.getFocusY());return true;}});
        gestures=new GestureDetector(c,new GestureDetector.SimpleOnGestureListener(){
            @Override public boolean onDown(android.view.MotionEvent e){return true;}
            @Override public boolean onScroll(android.view.MotionEvent a,android.view.MotionEvent b,float dx,float dy){if(!pinch.isInProgress()){x-=dx;y-=dy;constrain();invalidate();}return true;}
            @Override public boolean onDoubleTap(android.view.MotionEvent e){if(scale>base*1.1f)reset();else zoom(3,e.getX(),e.getY());return true;}
            @Override public boolean onSingleTapUp(android.view.MotionEvent e){performClick();return true;}
        });
    }
    private void zoom(float factor,float fx,float fy){float next=Math.max(base,Math.min(base*10,scale*factor)),ratio=next/scale;x=fx-(fx-x)*ratio;y=fy-(fy-y)*ratio;scale=next;constrain();invalidate();}
    private void constrain(){float w=page.getWidth()*scale,h=page.getHeight()*scale;x=w<=getWidth()?(getWidth()-w)/2:Math.max(getWidth()-w,Math.min(0,x));y=h<=getHeight()?(getHeight()-h)/2:Math.max(getHeight()-h,Math.min(0,y));}
    public void reset(){base=Math.min((float)getWidth()/page.getWidth(),(float)getHeight()/page.getHeight());scale=base;constrain();invalidate();}
    @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){reset();}
    @Override protected void onDraw(Canvas c){c.drawColor(Color.rgb(22,26,28));c.save();c.translate(x,y);c.scale(scale,scale);c.drawBitmap(page,0,0,paint);c.restore();}
    @Override public boolean onTouchEvent(android.view.MotionEvent e){pinch.onTouchEvent(e);gestures.onTouchEvent(e);return true;}
    @Override public boolean performClick(){super.performClick();return true;}
}
