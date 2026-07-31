// Checkbox toggle for field bar column visibility.
// Uses event delegation on #field-bars-container — survives Dash re-renders.
// Checkboxes are html.Div elements with class "field-checkbox".
(function () {
  var CHECKED_BG = "#1f77b4";
  var UNCHECKED_BG = "#fff";
  var CHECKED_BORDER = "1px solid #1f77b4";
  var UNCHECKED_BORDER = "1px solid #999";

  function isChecked(el) {
    return el.textContent.trim() === "✓";
  }

  function setChecked(el, checked) {
    el.textContent = checked ? "✓" : "";
    el.style.backgroundColor = checked ? CHECKED_BG : UNCHECKED_BG;
    el.style.border = checked ? CHECKED_BORDER : UNCHECKED_BORDER;
  }

  function pushState(container) {
    var boxes = container.querySelectorAll(".field-checkbox");
    var checked = [];
    for (var i = 0; i < boxes.length; i++) {
      if (isChecked(boxes[i])) {
        checked.push(boxes[i].id.replace("field-chk-", ""));
      }
    }
    window.dash_clientside.set_props("field-columns", {
      data: { fields: checked, _ts: Date.now() },
    });
  }

  function setup() {
    var container = document.getElementById("field-bars-container");
    if (!container) {
      setTimeout(setup, 200);
      return;
    }

    container.addEventListener("click", function (e) {
      var box = e.target.closest(".field-checkbox");
      if (!box) return;
      // Don't toggle locked (always-on) checkboxes.
      if (box.dataset.locked) return;
      // Don't toggle if this click is on a bar segment (handled elsewhere).
      if (e.target.closest(".bar-segment")) return;

      setChecked(box, !isChecked(box));
      pushState(container);

      // Stop propagation so the bar-segment click handler doesn't fire.
      e.stopPropagation();
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
