"""KV-memory-per-token model.

Formula (docs/architecture.md, component 2; FL-T003 requirement, verbatim):

    kv_bytes_per_token = 2 * layers * kv_heads * head_dim * dtype_bytes

Derivation: a transformer decoder's KV cache stores one Key vector and one
Value vector per layer per token (the factor of 2), each of dimension
`kv_heads * head_dim` (in multi-query/grouped-query attention, `kv_heads` can
be fewer than the number of attention/query heads — the K/V projections are
shared across a group of query heads, which is exactly what shrinks the
cache; PagedAttention (SOSP'23) §1-4 motivates this cache being the
capacity-limiting resource). Each element costs `dtype_bytes` (2 for fp16/
bf16, 1 for fp8/int8, 4 for fp32). Total footprint for `tokens` tokens of
context is this per-token cost times `tokens`.

Cross-check status: see docs/notes/model-validation.md. Architecture
parameters for Qwen2.5-1.5B-Instruct (GGUF Q4_K_M) were measured directly
from the checkpoint (layers=28, kv_heads=2, head_dim=128); the KV cache
dtype (fp16, llama.cpp's build default) is assumed, not confirmed by a
measured memory metric — no isolated KV-cache-memory measurement exists in
the available evidence (llama.cpp's /metrics has no such series; the
backend-capability descriptor records `kv_cache_usage_ratio: null`). The
cross-check is recorded PENDING, not fabricated as passing.
"""

from __future__ import annotations

DTYPE_BYTES = {
    "fp32": 4,
    "f32": 4,
    "fp16": 2,
    "f16": 2,
    "bf16": 2,
    "fp8": 1,
    "fp8_e4m3": 1,
    "fp8_e5m2": 1,
    "int8": 1,
    "q8_0": 1,  # llama.cpp KV-cache quantized type (1 byte/element)
}


def dtype_bytes_for(dtype: str) -> int:
    key = dtype.strip().lower()
    if key not in DTYPE_BYTES:
        raise ValueError(
            f"unknown KV-cache dtype '{dtype}'; known: {sorted(DTYPE_BYTES)}"
        )
    return DTYPE_BYTES[key]


def kv_cache_bytes_per_token(layers: int, kv_heads: int, head_dim: int, dtype_bytes: int) -> int:
    """2 * layers * kv_heads * head_dim * dtype_bytes."""
    for name, value in (
        ("layers", layers),
        ("kv_heads", kv_heads),
        ("head_dim", head_dim),
        ("dtype_bytes", dtype_bytes),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be > 0, got {value}")
    return 2 * layers * kv_heads * head_dim * dtype_bytes


def kv_cache_bytes(layers: int, kv_heads: int, head_dim: int, dtype_bytes: int, tokens: int) -> int:
    """Total KV-cache footprint for `tokens` tokens of context."""
    if tokens < 0:
        raise ValueError(f"tokens must be >= 0, got {tokens}")
    return kv_cache_bytes_per_token(layers, kv_heads, head_dim, dtype_bytes) * tokens
