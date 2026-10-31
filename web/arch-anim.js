// Architecture as an animation, written so that anyone gets it on the first watch:
// five plain steps build up, one company travels through them, a caption explains each step,
// then the learning loop with the measured benchmark numbers.
// Use: <div data-arch-anim></div> + <script src="/arch-anim.js"></script>
// Restart: ?play in the URL, the "Play again" button, or mountArch(el).
// Every step also fires window event "arch:step" with {i, title, text} for captions outside the SVG.
(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const BLUE = "#2346ff", INK = "#0a0a0a", MUTED = "#6b6b6b", LINE = "#e3e3e8", SOFT = "#f6f6f8";
  const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif";
  // [title, subtitle, tag on the travelling dot, plain caption]
  const STAGES = [
    ["Find lists", ["directories,", "member lists"], "bvi.de member list",
      "1. It searches the web for public lists of the niche: trade directories, member lists, registries."],
    ["Read companies", ["one clean row", "per company"], "240 companies read",
      "2. Every company on those lists becomes one clean row. Duplicates are merged."],
    ["Check database", ["is it in a big", "database?"], "database lookup",
      "3. Each company is checked against a 17 million company database. Not in there: lead databases most likely miss it too."],
    ["Enrich", ["decision maker,", "fresh signals"], "decision maker found",
      "4. The decision maker comes from the company's own legal notice, for free. Plus news and hiring from the last 6 months."],
    ["Rank", ["fit score, tier,", "legal channel"], "Score 97 · Tier A",
      "5. A trained model scores how well the company fits and picks a legal channel: letter, phone or LinkedIn."],
  ];
  const X0 = 178, Y0 = 30, W = 156, H = 96, GAP = 18;
  const sx = i => X0 + i * (W + GAP);

  function el(tag, attrs, parent, text) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  function box(g, x, y, w, h, title, sub, o = {}) {
    const grp = el("g", { opacity: 0 }, g);
    const r = el("rect", { x, y, width: w, height: h, rx: 14, fill: o.fill || "#fff", stroke: o.stroke || INK, "stroke-width": 1.5 }, grp);
    el("text", { x: x + 16, y: y + 34, "font-size": 16, "font-weight": 650, fill: o.ink || INK }, grp, title);
    [].concat(sub || []).forEach((t, k) => el("text", { x: x + 16, y: y + 60 + k * 18, "font-size": 14, fill: o.subInk || MUTED }, grp, t));
    grp._rect = r;
    return grp;
  }
  function arrow(g, d, o = {}) {
    const p = el("path", { d, fill: "none", stroke: o.stroke || "#b9b9c8", "stroke-width": 1.6, "stroke-dasharray": o.dash || "", "marker-end": "url(#aa-ar)" }, g);
    p.style.opacity = 0;
    return p;
  }

  function build(svg) {
    svg.innerHTML = "";
    const defs = el("defs", {}, svg);
    const m = el("marker", { id: "aa-ar", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
    el("path", { d: "M0,0 L10,5 L0,10 z", fill: "#b9b9c8" }, m);
    const g = el("g", { "font-family": FONT }, svg);
    const T = [];
    const show = (n, t, dur = .45) => T.push([t, () => n.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: dur * 1000, fill: "forwards", easing: "cubic-bezier(.2,.7,.2,1)" })]);
    const draw = (p, t, dur = .35) => T.push([t, () => {
      if (p.getAttribute("stroke-dasharray")) { p.style.transition = `opacity ${dur}s`; requestAnimationFrame(() => { p.style.opacity = 1; }); return; }
      let L = 0; try { L = p.getTotalLength(); } catch { /* not rendered */ } p.style.strokeDasharray = `${L} ${L}`; p.style.strokeDashoffset = L; p.style.opacity = 1;
      p.style.transition = `stroke-dashoffset ${dur}s ease`;
      requestAnimationFrame(() => requestAnimationFrame(() => { p.style.strokeDashoffset = 0; }));
    }]);

    // Input and output
    show(box(g, 20, Y0, 140, H, "Your niche", ["any niche,", "free text"]), 0);
    STAGES.forEach(([t, s], i) => {
      const b = box(g, sx(i), Y0, W, H, t, s);
      b.id = "aa-s" + i;
      show(b, .35 + i * .3);
      draw(arrow(g, `M${i ? sx(i) - GAP : 160} ${Y0 + H / 2} H${sx(i) - 5}`), .3 + i * .3, .25);
    });
    const outX = sx(5);
    show(box(g, outX, Y0, 140, H, "Clay table", ["ready for", "outreach"], { fill: INK, stroke: INK, ink: "#fff", subInk: "#bdbdbd" }), 1.9);
    draw(arrow(g, `M${outX - GAP} ${Y0 + H / 2} H${outX - 5}`), 1.85, .25);

    // Caption under the chain (inside the SVG, so it also works in the full-screen recording)
    const cap = el("text", { x: 20, y: Y0 + H + 50, "font-size": 18, fill: INK, opacity: 0 }, g, "");
    const setCap = (i, text) => {
      // wrap into at most two lines of about 75 characters
      cap.textContent = "";
      const words = text.split(" "), lines = [""];
      words.forEach(w => { if ((lines[lines.length - 1] + " " + w).length > 75 && lines.length < 2) lines.push(w); else lines[lines.length - 1] = (lines[lines.length - 1] + " " + w).trim(); });
      lines.forEach((t, k) => el("tspan", { x: 20, dy: k ? 26 : 0 }, cap, t));
      cap.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, fill: "forwards" });
      window.dispatchEvent(new CustomEvent("arch:step", { detail: { i, title: i >= 0 ? STAGES[i][0] : "", text } }));
    };

    // One company travels through the chain
    const dot = el("g", { opacity: 0 }, g);
    el("circle", { r: 9, fill: BLUE }, dot);
    const tagBg = el("rect", { x: -10, y: -40, rx: 8, height: 26, width: 10, fill: BLUE }, dot);
    const tag = el("text", { x: 0, y: -22, "font-size": 13, "font-weight": 600, fill: "#fff" }, dot, "");
    const setTag = t => { tag.textContent = t; const w = t.length * 7.2 + 20; tagBg.setAttribute("width", w); tagBg.setAttribute("x", -w / 2); tag.setAttribute("x", -w / 2 + 10); };
    const go = (x, y, ms) => { dot.style.transition = `transform ${ms}ms cubic-bezier(.5,0,.3,1)`; dot.style.transform = `translate(${x}px,${y}px)`; };
    const START = 2.6, STEP = 2.4;
    T.push([START, () => { dot.style.transition = "none"; dot.style.transform = `translate(100px,${Y0 + H}px)`; setTag("your niche"); dot.setAttribute("opacity", 1); }]);
    STAGES.forEach((st, i) => {
      T.push([START + .2 + i * STEP, () => go(sx(i) + W / 2, Y0 + H, 500)]);
      T.push([START + .7 + i * STEP, () => {
        setTag(st[2]); setCap(i, st[3]);
        const r = svg.querySelector(`#aa-s${i} rect`);
        if (r) { r.setAttribute("stroke", BLUE); r.setAttribute("stroke-width", 3); }
      }]);
    });
    const END = START + .2 + STAGES.length * STEP;
    T.push([END, () => { go(outX + 70, Y0 + H, 600); setTag("one row per lead"); setCap(-1, "The leads land as rows in Clay, the lead tool Arvana already uses. Nothing after that changes."); }]);
    T.push([END + 1.6, () => dot.setAttribute("opacity", 0)]);

    // Learning loop with the measured numbers (bench/results.md)
    const LY = 266;
    const lt = el("text", { x: 20, y: LY, "font-size": 15, "font-weight": 650, fill: INK, opacity: 0 }, g, "It can learn from Arvana");
    const ls = el("text", { x: 20, y: LY + 22, "font-size": 13.5, fill: MUTED, opacity: 0 }, g);
    el("tspan", { x: 20, dy: 0 }, ls, "When Arvana marks leads as fit or no fit,");
    el("tspan", { x: 20, dy: 18 }, ls, "the model retrains and step 5 gets better.");
    show(lt, END + 1.8); show(ls, END + 2);
    const loop = ["Hand labels", "Training", "Better ranking"];
    loop.forEach((t, k) => {
      const x = 20 + k * 200;
      show(box(g, x, LY + 58, 170, 52, t, "", k === 2 ? { stroke: BLUE } : {}), END + 2.2 + k * .3);
      if (k) draw(arrow(g, `M${x - 30} ${LY + 84} H${x - 5}`), END + 2.15 + k * .3, .25);
    });
    const back = arrow(g, `M${20 + 2 * 200 + 85} ${LY + 58} V${LY - 26} H${sx(4) + W / 2} V${Y0 + H + 6}`, { stroke: BLUE, dash: "5 4" });
    draw(back, END + 3.1, .5);

    const nums = el("g", { opacity: 0 }, g);
    const bx = 640, by = LY;
    el("text", { x: bx, y: by, "font-size": 14, fill: MUTED }, nums, "Are the best leads on top? Score 0 to 1, 330 labelled pairs");
    const bar = (y, label, val, color, txt) => {
      el("text", { x: bx, y: y + 12, "font-size": 13.5, fill: INK }, nums, label);
      el("rect", { x: bx + 170, y, width: 300, height: 14, rx: 7, fill: "#f0f0f2" }, nums);
      const b = el("rect", { x: bx + 170, y, width: 300 * val, height: 14, rx: 7, fill: color }, nums);
      b.style.transformBox = "fill-box"; b.style.transformOrigin = "left center"; b.style.transform = "scaleX(0)"; b.style.transition = "transform .9s cubic-bezier(.2,.7,.2,1)";
      el("text", { x: bx + 482, y: y + 12, "font-size": 13.5, "font-weight": 650, fill: color === BLUE ? BLUE : INK }, nums, txt);
      T.push([END + 3.6, () => { b.style.transform = "scaleX(1)"; }]);
    };
    bar(by + 16, "Fixed rules", .608, "#c4c4c4", "0.608");
    bar(by + 42, "Arvantir", .764, BLUE, "0.764");
    el("text", { x: bx, y: by + 96, "font-size": 13.5, fill: MUTED }, nums, "Small test set, most labels by an AI model. Car washes still rank worse than fixed rules.");
    show(nums, END + 3.4);
    return T;
  }

  function play(wrap) {
    const svg = wrap.querySelector("svg");
    (wrap._timers || []).forEach(clearTimeout);
    const T = build(svg);
    wrap._timers = T.map(([t, f]) => setTimeout(f, t * 1000));
  }

  function mount(wrap) {
    if (wrap._mounted) return play(wrap);
    wrap._mounted = true;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 1200 400");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "How Arvantir works: find lists, read companies, check against a big company database, enrich with decision maker and signals, rank. Leads go into Clay. Can learn from Arvana's labels.");
    svg.style.width = "100%"; svg.style.height = "auto"; svg.style.display = "block";
    wrap.appendChild(svg);
    const again = document.createElement("button");
    again.type = "button"; again.textContent = "Play again"; again.className = "aa-again";
    again.onclick = () => play(wrap);
    wrap.appendChild(again);
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (wrap.dataset.archAnim === "onview" && !new URLSearchParams(location.search).has("play")) {
      const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); play(wrap); } }, { threshold: .35 });
      io.observe(wrap);
    } else play(wrap);
    if (still) { (wrap._timers || []).forEach(clearTimeout); build(svg).forEach(([, f]) => f()); }
  }
  window.mountArch = mount;
  document.querySelectorAll("[data-arch-anim]").forEach(mount);
})();
