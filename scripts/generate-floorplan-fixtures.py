"""Reproducible invented 600×400 plans, 200px known lines = 10m; no real data."""
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin

root = Path(__file__).resolve().parents[1] / 'data/demo/floorplans'
root.mkdir(parents=True, exist_ok=True)
plans = []
for label in ('Ground floor', 'Basement B1'):
    image = Image.new('RGB', (600, 400), '#f8fafc')
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), 'SYNTHETIC FLOORPLAN — SOFTWARE TESTS ONLY', fill='black')
    draw.text((20, 45), label + ' · No rooms, corridors or routes verified', fill='black')
    draw.rectangle((70, 80, 460, 350), outline='#334155', width=3)
    draw.line((100, 100, 300, 100), fill='#2255aa', width=4)
    draw.line((100, 100, 100, 300), fill='#2255aa', width=4)
    draw.text((140, 112), 'Invented known line: 200px = 10m', fill='black')
    draw.rectangle((480, 320, 580, 380), fill='#ef4444')
    draw.text((483, 340), 'PRIVATE SAMPLE', fill='black')
    plans.append(image)
metadata = PngImagePlugin.PngInfo()
metadata.add_text('private_note', 'PRIVATE-ORIGINAL-METADATA: invented sensitive test region, mask before public review')
plans[0].save(root / 'synthetic-ground.png', pnginfo=metadata)
plans[1].save(root / 'synthetic-basement.jpg', quality=90, comment=b'PRIVATE-ORIGINAL-METADATA')
plans[0].save(root / 'synthetic-two-pages.pdf', format='PDF', save_all=True, append_images=[plans[1]], resolution=150.0, title='Synthetic plans: no institutional data', creationDate='D:20261001000000Z', modDate='D:20261001000000Z')
