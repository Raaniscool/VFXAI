import "./style.css";
import sample from "../examples/lightning-burst.vfx.json";
import { construct } from "./pipeline.js";
import { designer } from "./organs/designer.js";
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
  <a class="brand" href="./" aria-label="VFXAI home"><span class="brand-mark">${icon("bolt")}</span><span>VFX<span class="brand-light">AI</span></span><span class="version">α 0.3</span></a>
  <div class="workspace-label"><span class="divider"></span>Local neural VFX lab</div>
  <div class="top-right"><span class="local"><i></i>Offline-capable</span><span class="milestone">PYTHON + THREE.JS</span></div>
</header>
<section class="heading">
  <div><div class="eyebrow">LOCAL RESEARCH BUILD / RANDOM-WEIGHT START</div><h1>Prompt to structured VFX plan.</h1><p>A small trainable model, explicit validation, and a real-time procedural preview.</p></div>
  <div class="heading-actions"><button id="load" class="button secondary">${icon("upload")}Load plan</button><button id="download" class="button primary">${icon("download")}Save current <span class="small-tag">JSON</span></button></div>
  <input id="file" type="file" accept=".json,application/json" hidden />
</section>
<div id="message" class="message" role="alert" hidden></div>
<main class="workbench">
  <aside class="panel left-panel">
    <div class="panel-heading"><span>${icon("cube")}Construction</span><span class="subtle mono" id="layer-count">05</span></div>
    <div class="preset"><div class="eyebrow">CURRENT PLAN</div><h2 id="effect-name"></h2><span class="preset-type">Radial burst <span>·</span> schema 1.0</span></div>
    <div class="section-label">COMPONENT STACK <span id="stack-count"></span></div>
    <div id="components" class="components"></div>
    <div class="plan-summary"><div><span>Effect duration</span><strong id="duration"></strong></div><div><span>Random seed</span><strong id="seed" class="mono"></strong></div><div><span>Animation</span><strong>Absolute time</strong></div></div>
    <div class="foundation-note"><span class="note-icon">${icon("code")}</span><div><strong>Designer is a neural model.</strong><p>Generated parameters are adapted to plan v1, then validated. Failed outputs are kept; no sample fallback is used.</p></div></div>
    <button id="sample" class="text-button">Restore authored example ${icon("replay")}</button>
  </aside>
  <section class="preview-panel panel">
    <div class="preview-toolbar"><div class="tabs"><button class="tab active" id="preview-tab" aria-pressed="true">3D preview</button><button class="tab" id="plan-tab" aria-pressed="false">${icon("code")}Plan JSON</button></div><span class="live-badge" id="preview-status"><i></i>LIVE ENGINE</span></div>
    <div class="viewport-shell">
      <div id="viewport"></div>
      <div class="viewport-info"><span class="mini-dot"></span>PERSPECTIVE <span class="viewport-separator">/</span><span>Y-UP</span></div>
      <div class="viewport-tools" id="viewport-tools"><button id="grid" class="icon-button selected" title="Toggle ground grid" aria-label="Toggle ground grid" aria-pressed="true">${icon("grid")}</button><button id="camera" class="icon-button" title="Reset camera" aria-label="Reset camera">${icon("focus")}</button></div>
      <div class="axis" aria-hidden="true"><span class="axis-y">Y</span><span class="axis-z">Z</span><span class="axis-x">X</span></div>
      <div class="viewport-help">Drag to orbit <span>·</span> Scroll to zoom</div>
      <div id="plan-view" hidden><div class="json-heading">CONSTRUCTION PLAN <span>VERSION 1.0</span></div><pre id="json"></pre></div>
    </div>
    <div class="playback"><button id="play" class="play-button" aria-label="Pause animation">${icon("pause")}</button><button id="replay" class="icon-button" title="Replay" aria-label="Replay">${icon("replay")}</button><span id="time" class="time mono">0.00 <span>/ 1.50 s</span></span><label class="loop"><input id="loop" type="checkbox" checked />Loop</label><select id="speed" aria-label="Playback speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1× speed</option><option value="2">2×</option></select></div>
    <div class="timeline"><input id="scrub" type="range" min="0" max="1.5" value="0.38" step="0.001" aria-label="Animation time" /><div class="timeline-labels"><span>0.00 s</span><span id="timeline-half">0.75 s</span><span id="timeline-end">1.50 s</span></div></div>
    <div class="render-stats"><span><i></i><span id="render-status">WebGL preview</span></span><span id="draw-calls">— draw calls</span></div>
  </section>
  <aside class="panel right-panel">
    <div class="panel-heading"><span>${icon("check")}Reasoner + Verifier</span><span class="subtle mono">PLAN 1.0</span></div>
    <div class="verified"><span class="verified-icon">${icon("check")}</span><div><strong id="verification-title">Structurally verified</strong><p id="verification-subtitle">All construction checks passed</p></div></div>
    <div id="checks" class="checks"></div>
    <div class="section-label budget-label">RESOURCE BUDGET</div>
    <div class="budget"><div><span>Render objects</span><strong id="objects"></strong></div><div class="meter"><span id="object-meter"></span></div><div><span>Particles</span><strong id="particles"></strong></div><div class="meter cyan"><span id="particle-meter"></span></div></div>
    <div class="coverage"><span>Plan coverage</span><strong id="coverage">100<small>%</small></strong><p>Structural agreement only, not artistic quality.</p></div>
    <div class="scope-note">${icon("code")}<span>Preview only. Roblox export and visual-quality evaluation are not implemented.</span></div>
  </aside>
