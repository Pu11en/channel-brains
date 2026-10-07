#!/usr/bin/env bash
# Zip the ChatGPT plugin package for OpenAI directory submission.
#
# The ZIP root must contain plugin.json directly (not nested inside a folder),
# so entries are written relative to plugins/chatgpt/channel-brains.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$root/plugins/chatgpt/channel-brains"
out="${1:-$root/dist/channel-brains-chatgpt-plugin.zip}"
mkdir -p "$(dirname "$out")"
rm -f "$out"
python3 - "$src" "$out" <<'PY'
import pathlib
import sys
import zipfile

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
files = sorted(p for p in src.rglob("*") if p.is_file())
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in files:
        zf.write(path, path.relative_to(src).as_posix())
print(f"{out}: {out.stat().st_size} bytes, {len(files)} files")
for path in files:
    print(f"  {path.relative_to(src).as_posix()}")
PY
