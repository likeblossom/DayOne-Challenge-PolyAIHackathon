package org.dayone.midwife;

import ai.onnxruntime.*;
import android.graphics.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** One reader at a time; greedy decoder with no retained autoregressive KV cache. */
public final class MobileOcr implements AutoCloseable {
    private final OnDeviceModels models;private final String route;private final JSONObject config;
    private final OrtSession encoder,decoder;private final JSONArray pieces;private final Set<Integer> special=new HashSet<>();
    private final Map<Integer,Integer> byteDecoder=new HashMap<>();
    public MobileOcr(OnDeviceModels models,String route) throws Exception {
        this.models=models;this.route=route;config=models.json(route+"/reader.json");pieces=config.getJSONArray("pieces");
        for(int i=0;i<config.getJSONArray("special_ids").length();i++)special.add(config.getJSONArray("special_ids").getInt(i));
        List<Integer> bytes=new ArrayList<>();for(int i=33;i<=126;i++)bytes.add(i);for(int i=161;i<=172;i++)bytes.add(i);for(int i=174;i<=255;i++)bytes.add(i);
        for(int b:bytes)byteDecoder.put(b,b);int extra=256;for(int b=0;b<256;b++)if(!bytes.contains(b))byteDecoder.put(extra++,b);
        OrtSession e=models.open(route+"/"+config.getString("encoder"));try{decoder=models.open(route+"/"+config.getString("decoder"));}catch(Exception ex){e.close();throw ex;}encoder=e;
    }
    public JSONObject read(Bitmap crop) throws Exception {
        long started=android.os.SystemClock.elapsedRealtime(),encoderFinished=started;
        JSONObject proc=config.getJSONObject("processor");int height=config.getInt("height"),width=config.getInt("width");
        Bitmap input=prepareInput(crop,config);
        FloatBuffer pixels=MobileImages.tensor(input,width,height,MobileImages.vector(proc.getJSONArray("image_mean")),MobileImages.vector(proc.getJSONArray("image_std")));
        if(input!=crop)input.recycle();
        List<Integer> generated=new ArrayList<>();long[] sequence={config.getInt("start_id")};double logProbability=0;int count=0;boolean ended=false;
        try(OnnxTensor x=OnnxTensor.createTensor(models.environment,pixels,new long[]{1,3,height,width});OrtSession.Result encoded=encoder.run(Collections.singletonMap("pixels",x))) {
            encoderFinished=android.os.SystemClock.elapsedRealtime();
            OnnxTensor hidden=(OnnxTensor)encoded.get(0);
            for(int step=0;step<config.getInt("max_new_tokens");step++) {
                if(Thread.currentThread().isInterrupted())throw new InterruptedException("OCR cancelled");
                try(OnnxTensor ids=OnnxTensor.createTensor(models.environment,LongBuffer.wrap(sequence),new long[]{1,sequence.length})) {
                    Map<String,OnnxTensor> inputs=new HashMap<>();inputs.put("ids",ids);inputs.put("hidden",hidden);
                    try(OrtSession.Result result=decoder.run(inputs)) {
                        FloatBuffer logits=((OnnxTensor)result.get(0)).getFloatBuffer();int best=0;float max=logits.get(0);
                        for(int j=1;j<logits.limit();j++)if(logits.get(j)>max){best=j;max=logits.get(j);}
                        double sum=0;for(int j=0;j<logits.limit();j++)sum+=Math.exp(logits.get(j)-max);logProbability-=Math.log(sum);count++;
                        generated.add(best);if(best==config.getInt("eos_id")){ended=true;break;}
                        sequence=Arrays.copyOf(sequence,sequence.length+1);sequence[sequence.length-1]=best;
                    }
                }
            }
        }
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        for(int token:generated)if(!special.contains(token)) {
            String piece=pieces.getString(token);for(int i=0;i<piece.length();) {int cp=piece.codePointAt(i);i+=Character.charCount(cp);Integer b=byteDecoder.get(cp);if(b!=null)out.write(b);else out.write(new String(Character.toChars(cp)).getBytes(StandardCharsets.UTF_8));}
        }
        String text=out.toString("UTF-8").trim();
        return new JSONObject().put("text",text).put("token_confidence",Math.exp(logProbability/Math.max(1,count))).put("token_ids",new JSONArray(generated)).put("model",route).put("generation_limit",!ended).put("warnings",MobileRouting.outputWarnings(text,!ended,route)).put("precision",config.getString("precision"))
                .put("edge_rule_trim",config.optBoolean("strip_edge_rules")).put("input_crop_bounds",new JSONArray(cleanupBounds(crop,config)))
                .put("preprocess_and_encoder_ms",encoderFinished-started).put("decoder_ms",android.os.SystemClock.elapsedRealtime()-encoderFinished);
    }
    static Bitmap prepareInput(Bitmap crop,JSONObject config)throws JSONException {
        int width=config.getInt("width"),height=config.getInt("height");
        String type=config.getJSONObject("processor").getString("image_processor_type");
        int[] bounds=cleanupBounds(crop,config);
        Bitmap trimmed=Bitmap.createBitmap(crop,bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]),prepared;
        try {
            if(type.equals("NougatImageProcessor"))prepared=arabicInput(trimmed,width,height);
            else if(type.equals("ViTImageProcessor"))prepared=config.getJSONObject("processor").optBoolean("sanad_fit")?MobileImages.fitAntialiased(trimmed,width,height,Color.WHITE):MobileImages.resizeAntialiased(trimmed,width,height);
            else throw new IllegalArgumentException("Unsupported OCR image processor: "+type);
        } catch(RuntimeException error) {if(trimmed!=crop)trimmed.recycle();throw error;}
        if(trimmed!=crop&&prepared!=trimmed)trimmed.recycle();return prepared;
    }
    private static int[] cleanupBounds(Bitmap crop,JSONObject config) {
        int width=crop.getWidth(),height=crop.getHeight();
        if(!config.optBoolean("strip_edge_rules"))return new int[]{0,0,width,height};
        int[] pixels=new int[width*height];crop.getPixels(pixels,0,width,0,0,width,height);
        return EdgeRuleCrop.bounds(pixels,width,height);
    }
    private static Bitmap arabicInput(Bitmap crop,int width,int height) {
        // Nougat crop-margin: threshold relative to image gray range, then fit/pad.
        int min=255,max=0;for(int y=0;y<crop.getHeight();y++)for(int x=0;x<crop.getWidth();x++){int p=crop.getPixel(x,y);int g=(int)(.299*(p>>16&255)+.587*(p>>8&255)+.114*(p&255));min=Math.min(min,g);max=Math.max(max,g);}
        int left=crop.getWidth(),top=crop.getHeight(),right=-1,bottom=-1;
        if(max>min)for(int y=0;y<crop.getHeight();y++)for(int x=0;x<crop.getWidth();x++){int p=crop.getPixel(x,y);double g=.299*(p>>16&255)+.587*(p>>8&255)+.114*(p&255);if((g-min)/(max-min)*255<200){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}}
        Bitmap trimmed=right>=left?Bitmap.createBitmap(crop,left,top,right-left+1,bottom-top+1):crop;
        Bitmap fitted=MobileImages.fit(trimmed,width,height,Color.BLACK);if(trimmed!=crop)trimmed.recycle();return fitted;
    }
    @Override public void close() throws OrtException {try{decoder.close();}finally{encoder.close();}}
}
