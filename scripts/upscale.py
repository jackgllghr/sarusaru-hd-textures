#!/usr/bin/env python3
"""Upscale texture dumps into an HD pack directory.

Reads one or more texture dumps (sarusaru --dump-textures DIR: <hash>.png and
textures.tsv) and writes the pack the renderer loads: pack.ini and
<hash>.png at SCALE times each texture's size.

The same rules as the launcher's on-device packs (the recompilation's
docs/hd-textures.md):

- Colour and alpha are upscaled as separate straight planes, so the colour
  under transparent texels is kept (some textures are drawn with alpha off).
  Visible texels take their colour from a second upscale in which hidden
  texels are filled from their visible neighbours, so hidden colour does not
  fringe the edges of cut-outs and atlases.
- Each texture is padded before upscaling and cropped after, so the model
  sees past the edge (clamped), then finished with nearest-neighbour if the
  model's own scale is below SCALE.
- Left out: text the game draws at runtime (256x64 4-bit), movie frames
  (512x512 32-bit), and anything in --skip.
- Textures smaller than --min-size on a side are enlarged with Lanczos rather
  than the model, which smears tiny icons.

Runs any model spandrel loads (OpenModelDB .pth/.safetensors) on the Apple
GPU (MPS), CUDA or the CPU:

    python -I scripts/upscale.py --model 4x_HDCube_200k.pth --dump DUMP [--dump DUMP...] -o pack

Textures already in the output are skipped, so it can be rerun as dumps grow.
"""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import spandrel
import torch

PAD = 8  # texels of border the model sees around each texture, then cropped
TILE = 192  # input tile size, to bound GPU memory on large textures
OVERLAP = 16


def skipped_kind(row):
    width, height, fmt = int(row["width"]), int(row["height"]), int(row["format"])
    if (width, height, fmt) == (256, 64, 4):
        return "runtime text"
    if fmt == 3 and width == 512 and height == 512:
        return "movie frame"
    return None


def read_dumps(directories):
    textures = {}
    for directory in directories:
        with open(directory / "textures.tsv", newline="") as table:
            for row in csv.DictReader(table, delimiter="\t"):
                path = directory / f"{row['hash']}.png"
                if path.is_file():
                    textures.setdefault(row["hash"], (path, row))
    return textures


def device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class Upscaler:
    def __init__(self, model_path):
        self.device = device()
        self.model = spandrel.ModelLoader().load_from_file(model_path).eval().to(self.device)
        self.scale = self.model.scale

    @torch.inference_mode()
    def _run(self, rgb):
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(self.device)
        out = self.model(tensor).clamp(0.0, 1.0)
        return out.squeeze(0).permute(1, 2, 0).cpu().numpy()

    def upscale(self, rgb):
        """rgb: float32 HxWx3 in 0..1. Tiled with overlap for large images."""
        height, width, _ = rgb.shape
        if height <= TILE and width <= TILE:
            return self._run(rgb)
        s = self.scale
        out = np.zeros((height * s, width * s, 3), np.float32)
        step = TILE - 2 * OVERLAP
        for y in range(0, height, step):
            for x in range(0, width, step):
                y0, x0 = max(y - OVERLAP, 0), max(x - OVERLAP, 0)
                y1, x1 = min(y + step + OVERLAP, height), min(x + step + OVERLAP, width)
                tile = self._run(np.ascontiguousarray(rgb[y0:y1, x0:x1]))
                ty, tx = (y - y0) * s, (x - x0) * s
                h, w = (min(y + step, height) - y) * s, (min(x + step, width) - x) * s
                out[y * s:y * s + h, x * s:x * s + w] = tile[ty:ty + h, tx:tx + w]
        return out


