from pathlib import Path
from PIL import Image, ImageDraw

img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse((8, 8, 248, 248), fill="#1a73e8")
d.polygon([(128, 52), (196, 136), (154, 136), (154, 204), (102, 204), (102, 136), (60, 136)],
          fill="white")
img.save(Path(__file__).parent / "icon.ico",
         sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
