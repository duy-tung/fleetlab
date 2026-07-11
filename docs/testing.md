# fleetlab — Testing

fleetlab is Python; the program's evidence floor for it is **deterministic seeded simulation runs and a green pytest suite** (the analogue of `go test -race` clean for the Go repos). A test that cannot fail is not evidence — every generated or templated suite is reviewed for real failure modes before it counts.

## 1. Golden-file tests (ingestion, FL-T002)

Fixture classes under `tests/golden/`, exercised for every input type (workload manifest, benchmark-run manifest, raw events, benchmark result, backend capability, hardware/model/SLO/cost profiles):

- **valid** — a conforming file ingests cleanly and round-trips into the internal representation.
- **invalid** — schema violations fail with a typed error naming the file, the field, and the rule violated. No silent coercion, no defaulting.
- **provenance-missing** — a profile without provenance fields is refused, even if otherwise schema-valid. This encodes the provenance-mandatory rule as a test, not a convention.
- **unsupported-field** — unknown fields are rejected (not ignored), mirroring the program-wide unsupported-field rejection posture.

Synthetic fixtures are acceptable for golden tests and are clearly labeled synthetic; they are never used to fit profiles.

## 2. Known-answer-limit tests (analytic models, FL-T003/FL-T005)

Every closed-form model gets a documented derivation plus tests against hand-computable cases:

- **Little's law identities:** L = λW under stationary load; consistency across in-flight requests, queue depth, and concurrency views of the same trace.
- **KV-memory formula:** `2 × layers × kv_heads × head_dim × dtype_bytes × tokens` against hand-computed cases (e.g. a known model config at a known token count), including GQA cases where `kv_heads < attention heads` and dtype variations (fp16/bf16 = 2 bytes, fp8/int8 = 1).
- **Queue stability boundaries (dynamics):** λ < μ ⇒ bounded queue in steady state; λ > μ ⇒ queue length grows linearly at rate (λ − μ); burst decay back to steady state after the burst ends.
- **Arrival/length models:** distribution parameters recovered from generated samples within tolerance; Poisson arrival inter-arrival-time properties.

## 3. Contract-fixture validation in CI (I1 obligation)

On every CI run, against the **pinned bundle tag** (recorded in `interfaces.md`):

- Validate accepted inputs against the bundle's golden `examples/` fixtures.
- Validate every emitted recommendation against `capacity-recommendation.schema.json`.
- Targets: `make contracts-verify` (the bundle's own golden-fixture selftest) and `make recommendations-verify` (kit-validates every file under `examples/recommendations/` against the pinned bundle — FL-T009), both wired into `make check`, green in CI. Re-run on every contract release; the v1.0.0 re-run is a prerequisite for I6.

## 4. Holdout protocol (G8 — structural, not honor-system)

The fitting API in `fleetlab/fitting/` enforces the train/holdout split in its type/shape, not in documentation:

1. Fitting takes an **explicit, caller-supplied split**: a set of training run IDs and a disjoint set of holdout run IDs (disjointness verified, non-empty holdout required for any fit-quality report).
2. Fit-quality metrics are **only computable against the holdout set**. There is no code path that reports fit quality on training data — and a test proves that attempting it raises, i.e. the test asserts the *impossibility*, not just the happy path.
3. The split (run IDs on each side) is recorded in the fitted profile's provenance and in `reports/holdout-validation.md`.
4. **G8 acceptance:** prediction of the holdout run within the stated error bars, **or** the miss documented as a limitation with error analysis. Either outcome is publishable; only silence is a failure.
5. Overfitting guard: model complexity justified against training-set size (reviewed at the G8 human-review gate); error bars on every fitted parameter.

## 5. Determinism tests

- Same seed + same input files ⇒ **byte-identical result tables** for simulation and fitting runs. The test hashes serialized outputs across two runs.
- All randomness flows from an explicitly passed seeded RNG; a lint/test guards against module-level RNG use and wall-clock seeding.
- Output artifacts embed seed + input digests + bundle version; a test asserts the run record is present and complete in every emitted artifact.

## 6. Invariant tests (placement, FL-T007)

- Never place a model whose weights + KV budget exceed the hardware profile's VRAM.
- Never recommend hardware that has no measured profile — the refusal is asserted, not the absence of a recommendation.

## 7. What is deliberately NOT tested here

- No integration tests against live infergate/inferops/engines — fleetlab has no network at runtime; cross-repo integration is inference-lab's job (I1/I6).
- No performance benchmarks of fleetlab itself beyond keeping the suite fast; fleetlab's numbers are about the modeled fleet, not about fleetlab's own speed.

## Tooling

pytest as the runner; CI (GPU-free by rule) runs the full suite + `contracts-verify` on every push. The precise dependency set is fixed in ADR-0001.
