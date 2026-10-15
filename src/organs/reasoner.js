import validate from "../plan-validator.js";

export const PLAN_VERSION = "1.0";
export const HARD_LIMITS = Object.freeze({
  objects: 256,
  particles: 512,
  vertices: 8192,
});

/** @typedef {{code:string, path:string, message:string, correction:string}} Issue */
export function issue(code, path, message, correction) {
  return { code, path, message, correction };
}

/** Independent input boundary. No coercion, default insertion, or plan mutation. */
export function reason(plan) {
  if (!validate(plan)) {
    return {
      ok: false,
      schemaVersion: PLAN_VERSION,
      stats: null,
      issues: validate.errors.map((e) =>
        issue(
          "SCHEMA",
          e.instancePath || "/",
          `${e.message}${e.params.additionalProperty ? `: ${e.params.additionalProperty}` : ""}`,
          `Use the plan 1.0 schema; fix ${e.instancePath || "/"} (${e.keyword}).`,
        ),
      ),
    };
  }
  const issues = [];
  const ids = new Set();
  let objects = 0,
    particles = 0,
    vertices = 0;
  plan.components.forEach((c, i) => {
    const path = `/components/${i}`;
    if (ids.has(c.id))
      issues.push(
        issue(
          "DUPLICATE_ID",
          `${path}/id`,
          `Duplicate id: ${c.id}`,
          "Assign a unique component id.",
        ),
      );
    ids.add(c.id);
    if (c.start + c.duration > plan.duration + 1e-9) {
      issues.push(
        issue(
          "TIMELINE_OVERFLOW",
          path,
          "Component ends after the effect.",
          "Reduce start or duration to fit the effect timeline.",
        ),
      );
    }
    const p = c.properties;
    if (c.type === "ring" && p.endRadius < p.radius)
      issues.push(
        issue(
          "RING_CONTRACTS",
          `${path}/properties/endRadius`,
          "A shockwave must expand.",
          "Set endRadius >= radius.",
        ),
      );
    if (c.type === "ring" && p.thickness >= p.radius)
      issues.push(
        issue(
          "RING_THICKNESS",
          `${path}/properties/thickness`,
          "Ring thickness consumes the central opening.",
          "Set thickness < radius.",
        ),
      );
    switch (c.type) {
      case "core":
        objects += 2;
        vertices += 542;
        break; // sphere + glow shell
      case "ring":
        objects++;
        vertices += 585;
        break;
      case "lightning":
        objects += p.count;
        vertices += p.count * (p.segments + 1);
        break;
      case "particles":
        objects++;
        particles += p.count;
        vertices += p.count;
        break;
    }
  });
  if (objects > plan.constraints.maxObjects)
    issues.push(
      issue(
        "OBJECT_BUDGET",
        "/constraints/maxObjects",
        `${objects} render objects exceed the budget.`,
        "Reduce component counts or raise maxObjects within the hard limit.",
      ),
    );
  if (particles > plan.constraints.maxParticles)
    issues.push(
      issue(
        "PARTICLE_BUDGET",
        "/constraints/maxParticles",
        `${particles} particles exceed the budget.`,
        "Reduce particle counts or raise maxParticles within the hard limit.",
      ),
    );
  if (vertices > HARD_LIMITS.vertices)
    issues.push(
      issue(
        "VERTEX_BUDGET",
        "/components",
        `${vertices} vertices exceed ${HARD_LIMITS.vertices}.`,
        "Reduce component counts or lightning segments.",
      ),
    );
  return {
    ok: issues.length === 0,
    schemaVersion: PLAN_VERSION,
    issues,
    stats: { components: ids.size, objects, particles, vertices },
  };
}
