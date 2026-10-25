#!/usr/bin/env python3
"""Make a smaller HD pack (2x or 3x) from a finished 4x pack.

For devices that render the game at 2x (960x544), where 4x textures cost
memory and bandwidth for detail that never reaches the screen. The images are
the 4x pack's, resized, so the smaller packs keep everything the 4x pack has
(the hand-drawn reticles, save buttons and stage previews included):

    python -I scripts/downscale_pack.py pack --scale 3 -o pack-3x
    python -I scripts/downscale_pack.py pack --scale 2 -o pack-2x

The same rules as upscale.py:

- Colour and alpha are resized as separate straight planes (Lanczos), so the
  colour under transparent texels is kept (some textures are drawn with alpha
  off).
- Visible texels take their colour from an alpha-weighted resize, so hidden
  colour does not fringe the edges of cut-outs and atlases. Texels that end
  up fully transparent keep the straight resize's colour.

Each image becomes the texture's logical rectangle at the new scale: its 4x
size divided by 4 and multiplied by SCALE, which is exact for every texture
(their sizes are whole texels). pack.ini is rewritten with the new scale.
"""
import argparse
from pathlib import Path
import re
import sys

from PIL import Image

HASH = re.compile(r"^[0-9a-f]{32}$")


def read_manifest(pack):
    text = (pack / "pack.ini").read_text(encoding="utf-8")
    values = dict(re.findall(r"^\s*(\w+)\s*=\s*(\S+)\s*$", text, re.MULTILINE))
    if values.get("format") != "1" or "disc" not in values or "scale" not in values:
        sys.exit(f"downscale_pack: {pack}/pack.ini is not a format 1 pack")
    return values["disc"], int(values["scale"])


def resize(image, size):
    """Straight RGBA resize: alpha-weighted colour where visible, straight colour where hidden."""
    image = image.convert("RGBA")
    alpha = image.getchannel("A").resize(size, Image.Resampling.LANCZOS)
    straight = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    # Pillow's premultiplied mode: resized, then divided back by the new alpha.
    weighted = image.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA").convert("RGB")
    visible = alpha.point(lambda value: 255 if value > 0 else 0)
    colour = Image.composite(weighted, straight, visible)
    result = colour.convert("RGBA")
    result.putalpha(alpha)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pack", type=Path, help="A finished pack directory (pack.ini and <hash>.png)")
    parser.add_argument("--scale", type=int, required=True, choices=(2, 3), help="The new pack's scale")
    parser.add_argument("-o", "--output", type=Path, required=True, help="The new pack's directory")
    args = parser.parse_args()

    disc, source_scale = read_manifest(args.pack)
    if args.scale >= source_scale:
        sys.exit(f"downscale_pack: the source pack is {source_scale}x; the new one must be smaller")
    args.output.mkdir(parents=True, exist_ok=True)
    images = sorted(path for path in args.pack.glob("*.png") if HASH.match(path.stem))
    for path in images:
        with Image.open(path) as image:
            width, height = image.size
            if width % source_scale or height % source_scale:
                sys.exit(f"downscale_pack: {path.name} is {width}x{height}, not a multiple of {source_scale}")
            size = (width // source_scale * args.scale, height // source_scale * args.scale)
            resize(image, size).save(args.output / path.name, optimize=True)
    (args.output / "pack.ini").write_text(
        "# SaruSaru HD textures, resized from the "
        f"{source_scale}x pack.\nformat = 1\ndisc = {disc}\nscale = {args.scale}\n", encoding="utf-8")
    print(f"{len(images)} textures at {args.scale}x in {args.output}")


if __name__ == "__main__":
    main()
