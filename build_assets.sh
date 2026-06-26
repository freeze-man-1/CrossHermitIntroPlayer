#!/usr/bin/env bash
# One-shot: regenerate the web assets from the original game files.
# Usage: ./build_assets.sh /path/to/OPDATA.BIN /path/to/OPDATA2.BIN /path/to/OPENING.MP3
set -e
OPDATA="${1:-OPDATA.BIN}"; OPDATA2="${2:-OPDATA2.BIN}"; MUSIC="${3:-OPENING.MP3}"
python3 extract_textures.py --opdata "$OPDATA" --opdata2 "$OPDATA2" --out assets/textures
cp "$MUSIC" assets/OPENING.mp3
echo "Done. replay.json.gz / overlay.json.gz are shipped as-is (capture data)."
