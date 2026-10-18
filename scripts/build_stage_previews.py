#!/usr/bin/env python3
"""Redraw the stage-select preview pictures as wax crayon drawings at 4x.

Each preview is a 384x256 8-bit texture. The picture is the top 224 rows, with
rounded transparent corners; the 32 rows below it are never drawn. The picture
is upscaled with the same model and alpha handling as scripts/upscale.py, then
restyled: colour flattened with a generalized Kuwahara filter, laid down as
waxy hatching that leaves the paper's tooth showing, cross-hatched in the
shadows, with a soft broken outline. The noise is seeded, so reruns give the
same images. The unused rows are enlarged with Lanczos.

    python -I scripts/build_stage_previews.py --model 4x_HDCube_200k.pth \\
      --dump DUMP [--dump DUMP...] -o pack

Run it after the general upscale script; it replaces the 22 preview images.
"""
import argparse
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upscale  # noqa: E402

SCALE = 4
PICTURE_ROWS = 224
# The preview of each of the 22 stages in the select screen, by hash.
PREVIEWS = (
    "0009bf2d67f49b3d53894a2109ec1567", "059cfc9421d4ef334be7783120b6d837",
    "0f75c2c417514bda0f5b1df9186d56d7", "0fb2cfab2f803f034df488d4ab94f1d3",
    "154afc4cfe8bb92df166ec57e93049da", "36f67592d3e597bc9c36fc5556d391ea",
    "4765fd81ac8d4edbfe347078a4043dc0", "4c7cf552171d14c0ab0d03c10f960029",
    "6e3ddc846bdc7cb64aeb1f4fe8664304", "7d40f82c169652dcb07f84ff8e700efb",
    "7f49007e5ef0f48806de4a06158a51ef", "8e37d1f68aff7603b0d1681fd2c8fd58",
    "990d7af36bfd4e7f39e8a14332dbe885", "9b615f3487edee1d5e5d389d1bb44b19",
    "abf60af8163368d494bed7ed104fc806", "c5a88d3ffa45559ec29496625ab31e58",
    "c5bb78ebabd75ec287818faf7ee6a2e2", "c80993ef11f912f7148c1324d0ab06a6",
    "d6eaa58198fbb334d199948e8a5e4848", "e2b2d473b345b0c3b6b7ef36917c67e9",
    "ef2bae43a6e2984ad93df2e1913ea266", "f2a7979e73efe57ac4d83839e57caa04",
)


class Crayon:
    def __init__(self, device):
        self.device = device

    def tensor(self, rgb):
        return torch.from_numpy(np.ascontiguousarray(rgb)).permute(2, 0, 1).unsqueeze(0).float().to(self.device)

    def blur(self, x, sigma):
        r = int(sigma * 3)
        k = torch.exp(-torch.arange(-r, r + 1, dtype=torch.float32) ** 2 / (2 * sigma * sigma))
        k = (k / k.sum()).to(self.device)
        c = x.shape[1]
        x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="reflect"), k.view(1, 1, 1, -1).repeat(c, 1, 1, 1), groups=c)
        return F.conv2d(F.pad(x, (0, 0, r, r), mode="reflect"), k.view(1, 1, -1, 1).repeat(c, 1, 1, 1), groups=c)

    @staticmethod
    def luma(x):
        return 0.299 * x[:, 0:1] + 0.587 * x[:, 1:2] + 0.114 * x[:, 2:3]

    def edges(self, x, sigma):
        g = F.pad(self.blur(self.luma(x), sigma), (1, 1, 1, 1), mode="reflect")
        kx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device=self.device).view(1, 1, 3, 3)
        gx, gy = F.conv2d(g, kx), F.conv2d(g, kx.transpose(2, 3))
        return torch.sqrt(gx * gx + gy * gy)

    def kuwahara(self, x, radius, sectors=8, q=8.0):
        """Generalized (Papari) Kuwahara: the mean of the least varied of
        `sectors` overlapping Gaussian-weighted wedges around each pixel."""
        r = radius
        ys, xs = torch.meshgrid(torch.arange(-r, r + 1, dtype=torch.float32),
                                torch.arange(-r, r + 1, dtype=torch.float32), indexing="ij")
        dist, angle = torch.sqrt(xs ** 2 + ys ** 2), torch.atan2(ys, xs)
        gauss = torch.exp(-dist ** 2 / (2 * (r / 2.0) ** 2)) * (dist <= r)
        kernels = []
        for k in range(sectors):
            d = torch.remainder(angle - 2 * math.pi * k / sectors + math.pi, 2 * math.pi) - math.pi
            w = torch.exp(-d ** 2 / (2 * (math.pi / sectors) ** 2)) * gauss
            w[r, r] = gauss[r, r] / sectors
            kernels.append(w / w.sum())
        kernel = torch.stack(kernels).unsqueeze(1).to(self.device)
        channels = F.pad(x, (r, r, r, r), mode="reflect").permute(1, 0, 2, 3)
        mean = F.conv2d(channels, kernel)
        var = (F.conv2d(channels * channels, kernel) - mean * mean).clamp(min=0).sum(0, keepdim=True)
        weight = 1.0 / (1e-4 + torch.sqrt(var)) ** q
        return ((mean * weight).sum(1) / weight.sum(1)).unsqueeze(0)

    def strokes(self, h, w, length, degrees, seed):
        """Unit-variance noise streaked along `degrees`."""
        a = torch.from_numpy(np.random.default_rng(seed).standard_normal((1, 1, h, w)).astype(np.float32)).to(self.device)
        r = length // 2
        ys, xs = torch.meshgrid(torch.arange(-r, r + 1, dtype=torch.float32),
                                torch.arange(-r, r + 1, dtype=torch.float32), indexing="ij")
        c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
        along, across = xs * c + ys * s, -xs * s + ys * c
        k = torch.exp(-across ** 2 / (2 * 0.9 ** 2)) * torch.exp(-along ** 2 / (2 * (r * 0.6) ** 2))
        k = (k / k.sum()).view(1, 1, 2 * r + 1, 2 * r + 1).to(self.device)
        a = F.conv2d(F.pad(a, (r, r, r, r), mode="reflect"), k)
        return a / a.std()

    def tooth(self, h, w, seed):
        """The paper's grain: fine and coarse noise, unit variance."""
        rng = np.random.default_rng(seed)
        planes = [torch.from_numpy(rng.standard_normal((1, 1, h, w)).astype(np.float32)).to(self.device) for _ in range(2)]
        fine, coarse = self.blur(planes[0], 1.0), self.blur(planes[1], 2.5)
        x = fine / fine.std() * 0.7 + coarse / coarse.std() * 0.3
        return x / x.std()

    def __call__(self, rgb):
        """rgb: float32 HxWx3 in 0..1, already upscaled."""
        src = self.tensor(rgb)
        x = self.kuwahara(src, 6)
        h, w = x.shape[2:]
        grey = self.luma(x)
        x = (grey + (x - grey) * 1.25).clamp(0, 1)
        # One dominant hatching angle; a second crosses it in the shadows.
        s1 = self.strokes(h, w, 41, -62, 1062)
        s2 = self.strokes(h, w, 35, 25, 1025)
        tooth = self.tooth(h, w, 11)
        pressure = 0.45 + 0.55 * (1 - self.luma(x))
        cover1 = torch.sigmoid((pressure + 0.12 * tooth + 0.26 * s1 - 0.22) * 9.0)
        cover2 = torch.sigmoid((pressure + 0.12 * tooth + 0.26 * s2 - 0.70) * 9.0)
        cover = 1 - (1 - cover1) * (1 - cover2)
        # Gaps show off-white paper, tinted a little by the wax around them.
        paper = 0.6 * torch.tensor([0.98, 0.97, 0.94], device=self.device).view(1, 3, 1, 1)
        paper = paper + 0.4 * (1 - (1 - self.blur(x, 10)) * 0.5)
        wax = x * (1 - 0.12 * cover1 * cover2)  # overlapping strokes build up
        out = paper * (1 - cover) + wax * cover
        out = out * (1 + 0.04 * s1.clamp(-2, 2))
        line = torch.sigmoid((self.edges(src, 2.0) - 0.2) * 22) * torch.sigmoid((tooth + 0.6) * 4)
        out = out * (1 - 0.55 * line)
        return out.squeeze(0).permute(1, 2, 0).cpu().numpy().clip(0, 1)


