// Hover tooltip and click handling for the HTML field bars panel.
// Uses event delegation on #field-bars-container — survives Dash re-renders.
(function () {
  var lastMouse = { x: 0, y: 0 };

  document.addEventListener("mousemove", function (e) {
    lastMouse.x = e.clientX;
    lastMouse.y = e.clientY;
  });

  // Source family colour map for the tooltip badge.
  var BADGE_COLORS = {
    absent: "#d62728",
    unknown: "#c7c7c7",
    derived: "#8c8c8c",
  };

  function badgeColor(source) {
    if (BADGE_COLORS[source]) return BADGE_COLORS[source];
    if (source.indexOf("la_scrape") === 0 || source.indexOf("la_extract") === 0)
      return "#2ca02c";
    if (source.indexOf("ofsted") === 0) return "#1f77b4";
    if (source === "gias") return "#ff7f0e";
    if (source.indexOf("school") === 0) return "#9467bd";
    if (source.indexOf("os.") === 0 || source.indexOf("bbox:") === 0)
      return "#17becf";
    if (source === "free_breakfast") return "#bcbd22";
    return "#c7c7c7";
  }

  /** Read the segment metadata JSON from the hidden div. */
  function getSegmentData() {
    var el = document.getElementById("field-bars-data");
    if (!el || !el.textContent) return [];
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return [];
    }
  }

  /** Find the index of a .bar-segment element among all siblings in the container. */
  function segmentIndex(container, seg) {
    var all = container.querySelectorAll(".bar-segment");
    for (var i = 0; i < all.length; i++) {
      if (all[i] === seg) return i;
    }
    return -1;
  }

  function setup() {
    var container = document.getElementById("field-bars-container");
    var tip = document.getElementById("field-bars-hover");
    if (!container || !tip) {
      setTimeout(setup, 200);
      return;
    }

    // --- Hover ---
    container.addEventListener("mouseover", function (e) {
      var seg = e.target.closest(".bar-segment");
      if (!seg) return;
      var idx = segmentIndex(container, seg);
      var data = getSegmentData();
      if (idx < 0 || idx >= data.length) return;
      var d = data[idx];

      var bg = badgeColor(d.source);
      tip.textContent = "";
      var b = document.createElement("b");
      b.textContent = d.field;
      tip.appendChild(b);
      tip.appendChild(document.createTextNode(" "));
      var badge = document.createElement("span");
      badge.style.cssText =
        "background:" +
        bg +
        ";color:#fff;padding:1px 5px;border-radius:3px;font-size:11px";
      badge.textContent = d.source;
      tip.appendChild(badge);
      tip.appendChild(
        document.createTextNode(
          " " +
            Number(d.count).toLocaleString() +
            " providers (" +
            d.pct.toFixed(1) +
            "%)",
        ),
      );
      tip.style.display = "block";
      tip.style.top = lastMouse.y - 10 + "px";
      tip.style.left = lastMouse.x - tip.offsetWidth - 12 + "px";
    });

    container.addEventListener("mouseout", function (e) {
      var seg = e.target.closest(".bar-segment");
      if (!seg) return;
      // Only hide if we're actually leaving a segment (not entering a sibling).
      var related = e.relatedTarget;
      if (related && related.closest && related.closest(".bar-segment")) return;
      tip.style.display = "none";
    });

    container.addEventListener("mouseleave", function () {
      tip.style.display = "none";
    });

    // --- Click ---
    container.addEventListener("click", function (e) {
      var seg = e.target.closest(".bar-segment");
      if (!seg) return;
      var idx = segmentIndex(container, seg);
      var data = getSegmentData();
      if (idx < 0 || idx >= data.length) return;
      var d = data[idx];
      // Push click event to dcc.Store — the Dash callback handles toggle logic.
      window.dash_clientside.set_props("field-bars-click", {
        data: { field: d.field, source: d.source, _ts: Date.now() },
      });
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
