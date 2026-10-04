from pathlib import Path
from ..common import ROOT,BASE,MODELS,REPORTS,read_json,write_json
DATASET=ROOT/'data/dates'
CHECKPOINT=MODELS/'trocr_dates'
LOGS=REPORTS/'date_ocr'
OUTPUT=BASE/'outputs'/'date_ocr'
