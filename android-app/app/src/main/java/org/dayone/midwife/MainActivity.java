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
import java.io.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    private static final int GREEN=0xFF075E54, TEAL=0xFF087F6B, INK=0xFF193C35, MUTED=0xFF6D7D76;
    private static final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final Map<String,Bitmap> thumbnails=new HashMap<>();
    private EncryptedStore store;
    private SchemaCatalog catalog;
    private LinearLayout root, timeline, bottomActions;
    private ScrollView scroll;
    private TextView connection, sessionLabel;
    AlertDialog activeDialog;
    private String formId="late_postnatal_newborn", patientCode, documentId, retakeId;
    private String reviewId, pendingReviewId;
    private String sectionRecordId;
    private final Set<String> expandedDays=new HashSet<>(), expandedSections=new HashSet<>(), expandedSubsections=new HashSet<>();
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
            store=new EncryptedStore(this); catalog=new SchemaCatalog(this);
            JSONObject session=store.json("session.enc");
            patientCode=session.optString("patient_code",""); documentId=session.optString("document_id","");
            if(patientCode.isEmpty()) newSession();
            if(state!=null) { formId=state.getString("form_id",formId); retakeId=state.getString("retake_id"); reviewId=state.getString("review_id"); pendingReviewId=state.getString("pending_review_id"); }
            build(); render(true); resumePending();
            sync(); handler.postDelayed(refresh,5000);
        } catch(Exception e) { fatal(e); }
    }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); state.putString("form_id",formId); state.putString("retake_id",retakeId); state.putString("review_id",reviewId); state.putString("pending_review_id",pendingReviewId); }
    @Override public void onBackPressed(){if(reviewId!=null){reviewId=null;expandedSections.clear();lastRender="";render(false);}else super.onBackPressed();}
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
        root=vertical(); root.setBackgroundColor(0xFFF5F7F4); setContentView(root);
        LinearLayout header=horizontal(); header.setPadding(dp(16),dp(10),dp(10),dp(10)); header.setBackgroundColor(GREEN);
        LinearLayout identity=vertical(); identity.addView(bold("Sanad",24,Color.WHITE)); identity.addView(text("Form reader",12,0xFFCEE4DC)); header.addView(identity,new LinearLayout.LayoutParams(0,-2,1));
        header.addView(iconButton("more","Settings",Color.WHITE,this::settings)); root.addView(header);
        LinearLayout strip=horizontal(); strip.setBackgroundColor(Color.WHITE); strip.setPadding(dp(16),dp(7),dp(12),dp(7));
        sessionLabel=bold("Records",14,INK); strip.addView(sessionLabel,new LinearLayout.LayoutParams(0,dp(36),1)); sessionLabel.setGravity(Gravity.CENTER_VERTICAL);
        connection=bold("",12,TEAL); pad(connection,8); connection.setBackground(bg(0xFFE4EEE5,18)); connection.setOnClickListener(v -> toggleOffline()); strip.addView(connection); root.addView(strip);
        scroll=new ScrollView(this); scroll.setFillViewport(true); timeline=vertical(); timeline.setPadding(dp(14),dp(14),dp(14),dp(24)); scroll.addView(timeline); root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        bottomActions=horizontal(); bottomActions.setPadding(dp(10),dp(8),dp(10),dp(10)); bottomActions.setBackgroundColor(Color.WHITE);
        TextView upload=button("Upload",false,() -> gallery(null)); LinearLayout.LayoutParams small=new LinearLayout.LayoutParams(0,dp(52),1); small.rightMargin=dp(8); bottomActions.addView(upload,small);
        TextView scan=button("Scan a form",true,() -> camera(null)); bottomActions.addView(scan,new LinearLayout.LayoutParams(0,dp(52),2)); root.addView(bottomActions);
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
            connection.setText(online?"● PC database":"○ Offline");
            sessionLabel.setText(reviewId==null?"Records"+(queued>0?" · "+queued+" queued":""):"Review result");
            boolean modelsInstalled=ModelPackInstaller.isCurrentManifest(getFilesDir());
            StringBuilder workStatus=new StringBuilder();for(JSONObject r:records)if(r.optString("state").equals("PENDING_AI"))workStatus.append(OcrService.progress(r.getString("id")));
            if(pendingReviewId!=null){try{JSONObject pending=store.get(pendingReviewId);String state=pending.optString("state");if(pending.has("fields")&&!state.equals("PENDING_AI")&&!state.equals("CAPTURED")){reviewId=pendingReviewId;pendingReviewId=null;expandedSections.clear();}}catch(Exception ignored){pendingReviewId=null;}}
            String signature=records.toString()+online+modelImportStatus+modelsInstalled+workStatus+reviewId+expandedDays+expandedSections;
            if(signature.equals(lastRender) && !bottom) return; lastRender=signature;
            int y=scroll.getScrollY(); timeline.removeAllViews();
            bottomActions.setVisibility(reviewId==null?View.VISIBLE:View.GONE);
            if(reviewId==null)renderLibrary(records,modelsInstalled);else renderReview(store.get(reviewId));
            scroll.post(() -> { if(bottom) scroll.fullScroll(View.FOCUS_DOWN); else scroll.scrollTo(0,y); });
        } catch(Exception e) { error(e); }
    }
    private void renderLibrary(List<JSONObject> records,boolean modelsInstalled)throws Exception {
        if(!modelsInstalled||modelImport.get()){LinearLayout notice=card();notice.addView(bold(modelImport.get()?modelImportStatus:"Model pack required",17,INK));notice.addView(button(modelImport.get()?modelImportStatus:"Import model pack",true,this::chooseModelPack));timeline.addView(notice,cardParams());}
        timeline.addView(bold("Your records",26,INK));timeline.addView(text("Saved automatically by capture date",13,MUTED));gap(timeline,14);
        if(records.isEmpty()){LinearLayout empty=card();empty.addView(bold("No forms yet",18,INK));empty.addView(text("Scan a paper form or upload an image to begin.",14,MUTED));empty.addView(button("Scan a form",true,() -> camera(null)));timeline.addView(empty,cardParams());return;}
        records.sort((a,b)->RecordLibrary.captured(b).compareTo(RecordLibrary.captured(a)));
        String week=null,day=null;LinearLayout dayBody=null;
        for(JSONObject r:records){if(r.optString("state").equals("SUPERSEDED"))continue;
            String wk=RecordLibrary.weekKey(r),dk=RecordLibrary.dayKey(r);
            if(!wk.equals(week)){week=wk;day=null;TextView h=bold(RecordLibrary.weekLabel(r).toUpperCase(Locale.getDefault()),12,MUTED);h.setPadding(0,dp(18),0,dp(7));timeline.addView(h);}
            if(!dk.equals(day)){day=dk;String key=dk;boolean open=expandedDays.contains(key)||dk.equals(java.time.LocalDate.now().toString());if(open)expandedDays.add(key);
                LinearLayout folder=vertical();folder.setBackground(bg(Color.WHITE,12));folder.setElevation(dp(1));TextView label=bold((open?"▾  ":"▸  ")+RecordLibrary.dayLabel(r),16,INK);label.setPadding(dp(14),dp(13),dp(14),dp(13));folder.addView(label);dayBody=vertical();dayBody.setVisibility(open?View.VISIBLE:View.GONE);folder.addView(dayBody);LinearLayout body=dayBody;label.setOnClickListener(v->{if(expandedDays.contains(key))expandedDays.remove(key);else expandedDays.add(key);lastRender="";render(false);});timeline.addView(folder,cardParams());}
            recordTile(dayBody,r);
        }
    }
    private LinearLayout card(){LinearLayout box=vertical();box.setBackground(bg(Color.WHITE,12));box.setPadding(dp(14),dp(14),dp(14),dp(14));box.setElevation(dp(1));return box;}
    private LinearLayout.LayoutParams cardParams(){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(10);return p;}
    private void recordTile(LinearLayout parent,JSONObject r)throws Exception {
        String id=r.getString("id"), state=r.getString("state");
        if(state.equals("SYNCED")&&!r.has("pc_receipt"))state="REGISTERED";
        LinearLayout tile=horizontal();tile.setPadding(dp(14),dp(11),dp(14),dp(11));
        Icon icon=new Icon("file",TEAL);tile.addView(icon,new LinearLayout.LayoutParams(dp(40),dp(46)));LinearLayout info=vertical();info.setPadding(dp(8),0,0,0);info.addView(bold(RecordLibrary.title(r),16,INK));info.addView(text(catalog.title(r.getString("form_id")),12,MUTED));
        if(state.equals("PENDING_AI") || state.equals("CAPTURED")) {
            info.addView(text(OcrService.progress(id),12,TEAL));
        } else if(state.equals("PROCESSING_FAILED")){info.addView(text("Needs another scan",12,0xFF9A3D2F));}
        else {int uncertain=0;if(r.has("fields"))for(SchemaCatalog.Row row:SchemaCatalog.rows(catalog.schema(r.getString("form_id")).getJSONObject("fields"),r.getJSONObject("fields")))if(row.needsReview())uncertain++;info.addView(text(state.equals("SYNCED")?"Synced":uncertain+" to review",12,uncertain>0?0xFF946322:TEAL));}
        tile.addView(info,new LinearLayout.LayoutParams(0,-2,1));tile.addView(bold("›",28,MUTED));
        tile.setOnClickListener(v->{try{JSONObject fresh=store.get(id);if(fresh.has("fields")){reviewId=id;expandedSections.clear();lastRender="";render(false);}else if(fresh.optString("state").equals("PROCESSING_FAILED"))failedActions(fresh);}catch(Exception e){error(e);}});
        tile.setOnLongClickListener(v->{confirmDelete(r);return true;});parent.addView(tile);
        View line=new View(this);line.setBackgroundColor(0xFFE7ECE8);parent.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));
    }
    private void renderReview(JSONObject r)throws Exception {
        String id=r.getString("id"),state=r.getString("state"),type=r.getString("form_id");JSONObject fields=r.getJSONObject("fields");List<SchemaCatalog.Row> rows=SchemaCatalog.rows(catalog.schema(type).getJSONObject("fields"),fields);int uncertain=(int)rows.stream().filter(SchemaCatalog.Row::needsReview).count();
        TextView back=bold("‹  Records",15,TEAL);back.setPadding(0,0,0,dp(14));back.setOnClickListener(v->{reviewId=null;expandedSections.clear();lastRender="";render(false);});timeline.addView(back);
        timeline.addView(bold(RecordLibrary.title(r),25,INK));timeline.addView(text(catalog.title(type),14,MUTED));gap(timeline,12);
        if(r.has("image_file")){ImageView image=new ImageView(this);image.setImageBitmap(thumbnail(r));image.setScaleType(ImageView.ScaleType.CENTER_CROP);image.setContentDescription("Open original form");image.setOnClickListener(v->showOriginal(r));timeline.addView(image,new LinearLayout.LayoutParams(-1,dp(150)));}
        LinearLayout summary=horizontal();summary.setPadding(0,dp(12),0,dp(10));summary.addView(bold(rows.size()+" fields",14,INK),new LinearLayout.LayoutParams(0,-2,1));summary.addView(bold(uncertain+" to review",13,uncertain>0?0xFF946322:TEAL));timeline.addView(summary);
        LinkedHashMap<String,List<SchemaCatalog.Row>> groups=new LinkedHashMap<>();for(SchemaCatalog.Row row:rows)groups.computeIfAbsent(ReviewSections.title(type,row.path),k->new ArrayList<>()).add(row);
        if(!id.equals(sectionRecordId)&&!groups.isEmpty()){expandedSections.clear();expandedSubsections.clear();String first=groups.keySet().iterator().next();for(Map.Entry<String,List<SchemaCatalog.Row>> entry:groups.entrySet())if(entry.getValue().stream().anyMatch(SchemaCatalog.Row::needsReview)){first=entry.getKey();break;}expandedSections.add(first);sectionRecordId=id;}
        for(Map.Entry<String,List<SchemaCatalog.Row>> entry:groups.entrySet()){
            String key=entry.getKey();List<SchemaCatalog.Row> groupRows=entry.getValue();boolean open=expandedSections.contains(key);boolean oversized=groupRows.size()>8;LinkedHashMap<String,List<SchemaCatalog.Row>> children=oversized?ReviewSections.subsections(type,key,groupRows):null;
            int parentConfidence=oversized?ReviewSections.minimumSubsectionConfidence(children):ReviewSections.minimumConfidencePercent(groupRows);LinearLayout section=card();section.addView(reviewHeading(key,groupRows.size(),parentConfidence,open,false,()->{if(expandedSections.contains(key))expandedSections.remove(key);else expandedSections.add(key);lastRender="";render(false);}));LinearLayout body=vertical();body.setVisibility(open?View.VISIBLE:View.GONE);
            if(!oversized)for(SchemaCatalog.Row row:groupRows)reviewField(body,id,row);
            else for(Map.Entry<String,List<SchemaCatalog.Row>> child:children.entrySet()){String childKey=key+" / "+child.getKey();boolean childOpen=expandedSubsections.contains(childKey);LinearLayout childBox=vertical();childBox.setPadding(dp(6),dp(7),dp(6),0);childBox.addView(reviewHeading(child.getKey(),child.getValue().size(),ReviewSections.minimumConfidencePercent(child.getValue()),childOpen,true,()->{if(expandedSubsections.contains(childKey))expandedSubsections.remove(childKey);else expandedSubsections.add(childKey);lastRender="";render(false);}));LinearLayout childBody=vertical();childBody.setVisibility(childOpen?View.VISIBLE:View.GONE);for(SchemaCatalog.Row row:child.getValue())reviewField(childBody,id,row);childBox.addView(childBody);body.addView(childBox);}
            section.addView(body);timeline.addView(section,cardParams());
        }
        boolean submitted=state.equals("REGISTERED")||state.equals("SYNCED")||state.equals("SYNC_FAILED");if(!submitted){timeline.addView(button("Save reviewed form",true,()->submit(id)));TextView retake=button("Retake photo",false,()->captureMenu(id));LinearLayout.LayoutParams rp=cardParams();rp.topMargin=dp(7);timeline.addView(retake,rp);}else timeline.addView(text(state.equals("SYNCED")?"Saved and synced to the PC database":"Saved securely on this device",13,TEAL));
    }
    private Bitmap thumbnail(JSONObject r)throws Exception {String id=r.getString("id");Bitmap image=thumbnails.get(id);if(image==null){byte[] bytes=store.read(r.getString("image_file"));BitmapFactory.Options opts=new BitmapFactory.Options();opts.inJustDecodeBounds=true;BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);opts.inSampleSize=Math.max(1,Math.max(opts.outWidth,opts.outHeight)/800);opts.inJustDecodeBounds=false;image=BitmapFactory.decodeByteArray(bytes,0,bytes.length,opts);thumbnails.put(id,image);}return image;}
    private LinearLayout reviewHeading(String label,int count,int minimum,boolean open,boolean child,Runnable toggle){LinearLayout heading=horizontal();heading.setPadding(child?dp(8):0,child?dp(8):0,0,child?dp(8):0);if(child)heading.setBackground(bg(0xFFF4F7F4,8));TextView titleView=bold((open?"▾  ":"▸  ")+label,child?14:16,INK);heading.addView(titleView,new LinearLayout.LayoutParams(0,-2,1));TextView countView=text(count+(count==1?" field":" fields"),child?11:12,MUTED);countView.setPadding(dp(6),0,dp(8),0);heading.addView(countView);int scoreColor=minimum<0?MUTED:minimum>=80?TEAL:minimum>=70?0xFF946322:0xFFB3261E;int scoreBackground=minimum<0?0xFFECEFEC:minimum>=80?0xFFEDF5EF:minimum>=70?0xFFFFF1D6:0xFFFDE7E4;TextView score=bold(minimum<0?"—":minimum+"%",child?11:12,scoreColor);score.setGravity(Gravity.CENTER);score.setPadding(dp(7),dp(4),dp(7),dp(4));score.setBackground(bg(scoreBackground,7));heading.addView(score);heading.setOnClickListener(v->toggle.run());return heading;}
    private void reviewField(LinearLayout parent,String id,SchemaCatalog.Row row){LinearLayout field=vertical();field.setPadding(0,dp(10),0,dp(10));field.addView(text(row.label,12,MUTED));LinearLayout value=horizontal();String shown=row.field.isNull("value")?row.field.optString("status").replace('_',' '):row.field.opt("value").toString().replace('_',' ');value.addView(bold(shown,15,INK),new LinearLayout.LayoutParams(0,-2,1));TextView score=bold(Math.round(row.field.optDouble("confidence")*100)+"%",12,row.needsReview()?0xFF946322:TEAL);score.setPadding(dp(7),dp(4),dp(7),dp(4));score.setBackground(bg(row.needsReview()?0xFFFFF1D6:0xFFEDF5EF,7));value.addView(score);field.addView(value);field.setOnClickListener(v->editField(id,row.path));parent.addView(field);View line=new View(this);line.setBackgroundColor(0xFFE7ECE8);parent.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));}
    private void editField(String id,String path){try{JSONObject r=store.get(id);new FormEditor(this,catalog.title(r.getString("form_id")),catalog.schema(r.getString("form_id")).getJSONObject("fields"),r.getJSONObject("fields"),path,updated->{catalog.validate(r.getString("form_id"),updated);r.put("fields",updated);EncryptedStore.state(r,"NEEDS_REVIEW");store.save(r);lastRender="";render(false);}).show();}catch(Exception e){error(e);}}
    private void failedActions(JSONObject record){new AlertDialog.Builder(this).setTitle("This page needs another try").setMessage(record.optString("processing_error","The original image is still saved.")).setNegativeButton("Close",null).setNeutralButton("Enter manually",(d,w)->recoverManual(record)).setPositiveButton("Retry OCR",(d,w)->parse(record.optString("id"))).show();}
    private void confirmDelete(JSONObject record){String name=RecordLibrary.title(record);String note=record.optString("state").equals("SYNCED")?" The copy already synced to the PC database will remain there.":" This cannot be undone.";activeDialog=new AlertDialog.Builder(this).setTitle("Delete record?").setMessage("Are you sure you want to delete “"+name+"”?"+note).setNegativeButton("Cancel",null).setPositiveButton("Delete",(d,w)->deleteRecord(record.optString("id"),name)).show();}
    private void deleteRecord(String id,String name){try{if(store.deleteRecord(id)){thumbnails.remove(id);if(id.equals(pendingReviewId))pendingReviewId=null;if(id.equals(reviewId))reviewId=null;lastRender="";render(false);Toast.makeText(this,name+" deleted",Toast.LENGTH_SHORT).show();}}catch(Exception e){error(e);}}
    private void settings() {
        LinearLayout panel=vertical(); pad(panel,20);panel.addView(button("Import model pack",true,() -> {if(activeDialog!=null)activeDialog.dismiss();chooseModelPack();}));gap(panel,12);
        panel.addView(text("Results and images stay saved on this phone. Reviewed, submitted records transfer to the PC only when its authenticated USB database is reachable. Wi-Fi and mobile data are not used.",13,MUTED));
        activeDialog=new AlertDialog.Builder(this).setTitle("Settings").setView(panel).setPositiveButton("Done",null).show();
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
                runOnUiThread(() -> { importing=false; pendingReviewId=id; reviewId=null; lastRender=""; render(false); offerProcessingNotifications(); parse(id); });
            } catch(Exception e) { runOnUiThread(() -> { importing=false; error(e); }); }
            finally { if(request==101) new File(getCacheDir(),"capture.jpg").delete(); }
        });
    }
    private String createRecord(byte[] image,String selectedForm,String code,String document,String replacing,boolean manual) throws Exception {
        String id=UUID.randomUUID().toString();
        JSONObject record=new JSONObject().put("id",id).put("document_id",document).put("patient_code",code).put("midwife_id","demo-midwife")
            .put("captured_at",Instant.now().toString()).put("form_id",selectedForm).put("mock",image==null&&!manual).put("manual",manual);
        if(image!=null) { String file=id+".image.enc"; store.write(file,image); record.put("image_file",file); }
        EncryptedStore.state(record,"CAPTURED"); if(manual) EncryptedStore.state(record,"MANUAL_REVIEW_REQUIRED");
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
            try { String id=createRecord(null,ids.get(w),patientCode,documentId,null,true); reviewId=id; lastRender=""; render(false); } catch(Exception e) { error(e); }
        }).show();
    }
    private void recoverManual(JSONObject record) {
        List<String> ids=new ArrayList<>(catalog.forms.keySet());String[] titles=new String[ids.size()];
        for(int i=0;i<ids.size();i++)titles[i]=catalog.title(ids.get(i));
        new AlertDialog.Builder(this).setTitle("Choose a form for manual entry").setItems(titles,(dialog,index) -> {
            try {
                String id=record.getString("id"),selected=ids.get(index);
                synchronized(EncryptedStore.LOCK){store.save(ManualRecovery.prepare(store.get(id),selected,catalog.schema(selected)));}
                reviewId=id;expandedSections.clear();lastRender="";render(false);
            }catch(Exception e){error(e);}
        }).show();
    }
    private void resumePending() throws Exception { for(JSONObject r:store.records()) if(r.optString("state").equals("PENDING_AI") || r.optString("state").equals("CAPTURED")) parse(r.getString("id")); }
    private void offerProcessingNotifications() {
        if(Build.VERSION.SDK_INT<33||checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)==android.content.pm.PackageManager.PERMISSION_GRANTED)return;
        SharedPreferences preferences=getSharedPreferences("ui",MODE_PRIVATE);
        if(preferences.getBoolean("asked_processing_notifications",false))return;
        preferences.edit().putBoolean("asked_processing_notifications",true).apply();
        // Optional: denial never blocks recognition or encrypted capture storage.
        requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},103);
    }
    private void parse(String id) {
        try { OcrService.enqueue(this,id);render(false); }
        catch(Exception e) { error(e); }
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
