#!/usr/bin/env python3
"""romcheck - is this the exact ROM your recomp project wants?

Static recompilation projects (Zelda64Recomp, other N64Recomp ports, the
Harbour Masters PC ports) each accept ONE specific dump of a game: one
region, one revision. Feed them the wrong one and they just refuse it -
usually without telling you what you actually have.

romcheck reads the ROM you have, in any of the three N64 byte orders
(.z64 big-endian, .v64 byte-swapped, .n64 little-endian, or inside a
.zip), and tells you:

  - the game (internal header name and cartridge id), region, revision
  - MD5 / SHA1 / CRC32 of the normalized big-endian image - the values
    the ROM databases and the projects themselves compare against
  - which recomp/port projects this dump matches, by identity

It also converts between the three byte orders:

    python3 romcheck.py convert game.v64 game.z64

It never contains, downloads or modifies game data beyond byte order.
Use it with dumps of cartridges you own.
"""
import argparse
import hashlib
import json
import sys
import zipfile
import zlib

MAGICS = {
    b"\x80\x37\x12\x40": "z64",
    b"\x37\x80\x40\x12": "v64",
    b"\x40\x12\x37\x80": "n64",
}
COUNTRIES = {
    0x00: "Japan / USA (beta code)", 0x37: "Japan / USA", 0x41: "Asia (NTSC)",
    0x42: "Brazil", 0x43: "China", 0x44: "Germany", 0x45: "North America",
    0x46: "France", 0x49: "Italy", 0x4A: "Japan", 0x4B: "Korea",
    0x4E: "Canada", 0x50: "Europe (PAL)", 0x53: "Spain", 0x55: "Australia",
    0x58: "Europe", 0x59: "Europe",
}

# MD5 of the normalized big-endian image -> identity. Small on purpose:
# an entry ships only when its hash is publicly documented. The ROM
# header identity below covers everything else.
KNOWN_MD5 = {
    "2a0a8acb61538235bc1094d297fb6556": "The Legend of Zelda: Majora's Mask (USA) - Rev 0 dump",
}

# Project requirements by ROM identity (cartridge id + country + revision),
# as documented by the projects themselves.
PROJECT_RULES = [
    {
        "cart": "ZS", "countries": {0x37, 0x45}, "versions": {1},
        "project": "Zelda 64: Recompiled (Zelda64Recomp)",
        "note": "documents its target as the US Rev 1 dump (mm.us.rev1.z64)",
    },
    {
        "cart": "ZS", "countries": {0x37, 0x45}, "versions": {0},
        "project": "2 Ship 2 Harkinian (Majora's Mask PC port)",
        "note": "accepts the US N64 1.0 dump; the GameCube US dump is also supported",
    },
    {
        "cart": "ZL", "countries": {0x37, 0x45}, "versions": {0, 1, 2},
        "project": "Ship of Harkinian (Ocarina of Time PC port)",
        "note": "accepts specific US Ocarina of Time dumps - it verifies by hash at setup",
    },
]


def normalize(data, fmt):
    if fmt == "z64":
        return data
    out = bytearray(len(data))
    if fmt == "v64":  # swap every byte pair
        out[0::2] = data[1::2]
        out[1::2] = data[0::2]
    else:  # n64: reverse every 4-byte group
        for i in range(0, len(data) - 3, 4):
            out[i:i + 4] = data[i:i + 4][::-1]
    return bytes(out)


def convert_bytes(data, from_fmt, to_fmt):
    if from_fmt == to_fmt:
        return data
    return normalize(data, from_fmt) if to_fmt == "z64" else _denormalize(data, to_fmt)


def _denormalize(big_endian, to_fmt):
    if to_fmt == "v64":
        out = bytearray(len(big_endian))
        out[0::2] = big_endian[1::2]
        out[1::2] = big_endian[0::2]
        return bytes(out)
    out = bytearray(len(big_endian))
    for i in range(0, len(big_endian) - 3, 4):
        out[i:i + 4] = big_endian[i:i + 4][::-1]
    return bytes(out)


