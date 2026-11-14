// EduNest – premium behaviour layer.
// 1) wraps draw() so other modules can run code after every render (window.__afterDraw)
// 2) page-enter animation only when the VIEW changes (not on every click)
// 3) cursor-follow glow on cards (inspired by the Cerebromark "aurora" effect)
(() => {
  window.__afterDraw = window.__afterDraw || [];
  let lastView = null;
  const original = draw;
  draw = function () {
    original();
    const pad = document.querySelector(".pad");
    if (pad && S.view !== lastView) {
      pad.classList.add("enter");
      setTimeout(() => pad.classList.remove("enter"), 900);
      window.scrollTo({ top: 0 });
    }
    lastView = S.view;
    window.__afterDraw.forEach(fn => { try { fn(); } catch (e) { console.error(e); } });
  };
  document.addEventListener("pointermove", e => {
    const c = e.target.closest && e.target.closest(".card");
    if (!c) return;
    const r = c.getBoundingClientRect();
    c.style.setProperty("--mx", e.clientX - r.left + "px");
    c.style.setProperty("--my", e.clientY - r.top + "px");
  }, { passive: true });
})();
