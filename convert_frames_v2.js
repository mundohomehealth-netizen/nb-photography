/*
 * Turns the transparent PNG renders into the WebP frames the site serves.
 *
 *   node convert_frames_v2.js frames_v2 <output-folder>
 *
 * Blender's own WebP writer silently drops the alpha channel, which is why the
 * render is PNG and the conversion happens out here. The check at the end is
 * not optional: a flattened WebP looks perfectly fine on its own and only
 * reveals itself as a white box once it is on the page.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = process.argv[2];
const DEST = process.argv[3];
const DESK = path.join(DEST, "desktop");
const MOB = path.join(DEST, "mobile");

(async () => {
  const files = fs.readdirSync(SRC).filter((f) => /^\d{4}\.png$/.test(f)).sort();
  if (!files.length) { console.error("no frames found in " + SRC); process.exit(1); }

  // Mobile is derived from the real frame size rather than hardcoded, so this
  // keeps working now the album is portrait and the frame is 4:3, not 16:9.
  const meta = await sharp(path.join(SRC, files[0])).metadata();
  const mobW = Math.round(meta.width * 0.6), mobH = Math.round(meta.height * 0.6);

  for (const d of [DESK, MOB]) {
    fs.rmSync(d, { recursive: true, force: true });
    fs.mkdirSync(d, { recursive: true });
  }

  let dBytes = 0, mBytes = 0;
  for (const f of files) {
    const src = path.join(SRC, f);
    const out = f.replace(/\.png$/, ".webp");
    await sharp(src).webp({ quality: 74, alphaQuality: 90, effort: 4 })
      .toFile(path.join(DESK, out));
    await sharp(src).resize(mobW, mobH, { fit: "fill" })
      .webp({ quality: 70, alphaQuality: 88, effort: 4 })
      .toFile(path.join(MOB, out));
    dBytes += fs.statSync(path.join(DESK, out)).size;
    mBytes += fs.statSync(path.join(MOB, out)).size;
  }

  // alpha has to have survived, on both sets
  const checked = {};
  for (const [label, dir] of [["desktop", DESK], ["mobile", MOB]]) {
    const b = fs.readFileSync(path.join(dir, "0001.webp"));
    const fourcc = b.slice(12, 16).toString("ascii");
    checked[label] = fourcc === "VP8X" && (b[20] & 0x10) ? "has alpha" : "NO ALPHA";
  }

  console.log(JSON.stringify({
    frames: files.length,
    desktop: [meta.width, meta.height], mobile: [mobW, mobH],
    desktopMB: +(dBytes / 1048576).toFixed(2),
    mobileMB: +(mBytes / 1048576).toFixed(2),
    alpha: checked,
  }, null, 2));
})();
