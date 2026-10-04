"""One-time download of pinned OCR weights; inference itself is offline."""
from huggingface_hub import snapshot_download
from .common import MODELS,REPORTS,write_json

CHECKPOINTS={
 'trocr_latin':dict(repo='microsoft/trocr-base-handwritten',revision='eaacaf452b06415df8f10bb6fad3a4c11e609406',license='MIT'),
 'nougat_arabic':dict(repo='MohamedRashad/arabic-small-nougat',revision='2ccd10dd3b1d3ba9a24bc5274aa4c8a7508e8784',license='GPL-3.0'),
}

def main():
    for name,spec in CHECKPOINTS.items():
        snapshot_download(spec['repo'],revision=spec['revision'],local_dir=MODELS/name,
                          allow_patterns=['*.json','*.safetensors','*.txt','*.model','README.md','LICENSE*'])
    write_json(REPORTS/'ocr_models.json',CHECKPOINTS)

if __name__=='__main__':main()
