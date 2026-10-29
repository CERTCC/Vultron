window.MathJax = {
  // \texttip (used by the case event macros below) lives in the "action"
  // extension. Load it at startup: the bundle's autoload does not define it in
  // time for macros expanded from this config, so they render as red errors.
  loader: { load: ["[tex]/action"] },
  tex: {
    packages: { "[+]": ["action"] },
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
    // Case event symbols for the Measuring CVD pages. Each macro renders the
    // event's bold letter with a hover tip: "<short name>: <meaning>". The short
    // name must match the event legend (docs/topics/measuring_cvd/_case_events.md);
    // test/metadata/docs/test_event_symbol_tips.py checks it.
    macros: {
      evR: ["\\texttip{\\mathbf{R}}{report receipt: a participant receives the report}", 0],
      evVa: ["\\texttip{\\mathbf{Va}}{report validation: a participant decides that the report is valid}", 0],
      evAc: ["\\texttip{\\mathbf{Ac}}{report acceptance: a participant accepts the report for work}", 0],
      evC: ["\\texttip{\\mathbf{C}}{report closure: a participant closes the report}", 0],
      evJ: ["\\texttip{\\mathbf{J}}{joining: a participant joins the case}", 0],
      evS: ["\\texttip{\\mathbf{S}}{embargo agreement: a participant agrees to the active embargo}", 0],
      evV: ["\\texttip{\\mathbf{V}}{vendor awareness: a vendor becomes aware of the vul}", 0],
      evF: ["\\texttip{\\mathbf{F}}{fix readiness: a vendor has a fix ready}", 0],
      evD: ["\\texttip{\\mathbf{D}}{fix deployed: a deployer deploys a fix}", 0],
      evP: ["\\texttip{\\mathbf{P}}{public awareness: the public becomes aware of the vul}", 0],
      evX: ["\\texttip{\\mathbf{X}}{exploit public: an exploit becomes public}", 0],
      evA: ["\\texttip{\\mathbf{A}}{attacks observed: someone observes attacks that use the vul}", 0],
      evE: ["\\texttip{\\mathbf{E}}{embargo start: an embargo starts on the case}", 0],
      evEx: ["\\texttip{\\mathbf{E_x}}{embargo exit: the embargo ends}", 0],
      evExOwn: ["\\texttip{\\mathbf{E_x^\\ast}}{embargo exit on its own terms: the end time passed, or the fixes are ready or deployed}", 0],
      evExThreat: ["\\texttip{\\mathbf{E_x^!}}{embargo exit on a threat signal: public awareness, a public exploit, or attacks ended the embargo}", 0],
      evExOther: ["\\texttip{\\mathbf{E_x^\\circ}}{other early embargo exit: the embargo ended early for another reason, or for no recorded reason}", 0]
    }
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
    el.replaceWith(document.createTextNode(el.textContent ?? ""))
  })
  MathJax.startup.output.clearCache()
  MathJax.typesetClear()
  MathJax.texReset()
  MathJax.typesetPromise()
})