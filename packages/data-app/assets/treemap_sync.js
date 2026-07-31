// Sync treemap pathbar (breadcrumb) navigation to Dash state.
//
// Plotly's built-in pathbar clicks navigate the treemap visually but do NOT
// fire the dcc.Graph clickData property.  This script listens for the raw
// plotly_treemapclick event (which fires for ALL clicks including pathbar)
// and pushes the resulting level into a hidden dcc.Store.
//
// Plotly purges all .on() listeners when it rebuilds a plot (e.g. after a
// Dash callback sends a new figure).  We use a MutationObserver on the
// outer graph div to detect rebuilds and re-attach our listener.
(function () {
  function handler(data) {
    if (!data || !data.points || !data.points.length) return;
    var nextLevel = data.nextLevel || data.points[0].id || "England";
    window.dash_clientside.set_props("treemap-level", {
      data: { level: nextLevel, _ts: Date.now() },
    });
  }

  function attach(plotDiv) {
    // Plotly's .on() stacks handlers, so remove first to avoid duplicates.
    if (typeof plotDiv.removeAllListeners === "function") {
      plotDiv.removeAllListeners("plotly_treemapclick");
    }
    plotDiv.on("plotly_treemapclick", handler);
  }

  function setup() {
    var graph = document.getElementById("treemap-graph");
    if (!graph) {
      setTimeout(setup, 200);
      return;
    }

    // Initial attach
    var plotDiv = graph.querySelector(".js-plotly-plot") || graph;
    if (typeof plotDiv.on === "function") {
      attach(plotDiv);
    }

    // Re-attach after Plotly rebuilds the plot (which purges .on() listeners).
    // MutationObserver fires on DOM changes inside the graph div, which happen
    // whenever Plotly re-renders.
    var debounceTimer = null;
    var observer = new MutationObserver(function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        var pd = graph.querySelector(".js-plotly-plot") || graph;
        if (typeof pd.on === "function") {
          attach(pd);
        }
      }, 200);
    });
    observer.observe(graph, { childList: true, subtree: true });
  }

  if (document.readyState === "complete") {
    setTimeout(setup, 500);
  } else {
    window.addEventListener("load", function () {
      setTimeout(setup, 500);
    });
  }
})();
