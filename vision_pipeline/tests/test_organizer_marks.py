import fitz
from vision_pipeline.label_organizer import marked,printed_alignment
import numpy as np


def page_with(strokes):
    class Page:
        rect=fitz.Rect(0,0,100,100)
        def get_drawings(self):return strokes
    return Page()


def stroke(points,color=(.07,.07,.1)):
    points=[fitz.Point(*point) for point in points]
    return dict(color=color,rect=fitz.Rect(min(p.x for p in points),min(p.y for p in points),max(p.x for p in points),max(p.y for p in points)),
                items=[('l',a,b) for a,b in zip(points,points[1:])])


def test_black_tick_and_blue_cross_are_both_marks():
    box=[.4,.4,.5,.5]
    assert marked(page_with([stroke([(41,45),(44,50),(52,37)])]),box)
    assert marked(page_with([stroke([(40,40),(50,50)],(.1,.2,.8))]),box)


def test_printed_rectangles_and_underlines_are_not_marks():
    box=[.4,.4,.5,.5]
    assert not marked(page_with([stroke([(40,40),(50,41),(49,51),(39,50),(40,40)])]),box)
    assert not marked(page_with([stroke([(40,50),(50,50)])]),box)
    assert not marked(page_with([stroke([(10,10),(20,20)])]),box)


def test_annotation_tracks_source_pdf_printed_geometry():
    class Page:
        rect=fitz.Rect(0,0,100,100)
        def __init__(self,matrix):self.matrix=matrix
        def get_text(self,kind):
            spans=[]
            for i,(x,y) in enumerate(( (x,y) for x in [10,45,80] for y in [10,45,80])):
                cx,cy=np.array([x,y,1])@self.matrix
                spans.append(dict(font='Helvetica',text='Label '+str(i),bbox=[cx-2,cy-2,cx+2,cy+2]))
            return dict(blocks=[dict(lines=[dict(spans=spans)])])
    identity=np.array([[1,0],[0,1],[0,0]])
    expected=np.array([[.999,.012],[-.012,.999],[3,4]])
    actual,report=printed_alignment(Page(identity),Page(expected))
    assert report['accepted'] and report['inliers']==9
    np.testing.assert_allclose(actual,expected,atol=1e-10)
