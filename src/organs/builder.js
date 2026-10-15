import { reason } from "./reasoner.js";
import {
  clamp,
  lerp,
  easeOut,
  seededRandom,
  componentSeed,
} from "../engine/math.js";

export class PlanError extends Error {
  constructor(report) {
    super("Construction plan rejected");
    this.name = "PlanError";
    this.report = report;
  }
}

/** Builder boundary always validates, including when called without the pipeline.
 * Returns renderer-independent, seeded geometry descriptors, never executable code.
 */
export function build(plan) {
  const report = reason(plan);
  if (!report.ok) throw new PlanError(report);
  const snapshot = structuredClone(plan);
  const components = snapshot.components.map((c) => {
    const random = seededRandom(componentSeed(snapshot.seed, c.id));
    const descriptor = { ...c, geometry: null };
    if (c.type === "lightning") {
      const { count, segments, length, jitter } = c.properties;
      descriptor.geometry = Array.from({ length: count }, (_, arc) => {
        const angle = (arc / count) * Math.PI * 2;
        return Array.from({ length: segments + 1 }, (_, j) => {
          const t = j / segments;
          const offset =
            j === 0 || j === segments ? 0 : (random() - 0.5) * jitter * length;
          return [
            Math.cos(angle) * length * t - Math.sin(angle) * offset,
            Math.sin(t * Math.PI) * (0.2 + random() * 0.45) + offset * 0.4,
            Math.sin(angle) * length * t + Math.cos(angle) * offset,
          ];
        });
      });
    }
    if (c.type === "particles") {
      descriptor.geometry = Array.from({ length: c.properties.count }, () => {
        const angle = random() * Math.PI * 2;
        const y = random() * 1.5 - 0.45;
        const radial = Math.sqrt(1 - Math.min(1, y * y));
        const speed = c.properties.speed * (0.45 + random() * 0.55);
        return [
          Math.cos(angle) * radial * speed,
          y * speed,
          Math.sin(angle) * radial * speed,
        ];
      });
    }
    return descriptor;
  });
  return {
    schemaVersion: "1.0",
    name: snapshot.name,
    duration: snapshot.duration,
    components,
    stats: report.stats,
  };
}

/** Absolute-time animation; seeking/replay is deterministic, never accumulates drift.
 * All geometry uses local coordinates. Renderer adds the component position.
 */
export function sampleComponent(c, time) {
  if (!Number.isFinite(time)) throw new TypeError("Time must be finite.");
  const age = time - c.start;
  const t = clamp(age / c.duration);
  const visible = age >= 0 && age < c.duration;
  const opacity = visible ? (1 - t) ** 1.5 : 0;
  const state = { visible, opacity, scale: 1, positions: null, radius: null };
  switch (c.type) {
    case "core":
      state.scale = (0.35 + Math.sin(Math.PI * t) * 1.4) * (1 - t * 0.6);
      break;
    case "ring":
      state.radius = lerp(
        c.properties.radius,
        c.properties.endRadius,
        easeOut(t),
      );
      break;
    case "lightning":
      state.scale = 0.15 + easeOut(t) * 0.85;
      state.opacity *= 0.72 + Math.sin(t * 65) ** 2 * 0.28;
      break;
    case "particles":
      state.positions = c.geometry.map((v) => [
        v[0] * age,
        v[1] * age - 0.5 * c.properties.gravity * age ** 2,
        v[2] * age,
      ]);
      break;
  }
  return state;
}
