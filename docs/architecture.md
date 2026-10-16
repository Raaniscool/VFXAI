# Architecture and plan-v1 contract

## Active local pipeline

```text
PowerShell source command: python -m vfxai.dev
  ├── Python 3.11 process: stdlib HTTP API + NumPy model + persistent user data (127.0.0.1:8765)
  └── Vite/Three.js hot-reloading browser UI (127.0.0.1:5173, /api proxy)
        ├── Neural Designer: prompt features → random-start/trainable structured MLP
        ├── deterministic plan adapter → existing plan-v1 JSON
        ├── Reasoner: checked-in JSON Schema + hard resource/timing rules
        ├── Builder: seeded Three.js geometry descriptors (not generated code)
        └── Verifier: structural consistency checks, not artistic-quality scoring
```

The Python model is implemented in `vfxai/model.py`; the browser's `src/organs/designer.js` is a thin local API bridge. `src/pipeline.js` remains a deterministic manual-plan path for the preview and does not perform neural generation. The neural output is not silently substituted with a sample when invalid. The preview only receives a plan after the browser Reasoner, Builder, and Verifier succeed.

The Python standard-library HTTP server binds to `127.0.0.1` and exposes same-origin `/api/` routes with a restrictive CSP, no-store API headers, request-size limits, loopback Host checks, and same-origin POST checks. `python -m vfxai.dev` starts that API in API-only mode plus Vite for hot reload; Vite proxies relative `/api` requests to Python and strips a remote preview Origin before forwarding. The development launcher binds Vite to loopback by default; the Vite config also supports an explicit host for sandbox previews. `python -m vfxai.server` serves the already-built `dist/` UI and API directly when a production-style preview is desired.

Persistent user data is stored outside source/build folders (Windows `%LOCALAPPDATA%\VFXAI`, XDG data on Linux, macOS Application Support, or `VFXAI_DATA_DIR`). `.venv`, `node_modules`, `dist`, and generated model/data files are not source deliverables.

## Version 1.0 schema

`schemas/plan-v1.schema.json` is the source of truth. Required fields are `schemaVersion`, `name`, `effectType`, `duration`, `seed`, `constraints`, and `components`. Version 1.0 permits only `effectType: "radial-burst"` and these component types:

| Component | Constructed objects | Modeled plan properties | Geometry budget basis |
|---|---:|---|---:|
| `core` | 2 | radius | 542 vertices |
| `ring` | 1 | radius, endRadius, thickness | 585 vertices |
| `lightning` | count | count, length, segments, jitter | count × (segments + 1) vertices |
| `particles` | 1 | count, speed, size, gravity | count particles and vertices |

The JS and Python Reasoners enforce unique IDs, timeline bounds, ring expansion/opening, declared object/particle budgets, and hard limits of 256 render objects, 512 particles, and 8,192 vertices. The first model additionally supports at most one of each component type, so some valid manually authored v1 plans are outside the model's learned target subset. Synthetic “beam,” “trail,” orbit, aura, and charge categories are radial approximations only.

## Responsibility boundaries

- **Designer:** neural prediction of category, component presence, and 45 normalized plan values. Random weights at first setup; actual CPU backpropagation/Adam during training.
- **Adapter:** deterministic mapping of learned outputs into schema fields; not a prompt-rule or stored-example fallback.
- **Reasoner:** schema and explicit construction limits. It does not judge artistic quality.
- **Builder:** deterministic, seeded geometry generation from a validated plan. It does not execute code.
- **Verifier:** checks construction matches the plan and budgets. It is not a Roblox exporter or visual-quality judge.
- **Human review:** visual appeal, usefulness, and suitability remain subjective and are not inferred from lower loss or valid JSON.

Historical `desktop/` and Electron packaging files are inactive and not required by the above architecture.
