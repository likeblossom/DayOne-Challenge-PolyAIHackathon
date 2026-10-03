from pathlib import Path

from PIL import Image, ImageDraw

from midwife_extractor.imaging import checkbox_ink_score


def checkbox(checked: bool) -> Image.Image:
    image = Image.new("RGB", (40, 40), (240, 185, 200))
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 34, 34), outline="black", width=2)
    if checked:
        draw.line((4, 4, 35, 35), fill=(20, 60, 170), width=3)
        draw.line((35, 4, 4, 35), fill=(20, 60, 170), width=3)
    return image


def test_checked_box_has_stronger_ink_signal_than_empty_box():
    empty = checkbox_ink_score(checkbox(False))
    checked = checkbox_ink_score(checkbox(True))
    assert empty < 0.15
    assert checked > 0.15
    assert checked > empty + 0.2
