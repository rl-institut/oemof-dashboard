// Cytoscape only re-measures on window resize; the graph pane is resized via CSS `resize`, so watch the pane.
const graphResize = new ResizeObserver(() => document.getElementById("graph")?._cyreg?.cy?.resize());
new MutationObserver((_, watcher) => {
    const pane = document.querySelector(".graph-pane");
    if (pane) {
        graphResize.observe(pane);
        watcher.disconnect();
    }
}).observe(document.documentElement, { childList: true, subtree: true });
