import "./style.css";
import sample from "../examples/lightning-burst.vfx.json";
import { construct } from "./pipeline.js";
import { Preview } from "./engine/preview.js";

const icons = {
  bolt: '<path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z"/>',
  cube: '<path d="m12 3 9 5v8l-9 5-9-5V8l9-5Z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  play: '<path d="m8 4 12 8-12 8V4Z"/>',
  pause: '<path d="M8 4v16M16 4v16"/>',
  replay: '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
  ring: '<ellipse cx="12" cy="12" rx="9" ry="5"/><ellipse cx="12" cy="12" rx="5" ry="2"/>',
  core: '<circle cx="12" cy="12" r="5"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  particles:
    '<circle cx="6" cy="6" r="1"/><circle cx="18" cy="7" r="2"/><circle cx="11" cy="13" r="2"/><circle cx="5" cy="19" r="1"/><circle cx="19" cy="18" r="1"/>',
  grid: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
  focus:
    '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="3"/>',
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-16-2 20"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
};
const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.cube}</svg>`;
const escape = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const $ = (id) => document.getElementById(id);

$("app").innerHTML = `
<header class="topbar">
  <a class="brand" href="./" aria-label="VFX Forge home"><span class="brand-mark">${icon("bolt")}</span><span>VFX<span class="brand-light"> Forge</span></span><span class="version">α 0.1</span></a>
  <div class="workspace-label"><span class="divider"></span>Procedural workbench</div>
  <div class="top-right"><span class="local"><i></i>Local-first</span><span class="milestone">MILESTONE 01</span></div>
</header>
<section class="heading">
  <div><div class="eyebrow">FOUNDATION / PROOF OF CONCEPT</div><h1>From a plan. Into motion.</h1><p>Real geometry. Deterministic animation. Nothing flattened.</p></div>
  <div class="heading-actions"><button id="load" class="button secondary">${icon("upload")}Load plan</button><button id="download" class="button primary">${icon("download")}Save plan <span class="small-tag">JSON</span></button></div>
  <input id="file" type="file" accept=".json,application/json" hidden />
</section>
<div id="message" class="message" role="alert" hidden></div>
<main class="workbench">
  <aside class="panel left-panel">
    <div class="panel-heading"><span>${icon("cube")}Construction</span><span class="subtle mono" id="layer-count">05</span></div>
    <div class="preset"><div class="eyebrow">MANUALLY AUTHORED PLAN</div><h2 id="effect-name"></h2><span class="preset-type">Radial burst <span>·</span> schema 1.0</span></div>
    <div class="section-label">COMPONENT STACK <span id="stack-count"></span></div>
    <div id="components" class="components"></div>
    <div class="plan-summary"><div><span>Effect duration</span><strong id="duration"></strong></div><div><span>Random seed</span><strong id="seed" class="mono"></strong></div><div><span>Animation</span><strong>Absolute time</strong></div></div>
    <div class="foundation-note"><span class="note-icon">${icon("code")}</span><div><strong>Built from a plan, not a prompt.</strong><p>The Designer is not implemented yet. Load a JSON plan to explore the engine.</p></div></div>
    <button id="sample" class="text-button">Restore example ${icon("replay")}</button>
  </aside>
  <section class="preview-panel panel">
    <div class="preview-toolbar"><div class="tabs"><button class="tab active" id="preview-tab" aria-pressed="true">3D preview</button><button class="tab" id="plan-tab" aria-pressed="false">${icon("code")}Plan JSON</button></div><span class="live-badge" id="preview-status"><i></i>LIVE ENGINE</span></div>
    <div class="viewport-shell">
      <div id="viewport"></div>
      <div class="viewport-info"><span class="mini-dot"></span>PERSPECTIVE <span class="viewport-separator">/</span><span>Y-UP</span></div>
      <div class="viewport-tools" id="viewport-tools"><button id="grid" class="icon-button selected" title="Toggle ground grid" aria-label="Toggle ground grid" aria-pressed="true">${icon("grid")}</button><button id="camera" class="icon-button" title="Reset camera" aria-label="Reset camera">${icon("focus")}</button></div>
      <div class="axis" aria-hidden="true"><span class="axis-y">Y</span><span class="axis-z">Z</span><span class="axis-x">X</span></div>
      <div class="viewport-help">Drag to orbit <span>·</span> Scroll to zoom</div>
      <div id="plan-view" hidden><div class="json-heading">CONSTRUCTION PLAN <span>READ ONLY · VERSION 1.0</span></div><pre id="json"></pre></div>
    </div>
    <div class="playback"><button id="play" class="play-button" aria-label="Pause animation">${icon("pause")}</button><button id="replay" class="icon-button" title="Replay" aria-label="Replay">${icon("replay")}</button><span id="time" class="time mono">0.00 <span>/ 1.50 s</span></span><label class="loop"><input id="loop" type="checkbox" checked />Loop</label><select id="speed" aria-label="Playback speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1× speed</option><option value="2">2×</option></select></div>
    <div class="timeline"><input id="scrub" type="range" min="0" max="1.5" value="0.38" step="0.001" aria-label="Animation time" /><div class="timeline-labels"><span>0.00 s</span><span id="timeline-half">0.75 s</span><span id="timeline-end">1.50 s</span></div></div>
    <div class="render-stats"><span><i></i><span id="render-status">WebGL preview</span></span><span id="draw-calls">— draw calls</span></div>
  </section>
  <aside class="panel right-panel">
    <div class="panel-heading"><span>${icon("check")}Verification</span><span class="subtle mono">01</span></div>
    <div class="verified"><span class="verified-icon">${icon("check")}</span><div><strong id="verification-title">Structurally verified</strong><p id="verification-subtitle">All construction checks passed</p></div></div>
    <div id="checks" class="checks"></div>
    <div class="section-label budget-label">RESOURCE BUDGET</div>
    <div class="budget"><div><span>Render objects</span><strong id="objects"></strong></div><div class="meter"><span id="object-meter"></span></div><div><span>Particles</span><strong id="particles"></strong></div><div class="meter cyan"><span id="particle-meter"></span></div></div>
    <div class="coverage"><span>Requirement coverage</span><strong id="coverage">100<small>%</small></strong><p>Against this plan's structure, not artistic quality.</p></div>
    <div class="scope-note">${icon("code")}<span>Preview only. Roblox export and visual-quality evaluation are not implemented.</span></div>
  </aside>
