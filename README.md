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

2. **Upscale.** Write `<hash>.png` at 4× for each texture into `pack/`, along
   with `pack.ini` as above. Any upscaler works, as long as it handles colour
   and alpha as separate straight planes. Alternatively, let the launcher make
   a pack on the device from a recipe (`tools/build_texture_recipe.py`), then
   copy its directory. Leave out text the game draws at runtime: those 256×64
   4-bit textures change from frame to frame.

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
