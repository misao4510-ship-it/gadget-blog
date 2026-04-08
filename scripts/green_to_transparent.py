#!/usr/bin/env python3
"""緑背景除去（クロマキー方式）"""
from PIL import Image
import numpy as np
import sys


def remove_green(input_path, output_path, tolerance=60):
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    # 緑優位ピクセルを透過: g > r+tolerance かつ g > b+tolerance
    green_mask = (g.astype(int) > r.astype(int) + tolerance) & \
                 (g.astype(int) > b.astype(int) + tolerance)
    data[:,:,3] = np.where(green_mask, 0, a)
    Image.fromarray(data).save(output_path)
    print(f"Saved: {output_path}")
    green_pixels = int(green_mask.sum())
    total_pixels = green_mask.size
    print(f"Removed {green_pixels}/{total_pixels} pixels ({100*green_pixels/total_pixels:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 green_to_transparent.py input.png output.png [tolerance]")
        sys.exit(1)
    remove_green(sys.argv[1], sys.argv[2],
                 int(sys.argv[3]) if len(sys.argv) > 3 else 60)
