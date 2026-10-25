# SaruSaru Daisakusen: unofficial HD texture pack

A ready-made HD texture pack for the [SaruSaru recompilation](https://github.com/jackgllghr/bigmission-recomp)
of **Saru! Get You! SaruSaru Daisakusen** (UCJS10060, version 1.00). It covers
the menus, icons, backgrounds and game textures.

**This is an unofficial fan pack.** It is not affiliated with, endorsed by, or
sponsored by Sony Interactive Entertainment, which owns the game and its
artwork.

This repository is kept apart from the recompilation on purpose. The port
itself ships no game assets. Players opt in from the launcher: choosing
**Textures → HD (4×)**, or the **Modern** preset, downloads the pack published
here. The pack is upscaled game artwork, so it lives here rather than in the
port. A takedown of this repository leaves the port and the
[English translation](https://github.com/jackgllghr/sarusaru-translations)
untouched.

## Current pack

**v1** (103 textures, about 41 MB) covers the boot screens, the autosave
notice, the title and main menu in English and Japanese, name entry, the font
atlases, the start of stage 1-1 (HUD, tutorial dialogue, beach scenery) and
the title backdrop. Everything else is drawn as the original until later packs
add it.

It was upscaled with **[4x-HDCube](https://openmodeldb.info/models/4x-HDCube)**
by Venomalia (ESRGAN, CC0-1.0), an ESRGAN model trained on GameCube and Wii
textures, the same era and style as this game. HDCube was chosen over
Real-ESRGAN x4plus and x4plus-anime-6B (BSD-3-Clause) after comparing the
three on this game's textures:

- It keeps surface detail such as sand grain and brickwork. The anime model
  flattens that detail into flat colour, and x4plus smooths it away.
- It gives the cleanest kanji in the font atlases, where both Real-ESRGAN
  models invent strokes.
- Its CC0 licence puts no conditions on the images it makes. 4x-UltraSharp
  and 4x-AnimeSharp, the other common choices, are CC-BY-NC-SA.

## What the pack is

A zip of one HD pack directory, in the format the recompilation's renderer
loads (`profiles/sarusaru/host/textures/hd_pack.hpp`):

```
sarusaru-hd-4x/
  pack.ini        format = 1
                  disc = UCJS10060
                  scale = 4
  <hash>.png      one image per texture
```

- **`<hash>`** is the texture's identity: the first 32 hex digits of a SHA-256
  over the decoded pixels the game draws. It does not depend on where the
  texture lives on the disc.
- **Each PNG** is the texture's logical rectangle at `scale` times its size. It
  is straight (unpremultiplied) RGBA, and keeps the colour of fully
  transparent texels, because some textures are drawn with their alpha
  ignored.
- **Menus and icons** with Japanese lettering are matched after the English
  pack has replaced its regions. Translated menus therefore need their own
  images, under the hashes of the translated textures.
- **Missing textures:** any texture the pack doesn't cover is drawn as the
  original. An image that is unreadable or the wrong size is reported once
  and falls back to the original.

The full format, and how textures are identified, is in the recompilation's
[`docs/hd-textures.md`](https://github.com/jackgllghr/bigmission-recomp/blob/main/profiles/sarusaru/docs/hd-textures.md).

## How the launcher installs it

1. It downloads the zip pinned in the build (`SARUSARU_HD_PACK_URL`) with curl.
2. It keeps the zip only if its SHA-256 matches `SARUSARU_HD_PACK_SHA256`. The
   size, `_SIZE`, is used for the progress bar.
3. It unpacks the zip with the system's own tools: tar on Windows and macOS,
   and unzip, bsdtar or Python on Linux.
4. It checks that `pack.ini` (at the top of the zip, or in its only folder)
   names the player's disc.
5. It installs the pack whole into `<user data>/textures/4x-prebuilt-<sha16>/`
   and selects it. A refused or cancelled download leaves nothing behind.

## Making the pack

The images are made from the maintainer's own copy of the game. Neither the
disc nor the intermediate dumps are published.

1. **Collect textures.** Play with texture dumping on. This writes one PNG per
   texture the renderer decodes, plus `textures.tsv`. Running it again into
   the same directory adds only new textures, so a play-through can be
   collected over many sessions.

   ```sh
   cd ../bigmission-recomp
   out/macos-arm64/bin/sarusaru --dump-textures ~/sarusaru-dump '/path/to/game.iso'
   ```

   Movies are uploaded as textures too, so a dump also fills with 512×512
   32-bit movie frames, about 1 MB each. Delete them as they appear on a
   nearly full disk; the upscale script leaves them out anyway.

2. **Upscale** with `scripts/upscale.py`. It runs any model
   [spandrel](https://github.com/chaiNNer-org/spandrel) loads, on the Apple
   GPU, CUDA or the CPU:

   ```sh
   python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
   curl -LO https://raw.githubusercontent.com/Venomalia/HDcube/main/v1/4x_HDCube_200k.pth
   .venv/bin/python -I scripts/upscale.py --model 4x_HDCube_200k.pth \
     --dump ~/sarusaru-dump [--dump ...] -o pack
   ```

   - **Planes:** colour and alpha are upscaled as separate straight planes,
     with 8 texels of clamped padding that is cropped afterwards.
   - **Visible texels** take their colour from a second upscale in which
     hidden texels are filled from their neighbours, so cut-outs and atlases
     don't get fringes. Hidden texels keep their stored colour, for textures
     drawn with alpha off.
   - **Small textures** (under 16 texels on a side) use Lanczos instead of the
     model.
   - **Left out:** text drawn at runtime (256×64 4-bit), movie frames, and
     any hashes listed in `--skip`.
   - **Reruns:** textures already in `pack/` are skipped, so the script can be
     rerun as the dumps grow. It takes a few seconds per texture on an
     Apple M4.

3. **Check it in the game** before publishing:

   ```sh
   out/macos-arm64/bin/sarusaru --texture-pack ../sarusaru-hd-textures/pack '/path/to/game.iso'
   ```

4. **Package it.** This zips only `pack.ini` and the hash-named PNGs (stored,
   since PNGs are already compressed). It leaves out `wanted.txt`,
   `collected/` and anything else, and prints the build flags:

   ```sh
   python3 profiles/sarusaru/tools/package_hd_pack.py ../sarusaru-hd-textures/pack \
     -o ../sarusaru-hd-textures/sarusaru-hd-4x.zip
   ```

`pack/` and `*.zip` are ignored by git. Images are published only as release
assets, never committed.

### Aiming reticles

`scripts/build_aiming_reticles.py` renders the geometric aiming marks directly
at 4× resolution: the free-aim crosshair and circle, the enemy-targeted radial
ticks, and their red and white center crosses. Vector geometry keeps the thin
lines and circular edge smooth while preserving the original texel positions,
transparent background, and straight RGB beneath transparent pixels.

```sh
pip install Pillow CairoSVG
python3 scripts/build_aiming_reticles.py -o pack
```

Run this after the general upscale script, then package and verify the pack as
above. It replaces only the four hash-named aiming textures. These changes do
not update the published release or the launcher's pinned download.

The top-left banana life counter uses atlas
`a1fa91a72377409220d8751999d06040` (96×64). Its full, partly depleted, and empty
banana icons are upscaled together to 384×256 with the normal HDCube pipeline:

```sh
python3 scripts/upscale.py --model /path/to/4x_HDCube_200k.pth \
  --dump /path/to/gameplay-dump -o pack --only a1fa91a72377409220d8751999d06040
```

The atlas also retains its other HUD regions and transparent texels.

### Save-screen cursor and slot buttons

`scripts/build_save_ui.py` draws the glove cursor and the four numbered save
buttons at 4× using vector outlines and the game's M PLUS Rounded 1c Bold
face. The original 32×24 cursor silhouette, 32×32 button cells and texture
padding extents remain fixed. Both observed slot-atlas identities are included.

```sh
python3 scripts/build_save_ui.py -o pack
```

This requires Pillow, CairoSVG and the sibling `bigmission-recomp` checkout
for the font (or an explicit `--font` path). Run it after general upscaling,
then package the pack as above. The generated PNGs remain local release
artifacts, like the other HD textures.

### Stage-select previews

`scripts/build_stage_previews.py` redraws the 22 stage preview pictures on the
stage-select screen as wax crayon drawings. Each preview is a 384×256 8-bit
texture: the picture is the top 224 rows, with rounded transparent corners,
and the rows below it are never drawn. The script upscales the picture with
HDCube, using the same alpha handling as `upscale.py`, then restyles it. A
Kuwahara filter flattens the colour into waxy hatching that lets the paper
grain show through, with cross-hatching in the shadows and a soft, broken
outline. The noise is seeded, so reruns produce identical images.

Collect the previews by paging through every stage on the stage-select screen
with texture dumping on. Then:

```sh
python3 -I scripts/build_stage_previews.py --model /path/to/4x_HDCube_200k.pth \
  --dump /path/to/stage-select-dump -o pack
```

Run it after the general upscale script; it replaces the 22 hash-named
previews and reports any that are missing from the dumps.

### Smaller packs (2× and 3×)

The recompilation's **Modern Low** preset renders at 2× (960×544) for phones
and other low-power devices, and downloads a 3× pack; the Textures row also
offers 2×. Both are the finished 4× pack resized, so they keep everything in
it, the hand-drawn textures included:

```sh
python3 -I scripts/downscale_pack.py pack --scale 3 -o pack-3x
python3 -I scripts/downscale_pack.py pack --scale 2 -o pack-2x
```

Colour and alpha are resized as separate straight planes with Lanczos.
Visible texels take an alpha-weighted colour, so hidden colour doesn't fringe
cut-outs; texels left fully transparent keep their own colour, for textures
drawn with alpha off. Only Pillow is needed. Package each as above, as
`sarusaru-hd-3x.zip` and `sarusaru-hd-2x.zip`, and pin them as
`SARUSARU_HD3_PACK_*` and `SARUSARU_HD2_PACK_*`.

## Publishing

Publish the zip as a release tagged `hd-<date or version>`:

```sh
gh release create hd-2026-10-16 sarusaru-hd-4x.zip --title "HD textures 2026-10-16" \
  --notes "-DSARUSARU_HD_PACK_SHA256=<sha256> -DSARUSARU_HD_PACK_SIZE=<bytes>"
```

GitHub limits a release asset to 2 GiB. The launcher pins the pack's URL,
SHA-256 and size when it is built. After publishing, set the printed values
as the `SARUSARU_HD_PACK_*` defaults in the recompilation's
`profiles/sarusaru/CMakeLists.txt`:

```sh
-DSARUSARU_HD_PACK_URL=https://github.com/jackgllghr/sarusaru-hd-textures/releases/download/<tag>/sarusaru-hd-4x.zip
-DSARUSARU_HD_PACK_SHA256=<sha256> -DSARUSARU_HD_PACK_SIZE=<bytes>
```

Publishing a new pack means a new release and new values. A launcher keeps
the pack it already has until a build pins a different hash.

## Licence

No licence is granted. The pack is derived from artwork owned by Sony
Interactive Entertainment. It is offered as an unofficial fan pack for players
who own the game, and will be withdrawn on request from the rights holder.
