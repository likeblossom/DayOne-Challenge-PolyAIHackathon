from pathlib import Path
from ..common import ROOT,BASE,MODELS,REPORTS,read_json,write_json
DATASET=ROOT/'data/numbers'
CHECKPOINT=MODELS/'trocr_numbers'
LOGS=REPORTS/'numeric_ocr'
OUTPUT=BASE/'outputs'/'numeric_ocr'
