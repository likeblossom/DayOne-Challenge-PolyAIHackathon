package org.dayone.midwife;

import android.app.*;
import android.content.*;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.net.*;
import android.os.*;
import android.provider.MediaStore;
import android.view.*;
import android.widget.*;
import org.json.*;
import org.dayone.midwife.model.PresetForm;
import java.io.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    private static final int GREEN=0xFF075E54, TEAL=0xFF087F6B, INK=0xFF193C35, MUTED=0xFF6D7D76;
    private static final ExecutorService worker=Executors.newSingleThreadExecutor();
    private static final Set<String> parsing=ConcurrentHashMap.newKeySet();
    private final Map<String,Bitmap> thumbnails=new HashMap<>();
    private EncryptedStore store;
    private SchemaCatalog catalog;
    private FormParser parser;
    private LinearLayout root, timeline;
    private ScrollView scroll;
    private TextView connection, sessionLabel;
    AlertDialog activeDialog;
    private String formId="late_postnatal_newborn", patientCode, documentId, retakeId;
    private boolean importing, destroyed;
    private static final java.util.concurrent.atomic.AtomicBoolean modelImport=new java.util.concurrent.atomic.AtomicBoolean();
    private static volatile String modelImportStatus="";
    private static final ExecutorService syncWorker=Executors.newSingleThreadExecutor();
    private final java.util.concurrent.atomic.AtomicBoolean syncing=new java.util.concurrent.atomic.AtomicBoolean();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable refresh=new Runnable() { @Override public void run() { if(!destroyed) { render(false); sync(); handler.postDelayed(this,5000); } } };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state); if(!BuildConfig.DEMO_CAPTURE)getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        if(Build.VERSION.SDK_INT>=27) {
            getWindow().setNavigationBarColor(0xFFF6F5F0);
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        }
        try {
            store=new EncryptedStore(this); catalog=new SchemaCatalog(this); parser=new OnDeviceFormParser(this,catalog);
            JSONObject session=store.json("session.enc");
            patientCode=session.optString("patient_code",""); documentId=session.optString("document_id","");
            if(patientCode.isEmpty()) newSession();
            if(state!=null) { formId=state.getString("form_id",formId); retakeId=state.getString("retake_id"); }
            build(); render(true); resumePending();
            sync(); handler.postDelayed(refresh,5000);
        } catch(Exception e) { fatal(e); }
    }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); state.putString("form_id",formId); state.putString("retake_id",retakeId); }
    @Override protected void onResume() { super.onResume(); if(store!=null && timeline!=null) { render(false); sync(); } }
    @Override protected void onDestroy() {
        destroyed=true; handler.removeCallbacksAndMessages(null);
        if(activeDialog!=null) activeDialog.dismiss();
        super.onDestroy();
    }
    private void newSession() throws Exception {
        patientCode="MW-"+UUID.randomUUID().toString().substring(0,6).toUpperCase(Locale.ROOT);
        documentId=UUID.randomUUID().toString(); saveSession();
    }
    private void saveSession() throws Exception { store.json("session.enc",new JSONObject().put("patient_code",patientCode).put("document_id",documentId)); }
    private int dp(float n) { return Math.round(n*getResources().getDisplayMetrics().density); }
    private GradientDrawable bg(int color,int radius) { GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); return d; }
    private LinearLayout vertical() { LinearLayout l=new LinearLayout(this); l.setOrientation(LinearLayout.VERTICAL); return l; }
    private LinearLayout horizontal() { LinearLayout l=new LinearLayout(this); l.setGravity(Gravity.CENTER_VERTICAL); return l; }
    private TextView text(String value,int size,int color) { TextView t=new TextView(this); t.setText(value); t.setTextSize(size); t.setTextColor(color); t.setLineSpacing(dp(3),1); return t; }
    private TextView bold(String value,int size,int color) { TextView t=text(value,size,color); t.setTypeface(null,Typeface.BOLD); return t; }
    private void pad(View view,int n) { view.setPadding(dp(n),dp(n),dp(n),dp(n)); }
    private TextView button(String label,boolean primary,Runnable action) {
        TextView t=bold(label,14,primary?Color.WHITE:TEAL); t.setGravity(Gravity.CENTER); t.setMinHeight(dp(48)); t.setPadding(dp(12),dp(10),dp(12),dp(10)); t.setBackground(bg(primary?TEAL:0xFFE8F3ED,12));
        t.setOnClickListener(v -> action.run()); return t;
    }
    private View iconButton(String type,String description,int color,Runnable action) {
        Icon icon=new Icon(type,color); icon.setContentDescription(description); icon.setOnClickListener(v -> action.run()); icon.setLayoutParams(new LinearLayout.LayoutParams(dp(48),dp(48))); return icon;
    }
    private void build() {
        root=vertical(); root.setBackgroundColor(0xFFEFEAE2); setContentView(root);
        LinearLayout header=horizontal(); header.setPadding(dp(8),dp(6),dp(8),dp(6)); header.setBackgroundColor(GREEN);
        TextView avatar=bold("d₁",24,Color.WHITE); avatar.setGravity(Gravity.CENTER); avatar.setBackground(bg(0xFF278277,26)); header.addView(avatar,new LinearLayout.LayoutParams(dp(46),dp(46)));
        LinearLayout identity=vertical(); identity.setPadding(dp(12),0,0,0); identity.addView(bold("Sanad",21,Color.WHITE)); identity.addView(text("Your registry companion",12,0xFFCEE4DC)); header.addView(identity,new LinearLayout.LayoutParams(0,-2,1));
        header.addView(iconButton("file","Saved records",Color.WHITE,this::showRecords)); header.addView(iconButton("more","Settings",Color.WHITE,this::settings)); root.addView(header);
        LinearLayout strip=horizontal(); strip.setBackgroundColor(0xFFF9FAF6); strip.setPadding(dp(16),dp(8),dp(12),dp(8));
        sessionLabel=bold("",12,INK); sessionLabel.setCompoundDrawablePadding(dp(4)); sessionLabel.setOnClickListener(v -> sessions()); strip.addView(sessionLabel,new LinearLayout.LayoutParams(0,dp(36),1)); sessionLabel.setGravity(Gravity.CENTER_VERTICAL);
        connection=bold("",12,TEAL); pad(connection,9); connection.setBackground(bg(0xFFE4EEE5,20)); connection.setOnClickListener(v -> toggleOffline()); strip.addView(connection); root.addView(strip);
        FrameLayout conversation=new FrameLayout(this); conversation.addView(new Wallpaper());
        scroll=new ScrollView(this); scroll.setFillViewport(true); scroll.setClipToPadding(false); timeline=vertical(); timeline.setPadding(dp(14),dp(16),dp(14),dp(20)); scroll.addView(timeline); conversation.addView(scroll); root.addView(conversation,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout composer=horizontal(); composer.setPadding(dp(10),dp(8),dp(10),dp(10)); composer.setBackgroundColor(0xFFF6F5F0);
        LinearLayout input=horizontal(); input.setBackground(bg(Color.WHITE,28)); input.addView(iconButton("clip","Upload an image",MUTED,() -> gallery(null)));
        TextView prompt=text("Add a registry page…",15,MUTED); prompt.setOnClickListener(v -> captureMenu(null)); input.addView(prompt,new LinearLayout.LayoutParams(0,dp(48),1));
        input.addView(iconButton("file","Enter a form manually",MUTED,this::manual)); composer.addView(input,new LinearLayout.LayoutParams(0,dp(52),1));
        View camera=iconButton("camera","Take a picture",Color.WHITE,() -> camera(null)); camera.setBackground(bg(TEAL,28)); LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(dp(52),dp(52)); cp.leftMargin=dp(8); composer.addView(camera,cp); root.addView(composer);
    }
    private void center(String label,int color) {
        TextView t=text(label,11,color); t.setGravity(Gravity.CENTER); t.setPadding(dp(10),dp(6),dp(10),dp(6)); t.setBackground(bg(0xDDF8F7EF,8));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-2,-2); p.gravity=Gravity.CENTER; p.bottomMargin=dp(14); timeline.addView(t,p);
    }
    private LinearLayout bubble(boolean outgoing) {
        LinearLayout box=vertical(); box.setBackground(bg(outgoing?0xFFD9FDD3:Color.WHITE,14)); pad(box,15); box.setElevation(dp(1));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2); p.bottomMargin=dp(12); if(outgoing) p.leftMargin=dp(52); else p.rightMargin=dp(16); timeline.addView(box,p); return box;
    }
    private void gap(LinearLayout box,int height) { box.addView(new View(this),new LinearLayout.LayoutParams(1,dp(height))); }
    private void stamp(LinearLayout box,String label) { TextView t=text(label,10,MUTED); t.setGravity(Gravity.END); box.addView(t); }
    private String lastRender="";
    private void render(boolean bottom) {
        if(destroyed || timeline==null) return;
        try {
            List<JSONObject> records=store.records();
            long queued=records.stream().filter(r -> SyncEngine.pending(r)).count();
            boolean online=SyncEngine.online(this);
            connection.setText(online?"● USB connected":"○ Offline · saved locally");
            sessionLabel.setText(patientCode + "  ▾" + (queued>0?"  ·  "+queued+" queued":""));
            boolean modelsInstalled=new File(getFilesDir(),"sanad-models-v1/manifest.json").isFile();
            String signature=records.toString()+patientCode+online+modelImportStatus+modelsInstalled;
            if(signature.equals(lastRender) && !bottom) return; lastRender=signature;
            int y=scroll.getScrollY(); timeline.removeAllViews();
            center("DEMO WORKSPACE  ·  SYNTHETIC DATA ONLY",MUTED);
            LinearLayout welcome=bubble(false);
            if(!modelsInstalled||modelImport.get())welcome.addView(button(modelImport.get()?modelImportStatus:"Import model pack",true,this::chooseModelPack));
            else if(!modelImportStatus.isEmpty())welcome.addView(text(modelImportStatus,13,TEAL));
            welcome.addView(bold("Paper to record. One page at a time.",19,INK)); gap(welcome,7);
            welcome.addView(text("Take a photo or attach a registry page. I’ll prepare the fields, then you check and submit them.",15,INK)); gap(welcome,10);
            welcome.addView(text("Sanad offline OCR · eight-form model pack required\nSample button below uses synthetic demo values",12,TEAL)); gap(welcome,12);
            welcome.addView(button("Try a sample page  →",false,this::demo)); stamp(welcome,"DayOne  ·  private on this device");
            for(JSONObject record:records) if(record.optString("document_id").equals(documentId)) recordCard(record);
            if(queued>0) center(online?"Syncing the local queue…":"Saved locally. Queued records sync when you’re online.",TEAL);
            scroll.post(() -> { if(bottom) scroll.fullScroll(View.FOCUS_DOWN); else scroll.scrollTo(0,y); });
        } catch(Exception e) { error(e); }
    }
    private void recordCard(JSONObject r) throws Exception {
        String id=r.getString("id"), state=r.getString("state");
        if(state.equals("SYNCED")&&!r.has("pc_receipt"))state="REGISTERED";
        LinearLayout sent=bubble(true);
        if(r.has("image_file")) {
            Bitmap image=thumbnails.get(id);
            if(image==null) {
                byte[] bytes=store.read(r.getString("image_file")); BitmapFactory.Options opts=new BitmapFactory.Options(); opts.inJustDecodeBounds=true; BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);
                opts.inSampleSize=Math.max(1,Math.max(opts.outWidth,opts.outHeight)/800); opts.inJustDecodeBounds=false;
                image=BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts); thumbnails.put(id,image);
            }
            ImageView photo=new ImageView(this); photo.setImageBitmap(image); photo.setScaleType(ImageView.ScaleType.FIT_CENTER); photo.setContentDescription("Open original registry page"); photo.setOnClickListener(v -> showOriginal(r)); sent.addView(photo,new LinearLayout.LayoutParams(-1,dp(170)));
        } else {
            LinearLayout preview=horizontal(); preview.addView(new Icon("file",TEAL),new LinearLayout.LayoutParams(dp(40),dp(48)));
            preview.addView(bold(r.optBoolean("manual")?"Manual entry":"Synthetic sample page",15,INK)); sent.addView(preview);
        }
        gap(sent,7); sent.addView(text("Registry page · " + patientCode + (r.has("image_file")?" · tap image to expand":""),13,INK)); stamp(sent,time(r.optString("captured_at")) + "  ✓✓");
        LinearLayout card=bubble(false);
        if(state.equals("SUPERSEDED")) { card.addView(text("Photo replaced. The previous capture is retained in encrypted storage.",14,MUTED)); return; }
        if(state.equals("PENDING_AI") || state.equals("CAPTURED")) {
            card.addView(bold("Preparing your page…",17,INK)); gap(card,8); ProgressBar progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal); progress.setIndeterminate(true); card.addView(progress);
            card.addView(text(r.has("image_file")?"Running offline form detection and OCR. Your encrypted capture is already saved.":"Running the explicitly synthetic sample demo; no photo is being read.",13,MUTED)); return;
        }
        if(state.equals("PROCESSING_FAILED")) {
            card.addView(bold("This page needs another try",17,INK)); card.addView(text("Your original photo is safe. "+r.optString("processing_error","Retry extraction or enter the fields manually."),14,MUTED));
            card.addView(button("Retry parsing",false,() -> parse(id))); card.addView(button("Enter manually",false,() -> recoverManual(r))); return;
        }
        String type=r.getString("form_id"); JSONObject fields=r.getJSONObject("fields");
        List<SchemaCatalog.Row> rows=SchemaCatalog.rows(catalog.schema(type).getJSONObject("fields"),fields);
        int uncertain=(int)rows.stream().filter(SchemaCatalog.Row::needsReview).count();
        boolean submitted=state.equals("REGISTERED") || state.equals("SYNCED") || state.equals("SYNC_FAILED");
        card.addView(bold(submitted?(state.equals("SYNCED")?"✓ Synced to PC database":"✓ Saved securely on this phone"):uncertain==0?"Your results are ready":"Your page is ready to review",17,INK)); gap(card,5);
        if(r.has("image_file")){ImageView attachment=new ImageView(this);attachment.setImageBitmap(thumbnails.get(id));attachment.setScaleType(ImageView.ScaleType.FIT_CENTER);attachment.setContentDescription("View original attached to these results");attachment.setOnClickListener(v -> showOriginal(r));card.addView(attachment,new LinearLayout.LayoutParams(-1,dp(190)));card.addView(button("Expand original image",false,() -> showOriginal(r)));gap(card,8);}
        card.addView(text(catalog.title(type),14,TEAL)); card.addView(text(catalog.schema(type).optString("title_fr"),11,MUTED)); gap(card,12);
        TextView badge=bold(submitted?(state.equals("SYNCED")?"SYNCED · PC SQLITE DATABASE":"OFFLINE QUEUE · ENCRYPTED"):uncertain+" fields to check · "+(r.optBoolean("mock")?"demo confidence":"uncalibrated confidence"),11,uncertain>0&&!submitted?0xFF946322:TEAL); card.addView(badge); gap(card,10);
        List<SchemaCatalog.Row> populated=new ArrayList<>(); for(SchemaCatalog.Row row:rows) if(!row.field.isNull("value")) populated.add(row);
        populated.sort((a,b) -> Boolean.compare(b.needsReview(),a.needsReview()));
        for(int i=0;i<Math.min(5,populated.size());i++) fieldRow(card,populated.get(i));
        final boolean[] expanded={false}; LinearLayout all=vertical(); all.setVisibility(View.GONE); card.addView(all);
        TextView expand=button("View all " + rows.size() + " fields  ↓",false,() -> {
            try { if(all.getChildCount()==0) for(SchemaCatalog.Row row:rows) fieldRow(all,row); expanded[0]=!expanded[0]; all.setVisibility(expanded[0]?View.VISIBLE:View.GONE); }
            catch(Exception e) { error(e); }
        }); card.addView(expand); gap(card,10);
        if(!submitted) {
            card.addView(text(uncertain>0?"Please check the marked values against the paper. Edit a value or mark it as checked before submitting.":"Check the extracted data, then submit when you’re ready.",13,MUTED)); gap(card,12);
            card.addView(button("Submit record  ✓",true,() -> submit(id)));
            LinearLayout actions=horizontal(); TextView edit=button("Edit data",false,() -> edit(id)); TextView retake=button("Retake",false,() -> captureMenu(id));
            LinearLayout.LayoutParams a=new LinearLayout.LayoutParams(0,-2,1); a.rightMargin=dp(6); actions.addView(edit,a); actions.addView(retake,new LinearLayout.LayoutParams(0,-2,1)); gap(card,7); card.addView(actions);
        } else {
            card.addView(text(state.equals("SYNCED")?"Transferred over USB to the PC database. Your local copy remains available.":state.equals("SYNC_FAILED")?"USB transfer did not finish. Your record is safe locally and will retry.":"Saved locally. This reviewed record transfers when the PC USB database is connected.",13,MUTED));
            if(state.equals("SYNC_FAILED")) card.addView(button("Retry sync",false,this::sync));
        }
        gap(card,8); stamp(card,"DayOne  ·  " + state.toLowerCase(Locale.ROOT).replace('_',' '));
    }
    private void fieldRow(LinearLayout parent,SchemaCatalog.Row row) {
        LinearLayout field=vertical(); field.setPadding(0,dp(8),0,dp(8));
        field.addView(text(row.label,12,MUTED)); LinearLayout value=horizontal();
        String shown=row.field.isNull("value")?"—":row.field.opt("value").toString().replace('_',' ');
        value.addView(bold(shown,15,INK),new LinearLayout.LayoutParams(0,-2,1));
        TextView score=bold(Math.round(row.field.optDouble("confidence")*100)+"%",12,row.needsReview()?0xFF946322:TEAL); pad(score,5); score.setBackground(bg(row.needsReview()?0xFFFFF1D6:0xFFEDF5EF,7)); value.addView(score); field.addView(value);
        field.addView(text(row.field.optString("status").replace('_',' ') + (row.field.optBoolean("human_reviewed")?" · checked by you":""),10,MUTED)); parent.addView(field);
        View line=new View(this); line.setBackgroundColor(0xFFEDF0EA); parent.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));
    }
    private String time(String iso) { try { return java.time.format.DateTimeFormatter.ofPattern("HH:mm").withZone(java.time.ZoneId.systemDefault()).format(Instant.parse(iso)); } catch(Exception e) { return ""; } }
    private void settings() {
        LinearLayout panel=vertical(); pad(panel,20);panel.addView(button("Import model pack",true,() -> {if(activeDialog!=null)activeDialog.dismiss();chooseModelPack();}));gap(panel,12);panel.addView(text("Sample / manual form",14,MUTED));
        List<String> ids=new ArrayList<>(catalog.forms.keySet()); List<String> titles=new ArrayList<>(); for(String id:ids) titles.add(catalog.title(id));
        Spinner select=new Spinner(this); ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,titles); select.setAdapter(adapter); select.setSelection(ids.indexOf(formId)); panel.addView(select);
        panel.addView(text("Results and images stay saved on this phone. Reviewed, submitted records transfer to the PC only when its authenticated USB database is reachable. Wi-Fi and mobile data are not used.",13,MUTED));
        activeDialog=new AlertDialog.Builder(this).setTitle("Settings").setView(panel).setNegativeButton("Cancel",null).setPositiveButton("Apply",(d,w) -> {formId=ids.get(select.getSelectedItemPosition());render(false);sync();}).show();
    }
    private void chooseModelPack() {
        if(modelImport.get()){Toast.makeText(this,modelImportStatus,Toast.LENGTH_SHORT).show();return;}
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
        try{startActivityForResult(intent,102);}catch(ActivityNotFoundException e){error(new IOException("No file picker is installed."));}
    }
    private void importModelPack(Uri uri) {
        if(!modelImport.compareAndSet(false,true))return;
        modelImportStatus="Importing models…";render(false);
        Context app=getApplicationContext();getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        worker.submit(() -> {
            try(InputStream in=app.getContentResolver().openInputStream(uri)){
                if(in==null)throw new IOException("Cannot open model ZIP");
                final int[] last={-1};ModelPackInstaller.install(app.getFilesDir(),in,(done,total) -> {
                    int pct=(int)(100*done/Math.max(1,total));if(pct==last[0])return;last[0]=pct;modelImportStatus="Importing models · "+pct+"%";runOnUiThread(() -> render(false));
                });modelImportStatus="Models ready";
                runOnUiThread(() -> {if(!destroyed)Toast.makeText(this,"Models ready",Toast.LENGTH_LONG).show();});
            }catch(Exception e){modelImportStatus="Import failed. Select the Sanad model ZIP and try again.";runOnUiThread(() -> {if(!destroyed)error(e);});}
            finally{modelImport.set(false);runOnUiThread(() -> {if(!destroyed){getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);render(false);}});}
        });
    }
    private void toggleOffline() {
        activeDialog=new AlertDialog.Builder(this).setTitle("USB database sync")
            .setMessage("Offline: all results remain saved on this phone.\n\nOnline: connect USB and start the PC sync server with ADB reverse. Reviewed and submitted records transfer automatically; drafts remain local.")
            .setNegativeButton("Close",null).setPositiveButton("Check USB connection",(d,w) -> sync()).show();
    }
    private void showOriginal(JSONObject record) {
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Original page").setMessage("Loading encrypted original…").setNegativeButton("Close",null).create();
        activeDialog=dialog;dialog.show();if(!BuildConfig.DEMO_CAPTURE)dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        worker.submit(() -> {
            try {
                Bitmap page=MobileImages.decode(store.read(record.getString("image_file")));
                runOnUiThread(() -> {
                    if(destroyed||!dialog.isShowing()){page.recycle();return;}
                    LinearLayout panel=vertical();panel.setBackgroundColor(Color.WHITE);
                    panel.addView(text("Pinch to zoom · drag to pan · double tap to reset",13,MUTED));
                    ZoomPageView view=new ZoomPageView(this,page);panel.addView(view,new LinearLayout.LayoutParams(-1,0,1));
                    panel.addView(button("Close image",false,dialog::dismiss));
                    dialog.setContentView(panel);dialog.getWindow().setLayout(-1,-1);
                    dialog.setOnDismissListener(d -> {view.setVisibility(View.GONE);page.recycle();});
                });
            } catch(Exception e){runOnUiThread(() -> {dialog.dismiss();error(e);});}
        });
    }
    private void captureMenu(String replacing) { new AlertDialog.Builder(this).setTitle(replacing==null?"Add registry page":"Replace this photo").setItems(new String[]{"Take a picture","Upload an image"},(d,w) -> { if(w==0) camera(replacing); else gallery(replacing); }).show(); }
    private void gallery(String replacing) {
        if(importing) return; retakeId=replacing;
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE);
        if(BuildConfig.DEMO_CAPTURE)intent.putExtra("android.provider.extra.INITIAL_URI",Uri.parse("content://com.android.externalstorage.documents/document/primary%3ADownload%2FSanad-demo"));
        try { startActivityForResult(intent,100); } catch(ActivityNotFoundException e) { error(new Exception("No image picker is installed.")); }
    }
    private void camera(String replacing) {
        if(importing) return; retakeId=replacing;
        Intent intent=new Intent(MediaStore.ACTION_IMAGE_CAPTURE).putExtra(MediaStore.EXTRA_OUTPUT,CameraProvider.URI)
            .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setClipData(ClipData.newRawUri("Registry capture",CameraProvider.URI));
        try { startActivityForResult(intent,101); } catch(ActivityNotFoundException e) { error(new Exception("No camera app is available. Use Upload an image.")); }
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request==102){if(result==RESULT_OK&&data!=null&&data.getData()!=null)importModelPack(data.getData());return;}
        if(request!=100 && request!=101) return;
        if(result!=RESULT_OK) { if(request==101) new File(getCacheDir(),"capture.jpg").delete(); retakeId=null; return; }
        Uri uri=request==101?CameraProvider.URI:data==null?null:data.getData();
        if(uri==null) { error(new Exception("No image selected.")); return; }
        importing=true; final String replacing=retakeId; retakeId=null;
        final String selectedForm=formId, code=patientCode, document=documentId;
        worker.submit(() -> {
            try(InputStream in=getContentResolver().openInputStream(uri); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                byte[] buffer=new byte[8192]; int count;
                while((count=in.read(buffer))!=-1) { if(out.size()+count>25*1024*1024) throw new IOException("Choose an image smaller than 25 MB."); out.write(buffer,0,count); }
                byte[] bytes=out.toByteArray(); BitmapFactory.Options bounds=new BitmapFactory.Options(); bounds.inJustDecodeBounds=true; BitmapFactory.decodeByteArray(bytes,0,bytes.length,bounds);
                if(bounds.outWidth<=0 || bounds.outHeight<=0) throw new IOException("This image could not be read. Choose a JPG, PNG, or supported photo.");
                String id=createRecord(bytes,selectedForm,code,document,replacing,false);
                runOnUiThread(() -> { importing=false; render(true); parse(id); });
            } catch(Exception e) { runOnUiThread(() -> { importing=false; error(e); }); }
            finally { if(request==101) new File(getCacheDir(),"capture.jpg").delete(); }
        });
    }
    private String createRecord(byte[] image,String selectedForm,String code,String document,String replacing,boolean manual) throws Exception {
        String id=UUID.randomUUID().toString();
        JSONObject record=new JSONObject().put("id",id).put("document_id",document).put("patient_code",code).put("midwife_id","demo-midwife")
            .put("captured_at",Instant.now().toString()).put("form_id",selectedForm).put("mock",image==null&&!manual).put("manual",manual);
        if(image!=null) { String file=id+".image.enc"; store.write(file,image); record.put("image_file",file); }
        EncryptedStore.state(record,"CAPTURED"); EncryptedStore.state(record,manual?"MANUAL_REVIEW_REQUIRED":"PENDING_AI");
        if(manual) record.put("fields",SchemaCatalog.blank(catalog.schema(selectedForm).getJSONObject("fields")));
        if(replacing!=null) record.put("replaces_record_id",replacing);
        store.save(record);
        if(replacing!=null) { JSONObject old=store.get(replacing); EncryptedStore.state(old,"SUPERSEDED"); store.save(old); }
        return id;
    }
    private void demo() {
        try { String id=createRecord(null,formId,patientCode,documentId,null,false); render(true); parse(id); } catch(Exception e) { error(e); }
    }
    private void manual() {
        List<String> ids=new ArrayList<>(catalog.forms.keySet()); String[] titles=new String[ids.size()]; for(int i=0;i<ids.size();i++) titles[i]=catalog.title(ids.get(i));
        new AlertDialog.Builder(this).setTitle("Choose a form for manual entry").setItems(titles,(d,w) -> {
            try { String id=createRecord(null,ids.get(w),patientCode,documentId,null,true); render(true); edit(id); } catch(Exception e) { error(e); }
        }).show();
    }
    private void recoverManual(JSONObject record) {
        try { record.put("manual",true).put("fields",SchemaCatalog.blank(catalog.schema(record.getString("form_id")).getJSONObject("fields"))); EncryptedStore.state(record,"MANUAL_REVIEW_REQUIRED"); store.save(record); render(false); edit(record.getString("id")); } catch(Exception e) { error(e); }
    }
    private void resumePending() throws Exception { for(JSONObject r:store.records()) if(r.optString("state").equals("PENDING_AI") || r.optString("state").equals("CAPTURED")) parse(r.getString("id")); }
    private void parse(String id) {
        if(!parsing.add(id)) return;
        worker.submit(() -> {
            try {
                JSONObject record=store.get(id); EncryptedStore.state(record,"PENDING_AI"); store.save(record);
                runOnUiThread(() -> render(false));
                byte[] bytes=record.has("image_file")?store.read(record.getString("image_file")):new byte[0];
                PresetForm form=bytes.length==0?new MockFormParser(catalog).parse(bytes,record.getString("form_id")):parser.parse(bytes,record.getString("form_id"));
                catalog.validate(form.formId,form.toJson());
                // Another capture may have superseded this one while the parser was working.
                synchronized(EncryptedStore.LOCK) {
                    if(store.get(id).optString("state").equals("SUPERSEDED")) return;
                    record.remove("processing_error");record.put("mock",bytes.length==0).put("form_id",form.formId).put("fields",form.toJson()).put("extraction_metadata",form.extractionMetadata()); EncryptedStore.state(record,"AI_PROCESSED"); EncryptedStore.state(record,"NEEDS_REVIEW"); store.save(record);
                }
            } catch(Exception e) {
                try { JSONObject r=store.get(id); r.put("processing_error",e.getMessage()==null?"OCR failed; capture retained.":e.getMessage()); EncryptedStore.state(r,"PROCESSING_FAILED"); store.save(r); } catch(Exception ignored) { runOnUiThread(() -> error(e)); }
            } finally { parsing.remove(id); runOnUiThread(() -> render(true)); }
        });
    }
    private void edit(String id) {
        try {
            JSONObject r=store.get(id); new FormEditor(this,catalog.title(r.getString("form_id")),catalog.schema(r.getString("form_id")).getJSONObject("fields"),r.getJSONObject("fields"),fields -> {
                catalog.validate(r.getString("form_id"),fields); r.put("fields",fields); EncryptedStore.state(r,"NEEDS_REVIEW"); store.save(r); render(false);
            }).show();
        } catch(Exception e) { error(e); }
    }
    private void submit(String id) {
        try {
            JSONObject r=store.get(id); catalog.validate(r.getString("form_id"),r.getJSONObject("fields"));
            List<SchemaCatalog.Row> rows=SchemaCatalog.rows(catalog.schema(r.getString("form_id")).getJSONObject("fields"),r.getJSONObject("fields"));
            long uncertain=rows.stream().filter(SchemaCatalog.Row::needsReview).count();
            if(uncertain>0) {
                new AlertDialog.Builder(this).setTitle(uncertain+" fields still need checking").setMessage("Open Edit data to correct uncertain values or mark them as checked against the paper. Missing values can stay explicitly unknown.").setNegativeButton("Later",null).setPositiveButton("Edit data",(d,w) -> edit(id)).show(); return;
            }
            List<JSONObject> same=new ArrayList<>(); for(JSONObject old:store.records()) if(!old.getString("id").equals(id) && old.optString("document_id").equals(r.optString("document_id")) && old.optString("form_id").equals(r.optString("form_id")) && (old.optString("state").equals("SYNCED") || old.optString("state").equals("REGISTERED") || old.optString("state").equals("SYNC_FAILED"))) same.add(old);
            if(!same.isEmpty()) {
                JSONObject previous=same.get(same.size()-1);
                new AlertDialog.Builder(this).setTitle("This form already exists").setMessage("A " + catalog.title(r.getString("form_id")) + " form is already saved under " + r.getString("patient_code") + ". Is this another visit or a correction? The prior version will be retained.")
                    .setNegativeButton("Cancel",null).setNeutralButton("New visit",(d,w) -> confirmSubmit(r,null)).setPositiveButton("Correct previous",(d,w) -> confirmSubmit(r,previous.optString("id"))).show();
            } else confirmSubmit(r,null);
        } catch(Exception e) { error(e); }
    }
    private void confirmSubmit(JSONObject r,String revisionOf) {
        activeDialog=new AlertDialog.Builder(this).setTitle("Submit reviewed record?").setMessage("Link this page to " + r.optString("patient_code") + " and save it to the encrypted local queue. Confirm that the values match the paper.")
            .setNegativeButton("Keep reviewing",null).setPositiveButton("Submit",(d,w) -> {
                try {
                    if(revisionOf!=null) r.put("revision_of",revisionOf);
                    r.put("confirmed_at",Instant.now().toString()); EncryptedStore.state(r,"VALIDATED"); EncryptedStore.state(r,"PATIENT_MATCHED"); EncryptedStore.state(r,"REGISTERED"); store.save(r); render(true); sync();
                } catch(Exception e) { error(e); }
            }).show();
    }
    private void sync() {
        if(destroyed||store==null||!syncing.compareAndSet(false,true))return;
        syncWorker.submit(() -> {
            int count=0;
            try {
                if(SyncEngine.probe(this))count=SyncEngine.sync(this,store,new UsbDatabaseSink(this));
                boolean pending=false;for(JSONObject r:store.records())if(SyncEngine.pending(r))pending=true;
                if(pending)SyncEngine.schedule(this);
            } catch(Exception e){SyncEngine.schedule(this);}
            finally {syncing.set(false);final int sent=count;runOnUiThread(() -> {if(!destroyed){render(false);if(sent>0)Toast.makeText(this,sent+" record(s) synced to PC",Toast.LENGTH_SHORT).show();}});}
        });
    }
    private void sessions() {
        try {
            LinkedHashMap<String,String> docs=new LinkedHashMap<>(); docs.put(documentId,patientCode); for(JSONObject r:store.records()) docs.put(r.getString("document_id"),r.getString("patient_code"));
            List<String> ids=new ArrayList<>(docs.keySet()); List<String> labels=new ArrayList<>(docs.values()); labels.add("None of these — create a new code"); labels.add("I’m not sure — keep reviewing");
            new AlertDialog.Builder(this).setTitle("Which registry is this?").setItems(labels.toArray(new String[0]),(d,w) -> {
                try { if(w<ids.size()) { documentId=ids.get(w); patientCode=docs.get(documentId); saveSession(); } else if(w==ids.size()) newSession(); render(true); } catch(Exception e) { error(e); }
            }).show();
        } catch(Exception e) { error(e); }
    }
    private void showRecords() {
        try {
            List<JSONObject> records=store.records();
            if(records.isEmpty()) { new AlertDialog.Builder(this).setTitle("Your saved records").setMessage("No pages yet. Take a photo, upload an image, or try a sample page.").setPositiveButton("OK",null).show(); return; }
            String[] labels=new String[records.size()];
            for(int i=0;i<records.size();i++) { JSONObject r=records.get(i); labels[i]=r.getString("patient_code")+" · "+catalog.title(r.getString("form_id"))+"\n"+r.getString("state").replace('_',' '); }
            new AlertDialog.Builder(this).setTitle("Encrypted records · "+records.size()).setItems(labels,(d,w) -> {
                try { JSONObject r=records.get(w); documentId=r.getString("document_id"); patientCode=r.getString("patient_code"); saveSession(); render(true); } catch(Exception e) { error(e); }
            }).setNegativeButton("Close",null).show();
        } catch(Exception e) { error(e); }
    }
    private void error(Exception e) { if(!destroyed && !isFinishing()) new AlertDialog.Builder(this).setTitle("Couldn’t finish that step").setMessage(e.getMessage()==null?"Your saved records have been kept. Please try again.":e.getMessage()).setPositiveButton("OK",null).show(); }
    private void fatal(Exception e) { TextView t=text("DayOne couldn’t open local storage.\n\n"+e.getMessage(),18,INK); pad(t,24); setContentView(t); }
    private final class Wallpaper extends View {
        private final Paint paint=new Paint(3);
        Wallpaper() { super(MainActivity.this); }
        @Override protected void onDraw(Canvas c) {
            c.drawColor(0xFFEFEAE2); paint.setColor(0xFFC7CDBE); paint.setAlpha(75); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(dp(1));
            for(int y=dp(25);y<getHeight();y+=dp(105)) for(int x=dp(18);x<getWidth();x+=dp(98)) {
                c.save(); c.translate(x+(y/dp(105)%2)*dp(30),y); c.rotate(-18);
                c.drawRoundRect(0,0,dp(23),dp(29),dp(4),dp(4),paint); c.drawLine(dp(6),dp(9),dp(17),dp(9),paint); c.drawLine(dp(6),dp(15),dp(17),dp(15),paint);
                c.drawCircle(dp(52),dp(47),dp(9),paint); c.drawLine(dp(47),dp(47),dp(57),dp(47),paint); c.drawLine(dp(52),dp(42),dp(52),dp(52),paint); c.restore();
            }
        }
    }
    private final class Icon extends View {
        private final String type; private final Paint paint=new Paint(3);
        Icon(String type,int color) { super(MainActivity.this); this.type=type; paint.setColor(color); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(1.8f); paint.setStrokeCap(Paint.Cap.ROUND); setFocusable(true); }
        @Override protected void onDraw(Canvas c) {
            c.save(); c.translate(getWidth()/2f-getWidth()/4f,getHeight()/2f-getWidth()/4f); c.scale(getWidth()/48f,getWidth()/48f);
            switch(type) {
                case "camera": c.drawRoundRect(2,6,22,20,3,3,paint); c.drawCircle(12,13,4,paint); c.drawLine(7,6,9,3,paint); c.drawLine(9,3,15,3,paint); c.drawLine(15,3,17,6,paint); break;
                case "file": c.drawRoundRect(5,2,20,23,2,2,paint); c.drawLine(9,8,16,8,paint); c.drawLine(9,13,16,13,paint); c.drawLine(9,18,14,18,paint); break;
                case "clip": c.rotate(30,12,12); c.drawRoundRect(6,2,18,22,6,6,paint); c.drawRoundRect(9,5,15,18,3,3,paint); break;
                default: paint.setStyle(Paint.Style.FILL); c.drawCircle(12,5,1.6f,paint); c.drawCircle(12,12,1.6f,paint); c.drawCircle(12,19,1.6f,paint); paint.setStyle(Paint.Style.STROKE);
            } c.restore();
        }
    }
}
