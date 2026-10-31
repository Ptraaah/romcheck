# romcheck

**Is this the exact ROM your recomp project wants?**

The static recompilation wave — Zelda 64: Recompiled, the other N64Recomp
ports, the Harbour Masters PC ports, and their Android builds — has one
rule that trips everyone up: each project accepts **one specific dump** of
a game. One region, one revision. Hand it the wrong one and it refuses,
usually without telling you what you actually have.

romcheck tells you. One file, Python 3 standard library only.

```bash
python3 romcheck.py game.v64
```

```
file:     game.v64
format:   .v64 (byte order detected from header, not extension)
game:     ZELDA MAJORA'S MASK  [cartridge ZS]
region:   North America
revision: Rev 1
size:     33554432 bytes
md5:      9be74efa8d5f... (of the normalized big-endian image)
recomp / port projects this dump matches:
  - Zelda 64: Recompiled (Zelda64Recomp): documents its target as the US Rev 1 dump (mm.us.rev1.z64)
```

## What it does

- Detects the real byte order from the header magic — `.z64` big-endian,
  `.v64` byte-swapped, `.n64` little-endian — whatever the file is named.
  Reads ROMs straight out of a `.zip` too.
- Parses the header: internal name, cartridge id, region, revision.
- Computes MD5 / SHA1 / CRC32 of the **normalized big-endian** image —
  the values ROM databases and the projects themselves compare against,
  identical no matter which byte order your dump is stored in.
- Matches the dump's identity against built-in project rules
  (Zelda64Recomp, 2 Ship 2 Harkinian, Ship of Harkinian to start).
- Converts between byte orders:

```bash
python3 romcheck.py convert game.v64 game.z64
```

- `--json` output for scripting. Exit codes: `0` identified, `1` not an
  N64 image (plain hashes still printed), `2` usage / read error.

romcheck ships **no game data** and downloads nothing. Use it with dumps
of cartridges you own — the same rule every recomp project follows.

Indonesian: pemeriksa ROM N64 buat proyek recomp — mendeteksi format asli
file ROM (z64/v64/n64), membaca region dan revisinya, menghitung hash,
dan memberi tahu apakah dump kamu cocok dengan yang diminta proyek
recomp seperti Zelda64Recomp, plus konversi antar format.

## Support / Dukung

Free and MIT. If it saved you a re-download, you can support the maker:
https://trakteer.id/adel_putra2

Gratis dan berlisensi MIT. Kalau tool ini membantumu, dukung pembuatnya
di https://trakteer.id/adel_putra2
