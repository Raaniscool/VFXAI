import { reason, issue } from "./reasoner.js";
import { sampleComponent } from "./builder.js";

/** Structural correctness only; does not measure beauty or Roblox compatibility. */
export function verify(plan, built) {
  const input = reason(plan);
  if (!input.ok) return { ...input, coverage: 0 };
  const issues = [];
  const fail = (
    code,
    path,
    message,
    correction = "Rebuild from the validated plan.",
  ) => issues.push(issue(code, path, message, correction));
  if (!built || !Array.isArray(built.components)) {
    return {
      ok: false,
      coverage: 0,
      issues: [
        issue(
          "NO_BUILD",
          "/",
          "No construction to verify.",
          "Build the validated plan first.",
        ),
      ],
    };
  }
  if (
    built.schemaVersion !== plan.schemaVersion ||
    built.duration !== plan.duration ||
    built.name !== plan.name
  )
    fail(
      "BUILD_HEADER",
      "/",
      "Build name, version or duration differs from plan.",
    );
  const actual = built.components.filter(
    (c) => c && typeof c === "object" && !Array.isArray(c),
  );
  if (actual.length !== built.components.length)
    fail(
      "INVALID_COMPONENT",
      "/components",
      "Construction contains malformed component records.",
    );
  const expectedIds = new Set(plan.components.map((c) => c.id));
  const actualIds = new Set();
  let covered = 0,
    objects = 0,
    particles = 0;
  for (const c of actual) {
    if (actualIds.has(c.id))
      fail(
        "DUPLICATE_BUILD_ID",
        `/components/${c.id}`,
        "Duplicate constructed component.",
      );
    actualIds.add(c.id);
    if (!expectedIds.has(c.id))
      fail(
        "UNEXPECTED_COMPONENT",
        `/components/${c.id}`,
        "Construction includes an unrequested component.",
      );
  }
  for (const spec of plan.components) {
    const c = actual.find((item) => item.id === spec.id);
    const path = `/components/${spec.id}`;
    if (!c) {
      fail("MISSING_COMPONENT", path, "Required component missing.");
      continue;
    }
    const before = issues.length;
    for (const key of [
      "type",
      "color",
      "position",
      "start",
      "duration",
      "properties",
    ]) {
      if (JSON.stringify(c[key]) !== JSON.stringify(spec[key]))
        fail(
          "PROPERTY_MISMATCH",
          `${path}/${key}`,
          "Built property differs from specification.",
        );
    }
    if (c.type === "lightning" || c.type === "particles") {
      if (
        !Array.isArray(c.geometry) ||
        c.geometry.length !== spec.properties.count
      ) {
        fail(
          "GEOMETRY_COUNT",
          `${path}/geometry`,
          "Constructed count differs from specification.",
        );
      } else {
        const vectors = c.type === "lightning" ? c.geometry.flat() : c.geometry;
        if (
          c.type === "lightning" &&
          c.geometry.some(
            (arc) =>
              !Array.isArray(arc) ||
              arc.length !== spec.properties.segments + 1,
          )
        )
          fail("ARC_SEGMENTS", path, "Lightning segment count is incorrect.");
        if (
          vectors.some(
            (v) =>
              !Array.isArray(v) ||
              v.length !== 3 ||
              v.some((n) => !Number.isFinite(n)),
          )
        )
          fail(
            "INVALID_GEOMETRY",
            path,
            "Geometry must contain finite 3D vectors.",
          );
      }
    }
    try {
      for (const time of [
        0,
        c.start,
        c.start + c.duration / 2,
        plan.duration,
      ]) {
        const state = sampleComponent(c, time);
        if (
          !Number.isFinite(state.opacity) ||
          state.opacity < 0 ||
          state.opacity > 1 ||
          !Number.isFinite(state.scale) ||
          state.scale <= 0 ||
          (state.positions &&
            state.positions.flat().some((n) => !Number.isFinite(n)))
        )
          fail(
            "INVALID_ANIMATION",
            path,
            "Sampled animation has invalid values.",
          );
        if (time === plan.duration && state.visible)
          fail(
            "ANIMATION_OVERFLOW",
            path,
            "Component remains visible after the effect.",
          );
      }
    } catch {
      fail("INVALID_ANIMATION", path, "Animation cannot be sampled.");
    }
    if (issues.length === before) covered++;
    objects +=
      c.type === "core"
        ? 2
        : c.type === "lightning"
          ? Array.isArray(c.geometry)
            ? c.geometry.length
            : 0
          : 1;
    if (c.type === "particles")
      particles += Array.isArray(c.geometry) ? c.geometry.length : 0;
  }
  if (
    objects > plan.constraints.maxObjects ||
    particles > plan.constraints.maxParticles
  )
    fail(
      "BUILD_BUDGET",
      "/",
      "Actual construction exceeds the requested budget.",
      "Reduce actual geometry counts.",
    );
  if (built.stats?.objects !== objects || built.stats?.particles !== particles)
    fail(
      "BUILD_STATS",
      "/stats",
      "Reported counts do not match the construction.",
    );
  return {
    ok: issues.length === 0,
    issues,
    coverage: covered / plan.components.length,
    stats: { objects, particles },
    qualityEvaluated: false,
  };
}
