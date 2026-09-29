#!/usr/bin/env python3
r"""
生成站点图标 Image/favicon.jpg。

想换图标就改下面的 BG / TEXT，然后跑：
    .\.venv\Scripts\python.exe make_favicon.py
    .\.venv\Scripts\python.exe make_favicon.py --text 记 --bg "#b1743e"

需要 Pillow：.\.venv\Scripts\python.exe -m pip install Pillow
"""

import argparse

BG_DEFAULT = "#b1743e"   # 站点主色调，跟 Homepage.html 里的 --accent 一致
FG_DEFAULT = "#fdfbf7"   # 米白
TEXT_DEFAULT = "日"


def main():
    ap = argparse.ArgumentParser(description="生成 Image/favicon.jpg")
    ap.add_argument("--text", "-t", default=TEXT_DEFAULT, help="图标上的文字（一两个字）")
    ap.add_argument("--bg", default=BG_DEFAULT, help="背景色")
    ap.add_argument("--fg", default=FG_DEFAULT, help="文字色")
    ap.add_argument("--size", "-s", type=int, default=256, help="尺寸，默认 256")
    args = ap.parse_args()

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("❌ 需要 Pillow：.\\.venv\\Scripts\\python.exe -m pip install Pillow")
        return

    from pathlib import Path
    size = args.size
    img = Image.new("RGB", (size, size), args.bg)
    d = ImageDraw.Draw(img)

    font = None
    for p in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            font = ImageFont.truetype(p, int(size * 0.58))
            break
        except Exception:
            continue

    if font:
        bbox = d.textbbox((0, 0), args.text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), args.text, font=font, fill=args.fg)
    else:
        d.ellipse([size * 0.24] * 2 + [size * 0.76] * 2, outline=args.fg, width=int(size * 0.055))

    out = Path(__file__).resolve().parent / "Image" / "favicon.jpg"
    img.save(out, "JPEG", quality=92)
    print(f"✅ 已生成 {out}")
    print("   记得重新构建发布：控制台.bat → 7")


if __name__ == "__main__":
    main()
