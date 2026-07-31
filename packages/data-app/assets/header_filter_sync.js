// Sync Tabulator header filter inputs to Dash state via set_props.
//
// Uses event delegation on document so listeners survive DashTabulator
// re-renders (which replace the .tabulator DOM element when columns change).
// Also resets the table page to 0 on every filter change so the user always
// sees page 1 of filtered results.
(function () {
  var debounceTimer = null;

  function readAndPush() {
    var tabEl = document.querySelector(".tabulator");
    if (!tabEl) return;

    var filters = [];
    var inputs = tabEl.querySelectorAll(".tabulator-header-filter input");
    inputs.forEach(function (input) {
      var col = input.closest(".tabulator-col");
      if (!col) return;
      var field = col.getAttribute("tabulator-field");
      var rawValue = input.value;
      if (field && rawValue.trim()) {
        filters.push({ field: field, value: rawValue });
      }
    });

    window.dash_clientside.set_props("header-filters", {
      data: { filters: filters, _ts: Date.now() },
    });
    window.dash_clientside.set_props("table-page", { data: 0 });
  }

  document.addEventListener("input", function (e) {
    if (!e.target.closest(".tabulator-header-filter")) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(readAndPush, 350);
  });

  document.addEventListener("search", function (e) {
    if (!e.target.closest(".tabulator-header-filter")) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(readAndPush, 50);
  });
})();
