/* The album hero.
 *
 * The frames are a cut of the hero clip - the closed cover, the case opening,
 * and six spreads with a page turn between each - renumbered so there are no
 * dead stretches. The section is seven stops; between two of them the scroll
 * position maps straight onto that turn's frame range.
 *
 * Two canvases are painted from the same frame. The front one is the frame
 * itself, fitted so an open spread is never cropped. The back one is the same
 * image drawn into a 160px bitmap and stretched over the whole stage under a
 * CSS blur, which fills whatever margin a 9:16 frame leaves in a window that
 * is never 9:16. It costs one extra drawImage into a tiny canvas per frame.
 *
 * Sizing is left to CSS; the media queries live in the stylesheet and there
 * is no measuring here beyond picking a bitmap tier and placing the opening
 * mark.
 */
(function () {
  var section = document.querySelector("[data-album]");
  if (!section) return;

  /* Browsers restore the previous scroll position on reload, which dropped
     the visitor into the middle of a turn with no idea how they got there.
     The album is meant to start on the closed cover. */
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  // One reset is not enough: the restore can land after load, and a bfcache
  // return skips load altogether. Held briefly, then released.
  var holdUntil = 0;
  function toTop() { window.scrollTo(0, 0); }
  function holdTop(ms) {
    holdUntil = Date.now() + ms;
    toTop();
    (function again() {
      if (Date.now() > holdUntil) return;
      toTop();
      requestAnimationFrame(again);
      setTimeout(again, 60);            // rAF alone stalls in a hidden tab
    })();
  }
  holdTop(600);
  window.addEventListener("load", function () { holdTop(400); });
  window.addEventListener("pageshow", function (e) { if (e.persisted) holdTop(400); });

  var canvas = section.querySelector("[data-canvas]");
  var ctx = canvas.getContext("2d");
  var fill = section.querySelector("[data-fill]");
  var fctx = fill ? fill.getContext("2d") : null;
  var cta = section.querySelector("[data-cta]");
  var caption = section.querySelector("[data-caption]");

  var COUNT = parseInt(section.getAttribute("data-count"), 10) || 245;
  var BASE = section.getAttribute("data-frames") || "assets/hero/";
  var STOPS = section.getAttribute("data-stops").split(",").map(Number);
  var SEGMENTS = STOPS.length - 1;

  /* Stop 1 is the closed cover, so the spreads begin at stop 2. */
  var SPREADS = [
    { title: "Petals & prayers", note: "The ceremony" },
    { title: "Quiet grace", note: "Portraits" },
    { title: "In full colour", note: "The bride" },
    { title: "Golden hour", note: "After the day" },
    { title: "Soft light", note: "Portraits" },
    { title: "Under the marigolds", note: "Celebration" }
  ];

  /* The canvas is laid out in CSS pixels but painted in device pixels, so the
     bitmap is chosen against the box CSS actually gave it times the display
     density. Picking on viewport alone left a phone at 3x upscaling. */
  var TIERS = [
    { dir: "sm/", w: 540 },
    { dir: "md/", w: 810 },
    { dir: "lg/", w: 1080 }
  ];
  function pickTier() {
    var box = canvas.getBoundingClientRect().width || window.innerWidth;
    var need = box * Math.min(window.devicePixelRatio || 1, 3);
    for (var i = 0; i < TIERS.length; i++) if (TIERS[i].w >= need) return TIERS[i];
    return TIERS[TIERS.length - 1];
  }
  var tier = pickTier();
  var DIR = BASE.replace(new RegExp("/?$"), "/") + tier.dir;
  var IMG_W = tier.w, IMG_H = Math.round(tier.w * 1920 / 1080);
  canvas.width = IMG_W; canvas.height = IMG_H;

  var frames = new Array(COUNT + 1), ready = new Array(COUNT + 1);
  var drawn = -1, rafId = 0, state = -1, shownSpread = -1;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function load(i) {
    if (frames[i]) return;
    var im = new Image();
    im.decoding = "async";
    im.onload = function () { ready[i] = true; drawn = -1; request(); };
    im.src = DIR + String(i).padStart(4, "0") + ".webp";
    frames[i] = im;
  }

  /* The settled frames first - those are what a reader stops on - then a
     coarse pass, then everything, so a fast scroll always has something
     close to show. The bulk pass waits for the opening animation: decoding
     the whole sequence saturates the main thread, which was what left the
     mark sitting on screen for ten seconds on a cold load. */
  STOPS.forEach(load);
  var bulkStarted = false;
  function preloadRest() {
    if (bulkStarted) return;
    bulkStarted = true;
    var order = [], i, s;
    var steps = [8, 4, 2, 1];
    for (s = 0; s < steps.length; s++) {
      for (i = 1; i <= COUNT; i += steps[s]) order.push(i);
    }
    var k = 0;
    (function next() {
      for (var n = 0; k < order.length && n < 10; n++) load(order[k++]);
      if (k < order.length) setTimeout(next, 30);
    })();
  }

  function nearest(i) {
    for (var d = 0; d < COUNT; d++) {
      if (i - d >= 1 && ready[i - d]) return i - d;
      if (i + d <= COUNT && ready[i + d]) return i + d;
    }
    return -1;
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

    // Linear within a segment, deliberately. Easing here flattens the rate to
    // zero at both ends of every turn, which under a steady scroll reads as
    // the book stopping. The cut already keeps a beat of stillness at each
    // spread, so the settling is in the footage rather than in the mapping.
    var want = Math.round(STOPS[i] + (STOPS[i + 1] - STOPS[i]) * t);

    var use = nearest(want);
    if (use > 0 && use !== drawn) {
      ctx.drawImage(frames[use], 0, 0, IMG_W, IMG_H);
      if (fctx) fctx.drawImage(frames[use], 0, 0, fill.width, fill.height);
      drawn = use;
    }

    // Both belong to the closed cover. The cover swings up through the top
    // of the frame as it opens, straight across the headline, so the words
    // go before it gets there rather than being overlapped by it.
    section.style.setProperty("--cueFade", String(Math.max(0, 1 - seg * 1.3)));
    section.style.setProperty("--heroFade", String(Math.max(0, 1 - seg * 1.6)));

    var nearestStop = Math.round(seg);
    setState(nearestStop);

    // There is nothing to show a gallery of until the cover is open, so the
    // button arrives as the first spread lands and then stays, title
    // changing. Fading it per spread was what made the scroll feel like it
    // stuttered.
    var open = seg > 0.85;
    cta.classList.toggle("is-on", open);
    cta.setAttribute("aria-hidden", String(!open));

    var which = Math.min(SPREADS.length, Math.max(1, nearestStop));
    if (which !== shownSpread) {
      shownSpread = which;
      if (caption) caption.textContent = SPREADS[which - 1].title;
      cta.setAttribute("data-spread", String(which));
    }
  }

  function request() { if (!rafId) rafId = requestAnimationFrame(tick); }

  function fit() {
    drawn = -1;
    if (placeBoot) placeBoot();
    request();
  }

  /* Where the opening mark has to land, as fractions of the CANVAS - the
     frame box, not the window. The canvas is anchored to the bottom of the
     stage and can run past its top, so anything measured against the
     viewport lands in the wrong place.

     Read off frame 1: the cover occupies x 0.158-0.895 and y 0.259-0.771 of
     the frame, and the mark sits above the middle of it. These three were
     then checked by drawing the mark's box back onto the frame and nudged
     until it sat over the deboss.

     They cannot be exact. The mark on the cover is about 1.34 times as wide
     as it is tall and the logo file is 1.61, so the two lockups are not the
     same drawing; matching the centre and the width is as close as it goes,
     and the mark is fading out as it arrives. */
  var DEBOSS_W = 0.202, DEBOSS_CX = 0.544, DEBOSS_CY = 0.400;
  var placeBoot = null;

  (function boot() {
    var el = document.querySelector("[data-boot]");
    if (!el || reduce) { if (el) el.remove(); preloadRest(); return; }
    var mark = el.querySelector(".boot__logo");
    var markAspect = (parseFloat(mark.getAttribute("width")) || 657) /
                     (parseFloat(mark.getAttribute("height")) || 408);
    function size() {
      var r = canvas.getBoundingClientRect();
      if (!r.width) return;
      var w = r.width * DEBOSS_W;
      var h = w / markAspect;
      mark.style.width = w + "px";
      mark.style.left = (r.left + r.width * DEBOSS_CX - w / 2) + "px";
      mark.style.top = (r.top + r.height * DEBOSS_CY - h / 2) + "px";
      // A fixed multiple of where it lands, so the travel reads the same on
      // every screen. The absolute caps only matter when the screen is too
      // small to show the mark at that size.
      var start = Math.min(w * 2.2, window.innerWidth * 0.74, window.innerHeight * 0.4);
      mark.style.setProperty("--bootScale", String(Math.max(1.2, start / w)));
    }
    placeBoot = size;
    size();
    window.addEventListener("resize", size);
    function done() {
      if (el.parentNode) el.remove();
      placeBoot = null;
      preloadRest();
    }
    el.addEventListener("animationend", done);
    // A CSS animation does not begin until the first paint, so a timer
    // started at script time can expire before the sequence has been seen.
    // This one waits for a painted frame and only then starts its clock.
    requestAnimationFrame(function () { setTimeout(done, 2800); });
    // And a hard ceiling, for a tab that never paints at all.
    setTimeout(done, 8000);
  })();

  setState(0);
  window.addEventListener("scroll", request, { passive: true });
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
