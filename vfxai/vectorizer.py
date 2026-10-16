"""Deterministic hashed text features; no vocabulary download or pretrained embeddings."""

from __future__ import annotations

import hashlib
import re

import numpy as np

from .config import INPUT_SIZE

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _bucket(feature: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.blake2b(
        feature.encode("utf-8"), digest_size=8, person=b"vfxai-feat-v1"
    ).digest()
    value = int.from_bytes(digest, "little", signed=False)
    return value % dimensions, (1.0 if (value >> 63) else -1.0)


def encode_prompt(text: str, dimensions: int = INPUT_SIZE) -> np.ndarray:
    """Hash words, word pairs, and character 2–5-grams into one normalized vector."""
    if not isinstance(text, str):
        raise TypeError("Prompt must be text.")
    if len(text) > 1000:
        raise ValueError("Prompt is limited to 1,000 characters.")
    words = [word.lower() for word in _TOKEN_RE.findall(text)]
    vector = np.zeros(dimensions, dtype=np.float32)
    if not words:
        return vector

    features: list[str] = []
    for index, word in enumerate(words):
        features.append(f"w:{word}")
        if index:
            features.append(f"b:{words[index - 1]}_{word}")
        padded = f"^{word}$"
        for n in (2, 3, 4, 5):
            for start in range(max(0, len(padded) - n + 1)):
                features.append(f"c{n}:{padded[start:start + n]}")

    for feature in features:
        index, sign = _bucket(feature, dimensions)
        vector[index] += sign
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= np.float32(norm)
    return vector


def encode_prompts(prompts: list[str]) -> np.ndarray:
    if not prompts:
        return np.empty((0, INPUT_SIZE), dtype=np.float32)
    return np.stack([encode_prompt(prompt) for prompt in prompts]).astype(np.float32)
