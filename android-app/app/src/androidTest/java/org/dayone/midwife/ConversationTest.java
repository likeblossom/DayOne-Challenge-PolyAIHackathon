package org.dayone.midwife;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.os.SystemClock;
import android.test.InstrumentationTestCase;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.util.*;

/** Synthetic-only UI smoke test on a disposable emulator. */
public final class ConversationTest extends InstrumentationTestCase {
    private MainActivity activity;
    private EncryptedStore store;
    private void main(Runnable action) { getInstrumentation().runOnMainSync(action); }
    private View find(View view,String prefix) {
        if(view instanceof TextView && ((TextView)view).getText().toString().startsWith(prefix)) return view;
        if(view instanceof ViewGroup) for(int i=0;i<((ViewGroup)view).getChildCount();i++) { View found=find(((ViewGroup)view).getChildAt(i),prefix); if(found!=null) return found; }
        return null;
    }
    private void click(String prefix) {
        main(() -> { View view=find(activity.getWindow().getDecorView(),prefix); assertNotNull("Missing UI: "+prefix,view); view.performClick(); });
        getInstrumentation().waitForIdleSync();
    }
    private void checkAll(View view) {
        if(view instanceof CheckBox) ((CheckBox)view).setChecked(true);
        if(view instanceof ViewGroup) for(int i=0;i<((ViewGroup)view).getChildCount();i++) checkAll(((ViewGroup)view).getChildAt(i));
    }
    private void dialogButton(String label) {
        // Exercise the actual dialog button on the UI thread, independently of system overlays.
        main(() -> {
            AlertDialog dialog=activity.activeDialog;
            assertNotNull("Missing dialog: "+label,dialog); assertTrue(dialog.isShowing());
            Button button=dialog.getButton(AlertDialog.BUTTON_POSITIVE);
            assertTrue("Unexpected dialog button: "+button.getText(),label.equalsIgnoreCase(button.getText().toString()));
            button.performClick();
        });
        getInstrumentation().waitForIdleSync();
    }
    private JSONObject waitState(String id,String state) throws Exception {
        long end=SystemClock.uptimeMillis()+45000;
        while(SystemClock.uptimeMillis()<end) { JSONObject r=store.get(id); if(r.optString("state").equals(state)) return r; SystemClock.sleep(250); }
        fail("Expected "+state+", got "+store.get(id).optString("state")); return null;
    }
    public void testCaptureReviewSubmitReconnectAndReopen() throws Exception {
        Context context=getInstrumentation().getTargetContext(); store=new EncryptedStore(context);
        context.getSharedPreferences("settings",0).edit().putBoolean("demo_offline",true).commit();
        store.json("session.enc",new JSONObject().put("patient_code","UI-"+UUID.randomUUID().toString().substring(0,6)).put("document_id",UUID.randomUUID().toString()));
        Set<String> before=new HashSet<>(); for(JSONObject r:store.records()) before.add(r.getString("id"));
        Intent intent=new Intent(context,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        activity=(MainActivity)getInstrumentation().startActivitySync(intent); getInstrumentation().waitForIdleSync();
        try {
            click("Try a sample page"); String id=null;
            for(JSONObject r:store.records()) if(!before.contains(r.getString("id"))) id=r.getString("id");
            assertNotNull(id); JSONObject record=waitState(id,"NEEDS_REVIEW");
            SchemaCatalog catalog=new SchemaCatalog(context); final FormEditor[] editor={null};
            main(() -> {
                try {
                    editor[0]=new FormEditor(activity,catalog.title(record.getString("form_id")),catalog.schema(record.getString("form_id")).getJSONObject("fields"),record.getJSONObject("fields"),fields -> { record.put("fields",fields); store.save(record); });
                    editor[0].show(); checkAll(editor[0].getWindow().getDecorView());
                    View save=find(editor[0].getWindow().getDecorView(),"Save changes"); assertNotNull(save); save.performClick();
                } catch(Exception e) { throw new RuntimeException(e); }
            });
            assertEquals(.68,store.get(id).getJSONObject("fields").getJSONObject("temperature_c").getDouble("confidence"),.001);
            SystemClock.sleep(5500); getInstrumentation().waitForIdleSync();
            click("Submit record"); dialogButton("Submit"); waitState(id,"REGISTERED");
            main(() -> { View offline=find(activity.getWindow().getDecorView(),"○ Offline"); assertNotNull(offline); offline.performClick(); });
            dialogButton("Go online"); waitState(id,"SYNCED");
            main(() -> activity.finish());
            activity=(MainActivity)getInstrumentation().startActivitySync(intent); getInstrumentation().waitForIdleSync();
            main(() -> {
                assertNotNull(find(activity.getWindow().getDecorView(),"✓ Saved to demo database"));
                View view=activity.getWindow().getDecorView(); Bitmap image=Bitmap.createBitmap(view.getWidth(),view.getHeight(),Bitmap.Config.ARGB_8888); view.draw(new Canvas(image));
                try(FileOutputStream out=new FileOutputStream(new File(context.getFilesDir(),"ui-smoke.png"))) { image.compress(Bitmap.CompressFormat.PNG,100,out); } catch(IOException e) { throw new RuntimeException(e); }
            });
        } finally { if(activity!=null) main(() -> activity.finish()); }
    }
}
