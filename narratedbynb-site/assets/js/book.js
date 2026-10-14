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

  var canvas = section.querySelector("[data-canvas]");
  var ctx = canvas.getContext("2d");
  var intro = section.querySelector("[data-intro]");
  var cue = section.querySelector("[data-cue]");
  var cta = section.querySelector("[data-cta]");
  var caption = section.querySelector("[data-caption]");
  var dotList = section.querySelector("[data-dots]");

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

  var small = Math.min(window.screen.width, window.screen.height) < 820;
  var DIR = BASE.replace(/\/?$/, "/") + (small ? "mobile/" : "desktop/");
  var IMG_W = small ? 840 : 1400, IMG_H = small ? 630 : 1050;
  canvas.width = IMG_W; canvas.height = IMG_H;

  var frames = new Array(COUNT), ready = new Array(COUNT);
  var drawn = -1, rafId = 0, state = 0;
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
     something close to show. */
  (function preload() {
    STOPS.forEach(load);
    var order = [], step, i;
    for (step of [8, 4, 2, 1]) for (i = 1; i <= COUNT; i += step) order.push(i);
    var k = 0;
    (function next() {
      for (var n = 0; k < order.length && n < 12; n++) load(order[k++]);
      if (k < order.length) setTimeout(next, 28);
    })();
  })();

  function nearest(i) {
    for (var d = 0; d < COUNT; d++) {
      if (i - d >= 1 && ready[i - d]) return i - d;
      if (i + d <= COUNT && ready[i + d]) return i + d;
    }
    return -1;
  }

  function easeInOut(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }

  function progress() {
    var r = section.getBoundingClientRect();
    var travel = section.offsetHeight - window.innerHeight;
    if (travel <= 0) return 0;
    return Math.min(1, Math.max(0, -r.top / travel));
  }

  function buildDots() {
    if (!dotList) return;
    STOPS.forEach(function (_, i) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-label", i === 0 ? "Closed album" : "Spread " + i);
      b.addEventListener("click", function () {
        var travel = section.offsetHeight - window.innerHeight;
        // "auto" on purpose: while snapping is on, a smooth scroll is
        // cancelled by the snap. The snap animates the move instead.
        window.scrollTo({ top: section.offsetTop + (travel * i) / SEGMENTS, behavior: "auto" });
      });
      li.appendChild(b);
      dotList.appendChild(li);
    });
  }

  function setState(next) {
    if (next === state && section.hasAttribute("data-state")) return;
    state = next;
    if (dotList) {
      [].forEach.call(dotList.querySelectorAll("button"), function (b, i) {
        b.setAttribute("aria-current", String(i === state));
      });
    }
    section.setAttribute("data-state", String(state));
  }

  function tick() {
    rafId = 0;
    var p = progress();
    var seg = p * SEGMENTS;
    var i = Math.min(SEGMENTS - 1, Math.floor(seg));
    var t = seg - i;

    var want = Math.round(STOPS[i] + (STOPS[i + 1] - STOPS[i]) * easeInOut(t));
    var use = nearest(want);
    if (use > 0 && use !== drawn) {
      ctx.clearRect(0, 0, IMG_W, IMG_H);           // the frames carry alpha
      ctx.drawImage(frames[use], 0, 0, IMG_W, IMG_H);
      drawn = use;
    }

    // The intro wordmark belongs to the closed book only.
    section.style.setProperty("--introFade", String(Math.max(0, 1 - seg * 2.2)));
    section.style.setProperty("--cueFade", String(Math.max(0, 1 - seg * 1.6)));

    // Settled is within a little of a stop; a gallery button has no business
    // appearing while a page is still in the air.
    var nearestStop = Math.round(seg);
    var settled = Math.abs(seg - nearestStop) < 0.12;
    setState(nearestStop);
    // Visibility is the class alone, so the fade can play both ways. The
    // earlier version only re-hid it when NOT settled, which left the button
    // stranded on the closed book - settled at stop 0 took the else branch
    // but never actually hid anything.
    var wantCta = settled && nearestStop >= 1;
    if (wantCta) {
      var meta = SPREADS[nearestStop - 1];
      if (caption && meta) caption.textContent = meta.title;
      cta.setAttribute("data-spread", String(nearestStop));
    }
    cta.classList.toggle("is-on", wantCta);
    cta.setAttribute("aria-hidden", String(!wantCta));
  }

  function request() { if (!rafId) rafId = requestAnimationFrame(tick); }

  function fit() {
    // Snapping is only wanted while the album owns the screen. Leaving it on
    // for the whole document would fight the sections underneath.
    var r = section.getBoundingClientRect();
    var active = r.top <= 1 && r.bottom > window.innerHeight * 1.02;
    // A nav jump has to pass straight through the album. Mandatory snap would
    // otherwise catch the scroll on its way past and strand it on a spread.
    var jumping = document.documentElement.classList.contains("nav-jump");
    document.documentElement.classList.toggle("snapping", active && !reduce && !jumping);
    drawn = -1;
    request();
  }

  buildDots();
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
    window.scrollTo({ top: section.offsetTop + (travel * to) / SEGMENTS, behavior: "auto" });
  });

  window.NB_ALBUM = { spreads: SPREADS, stops: STOPS };
})();
