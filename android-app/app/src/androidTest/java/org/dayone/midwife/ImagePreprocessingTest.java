package org.dayone.midwife;
import android.test.AndroidTestCase;
import android.graphics.*;
import java.io.ByteArrayOutputStream;
import org.json.JSONObject;

public class ImagePreprocessingTest extends AndroidTestCase {
    public void testNearLimitDoesNotHalveResolution()throws Exception {
        Bitmap source=Bitmap.createBitmap(2700,1000,Bitmap.Config.ARGB_8888);source.eraseColor(Color.WHITE);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();source.compress(Bitmap.CompressFormat.PNG,100,bytes);source.recycle();
        Bitmap decoded=MobileImages.decode(bytes.toByteArray());
        try{assertEquals(2600,decoded.getWidth());assertEquals(963,decoded.getHeight());assertEquals(Color.WHITE,decoded.getPixel(100,100));}
        finally{decoded.recycle();}
    }
    public void testPadUsesTrainingCenterRounding() {
        Bitmap source=Bitmap.createBitmap(3,2,Bitmap.Config.ARGB_8888);source.eraseColor(Color.BLACK);
        Bitmap padded=MobileImages.fitAntialiased(source,8,8,Color.WHITE);
        try{assertEquals(Color.WHITE,padded.getPixel(4,1));assertEquals(Color.BLACK,padded.getPixel(4,2));assertEquals(Color.BLACK,padded.getPixel(4,6));assertEquals(Color.WHITE,padded.getPixel(4,7));}
        finally{source.recycle();padded.recycle();}
    }
    public void testReaderCanPreserveLineAspectRatio()throws Exception {
        Bitmap source=Bitmap.createBitmap(100,20,Bitmap.Config.ARGB_8888);source.eraseColor(Color.BLACK);
        JSONObject config=new JSONObject("{\"width\":100,\"height\":60,\"processor\":{\"image_processor_type\":\"ViTImageProcessor\",\"sanad_fit\":true}}");
        Bitmap input=MobileOcr.prepareInput(source,config);
        try{assertEquals(100,input.getWidth());assertEquals(60,input.getHeight());assertEquals(Color.WHITE,input.getPixel(50,10));assertEquals(Color.BLACK,input.getPixel(50,30));}
        finally{if(input!=source)input.recycle();source.recycle();}
    }
    public void testReaderRemovesFullHeightEdgeRuleOnlyWhenEnabled()throws Exception {
        Bitmap source=Bitmap.createBitmap(100,40,Bitmap.Config.ARGB_8888);source.eraseColor(Color.WHITE);
        for(int y=0;y<40;y++)source.setPixel(2,y,Color.BLACK);
        JSONObject config=new JSONObject("{\"width\":100,\"height\":40,\"strip_edge_rules\":true,\"processor\":{\"image_processor_type\":\"ViTImageProcessor\"}}");
        Bitmap input=MobileOcr.prepareInput(source,config);
        try{for(int x=0;x<100;x++)assertEquals(Color.WHITE,input.getPixel(x,20));}
        finally{if(input!=source)input.recycle();source.recycle();}
    }
}
