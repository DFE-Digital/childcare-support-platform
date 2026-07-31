// Manages open/close animation for the provider JSON panel.
//
// Dash sets className to:
//   "provider-panel-ready" — show element off-screen, then animate in
//   "provider-panel-closing" — animate out, then hide
//
// This script handles the intermediate transitions:
//   ready → (one frame) → open
//   closing → (after animation) → closed
(function () {
  function setup() {
    var panel = document.getElementById("provider-modal");
    if (!panel) {
      setTimeout(setup, 200);
      return;
    }

    var observer = new MutationObserver(function () {
      var cls = panel.className;

      if (cls.indexOf("provider-panel-ready") !== -1) {
        // Force the browser to paint the off-screen state,
        // then swap to open to trigger the CSS transition.
        void panel.offsetHeight;
        requestAnimationFrame(function () {
          panel.className = "provider-panel-open";
        });
      }

      if (cls.indexOf("provider-panel-closing") !== -1) {
        setTimeout(function () {
          if (panel.className.indexOf("provider-panel-closing") !== -1) {
            panel.className = "provider-panel-closed";
          }
        }, 250);
      }
    });

    observer.observe(panel, {
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  if (document.readyState === "complete") {
    setTimeout(setup, 500);
  } else {
    window.addEventListener("load", function () {
      setTimeout(setup, 500);
    });
  }
})();
