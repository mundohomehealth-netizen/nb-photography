/* NB album - scroll-driven hero (no libraries needed)
   Scrolling down plays the frames forward; scrolling up plays them backward.

   The hero opens as three books side by side. The middle one is this canvas.
   As you scroll, the two outer books slide away (CSS, driven by --nb-p) while
   the album here grows from book-size to filling the screen, then opens. */
(function () {
  var section = document.querySelector("[data-nb-hero]");
  if (!section) return;

  var FRAME_COUNT = parseInt(section.getAttribute("data-frame-count") || "248", 10);
  var BASE = section.getAttribute("data-frames-path") || "frames/";   // folder that holds desktop/ and mobile/
  // Set to "true" once the frames are re-rendered with a transparent background.
  var ALPHA = section.getAttribute("data-frames-alpha") === "true";
  var BG = getComputedStyle(section).getPropertyValue("--nb-bg").trim() || "#b9aea0";
  var small = Math.min(window.screen.width, window.screen.height) < 700;
  var DIR = BASE.replace(/\/?$/, "/") + (small ? "mobile/" : "desktop/");
  var IMG_W = small ? 960 : 1600, IMG_H = small ? 540 : 900;

  // The closed book occupies roughly this much of the frame's height. Used to
  // match the canvas book to the height of the two CSS books beside it.
  var BOOK_FRAC_H = 0.804;   // 724px of the 900px frame
  // Scroll fraction over which the album grows from book-size to full-bleed.
  var GROW_UNTIL = 0.18;

  var canvas = section.querySelector("canvas");
  var ctx = canvas.getContext("2d");
  var frames = new Array(FRAME_COUNT);
  var ready = new Array(FRAME_COUNT);
  var current = 0, target = 0, drawn = -1, drawnT = -1, rafId = 0;
  var p = 0;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function src(i) { return DIR + String(i + 1).padStart(4, "0") + ".webp"; }

  function load(i) {
    if (frames[i]) return;
    var img = new Image();
    img.decoding = "async";
    img.onload = function () {
      ready[i] = true;
      if (Math.abs(i - Math.round(current)) < 12) { drawn = -1; requestTick(); }
    };
    img.src = src(i);
    frames[i] = img;
  }

  // Load the first frame immediately, then a coarse pass (every 8th frame) so
  // fast scrolling always has something close to show, then fill in the rest.
  function preload() {
    load(0);
    var order = [], i, step;
    for (step of [8, 4, 2, 1]) for (i = 0; i < FRAME_COUNT; i += step) order.push(i);
    var k = 0;
    (function next() {
      var batch = 0;
      while (k < order.length && batch < 12) { load(order[k++]); batch++; }
      if (k < order.length) setTimeout(next, 30);
    })();
  }

  function nearestReady(i) {
    for (var d = 0; d < FRAME_COUNT; d++) {
      if (i - d >= 0 && ready[i - d]) return i - d;
      if (i + d < FRAME_COUNT && ready[i + d]) return i + d;
    }
    return -1;
  }

  function dpr() { return Math.min(window.devicePixelRatio || 1, 2); }

  function resize() {
    canvas.width = Math.round(canvas.clientWidth * dpr());
    canvas.height = Math.round(canvas.clientHeight * dpr());
    drawn = -1;
    requestTick();
  }

  /* Height in canvas pixels that one book should occupy. Measured off a real
     element rather than parsed from --book-h, because that token is a min()
     expression that no amount of parseFloat will resolve correctly. */
  var sizer = section.querySelector(".album-shadow");
  function bookPx() {
    var h = sizer ? sizer.getBoundingClientRect().height : 0;
    if (!h) h = window.innerHeight * 0.3;      // same intent as the CSS fallback
    return h * dpr();
  }

  function smoothstep(t) { return t * t * (3 - 2 * t); }

  function draw(i, t) {
    var img = frames[i];
    var cw = canvas.width, ch = canvas.height;

    // Full-bleed size: wide screens fill edge to edge, tall screens fit the book.
    var cover = cw / ch >= 1.5;
    var fullS = cover ? Math.max(cw / IMG_W, ch / IMG_H) : Math.min(cw / IMG_W, ch / IMG_H);
    var fullH = IMG_H * fullS;
    // Book-in-a-row size at the very top of the page.
    var smallH = bookPx() / BOOK_FRAC_H;

    var h = smallH + (fullH - smallH) * t;
    var s = h / IMG_H, w = IMG_W * s;
    var x = (cw - w) / 2, y = (ch - h) / 2;

    ctx.clearRect(0, 0, cw, ch);
    // Opaque frames still carry their own backdrop; only paint it once the frame
    // actually covers the canvas, so the page colour shows through beforehand.
    if (!ALPHA && t > 0.995 && cover) {
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, cw, ch);
    }
    ctx.drawImage(img, x, y, w, h);
  }

  function progress() {
    var r = section.getBoundingClientRect();
    var total = section.offsetHeight - window.innerHeight;
    if (total <= 0) return reduce ? 1 : 0;
    return Math.min(1, Math.max(0, -r.top / total));
  }

  function tick() {
    rafId = 0;
    p = progress();
    section.style.setProperty("--nb-p", p.toFixed(4));   // drives the CSS: books part, wordmark fades
    target = p * (FRAME_COUNT - 1);
    current += (target - current) * 0.25;            // gentle easing between scroll steps
    if (Math.abs(target - current) < 0.3) current = target;

    var t = smoothstep(Math.min(1, p / GROW_UNTIL));
    var want = nearestReady(Math.round(current));
    if (want >= 0 && (want !== drawn || Math.abs(t - drawnT) > 0.001)) {
      draw(want, t);
      drawn = want; drawnT = t;
    }
    if (current !== target) requestTick();
  }
  function requestTick() { if (!rafId) rafId = requestAnimationFrame(tick); }

  window.addEventListener("scroll", requestTick, { passive: true });
  window.addEventListener("resize", function () { resize(); });
  if (reduce) { current = target = FRAME_COUNT - 1; }
  preload();
  if (reduce) load(FRAME_COUNT - 1);
  resize();
})();
