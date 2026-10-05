import org.dayone.midwife.CropBoundaryEvidence;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.*;

public final class CropBoundaryDiagnostic {
    public static void main(String[] args)throws Exception {
        BufferedReader input=new BufferedReader(new InputStreamReader(System.in));String path;
        while((path=input.readLine())!=null) {
            BufferedImage image=ImageIO.read(new File(path));
            if(image==null)throw new IOException("Cannot read diagnostic crop");
            int width=image.getWidth(),height=image.getHeight();
            System.out.println(CropBoundaryEvidence.touchesSide(image.getRGB(0,0,width,height,null,0,width),width,height));
        }
    }
}
