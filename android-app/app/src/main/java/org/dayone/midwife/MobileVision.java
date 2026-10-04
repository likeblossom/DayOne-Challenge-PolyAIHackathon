package org.dayone.midwife;

import ai.onnxruntime.*;
import android.graphics.*;
import java.nio.*;
import java.util.*;
import org.json.*;

/** Native ports of detector decoding, local anchor geometry and one-to-one matching. */
public final class MobileVision {
    public static final class Box {
        public float[][] quad;public double confidence,cx,cy,w,h,angle;public int label;
    }
    public static final class Prediction {public String label;public double confidence;}
    public static final class Classifier implements AutoCloseable {
        private final OnDeviceModels models;private final OrtSession session;private final JSONObject config;
        public Classifier(OnDeviceModels models,String name)throws Exception{this.models=models;config=models.json(name+".json");session=models.open(name+".onnx");}
        public Prediction predict(Bitmap image)throws Exception {
            int size=config.getInt("size");Bitmap input=MobileImages.fit(image,size,size,Color.WHITE);
            FloatBuffer pixels=MobileImages.tensor(input,size,size,new double[]{.485,.456,.406},new double[]{.229,.224,.225});input.recycle();
            try(OnnxTensor tensor=OnnxTensor.createTensor(models.environment,pixels,new long[]{1,3,size,size});OrtSession.Result result=session.run(Collections.singletonMap("pixels",tensor))) {
                FloatBuffer values=((OnnxTensor)result.get(0)).getFloatBuffer();int best=0;double max=values.get(0);for(int i=1;i<values.limit();i++)if(values.get(i)>max){best=i;max=values.get(i);}double sum=0;for(int i=0;i<values.limit();i++)sum+=Math.exp(values.get(i)-max);
                Prediction p=new Prediction();p.label=config.getJSONArray("classes").getString(best);p.confidence=1/sum;return p;
            }
        }
        public void close()throws OrtException{session.close();}
    }
    public static List<Box> detect(OnDeviceModels models,String name,Bitmap page)throws Exception {
        JSONObject cfg=models.json(name+".json");int size=cfg.getInt("size"),classes=cfg.getJSONArray("classes").length();
        Bitmap input=MobileImages.fit(page,size,size,Color.rgb(114,114,114));double scale=Math.min((double)size/page.getWidth(),(double)size/page.getHeight());
        int dw=(size-(int)Math.round(page.getWidth()*scale))/2,dh=(size-(int)Math.round(page.getHeight()*scale))/2;
        FloatBuffer pixels=MobileImages.tensor(input,size,size,new double[]{0,0,0},new double[]{1,1,1});input.recycle();List<Box> candidates=new ArrayList<>();
        try(OrtSession session=models.open(name+".onnx");OnnxTensor tensor=OnnxTensor.createTensor(models.environment,pixels,new long[]{1,3,size,size});OrtSession.Result result=session.run(Collections.singletonMap("pixels",tensor))) {
            OnnxTensor output=(OnnxTensor)result.get(0);FloatBuffer values=output.getFloatBuffer();long[] shape=output.getInfo().getShape();int n=(int)shape[2];
            if(shape[1]!=classes+5)throw new IllegalStateException("Unexpected YOLO output shape");
            for(int i=0;i<n;i++) {
                int label=0;double score=0;for(int c=0;c<classes;c++){double p=values.get((4+c)*n+i);if(p>score){label=c;score=p;}}
                if(score<.15)continue;Box b=new Box();b.label=label;b.confidence=score;b.cx=(values.get(i)-dw)/scale;b.cy=(values.get(n+i)-dh)/scale;b.w=values.get(2*n+i)/scale;b.h=values.get(3*n+i)/scale;b.angle=values.get((4+classes)*n+i);
                if(b.w<1||b.h<1)continue;double ca=Math.cos(b.angle),sa=Math.sin(b.angle);b.quad=new float[4][2];int[] xs={1,1,-1,-1},ys={1,-1,-1,1};
                for(int j=0;j<4;j++){b.quad[j][0]=(float)(b.cx+xs[j]*b.w/2*ca-ys[j]*b.h/2*sa);b.quad[j][1]=(float)(b.cy+xs[j]*b.w/2*sa+ys[j]*b.h/2*ca);}candidates.add(b);
            }
        }
        candidates.sort((a,b)->Double.compare(b.confidence,a.confidence));List<Box> result=new ArrayList<>();
        // Match Ultralytics fast rotated NMS: reject if any higher-scoring box overlaps.
        for(int i=0;i<candidates.size()&&result.size()<cfg.optInt("max_det",150);i++){Box b=candidates.get(i);boolean suppressed=false;for(int j=0;j<i;j++){Box a=candidates.get(j);if(a.label==b.label&&probIou(a,b)>.45){suppressed=true;break;}}if(!suppressed)result.add(b);}return result;
    }
    private static double[] covariance(Box b){double a=b.w*b.w/12,c=b.h*b.h/12,co=Math.cos(b.angle),si=Math.sin(b.angle);return new double[]{a*co*co+c*si*si,a*si*si+c*co*co,(a-c)*co*si};}
    private static double probIou(Box a,Box b){double[] x=covariance(a),y=covariance(b);double eps=1e-7,A=x[0]+y[0],B=x[1]+y[1],C=x[2]+y[2],den=A*B-C*C+eps,dx=a.cx-b.cx,dy=a.cy-b.cy;
        double t1=(A*dy*dy+B*dx*dx)/den*.25,t2=-C*dx*dy/den*.5,t3=Math.log((A*B-C*C)/(4*Math.sqrt(Math.max(0,x[0]*x[1]-x[2]*x[2])*Math.max(0,y[0]*y[1]-y[2]*y[2]))+eps)+eps)*.5;
        double distance=Math.max(eps,Math.min(100,t1+t2+t3));return 1-Math.sqrt(1-Math.exp(-distance)+eps);
    }
    public static Map<String,Box> pair(Map<String,Box> anchors,List<Box> hands,JSONObject bindings,JSONObject priors)throws Exception {
        List<String> keys=new ArrayList<>();List<JSONObject> units=new ArrayList<>();
        for(Iterator<String> it=bindings.keys();it.hasNext();){String key=it.next();JSONObject b=bindings.getJSONObject(key),u=b.optString("kind").equals("text")?b:b.optJSONObject("note");if(u!=null&&unitAnchor(u,anchors)!=null){keys.add(key);units.add(u);}}
        int n=keys.size();double[][] costs=new double[n][hands.size()+n];
        for(int i=0;i<n;i++){
            Arrays.fill(costs[i],2.5);JSONObject u=units.get(i);double[] f=MobileImages.frame(unitAnchor(u,anchors).quad);float[][] reg=MobileImages.points(u.getJSONArray("relative_region"));double lx=Double.MAX_VALUE,ly=lx,hx=-lx,hy=-lx;
            for(float[] p:reg){lx=Math.min(lx,p[0]);ly=Math.min(ly,p[1]);hx=Math.max(hx,p[0]);hy=Math.max(hy,p[1]);}
            JSONObject prior=priors.optJSONObject(keys.get(i));
            for(int j=0;j<hands.size();j++){Box h=hands.get(j);double dx=h.cx-f[0],dy=h.cy-f[1],x=(dx*f[2]+dy*f[3])/Math.max(1,f[4]),y=(-dx*f[3]+dy*f[2])/Math.max(1,f[5]);
                double outside=Math.hypot((Math.max(lx-x,0)+Math.max(x-hx,0))/Math.max(hx-lx,.2),(Math.max(ly-y,0)+Math.max(y-hy,0))/Math.max(hy-ly,.5));
                double ps=prior==null?0:Math.hypot((x-prior.getJSONArray("mean").getDouble(0))/prior.getJSONArray("std").getDouble(0),(y-prior.getJSONArray("mean").getDouble(1))/prior.getJSONArray("std").getDouble(1));
                costs[i][j]=outside>.65?10:Math.min(10,outside*3+ps*.12+(1-h.confidence)*.15);
            }
        }
        int[] assigned=hungarian(costs);Map<String,Box> matches=new HashMap<>();for(int i=0;i<n;i++)if(assigned[i]<hands.size()&&costs[i][assigned[i]]<2.5)matches.put(keys.get(i),hands.get(assigned[i]));return matches;
    }
    public static int[] hungarian(double[][] cost){int n=cost.length;if(n==0)return new int[0];int m=cost[0].length;double[] u=new double[n+1],v=new double[m+1];int[] p=new int[m+1],way=new int[m+1];
        for(int i=1;i<=n;i++){p[0]=i;int j0=0;double[] min=new double[m+1];Arrays.fill(min,Double.POSITIVE_INFINITY);boolean[] used=new boolean[m+1];do{used[j0]=true;int i0=p[j0],j1=0;double delta=Double.POSITIVE_INFINITY;for(int j=1;j<=m;j++)if(!used[j]){double cur=cost[i0-1][j-1]-u[i0]-v[j];if(cur<min[j]){min[j]=cur;way[j]=j0;}if(min[j]<delta){delta=min[j];j1=j;}}for(int j=0;j<=m;j++)if(used[j]){u[p[j]]+=delta;v[j]-=delta;}else min[j]-=delta;j0=j1;}while(p[j0]!=0);do{int j1=way[j0];p[j0]=p[j1];j0=j1;}while(j0!=0);}
        int[] result=new int[n];for(int j=1;j<=m;j++)if(p[j]>0)result[p[j]-1]=j-1;return result;
    }
    public static Box unitAnchor(JSONObject unit,Map<String,Box> anchors)throws Exception {
        Box row=anchors.get(unit.getString("anchor"));if(row==null||!unit.has("column_anchor"))return row;
        Box column=anchors.get(unit.getString("column_anchor"));if(column==null)return null;
        double[] f=MobileImages.frame(row.quad);float[][] target=MobileImages.world(unit.getJSONArray("column_relative_region"),column.quad),expected=MobileImages.world(unit.getJSONArray("relative_region"),row.quad);
        double dx=0,dy=0;for(int i=0;i<4;i++){dx+=(target[i][0]-expected[i][0])/4.;dy+=(target[i][1]-expected[i][1])/4.;}double shift=dx*f[2]+dy*f[3];
        Box result=new Box();result.confidence=Math.min(row.confidence,column.confidence);result.quad=new float[4][2];for(int i=0;i<4;i++){result.quad[i][0]=(float)(row.quad[i][0]+shift*f[2]);result.quad[i][1]=(float)(row.quad[i][1]+shift*f[3]);}return result;
    }
}
