#!/usr/bin/env bash
# ==============================================================================
# scripts/ingest-profile-assets.sh
# Optimize the raw profile PNGs (avatars + border overlays) into AVIF.
#
# Deviations from the original SBGC-221 spec (recorded):
#   * The raw assets live FLAT in the source directory — no `avatars/` or
#     `borders/` subfolders.  Border files are `Border N.png`; every other PNG
#     is an avatar.
#   * `magick` (ImageMagick) is not assumed installed; Node + `sharp` is used
#     instead (sharp is already available in the workspace).
#   * Output goes to `public/assets/…` (not `src/assets/…`) so the files are
#     served at `/assets/avatars/*.avif` and `/assets/borders/*.avif`.
# ==============================================================================
set -euo pipefail

SRC_DIR="/home/ammaris/Downloads/Profile Assets"
DEST_AVATARS="apps/frontend/public/assets/avatars"
DEST_BORDERS="apps/frontend/public/assets/borders"

export SRC_DIR DEST_AVATARS DEST_BORDERS

mkdir -p "$DEST_AVATARS" "$DEST_BORDERS"

echo "Optimizing profile assets (avatars 512x512, borders 524x524) to AVIF..."

node --input-type=module <<'NODE'
import { readdirSync } from "node:fs";
import path from "node:path";
import sharp from "sharp";

const srcDir = process.env.SRC_DIR;
const destAvatars = process.env.DEST_AVATARS;
const destBorders = process.env.DEST_BORDERS;

for (const entry of readdirSync(srcDir)) {
  if (!entry.toLowerCase().endsWith(".png")) continue;
  const input = path.join(srcDir, entry);
  const base = entry.slice(0, -4);

  // Border overlays: "Border N.png" -> border_N.avif (524x524).
  const borderMatch = /^Border\s+(\d+)$/i.exec(base);
  if (borderMatch) {
    await sharp(input)
      .resize(524, 524)
      .avif({ quality: 85 })
      .toFile(path.join(destBorders, `border_${borderMatch[1]}.avif`));
    console.log(`border_${borderMatch[1]}.avif`);
    continue;
  }

  // Avatar: lowercased basename -> 512x512.
  await sharp(input)
    .resize(512, 512)
    .avif({ quality: 82 })
    .toFile(path.join(destAvatars, `${base.toLowerCase()}.avif`));
  console.log(`${base.toLowerCase()}.avif`);
}
console.log("Profile assets ingested successfully.");
NODE