def read_input(path):
    """Return (bytes, display_name), transparently opening .zip archives."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist()
                     if n.lower().endswith((".z64", ".v64", ".n64"))]
            if not names:
                raise ValueError("zip contains no .z64/.v64/.n64 file")
            return z.read(names[0]), names[0]
    with open(path, "rb") as f:
        return f.read(), path


def inspect(data):
    fmt = MAGICS.get(data[:4])
    if fmt is None:
        return {"format": None}
    img = normalize(data, fmt)
    name = img[0x20:0x34].decode("ascii", "replace").strip("\x00 ").strip()
    cart = img[0x3C:0x3E].decode("ascii", "replace")
    country = img[0x3E]
    version = img[0x3F]
    md5 = hashlib.md5(img).hexdigest()
    info = {
        "format": fmt,
        "size": len(img),
        "internal_name": name,
        "cartridge_id": cart,
        "country_code": country,
        "country": COUNTRIES.get(country, f"unknown (0x{country:02X})"),
        "revision": version,
        "header_crc": f"{int.from_bytes(img[0x10:0x14], 'big'):08X} {int.from_bytes(img[0x14:0x18], 'big'):08X}",
        "md5": md5,
        "sha1": hashlib.sha1(img).hexdigest(),
        "crc32": f"{zlib.crc32(img) & 0xFFFFFFFF:08x}",
        "known_dump": KNOWN_MD5.get(md5),
        "projects": [],
    }
    for rule in PROJECT_RULES:
        if (cart == rule["cart"] and country in rule["countries"]
                and version in rule["versions"]):
            info["projects"].append(
                {"project": rule["project"], "note": rule["note"]})
    return info


def report(path):
    try:
        data, shown = read_input(path)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return 2, None
    info = inspect(data)
    info["file"] = shown
    if info["format"] is None:
        info["md5"] = hashlib.md5(data).hexdigest()
        info["sha1"] = hashlib.sha1(data).hexdigest()
        info["crc32"] = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
        info["size"] = len(data)
    return (0 if info["format"] else 1), info


def print_human(info):
    if info["format"] is None:
        print(f"file:    {info['file']}")
        print("Not an N64 ROM image (unknown header magic). Plain hashes:")
        print(f"  size:  {info['size']} bytes")
        print(f"  md5:   {info['md5']}")
        print(f"  sha1:  {info['sha1']}")
        print(f"  crc32: {info['crc32']}")
        return
    print(f"file:     {info['file']}")
    print(f"format:   .{info['format']} (byte order detected from header, not extension)")
    print(f"game:     {info['internal_name']}  [cartridge {info['cartridge_id']}]")
    print(f"region:   {info['country']}")
    print(f"revision: Rev {info['revision']}")
    print(f"size:     {info['size']} bytes")
    print(f"md5:      {info['md5']}")
    print(f"sha1:     {info['sha1']}")
    print(f"crc32:    {info['crc32']}")
    if info["known_dump"]:
        print(f"known dump: {info['known_dump']}")
    if info["projects"]:
        print("recomp / port projects this dump matches:")
        for p in info["projects"]:
            print(f"  - {p['project']}: {p['note']}")
    else:
        print("recomp / port projects: no match in the built-in rules - "
              "check the project's docs for its exact target dump and "
              "compare the MD5 above.")


def main():
    if "--ptraaa" in sys.argv:
        print("romcheck - built by ptraaa (github.com/Ptraaah). Lived by your own thinking.")
        return 0
    argv = sys.argv[1:]
    if argv and argv[0] == "convert":
        cv = argparse.ArgumentParser(prog="romcheck.py convert",
                                     description="Convert between .z64 / .v64 / .n64 byte orders")
        cv.add_argument("src")
        cv.add_argument("dst")
        args = cv.parse_args(argv[1:])
        try:
            data, _ = read_input(args.src)
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"cannot read {args.src}: {e}", file=sys.stderr)
            return 2
        from_fmt = MAGICS.get(data[:4])
        to_fmt = args.dst.rsplit(".", 1)[-1].lower()
        if from_fmt is None or to_fmt not in ("z64", "v64", "n64"):
            print("convert needs an N64 ROM source and a .z64/.v64/.n64 destination",
                  file=sys.stderr)
            return 2
        try:
            with open(args.dst, "xb") as f:
                f.write(convert_bytes(data, from_fmt, to_fmt))
        except FileExistsError:
            print(f"{args.dst} already exists - refusing to overwrite", file=sys.stderr)
            return 2
        except OSError as e:
            print(f"cannot write {args.dst}: {e}", file=sys.stderr)
            return 2
        print(f"converted .{from_fmt} -> .{to_fmt}: {args.dst}")
        return 0
    if argv and argv[0] == "check":
        argv = argv[1:]
    ap = argparse.ArgumentParser(
        description="Identify an N64 ROM dump and check it against recomp project requirements")
    ap.add_argument("rom", help="ROM file (.z64/.v64/.n64 or a .zip containing one)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)
    code, info = report(args.rom)
    if info is None:
        return code
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print_human(info)
    return code


if __name__ == "__main__":
    sys.exit(main())
