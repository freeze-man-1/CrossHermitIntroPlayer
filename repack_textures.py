#!/usr/bin/env python3
"""
repack_textures.py  --  Rebuild OPDATA.BIN / OPDATA2.BIN from extracted PNGs.

For translators who want to test their edited textures inside the real game:
edit the PNGs under textures/ (keep the same dimensions), then repack to .BIN.

The OPDATA repack is byte-lossless when the PNGs are unmodified, because PNG
alpha carries the original bit-15 flag and the 5-bit colour expansion is
reversible. Edited PNGs are quantised back to ARGB1555 (5 bits per channel,
1-bit alpha: any pixel with alpha < 128 OR pure-zero colour becomes the
transparent 0x0000).

USAGE
  python repack_textures.py --in textures/ --opdata-out OPDATA.BIN --opdata2-out OPDATA2.BIN

Notes
  * Dimensions must match the manifest (the game expects fixed sizes).
  * OPDATA2 non-image entries are restored verbatim from the dumped *.bin files;
    the 53 orb frames are re-encoded as 8-bit indexed BMPs with palette index 0
    transparent. If you only translate OPDATA text, you can skip --opdata2-out.
"""
import argparse, struct, json, os, io
import numpy as np
from PIL import Image


def repack_opdata(in_dir, manifest, out_path):
    md = manifest["opdata"]
    count = md["count"]
    # build each texture's 12-byte header + pixel block
    blocks = []
    for ent in md["textures"]:
        w, h = ent["w"], ent["h"]
        png = os.path.join(in_dir, ent["file"])
        im = Image.open(png).convert("RGBA")
        if im.size != (w, h):
            raise SystemExit(f"{png}: size {im.size} != expected {(w, h)}; keep dimensions unchanged")
        a = np.array(im)
        r5 = (a[:, :, 0] >> 3).astype("<u2")
        g5 = (a[:, :, 1] >> 3).astype("<u2")
        b5 = (a[:, :, 2] >> 3).astype("<u2")
        opaque = (a[:, :, 3] >= 128)
        px = ((np.uint16(1) << 15) | (r5 << 10) | (g5 << 5) | b5).astype("<u2")
        # transparent pixels -> 0x0000
        px = np.where(opaque, px, np.uint16(0)).astype("<u2")
        hdr = struct.pack("<6H", ent.get("magic", 22596), ent.get("fmt", 2), w, h, w, h)
        blocks.append(hdr + px.tobytes())

    # layout: [filesize][count][count u32 offsets][blocks...]
    header_size = 8 + count * 4
    offsets = []
    pos = header_size
    for b in blocks:
        offsets.append(pos)
        pos += len(b)
    filesize = pos
    out = bytearray()
    out += struct.pack("<II", filesize, count)
    for off in offsets:
        out += struct.pack("<I", off)
    for b in blocks:
        out += b
    open(out_path, "wb").write(out)
    print(f"[*] wrote {out_path} ({filesize} bytes, {count} textures)")


def repack_opdata2(in_dir, manifest, out_path):
    md = manifest["opdata2"]
    count = md["count"]
    # rebuild each entry
    entry_blobs = [None] * count
    anim_index = None
    for ent in md["entries"]:
        ei = ent["index"]
        if ent.get("type") == "raw":
            entry_blobs[ei] = open(os.path.join(in_dir, ent["file"]), "rb").read()
        elif ent.get("type") == "animation":
            anim_index = ei
            frames = ent["frames"]
            bmps = []
            for fr in frames:
                im = Image.open(os.path.join(in_dir, fr["file"])).convert("RGBA")
                # rebuild an 8-bit indexed BMP, palette index 0 = transparent
                arr = np.array(im)
                transparent = arr[:, :, 3] < 128
                rgb = Image.fromarray(arr[:, :, :3], "RGB").convert(
                    "P", palette=Image.ADAPTIVE, colors=255)
                # shift palette so index 0 is free for transparency
                idx = np.array(rgb) + 1
                idx[transparent] = 0
                pal = rgb.getpalette()[:255 * 3]
                newpal = [0, 0, 0] + pal  # index 0 black/transparent
                out_im = Image.fromarray(idx.astype("u1"), "P")
                out_im.putpalette(newpal)
                buf = io.BytesIO()
                out_im.save(buf, format="BMP")
                bmps.append(buf.getvalue())
            # assemble entry 6: [u32 size][u32 nframes][nframes u32 sub-offsets][bmps]
            n = len(bmps)
            sub_table_size = 8 + n * 4
            suboffs = []
            pos = sub_table_size
            for b in bmps:
                suboffs.append(pos)
                pos += len(b)
            body = bytearray()
            body += struct.pack("<II", pos, n)
            for so in suboffs:
                body += struct.pack("<I", so)
            for b in bmps:
                body += b
            entry_blobs[ei] = bytes(body)

    # layout: [filesize][count][count u32 offsets][entries...]
    header_size = 8 + count * 4
    offsets = []
    pos = header_size
    for b in entry_blobs:
        offsets.append(pos)
        pos += len(b) if b else 0
    filesize = pos
    out = bytearray()
    out += struct.pack("<II", filesize, count)
    for off in offsets:
        out += struct.pack("<I", off)
    for b in entry_blobs:
        if b:
            out += b
    open(out_path, "wb").write(out)
    print(f"[*] wrote {out_path} ({filesize} bytes)  [orb frames re-encoded]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", default="textures")
    ap.add_argument("--opdata-out", default=None)
    ap.add_argument("--opdata2-out", default=None)
    args = ap.parse_args()
    manifest = json.load(open(os.path.join(args.in_dir, "manifest.json")))
    if args.opdata_out and "opdata" in manifest:
        repack_opdata(args.in_dir, manifest, args.opdata_out)
    if args.opdata2_out and "opdata2" in manifest:
        repack_opdata2(args.in_dir, manifest, args.opdata2_out)
    if not args.opdata_out and not args.opdata2_out:
        print("Nothing to do. Pass --opdata-out and/or --opdata2-out.")


if __name__ == "__main__":
    main()
