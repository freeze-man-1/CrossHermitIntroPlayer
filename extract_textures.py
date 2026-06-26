#!/usr/bin/env python3
"""
extract_textures.py  --  Cross Hermit intro texture extractor

Dumps every sprite from OPDATA.BIN and OPDATA2.BIN to individual PNG files,
plus a manifest.json describing each one. The PNGs are LOSSLESS with respect to
the original 16-bit pixel data: the top bit (bit 15) of each ARGB1555 pixel is
stored as the PNG alpha channel, and the 5-bit colour channels expand to 8-bit
reversibly, so repack_textures.py can rebuild byte-identical .BIN files.

FORMATS
  OPDATA.BIN   : header [u32 filesize][u32 count] then `count` u32 offsets.
                 Each texture: 12-byte header ('DX', fmt=2, w, h, w, h) followed
                 by w*h ARGB1555 pixels (little-endian u16). bit15=opaque flag,
                 bits10-14=R5, bits5-9=G5, bits0-4=B5. A fully-zero pixel is
                 transparent.
  OPDATA2.BIN  : 7 entries; entry 6 holds the 53-frame orb/teardrop animation as
                 53 standard 8-bit indexed BMP frames (palette index 0 = transparent).
                 The other entries are small/struct data and are dumped as raw .bin.

USAGE
  python extract_textures.py  --opdata OPDATA.BIN  --opdata2 OPDATA2.BIN  --out textures/

OUTPUT
  textures/
    opdata/opdata_00.png ... opdata_47.png
    opdata2/orb_00.png   ... orb_52.png
    opdata2/entry_0.bin  ... (non-image entries, raw)
    manifest.json
"""
import argparse, struct, json, os
import numpy as np
from PIL import Image


# ---------- OPDATA (ARGB1555 sprite bank) ----------
def extract_opdata(path, out_dir):
    buf = open(path, "rb").read()
    filesize, count = struct.unpack_from("<II", buf, 0)
    offs = [struct.unpack_from("<I", buf, 8 + i * 4)[0] for i in range(count)]
    os.makedirs(out_dir, exist_ok=True)
    entries = []
    for i in range(count):
        o = offs[i]
        magic, fmt, w, h, w2, h2 = struct.unpack_from("<6H", buf, o)
        px = np.frombuffer(buf[o + 12 : o + 12 + w * h * 2], dtype="<u2").reshape(h, w)
        r5 = (px >> 10) & 31
        g5 = (px >> 5) & 31
        b5 = px & 31
        # reversible 5->8 bit expansion
        r8 = ((r5 << 3) | (r5 >> 2)).astype("u1")
        g8 = ((g5 << 3) | (g5 >> 2)).astype("u1")
        b8 = ((b5 << 3) | (b5 >> 2)).astype("u1")
        a8 = np.where((px >> 15) & 1, 255, 0).astype("u1")
        rgba = np.dstack([r8, g8, b8, a8])
        name = f"opdata_{i:02d}.png"
        Image.fromarray(rgba, "RGBA").save(os.path.join(out_dir, name))
        entries.append({"index": i, "file": f"opdata/{name}", "w": int(w), "h": int(h),
                        "magic": magic, "fmt": fmt})
    return {"source": os.path.basename(path), "filesize": filesize, "count": count,
            "format": "ARGB1555", "textures": entries}


# ---------- OPDATA2 (entry 6 = 53 indexed-BMP animation frames) ----------
def extract_opdata2(path, out_dir):
    buf = open(path, "rb").read()
    count = struct.unpack_from("<I", buf, 4)[0]
    offs = [struct.unpack_from("<I", buf, 8 + i * 4)[0] for i in range(count)]
    os.makedirs(out_dir, exist_ok=True)
    result = {"source": os.path.basename(path), "count": count, "entries": []}

    for ei in range(count):
        o = offs[ei]
        end = offs[ei + 1] if ei + 1 < count else len(buf)
        if ei == 6:
            # the animation: [u32 size][u32 nframes] then nframes u32 sub-offsets, then BMPs
            nframes = struct.unpack_from("<I", buf, o + 4)[0]
            sub = [struct.unpack_from("<I", buf, o + 8 + k * 4)[0] for k in range(nframes)]
            frames = []
            for k in range(nframes):
                fo = o + sub[k]
                fend = (o + sub[k + 1]) if k + 1 < nframes else end
                bmp = buf[fo:fend]
                # load the indexed BMP; palette index 0 -> transparent
                im = Image.open(__import__("io").BytesIO(bmp))
                im = im.convert("P") if im.mode != "P" else im
                rgba = im.convert("RGBA")
                # make palette index 0 transparent
                idx = np.array(im)
                a = np.where(idx == 0, 0, 255).astype("u1")
                arr = np.array(rgba)
                arr[:, :, 3] = a
                name = f"orb_{k:02d}.png"
                Image.fromarray(arr, "RGBA").save(os.path.join(out_dir, name))
                frames.append({"frame": k, "file": f"opdata2/{name}",
                               "w": rgba.width, "h": rgba.height})
            result["entries"].append({"index": 6, "type": "animation",
                                      "nframes": nframes, "frames": frames})
        else:
            # non-image struct data -> raw dump so repack can restore it verbatim
            raw = buf[o:end]
            name = f"entry_{ei}.bin"
            open(os.path.join(out_dir, name), "wb").write(raw)
            result["entries"].append({"index": ei, "type": "raw",
                                      "file": f"opdata2/{name}", "size": len(raw)})
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opdata", default="OPDATA.BIN")
    ap.add_argument("--opdata2", default="OPDATA2.BIN")
    ap.add_argument("--out", default="textures")
    args = ap.parse_args()

    manifest = {"version": 1}
    if os.path.exists(args.opdata):
        manifest["opdata"] = extract_opdata(args.opdata, os.path.join(args.out, "opdata"))
        print(f"[*] OPDATA: {manifest['opdata']['count']} textures -> {args.out}/opdata/")
    if os.path.exists(args.opdata2):
        manifest["opdata2"] = extract_opdata2(args.opdata2, os.path.join(args.out, "opdata2"))
        nf = next((e["nframes"] for e in manifest["opdata2"]["entries"] if e.get("type") == "animation"), 0)
        print(f"[*] OPDATA2: {nf} orb frames -> {args.out}/opdata2/")

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[*] wrote {args.out}/manifest.json")


if __name__ == "__main__":
    main()
