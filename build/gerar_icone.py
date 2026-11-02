"""Gera build/baixa.ico (botão vermelho com seta de download). Requer Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw

TAMANHO = 256
img = Image.new("RGBA", (TAMANHO, TAMANHO), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, 248, 248), radius=56, fill=(220, 30, 40))
# seta para baixo
d.rectangle((108, 52, 148, 140), fill="white")
d.polygon([(68, 132), (188, 132), (128, 196)], fill="white")
# base
d.rounded_rectangle((60, 206, 196, 222), radius=8, fill="white")

destino = Path(__file__).with_name("baixa.ico")
img.save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(destino)
