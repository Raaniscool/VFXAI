# Python model and local experiment design

## Pipeline boundaries

```text
Prompt
  → deterministic hashed-text vector (512 signed features)
  → randomly initialized NumPy MLP
  → learned category / component-presence / 45 numeric heads
  → deterministic structured adapter to plan 1.0
  → Python schema + timing/resource checks
  → browser Reasoner → deterministic Builder → Verifier → Three.js preview
```

`vfxai/model.py` contains the trainable model, loss, backpropagation, and Adam optimizer. `vfxai/inference.py` runs one forward pass and preserves its raw heads, candidate JSON, provenance, and validation result. `vfxai/contracts.py` validates the checked-in `schemas/plan-v1.schema.json` plus timeline, duplicate-ID, ring consistency, object, particle, and vertex budgets. The existing JS Reasoner/Builder/Verifier remain a separate boundary; only a candidate that passes those checks is sent to the preview.

The local endpoint is bound to loopback by default. The built browser UI and Python API share one origin. Requests, datasets, ratings, checkpoints, and evaluation results are stored locally; the code contains no telemetry, remote model request, or generated-code execution. Vite is an optional development preview and proxies relative `/api` calls to the loopback Python endpoint.

## Model specification

- Input: 512-dimensional L2-normalized signed feature hashing over lowercased words, adjacent word pairs, and per-word character 2–5-grams. There is no trainable/downloaded vocabulary and no pretrained embedding.
- Network: one `tanh` hidden layer (default 64 units; configurable 16–128), with separate category softmax, four sigmoid component-presence outputs, and 45 linear numeric outputs. The default model has 36,667 trainable parameters.
- Targets: category cross-entropy + four-label binary cross-entropy + masked normalized numeric MSE. Numeric loss has an explicit weight. Absent component parameters are masked rather than learned from arbitrary zeros.
- Training: seeded NumPy initialization and per-epoch deterministic shuffle, minibatch forward pass, analytical gradient propagation through all heads and `tanh`, global gradient clipping, and Adam. The checkpoint stores weights and optimizer moments for an explicit resume.
- Decoding: a deterministic adapter scales learned values back into schema ranges and rounds integer properties. It does not read prompt keywords, look up a similar prompt, pick a synthetic example, clip invalid results, or repair failures. Category and component decisions are learned argmax/threshold outputs. The adapter supplies the fixed `radial-burst` effect type, component IDs, a category/checkpoint-derived name, and hard resource defaults; these are not separate learned outputs.

The candidate may fail the Python schema/Reasoner or the browser Builder/Verifier. Such output remains visible and locally recorded; it is not replaced by a sample. It is previewed only after explicit validation. Manual edits are permitted and revalidated before preview.

## Synthetic data and split policy

The default first-run dataset contains 1,000 deterministic local prompt/plan pairs. The generator supports 100–5,000 records and a seed. It uses 10 prompt categories, color/power/scale/duration descriptors, and 20 category-specific prompt-family templates. Each template family belongs to exactly one split; the split is assigned before records are sampled. Target proportions are approximately 80% train, 10% validation, and 10% test, with per-category rounding recorded in the manifest. Duplicate prompts and cross-split family leakage are rejected.

Each generated plan is checked against the JSON schema and the Python Reasoner before it is written. JSONL rows include stable IDs, prompt, label, schema-valid plan, split, family ID, generator version, and seed. A companion manifest records hashes, counts, split/family/category distribution, schema/generator version, and limitations. New datasets get new filenames; the active pointer changes only when a newly generated dataset is selected, and older files remain.

The synthetic recipes map the ten labels to combinations of the existing four component types. `energy-beam`, `energy-trail`, `magical-aura`, `charge-release`, and `orbiting-energy` are labels for radial approximations—not implementation of beam/trail geometry, rotational motion, or staged timing. Generated examples are synthetic, not human-authored or artistically rated. Training does not automatically create better-looking art simply because loss decreases.

## Checkpoints and evaluation

- First-run setup writes a named **untrained random checkpoint** so users can test inference before training.
- Each training run saves an untrained baseline and per-epoch trained checkpoints. Training reports keep initialization seed, optimizer settings, dataset hash/version, train/validation/test counts, feedback inclusion, per-epoch losses, and best validation checkpoint.
- Validation loss selects a best checkpoint; held-out test prompts are not used for gradient updates. At run end, baseline and best trained checkpoints are evaluated on the **same test rows**. Their raw predictions, including invalid candidates, are written to local JSONL files.
- Metrics include held-out total/category/component/numeric loss, category accuracy, exact component-mask agreement, component precision/recall/F1, normalized numeric MAE, plan-v1 valid rate, and validation issue counts. Users can also compare checkpoints on one identical prompt and seed or run a fresh held-out comparison.
- The report explicitly says artistic quality is not measured. These metrics do not prove perceptual appeal, helpfulness, Roblox Studio behavior, export compatibility, or runtime performance.

## Feedback governance and data retention

Every generation is persisted locally with prompt, selected checkpoint, raw head outputs, candidate JSON, validation issues, and a provenance marker. Rating feedback is stored in a separate pending queue. A rating alone never changes weights. To use feedback, a user must provide or select a valid supported plan, explicitly approve it, and separately opt in to including approved feedback in a later training run. Invalid corrections/raw text are retained for review but cannot be approved. Approved prompts that duplicate an active dataset row are excluded to protect the held-out split.

User data is stored outside the source checkout and `dist/`: Windows `%LOCALAPPDATA%\VFXAI`, XDG user data on Linux, or macOS Application Support. `VFXAI_DATA_DIR` overrides the path. Setup/build operations do not delete this folder. Back it up before manually removing it.

## Known limitations and next experiments

This first experiment is intentionally small and CPU-focused. It does not generate arbitrary JSON token sequences; the adapter is schema-specific. A single compact hashed-feature MLP has limited language coverage and cannot model long-range compositional intent, assets, arbitrary numbers, multiple same-type components, texture/material graphs, arbitrary beam/trail paths, or Roblox code. Inference and training quality must be judged separately by people reviewing plans and rendered effects. The held-out split is by prompt template family, but all prompts still originate from the same synthetic generator; generalization to real artist prompts remains unproven.
