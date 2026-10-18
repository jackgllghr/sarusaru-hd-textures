#!/usr/bin/env python3
"""Render the game's geometric aiming marks as antialiased 4x pack textures.

Requires Pillow and CairoSVG. The SVG geometry follows the source texel
coordinates observed in UCJS10060 texture dumps; no game dump is distributed.
Hash names match the decoded native textures. Keep straight RGB even under
transparent pixels, as required by the pack format.
"""
import argparse
import io
from pathlib import Path

import cairosvg
from PIL import Image


def rect(x, y, width, height):
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}"/>'


def free_aim():
    shapes = ['<circle cx="64" cy="64" r="7.5" fill="none" stroke="white" stroke-width="1"/>']
    # The arm, three dots, and their opposite retain the original spacing.
    for start, length in [(16, 18), (35, 1), (38, 1), (42, 1), (85, 1), (89, 1), (92, 1), (94, 18)]:
        shapes.extend([rect(63, start, 2, length), rect(start, 63, length, 2)])
    return ''.join(shapes)


def target_ring():
    shapes = []
    # Three ticks in each quadrant, with empty horizontal/vertical sectors.
    for rotation in (0, 90, 180, 270):
        for x1, y1, x2, y2 in [(96, 80, 105, 84.5), (88, 88, 95, 95), (80, 96, 84.5, 105)]:
            shapes.append(f'<path d="M{x1} {y1} L{x2} {y2}" transform="rotate({rotation} 64 64)" '
                          'fill="none" stroke="white" stroke-width="1.5"/>')
    return ''.join(shapes)


def cross():
    return ''.join(rect(*r) for r in [(15, 5, 2, 6), (5, 15, 6, 2), (21, 15, 6, 2), (15, 21, 2, 6)])


# Native identity, logical size, straight RGB, SVG geometry.
RETICLES = [
    ('c0b50f1a1a4d1a1bbbcc244dbabf742c', 128, (255, 255, 255), free_aim),
    ('e7b51d3c781a013dc6a4828fb7a277c7', 128, (255, 255, 255), target_ring),
    ('92075a9cdd5781dc0609a709fe9a2c12', 32, (225, 0, 8), cross),
    ('4cc58e8977e1d01e7b03152de3d29738', 32, (255, 255, 255), cross),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--output', type=Path, default=Path(__file__).resolve().parents[1] / 'pack')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for identity, size, rgb, geometry in RETICLES:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
               f'width="{size * 4}" height="{size * 4}"><g fill="white">{geometry()}</g></svg>')
        rendered = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert('RGBA')
        output = Image.new('RGBA', rendered.size, (*rgb, 0))
        output.putalpha(rendered.getchannel('A'))
        path = args.output / f'{identity}.png'
        output.save(path)
        print(f'{identity}: {size}x{size} -> {output.width}x{output.height}')


if __name__ == '__main__':
    main()
