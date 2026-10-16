"""Deterministic, schema-checked synthetic prompt/plan dataset generation.

These examples teach a small structured predictor the existing plan-v1 subset.
They are not human art direction, not rendered screenshots, and not a claim of
artistic quality. Template-family groups are split before examples are written.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import zlib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .config import (
    CATEGORIES,
    COMPONENT_TYPES,
    DEFAULT_DATASET_COUNT,
    DEFAULT_DATASET_SEED,
    DEFAULT_CONSTRAINTS,
    GENERATOR_VERSION,
)
from .contracts import analyze_plan
from .paths import DATASETS_DIR, ensure_state_dirs


PALETTES: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("blue", (60, 145, 255)),
    ("cyan", (42, 218, 236)),
    ("purple", (150, 90, 248)),
    ("red", (241, 68, 85)),
    ("green", (66, 205, 120)),
    ("gold", (250, 190, 55)),
    ("orange", (250, 116, 44)),
    ("pink", (244, 92, 180)),
)
POWER_LEVELS = ("soft", "bright", "intense")
SCALE_LEVELS = ("compact", "balanced", "large-scale")
DURATION_LEVELS = ("brief", "steady", "lingering")

CATEGORY_PHRASES: dict[str, tuple[str, ...]] = {
    "lightning": (
        "branching lightning explosion", "branching electric burst", "forked-bolt attack", "radial lightning storm", "crackling arc detonation",
        "jagged lightning burst", "electric shock eruption", "chain-lightning flare", "thunderbolt detonation", "plasma arc eruption",
        "bright bolt explosion", "charged storm impact", "multi-branch electric blast", "lightning shock burst", "bolt-filled energy pulse",
        "electric skyburst", "charged arc release", "serrated lightning bloom", "electric burst with branching bolts", "storm of blue-white arcs",
    ),
    "energy-beam": (
        "focused energy beam burst", "plasma beam projectile", "charged beam shot", "radiant energy lance", "concentrated power bolt",
        "bright beam impact", "energy ray release", "plasma lance burst", "charged laser-like streak", "focused arc projectile",
        "glowing beam strike", "energy bolt discharge", "radiant beam collision", "plasma shot burst", "directed energy flash",
        "charged light projectile", "bright ray detonation", "power-beam release", "focused electric projectile", "energy lance impact",
    ),
    "explosion": (
        "layered explosion with sparks", "radial impact detonation", "bright burst with debris sparks", "energy blast", "firework-like impact burst",
        "powerful detonation", "radial flare explosion", "shock blast with sparks", "bursting energy impact", "bright explosive bloom",
        "impact flare with a glowing core", "outward energy burst", "detonation with a central flash", "radiant explosion with particles", "comic-book impact burst",
        "plasma explosion", "burst of scattered sparks", "high-energy collision effect", "expanding detonation", "multi-layer impact flare",
    ),
    "shockwave": (
        "expanding shockwave ring", "concentric impact wave", "outward energy ring", "wide radial wave", "expanding circular blast",
        "ring-shaped impact pulse", "radiant pressure wave", "glowing shock ring", "expanding plasma ripple", "circular energy ripple",
        "outgoing wave with sparks", "bursting shock ring", "wide energy ripple", "radial force wave", "expanding impact halo",
        "pulse wave with a bright edge", "concentric energy ripple", "glowing pressure ring", "radiating impact circle", "expanding shock pulse",
    ),
    "magical-aura": (
        "magical aura around a character", "rotating energy aura", "glowing spell sphere", "arcane energy halo", "enchanted radial aura",
        "mystic shield burst", "luminous magic field", "sorcerous energy bloom", "spell-charged halo", "arcane power sphere",
        "radiant aura with sparks", "glowing magical barrier", "enchanted energy ring", "mystical power burst", "spell effect with a bright core",
        "magic-charged energy field", "arcane shock aura", "shimmering power globe", "enchanted radial shield", "mystic energy pulse",
    ),
    "particle-burst": (
        "particle burst with sparks", "radial spark spray", "burst of glowing motes", "scatter of energy particles", "outward particle bloom",
        "spark shower impact", "bright particle detonation", "radial ember burst", "spray of luminous fragments", "glittering energy burst",
        "particle impact with a core flash", "spark-filled radial pulse", "explosion of glowing specks", "bursting particle cloud", "energy mote scatter",
        "radiant spark impact", "flash with floating particles", "particle flare with sparks", "expanding motes and embers", "radial particle attack",
    ),
    "energy-trail": (
        "energy trail with sparks", "streaking radial trail burst", "electric motion streaks", "projectile trail flare", "arcing energy streak",
        "spark trail impact", "radiant trail release", "plasma trail burst", "trailing electric arcs", "glowing motion trail",
        "energy streak collision", "charged trail with particles", "radial bolt trails", "burst of luminous streaks", "light trail detonation",
        "sparkling energy wake", "plasma arc trail", "bright streaking effect", "electric trail burst", "radiating projectile traces",
    ),
    "charge-release": (
        "charging energy release", "powering-up lightning attack", "charged core firing burst", "energy charge and release", "build-up then blast effect",
        "electric charge-up flare", "charging plasma burst", "power release with a flash", "charged ring and bolt attack", "energy build-up detonation",
        "charging aura release", "burst after a bright charge", "powerful charge discharge", "lightning charge-and-fire effect", "radial release pulse",
        "charged energy impact", "electric build-up with sparks", "plasma charge release", "flash after a power-up", "charged shockwave attack",
    ),
    "orbiting-energy": (
        "orbiting energy around a character", "rotating ring of power", "spinning arcane aura", "orbital spark burst", "energy halo with orbiting motes",
        "rotating lightning sphere", "orbiting plasma arcs", "spinning magical ring", "radial orbit effect", "rotating charged aura",
        "orbiting sparks around a core", "energy sphere with a rotating halo", "spinning shock ring", "orbital energy pulse", "rotating luminous field",
        "orbiting electric fragments", "spinning arc burst", "ringed energy globe", "rotational magic aura", "orbiting power flare",
    ),
    "layered-effect": (
        "multi-layered energy effect", "layered lightning and shockwave", "composite burst with core and sparks", "stacked radial energy attack", "multi-part plasma detonation",
        "layered electric explosion", "combined ring and bolt burst", "complex energy impact", "multi-component magic attack", "stacked shockwave with particles",
        "layered aura with branching arcs", "composite radial blast", "multi-stage energy flare", "layered core and ring effect", "combined lightning impact",
        "composite spark explosion", "multi-layer charge release", "complex radial energy pulse", "stacked impact with a bright core", "combined aura and shock ring",
    ),
}

RECIPES: dict[str, tuple[str, ...]] = {
    "lightning": ("core", "lightning", "particles"),
    "energy-beam": ("core", "lightning"),
    "explosion": ("core", "ring", "particles"),
    "shockwave": ("ring", "particles"),
    "magical-aura": ("core", "ring", "particles"),
    "particle-burst": ("core", "particles"),
    "energy-trail": ("lightning", "particles"),
    "charge-release": ("core", "ring", "lightning"),
    "orbiting-energy": ("core", "ring", "lightning"),
    "layered-effect": ("core", "ring", "lightning", "particles"),
}

FRAMES: tuple[str, ...] = (
    "Create a {color} {effect} with {power} energy, a {scale} shape, and a {duration} finish.",
    "Make a {scale} {effect} in {color}; keep its glow {power} and its timing {duration}.",
    "Design a {power} {color} {effect}, using a {scale} composition that feels {duration}.",
    "Build a {color} {effect} with a {duration} pulse, {power} brightness, and {scale} size.",
    "I need a {scale} {color} {effect}; make the impact {power} and the motion {duration}.",
    "Generate a {duration} {effect} in {color}, with {power} light and a {scale} silhouette.",
    "Show a {power} {color} {effect} in a {scale} layout with {duration} timing.",
    "Create a {duration} {color} {effect}; keep the geometry {scale} and the flash {power}.",
    "Produce a {scale}, {power} {effect} with a {color} palette and a {duration} fade.",
    "Make the {color} {effect} feel {power} and {scale}, then let it fade {duration}.",
    "Set up a {power} {effect} colored {color}, with a {scale} footprint and {duration} lifetime.",
    "Create a {color} {effect} whose burst is {scale}, whose light is {power}, and whose life is {duration}.",
    "I want a {power} {color} {effect} that reads as {scale} and fades in a {duration} way.",
    "Design the {scale} {color} {effect} with {power} intensity and {duration} motion.",
    "Render a {color} {effect}: {power} glow, {scale} composition, {duration} timing.",
    "Make an effect with {duration} timing: a {power}, {scale} {color} {effect}.",
    "Build a {color} {effect} that is {power} rather than subtle, with a {scale} shape and {duration} fade.",
    "For the preview, create a {scale} {effect} in {color}; use {power} energy and {duration} motion.",
    "Compose a {duration} {color} {effect} with a {power} flash and a {scale} spread.",
    "Create a {power} {effect} with {scale} geometry, a {color} palette, and {duration} timing.",
)


def _clean_color(value: tuple[int, int, int], multiplier: float = 1.0) -> str:
    channels = [max(0, min(255, int(round(channel * multiplier)))) for channel in value]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _component(plan: dict[str, Any], kind: str, color: str, start: float, duration: float, properties: dict[str, Any], position: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
    plan["components"].append(
        {
            "id": kind,
            "type": kind,
            "color": color,
            "position": [float(value) for value in position],
            "start": round(float(start), 4),
            "duration": round(float(duration), 4),
            "properties": properties,
        }
    )


def _make_plan(category: str, palette_index: int, power_index: int, scale_index: int, duration_index: int, seed: int) -> dict[str, Any]:
    palette_name, base_rgb = PALETTES[palette_index]
    power_scale = (0.72, 1.0, 1.28)[power_index]
    size_scale = (0.72, 1.0, 1.32)[scale_index]
    effect_duration = (0.85, 1.55, 2.45)[duration_index]
    recipe = RECIPES[category]
    plan: dict[str, Any] = {
        "schemaVersion": "1.0",
        "name": f"{palette_name.title()} {category.replace('-', ' ').title()}",
        "effectType": "radial-burst",
        "duration": effect_duration,
        "seed": int(seed) & 0xFFFFFFFF,
        "constraints": dict(DEFAULT_CONSTRAINTS),
        "components": [],
    }
    starts = {"core": 0.0, "ring": 0.035, "lightning": 0.02, "particles": 0.06}
    lengths = {"core": 0.68, "ring": 0.88, "lightning": 0.78, "particles": 0.94}
    for kind in recipe:
        color_factor = {"core": 1.25, "ring": 0.95, "lightning": 1.08, "particles": 1.18}[kind]
        color = _clean_color(base_rgb, color_factor)
        start = starts[kind] * effect_duration
        component_duration = lengths[kind] * effect_duration
        if kind == "core":
            _component(plan, kind, color, start, component_duration, {"radius": round(0.54 * size_scale * power_scale, 4)})
        elif kind == "ring":
            radius = round(0.42 * size_scale, 4)
            end_radius = round((3.1 + 0.5 * power_scale) * size_scale, 4)
            _component(
                plan,
                kind,
                color,
                start,
                component_duration,
                {"radius": radius, "endRadius": end_radius, "thickness": round(0.045 + 0.008 * power_index, 4)},
                (0.0, 0.04, 0.0),
            )
        elif kind == "lightning":
            count = (4, 8, 12)[power_index]
            _component(
                plan,
                kind,
                color,
                start,
                component_duration,
                {
                    "count": count,
                    "length": round((2.6 + 0.8 * power_index) * size_scale, 4),
                    "segments": (8, 11, 14)[power_index],
                    "jitter": round((0.12, 0.22, 0.32)[power_index], 4),
                },
            )
        elif kind == "particles":
            count = (24, 56, 96)[power_index]
            _component(
                plan,
                kind,
                color,
                start,
                component_duration,
                {
                    "count": count,
                    "speed": round((2.0 + 1.0 * power_index) * size_scale, 4),
                    "size": round((0.045 + 0.012 * power_index) * size_scale, 4),
                    "gravity": round((0.35, 0.65, 0.9)[power_index], 4),
                },
            )
    return plan


def _prompt(category: str, template_index: int, palette_name: str, power: str, size: str, duration: str) -> str:
    phrase = CATEGORY_PHRASES[category][template_index]
    return FRAMES[template_index].format(
        color=palette_name,
        effect=phrase,
        power=power,
        scale=size,
        duration=duration,
    )


def _split_templates(seed: int) -> dict[str, dict[int, str]]:
    assignments: dict[str, dict[int, str]] = {}
    for category_index, category in enumerate(CATEGORIES):
        rng = np.random.default_rng(int(seed) + 97 * category_index + 11)
        order = [int(item) for item in rng.permutation(len(FRAMES))]
        assignments[category] = {}
        for index, template_index in enumerate(order):
            split = "train" if index < 16 else "validation" if index < 18 else "test"
            assignments[category][template_index] = split
    return assignments


def generate_records(count: int = DEFAULT_DATASET_COUNT, seed: int = DEFAULT_DATASET_SEED) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if int(count) < 100 or int(count) > 5000:
        raise ValueError("Dataset count must be between 100 and 5,000.")
    seed = int(seed) & 0xFFFFFFFF
    assignments = _split_templates(seed)
    per_category = [count // len(CATEGORIES) + (1 if index < count % len(CATEGORIES) else 0) for index in range(len(CATEGORIES))]
    records: list[dict[str, Any]] = []
    group_sizes: Counter[str] = Counter()
    prompt_seen: set[str] = set()
    category_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    all_variants = list(itertools.product(range(len(PALETTES)), range(len(POWER_LEVELS)), range(len(SCALE_LEVELS)), range(len(DURATION_LEVELS))))

    for category_index, category in enumerate(CATEGORIES):
        category_count = per_category[category_index]
        train_count = int(math.floor(category_count * 0.8))
        validation_count = int(math.floor(category_count * 0.1))
        desired = {"train": train_count, "validation": validation_count, "test": category_count - train_count - validation_count}
        templates_by_split = {
            "train": [template for template, split in assignments[category].items() if split == "train"],
            "validation": [template for template, split in assignments[category].items() if split == "validation"],
            "test": [template for template, split in assignments[category].items() if split == "test"],
        }
        for split, split_count in desired.items():
            templates = templates_by_split[split]
            base, extra = divmod(split_count, len(templates))
            for group_order, template_index in enumerate(templates):
                group_count = base + (1 if group_order < extra else 0)
                group_id = f"{category}:family-{template_index:02d}"
                if group_count > len(all_variants):
                    raise ValueError("Requested count exceeds unique prompt variants per family.")
                group_seed = (seed + zlib.crc32(group_id.encode("utf-8"))) & 0xFFFFFFFF
                rng = np.random.default_rng(group_seed)
                variant_indices = [int(value) for value in rng.permutation(len(all_variants))[:group_count]]
                for variant_index in variant_indices:
                    palette_index, power_index, scale_index, duration_index = all_variants[variant_index]
                    palette_name = PALETTES[palette_index][0]
                    prompt = _prompt(
                        category,
                        template_index,
                        palette_name,
                        POWER_LEVELS[power_index],
                        SCALE_LEVELS[scale_index],
                        DURATION_LEVELS[duration_index],
                    )
                    if prompt in prompt_seen:
                        raise ValueError(f"Generator produced duplicate prompt: {prompt}")
                    prompt_seen.add(prompt)
                    sample_seed = (group_seed + variant_index * 104729) & 0xFFFFFFFF
                    plan = _make_plan(category, palette_index, power_index, scale_index, duration_index, sample_seed)
                    report = analyze_plan(plan)
                    if not report["ok"]:
                        raise ValueError(f"Synthetic generator emitted invalid plan for {prompt!r}: {report['issues']}")
                    records.append(
                        {
                            "id": f"syn-{hashlib.sha256(f'{group_id}|{variant_index}|{seed}'.encode()).hexdigest()[:16]}",
                            "prompt": prompt,
                            "category": category,
                            "plan": plan,
                            "split": split,
                            "group_id": group_id,
                            "source": GENERATOR_VERSION,
                            "seed": sample_seed,
                        }
                    )
                    category_counts[category] += 1
                    split_counts[split] += 1
                    group_sizes[group_id] += 1

    records.sort(key=lambda row: row["id"])
    group_splits: dict[str, str] = {}
    for record in records:
        previous = group_splits.setdefault(record["group_id"], record["split"])
        if previous != record["split"]:
            raise ValueError(f"Prompt family leaked across splits: {record['group_id']}")
    split_groups: dict[str, set[str]] = {split: set() for split in ("train", "validation", "test")}
    for row in records:
        split_groups[row["split"]].add(row["group_id"])
    if (split_groups["train"] & split_groups["validation"]) or (split_groups["train"] & split_groups["test"]) or (split_groups["validation"] & split_groups["test"]):
        raise ValueError("Prompt-family group leakage detected.")

    manifest = {
        "format_version": 1,
        "generator": GENERATOR_VERSION,
        "plan_schema": "1.0",
        "seed": seed,
        "requested_count": int(count),
        "actual_count": len(records),
        "split_counts": {split: split_counts.get(split, 0) for split in ("train", "validation", "test")},
        "category_counts": {category: category_counts.get(category, 0) for category in CATEGORIES},
        "prompt_family_counts": {split: len(split_groups[split]) for split in split_groups},
        "unique_prompt_count": len(prompt_seen),
        "exact_duplicate_prompts": 0,
        "validated_plan_count": len(records),
        "validation_failures": 0,
        "leakage_policy": "Group by category-specific prompt-family template before an 80/10/10 split; a family never crosses splits.",
        "composition_counts": {
            "component_types": list(COMPONENT_TYPES),
            "component_masks": dict(Counter("+".join(sorted(item["type"] for item in row["plan"]["components"])) for row in records)),
        },
        "limitations": [
            "All plans use the existing radial-burst effect type and plan-v1's core, ring, lightning, and particle primitives.",
            "Beam, trail, aura, charge, and orbit wording is a supervised category label mapped to radial primitives; the renderer does not yet simulate true linear beams, paths, rotation, or staged charge timing.",
            "These are deterministic synthetic examples, not human-rated art direction or evidence of artistic quality.",
        ],
    }
    return records, manifest


def _manifest_path(dataset_path: Path) -> Path:
    return dataset_path.with_suffix(".manifest.json")


def _unique_output_path(base: Path) -> Path:
    if not base.exists():
        return base
    index = 2
    while True:
        candidate = base.with_name(f"{base.stem}-v{index}{base.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def write_dataset(path: Path, records: Iterable[dict[str, Any]], manifest: dict[str, Any]) -> Path:
    path = Path(path)
    ensure_state_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    final_manifest = {**manifest, "dataset_file": path.name, "sha256": content_hash}
    manifest_path = _manifest_path(path)
    temp_manifest = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp_manifest.write_text(json.dumps(final_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_manifest.replace(manifest_path)
    return path


def generate_dataset(
    count: int = DEFAULT_DATASET_COUNT,
    seed: int = DEFAULT_DATASET_SEED,
    output: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    ensure_state_dirs()
    records, manifest = generate_records(count, seed)
    if output is None:
        base = DATASETS_DIR / f"synthetic-v1-seed-{int(seed) & 0xFFFFFFFF}.jsonl"
        output = _unique_output_path(base)
    path = write_dataset(output, records, manifest)
    final_manifest = json.loads(_manifest_path(path).read_text(encoding="utf-8"))
    return path, final_manifest


def load_dataset(path: Path, verify: bool = True) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Dataset exceeds the 100 MiB safety limit.")
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    prompts: set[str] = set()
    groups: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Malformed JSONL at {path.name}:{line_number}: {error}") from error
            if not isinstance(row, dict) or not isinstance(row.get("prompt"), str) or not isinstance(row.get("plan"), dict):
                raise ValueError(f"Invalid dataset row at {path.name}:{line_number}.")
            if row.get("split") not in {"train", "validation", "test"}:
                raise ValueError(f"Unknown split at {path.name}:{line_number}.")
            if row.get("id") in ids:
                raise ValueError(f"Duplicate dataset id at {path.name}:{line_number}.")
            ids.add(row["id"])
            if row["prompt"] in prompts:
                raise ValueError(f"Duplicate prompt at {path.name}:{line_number}.")
            prompts.add(row["prompt"])
            group_id = row.get("group_id", row["id"])
            previous_split = groups.setdefault(group_id, row["split"])
            if previous_split != row["split"]:
                raise ValueError(f"Prompt-family leakage for {group_id!r}.")
            if verify:
                report = analyze_plan(row["plan"])
                if not report["ok"]:
                    raise ValueError(f"Invalid plan at {path.name}:{line_number}: {report['issues'][:3]}")
            records.append(row)
    if not records:
        raise ValueError(f"Dataset contains no examples: {path}")
    if not any(row["split"] == "train" for row in records) or not any(row["split"] == "validation" for row in records) or not any(row["split"] == "test" for row in records):
        raise ValueError("Dataset requires non-empty train, validation, and test splits.")
    return records


def load_manifest(path: Path) -> dict[str, Any]:
    manifest_path = _manifest_path(Path(path))
    if not manifest_path.is_file():
        return {"dataset_file": Path(path).name, "manifest_missing": True}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def set_active_dataset(path: Path) -> None:
    path = Path(path).resolve()
    root = DATASETS_DIR.resolve()
    if root not in path.parents:
        raise ValueError("Active dataset must be stored inside .vfxai/datasets.")
    ensure_state_dirs()
    pointer = DATASETS_DIR / "active.json"
    temp = pointer.with_suffix(".tmp")
    temp.write_text(json.dumps({"path": path.name}, indent=2) + "\n", encoding="utf-8")
    temp.replace(pointer)


def get_active_dataset_path() -> Path | None:
    pointer = DATASETS_DIR / "active.json"
    if pointer.is_file():
        try:
            name = json.loads(pointer.read_text(encoding="utf-8"))["path"]
            candidate = (DATASETS_DIR / name).resolve()
            if candidate.parent == DATASETS_DIR.resolve() and candidate.is_file():
                return candidate
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return None
    default = DATASETS_DIR / f"synthetic-v1-seed-{DEFAULT_DATASET_SEED}.jsonl"
    return default if default.is_file() else None


def dataset_summary(path: Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else get_active_dataset_path()
    if path is None or not path.is_file():
        return {"available": False, "split_counts": {"train": 0, "validation": 0, "test": 0}}
    manifest = load_manifest(path)
    split_counts = Counter()
    category_counts = Counter()
    records = load_dataset(path)
    for row in records:
        split_counts[row["split"]] += 1
        category_counts[row.get("category", "unknown")] += 1
    return {
        "available": True,
        "path": str(path),
        "file": path.name,
        "count": len(records),
        "split_counts": {split: split_counts.get(split, 0) for split in ("train", "validation", "test")},
        "category_counts": dict(category_counts),
        "manifest": manifest,
    }
