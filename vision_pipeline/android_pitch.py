"""Six-slide Android pitch; editable PPTX, matching PDF and architecture image."""
import html,json,math
from pathlib import Path
import fitz
from PIL import Image,ImageDraw
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'vision_pipeline/presentation';REPORTS=ROOT/'vision_pipeline/reports'
W,H=13.333,7.5
INK='152638';MUTED='536579';TEAL='087F78';LIGHT='EFF6F5';LINE='DCE5E8'

class Deck:
    def __init__(self):
        OUT.mkdir(exist_ok=True);self.p=Presentation();self.p.slide_width=Inches(W);self.p.slide_height=Inches(H)
        self.pdf=canvas.Canvas(str(OUT/'Sanad_pitch.pdf'),pagesize=(W*72,H*72));self.titles=[];self.notes=[];self.architecture_index=None
    def text(self,x,y,w,h,text,size=20,bold=False,color=INK):
        assert min(x,y)>=0 and x+w<=W+.01 and y+h<=H+.01
        font='Helvetica-Bold' if bold else 'Helvetica';lines=[]
        for paragraph in str(text).split('\n'):
            line=''
            for word in paragraph.split():
                proposed=(line+' '+word).strip()
                if line and stringWidth(proposed,font,size)>w*72:lines.append(line);line=word
                else:line=proposed
            lines.append(line)
        assert len(lines)*size*1.18<=h*72+2,f'Text overflow: {text}'
        tf=self.slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)).text_frame;tf.word_wrap=False
        tf.margin_left=tf.margin_top=tf.margin_right=tf.margin_bottom=0
        self.pdf.setFillColor('#'+color);self.pdf.setFont(font,size)
        for i,line in enumerate(lines):
            p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line;p.font.name='Arial';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color);p.line_spacing=1.18;p.space_after=Pt(0)
            yy=y*72+size+i*size*1.18;self.pdf.drawString(x*72,H*72-yy,line)
            self.svg.append(f'<text x="{x*100}" y="{yy/72*100}" font-family="Arial,sans-serif" font-size="{size/72*100}" fill="#{color}" font-weight="{700 if bold else 400}">{html.escape(line)}</text>')
    def box(self,x,y,w,h,fill=LIGHT):
        s=self.slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h));s.fill.solid();s.fill.fore_color.rgb=RGBColor.from_string(fill);s.line.color.rgb=RGBColor.from_string(LINE)
        for ref in s._element.xpath('.//a:effectRef'):ref.set('idx','0')
        self.pdf.setFillColor('#'+fill);self.pdf.setStrokeColor('#'+LINE);self.pdf.rect(x*72,(H-y-h)*72,w*72,h*72,fill=1,stroke=1)
        self.svg.append(f'<rect x="{x*100}" y="{y*100}" width="{w*100}" height="{h*100}" fill="#{fill}" stroke="#{LINE}"/>')
    def line(self,a,b):
        s=self.slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(a[0]),Inches(a[1]),Inches(b[0]),Inches(b[1]));s.line.color.rgb=RGBColor.from_string(MUTED);s.line.width=Pt(1.4)
        self.pdf.setStrokeColor('#'+MUTED);self.pdf.setLineWidth(1.4);self.pdf.line(a[0]*72,(H-a[1])*72,b[0]*72,(H-b[1])*72)
        self.svg.append(f'<line x1="{a[0]*100}" y1="{a[1]*100}" x2="{b[0]*100}" y2="{b[1]*100}" stroke="#{MUTED}" stroke-width="1.4"/>')
    def arrow(self,*points):
        for a,b in zip(points,points[1:]):self.line(a,b)
        a,b=points[-2:];angle=math.atan2(b[1]-a[1],b[0]-a[0])
        for delta in [-.45,.45]:self.line(b,(b[0]-.10*math.cos(angle+delta),b[1]-.10*math.sin(angle+delta)))
    def image(self,path,x,y,w,h):
        with Image.open(path) as im:scale=min(w/im.width,h/im.height);ww,hh=im.width*scale,im.height*scale
        xx,yy=x+(w-ww)/2,y+(h-hh)/2;self.slide.shapes.add_picture(str(path),Inches(xx),Inches(yy),Inches(ww),Inches(hh));self.pdf.drawImage(str(path),xx*72,(H-yy-hh)*72,ww*72,hh*72)
    def start(self,title,note=''):
        if self.titles:self.pdf.showPage()
        self.slide=self.p.slides.add_slide(self.p.slide_layouts[6]);self.svg=[];self.titles.append(title);self.notes.append(note);self.slide.notes_slide.notes_text_frame.text=note
        self.text(.55,.3,10,.25,'SANAD / ANDROID',10,True,TEAL);self.text(.55,.85,12.1,.7,title,30,True)
        self.text(.55,7.1,11.8,.2,'Sanad | Hackathon prototype',9,color=MUTED);self.text(12.3,7.1,.5,.2,str(len(self.titles)),9,color=MUTED)
    def node(self,x,y,w,title,body):
        self.box(x,y,w,1.0);self.text(x+.12,y+.13,w-.24,.3,title,15,True);self.text(x+.12,y+.53,w-.24,.43,body,11,color=MUTED)
    def save(self):
        self.p.save(OUT/'Sanad_pitch.pptx');self.pdf.save();(OUT/'speaker_notes.txt').write_text('\n\n'.join(f'{i+1}. {t}\n{n}' for i,(t,n) in enumerate(zip(self.titles,self.notes))))
        previews=OUT/'previews';previews.mkdir(exist_ok=True);sheet=Image.new('RGB',(1440,math.ceil(len(self.titles)/3)*295),'white');draw=ImageDraw.Draw(sheet)
        with fitz.open(OUT/'Sanad_pitch.pdf') as doc:
            for i,page in enumerate(doc):
                pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5));path=previews/f'slide_{i+1:02}.png';pix.save(path)
                if i==self.architecture_index:pix.save(OUT/'architecture.png')
                with Image.open(path) as im:
                    im.thumbnail((480,270));x,y=i%3*480,i//3*295;sheet.paste(im,(x,y));draw.text((x+8,y+273),f'{i+1}. {self.titles[i]}',fill='black')
        sheet.save(OUT/'contact_sheet.jpg');(OUT/'build_report.json').write_text(json.dumps({'slides':len(self.titles),'titles':self.titles,'words_per_slide':[len(' '.join(s.text for s in slide.shapes if s.has_text_frame).split()) for slide in self.p.slides],'scope':'Android app; synthetic training metrics separately identified'},indent=2)+'\n')

