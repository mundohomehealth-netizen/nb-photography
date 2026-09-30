/* NB Photography - site interactions */
(function () {
  // Header: transparent over the album, solid afterwards
  var header = document.querySelector("[data-header]");
  var hero = document.querySelector("[data-nb-hero]");
  function headerState() {
    var solid = !hero || hero.getBoundingClientRect().bottom <= header.offsetHeight + 1;
    header.classList.toggle("is-solid", solid);
  }
  window.addEventListener("scroll", headerState, { passive: true });
  headerState();

  // Mobile menu
  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.querySelector("[data-nav]");
  function setMenu(open) {
    toggle.setAttribute("aria-expanded", String(open));
    nav.classList.toggle("is-open", open);
    header.classList.toggle("menu-open", open);
  }
  toggle.addEventListener("click", function () { setMenu(toggle.getAttribute("aria-expanded") !== "true"); });
  nav.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") setMenu(false); });

  // Portfolio filters
  var shots = Array.prototype.slice.call(document.querySelectorAll(".shot"));
  document.querySelectorAll("[data-filter]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var f = btn.getAttribute("data-filter");
      document.querySelectorAll("[data-filter]").forEach(function (b) {
        var on = b === btn; b.classList.toggle("is-active", on); b.setAttribute("aria-pressed", String(on));
      });
      shots.forEach(function (s) { s.hidden = !(f === "all" || s.getAttribute("data-category") === f); });
    });
  });

  // Lightbox
  var lb = document.querySelector("[data-lightbox]");
  var lbImg = lb.querySelector("[data-lb-img]");
  var lbCap = lb.querySelector("[data-lb-cap]");
  var idx = 0;
  function visible() { return shots.filter(function (s) { return !s.hidden; }); }
  function show(i) {
    var list = visible(); if (!list.length) return;
    idx = (i + list.length) % list.length;
    var s = list[idx], img = s.querySelector("img");
    lbImg.src = s.querySelector("[data-full]").getAttribute("data-full");
    lbImg.alt = img.alt;
    lbCap.textContent = s.querySelector("figcaption").lastChild.textContent.trim();
  }
  shots.forEach(function (s) {
    s.querySelector("[data-full]").addEventListener("click", function () {
      show(visible().indexOf(s));
      if (lb.showModal) lb.showModal(); else lb.setAttribute("open", "");
    });
  });
  lb.querySelector("[data-lb-prev]").addEventListener("click", function () { show(idx - 1); });
  lb.querySelector("[data-lb-next]").addEventListener("click", function () { show(idx + 1); });
  lb.querySelector("[data-lb-close]").addEventListener("click", function () { lb.close(); });
  lb.addEventListener("click", function (e) { if (e.target === lb) lb.close(); });
  lb.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") show(idx - 1);
    if (e.key === "ArrowRight") show(idx + 1);
  });

  // "Enquire" buttons preselect the collection in the form
  var select = document.querySelector("[data-package-select]");
  document.querySelectorAll("[data-package]").forEach(function (a) {
    a.addEventListener("click", function () { if (select) select.value = a.getAttribute("data-package"); });
  });

  var y = document.querySelector("[data-year]");
  if (y) y.textContent = new Date().getFullYear();
})();
