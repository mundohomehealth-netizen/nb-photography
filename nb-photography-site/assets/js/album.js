/* NB album - scroll-driven hero (no libraries needed)
   Scrolling down plays the frames forward; scrolling up plays them backward. */
(function () {
  var section = document.querySelector("[data-nb-hero]");
  if (!section) return;

  var FRAME_COUNT = parseInt(section.getAttribute("data-frame-count") || "248", 10);
  var BASE = section.getAttribute("data-frames-path") || "frames/";   // folder that holds desktop/ and mobile/
  var BG = getComputedStyle(section).getPropertyValue("--nb-bg").trim() || "#b9aea0";
  var small = Math.min(window.screen.width, window.screen.height) < 700;
  var DIR = BASE.replace(/\/?$/, "/") + (small ? "mobile/" : "desktop/");
  var IMG_W = small ? 960 : 1600, IMG_H = small ? 540 : 900;

  var canvas = section.querySelector("canvas");
  var ctx = canvas.getContext("2d");
  ctx.fillStyle = BG;                                   // normalise the colour to #rrggbb
  // one-pixel-tall strips of the table colour, used to extend the frame on tall screens
  function strip() { var c = document.createElement("canvas"); c.width = 48; c.height = 1; return c; }
  var topStrip = strip(), bottomStrip = strip(), edgeReady = false;
  var frames = new Array(FRAME_COUNT);
  var ready = new Array(FRAME_COUNT);
  var current = 0, target = 0, drawn = -1, rafId = 0;
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

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(canvas.clientWidth * dpr);
    canvas.height = Math.round(canvas.clientHeight * dpr);
    drawn = -1;
    requestTick();
  }

  function draw(i) {
    var img = frames[i];
    var cw = canvas.width, ch = canvas.height;
    // Wide screens: fill edge to edge. Tall screens (phones): fit the whole book.
    var cover = cw / ch >= 1.5;
    var s = cover ? Math.max(cw / IMG_W, ch / IMG_H) : Math.min(cw / IMG_W, ch / IMG_H);
    var w = IMG_W * s, h = IMG_H * s, x = (cw - w) / 2, y = (ch - h) / 2;
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, cw, ch);
    ctx.drawImage(img, x, y, w, h);
    if (y > 1) {
      // Phones: extend the table surface above and below the frame by stretching a
      // softened copy of the frame's top and bottom rows, so there is no visible seam.
      if (!edgeReady && ready[0]) {                     // sample the plain table from the first frame
        topStrip.getContext("2d").drawImage(frames[0], 0, 0, IMG_W, 3, 0, 0, 48, 1);
        bottomStrip.getContext("2d").drawImage(frames[0], 0, IMG_H - 3, IMG_W, 3, 0, 0, 48, 1);
        edgeReady = true;
      }
      ctx.drawImage(topStrip, x, 0, w, y + 1);
      ctx.drawImage(bottomStrip, x, y + h - 1, w, ch - (y + h) + 1);
    }
  }

  function progress() {
    var r = section.getBoundingClientRect();
    var total = section.offsetHeight - window.innerHeight;
    if (total <= 0) return reduce ? 1 : 0;
    return Math.min(1, Math.max(0, -r.top / total));
  }

  function tick() {
    rafId = 0;
    var p = progress();
    section.style.setProperty("--nb-p", p.toFixed(4));   // lets CSS fade the intro text
    target = p * (FRAME_COUNT - 1);
    current += (target - current) * 0.25;            // gentle easing between scroll steps
    if (Math.abs(target - current) < 0.3) current = target;
    var want = nearestReady(Math.round(current));
    if (want >= 0 && want !== drawn) { draw(want); drawn = want; }
    if (current !== target) requestTick();
  }
  function requestTick() { if (!rafId) rafId = requestAnimationFrame(tick); }

  window.addEventListener("scroll", requestTick, { passive: true });
  window.addEventListener("resize", resize);
  if (reduce) { current = target = FRAME_COUNT - 1; }
  preload();
  if (reduce) load(FRAME_COUNT - 1);
  resize();
})();