def architecture(d):
    d.start('On-device architecture','Java + ONNX Runtime CPU. YOLO11n OBB detects form-specific printed anchors and shared handwriting lines. Relative regions and Hungarian assignment produce oriented crops. Dates and numbers route by schema; other text uses the script classifier. One transformer reader is loaded at a time. Checkboxes bypass OCR. No fixed page coordinates or global page alignment. Confidence is heuristic, not calibrated.')
    d.text(.6,1.7,12,.4,'All image processing and OCR run on Android.',18,color=MUTED)
    for args in [(.6,2.75,1.5,'Photo','Camera / file'),(2.5,2.75,2.3,'Form classifier','MobileNetV3 / 8 classes'),(5.3,2.2,3,'Printed-label YOLO','One detector per form'),(5.3,3.45,3,'Handwriting YOLO','Shared line detector'),(9,2.75,3.7,'Pair + crop','Relative position / local margin'),(9,5.05,3.7,'Field + script routing','Date / numeric / Latin / Arabic'),(5.95,5.05,2.65,'Transformer OCR','TrOCR / Arabic Nougat'),(3,5.05,2.55,'Field validation','Units / dates / consistency'),(.6,5.05,2,'App record','Value / status / confidence')]:d.node(*args)
    for points in [[(2.1,3.25),(2.5,3.25)],[(4.8,3.25),(5,3.25),(5,2.7),(5.3,2.7)],[(5,3.25),(5,3.95),(5.3,3.95)],[(8.3,2.7),(8.6,2.7),(8.6,3.25),(9,3.25)],[(8.3,3.95),(8.6,3.95),(8.6,3.25)],[(10.85,3.75),(10.85,5.05)],[(9,5.55),(8.6,5.55)],[(5.95,5.55),(5.55,5.55)],[(3,5.55),(2.6,5.55)]]:d.arrow(*points)
    d.text(.6,6.5,12,.35,'One OCR reader at a time. Checkboxes bypass OCR. Original image stays attached.',15,color=MUTED)
    d.architecture_index=len(d.titles)-1;(OUT/'architecture.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1333" height="750" viewBox="0 0 1333 750"><rect width="1333" height="750" fill="white"/>'+''.join(d.svg)+'</svg>')

