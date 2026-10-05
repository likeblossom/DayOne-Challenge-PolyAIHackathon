import org.dayone.midwife.BlankEvidence;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.*;
public final class BlankDiagnostic {
    public static void main(String[] args)throws Exception {
        BufferedReader reader=new BufferedReader(new InputStreamReader(System.in));String path;
        while((path=reader.readLine())!=null){BufferedImage image=ImageIO.read(new File(path));int w=image.getWidth(),h=image.getHeight();System.out.println(BlankEvidence.empty(image.getRGB(0,0,w,h,null,0,w),w,h));}
    }
}