</main>
<section class="ai-lab" aria-labelledby="lab-heading">
  <div class="ai-lab-heading"><div><div class="eyebrow">EXPERIMENTAL / LOCAL-ONLY</div><h2 id="lab-heading">Neural Designer &amp; Training Lab</h2><p>Prompts and outputs stay in this project folder. The model is randomly initialized; synthetic examples are intentionally narrow.</p></div><span class="local-chip"><i></i>NO CLOUD API</span></div>
  <div class="ai-grid">
    <div class="ai-column">
      <section class="lab-card">
        <div class="lab-card-heading"><div><span class="lab-step">01</span><h3>Generate a plan</h3></div><span id="model-badge" class="model-badge">Loading model…</span></div>
        <label class="field-label" for="ai-prompt">VFX prompt <span>1,000 characters max</span></label>
        <textarea id="ai-prompt" class="prompt-input" maxlength="1000">Create a bright cyan branching lightning burst, with a large-scale shape and a brief finish.</textarea>
        <div class="form-grid three">
          <label class="field-label">Checkpoint<select id="checkpoint-select" class="field-control"></select></label>
          <label class="field-label">Plan seed<input id="generation-seed" class="field-control" type="number" value="2026" min="0" max="4294967295" /></label>
          <button id="generate" class="button primary action-align">${icon("bolt")}Generate</button>
        </div>
        <p class="lab-explainer">Same prompt + checkpoint gives the same neural prediction. The plan seed changes the Builder’s procedural geometry, not model sampling.</p>
        <div id="ai-message" class="ai-message" role="status" hidden></div>
        <div id="ai-result" class="ai-result" hidden>
          <div class="result-header"><div><span class="eyebrow">NEURAL OUTPUT</span><h4 id="ai-category">—</h4></div><span id="ai-validity" class="validity-badge">Not checked</span></div>
          <div class="result-meta"><span id="ai-checkpoint-label"></span><span id="ai-confidence"></span></div>
          <div id="ai-component-probs" class="probability-list"></div>
          <label class="field-label" for="ai-plan-json">Raw candidate plan JSON <span>editable; never auto-repaired</span></label>
          <textarea id="ai-plan-json" class="plan-editor" spellcheck="false" rows="12" aria-label="Raw candidate plan JSON"></textarea>
          <div id="ai-validation" class="validation-box" role="status"></div>
          <div class="button-row"><button id="ai-preview" class="button primary" disabled>${icon("play")}Preview validated plan</button><button id="ai-download" class="button secondary" disabled>${icon("download")}Save candidate</button></div>
          <details class="raw-output"><summary>Raw neural heads and provenance</summary><pre id="ai-raw-output"></pre></details>
        </div>
      </section>
      <section class="lab-card">
        <div class="lab-card-heading"><div><span class="lab-step">02</span><h3>Compare checkpoints</h3></div></div>
        <p class="lab-explainer">Same prompt and plan seed; each checkpoint gets its own neural forward pass. Invalid plans remain visible.</p>
        <div class="form-grid three">
          <label class="field-label">Checkpoint A<select id="compare-a" class="field-control"></select></label>
          <label class="field-label">Checkpoint B<select id="compare-b" class="field-control"></select></label>
          <button id="compare-button" class="button secondary action-align">Compare</button>
        </div>
        <div id="compare-result" class="compare-result" hidden></div>
      </section>
      <section id="feedback-editor" class="lab-card" hidden>
        <div class="lab-card-heading"><div><span class="lab-step">03</span><h3>Review this output</h3></div><span class="subtle">No automatic learning</span></div>
        <p class="lab-explainer">A rating is only a local record. To train on it, first validate it and explicitly approve it in the review queue.</p>
        <div class="form-grid three">
          <label class="field-label">Rating<select id="feedback-rating" class="field-control"><option value="good">Useful</option><option value="poor">Not useful</option><option value="invalid">Invalid / unsafe</option></select></label>
          <label class="field-label">Training category<select id="feedback-category" class="field-control"></select></label>
          <button id="save-feedback" class="button secondary action-align">Save feedback</button>
        </div>
        <label class="field-label" for="feedback-notes">Notes <span>optional · kept locally</span></label>
        <textarea id="feedback-notes" class="small-textarea" maxlength="2000" placeholder="What should be different? This is a note, not a training signal."></textarea>
        <details class="correction-details"><summary>Optional corrected plan (JSON)</summary><p class="lab-explainer">If you edited the neural candidate above, that edited JSON is saved as the correction. Otherwise a “Useful” rating records the original valid candidate; other ratings can be notes only.</p><textarea id="feedback-plan" class="plan-editor" spellcheck="false" rows="8" placeholder="Paste a separate corrected plan here, or leave blank. A valid, supported plan is required before approval."></textarea></details>
        <div id="feedback-message" class="ai-message" role="status" hidden></div>
      </section>
    </div>
    <div class="ai-column">
      <section class="lab-card">
        <div class="lab-card-heading"><div><span class="lab-step">04</span><h3>Local data &amp; training</h3></div><span id="dataset-badge" class="model-badge">Dataset loading…</span></div>
        <p id="dataset-summary" class="lab-explainer">Synthetic prompts are generated reproducibly, schema-checked, and split by prompt family into train, validation, and held-out test sets.</p>
        <div class="form-grid three dataset-controls">
          <label class="field-label">Examples<input id="dataset-count" class="field-control" type="number" min="100" max="5000" step="100" value="1000" /></label>
          <label class="field-label">Dataset seed<input id="dataset-seed" class="field-control" type="number" min="0" max="4294967295" value="2026" /></label>
          <button id="generate-dataset" class="button secondary action-align">Generate dataset</button>
        </div>
        <div class="form-grid four training-controls">
          <label class="field-label">Target epochs<input id="train-epochs" class="field-control" type="number" min="1" max="1000" value="20" /></label>
          <label class="field-label">Batch size<input id="train-batch" class="field-control" type="number" min="1" max="128" value="16" /></label>
          <label class="field-label">Hidden units<select id="train-hidden" class="field-control"><option>16</option><option>32</option><option selected>64</option><option>128</option></select></label>
          <label class="field-label">Learning rate<input id="train-rate" class="field-control" type="number" min="0.00001" max="0.1" step="0.0001" value="0.003" /></label>
        </div>
        <div class="form-grid three">
          <label class="field-label">Initialization / shuffle seed<input id="train-seed" class="field-control" type="number" min="0" max="4294967295" value="1337" /></label>
          <label class="field-label">Resume trained checkpoint<select id="resume-checkpoint" class="field-control"><option value="">Start from random weights</option></select></label>
          <button id="start-training" class="button primary action-align">${icon("play")}Start training</button>
        </div>
        <label class="check-option"><input id="include-feedback" type="checkbox" /><span>Include explicitly approved feedback in this run</span></label>
        <div class="training-status"><div class="training-status-head"><strong id="training-state">No training run active</strong><span id="training-progress-label">0%</span></div><div class="training-progress"><span id="training-progress"></span></div><p id="training-detail" class="lab-explainer">Training uses local CPU NumPy and saves checkpoints under .vfxai/checkpoints.</p><div class="button-row compact"><button id="pause-training" class="button secondary" disabled>Pause</button><button id="resume-training" class="button secondary" disabled>Resume</button><button id="stop-training" class="button danger" disabled>Stop</button></div></div>
      </section>
      <section class="lab-card">
        <div class="lab-card-heading"><div><span class="lab-step">05</span><h3>Held-out evaluation</h3></div><span class="subtle">Not artistic scoring</span></div>
        <p class="lab-explainer">Evaluate both checkpoints on the same held-out prompt families. Test prompts are not used for gradient updates.</p>
        <div class="form-grid three">
          <label class="field-label">Checkpoint A<select id="eval-checkpoint" class="field-control"></select></label>
          <label class="field-label">Compare with<select id="eval-compare" class="field-control"><option value="">No comparison</option></select></label>
          <button id="evaluate-button" class="button secondary action-align">Evaluate test split</button>
        </div>
        <div id="evaluation-result" class="evaluation-result" hidden></div>
      </section>
      <section class="lab-card">
        <div class="lab-card-heading"><div><span class="lab-step">06</span><h3>Review records &amp; checkpoints</h3></div><button id="refresh-lab" class="text-button">Refresh</button></div>
        <div id="checkpoint-list" class="record-list"></div>
        <details class="record-details"><summary>Saved experiments</summary><div id="experiment-list" class="record-list"></div></details>
        <details class="record-details"><summary>Feedback review queue <span id="feedback-count" class="subtle"></span></summary><div id="feedback-list" class="record-list"></div></details>
      </section>
    </div>
  </div>
  <div class="lab-disclaimer"><strong>Scope:</strong> this model learns category, component presence, timing, colors, positions, and selected numeric properties, then maps them into plan v1. The adapter supplies the effect type, IDs, name, and resource defaults; they are not additional neural outputs. All effects remain <code>radial-burst</code>. “Beam,” “trail,” aura, charge, and orbit prompts are approximated with the existing core/ring/lightning/particle primitives. Generated JSON is never executed; Reasoner, Builder, Verifier, and the subjective artistic-quality judgment remain separate.</div>