def main():
    d=Deck()
    d.start('Sanad','Android prototype for eight maternal/newborn forms. Records and original images use AES-GCM with Android Keystore. Data extraction, not diagnosis. Actual phone screenshot, not a mock UI.')
    d.text(.65,2.05,8,1.4,'Paper forms to structured\nrecords on Android.',34,True);d.text(.65,4,7.8,1.1,'8 form types. Offline OCR.\nOriginal image, values, status and confidence.',22);d.text(.65,5.7,7.8,.7,'Review, save locally, sync over USB.',21,color=TEAL);d.image(ROOT/'demo/Sanad-main-screen.png',9.4,1.65,2.8,5.15)
    d.start('We generated the training data','Removed /F3 handwriting text objects and blue vector mark paths from an in-memory copy of the supplied PDF; retained printed artwork. This is not raster inpainting. Schema values are drawn using 18 handwriting fonts, including cursive and Arabic shaping. Panels are verified renderer replay. 4,800 base pages; extra long-line and specialist date/numeric crops are separate. CSV/JSONL labels store values, statuses and boxes. Rotation, blur, noise and JPEG degradation transform image and geometry together.')
    for i,(name,title) in enumerate([('source','Supplied form'),('blank','Remove handwriting'),('synthetic','Write new values'),('augmented','Augment image')]):
        x=.6+i*3.1;d.image(OUT/'assets'/f'{name}.png',x,1.9,2.8,3.7);d.text(x,5.75,2.8,.4,title,17,True)
    d.text(.6,6.3,12,.55,'4,800 base pages / 18 fonts / English, French, Arabic / CSV + JSONL labels',18)
    architecture(d)
    date=json.loads((REPORTS/'date_ocr/training.json').read_text());number=json.loads((REPORTS/'numeric_ocr/training.json').read_text())
    d.start('Models trained for the app','Synthetic training: MobileNetV3 form/script classifiers, eight YOLO anchor detectors and shared handwriting detector. Date/numeric TrOCR specialists fine-tuned for three epochs; Arabic Nougat is pretrained. Bars show synthetic validation accuracy, not Android accuracy. Mixed TrOCR exports use FP32 encoders/embeddings and INT8 decoder linear weights. Model storage is not peak RAM.')
    d.text(.6,1.85,12,.6,'YOLO labels + handwriting. TrOCR fine-tuned on dates, numbers and units.',21)
    for j,(name,r,color) in enumerate([('Date OCR',date,TEAL),('Numeric OCR',number,'245CA6')]):
        x=.75+j*6.25;d.text(x,2.8,5.6,.4,name+' / validation exact match',18,True)
        for i,row in enumerate(r['history']):
            y=3.5+i*.65;score=row['validation']['exact_accuracy'];d.text(x,y,1.05,.3,'Epoch '+str(row['epoch']),13,color=MUTED);d.box(x+1.15,y+.02,score*3.3,.24,color);d.text(x+4.65,y,.9,.3,f'{score:.0%}',14,True)
        d.text(x,5.65,5.7,.45,f"Synthetic test: {r['synthetic_test']['exact_accuracy']:.1%} exact",19)
    d.text(.6,6.4,12,.35,'Android: mixed-precision ONNX / 2 CPU threads / one reader loaded at a time',16,color=MUTED)
    d.start('Three problems we addressed','Detected anchors replace fixed-coordinate crops. Cursive/Arabic fonts, longer lines and augmentation diversify training. Schema grammar checks units, numeric ranges, real dates and cross-field logic. Ambiguous digit/unit changes stay flagged. Valid fields at >=0.70 pass; genuine issues require review regardless of score. Missing handwriting alone is not proof of blank. Conditional non-applicability requires an accepted parent field.')
    for i,(problem,solution) in enumerate([('Cropping coordinates','Detect labels and handwriting; pair by relative position.'),('Handwriting','Cursive fonts, longer lines, augmentation and OCR fine-tuning.'),('Character context','Field-specific units, dates, ranges and consistency checks.')]):
        y=2.1+i*1.25;d.box(.6,y,12.1,1.05);d.text(.85,y+.2,3.15,.7,problem,20,True);d.text(4.2,y+.2,8.15,.7,solution,21)
    d.text(.6,6.25,12,.45,'Valid fields at 70%+ pass. Unresolved issues stay flagged. Raw OCR is retained.',17,color=MUTED)
    d.start('Running on an Android phone','DOOGEE S200 Plus, Android 15. Organizer specimen page 41, form type 1, record 2026-987-006. Live extraction 37.016 seconds; no manual field edits, zero review flags under current policy. Preflight process PSS snapshots reached 888905 KB (~0.91 GB decimal): sampled, not continuous peak or minimum RAM. Pack storage ~2.94 GB. USB SQLite commit bd91745a-9116-409e-9d56-7514b055e577. Curated demo, not aggregate phone accuracy. All eight forms are wired into Android. Screenshot protection restored after capture.')
    d.image(ROOT/'demo/Sanad-main-screen.png',.7,1.85,2.3,4.9);d.text(3.55,2,8.8,.6,'37 seconds / one complete form',28,True);d.text(3.55,3,8.8,.9,'~0.91 GB sampled process memory\n2.94 GB model pack',21)
    d.save();print(OUT/'Sanad_pitch.pptx')

if __name__=='__main__':main()
