package org.dayone.midwife;
import android.test.ActivityInstrumentationTestCase2;
import android.view.*;

/** Uses the already imported specimen; never changes its values or submits it. */
public final class ImageViewerTest extends ActivityInstrumentationTestCase2<MainActivity> {
    public ImageViewerTest(){super(MainActivity.class);}
    private View find(View v,boolean zoom){
        if(zoom&&v instanceof ZoomPageView)return v;
        if(!zoom&&"View original attached to these results".contentEquals(v.getContentDescription()==null?"":v.getContentDescription()))return v;
        if(v instanceof ViewGroup){ViewGroup group=(ViewGroup)v;for(int i=0;i<group.getChildCount();i++){View found=find(group.getChildAt(i),zoom);if(found!=null)return found;}}
        return null;
    }
    public void testAttachmentExpandsAndCloses()throws Exception {
        MainActivity activity=getActivity();getInstrumentation().waitForIdleSync();
        getInstrumentation().runOnMainSync(() -> {View attachment=find(activity.getWindow().getDecorView(),false);assertNotNull("Import a specimen first",attachment);attachment.performClick();});
        final boolean[] ready={false};
        for(int i=0;i<100&&!ready[0];i++){Thread.sleep(100);getInstrumentation().runOnMainSync(() -> {ready[0]=activity.activeDialog!=null&&find(activity.activeDialog.getWindow().getDecorView(),true)!=null;});}
        assertTrue("Expandable original did not load",ready[0]);
        getInstrumentation().runOnMainSync(() -> {ZoomPageView view=(ZoomPageView)find(activity.activeDialog.getWindow().getDecorView(),true);assertTrue(view.getWidth()>0);view.reset();activity.activeDialog.dismiss();});
        assertFalse(activity.activeDialog.isShowing());
    }
}
