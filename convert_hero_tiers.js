/*
 * Builds the frame tiers the site serves, from the full-resolution extraction.
 *
 *   node convert_hero_tiers.js frames_hero narratedbynb-site/assets/hero
 *
 * Why three. The canvas is laid out in CSS pixels but painted in device
 * pixels, so a phone at 3x needs roughly three times the bitmap a 1x screen
 * does. Serving the largest set to everyone wastes most of a 10MB download on
 * a screen that cannot show it; serving the smallest to a modern phone is
 * what makes the book look soft against the rest of the page.
 *
 * These frames carry no alpha - the clip has its own background baked in -
 * which is why they cost a third of what the old transparent renders did.
 *
 * The manifest is copied across untouched. It is what tells the player how
 * many frames there are and which of them are the settled spreads.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = process.argv[2];
const DEST = process.argv[3];

/* name, width, quality. The source is 1080 wide, so the top tier is a
   straight re-encode and can afford a point or two less quality than the
   ones being downscaled, which gain sharpness from the resample. */
const TIERS = [
  { name: "sm", w: 540, q: 72 },
  { name: "md", w: 810, q: 70 },
  { name: "lg", w: 1080, q: 68 },
];

(async () => {
  const isFrame = (f) => /^[0-9]{4}[.]png$/.test(f);
  const files = fs.readdirSync(SRC).filter(isFrame).sort();
  if (!files.length) { console.error("no frames in " + SRC); process.exit(1); }

  const manifestPath = path.join(SRC, "manifest.json");
  if (!fs.existsSync(manifestPath)) {
    console.error("missing manifest.json - run extract_hero.py, which writes it");
    process.exit(1);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  if (manifest.count !== files.length) {
    console.error("manifest says " + manifest.count + " frames but " +
                  files.length + " are on disk");
    process.exit(1);
  }

  const meta = await sharp(path.join(SRC, files[0])).metadata();
  console.error("source " + meta.width + "x" + meta.height + ", " + files.length + " frames");

  fs.mkdirSync(DEST, { recursive: true });
  const report = {};

  for (const t of TIERS) {
    if (t.w > meta.width) { console.error("skipping " + t.name + ": source is narrower"); continue; }
    const dir = path.join(DEST, t.name);
    fs.rmSync(dir, { recursive: true, force: true });
    fs.mkdirSync(dir, { recursive: true });

    let bytes = 0;
    for (const f of files) {
      const pipe = sharp(path.join(SRC, f));
      if (t.w !== meta.width) pipe.resize(t.w);
      await pipe.webp({ quality: t.q, effort: 5 })
        .toFile(path.join(dir, f.replace(".png", ".webp")));
      bytes += fs.statSync(path.join(dir, f.replace(".png", ".webp"))).size;
    }
    report[t.name] = {
      width: t.w,
      mb: +(bytes / 1048576).toFixed(2),
      kbPerFrame: +(bytes / files.length / 1024).toFixed(1),
    };
    console.error("  " + t.name + " done");
  }

  // The player reads this for the frame count and the stop list, so it ships
  // with the frames rather than being duplicated into the markup by hand.
  fs.writeFileSync(path.join(DEST, "manifest.json"), JSON.stringify({
    count: manifest.count,
    stops: manifest.stops,
    width: manifest.width,
    height: manifest.height,
    tiers: TIERS.map((t) => ({ dir: t.name + "/", w: t.w })),
  }, null, 2));

  console.log(JSON.stringify({ frames: files.length, stops: manifest.stops, tiers: report }, null, 2));
})();
