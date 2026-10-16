"""Small randomly initialized multi-head MLP with explicit backpropagation and Adam.

This is the actual trainable Designer for the first experiment. It predicts a
category, four component-presence probabilities, and 45 normalized schema
fields from hashed text features. The plan decoder only maps those predictions
to plan-v1 JSON; it does not inspect prompt keywords or substitute examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import (
    CATEGORIES,
    COMPONENT_TYPES,
    DEFAULT_HIDDEN_SIZE,
    INPUT_SIZE,
    LOSS_WEIGHTS,
    MAX_HIDDEN_SIZE,
    MIN_HIDDEN_SIZE,
)
from .contracts import FIELDS

PARAMETER_NAMES = (
    "W1",
    "b1",
    "W_category",
    "b_category",
    "W_components",
    "b_components",
    "W_numeric",
    "b_numeric",
)


@dataclass
class ForwardOutput:
    hidden: np.ndarray
    category_logits: np.ndarray
    category_probabilities: np.ndarray
    component_logits: np.ndarray
    component_probabilities: np.ndarray
    numeric_values: np.ndarray


class StructuredMLP:
    """A 512 -> hidden tanh MLP with category, mask, and numeric output heads."""

    def __init__(
        self,
        seed: int,
        hidden_size: int = DEFAULT_HIDDEN_SIZE,
        input_size: int = INPUT_SIZE,
    ) -> None:
        if not MIN_HIDDEN_SIZE <= int(hidden_size) <= MAX_HIDDEN_SIZE:
            raise ValueError(f"hidden_size must be {MIN_HIDDEN_SIZE}..{MAX_HIDDEN_SIZE}.")
        if int(input_size) != INPUT_SIZE:
            raise ValueError(f"input_size must be {INPUT_SIZE} for {self.__class__.__name__}.")
        self.seed = int(seed)
        self.input_size = int(input_size)
        self.hidden_size = int(hidden_size)
        self.rng = np.random.default_rng(self.seed)
        self.params: dict[str, np.ndarray] = {
            "W1": self.rng.normal(0.0, np.sqrt(1.0 / input_size), (input_size, hidden_size)).astype(np.float32),
            "b1": np.zeros(hidden_size, dtype=np.float32),
            "W_category": self.rng.normal(0.0, 0.01, (hidden_size, len(CATEGORIES))).astype(np.float32),
            "b_category": np.zeros(len(CATEGORIES), dtype=np.float32),
            "W_components": self.rng.normal(0.0, 0.01, (hidden_size, len(COMPONENT_TYPES))).astype(np.float32),
            "b_components": np.zeros(len(COMPONENT_TYPES), dtype=np.float32),
            "W_numeric": self.rng.normal(0.0, 0.01, (hidden_size, len(FIELDS))).astype(np.float32),
            "b_numeric": np.zeros(len(FIELDS), dtype=np.float32),
        }

    @property
    def parameter_count(self) -> int:
        return int(sum(parameter.size for parameter in self.params.values()))

    @property
    def architecture(self) -> dict[str, Any]:
        return {
            "version": "structured-mlp-v1",
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "categories": list(CATEGORIES),
            "components": list(COMPONENT_TYPES),
            "numeric_fields": len(FIELDS),
            "parameter_count": self.parameter_count,
            "text_features": "signed hashed word, word-pair, and character 2–5-grams; L2 normalized",
        }

    def forward(self, features: np.ndarray) -> ForwardOutput:
        x = np.asarray(features, dtype=np.float32)
        if x.ndim == 1:
            x = x[None, :]
        if x.ndim != 2 or x.shape[1] != self.input_size:
            raise ValueError(f"Expected feature matrix [batch, {self.input_size}].")
        if not np.isfinite(x).all():
            raise ValueError("Input features must be finite.")
        hidden = np.tanh(x @ self.params["W1"] + self.params["b1"]).astype(np.float32)
        category_logits = hidden @ self.params["W_category"] + self.params["b_category"]
        category_probabilities = _softmax(category_logits)
        component_logits = hidden @ self.params["W_components"] + self.params["b_components"]
        component_probabilities = _sigmoid(component_logits)
        numeric_values = hidden @ self.params["W_numeric"] + self.params["b_numeric"]
        return ForwardOutput(
            hidden=hidden,
            category_logits=category_logits.astype(np.float32),
            category_probabilities=category_probabilities,
            component_logits=component_logits.astype(np.float32),
            component_probabilities=component_probabilities,
            numeric_values=numeric_values.astype(np.float32),
        )

    def predict(self, features: np.ndarray) -> ForwardOutput:
        return self.forward(features)

    def loss(
        self,
        features: np.ndarray,
        categories: np.ndarray,
        component_targets: np.ndarray,
        numeric_targets: np.ndarray,
        numeric_mask: np.ndarray,
    ) -> dict[str, float]:
        output = self.forward(features)
        cat = _category_loss(output.category_logits, categories)
        components = _binary_loss(output.component_logits, component_targets)
        numeric = _masked_mse(output.numeric_values, numeric_targets, numeric_mask)
        return {
            "category": cat,
            "components": components,
            "numeric": numeric,
            "total": _weighted_total(cat, components, numeric),
        }

    def train_batch(
        self,
        features: np.ndarray,
        categories: np.ndarray,
        component_targets: np.ndarray,
        numeric_targets: np.ndarray,
        numeric_mask: np.ndarray,
        optimizer: "Adam",
    ) -> dict[str, float]:
        x = np.asarray(features, dtype=np.float32)
        if x.ndim == 1:
            x = x[None, :]
        categories = np.asarray(categories, dtype=np.int64).reshape(-1)
        component_targets = np.asarray(component_targets, dtype=np.float32)
        numeric_targets = np.asarray(numeric_targets, dtype=np.float32)
        numeric_mask = np.asarray(numeric_mask, dtype=np.float32)
        output = self.forward(x)
        batch_size = max(1, x.shape[0])

        cat_loss = _category_loss(output.category_logits, categories)
        component_loss = _binary_loss(output.component_logits, component_targets)
        numeric_loss = _masked_mse(output.numeric_values, numeric_targets, numeric_mask)

        category_gradient = output.category_probabilities.copy()
        category_gradient[np.arange(batch_size), categories] -= 1.0
        category_gradient /= np.float32(batch_size)
        category_gradient *= np.float32(LOSS_WEIGHTS["category"])

        component_gradient = (output.component_probabilities - component_targets) / np.float32(
            batch_size * max(1, component_targets.shape[1])
        )
        component_gradient *= np.float32(LOSS_WEIGHTS["components"])

        numeric_denominator = max(1.0, float(numeric_mask.sum()))
        numeric_gradient = (2.0 * (output.numeric_values - numeric_targets) * numeric_mask) / np.float32(numeric_denominator)
        numeric_gradient *= np.float32(LOSS_WEIGHTS["numeric"])

        hidden_gradient = (
            category_gradient @ self.params["W_category"].T
            + component_gradient @ self.params["W_components"].T
            + numeric_gradient @ self.params["W_numeric"].T
        )
        preactivation_gradient = hidden_gradient * (1.0 - output.hidden * output.hidden)
        gradients = {
            "W_category": output.hidden.T @ category_gradient,
            "b_category": category_gradient.sum(axis=0),
            "W_components": output.hidden.T @ component_gradient,
            "b_components": component_gradient.sum(axis=0),
            "W_numeric": output.hidden.T @ numeric_gradient,
            "b_numeric": numeric_gradient.sum(axis=0),
            "W1": x.T @ preactivation_gradient,
            "b1": preactivation_gradient.sum(axis=0),
        }
        optimizer.update(self.params, gradients)
        return {
            "category": cat_loss,
            "components": component_loss,
            "numeric": numeric_loss,
            "total": _weighted_total(cat_loss, component_loss, numeric_loss),
        }

    def load_parameters(self, parameters: dict[str, np.ndarray]) -> None:
        if set(parameters) != set(PARAMETER_NAMES):
            raise ValueError("Checkpoint has missing or unexpected parameter arrays.")
        for name in PARAMETER_NAMES:
            incoming = np.asarray(parameters[name])
            current = self.params[name]
            if incoming.shape != current.shape or incoming.dtype.kind not in "fiu":
                raise ValueError(f"Checkpoint parameter {name} has an incompatible shape or type.")
            if not np.isfinite(incoming).all():
                raise ValueError(f"Checkpoint parameter {name} contains non-finite values.")
            if incoming.size and float(np.max(np.abs(incoming))) > 1000.0:
                raise ValueError(f"Checkpoint parameter {name} exceeds the numeric safety bound.")
            self.params[name] = incoming.astype(np.float32, copy=True)


def _softmax(logits: np.ndarray) -> np.ndarray:
    safe = np.clip(np.asarray(logits, dtype=np.float32), -60.0, 60.0)
    shifted = safe - safe.max(axis=1, keepdims=True)
    exponents = np.exp(shifted)
    return (exponents / np.maximum(exponents.sum(axis=1, keepdims=True), 1e-12)).astype(np.float32)


def _sigmoid(logits: np.ndarray) -> np.ndarray:
    safe = np.clip(np.asarray(logits, dtype=np.float32), -30.0, 30.0)
    return (1.0 / (1.0 + np.exp(-safe))).astype(np.float32)


def _category_loss(logits: np.ndarray, targets: np.ndarray) -> float:
    probabilities = _softmax(logits)
    indices = np.asarray(targets, dtype=np.int64).reshape(-1)
    selected = np.maximum(probabilities[np.arange(len(indices)), indices], 1e-12)
    return float(-np.log(selected).mean())


def _binary_loss(logits: np.ndarray, targets: np.ndarray) -> float:
    y = np.asarray(targets, dtype=np.float32)
    z = np.clip(np.asarray(logits, dtype=np.float32), -30.0, 30.0)
    stable = np.maximum(z, 0.0) - z * y + np.log1p(np.exp(-np.abs(z)))
    return float(stable.mean())


def _masked_mse(prediction: np.ndarray, target: np.ndarray, mask: np.ndarray) -> float:
    m = np.asarray(mask, dtype=np.float32)
    denominator = max(1.0, float(m.sum()))
    return float((((prediction - target) ** 2) * m).sum() / denominator)


def _weighted_total(category: float, components: float, numeric: float) -> float:
    return float(
        LOSS_WEIGHTS["category"] * category
        + LOSS_WEIGHTS["components"] * components
        + LOSS_WEIGHTS["numeric"] * numeric
    )


class Adam:
    """Small deterministic Adam optimizer with global gradient clipping."""

    def __init__(self, learning_rate: float = 0.003) -> None:
        if not 1e-5 <= float(learning_rate) <= 0.1:
            raise ValueError("learning_rate must be between 0.00001 and 0.1.")
        self.learning_rate = float(learning_rate)
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.epsilon = 1e-8
        self.steps = 0
        self.m = {name: np.zeros((), dtype=np.float32) for name in PARAMETER_NAMES}
        self.v = {name: np.zeros((), dtype=np.float32) for name in PARAMETER_NAMES}

    def initialize_shapes(self, params: dict[str, np.ndarray]) -> None:
        self.m = {name: np.zeros_like(params[name]) for name in PARAMETER_NAMES}
        self.v = {name: np.zeros_like(params[name]) for name in PARAMETER_NAMES}

    def update(self, params: dict[str, np.ndarray], gradients: dict[str, np.ndarray]) -> None:
        if self.m["W1"].shape != params["W1"].shape:
            self.initialize_shapes(params)
        self.steps += 1
        norm_sq = sum(float(np.square(gradient).sum()) for gradient in gradients.values())
        norm = float(np.sqrt(norm_sq))
        scale = min(1.0, 5.0 / max(norm, 1e-12))
        correction1 = 1.0 - self.beta1**self.steps
        correction2 = 1.0 - self.beta2**self.steps
        for name in PARAMETER_NAMES:
            gradient = np.asarray(gradients[name], dtype=np.float32) * np.float32(scale)
            self.m[name] = self.beta1 * self.m[name] + (1.0 - self.beta1) * gradient
            self.v[name] = self.beta2 * self.v[name] + (1.0 - self.beta2) * (gradient * gradient)
            m_hat = self.m[name] / np.float32(correction1)
            v_hat = self.v[name] / np.float32(correction2)
            params[name] -= np.float32(self.learning_rate) * m_hat / (np.sqrt(v_hat) + self.epsilon)

    def state_dict(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            "learning_rate": self.learning_rate,
            "beta1": self.beta1,
            "beta2": self.beta2,
            "epsilon": self.epsilon,
            "steps": self.steps,
            "m": {name: value.copy() for name, value in self.m.items()},
            "v": {name: value.copy() for name, value in self.v.items()},
        }
        return state

    def load_state_dict(self, state: dict[str, Any], params: dict[str, np.ndarray]) -> None:
        self.learning_rate = float(state["learning_rate"])
        self.beta1 = float(state["beta1"])
        self.beta2 = float(state["beta2"])
        self.epsilon = float(state["epsilon"])
        self.steps = int(state["steps"])
        self.initialize_shapes(params)
        for name in PARAMETER_NAMES:
            for collection in ("m", "v"):
                incoming = np.asarray(state[collection][name])
                if incoming.shape != params[name].shape or not np.isfinite(incoming).all():
                    raise ValueError(f"Invalid Adam {collection} state for {name}.")
                getattr(self, collection)[name] = incoming.astype(np.float32, copy=True)
