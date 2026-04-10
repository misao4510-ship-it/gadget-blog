#!/usr/bin/env python3
"""Remove backgrounds from sakura chibi images using rembg"""

import os
from rembg import remove
from PIL import Image

OUTPUT_DIR = "/home/misao/gadget-blog/output_sd"

for i in range(1, 11):
    src = os.path.join(OUTPUT_DIR, f"sakura_chibi_{i:02d}.png")
    dst = os.path.join(OUTPUT_DIR, f"sakura_chibi_{i:02d}_nobg.png")
    if not os.path.exists(src):
        print(f"MISSING: {src}")
        continue
    print(f"Processing {i:02d}/10: {os.path.basename(src)}...")
    with open(src, "rb") as f:
        img_data = f.read()
    result = remove(img_data)
    with open(dst, "wb") as f:
        f.write(result)
    print(f"  Saved: {dst}")

print("Background removal complete.")
