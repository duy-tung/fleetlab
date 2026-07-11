# serving-contracts

The contract bundle for the inference-serving program: one repository holding every
cross-repo contract, versioned and released **together** under a single SemVer tag
(ADR-0001). Consumers — `infergate`, `inferbench`, `fleetlab`, `inferops`,
`inference-lab` — depend on released tags of this bundle, never on its source.

## What's in the bundle

| Surface | Where |
|---|---|
| Contract 1 — Inference API (OpenAI-compatible subset) | `openapi/inference-api.yaml` + `examples/api/**` |
| Contract 2 — Metrics + trace vocabulary | `metrics/metrics.md`, `metrics/cardinality-policy.md` |
| Contract 3 — Benchmark data schemas | `schemas/*.schema.json` + `examples/{workloads,benchmark}/**` |
| Contract 4 — Backend capability | `schemas/backend-capability.schema.json` + `examples/capabilities/**` |
| Contract 5 — Deployment | `schemas/deployment-contract.schema.json` + `examples/deployment/**` |
| Contract 6 — Fault scenarios (12, fs-01…fs-12) | `schemas/fault-scenario.schema.json` + `examples/faults/**` |
| Contract 7 — Capacity recommendation | `schemas/capacity-recommendation.schema.json` + `examples/capacity/**` |
| Fleet schemas (provenance-mandatory) | `schemas/{hardware-profile,model-profile,slo,cost-profile}.schema.json` + `examples/fleet/**` |
| Compatibility policy (normative) | `compatibility/compatibility-policy.md` |
| Consumer compatibility kit | `kit/` |
| Release notes | `RELEASES.md` |

Contracts 5–7 and the fleet schemas arrive with v0.2.0 (additive MINOR, SC-T006/SC-T007;
prepared, tag pending review). Program docs and ADRs live under `docs/`.

## How consumers pin

Pin an annotated release tag (`vX.Y.Z`) in your CI config **and** in the inference-lab pins
file, fetch the release artifact for that tag, and validate against it. Do **not** check out
this repo's source in consumer builds; there are no per-file versions and no generated
code/shared libraries. Upgrade rules (MINOR at your own pace, MAJOR with migration note +
pin bump + green I1 re-run, and the pre-1.0 exception) are in
`compatibility/compatibility-policy.md` §§5–8.

## Validating against the bundle

The kit ships inside the bundle — see `kit/README.md` for commands and per-consumer wiring:

```sh
pip install -r kit/requirements.txt
python3 kit/contracts-validate.py selftest        # golden-fixture sweep
python3 kit/contracts-validate.py check <dir>     # validate your emitted artifacts
```

## License

Apache-2.0 (chosen at the v0.1.0 release review; see `LICENSE` and `RELEASES.md`).
