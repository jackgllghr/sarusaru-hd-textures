#!/usr/bin/env python3
"""Render the save-screen glove cursor and slot buttons from vector geometry.

Requires Pillow and CairoSVG. Identities and extents are from UCJS10060
guest draws. No extracted game artwork is needed or written by this script.
"""
import argparse
import io
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont


CURSOR = 'a23c6eed1fb1ba911a845ddf15fb6dc6'
# The same 32x192 slot artwork occurs with two different unused padding tails.
SLOTS = ('2c39d42fc90516bd8d3b7b4f94641b3f', '99e9692c652d992e5a7bc0e046339114')


def svg_image(body, width, height, scale):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'width="{width * scale}" height="{height * scale}">{body}</svg>')
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode()))).convert('RGBA')


def cursor(scale):
    # The pointing finger, folded fingers and cuff follow the native 32x24
    # silhouette; the remaining eight rows are unused transparent padding.
    body = '''
      <defs><linearGradient id="glove" x2="0" y2="1">
        <stop stop-color="#ffffff"/><stop offset="1" stop-color="#e0e5ee"/>
      </linearGradient></defs>
      <path d="M3 18 C0 16 1 11 3 8 C5 5 8 4 11 5 L15 7
        C17 6 18 4 19 2 C20 -0.2 22 -0.4 23 1 C25 3 23 6 21 8
        L17 13 C19 12 22 12 23 14 C25 17 22 18 19 18
        C16 22 11 23 7 22 C5 21 4 20 3 18 Z"
        fill="url(#glove)" stroke="#30375f" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M3 17 C5 21 10 22 14 20 M3.5 16.5 C5 18.5 7 19.5 10 19.5"
        fill="none" stroke="#8b9cac" stroke-width="1" stroke-linecap="round"/>
      <path d="M4 17 C5 19 7 20 10 20" fill="none" stroke="white" stroke-width=".8"/>
    '''
    return svg_image(body, 32, 32, scale)


def slots(scale, font_path):
    body = '''<defs><linearGradient id="rim" x2="0" y2="1">
      <stop stop-color="white"/><stop offset="1" stop-color="#c2cdd8"/>
      </linearGradient></defs>'''
    for index in range(4):
        y = index * 32
        body += f'''<rect x="1" y="{y + 1}" width="30" height="30" rx="6.8"
          fill="#2c334b" stroke="#8799a5" stroke-width="1.3"/>
          <rect x="2.2" y="{y + 2.2}" width="27.6" height="27.6" rx="5.5"
          fill="none" stroke="url(#rim)" stroke-width="1.6"/>'''
    image = svg_image(body, 32, 256, scale)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 23 * scale)
    for index in range(4):
        text = str(index + 1)
        box = draw.textbbox((0, 0), text, font=font)
        x = (32 * scale - box[2] + box[0]) / 2 - box[0]
        y = (index * 32 + 16) * scale - (box[3] - box[1]) / 2 - box[1]
        draw.text((x + .6 * scale, y + .6 * scale), text, font=font,
                  fill='#aab9c9', stroke_width=max(1, scale // 3), stroke_fill='#182348')
        draw.text((x, y), text, font=font, fill='#ffffff')
    return image


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-o', '--output', type=Path, default=root / 'pack')
    parser.add_argument('--font', type=Path, default=root.parent / 'bigmission-recomp' /
                        'profiles/sarusaru/tools/fonts/MPLUSRounded1c-Bold-ASCII.ttf')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    images = {CURSOR: cursor(4), **dict.fromkeys(SLOTS, slots(4, args.font))}
    for identity, image in images.items():
        image.save(args.output / f'{identity}.png')
        print(f'{identity}: {image.width}x{image.height}')


if __name__ == '__main__':
    main()
