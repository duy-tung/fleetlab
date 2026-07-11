"""Known-answer tests: KV-memory-per-token model.

`kv_bytes_per_token = 2 * layers * kv_heads * head_dim * dtype_bytes`
"""

import pytest

from fleetlab.models.kv_memory import (
    dtype_bytes_for,
    kv_cache_bytes,
    kv_cache_bytes_per_token,
)


def test_llama31_8b_matches_the_published_contract_fixture():
    """serving-contracts' model-llama31-8b.json documents its
    kv_cache_bytes_per_token (131072) as computed from: '2 x 32 layers x 8 KV
    heads x 128 head_dim x 2 bytes (fp16 KV dtype)'. This is a real,
    independently-authored known-answer case; fleetlab's formula must
    reproduce it exactly."""
    result = kv_cache_bytes_per_token(layers=32, kv_heads=8, head_dim=128, dtype_bytes=2)
    assert result == 131072


def test_qwen2_5_1_5b_matches_the_fleetlab_authored_profile():
    """profiles/examples/model-qwen2.5-1.5b-instruct-gguf-q4km.json documents
    28,672 bytes/token from measured GGUF architecture (layers=28,
    kv_heads=2, head_dim=128) at an assumed fp16 KV dtype."""
    result = kv_cache_bytes_per_token(layers=28, kv_heads=2, head_dim=128, dtype_bytes=2)
    assert result == 28672


def test_gqa_kv_heads_below_attention_heads_shrinks_the_cache():
    """GQA case: kv_heads < attention heads. Both real models above are GQA
    (Llama-3.1-8B: 8 kv heads vs 32 attention heads; Qwen2.5-1.5B: 2 kv heads
    vs 12 attention heads) — the formula uses kv_heads, not attention heads,
    which is exactly what makes GQA shrink the cache relative to MHA."""
    mha_equivalent = kv_cache_bytes_per_token(layers=32, kv_heads=32, head_dim=128, dtype_bytes=2)
    gqa = kv_cache_bytes_per_token(layers=32, kv_heads=8, head_dim=128, dtype_bytes=2)
    assert gqa == mha_equivalent / 4  # 8/32 = 1/4 as many KV heads
    assert gqa == 131072  # this is exactly the Llama-3.1-8B case above


@pytest.mark.parametrize(
    "dtype,expected_bytes",
    [
        ("fp16", 2),
        ("bf16", 2),
        ("f16", 2),
        ("fp32", 4),
        ("f32", 4),
        ("fp8", 1),
        ("int8", 1),
    ],
)
def test_dtype_bytes_known_values(dtype, expected_bytes):
    assert dtype_bytes_for(dtype) == expected_bytes


def test_dtype_variation_halves_or_quarters_the_footprint():
    fp16 = kv_cache_bytes_per_token(layers=28, kv_heads=2, head_dim=128, dtype_bytes=dtype_bytes_for("fp16"))
    fp8 = kv_cache_bytes_per_token(layers=28, kv_heads=2, head_dim=128, dtype_bytes=dtype_bytes_for("fp8"))
    fp32 = kv_cache_bytes_per_token(layers=28, kv_heads=2, head_dim=128, dtype_bytes=dtype_bytes_for("fp32"))
    assert fp8 == fp16 // 2
    assert fp32 == fp16 * 2


def test_dtype_bytes_for_rejects_unknown_dtype():
    with pytest.raises(ValueError):
        dtype_bytes_for("not-a-real-dtype")


def test_kv_cache_bytes_scales_linearly_with_tokens():
    per_token = kv_cache_bytes_per_token(layers=28, kv_heads=2, head_dim=128, dtype_bytes=2)
    total = kv_cache_bytes(layers=28, kv_heads=2, head_dim=128, dtype_bytes=2, tokens=4096)
    assert total == per_token * 4096


@pytest.mark.parametrize("bad_kwargs", [
    dict(layers=0, kv_heads=2, head_dim=128, dtype_bytes=2),
    dict(layers=28, kv_heads=0, head_dim=128, dtype_bytes=2),
    dict(layers=28, kv_heads=2, head_dim=0, dtype_bytes=2),
    dict(layers=28, kv_heads=2, head_dim=128, dtype_bytes=0),
    dict(layers=-1, kv_heads=2, head_dim=128, dtype_bytes=2),
])
def test_rejects_nonpositive_architecture_parameters(bad_kwargs):
    with pytest.raises(ValueError):
        kv_cache_bytes_per_token(**bad_kwargs)


def test_kv_cache_bytes_rejects_negative_tokens():
    with pytest.raises(ValueError):
        kv_cache_bytes(layers=28, kv_heads=2, head_dim=128, dtype_bytes=2, tokens=-1)
