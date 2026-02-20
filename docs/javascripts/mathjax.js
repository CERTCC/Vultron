window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};

document$.subscribe(() => {
  // Strip any <abbr> elements inserted inside arithmatex spans/divs by the
  // abbreviation extension to prevent them from interfering with MathJax.
  document.querySelectorAll(".arithmatex abbr").forEach((el) => {
    el.replaceWith(document.createTextNode(el.textContent))
  })
  MathJax.startup.output.clearCache()
  MathJax.typesetClear()
  MathJax.texReset()
  MathJax.typesetPromise()
})