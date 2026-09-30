const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = process.argv[2];
const SITE = process.argv[3];
const DESK = path.join(SITE, "frames", "desktop");
const MOB  = path.join(SITE, "frames", "mobile");

(async () => {
  for (const d of [DESK, MOB]) { fs.rmSync(d, { recursive: true, force: true }); fs.mkdirSync(d, { recursive: true }); }
  const files = fs.readdirSync(SRC).filter(f => /^\d{4}\.png$/.test(f)).sort();
  let dBytes = 0, mBytes = 0;
  for (const f of files) {
    const src = path.join(SRC, f);
    const out = f.replace(/\.png$/, ".webp");
    // alpha must survive: webp with alphaQuality, no flattening
    await sharp(src).webp({ quality: 72, alphaQuality: 90, effort: 4 }).toFile(path.join(DESK, out));
    await sharp(src).resize(960, 540, { fit: "fill" }).webp({ quality: 70, alphaQuality: 88, effort: 4 }).toFile(path.join(MOB, out));
    dBytes += fs.statSync(path.join(DESK, out)).size;
    mBytes += fs.statSync(path.join(MOB, out)).size;
  }
  console.log(JSON.stringify({
    frames: files.length,
    desktopMB: +(dBytes / 1048576).toFixed(2),
    mobileMB: +(mBytes / 1048576).toFixed(2),
  }, null, 2));
})();
