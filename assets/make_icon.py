import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from PIL import Image, ImageDraw  # noqa: E402


def logo(size, color="#2563eb"):
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = s
    d.polygon([(w * .5, w * .04), (w * .9, w * .18), (w * .88, w * .52), (w * .5, w * .96),
               (w * .12, w * .52), (w * .1, w * .18)], fill=color)
    d.polygon([(w * .5, w * .24), (w * .72, w * .5), (w * .58, w * .5), (w * .58, w * .74),
               (w * .42, w * .74), (w * .42, w * .5), (w * .28, w * .5)], fill="white")
    return img.resize((size, size), Image.LANCZOS)


out = Path(__file__).parent
logo(256).save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                        (128, 128), (256, 256)])
logo(512).save(out / "logo.png")
