/*
 * Builds every texture the v2 album needs, into textures_v2/.
 *
 *   node make_pages_v2.js <folder-with-the-source-photos>
 *
 * Pages are portrait 2:3 to match the reference cover. Photos are cropped to
 * the aspect of the inset area rather than the page, so the paper border ends
 * up the same width on all four sides - which is what "a consistent border"
 * means once the margin is uniform.
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = process.argv[2];
const OUT = path.join(__dirname, "textures_v2");

const PAGE_W = 1000, PAGE_H = 1491;          // 0.671, the reference cover's ratio
const MARGIN = 80;                            // uniform, all four sides
const IN_W = PAGE_W - 2 * MARGIN;             // 840
const IN_H = PAGE_H - 2 * MARGIN;             // 1331
const PHOTO_ASPECT = IN_W / IN_H;             // 0.631

const PAPER = "#f3ece0";
const INK = "#2e2620";

/* crop windows chosen per photo so the subject stays centred and nobody
   important gets cut off; [left, top, width, height] in source pixels */
const SPREADS = [
  { photo: "3.jpg", crop: [495, 0, 1010, 1600],
    quote: "The photos came out absolutely stunning! He captured all the important moments so beautifully.",
    name: "Sujan Sribalan" },
  { photo: "6.jpg", crop: [0, 0, 1262, 2000],
    quote: "Neveen captured every moment with care and an artistic approach!",
    name: "Thushane Shan" },
  { photo: "4.jpg", crop: [580, 0, 841, 1333],
    quote: "He is very professional, friendly and made us super comfortable in front of the camera.",
    name: "Abijengka Geevan" },
  { photo: "5.jpg", crop: [169, 0, 1262, 2000],
    quote: "The photos turned out stunning — full of emotion, candid moments, colour, and detail.",
    name: "Sharanha A" },
  { photo: "7.jpg", crop: [480, 0, 841, 1333],
    quote: "The quality of his work is truly unmatched.",
    name: "Vitheka Satputhiran" },
];

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/* Segoe Script averages a bit over 0.5em per character. The estimate is
   deliberately generous: underestimating runs the longest line into the
   gutter, where the facing page crops it. */
function wrap(text, fontSize, maxWidth) {
  const per = fontSize * 0.525;
  const max = Math.floor(maxWidth / per);
  const words = text.split(/\s+/);
  const lines = [];
  let line = "";
  for (const w of words) {
    const next = line ? line + " " + w : w;
    if (next.length > max && line) { lines.push(line); line = w; } else { line = next; }
  }
  if (line) lines.push(line);
  return lines;
}

async function photoPage(srcFile, crop, outFile) {
  const [left, top, width, height] = crop;
  // the crop window is trimmed to the inset aspect before resizing, so nothing
  // is squashed and the border stays even
  let w = width, h = Math.round(width / PHOTO_ASPECT);
  if (h > height) { h = height; w = Math.round(height * PHOTO_ASPECT); }
  const l = left + Math.round((width - w) / 2);
  const t = top + Math.round((height - h) / 2);

  const photo = await sharp(path.join(SRC, srcFile))
    .extract({ left: l, top: t, width: w, height: h })
    .resize(IN_W, IN_H, { fit: "fill" })
    .toBuffer();

  const paper = Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${PAGE_W}" height="${PAGE_H}">
       <rect width="${PAGE_W}" height="${PAGE_H}" fill="${PAPER}"/>
     </svg>`);

  await sharp(paper)
    .composite([{ input: photo, left: MARGIN, top: MARGIN }])
    .jpeg({ quality: 92 })
    .toFile(path.join(OUT, outFile));
  return { crop: [l, t, w, h] };
}

async function quotePage(quote, name, outFile) {
  const size = 52;
  const lines = wrap("“" + quote + "”", size, IN_W - 110);
  const lh = size * 1.52;
  const blockH = lines.length * lh + 90;
  let y = (PAGE_H - blockH) / 2 + size;

  let body = "";
  for (const ln of lines) {
    body += `<text x="${PAGE_W / 2}" y="${y}" font-family="Segoe Script" font-size="${size}" fill="${INK}" text-anchor="middle">${esc(ln)}</text>`;
    y += lh;
  }
  // a short rule, then the reviewer's name
  body += `<line x1="${PAGE_W / 2 - 46}" y1="${y + 6}" x2="${PAGE_W / 2 + 46}" y2="${y + 6}" stroke="${INK}" stroke-width="1.6" opacity="0.5"/>`;
  body += `<text x="${PAGE_W / 2}" y="${y + 74}" font-family="Segoe Script" font-size="${size * 0.74}" fill="${INK}" opacity="0.8" text-anchor="middle">${esc(name)}</text>`;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${PAGE_W}" height="${PAGE_H}">
      <rect width="${PAGE_W}" height="${PAGE_H}" fill="${PAPER}"/>${body}</svg>`;
  await sharp(Buffer.from(svg)).jpeg({ quality: 94 }).toFile(path.join(OUT, outFile));
  return lines.length;
}

