# Milestone 1 architecture and plan contract

> This document records the procedural foundation. The 0.2.0 desktop conversion now wraps it in Electron; see [Windows desktop](windows-desktop.md) for the current application shell and packaging. The plan and organ contracts below remain unchanged.

## Stack decision

The initial checkout contained only a README and an initial commit. There was no desktop framework or engine to preserve. Node 22 was available. JavaScript ES modules, Vite, Three.js, and Ajv minimize dependencies and permit a working local preview on Windows without installing Python or a large desktop shell. Node's own test runner exercises the engine without a graphics device. Playwright is development-only.

Trade-offs: this is a standalone local **browser application**, not a native desktop installer; Three.js needs WebGL2 and accounts for most of the client bundle; units and shader behavior are preview-specific, not an export promise. No runtime cloud API or neural-network framework is added in M1. CPU training feasibility has not been benchmarked.

## Module interfaces

All plan-facing organs exchange structured objects, not prose or generated code:

```js
// Designer interface (M1 implementation explicitly unavailable)
await designer.design(prompt);
// -> { ok, plan: PlanV1 | null, issues: Issue[] }

reason(plan);
// -> { ok, schemaVersion: '1.0', issues, stats: Stats | null }

build(plan);
// -> BuiltEffectV1; throws PlanError with .report on invalid input

sampleComponent(builtComponent, seconds);
// -> { visible, opacity, scale, radius: number | null, positions: number[][] | null }

verify(plan, built);
// -> { ok, issues, coverage, stats?, qualityEvaluated: false }
// Invalid input/no build paths return a failed report without quality evaluation.

construct(plan);
// -> { ok: true, built, reasoning, verification }
// or { ok: false, stage: 'reasoner' | 'verifier', issues }
```

`Issue` is `{ code, path, message, correction }`; `path` refers to the input plan or built descriptor. `Stats` is `{ components, objects, particles, vertices }`. The UI displays errors with codes and corrections; validation and verification reports are directly usable in future evaluation code.

The Builder validates even when called directly. It snapshots the input, then creates descriptors. No geometry is allocated for rejected plans. The pipeline builds only after Reasoner acceptance and sends only verified descriptors to the preview. The Verifier validates the original plan independently and inspects the actual descriptors, not only the reported statistics. It does not rely on a working Designer.

There is exactly **one construction attempt and zero automatic correction retries**. A failed plan requires an explicit corrected load. No hidden retry loop exists. Automatic correction belongs to later milestones.

`BuiltEffectV1` has `schemaVersion`, `name`, `duration`, `components`, and `stats`. Each built component copies its specification and adds `geometry`: local-coordinate polyline vectors for lightning, velocity vectors for particles, or `null` for analytic spheres/rings. This is a preview-neutral descriptor, not a serialized Roblox scene. The Three.js adapter owns disposable meshes, buffers, materials and camera controls; mathematical construction and time sampling do not import Three.js or browser APIs.

## Plan 1.0

The executable source of truth is [`schemas/plan-v1.schema.json`](../schemas/plan-v1.schema.json), draft-07. Version matching is exact. Unknown fields, unsupported types, malformed vectors, non-finite numbers, and out-of-range properties fail validation. Numeric strings are not coerced. JSON files cannot carry executable scripts.

Top-level fields are all required:

| Field                      | Meaning / range                 | Authoring default    |
| -------------------------- | ------------------------------- | -------------------- |
| `schemaVersion`            | Exactly `"1.0"`                 | `"1.0"`              |
| `name`                     | Display name, 1–80 characters   | `"Untitled burst"`   |
| `effectType`               | Exactly `"radial-burst"` in M1  | `"radial-burst"`     |
| `duration`                 | Effect duration, 0.1–10 seconds | 1.5                  |
| `seed`                     | Unsigned 32-bit integer         | 42                   |
| `constraints.maxObjects`   | 1–256 effect render objects     | 64                   |
| `constraints.maxParticles` | 0–512 individual particles      | 128                  |
| `components`               | 1–32 explicit component records | No default; required |

Every component requires an `id` (unique, lowercase safe identifier, at most 40 characters), `type`, `color` (`#RRGGBB`), `position` (three numbers, each −20…20), `start` (0…10 seconds), `duration` (0.05…10 seconds), and type-specific `properties`. Authoring defaults: color `#529dff`, position `[0,0,0]`, start `0`, component duration `1`.

**Defaults in the schema are authoring annotations, not silent runtime insertion.** All fields must be present. This keeps dataset targets and regeneration explicit and reproducible. An omitted required field fails validation even if the schema documents a default. Use the example for a complete plan; adjust suggested durations to fit a shorter effect.

### Supported components and properties

All lengths are **preview units**, all times are seconds, velocities units/second, accelerations units/second². Y is up. Components are positioned independently in world space; lightning and particle geometry is local to their position. Rings lie in the XZ plane. Parent-child relationships, orientation inputs, beams, trails and arbitrary keyframes are intentionally unsupported.

