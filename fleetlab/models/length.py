"""Length (and cancellation-point) distribution model.

Implements the workload schema's `$defs/distribution` shape (constant,
uniform, normal, lognormal, empirical, mixture) exactly: same sampling
semantics as `workload.schema.json` documents, so a fleetlab-simulated
length distribution and an inferbench-generated one describe the same
workload by construction (docs/architecture.md, component 2).

Rounding is the caller's responsibility (via `LengthDistribution.sample`),
matching the schema note: token-valued distributions are "rounded to the
nearest integer >= 1" for input/output length, ">= 0" for a cancellation
point in tokens; a cancellation point in elapsed seconds is not rounded at
all. `sample_distribution` itself returns raw floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def sample_distribution(dist: dict, rng: np.random.Generator, size: int) -> np.ndarray:
    """Draw `size` raw (unrounded) samples from a workload-schema distribution.

    `dist` is exactly one of the schema's `$defs/distribution` shapes, already
    schema-validated by `fleetlab.ingest` (never called on unvalidated input).
    """
    kind = dist["type"]

    if kind == "constant":
        return np.full(size, float(dist["value"]))

    if kind == "uniform":
        return rng.uniform(dist["min"], dist["max"], size=size)

    if kind == "normal":
        samples = rng.normal(dist["mean"], dist["stddev"], size=size)
        return _clamp(samples, dist.get("min"), dist.get("max"))

    if kind == "lognormal":
        # numpy's lognormal parameterizes directly by the underlying normal's
        # (mean, sigma) in log-space, matching the schema's mu/sigma exactly.
        samples = rng.lognormal(mean=dist["mu"], sigma=dist["sigma"], size=size)
        return _clamp(samples, dist.get("min"), dist.get("max"))

    if kind == "empirical":
        pool = np.asarray(dist["samples"], dtype=float)
        idx = rng.integers(0, len(pool), size=size)
        return pool[idx]

    if kind == "mixture":
        components = dist["components"]
        weights = np.asarray([c["weight"] for c in components], dtype=float)
        weights = weights / weights.sum()
        labels = rng.choice(len(components), size=size, p=weights)
        out = np.empty(size, dtype=float)
        for i, component in enumerate(components):
            mask = labels == i
            count = int(mask.sum())
            if count:
                out[mask] = sample_distribution(component["distribution"], rng, count)
        return out

    raise ValueError(f"unknown distribution type '{kind}'")


def _clamp(samples: np.ndarray, lo: Optional[float], hi: Optional[float]) -> np.ndarray:
    if lo is not None:
        samples = np.maximum(samples, lo)
    if hi is not None:
        samples = np.minimum(samples, hi)
    return samples


def mean_of_distribution(dist: dict) -> float:
    """Closed-form mean, ignoring any post-sampling min/max clamp.

    Documented assumption: clamping truncates the tails and shifts the true
    mean slightly; for the workload suite's parameter ranges (clamps set well
    into the tails, e.g. chat-short's lognormal mu=4.8/sigma=0.6 capped at
    384 against a median of ~120) the shift is a minor-order-of-magnitude
    correction, not validated numerically here. Treat this as an
    approximation for capacity arithmetic, not a certified expectation.
    """
    kind = dist["type"]
    if kind == "constant":
        return float(dist["value"])
    if kind == "uniform":
        return (dist["min"] + dist["max"]) / 2.0
    if kind == "normal":
        return float(dist["mean"])
    if kind == "lognormal":
        mu, sigma = dist["mu"], dist["sigma"]
        return float(np.exp(mu + sigma**2 / 2.0))
    if kind == "empirical":
        return float(np.mean(dist["samples"]))
    if kind == "mixture":
        weights = np.asarray([c["weight"] for c in dist["components"]], dtype=float)
        weights = weights / weights.sum()
        means = np.asarray([mean_of_distribution(c["distribution"]) for c in dist["components"]])
        return float(np.dot(weights, means))
    raise ValueError(f"unknown distribution type '{kind}'")


@dataclass(frozen=True)
class LengthDistribution:
    """A token-length (or cancellation-point) distribution bound to a
    workload-schema `$defs/distribution` instance."""

    spec: dict
    round_floor: int = 1  # 1 for input/output length; 0 for a token-valued
    # cancellation point; ignored for an elapsed-seconds cancellation point
    # (pass round_to_int=False in that case).

    def sample(self, rng: np.random.Generator, size: int, round_to_int: bool = True) -> np.ndarray:
        raw = sample_distribution(self.spec, rng, size)
        if not round_to_int:
            return raw
        rounded = np.round(raw).astype(np.int64)
        return np.maximum(rounded, self.round_floor)

    def mean(self) -> float:
        return mean_of_distribution(self.spec)
