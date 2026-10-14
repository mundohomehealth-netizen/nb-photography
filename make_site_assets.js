/*
 * Prepares every image the site needs, into narratedbynb-site/assets/img/.
 *
 *   node make_site_assets.js <folder-with-the-source-images>
 *
 * The logo arrives as a JPEG with its transparency checkerboard flattened into
 * it, so the mark is thresholded back out rather than taken from an alpha
 * channel, then tinted for use on light and on dark.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = process.argv[2];
const OUT = path.join(__dirname, "narratedbynb-site", "assets", "img");

const CHARCOAL = { r: 0x18, g: 0x19, b: 0x17 };
const IVORY = { r: 0xf3, g: 0xf1, b: 0xea };

/* source file -> the name the site refers to it by, and how it is framed */
const PHOTOS = [
  { src: "13.jpg", name: "ceremony-petals", alt: "A bride showered with rose petals during the ceremony" },
  { src: "14.jpg", name: "couple-greenery", alt: "A couple laughing together among greenery" },
  { src: "15.jpg", name: "bride-golden", alt: "A bride in golden light, in a cream and gold saree" },
  { src: "16.jpg", name: "bride-veil-bw", alt: "A bride beneath an embroidered veil, in black and white" },
  { src: "17.jpg", name: "couple-beach", alt: "A couple walking hand in hand on a beach at sunset" },
  { src: "18.jpg", name: "haldi-marigolds", alt: "Marigold petals thrown over a couple at their haldi" },
];

const WIDTHS = [600, 1200, 2000];

async function logo(srcFile) {
  const g = await sharp(path.join(SRC, srcFile)).greyscale().raw()
    .toBuffer({ resolveWithObject: true });
  const { data, info } = g;
  const W = info.width, H = info.height;

  // The mark is near-black; the checkerboard behind it is light grey and white.
  // Alpha comes from how dark each pixel is, which keeps the edges soft rather
  // than stairstepped.
  const alpha = Buffer.alloc(W * H);
  for (let i = 0; i < alpha.length; i++) {
    const v = data[i];
    alpha[i] = v >= 170 ? 0 : v <= 60 ? 255 : Math.round(((170 - v) / 110) * 255);
  }
  const mask = await sharp(alpha, { raw: { width: W, height: H, channels: 1 } })
    .png().toBuffer();

  // sharp trim() compares COLOUR, and these are a single flat colour varying
  // only in alpha - so it finds nothing. The bounding box has to come from the
  // alpha channel directly.
  let x0 = W, y0 = H, x1 = -1, y1 = -1;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (alpha[y * W + x] > 12) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  const box = { left: x0, top: y0, width: x1 - x0 + 1, height: y1 - y0 + 1 };

  for (const [name, c] of [["logo-charcoal", CHARCOAL], ["logo-ivory", IVORY]]) {
    const flat = await sharp({
      create: { width: W, height: H, channels: 3, background: c },
    }).png().toBuffer();
    // Two passes on purpose: extract chained after joinChannel in one
    // pipeline silently does not apply, so the alpha is baked first and the
    // crop happens on the finished image.
    const rgba = await sharp(flat).joinChannel(mask).png().toBuffer();
    const info2 = await sharp(rgba).extract(box)
      .png({ compressionLevel: 9 }).toFile(path.join(OUT, name + ".png"));
    if (name === "logo-charcoal") {
      console.log("  logo trimmed to " + info2.width + "x" + info2.height +
        "  aspect " + (info2.width / info2.height).toFixed(3));
    }
  }
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  console.log("logo:");
  await logo("12.jpg");

  console.log("photos:");
  const manifest = [];
  for (const p of PHOTOS) {
    const meta = await sharp(path.join(SRC, p.src)).metadata();
    const entry = { name: p.name, alt: p.alt, w: meta.width, h: meta.height, srcset: [] };
    for (const w of WIDTHS) {
      if (w > meta.width) continue;
      const file = `${p.name}-${w}.webp`;
      await sharp(path.join(SRC, p.src))
        .resize(w, null, { withoutEnlargement: true })
        .webp({ quality: 80 })
        .toFile(path.join(OUT, file));
      entry.srcset.push({ file, w });
    }
    manifest.push(entry);
    console.log("  " + p.name.padEnd(18) + entry.srcset.map(s => s.w).join(" "));
  }

  fs.writeFileSync(path.join(OUT, "photos.json"), JSON.stringify(manifest, null, 2));
  console.log("wrote photos.json (" + manifest.length + " photos)");
})();
