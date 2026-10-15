/* The album hero.
 *
 * The scroll does not drive the frames freely. The section is six full-height
 * stops, one per settled spread, and CSS scroll snapping makes the browser
 * land on one of them. That is what gives "a gesture completes a flip": you
 * can drag through the middle of a turn, but you cannot come to rest there -
 * the snap carries you forward or back to a settled page. Doing it with native
 * snapping rather than by intercepting wheel events keeps trackpad momentum,
 * touch, keyboard and the scrollbar all working as they should.
 *
 * Between two stops the scroll position maps onto the frame range for that
 * turn, eased, so the page sweeps over rather than running at a constant rate.
 */
(function () {
  var section = document.querySelector("[data-album]");
  if (!section) return;

  /* Browsers restore the previous scroll position on reload, which dropped the
     visitor into the middle of an open spread with no idea how they got there.
     The album is meant to start closed. */
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  window.scrollTo(0, 0);
  window.addEventListener("load", function () { window.scrollTo(0, 0); });

  var canvas = section.querySelector("[data-canvas]");
  var ctx = canvas.getContext("2d");
  var intro = section.querySelector("[data-intro]");
  var cue = section.querySelector("[data-cue]");
  var cta = section.querySelector("[data-cta]");
  var caption = section.querySelector("[data-caption]");

  var COUNT = parseInt(section.getAttribute("data-count"), 10) || 292;
  var BASE = section.getAttribute("data-frames") || "assets/frames/";
  var STOPS = section.getAttribute("data-stops").split(",").map(Number);
  var SEGMENTS = STOPS.length - 1;

  /* What each spread is, for the caption and the gallery that opens from it. */
  var SPREADS = [
    { title: "Petals & prayers", note: "The ceremony" },
    { title: "Quiet grace", note: "Portraits" },
    { title: "The two of you", note: "Together" },
    { title: "Light & detail", note: "The bride" },
    { title: "Golden hour", note: "After the day" }
  ];

  /* The canvas is laid out in CSS pixels but painted in device pixels, so the
     bitmap has to be chosen against both. Picking on screen size alone left a
     retina laptop upscaling a 1400px frame by about 1.7, which is why the book
     looked soft next to the rest of the page. */
  var TIERS = [
    { dir: "mobile/", w: 840, h: 630 },
    { dir: "desktop/", w: 1400, h: 1050 },
    { dir: "xl/", w: 2400, h: 1800 }
  ];
  function pickTier() {
    var vw = window.innerWidth, vh = window.innerHeight;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var byHeight = (Math.max(vh * 0.45, vh - 250) / 0.926) * (4 / 3);
    // the widest the canvas ever gets, which is while the book is closed
    var widest = Math.max(Math.min((vw * 0.74) / 0.486, byHeight),
                          Math.min((vw * 0.92) / 0.917, byHeight));
    var need = widest * dpr;
    for (var i = 0; i < TIERS.length; i++) if (TIERS[i].w >= need) return TIERS[i];
    return TIERS[TIERS.length - 1];
  }
  var tier = pickTier();
  var DIR = BASE.replace(new RegExp("/?$"), "/") + tier.dir;
  var IMG_W = tier.w, IMG_H = tier.h;
  canvas.width = IMG_W; canvas.height = IMG_H;

  var frames = new Array(COUNT), ready = new Array(COUNT);
  var drawn = -1, rafId = 0, state = 0, shownSpread = -1;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function src(i) { return DIR + String(i).padStart(4, "0") + ".webp"; }

  function load(i) {
    if (frames[i]) return;
    var im = new Image();
    im.decoding = "async";
    im.onload = function () { ready[i] = true; drawn = -1; tick(); };
    im.src = src(i);
    frames[i] = im;
  }

  /* The settled frames first - those are what a reader actually stops on -
     then a coarse pass, then everything, so a fast scroll always has
     something close to show.
  
     The bulk pass waits for the opening sequence. Decoding 292 frames saturates
     the main thread, which delayed the boot animation and the animationend that
     clears it: the mark sat there for ten seconds or more on a cold load. */
  STOPS.forEach(load);
  var bulkStarted = false;
  function preloadRest() {
    if (bulkStarted) return;
    bulkStarted = true;
    var order = [], step, i;
    for (step of [8, 4, 2, 1]) for (i = 1; i <= COUNT; i += step) order.push(i);
    var k = 0;
    (function next() {
      for (var n = 0; k < order.length && n < 12; n++) load(order[k++]);
      if (k < order.length) setTimeout(next, 28);
    })();
  }

  function nearest(i) {
    for (var d = 0; d < COUNT; d++) {
      if (i - d >= 1 && ready[i - d]) return i - d;
      if (i + d <= COUNT && ready[i + d]) return i + d;
    }
    return -1;
  }

  function easeInOut(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

  /* Measured off the frames: the closed book takes 48.6% of the frame width,
     an open spread 91.7%, and both about 92.6% of its height. A closed book
     can therefore be drawn far larger than an open one before anything runs
     off the screen - which is the difference between a phone showing a decent
     book and a postage stamp. The canvas is sized between those two as the
     cover opens, so it reads as the album coming toward you. */
  var CLOSED_SHARE = 0.486, OPEN_SHARE = 0.917, H_SHARE = 0.926;
  var TOP_CHROME = 100, BOT_CHROME = 150;   // header + a gap, title + button + a gap
  var sizedAt = -1;
  function sizeCanvas(t) {
    if (Math.abs(t - sizedAt) < 0.004) return;
    sizedAt = t;
    var vw = window.innerWidth, vh = window.innerHeight;
    // The book has to clear the fixed header above it and the spread title and
    // gallery button below it. Budgeting against the full viewport height ran
    // the cover under the nav and put the button on the leather. The band is
    // not centred on the screen either, so the canvas is nudged up by half the
    // difference rather than being centred on the viewport.
    // When the two phrases stack above the book they take a variable amount of
    // room, so the clearance is measured rather than assumed - a fixed figure
    // is what let the text clip the cover on tablets.
    var top = TOP_CHROME;
    if (!window.matchMedia("(min-width: 980px)").matches) {
      var lowest = 0;
      [].forEach.call(section.querySelectorAll(".album__intro"), function (el) {
        lowest = Math.max(lowest, el.getBoundingClientRect().bottom);
      });
      if (lowest) top = Math.max(TOP_CHROME, lowest + 18);
    }
    var band = Math.max(vh * 0.45, vh - top - BOT_CHROME);
    var byHeight = (band / H_SHARE) * (4 / 3);
    canvas.style.setProperty("--shift", ((BOT_CHROME - top) / 2) + "px");
    // different margins either side of the turn: a closed book wants air
    // around it, an open spread wants the width it can get
    var closed = Math.min((vw * 0.74) / CLOSED_SHARE, byHeight);
    var open = Math.min((vw * 0.92) / OPEN_SHARE, byHeight);
    canvas.style.width = (closed + (open - closed) * t) + "px";
  }

  function progress() {
    var r = section.getBoundingClientRect();
    var travel = section.offsetHeight - window.innerHeight;
    if (travel <= 0) return 0;
    return Math.min(1, Math.max(0, -r.top / travel));
  }

  function setState(next) {
    if (next === state && section.hasAttribute("data-state")) return;
    state = next;
    section.setAttribute("data-state", String(state));
  }

  function tick() {
    rafId = 0;
    var p = progress();
    var seg = p * SEGMENTS;
    var i = Math.min(SEGMENTS - 1, Math.floor(seg));
    var t = seg - i;

    sizeCanvas(easeInOut(Math.min(1, seg)));

    // Linear within a segment, deliberately. Easing here flattens the rate to
    // zero at both ends of every turn, which under a steady scroll reads as
    // the book stopping at each spread. The renders already carry their own
    // hold frames, so the settling is in the footage rather than the mapping.
    var want = Math.round(STOPS[i] + (STOPS[i + 1] - STOPS[i]) * t);
    var use = nearest(want);
    if (use > 0 && use !== drawn) {
      ctx.clearRect(0, 0, IMG_W, IMG_H);           // the frames carry alpha
      ctx.drawImage(frames[use], 0, 0, IMG_W, IMG_H);
      drawn = use;
    }

    // The intro wordmark belongs to the closed book only.
    section.style.setProperty("--introFade", String(Math.max(0, 1 - seg * 2.2)));
    section.style.setProperty("--cueFade", String(Math.max(0, 1 - seg * 1.6)));

    // The button stays put and only its title changes. Fading it in and out at
    // every spread was the other thing making the scroll feel like it stuttered.
    var nearestStop = Math.round(seg);
    setState(nearestStop);
    var which = Math.min(SPREADS.length, Math.max(1, nearestStop));
    if (which !== shownSpread) {
      shownSpread = which;
      if (caption) caption.textContent = SPREADS[which - 1].title;
      cta.setAttribute("data-spread", String(which));
    }
    // There is nothing to show a gallery of until the cover is open, so it
    // arrives once - as the cover lands - and then stays, title changing.
    var open = seg > 0.8;
    cta.classList.toggle("is-on", open);
    cta.setAttribute("aria-hidden", String(!open));
  }

  function request() { if (!rafId) rafId = requestAnimationFrame(tick); }

  function fit() {
    sizedAt = -1;
    drawn = -1;
    request();
  }

  /* The deboss sits at about 23.5% of the frame width, dead centre: the cover
     is 55.3% of the frame and the mark is 46% of the cover. Measuring it off
     the live canvas keeps the landing true at any size. */
  sizeCanvas(0);

  (function boot() {
    var el = document.querySelector("[data-boot]");
    if (!el || reduce) { if (el) el.remove(); preloadRest(); return; }
    var mark = el.querySelector(".boot__logo");
    function size() {
      var w = canvas.getBoundingClientRect().width;
      if (!w) return;
      var target = w * 0.235;
      var start = Math.min(window.innerWidth * 0.46, 430);
      mark.style.setProperty("--bootTarget", target + "px");
      mark.style.setProperty("--bootScale", String(Math.max(1.2, start / target)));
    }
    size();
    window.addEventListener("resize", size);
    function done() {
      if (el.parentNode) el.remove();
      preloadRest();
    }
    el.addEventListener("animationend", done);
    // A CSS animation does not begin until the first paint, so a timer started
    // at script time can expire before the sequence has even been seen - in a
    // background tab that is seconds out. The fallback waits for a frame to be
    // painted and only then starts its clock.
    requestAnimationFrame(function () { setTimeout(done, 3000); });
    // And a hard ceiling. If the page never paints - a tab left in the
    // background, a window behind another - neither the animation nor the
    // frame callback above ever runs, and without this the veil would cover
    // the site indefinitely.
    setTimeout(done, 8000);
  })();

  setState(0);
  window.addEventListener("scroll", function () { request(); fit(); }, { passive: true });
  window.addEventListener("resize", fit);
  fit();

  /* Keyboard: arrows and page keys move one spread at a time. */
  window.addEventListener("keydown", function (e) {
    var r = section.getBoundingClientRect();
    if (r.top > 1 || r.bottom < window.innerHeight) return;
    var dir = 0;
    if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === " ") dir = 1;
    if (e.key === "ArrowUp" || e.key === "PageUp") dir = -1;
    if (!dir) return;
    var to = Math.min(SEGMENTS, Math.max(0, state + dir));
    if (to === state) return;
    e.preventDefault();
    var travel = section.offsetHeight - window.innerHeight;
    window.scrollTo({ top: section.offsetTop + (travel * to) / SEGMENTS,
                      behavior: reduce ? "auto" : "smooth" });
  });

  window.NB_ALBUM = { spreads: SPREADS, stops: STOPS };
})();