</main>
<section class="pipeline"><span class="pipeline-label">THE PIPELINE</span><div class="pipeline-step muted"><span class="step-number">01</span><span>Designer <small>Not implemented</small></span></div>${icon("arrow", "pipeline-arrow")}<div class="pipeline-step"><span class="step-number">02</span><span>Reasoner <small>Schema + constraints</small></span></div>${icon("arrow", "pipeline-arrow")}<div class="pipeline-step"><span class="step-number">03</span><span>Builder <small>Procedural geometry</small></span></div>${icon("arrow", "pipeline-arrow")}<div class="pipeline-step"><span class="step-number">04</span><span>Verifier <small>Structural checks</small></span></div><span class="pipeline-end">${icon("check")} No AI service required</span></section>
<footer><span>VFX FORGE <span class="footer-slash">/</span> A foundation for editable effects</span><span>ENGINE v0.1.0 <span class="footer-slash">·</span> PLAN v1.0</span></footer>`;

let currentPlan, result, preview;
function showError(message) {
  $("message").textContent = message;
  $("message").hidden = false;
}
function hideError() {
  $("message").hidden = true;
}
function loadPlan(plan) {
  const candidate = construct(plan);
  if (!candidate.ok) {
    const details = candidate.issues
      .slice(0, 4)
      .map((i) => `${i.code} ${i.path}: ${i.message} ${i.correction}`)
      .join(" • ");
    throw new Error(
      `Plan rejected by ${candidate.stage}. ${details} Current effect unchanged.`,
    );
  }
  // Validate and verify before handing any descriptors to the preview adapter.
  preview?.load(candidate.built);
  currentPlan = structuredClone(plan);
  result = candidate;
  $("effect-name").textContent = plan.name;
  $("duration").textContent = `${plan.duration.toFixed(2)} s`;
  $("seed").textContent = plan.seed;
  $("layer-count").textContent = String(plan.components.length).padStart(
    2,
    "0",
  );
  $("stack-count").textContent = `${plan.components.length} layers`;
  $("components").innerHTML = plan.components
    .map((c, i) => {
      const description =
        c.type === "core"
          ? `Sphere · ${c.properties.radius} u radius`
          : c.type === "ring"
            ? `${c.properties.radius} → ${c.properties.endRadius} u`
            : c.type === "lightning"
              ? `${c.properties.count} arcs · ${c.properties.segments} segments`
              : `${c.properties.count} particles · seeded`;
      return `<div class="component"><span class="component-icon" style="color:${c.color}">${icon(c.type === "lightning" ? "bolt" : c.type)}</span><div><strong>${escape(c.id.replaceAll("-", " "))}</strong><small>${description}</small></div><span class="component-index mono">${String(i + 1).padStart(2, "0")}</span></div>`;
    })
    .join("");
  $("json").textContent = JSON.stringify(plan, null, 2);
  $("scrub").max = plan.duration;
  $("timeline-half").textContent = `${(plan.duration / 2).toFixed(2)} s`;
  $("timeline-end").textContent = `${plan.duration.toFixed(2)} s`;
  const stats = candidate.reasoning.stats;
  $("objects").textContent =
    `${stats.objects} / ${plan.constraints.maxObjects}`;
  $("particles").textContent =
    `${stats.particles} / ${plan.constraints.maxParticles}`;
  $("object-meter").style.width =
    `${(stats.objects / plan.constraints.maxObjects) * 100}%`;
  $("particle-meter").style.width =
    `${plan.constraints.maxParticles ? (stats.particles / plan.constraints.maxParticles) * 100 : 0}%`;
  $("coverage").innerHTML =
    `${Math.round(candidate.verification.coverage * 100)}<small>%</small>`;
  const checks = [
    ["Schema & properties", "Version 1.0 · valid ranges"],
    ["Component construction", `${stats.components} layers · counts match`],
    [
      "Animation timeline",
      `All layers fit ${plan.duration.toFixed(2)} seconds`,
    ],
    ["Geometry & resource limits", "Finite vectors · within budgets"],
  ];
  $("checks").innerHTML = checks
    .map(
      ([title, detail]) =>
        `<div class="check-row">${icon("check")}<div><strong>${title}</strong><small>${detail}</small></div></div>`,
    )
    .join("");
  hideError();
}
function frame(time, info) {
  $("time").innerHTML =
    `${time.toFixed(2)} <span>/ ${currentPlan?.duration.toFixed(2) ?? "1.50"} s</span>`;
  $("scrub").value = time;
  $("scrub").style.setProperty(
    "--progress",
    `${(time / (currentPlan?.duration || 1.5)) * 100}%`,
  );
  $("draw-calls").textContent = `${info.calls} draw calls`;
  syncPlay();
}
function syncPlay() {
  const playing = preview?.playing;
  $("play").innerHTML = icon(playing ? "pause" : "play");
  $("play").setAttribute(
    "aria-label",
    playing ? "Pause animation" : "Play animation",
  );
}
loadPlan(sample);
try {
  preview = new Preview($("viewport"), frame, (message) => {
    showError(message);
    $("preview-status").textContent = "PREVIEW UNAVAILABLE";
  });
  preview.load(result.built);
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches)
    preview.playing = false;
} catch (error) {
  $("preview-status").textContent = "PREVIEW UNAVAILABLE";
  $("render-status").textContent = "WebGL unavailable";
  $("viewport").innerHTML =
    '<div class="webgl-error"><h2>3D preview unavailable</h2><p>Enable WebGL in a modern browser, then reload. No screenshot has been substituted.</p></div>';
  showError(
    `Could not initialize the 3D preview: ${error.message}. The plan is still available in Plan JSON.`,
  );
  for (const id of [
    "play",
    "replay",
    "scrub",
    "grid",
    "camera",
    "speed",
    "loop",
  ])
    $(id).disabled = true;
}
$("play").onclick = () => {
  if (!preview) return;
  if (preview.time >= preview.duration) preview.seek(0);
  preview.playing = !preview.playing;
  syncPlay();
};
$("replay").onclick = () => {
  preview?.seek(0);
  if (preview) preview.playing = true;
  syncPlay();
};
$("scrub").oninput = (e) => {
  if (preview) {
    preview.playing = false;
    preview.seek(Number(e.target.value));
    syncPlay();
  }
};
$("loop").onchange = (e) => {
  if (preview) preview.loop = e.target.checked;
};
$("speed").onchange = (e) => {
  if (preview) preview.speed = Number(e.target.value);
};
$("grid").onclick = () => {
  if (!preview) return;
  preview.grid.visible = !preview.grid.visible;
  $("grid").classList.toggle("selected", preview.grid.visible);
  $("grid").setAttribute("aria-pressed", String(preview.grid.visible));
};
$("camera").onclick = () => preview?.resetCamera();
function tab(showPlan) {
  $("plan-view").hidden = !showPlan;
  $("viewport-tools")?.classList.toggle("hidden", showPlan);
  for (const [id, active] of [
    ["preview-tab", !showPlan],
    ["plan-tab", showPlan],
  ]) {
    $(id).classList.toggle("active", active);
    $(id).setAttribute("aria-pressed", String(active));
  }
}
$("preview-tab").onclick = () => tab(false);
$("plan-tab").onclick = () => tab(true);
$("sample").onclick = () => {
  try {
    loadPlan(sample);
  } catch (e) {
    showError(e.message);
  }
};
$("load").onclick = () => $("file").click();
$("file").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    if (file.size > 64 * 1024)
      throw new Error(
        "Plan exceeds the 64 KiB input limit. Current effect unchanged.",
      );
    loadPlan(JSON.parse(await file.text()));
  } catch (error) {
    showError(error.message);
  } finally {
    e.target.value = "";
  }
};
$("download").onclick = () => {
  const blob = new Blob([JSON.stringify(currentPlan, null, 2) + "\n"], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "effect.vfx.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
window.addEventListener("pagehide", (event) => {
  if (!event.persisted) preview?.dispose();
});