| Type        | Required properties: valid range (authoring default)                                                   | Animation                                                                             |
| ----------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| `core`      | `radius`: 0.05–5 (0.65)                                                                                | Sphere plus additive glow shell. Pulses then fades.                                   |
| `ring`      | `radius`: 0.1–10 (0.6); `endRadius`: 0.1–20 (5.6); `thickness`: 0.01–0.5 (0.055)                       | Torus major radius expands using cubic ease-out. Tube thickness is preserved.         |
| `lightning` | `count`: integer 1–32 (8); `length`: 0.1–20 (4.5); `segments`: integer 2–32 (12); `jitter`: 0–1 (0.24) | Seeded, equally spaced radial polylines expand and flicker/fade.                      |
| `particles` | `count`: integer 1–512 (96); `speed`: 0–20 (4.2); `size`: 0.01–0.5 (0.065); `gravity`: −20…20 (0.65)   | Simultaneous seeded burst with ballistic movement and fade; not a continuous emitter. |

One ring record means one ring. Lightning and particle records have explicit multiplicities. Particle size is a nominal point diameter; the preview clamps point size to 1–64 device pixels to accommodate hardware. Lightning uses platform-dependent native line width. Neither behavior should be assumed to match Roblox.

### Animation format

The v1 animation format is a component's `start` + `duration` and a fixed type-specific transformation preset. There is no arbitrary instruction language. Every interval must end by the effect duration. At an absolute sample time:

```text
age = time − component.start
t = clamp(age / component.duration, 0, 1)
visible = 0 <= age < component.duration
opacity = visible ? (1 − t)^1.5 : 0
core scale = (0.35 + sin(πt) × 1.4) × (1 − 0.6t)
ring radius = lerp(radius, endRadius, 1 − (1 − t)^3)
lightning scale = 0.15 + 0.85 × (1 − (1 − t)^3)
lightning opacity multiplier = 0.72 + 0.28 × sin(65t)^2
particle position = velocity × age + [0, −0.5 × gravity × age², 0]
```

Component world position is added by the renderer. Hidden particles' sampled positions are not rendered. Using absolute time makes seeking and replay deterministic; no integration drift or physics engine is involved. Seeded randomness is derived from the plan seed and component id, so adding unrelated components does not perturb existing geometry. Browser floating-point/rasterization can still differ across hardware.

Looping is a playback option outside the plan: 0.35 seconds of empty hold before restart. It does not extend the authored animation. Default preview begins at 0.38 seconds (or one third of a short plan); Replay starts at zero. Reduced-motion users see a paused real frame.

## Real validation and resource checks

- Unique ids and no component end-time overflow (1e−9 tolerance for floating-point sums).
- Rings cannot contract; thickness must be less than initial radius.
- Declared budgets must fit schema hard caps; actual requested counts must fit declared budgets.
- Hard vertex cap: 8,192. Cost is based on the fixed preview geometry:
  - Core: two objects, 542 vertices (24×16 sphere plus 12×8 shell).
  - Ring: one object, 585 vertices (8×64 torus).
  - Lightning: `count` objects, `count × (segments + 1)` vertices.
  - Particles: one Points object, `count` vertices and individual particles.
- Ground grid is preview decoration, not part of the effect budget. The example has 13 effect objects; while all are active with the grid enabled, the renderer issues 14 draw calls.
- Uploaded files are capped at 64 KiB by the UI. Pure module callers should apply their own transport/input size limits; schema caps geometry allocation.

These are predictable construction budgets, not Roblox instance counts, memory limits, or measured frame-time guarantees. No performance benchmark promotion is implemented.

The Verifier checks name/version/duration, presence and uniqueness, built properties against the specification, actual geometry counts, finite vectors, arc segments, budget/stat consistency, and animation at start, midpoint, zero and effect end. **Sampling a few times is not an exhaustive animation proof** and the Verifier currently does not inspect rasterized aesthetics or validate Roblox APIs. Coverage is the proportion of requested components whose built properties and sampled behavior passed; it is not a subjective rating.

## Extension boundaries

1. For a new component: extend the versioned schema, Reasoner cost/range rules, Builder descriptor and sampler, preview adapter, Verifier as needed, and regression tests together. Breaking semantics require a new schema version rather than silently changing old plans.
2. A future Designer implements `design(prompt)` and outputs a plan; it never outputs code. The same validation pipeline remains mandatory. Keep module id/model version metadata outside the strict plan or version the schema to add it.
3. A future training subsystem can use the explicit prompt→plan target representation. Dataset splits, tokenization/features, architecture, seeds, checkpoints, metrics, correction records, benchmarks and promotion logic still need deliberate implementation. No current module claims to learn.
4. A future Roblox adapter consumes validated plans/descriptors separately from Three.js. Choose supported Studio objects/properties, generate constrained Luau or plugin data, and test in Studio before claiming compatibility. Neither save-plan nor the preview is an exporter.
5. Do not replace local deterministic reasoning with a conversational model where ordinary math suffices.
