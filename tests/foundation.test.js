import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import plan from "../examples/lightning-burst.vfx.json" with { type: "json" };
import { reason } from "../src/organs/reasoner.js";
import { build, sampleComponent, PlanError } from "../src/organs/builder.js";
import { verify } from "../src/organs/verifier.js";
import { designer } from "../src/organs/designer.js";
import { construct } from "../src/pipeline.js";
import { seededRandom } from "../src/engine/math.js";
const copy = () => structuredClone(plan);
const rejects = (edit, code) => {
  const p = copy();
  edit(p);
  const report = reason(p);
  assert.equal(report.ok, false);
  assert.ok(
    report.issues.some((i) => i.code === code),
    JSON.stringify(report),
  );
  assert.ok(report.issues.every((i) => i.path && i.correction));
  assert.throws(() => build(p), PlanError);
  const pipeline = construct(p);
  assert.equal(pipeline.stage, "reasoner");
  assert.equal(pipeline.built, undefined);
};

test("manual example validates with concrete resource counts, without mutation", () => {
  const before = JSON.stringify(plan);
  assert.deepEqual(reason(plan).stats, {
    components: 5,
    objects: 13,
    particles: 96,
    vertices: 1912,
  });
  assert.equal(reason(plan).ok, true);
  assert.equal(JSON.stringify(plan), before);
  const missing = copy();
  delete missing.seed;
  assert.equal(reason(missing).ok, false);
  assert.equal("seed" in missing, false);
});
test("rejects malformed and unsupported schemas independently of Designer", () => {
  for (const bad of [null, {}, [], "plan"]) assert.equal(reason(bad).ok, false);
  rejects((p) => {
    p.schemaVersion = "2.0";
  }, "SCHEMA");
  rejects((p) => {
    p.components[0].type = "script";
  }, "SCHEMA");
  rejects((p) => {
    p.code = "alert(1)";
  }, "SCHEMA");
  rejects((p) => {
    p.components[0].properties.unrecognized = true;
  }, "SCHEMA");
});
test("rejects unsafe numbers, invalid colors and vectors", () => {
  for (const value of [NaN, Infinity, -1, 0, 11, "1.5"])
    rejects((p) => {
      p.duration = value;
    }, "SCHEMA");
  rejects((p) => {
    p.components[0].color = "<script>";
  }, "SCHEMA");
  rejects((p) => {
    p.components[0].position = [0, 0];
  }, "SCHEMA");
  rejects((p) => {
    p.components[0].position[2] = Infinity;
  }, "SCHEMA");
  rejects((p) => {
    p.components[4].properties.count = 1.5;
  }, "SCHEMA");
});
test("checks unique ids, timing and spatial contradictions", () => {
  rejects((p) => {
    p.components[1].id = "core";
  }, "DUPLICATE_ID");
  rejects((p) => {
    p.components[1].start = 1;
  }, "TIMELINE_OVERFLOW");
  rejects((p) => {
    p.components[2].properties.endRadius = 0.2;
  }, "RING_CONTRACTS");
  rejects((p) => {
    p.components[2].properties.radius = 0.1;
    p.components[2].properties.thickness = 0.2;
  }, "RING_THICKNESS");
});
test("enforces declared and hard budgets before allocation", () => {
  rejects((p) => {
    p.constraints.maxObjects = 12;
  }, "OBJECT_BUDGET");
  rejects((p) => {
    p.constraints.maxParticles = 95;
  }, "PARTICLE_BUDGET");
  rejects((p) => {
    p.constraints.maxParticles = 999;
  }, "SCHEMA");
  rejects((p) => {
    p.components[4].properties.count = 513;
  }, "SCHEMA");
  rejects((p) => {
    p.components = Array.from({ length: 15 }, (_, i) => ({
      ...structuredClone(p.components[2]),
      id: `ring-${i}`,
    }));
    p.constraints.maxObjects = 256;
  }, "VERTEX_BUDGET");
});
test("builds real geometry with exact arc and particle counts", () => {
  const built = build(plan);
  const arcs = built.components.find((c) => c.type === "lightning");
  assert.equal(arcs.geometry.length, 8);
  assert.ok(arcs.geometry.every((arc) => arc.length === 13));
  assert.ok(
    arcs.geometry
      .flat()
      .every((v) => v.length === 3 && v.every(Number.isFinite)),
  );
  for (const arc of arcs.geometry) {
    assert.ok(Math.abs(arc[0][0]) < 1e-10 && Math.abs(arc[0][2]) < 1e-10);
    const end = arc.at(-1);
    assert.ok(Math.abs(Math.hypot(end[0], end[2]) - 4.5) < 1e-9);
  }
  assert.equal(
    built.components.find((c) => c.type === "particles").geometry.length,
    96,
  );
});
test("seeded construction is reproducible, isolated and sensitive to seed", () => {
  assert.deepEqual(build(plan), build(plan));
  const p = copy();
  p.seed++;
  assert.notDeepEqual(
    build(p).components[1].geometry,
    build(plan).components[1].geometry,
  );
  const first = build(plan);
  first.components[0].properties.radius = 3;
  assert.equal(plan.components[0].properties.radius, 0.65);
  const r1 = seededRandom(0),
    r2 = seededRandom(0);
  for (let i = 0; i < 20; i++) {
    const n = r1();
    assert.equal(n, r2());
    assert.ok(n >= 0 && n < 1);
  }
});
test("every component activates and fades in its specified time window", () => {
  for (const c of build(plan).components) {
    assert.equal(sampleComponent(c, c.start - 0.001).visible, false);
    assert.equal(sampleComponent(c, c.start).visible, true);
    const mid = sampleComponent(c, c.start + c.duration / 2);
    assert.equal(mid.visible, true);
    assert.ok(mid.opacity > 0 && mid.opacity <= 1);
    assert.equal(sampleComponent(c, c.start + c.duration).opacity, 0);
    assert.equal(sampleComponent(c, plan.duration).visible, false);
  }
});
test("rings expand monotonically between authored radii", () => {
  const c = build(plan).components[2];
  assert.equal(sampleComponent(c, c.start).radius, c.properties.radius);
  let previous = 0;
  for (let i = 0; i <= 100; i++) {
    const radius = sampleComponent(c, c.start + (c.duration * i) / 100).radius;
    assert.ok(radius >= previous);
    previous = radius;
  }
  assert.equal(previous, c.properties.endRadius);
});
test("particles follow velocity and gravity, and seeking does not drift", () => {
  const c = build(plan).components[4];
  const age = 0.5;
  const state = sampleComponent(c, c.start + age);
  const v = c.geometry[0],
    pos = state.positions[0];
  assert.ok(Math.abs(pos[0] - v[0] * age) < 1e-10);
  assert.ok(
    Math.abs(pos[1] - (v[1] * age - 0.5 * c.properties.gravity * age ** 2)) <
      1e-10,
  );
  sampleComponent(c, 0);
  sampleComponent(c, 1.5);
  assert.deepEqual(state, sampleComponent(c, c.start + age));
  assert.throws(() => sampleComponent(c, Infinity), TypeError);
});
test("successful pipeline reports structural coverage, not artistic quality", () => {
  const result = construct(plan);
  assert.equal(result.ok, true);
  assert.equal(result.verification.coverage, 1);
  assert.equal(result.verification.qualityEvaluated, false);
});
test("Verifier finds missing, extra, duplicate and mismatched components", () => {
  const changes = [
    [(b) => b.components.pop(), "MISSING_COMPONENT"],
    [
      (b) => {
        b.components[0] = null;
      },
      "INVALID_COMPONENT",
    ],
    [
      (b) => b.components.push({ ...b.components[0], id: "extra" }),
      "UNEXPECTED_COMPONENT",
    ],
    [(b) => b.components.push(b.components[0]), "DUPLICATE_BUILD_ID"],
    [
      (b) => {
        b.components[0].color = "#ffffff";
      },
      "PROPERTY_MISMATCH",
    ],
    [
      (b) => {
        b.duration = 2;
      },
      "BUILD_HEADER",
    ],
    [
      (b) => {
        b.stats.objects = 0;
      },
      "BUILD_STATS",
    ],
    [
      (b) => {
        b.components[1].geometry.pop();
      },
      "GEOMETRY_COUNT",
    ],
    [
      (b) => {
        b.components[1].geometry[0].pop();
      },
      "ARC_SEGMENTS",
    ],
    [
      (b) => {
        b.components[4].geometry[0][0] = NaN;
      },
      "INVALID_GEOMETRY",
    ],
  ];
  for (const [mutate, code] of changes) {
    const built = build(plan);
    mutate(built);
    const report = verify(plan, built);
    assert.equal(report.ok, false);
    assert.ok(
      report.issues.some((i) => i.code === code),
      JSON.stringify(report),
    );
  }
  assert.equal(verify(plan, null).ok, false);
  const invalid = copy();
  invalid.duration = 0;
  assert.equal(verify(invalid, build(plan)).ok, false);
});
test("Python Designer adapter fails explicitly instead of fabricating a plan", async () => {
  const result = await designer.design("blue explosion", {
    checkpointId: "not-used-without-a-server",
    seed: 1,
  });
  assert.equal(result.ok, false);
  assert.equal(result.plan, null);
  assert.equal(result.prediction, null);
  assert.equal(result.issues[0].code, "LOCAL_API_UNAVAILABLE");
  assert.match(result.issues[0].message, /Local Python Designer is unavailable/);
});
test("training launcher consumes its internal /nopause switch before forwarding CLI args", () => {
  const source = readFileSync(new URL("../TRAIN_VFXAI.bat", import.meta.url), "utf8");
  const command = source.split(/\r?\n/).find((line) => /^python -m vfxai\.cli train /i.test(line));
  assert.match(source, /if \/i "%~1"=="\/nopause"/i);
  assert.match(source, /shift/i);
  assert.ok(command);
  assert.doesNotMatch(command, /%\*/);
  assert.match(command, /%1 %2 %3/);
});
test("Python Designer bridge preserves an invalid neural candidate without fallback", async () => {
  const originalFetch = globalThis.fetch;
  const predicted = {
    candidate_plan: { schemaVersion: "1.0", components: [] },
    validation: { ok: false, issues: [{ code: "SCHEMA", path: "/components", message: "No components" }] },
  };
  let requestURL;
  try {
    globalThis.fetch = async (url, options) => {
      requestURL = url;
      assert.equal(options.credentials, "same-origin");
      return new Response(JSON.stringify(predicted), { status: 200, headers: { "Content-Type": "application/json" } });
    };
    const result = await designer.design("test prompt", { checkpointId: "random-seed-1-h16", seed: 7 });
    assert.equal(requestURL, "/api/generate");
    assert.equal(result.ok, false);
    assert.deepEqual(result.plan, predicted.candidate_plan);
    assert.deepEqual(result.prediction, predicted);
    assert.equal(result.issues[0].code, "SCHEMA");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