/* White-on-black height map for the cover deboss: NB with the script laid
   across its middle, as on the reference cover. */
async function logo(outFile) {
  const W = 1200, H = 1200;
  const cx = W / 2, cy = H / 2;
  // Script and monogram are both debossed to the same depth, so where they
  // overlap they would merge into one unreadable blob. Drawing the script with
  // a dark halo first cuts a thin gap through the NB and keeps both legible,
  // which is how the separation reads on the reference cover.
  const script = (fill, stroke, sw) =>
    `<text x="0" y="0" font-family="Segoe Script" font-size="112" fill="${fill}"
           ${stroke ? `stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round"` : ""}
           text-anchor="middle" letter-spacing="1">Narratedby</text>`;
  const flourish = (stroke, sw) =>
    `<path d="M -232 34 C -120 52, 120 52, 250 22" stroke="${stroke}" stroke-width="${sw}"
           fill="none" stroke-linecap="round"/>`;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">
    <rect width="${W}" height="${H}" fill="#000"/>
    <text x="${cx}" y="${cy + 165}" font-family="Georgia" font-weight="bold" font-size="460"
          fill="#fff" text-anchor="middle" letter-spacing="-16">NB</text>
    <g transform="translate(${cx}, ${cy + 10})">
      ${script("#000", "#000", 26)}
      ${flourish("#000", 22)}
      ${script("#fff", null, 0)}
      ${flourish("#fff", 5)}
    </g>
  </svg>`;
  // Trim the padding away so the image IS the mark. Blender maps the texture
  // across a share of the cover, so any dead space around the logo shrinks it.
  const trimmed = await sharp(Buffer.from(svg)).trim({ threshold: 8 }).toBuffer();
  const m = await sharp(trimmed).metadata();
  const padX = Math.round(m.width * 0.04), padY = Math.round(m.height * 0.08);
  const info = await sharp(trimmed)
    .extend({ top: padY, bottom: padY, left: padX, right: padX,
              background: { r: 0, g: 0, b: 0, alpha: 1 } })
    .png().toFile(path.join(OUT, outFile));
  return { w: info.width, h: info.height, aspect: +(info.width / info.height).toFixed(3) };
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const report = [];
  for (let i = 0; i < SPREADS.length; i++) {
    const s = SPREADS[i];
    const p = await photoPage(s.photo, s.crop, `photo_${i + 1}.jpg`);
    const n = await quotePage(s.quote, s.name, `quote_${i + 1}.jpg`);
    report.push({ spread: i + 1, photo: s.photo, cropped: p.crop, quoteLines: n, name: s.name });
  }
  const lg = await logo("logo.png");
  console.log(JSON.stringify({ out: OUT, page: [PAGE_W, PAGE_H], margin: MARGIN,
    insetAspect: +PHOTO_ASPECT.toFixed(3), logo: lg, spreads: report }, null, 2));
})();