def build(path, upscaler, crayon):
    rgba = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
    height, width, _ = rgba.shape
    if (width, height) != (384, 256):
        raise SystemExit(f"{path}: expected 384x256, found {width}x{height}")
    picture = np.ascontiguousarray(rgba[:PICTURE_ROWS])
    stored = np.ascontiguousarray(picture[:, :, :3])
    alpha_plane = picture[:, :, 3]
    visible = alpha_plane > 0.0
    # Like upscale.py: hidden texels keep their stored colour, the rounded
    # corners stay a hard cut-out shaped by the model's upscale of the alpha.
    hidden_colour = upscale.enlarge(stored, SCALE, upscaler, True)
    drawn = crayon(upscale.enlarge(upscale.fill_hidden(stored, visible), SCALE, upscaler, True))
    grey = upscale.enlarge(np.repeat(alpha_plane[:, :, None], 3, axis=2), SCALE, upscaler, True).mean(axis=2)
    alpha = (grey >= 0.5).astype(np.float32)
    top = np.dstack([np.where(alpha[:, :, None] > 0, drawn, hidden_colour), alpha])
    unused = Image.fromarray((rgba[PICTURE_ROWS:] * 255.0 + 0.5).astype(np.uint8), "RGBA")
    unused = unused.resize((width * SCALE, (height - PICTURE_ROWS) * SCALE), Image.LANCZOS)
    out = np.concatenate([(top * 255.0 + 0.5).clip(0, 255).astype(np.uint8), np.asarray(unused)], axis=0)
    return Image.fromarray(out, "RGBA")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True, help="the upscale model (4x_HDCube_200k.pth)")
    parser.add_argument("--dump", type=Path, action="append", required=True, help="a --dump-textures directory")
    parser.add_argument("-o", "--output", type=Path, required=True, help="the pack directory")
    parser.add_argument("--only", nargs="*", help="only these hashes")
    args = parser.parse_args()

    upscaler = upscale.Upscaler(args.model)
    if upscaler.scale != SCALE:
        raise SystemExit(f"{args.model}: a {SCALE}x model is needed, this one is {upscaler.scale}x")
    crayon = Crayon(upscaler.device)
    args.output.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in args.only or PREVIEWS:
        path = next((d / f"{name}.png" for d in args.dump if (d / f"{name}.png").is_file()), None)
        if path is None:
            missing.append(name)
            continue
        build(path, upscaler, crayon).save(args.output / f"{name}.png", optimize=True)
        print(name)
    if missing:
        print(f"not in any dump: {' '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
