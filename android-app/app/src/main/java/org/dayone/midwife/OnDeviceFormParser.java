package org.dayone.midwife;

import android.content.Context;
import android.graphics.Bitmap;
import android.os.Debug;
import android.os.SystemClock;
import org.dayone.midwife.model.*;
import org.json.*;
import java.io.IOException;
import java.util.*;

/** Offline eight-form extraction. No mock fallback for captured images. */
public final class OnDeviceFormParser implements FormParser {
    private final SchemaCatalog catalog;private final OnDeviceModels models;
    private static final Object INFERENCE_LOCK=ModelPackInstaller.LOCK;
    interface Progress {void update(int done,int total);}
    private final Progress progress;
    public OnDeviceFormParser(Context context,SchemaCatalog catalog){this(context,catalog,(done,total)->{});}
    OnDeviceFormParser(Context context,SchemaCatalog catalog,Progress progress){this(catalog,new OnDeviceModels(context.getApplicationContext()),progress);}
    OnDeviceFormParser(SchemaCatalog catalog,OnDeviceModels models,Progress progress){this.catalog=catalog;this.models=models;this.progress=progress;}
    private static final class Work {String key;MobileVision.Box hand;double confidence;JSONObject localization;List<String> routes=new ArrayList<>();Set<String> completed=new HashSet<>();JSONObject best;}
    @Override public PresetForm parse(byte[] originalImage,String ignoredHint)throws Exception {
        if(originalImage.length==0)throw new IOException("No photo supplied. Use the explicitly labelled sample demo or manual entry.");
        // Across Activity recreation too: never have two heavy parser instances in flight.
        synchronized(INFERENCE_LOCK){
            try{return extract(originalImage);}
            catch(OutOfMemoryError e){throw new IOException("Not enough memory for on-device OCR. Your capture is retained; close other apps or use manual entry.",e);}
        }
    }
    private PresetForm extract(byte[] bytes)throws Exception {
        long started=SystemClock.elapsedRealtime();progress.update(0,0);models.verify();Bitmap page=MobileImages.decode(bytes);JSONObject fields=new JSONObject(),evidence=new JSONObject(),marks=new JSONObject();
        try {
            MobileVision.Prediction form;
            try(MobileVision.Classifier c=new MobileVision.Classifier(models,"forms")){form=c.predict(page);}
            if(form.confidence<.75)throw new IOException("Could not recognize the form. Try a clearer full-page photo or enter it manually.");
            JSONObject routes=models.json("routing.json");JSONObject routeConfig=routes.getJSONObject(form.label);String formId=routeConfig.getString("form_id"),folder=routeConfig.getString("folder");
            JSONObject spec=models.json(folder+"/spec.json"),bindings=spec.getJSONObject("bindings"),priors=models.json(folder+"/pairing_priors.json");
            Map<String,MobileVision.Box> anchors=new HashMap<>();JSONArray classes=spec.getJSONArray("classes");
            for(MobileVision.Box b:MobileVision.detect(models,folder+"/anchors",page)){String name=classes.getString(b.label);if(!anchors.containsKey(name)||anchors.get(name).confidence<b.confidence)anchors.put(name,b);}
            if(anchors.size()<Math.max(3,classes.length()/5))throw new IOException("Could not locate enough fields in this layout. Try a clearer full-page photo or enter it manually.");
            List<MobileVision.Box> hands=MobileVision.detect(models,"handwriting",page);
            int detectedHands=hands.size();
            JSONObject runtime=models.json("manifest.json").optJSONObject("runtime");
            if(runtime!=null&&runtime.optBoolean("reject_printed_centers"))hands=MobileVision.excludePrinted(hands,anchors.values());
            Map<String,MobileVision.Box> matches=MobileVision.pair(anchors,hands,bindings,priors);
            MobileGrammar grammar=new MobileGrammar(models.json(folder+"/grammar.json"));JSONObject schema=catalog.schema(formId).getJSONObject("fields");List<Work> work=new ArrayList<>();
            for(Iterator<String> it=bindings.keys();it.hasNext();) {
                String key=it.next();JSONObject binding=bindings.getJSONObject(key),fieldSpec=binding.getJSONObject("schema");
                JSONObject f=MobileGrammar.field(null,0);fields.put(key,f);
                if(binding==null){MobileGrammar.issue(f,"NO_TRAINED_ANCHOR_FOR_FIELD");continue;}
                String kind=binding.getString("kind");
                if(kind.equals("printed")){MobileVision.Box a=MobileVision.unitAnchor(binding,anchors);if(a!=null)f.put("value",binding.get("fixed")).put("confidence",a.confidence).put("source","detected_preprinted_identifier");else MobileGrammar.issue(f,"PRINTED_IDENTIFIER_ANCHOR_MISSING");continue;}
                if(kind.equals("checkbox")){Boolean mark=mark(page,binding,anchors,marks,key);f.put("value",mark==null?JSONObject.NULL:mark).put("confidence",mark==null?0:Math.min(.70,Math.min(form.confidence,marks.getJSONObject(key).optDouble("anchor_confidence",0))));if(mark==null)MobileGrammar.issue(f,"AMBIGUOUS_OR_MISSING_CHECKBOX");}
                else if(kind.equals("choice")){
                    JSONArray selected=new JSONArray(),options=binding.getJSONArray("options");boolean uncertain=false;double localizationConfidence=form.confidence;
                    for(int i=0;i<options.length();i++){JSONObject option=options.getJSONObject(i);String optionKey=key+"::"+option.get("value");Boolean mark=mark(page,option,anchors,marks,optionKey);localizationConfidence=Math.min(localizationConfidence,marks.getJSONObject(optionKey).optDouble("anchor_confidence",0));if(mark==null)uncertain=true;else if(mark)selected.put(option.get("value"));}
                    if(fieldSpec.getString("type").equals("array"))f.put("value",selected);
                    else if(selected.length()==1)f.put("value",selected.get(0));
                    else if(selected.length()>1)MobileGrammar.issue(f,"MULTIPLE_EXCLUSIVE_OPTIONS");
                    f.put("confidence",Math.min(localizationConfidence,uncertain?.2:.70)).put("selection_observed",!uncertain);if(uncertain)MobileGrammar.issue(f,"MISSING_OPTION_ANCHOR_OR_UNCLEAR_MARK");
                }
                if(matches.containsKey(key)) {Work w=new Work();w.key=key;w.hand=matches.get(key);JSONObject unit=kind.equals("text")?binding:binding.getJSONObject("note");MobileVision.Box anchor=MobileVision.unitAnchor(unit,anchors);w.confidence=Math.min(form.confidence,Math.min(anchor.confidence,w.hand.confidence));w.localization=new JSONObject().put("anchor_confidence",anchor.confidence).put("handwriting_confidence",w.hand.confidence).put("label_quad",quad(anchor.quad));work.add(w);}
                else if(kind.equals("text")){MobileGrammar.issue(f,MobileVision.unitAnchor(binding,anchors)==null?"PRINTED_LABEL_NOT_DETECTED":"NO_HANDWRITING_MATCH_NOT_PROOF_OF_BLANK");}
            }
            // Classify first, then close script model before opening any OCR reader.
            try(MobileVision.Classifier script=new MobileVision.Classifier(models,"script")) {
                for(Work w:work){String type=bindings.getJSONObject(w.key).getJSONObject("schema").getString("type");
                    if(type.equals("date"))w.routes.add("date");else if(MobileRouting.numeric(w.key,type))w.routes.add("numeric");
                    else{Bitmap crop=MobileImages.crop(page,w.hand.quad,.12);MobileVision.Prediction p;try{p=script.predict(crop);}finally{crop.recycle();}
                        fields.getJSONObject(w.key).put("script_prediction",new JSONObject().put("label",p.label).put("confidence",p.confidence));
                        if(p.confidence<.8){w.routes.add("latin");w.routes.add("arabic");}else{w.routes.add(p.label);w.confidence=Math.min(w.confidence,p.confidence);}
                    }
                }
            }
            JSONArray phases=new JSONArray();int totalReads=0,completedReads=0;for(Work w:work)totalReads+=w.routes.size();progress.update(0,totalReads);
            for(String route:new String[]{"date","numeric","arabic","latin","arabic"}) {
                boolean needed=false;for(Work w:work)if(w.routes.contains(route)&&!w.completed.contains(route))needed=true;if(!needed)continue;
                long phaseStart=SystemClock.elapsedRealtime();
                try(MobileOcr reader=new MobileOcr(models,route)) {
                    for(Work w:work)if(w.routes.contains(route)&&!w.completed.contains(route)) {
                        Bitmap crop=MobileImages.crop(page,w.hand.quad,.12);double horizontalPad=.15;
                        if(route.equals("numeric")&&runtime!=null&&runtime.optBoolean("adaptive_numeric_crop")) {
                            int width=crop.getWidth(),height=crop.getHeight();int[] pixels=new int[width*height];
                            crop.getPixels(pixels,0,width,0,0,width,height);
                            if(CropBoundaryEvidence.touchesSide(pixels,width,height)) {
                                crop.recycle();horizontalPad=.5;crop=MobileImages.crop(page,w.hand.quad,.12,horizontalPad);
                            }
                        }
                        JSONObject raw;try{raw=reader.read(crop);}finally{crop.recycle();}
                        raw.put("crop_horizontal_pad",horizontalPad);
                        JSONObject parsed=grammar.parse(w.key,raw.getString("text"),Math.min(w.confidence,raw.getDouble("token_confidence")));
                        parsed.put("ocr",raw).put("crop_quad",quad(w.hand.quad)).put("crop_horizontal_pad",horizontalPad).put("localization",w.localization);
                        JSONArray warnings=raw.getJSONArray("warnings");
                        for(int i=0;i<warnings.length();i++)MobileGrammar.issue(parsed,warnings.getString(i));
                        if(warnings.length()>0) {
                            parsed.put("rejected_value",parsed.opt("value")).put("value",JSONObject.NULL);
                            if(route.equals("arabic")||route.equals("latin")) {
                                String fallback=route.equals("arabic")?"latin":"arabic";
                                if(!w.routes.contains(fallback)){w.routes.add(fallback);totalReads++;}
                            }
                        }
                        w.completed.add(route);
                        if(route.equals("arabic"))MobileGrammar.issue(parsed,"ARABIC_OCR_REQUIRES_REVIEW");
                        JSONObject existing=fields.getJSONObject(w.key);JSONArray attempts=existing.optJSONArray("raw_candidates");if(attempts==null)attempts=new JSONArray();attempts.put(raw);existing.put("raw_candidates",attempts);
                        if(w.best==null||rank(parsed)>rank(w.best))w.best=parsed;
                        progress.update(++completedReads,totalReads);
                    }
                    phases.put(new JSONObject().put("reader",route).put("elapsed_ms",SystemClock.elapsedRealtime()-phaseStart).put("process_pss_kb",Debug.getPss()).put("native_heap_bytes",Debug.getNativeHeapAllocatedSize()));
                }
                // Session.close releases native weights; do not rely on System.gc().
            }
            for(Work w:work)if(w.best!=null){JSONObject previous=fields.getJSONObject(w.key);w.best.put("raw_candidates",previous.getJSONArray("raw_candidates"));if(previous.has("script_prediction"))w.best.put("script_prediction",previous.getJSONObject("script_prediction"));
                if(bindings.getJSONObject(w.key).getString("kind").equals("choice")){
                    Object old=previous.opt("value"),note=w.best.opt("value");if(old instanceof JSONArray&&note instanceof JSONArray){JSONArray merged=new JSONArray();Set<String> seen=new HashSet<>();for(JSONArray arr:new JSONArray[]{(JSONArray)old,(JSONArray)note})for(int i=0;i<arr.length();i++)if(seen.add(arr.getString(i)))merged.put(arr.get(i));w.best.put("value",merged);}else if(note==JSONObject.NULL)w.best.put("value",old);
                    MobileGrammar.issue(w.best,"REVIEW_CHECKBOX_AND_NOTE_AGREEMENT");
                }
                if(w.routes.size()>1){boolean resolved=MobileRouting.resolvedByReaders(w.best,w.best.getJSONArray("raw_candidates"));w.best.put("script_resolution",resolved?"dual_reader_margin_v1":"unresolved");if(!resolved)MobileGrammar.issue(w.best,"UNCERTAIN_SCRIPT_ROUTE");}fields.put(w.key,w.best);
            }
            for(Iterator<String> it=fields.keys();it.hasNext();)MobileGrammar.review(fields.getJSONObject(it.next()));
            CombinedBloodPressure.apply(fields,grammar);
            MobileRelations.apply(fields);
            for(Iterator<String> it=fields.keys();it.hasNext();)MobileGrammar.review(fields.getJSONObject(it.next()));
            JSONObject nested=MobileStructure.build(schema,fields);
            catalog.validate(formId,nested);PresetForm result=FormTypes.create(formId,nested);
            evidence.put("engine","ONNX Runtime Android CPU").put("model_pack",models.json("manifest.json").getString("precision")).put("form_classifier_confidence",form.confidence).put("anchors",anchors.size()).put("handwriting_boxes",hands.size()).put("ocr_phases",phases).put("elapsed_ms",SystemClock.elapsedRealtime()-started).put("confidence_calibrated",false).put("mobile_accuracy_validated",false).put("orientation_scope","upright +/-45 degrees; EXIF orientation honored");
            evidence.put("model_pack_revision",models.json("manifest.json").optString("revision","original-v1"))
                    .put("printed_handwriting_rejections",detectedHands-hands.size())
                    .put("mark_observations",marks).put("predicted_form_id",formId).put("field_positions",bindings.length()).put("matched_text_regions",work.size()).put("ocr_reads",completedReads).put("decoded_page_width",page.getWidth()).put("decoded_page_height",page.getHeight()).put("preprocessing_version","antialiased-rgb-v2").put("table_pairing","detected_row_and_column_anchors");result.setExtractionMetadata(evidence);return result;
        }finally{page.recycle();}
    }
    private static double rank(JSONObject p){return (p.isNull("value")?0:2)+(p.optJSONArray("issues").length()==0?1:0)+p.optDouble("confidence");}
    private static Boolean mark(Bitmap page,JSONObject binding,Map<String,MobileVision.Box> anchors,JSONObject observations,String key)throws Exception {
        MobileVision.Box anchor=MobileVision.unitAnchor(binding,anchors);if(anchor==null){observations.put(key,new JSONObject().put("anchor_missing",true));return null;}
        float[][] region=MobileImages.world(binding.getJSONArray("relative_region"),anchor.quad);
        double[] frame=MobileImages.frame(region);
        for(float[] point:region){point[0]=(float)(frame[0]+(point[0]-frame[0])*1.8);point[1]=(float)(frame[1]+(point[1]-frame[1])*1.8);}
        Bitmap crop=MobileImages.crop(page,region,0);try{
            int width=crop.getWidth(),height=crop.getHeight();int[] pixels=new int[width*height];crop.getPixels(pixels,0,width,0,0,width,height);
            CheckboxReader.Result result=CheckboxReader.read(pixels,width,height,frame[4],frame[5]);
            observations.put(key,new JSONObject().put("quad",quad(region)).put("ink_fraction",result.ink)
                    .put("value",result.value==null?JSONObject.NULL:result.value).put("anchor_confidence",anchor.confidence)
                    .put("outline_located",result.located).put("outline_score",result.outlineScore)
                    .put("interior_box",new JSONArray().put(result.left).put(result.top).put(result.right).put(result.bottom)));
            return result.value;
        }finally{crop.recycle();}
    }
    private static JSONArray quad(float[][] points)throws JSONException{JSONArray out=new JSONArray();for(float[] p:points)out.put(new JSONArray().put(p[0]).put(p[1]));return out;}
}