</section>
<section class="pipeline"><span class="pipeline-label">THE PIPELINE</span><div class="pipeline-step"><span class="step-number">01</span><span>Designer <small>Random-start structured MLP</small></span></div>${icon("arrow", "pipeline-arrow")}<div class="pipeline-step"><span class="step-number">02</span><span>Reasoner <small>Schema + hard limits</small></span></div>${icon("arrow", "pipeline-arrow")}<div class="pipeline-step"><span class="step-number">03</span><span>Builder <small>Procedural geometry</small></span></div>${icon("arrow", "pipeline-arrow")}<div class="pipeline-step"><span class="step-number">04</span><span>Verifier <small>Structural checks</small></span></div><span class="pipeline-end">${icon("check")} Local-only · no paid AI</span></section>
<footer><span>VFXAI <span class="footer-slash">/</span> A small, inspectable training experiment</span><span>MODEL v0.3.0 <span class="footer-slash">·</span> PLAN v1.0</span></footer>`;

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

let labMeta = null;
let lastPrediction = null;
let compareReport = null;
let previousTrainingState = "idle";
let pollingBusy = false;

async function localApi(path, body) {
  const options = { cache: "no-store", credentials: "same-origin" };
  if (body !== undefined) {
    options.method = "POST";
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`Local API returned non-JSON (${response.status}). Start the app with START_VFXAI.bat.`);
  }
  if (!response.ok) throw new Error(data.error || `Local API request failed (${response.status}).`);
  return data;
}
function labMessage(message, kind = "info", target = "ai-message") {
  const node = $(target);
  if (!node) return;
  node.textContent = message;
  node.className = `ai-message ${kind}`;
  node.hidden = false;
}
function clearLabMessage(target = "ai-message") {
  const node = $(target);
  if (node) node.hidden = true;
}
function optionMarkup(value, label) {
  return `<option value="${escape(value)}">${escape(label)}</option>`;
}
function setSelectOptions(selectId, options, desired = "") {
  const select = $(selectId);
  const previous = select.value;
  select.innerHTML = options.map(([value, label]) => optionMarkup(value, label)).join("");
  const values = new Set(options.map(([value]) => value));
  select.value = values.has(previous) ? previous : values.has(desired) ? desired : (options[0]?.[0] ?? "");
}
function checkpointLabel(checkpoint) {
  const size = checkpoint.model?.hidden_size ? ` · h${checkpoint.model.hidden_size}` : "";
  const status = checkpoint.trained ? "trained" : "untrained random";
  return `${checkpoint.checkpoint_id} · ${status}${size}`;
}
function populateLabSelects() {
  const checkpoints = labMeta?.checkpoints || [];
  const allOptions = checkpoints.map((item) => [item.checkpoint_id, checkpointLabel(item)]);
  const defaultId = labMeta?.default_checkpoint || checkpoints[0]?.checkpoint_id || "";
  const trained = checkpoints.filter((item) => item.trained);
  const trainedOptions = [["", "Start from random weights"], ...trained.map((item) => [item.checkpoint_id, checkpointLabel(item)])];
  setSelectOptions("checkpoint-select", allOptions, defaultId);
  setSelectOptions("compare-a", allOptions, trained[0]?.checkpoint_id || defaultId);
  const compareDefault = checkpoints.find((item) => item.checkpoint_id !== $("compare-a").value)?.checkpoint_id || defaultId;
  setSelectOptions("compare-b", allOptions, trained.find((item) => item.checkpoint_id !== $("compare-a").value)?.checkpoint_id || compareDefault);
  setSelectOptions("eval-checkpoint", allOptions, trained[0]?.checkpoint_id || defaultId);
  const evalOther = checkpoints.find((item) => item.checkpoint_id !== $("eval-checkpoint").value)?.checkpoint_id || "";
  setSelectOptions("eval-compare", [["", "No comparison"], ...allOptions], "");
  if (!$("eval-compare").value && evalOther) $("eval-compare").value = evalOther;
  setSelectOptions("resume-checkpoint", trainedOptions, "");
  const categories = (labMeta?.categories || []).map((category) => [category, category.replaceAll("-", " ")]);
  setSelectOptions("feedback-category", categories, lastPrediction?.category || categories[0]?.[0] || "");
  $("compare-button").disabled = checkpoints.length < 2 || $("compare-a").value === $("compare-b").value;
  $("evaluate-button").disabled = checkpoints.length === 0;
  updateSelectedCheckpointBadge();
}
function updateSelectedCheckpointBadge() {
  const selected = (labMeta?.checkpoints || []).find((item) => item.checkpoint_id === $("checkpoint-select").value);
  if (!selected) {
    $("model-badge").textContent = "No checkpoint";
    return;
  }
  $("model-badge").textContent = selected.trained ? "TRAINED CHECKPOINT" : "UNTRAINED · RANDOM WEIGHTS";
  $("model-badge").classList.toggle("trained", selected.trained);
}
function renderCheckpointList() {
  const checkpoints = labMeta?.checkpoints || [];
  if (!checkpoints.length) {
    $("checkpoint-list").innerHTML = '<div class="empty-record">No checkpoint is available yet. Run first-time setup.</div>';
    return;
  }
  $("checkpoint-list").innerHTML = checkpoints.slice(0, 8).map((checkpoint) => {
    const metric = checkpoint.test?.valid_plan_rate;
    const detail = checkpoint.trained
      ? `Epoch ${checkpoint.epoch ?? "—"} · held-out valid ${metric == null ? "not evaluated" : `${(metric * 100).toFixed(0)}%`}`
      : `Random initialization · ${checkpoint.model?.parameter_count?.toLocaleString?.() || "—"} parameters`;
    return `<div class="record-row"><div><strong>${escape(checkpoint.checkpoint_id)}</strong><small>${escape(detail)}</small></div><button class="mini-button" data-select-checkpoint="${escape(checkpoint.checkpoint_id)}">Use</button></div>`;
  }).join("");
  for (const button of $("checkpoint-list").querySelectorAll("[data-select-checkpoint]")) {
    button.onclick = () => {
      const id = button.dataset.selectCheckpoint;
      $("checkpoint-select").value = id;
      updateSelectedCheckpointBadge();
      labMessage(`Selected ${id} for neural prompt inference.`);
    };
  }
}
function renderExperiments(items = []) {
  if (!items.length) {
    $("experiment-list").innerHTML = '<div class="empty-record">No training experiments recorded yet.</div>';
    return;
  }
  $("experiment-list").innerHTML = items.slice(0, 8).map((item) => {
    const comparison = item.test_comparison?.metrics?.category_accuracy;
    const delta = comparison ? comparison.delta_trained_minus_untrained : null;
    const detail = item.status === "failed"
      ? item.error || "Run failed; inspect the experiment JSON/log."
      : `Status: ${item.status || "unknown"}${delta == null ? "" : ` · category agreement Δ ${(delta * 100).toFixed(1)} pp`}`;
    return `<div class="record-row"><div><strong>${escape(item.run_id || "training run")}</strong><small>${escape(detail)}</small></div><span class="record-state">${escape(item.status || "saved")}</span></div>`;
  }).join("");
}
function renderFeedback(items = []) {
  $("feedback-count").textContent = `${items.length} saved`;
  if (!items.length) {
    $("feedback-list").innerHTML = '<div class="empty-record">No feedback records yet. Ratings never train automatically.</div>';
    return;
  }
  $("feedback-list").innerHTML = items.slice(0, 30).map((item) => {
    const issueText = (item.eligibility_issues || []).slice(0, 2).join("; ");
    const status = item.approval_status === "approved" ? "approved" : item.training_eligible ? "valid · pending review" : "rating only / not trainable";
    const prompt = (item.prompt || "").slice(0, 160);
    const action = item.approval_status === "pending" && item.training_eligible
      ? `<button class="mini-button approve-feedback" data-approve-feedback="${escape(item.id)}">Approve for training</button>`
      : `<span class="record-state">${escape(item.approval_status || "pending")}</span>`;
    return `<div class="record-row feedback-row"><div><strong>${escape(item.rating || "feedback")} · ${escape(item.category || "no category")}</strong><small>${escape(prompt)}${prompt.length >= 160 ? "…" : ""}</small><small>${escape(status)}${issueText ? ` · ${escape(issueText)}` : ""}</small></div>${action}</div>`;
  }).join("");
  for (const button of $("feedback-list").querySelectorAll("[data-approve-feedback]")) {
    button.onclick = async () => {
      button.disabled = true;
      try {
        const response = await localApi(`/api/feedback/${encodeURIComponent(button.dataset.approveFeedback)}/approve`, {});
        labMessage(response.message, "success", "feedback-message");
        await refreshLab();
      } catch (error) {
        labMessage(error.message, "error", "feedback-message");
        button.disabled = false;
      }
    };
  }
}
function updateDatasetSummary(dataset) {
  if (!dataset?.available) {
    $("dataset-badge").textContent = "NO DATASET";
    $("dataset-summary").textContent = "No active dataset. Generate a versioned synthetic prompt/plan dataset to train and evaluate. Existing local files are never deleted.";
    return;
  }
  const splits = dataset.split_counts || {};
  $("dataset-badge").textContent = `${dataset.count} EXAMPLES`;
  $("dataset-badge").classList.add("trained");
  $("dataset-summary").textContent = `${dataset.file}: ${splits.train || 0} train · ${splits.validation || 0} validation · ${splits.test || 0} held-out test. Plans are schema-checked; prompt families do not cross splits. Dataset version ${String(dataset.manifest?.sha256 || "unknown").slice(0, 12)}.`;
}
function renderTrainingStatus(status = {}) {
  const state = status.status || "idle";
  const active = ["starting", "running", "paused"].includes(state) && status.process_alive !== false;
  const percent = Math.max(0, Math.min(100, Math.round((Number(status.progress) || 0) * 100)));
  $("training-state").textContent = state === "idle" ? "No training run active" : `${state.toUpperCase()}${status.run_id ? ` · ${status.run_id}` : ""}`;
  $("training-progress-label").textContent = `${percent}%`;
  $("training-progress").style.width = `${percent}%`;
  let detail = status.message || "Training uses local CPU NumPy and saves checkpoints under .vfxai/checkpoints.";
  if (status.epoch && status.target_epochs) detail += ` · epoch ${status.epoch}/${status.target_epochs}`;
  if (status.last_loss?.total != null) detail += ` · batch loss ${Number(status.last_loss.total).toFixed(4)}`;
  if (status.checkpoint) detail += ` · checkpoint ${status.checkpoint}`;
  $("training-detail").textContent = detail;
  $("start-training").disabled = active;
  $("pause-training").disabled = !active || state !== "running";
  $("resume-training").disabled = !active || state !== "paused";
  $("stop-training").disabled = !active;
  if ((state === "completed" || state === "stopped") && previousTrainingState !== state) {
    setTimeout(() => refreshLab().catch(() => {}), 100);
  }
  previousTrainingState = state;
}
async function refreshTrainingStatus() {
  const status = await localApi("/api/training/status");
  renderTrainingStatus(status);
  return status;
}
async function refreshLab() {
  try {
    const [meta, experiments, feedback] = await Promise.all([
      localApi("/api/meta"),
      localApi("/api/experiments?limit=20"),
      localApi("/api/feedback"),
    ]);
    labMeta = meta;
    populateLabSelects();
    updateDatasetSummary(meta.dataset);
    renderCheckpointList();
    renderExperiments(experiments.experiments || []);
    renderFeedback(feedback.feedback || []);
    renderTrainingStatus(meta.training || {});
    if (!meta.dataset?.available) $("generate-dataset").disabled = false;
    return meta;
  } catch (error) {
    $("model-badge").textContent = "LOCAL API OFFLINE";
    $("dataset-badge").textContent = "API OFFLINE";
    labMessage(`${error.message} Use START_VFXAI.bat; npm run dev alone does not start the Python model/API.`, "error");
    return null;
  }
}
function renderPrediction(record) {
  lastPrediction = record;
  $("ai-result").hidden = false;
  $("feedback-editor").hidden = false;
  $("ai-category").textContent = record.category || "Unknown category";
  const valid = Boolean(record.validation?.ok);
  $("ai-validity").textContent = valid ? "Python checks passed" : "Invalid candidate preserved";
  $("ai-validity").classList.toggle("valid", valid);
  $("ai-validity").classList.toggle("invalid", !valid);
  $("ai-checkpoint-label").textContent = `${record.checkpoint_id} · ${record.model_trained ? "trained" : "random weights; untrained"}`;
  $("ai-confidence").textContent = `Category confidence ${Number(record.confidence || 0).toFixed(3)}`;
  $("ai-component-probs").innerHTML = (record.component_probabilities || []).map((entry) =>
    `<span class="prob-chip ${entry.selected ? "selected" : ""}">${escape(entry.component)} ${Number(entry.probability || 0).toFixed(2)}</span>`,
  ).join("");
  $("ai-plan-json").value = JSON.stringify(record.candidate_plan, null, 2);
  $("ai-raw-output").textContent = JSON.stringify({
    source: record.provenance,
    category_probabilities: record.category_probabilities,
    component_probabilities: record.component_probabilities,
    numeric_outputs_normalized: record.numeric_outputs_normalized,
    python_validation: record.validation,
  }, null, 2);
  $("feedback-category").value = record.category || "explosion";
  renderEditorValidation();
  if (!record.model_trained) {
    labMessage("This checkpoint has random weights and has not been trained. Its output is shown as-is; it is not replaced with a sample.", "warning");
  } else if (!valid) {
    labMessage("The neural prediction failed plan validation. Its raw candidate and failed checks are preserved; it was not rendered or replaced.", "warning");
  } else {
    labMessage("Neural structured prediction received. Use Preview only after the browser Reasoner, Builder, and Verifier pass.", "success");
  }
}
function renderEditorValidation() {
  const box = $("ai-validation");
  const previewButton = $("ai-preview");
  if (!lastPrediction) {
    previewButton.disabled = true;
    box.textContent = "Generate a neural candidate to inspect it.";
    box.className = "validation-box";
    return;
  }
  try {
    const plan = JSON.parse($("ai-plan-json").value);
    const checked = construct(plan);
    if (checked.ok) {
      previewButton.disabled = false;
      box.className = "validation-box valid";
      box.textContent = JSON.stringify(plan) === JSON.stringify(lastPrediction.candidate_plan)
        ? "Browser schema + Reasoner + Builder + Verifier passed. This candidate may be previewed."
        : "Edited JSON passes browser Reasoner + Builder + Verifier. The original neural output remains saved separately.";
    } else {
      previewButton.disabled = true;
      box.className = "validation-box invalid";
      box.textContent = `${checked.stage} rejected this candidate: ${checked.issues.slice(0, 6).map((issue) => `${issue.code} ${issue.path}: ${issue.message} ${issue.correction}`).join(" • ")}`;
    }
  } catch (error) {
    previewButton.disabled = true;
    box.className = "validation-box invalid";
    box.textContent = `Candidate JSON is invalid: ${error.message}`;
  }
}
function downloadText(filename, text) {
  const blob = new Blob([text.endsWith("\n") ? text : `${text}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function renderCompare(report) {
  compareReport = report;
  const summaries = [report.checkpoint_a, report.checkpoint_b];
  $("compare-result").hidden = false;
  $("compare-result").innerHTML = summaries.map((record, index) => {
    const check = record.validation?.ok ? "valid" : "invalid";
    const selected = (record.component_probabilities || []).filter((item) => item.selected).map((item) => item.component).join(", ") || "none selected";
    return `<article class="compare-card"><div class="result-header"><div><span class="eyebrow">CHECKPOINT ${index ? "B" : "A"}</span><h4>${escape(record.category)}</h4></div><span class="validity-badge ${check}">${record.validation?.ok ? "valid plan" : "invalid plan"}</span></div><p>${escape(record.checkpoint_id)} · confidence ${Number(record.confidence || 0).toFixed(3)}</p><small>Components: ${escape(selected)}</small><button class="mini-button use-comparison" data-use-comparison="${index}">Inspect this raw output</button></article>`;
  }).join("");
  for (const button of $("compare-result").querySelectorAll("[data-use-comparison]")) {
    button.onclick = () => renderPrediction(summaries[Number(button.dataset.useComparison)]);
  }
}
function metricText(report) {
  return `<div class="metric-grid"><div><span>Category agreement</span><strong>${(report.category_accuracy * 100).toFixed(1)}%</strong></div><div><span>Exact component mask</span><strong>${(report.component_exact_match * 100).toFixed(1)}%</strong></div><div><span>Component F1</span><strong>${report.component_f1.toFixed(3)}</strong></div><div><span>Normalized numeric MAE</span><strong>${report.numeric_mae_normalized.toFixed(3)}</strong></div><div><span>Plan-v1 validity</span><strong>${(report.valid_plan_rate * 100).toFixed(1)}% (${report.valid_plan_count}/${report.example_count})</strong></div><div><span>Total test loss</span><strong>${report.loss.total.toFixed(4)}</strong></div></div>`;
}
function renderEvaluation(result) {
  $("evaluation-result").hidden = false;
  const reports = result.reports || [];
  const cards = reports.map((report) => `<article class="evaluation-card"><h4>${escape(report.checkpoint_id)} · ${escape(report.split)} (${report.example_count} prompts)</h4>${metricText(report)}<details><summary>Validation issue counts</summary><pre>${escape(JSON.stringify(report.validation_issue_counts, null, 2))}</pre></details></article>`).join("");
  const comparison = result.comparison?.metrics
    ? `<p class="evaluation-note">Same held-out prompts. Differences describe target agreement/validity only, not artistic quality.</p><div class="comparison-deltas">${Object.entries(result.comparison.metrics).map(([key, item]) => `<span>${escape(key.replaceAll("_", " "))}: Δ ${Number(item.delta_b_minus_a).toFixed(4)}</span>`).join("")}</div>`
    : "";
  $("evaluation-result").innerHTML = `${cards}${comparison}<small>Full raw predictions, including invalid candidates, saved locally: ${escape(result.output_directory)}</small>`;
}

