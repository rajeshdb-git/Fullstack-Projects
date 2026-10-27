from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import colorsys

folder = Path('static/images')
folder.mkdir(exist_ok=True)

items = {
    'back-neck.jpg': ('Back & Neck', (20, 95, 120)),
    'knee-ankle.jpg': ('Knee & Ankle', (18, 96, 91)),
    'shoulder.jpg': ('Shoulder & Elbow', (111, 71, 24)),
    'neurological.jpg': ('Neurological Care', (80, 52, 120)),
    'sports.jpg': ('Sports Injury', (144, 72, 36)),
    'post-operative.jpg': ('Post Operative', (41, 89, 124)),
    'womens-health.jpg': ("Women's Health", (150, 78, 110)),
    'posture.jpg': ('Posture & Ergonomics', (86, 112, 55)),
    'geriatric.jpg': ('Geriatric Care', (90, 90, 110)),
    'paediatric.jpg': ('Paediatric Care', (35, 102, 110)),
    'home-physio.jpg': ('Home Physiotherapy', (45, 86, 80)),
    'image.png': ('Physio Whitefield', (24, 90, 120)),
}

for name, (label, base) in items.items():
    img = Image.new('RGB', (900, 600), base)
    draw = ImageDraw.Draw(img)

    for i in range(12):
        x = (i * 71) % 900
        y = (i * 97) % 600
        color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((i / 12) % 1, 0.55, 0.9))
        overlay = Image.new('RGBA', (900, 600), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.ellipse((x - 120, y - 120, x + 120, y + 120), fill=(color[0], color[1], color[2], 80))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    draw.rectangle((0, 430, 900, 600), fill=(0, 0, 0, 70))

    try:
        font = ImageFont.truetype('arial.ttf', 52)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    w = bbox[2] - bbox[0]
    x = (900 - w) / 2
    y = 470
    draw.text((x + 2, y + 2), label, font=font, fill=(20, 20, 20))
    draw.text((x, y), label, font=font, fill=(255, 255, 255))

    out = folder / name
    if name.endswith('.png'):
        img.save(out)
    else:
        img.save(out, quality=90)

print(f'created {len(items)} images in {folder}')
