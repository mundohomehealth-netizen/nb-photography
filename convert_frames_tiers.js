/*
 * Builds the three frame tiers the site serves, from one high-resolution render.
 *
 *   node convert_frames_tiers.js frames_v4_xl narratedbynb-site/assets/frames
 *
 * Why three. The hero canvas is sized in CSS pixels but drawn in device pixels,
 * so a retina laptop needs roughly twice the bitmap a standard display does.
 * Serving the large set to everyone wastes tens of megabytes on phones;
 * serving the small one to a retina screen is what made the book look soft
 * against the rest of the page.
 *
 * Blender's WebP writer drops alpha, which is why the render is PNG and the
 * conversion happens out here. The check at the end is not optional: a
 * flattened WebP looks fine on its own and only reveals itself as a white box
 * once it is over the page.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = process.argv[2];
const DEST = process.argv[3];

/* name, width, quality. Quality drops as the tier grows: a 2400px frame is
   displayed at roughly half size, so it can carry more compression. */
const TIERS = [
  { name: "mobile", w: 840, q: 70, alpha: 88 },
  { name: "desktop", w: 1400, q: 74, alpha: 90 },
  { name: "xl", w: 2400, q: 66, alpha: 88 },
];

(async () => {
  const files = fs.readdirSync(SRC).filter((f) => /^\d{4}\.png$/.test(f)).sort();
  if (!files.length) { console.error("no frames in " + SRC); process.exit(1); }
  const meta = await sharp(path.join(SRC, files[0])).metadata();
  console.error("source " + meta.width + "x" + meta.height + ", " + files.length + " frames");

  const report = {};
  for (const t of TIERS) {
    if (t.w > meta.width) { console.error("skipping " + t.name + ": source is narrower"); continue; }
    const dir = path.join(DEST, t.name);
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });

    let bytes = 0;
    for (const f of files) {
      const out = f.replace(/\.png$/, ".webp");
      const pipe = sharp(path.join(SRC, f));
      if (t.w !== meta.width) pipe.resize(t.w, null, { withoutEnlargement: true });
      await pipe.webp({ quality: t.q, alphaQuality: t.alpha, effort: 4 })
        .toFile(path.join(dir, out));
      bytes += fs.statSync(path.join(dir, out)).size;
    }

    const probe = fs.readFileSync(path.join(dir, "0001.webp"));
    const fourcc = probe.slice(12, 16).toString("ascii");
    report[t.name] = {
      width: t.w,
      mb: +(bytes / 1048576).toFixed(2),
      alpha: fourcc === "VP8X" && (probe[20] & 0x10) ? "has alpha" : "NO ALPHA",
    };
    console.error("  " + t.name + " done");
  }
  console.log(JSON.stringify({ frames: files.length, tiers: report }, null, 2));
})();
