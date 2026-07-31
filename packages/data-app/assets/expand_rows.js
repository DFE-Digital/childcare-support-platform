// Toggle expand/collapse all dataTree rows in the detail grid.
(function () {
  function getTabulator() {
    var tabEl = document.querySelector(".tabulator");
    if (!tabEl) return null;

    var reactKey = Object.keys(tabEl).find(function (k) {
      return (
        k.indexOf("__reactInternalInstance") === 0 ||
        k.indexOf("__reactFiber") === 0
      );
    });
    if (!reactKey) return null;

    var node = tabEl[reactKey];
    var depth = 0;
    while (node && depth < 20) {
      if (
        node.stateNode &&
        node.stateNode !== tabEl &&
        node.stateNode.table &&
        typeof node.stateNode.table.getRows === "function"
      ) {
        return node.stateNode.table;
      }
      node = node.return;
      depth++;
    }
    return null;
  }

  function setup() {
    var btn = document.getElementById("expand-rows");
    if (!btn) {
      setTimeout(setup, 200);
      return;
    }

    var expanded = false;

    function resetButton() {
      if (!expanded) return;
      expanded = false;
      btn.textContent = "Expand rows";
    }

    // Reset when table data changes (filter/pagination).
    // The page-info span always updates when data changes.
    var pageInfo = document.getElementById("page-info");
    if (pageInfo) {
      new MutationObserver(resetButton).observe(pageInfo, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }

    btn.addEventListener("click", function () {
      var table = getTabulator();
      if (!table) return;

      expanded = !expanded;
      var rows = table.getRows();
      for (var i = 0; i < rows.length; i++) {
        if (expanded) {
          rows[i].treeExpand();
        } else {
          rows[i].treeCollapse();
        }
      }
      btn.textContent = expanded ? "Collapse rows" : "Expand rows";
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