$("checkpoint-select").onchange = updateSelectedCheckpointBadge;
$("compare-a").onchange = populateLabSelects;
$("compare-b").onchange = () => {
  $("compare-button").disabled = $("compare-a").value === $("compare-b").value;
};
$("ai-plan-json").addEventListener("input", renderEditorValidation);
$("generate").onclick = async () => {
  const button = $("generate");
  button.disabled = true;
  clearLabMessage();
  try {
    const design = await designer.design($("ai-prompt").value, {
      checkpointId: $("checkpoint-select").value,
      seed: Number($("generation-seed").value),
    });
    if (!design.prediction) throw new Error(design.issues.map((issue) => issue.message).join(" "));
    renderPrediction(design.prediction);
  } catch (error) {
    labMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
};
$("ai-preview").onclick = () => {
  try {
    const candidate = JSON.parse($("ai-plan-json").value);
    loadPlan(candidate);
    labMessage("Validated candidate sent to the deterministic Builder/preview. Neural output and checkpoint remain unchanged.", "success");
  } catch (error) {
    showError(`Candidate not loaded: ${error.message}`);
    labMessage(`Candidate not loaded: ${error.message}`, "error");
  }
};
$("ai-download").onclick = () => {
  if (!lastPrediction) return;
  downloadText("neural-candidate.vfx.json", $("ai-plan-json").value);
};
$("compare-button").onclick = async () => {
  const button = $("compare-button");
  button.disabled = true;
  try {
    const report = await localApi("/api/compare", {
      prompt: $("ai-prompt").value,
      checkpoint_a: $("compare-a").value,
      checkpoint_b: $("compare-b").value,
      seed: Number($("generation-seed").value),
    });
    renderCompare(report);
  } catch (error) {
    labMessage(error.message, "error");
  } finally {
    button.disabled = $("compare-a").value === $("compare-b").value;
  }
};
$("save-feedback").onclick = async () => {
  if (!lastPrediction) return labMessage("Generate or compare a prediction before saving feedback.", "error", "feedback-message");
  const payload = {
    generation_id: lastPrediction.id,
    rating: $("feedback-rating").value,
    category: $("feedback-category").value,
    notes: $("feedback-notes").value,
  };
  if ($("feedback-plan").value.trim()) {
    payload.corrected_plan_json = $("feedback-plan").value;
  } else if (
    $("ai-plan-json").value.trim() &&
    $("ai-plan-json").value !== JSON.stringify(lastPrediction.candidate_plan, null, 2)
  ) {
    payload.corrected_plan_json = $("ai-plan-json").value;
  }
  $("save-feedback").disabled = true;
  try {
    const response = await localApi("/api/feedback", payload);
    const feedback = response.feedback;
    labMessage(`${response.message} ${feedback.training_eligible ? "This plan is valid and can be explicitly approved." : "This is stored as feedback only: " + (feedback.eligibility_issues || []).join("; ")}`, feedback.training_eligible ? "success" : "warning", "feedback-message");
    const queue = await localApi("/api/feedback");
    renderFeedback(queue.feedback || []);
  } catch (error) {
    labMessage(error.message, "error", "feedback-message");
  } finally {
    $("save-feedback").disabled = false;
  }
};
$("generate-dataset").onclick = async () => {
  const button = $("generate-dataset");
  button.disabled = true;
  try {
    const result = await localApi("/api/dataset/generate", {
      count: Number($("dataset-count").value),
      seed: Number($("dataset-seed").value),
    });
    labMessage(`Created ${result.manifest.actual_count} validated prompt/plan pairs in ${result.manifest.dataset_file}. The new dataset is active; older datasets remain in place.`, "success");
    await refreshLab();
  } catch (error) {
    labMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
};
$("start-training").onclick = async () => {
  const button = $("start-training");
  button.disabled = true;
  try {
    const payload = {
      epochs: Number($("train-epochs").value),
      batch_size: Number($("train-batch").value),
      hidden_size: Number($("train-hidden").value),
      learning_rate: Number($("train-rate").value),
      seed: Number($("train-seed").value),
      include_feedback: $("include-feedback").checked,
    };
    if ($("resume-checkpoint").value) payload.resume_checkpoint = $("resume-checkpoint").value;
    const response = await localApi("/api/train/start", payload);
    labMessage(`${response.message} Run ${response.run_id}.`, "success");
    await refreshTrainingStatus();
  } catch (error) {
    labMessage(error.message, "error");
    button.disabled = false;
  }
};
async function trainingControl(action) {
  try {
    await localApi("/api/train/control", { action });
    await refreshTrainingStatus();
  } catch (error) {
    labMessage(error.message, "error");
  }
}
$("pause-training").onclick = () => trainingControl("pause");
$("resume-training").onclick = () => trainingControl("resume");
$("stop-training").onclick = () => trainingControl("stop");
$("evaluate-button").onclick = async () => {
  const button = $("evaluate-button");
  button.disabled = true;
  try {
    const payload = { checkpoint_id: $("eval-checkpoint").value, split: "test" };
    if ($("eval-compare").value) payload.compare_checkpoint = $("eval-compare").value;
    const result = await localApi("/api/evaluate", payload);
    renderEvaluation(result);
  } catch (error) {
    labMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
};
$("refresh-lab").onclick = () => refreshLab();
refreshLab();
setInterval(async () => {
  if (pollingBusy) return;
  pollingBusy = true;
  try {
    await refreshTrainingStatus();
  } catch {
    // The app can be temporarily unavailable while Python starts; the next poll retries.
  } finally {
    pollingBusy = false;
  }
}, 1800);