def enlarge(plane, scale, upscaler, use_model):
    """plane: float32 HxWx3. Padded, upscaled to `scale`, cropped."""
    height, width, _ = plane.shape
    if not use_model:
        image = Image.fromarray((plane * 255.0 + 0.5).astype(np.uint8))
        image = image.resize((width * scale, height * scale), Image.LANCZOS)
        return np.asarray(image).astype(np.float32) / 255.0
    padded = np.pad(plane, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
    big = upscaler.upscale(padded)
    s = upscaler.scale
    big = big[PAD * s:(PAD + height) * s, PAD * s:(PAD + width) * s]
    if s != scale:
        factor = scale // s
        big = big.repeat(factor, axis=0).repeat(factor, axis=1)
    return big


def fill_hidden(colour, visible, passes=32):
    """`colour` with each texel where `visible` is false taken from its visible
    neighbours (spreading outwards), so the model does not smear hidden colour
    into the edges of what is drawn."""
    filled = colour.copy()
    known = visible.copy()
    for _ in range(passes):
        if known.all():
            break
        total = np.zeros_like(filled)
        count = np.zeros(known.shape, np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shifted_known = np.roll(known, (dy, dx), axis=(0, 1))
            total += np.roll(filled, (dy, dx), axis=(0, 1)) * shifted_known[:, :, None]
            count += shifted_known
        grow = ~known & (count > 0)
        filled[grow] = total[grow] / count[grow][:, None]
        known = known | grow
    return filled


def upscale_texture(path, scale, upscaler, min_size):
    rgba = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
    height, width, _ = rgba.shape
    use_model = min(width, height) >= min_size
    stored = np.ascontiguousarray(rgba[:, :, :3])
    colour = enlarge(stored, scale, upscaler, use_model)
    alpha_plane = rgba[:, :, 3]
    # Texels drawn with alpha take their colour from an upscale of the visible
    # colour only; hidden ones keep the stored colour (alpha may be ignored).
    if alpha_plane.min() < 1.0 and alpha_plane.max() > 0.0:
        visible = enlarge(fill_hidden(stored, alpha_plane > 0.0), scale, upscaler, use_model)
    if alpha_plane.min() >= 1.0:
        alpha = np.ones(colour.shape[:2], np.float32)
    elif ((alpha_plane == 0.0) | (alpha_plane == 1.0)).all():
        # Cut-outs keep hard edges: nearest, then smoothed by the colour's own detail.
        alpha = alpha_plane.repeat(scale, axis=0).repeat(scale, axis=1)
        if use_model:
            grey = enlarge(np.repeat(alpha_plane[:, :, None], 3, axis=2), scale, upscaler, True).mean(axis=2)
            alpha = (grey >= 0.5).astype(np.float32)
    else:
        alpha = enlarge(np.repeat(alpha_plane[:, :, None], 3, axis=2), scale, upscaler, use_model).mean(axis=2)
    if alpha_plane.min() < 1.0 and alpha_plane.max() > 0.0:
        colour = np.where((alpha > 0.0)[:, :, None], visible, colour)
    out = np.dstack([colour, alpha])
    return Image.fromarray((out * 255.0 + 0.5).clip(0, 255).astype(np.uint8), "RGBA")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True, help="a model spandrel loads (.pth, .safetensors)")
    parser.add_argument("--dump", type=Path, action="append", required=True, help="a --dump-textures directory")
    parser.add_argument("-o", "--output", type=Path, required=True, help="the pack directory")
    parser.add_argument("--scale", type=int, default=4, choices=range(2, 9))
    parser.add_argument("--disc", default="UCJS10060")
    parser.add_argument("--min-size", type=int, default=16, help="smaller sides use Lanczos instead of the model")
    parser.add_argument("--skip", type=Path, help="a file of hashes to leave out, one per line (# comments)")
    parser.add_argument("--only", nargs="*", help="only these hashes (for comparing models)")
    args = parser.parse_args()

    skip = set()
    if args.skip and args.skip.is_file():
        for line in args.skip.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                skip.add(line)
    textures = read_dumps(args.dump)
    work, left_out = [], {}
    for texture_hash, (path, row) in sorted(textures.items()):
        kind = "skip list" if texture_hash in skip else skipped_kind(row)
        if args.only is not None and texture_hash not in args.only:
            continue
        if kind:
            left_out[kind] = left_out.get(kind, 0) + 1
        elif not (args.output / f"{texture_hash}.png").is_file():
            work.append((texture_hash, path))
    print(f"{len(textures)} textures dumped; left out {left_out or 'none'}; {len(work)} to upscale", flush=True)

    args.output.mkdir(parents=True, exist_ok=True)
    upscaler = Upscaler(args.model)
    print(f"model {args.model.name}: {upscaler.model.architecture.name} {upscaler.scale}x on {upscaler.device}", flush=True)
    for index, (texture_hash, path) in enumerate(work, 1):
        image = upscale_texture(path, args.scale, upscaler, args.min_size)
        partial = args.output / f"{texture_hash}.png.partial"
        image.save(partial, format="PNG", compress_level=9)
        partial.replace(args.output / f"{texture_hash}.png")
        if index % 25 == 0 or index == len(work):
            print(f"{index}/{len(work)}", flush=True)
    (args.output / "pack.ini").write_text(
        f"# SaruSaru HD textures, upscaled with {args.model.name}.\nformat = 1\ndisc = {args.disc}\nscale = {args.scale}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
