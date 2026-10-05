import org.dayone.midwife.CheckboxReader;
import org.dayone.midwife.EdgeRuleCrop;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.*;

/** Desktop harness for the exact pure-Java checkbox implementation. */
public class CheckboxDiagnostic {
    public static void main(String[] args)throws Exception {
        BufferedReader input=new BufferedReader(new InputStreamReader(System.in));String line;
        while((line=input.readLine())!=null) {
            String[] fields=line.split("\t");BufferedImage image=ImageIO.read(new File(fields[0]));
            int w=image.getWidth(),h=image.getHeight();
            if(fields[1].equals("rules")) {
                int[] b=EdgeRuleCrop.bounds(image.getRGB(0,0,w,h,null,0,w),w,h);
                System.out.println("["+b[0]+","+b[1]+","+b[2]+","+b[3]+"]");continue;
            }
            CheckboxReader.Result r=CheckboxReader.read(image.getRGB(0,0,w,h,null,0,w),w,h,Double.parseDouble(fields[1]),Double.parseDouble(fields[2]));
            System.out.println("{\"located\":"+r.located+",\"value\":"+r.value+",\"ink\":"+r.ink+",\"left\":"+r.left+",\"top\":"+r.top+",\"right\":"+r.right+",\"bottom\":"+r.bottom+"}");
        }
    }
}
