/* Header, navigation, the portfolio grid, the gallery and the enquiry form. */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };

  /* ------------------------------- header ------------------------------ */
  var head = $("[data-head]");
  function onScroll() { head.classList.toggle("is-solid", window.scrollY > 40); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  var burger = $("[data-burger]"), nav = $("[data-nav]");
  if (burger && nav) {
    burger.addEventListener("click", function () {
      var open = burger.getAttribute("aria-expanded") === "true";
      burger.setAttribute("aria-expanded", String(!open));
      nav.classList.toggle("is-open", !open);
      head.classList.toggle("menu-open", !open);
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName !== "A") return;
      burger.setAttribute("aria-expanded", "false");
      nav.classList.remove("is-open");
      head.classList.remove("menu-open");
    });
  }

  /* which section the nav should highlight */
  var sections = ["about", "work", "contact"].map(function (id) { return document.getElementById(id); }).filter(Boolean);
  var links = {};
  $$(".nav a").forEach(function (a) { links[a.getAttribute("href").replace("#", "")] = a; });
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var a = links[en.target.id];
        if (a) a.setAttribute("aria-current", String(en.isIntersecting && en.intersectionRatio > 0.4));
      });
    }, { threshold: [0, 0.4, 1] });
    sections.forEach(function (s) { io.observe(s); });
  }

  var year = $("[data-year]");
  if (year) year.textContent = String(new Date().getFullYear());

  /* ------------------------------ gallery ------------------------------ */
  var PHOTOS = [];
  var lb = $("[data-lightbox]");
  var lbImg = $("[data-lb-img]"), lbCap = $("[data-lb-cap]");
  var lbTitle = $("[data-lb-title]"), lbThumbs = $("[data-lb-thumbs]");
  var at = 0, lastFocus = null;

  function biggest(p) { return "assets/img/" + p.srcset[p.srcset.length - 1].file; }
  function smallest(p) { return "assets/img/" + p.srcset[0].file; }
  function srcset(p) {
    return p.srcset.map(function (s) { return "assets/img/" + s.file + " " + s.w + "w"; }).join(", ");
  }

  function show(i) {
    if (!PHOTOS.length) return;
    at = (i + PHOTOS.length) % PHOTOS.length;
    var p = PHOTOS[at];
    lbImg.src = biggest(p);
    lbImg.alt = p.alt;
    lbCap.textContent = p.alt;
    $$("button", lbThumbs).forEach(function (b, n) { b.setAttribute("aria-current", String(n === at)); });
  }

  function openGallery(spread) {
    if (!PHOTOS.length) return;
    lastFocus = document.activeElement;
    var meta = (window.NB_ALBUM && window.NB_ALBUM.spreads[spread - 1]) || null;
    lbTitle.textContent = meta ? meta.title + " — " + meta.note : "Selected work";
    lb.hidden = false;
    document.body.style.overflow = "hidden";
    show(0);
    $("[data-lb-close]").focus();
  }
  function closeGallery() {
    lb.hidden = true;
    document.body.style.overflow = "";
    if (lastFocus) lastFocus.focus();
  }

  $("[data-lb-close]").addEventListener("click", closeGallery);
  $("[data-lb-prev]").addEventListener("click", function () { show(at - 1); });
  $("[data-lb-next]").addEventListener("click", function () { show(at + 1); });
  lb.addEventListener("click", function (e) { if (e.target === lb) closeGallery(); });
  window.addEventListener("keydown", function (e) {
    if (lb.hidden) return;
    if (e.key === "Escape") closeGallery();
    if (e.key === "ArrowRight") show(at + 1);
    if (e.key === "ArrowLeft") show(at - 1);
  });

  fetch("assets/img/photos.json")
    .then(function (r) { return r.json(); })
    .then(function (list) {
      PHOTOS = list;

      var grid = $("[data-grid]");
      if (grid) {
        PHOTOS.forEach(function (p, i) {
          var b = document.createElement("button");
          b.type = "button";
          b.setAttribute("aria-label", "Open gallery at " + p.alt);
          var im = document.createElement("img");
          im.src = smallest(p);
          im.srcset = srcset(p);
          im.sizes = "(max-width: 720px) 100vw, (max-width: 900px) 50vw, 33vw";
          im.alt = p.alt;
          im.loading = "lazy";
          im.width = p.w; im.height = p.h;
          b.appendChild(im);
          b.addEventListener("click", function () { openGallery(0); show(i); });
          grid.appendChild(b);
        });
      }

      PHOTOS.forEach(function (p, i) {
        var li = document.createElement("li");
        var b = document.createElement("button");
        b.type = "button";
        b.setAttribute("aria-label", p.alt);
        var im = document.createElement("img");
        im.src = smallest(p); im.alt = ""; im.loading = "lazy";
        b.appendChild(im);
        b.addEventListener("click", function () { show(i); });
        li.appendChild(b);
        lbThumbs.appendChild(li);
      });
    })
    .catch(function () { /* the grid simply stays empty rather than erroring */ });

  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-open-gallery]") : null;
    if (!t) return;
    var host = t.closest("[data-spread]");
    openGallery(host ? parseInt(host.getAttribute("data-spread"), 10) : 0);
  });

  /* -------------------------------- form ------------------------------- */
  var form = $(".form");
  if (form) {
    var status = $(".form__status", form);
    var stub = form.hasAttribute("data-form-stub");
    form.addEventListener("submit", function (e) {
      if (!form.checkValidity()) {
        e.preventDefault();
        status.className = "form__status err";
        status.textContent = "Please fill in the fields marked with a star.";
        form.reportValidity();
        return;
      }
      if (stub) {
        // No backend is connected. Saying "sent" here would be a lie to anyone
        // who finds the site, and a silent one - the enquiry simply vanishes.
        e.preventDefault();
        var to = (document.querySelector('.contact__list a[href^="mailto:"]') || {}).textContent || "";
        status.className = "form__status err";
        status.textContent = "This form is not connected yet — please email " +
          (to.trim() || "us") + " directly.";
        return;
      }
      status.className = "form__status";
      status.textContent = "Sending…";
    });
  }
})();
