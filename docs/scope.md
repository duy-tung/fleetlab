# fleetlab — Scope

Single-owner rule: every capability in the portfolio has exactly one owner. This file lists what fleetlab owns. Anything not listed here is out of scope; see `non-goals.md` for the explicit never-list.

## Owned capabilities

### 1. Ingestion & validation
- Loading versioned workload manifests, benchmark-run manifests, raw-event JSONL, benchmark-result files (Contract 3), backend-capability files (Contract 4), and hardware/model/SLO/cost profiles (SC-T007 schemas).
- Schema validation of all inputs against the pinned `serving-contracts` bundle.
- **Provenance enforcement:** refusing any profile without provenance fields and any fabricated default, with typed file-and-field-naming errors.

### 2. Analytic models
- Arrival and length models parameterized from workload manifests.
- Token-rate model fitted from raw events.
- Little's-law relationships (in-flight requests, queue depth, concurrency).
- KV-memory-per-token model (`2 × layers × kv_heads × head_dim × dtype_bytes × tokens`), cross-checked against measured engine memory.

### 3. Profile fitting
- Per-(hardware, model, engine-config) goodput and memory profiles fitted from benchmark measurements, with error bars, an overfitting guard, and a structurally enforced train/holdout split (gate G8).

### 4. Dynamics simulation
- Queue-growth analysis under bursts; cold-start/warm-up delay modeling; scale-up/down lag; failover headroom; failure-capacity analysis (N−1 replicas, degraded hardware).

### 5. Autoscaling-signal comparison (capacity *logic*, not experiments)
- Simulation-based comparison of CPU utilization, GPU utilization, queue depth, in-flight requests, token-arrival rate, and predicted-goodput deficit as scaling signals, across the named workloads, with a when-each-signal-fails analysis.
- Boundary: autoscaling **experiments** on a cluster (HPA, justified KEDA) belong to `inferops`. fleetlab supplies the predictions and threshold recommendations that those experiments test.

### 6. Heterogeneous placement
- Placement recommendations across GPU types covered by **measured profiles only**: model fit vs VRAM, throughput/cost differences, cold starts, failover headroom, fragmentation, workload affinity.

### 7. Cost model
- Cost per 1M tokens at SLO per configuration; sensitivity analysis over price/load/SLO; dated, provenance-flagged prices.

### 8. Recommendation emission & reports
- Contract 7 capacity-recommendation files (schema-validated in CI), the fleetlab side of the I6 loop.
- The five required reports: autoscaling policy comparison, cold-start headroom, heterogeneous placement, cost/capacity model, **simulation limitations**.

## Owned state

- Hardware/model/cost/SLO profile files: versioned YAML/JSON with mandatory provenance fields, conforming to the contract schemas. Consumers: fleetlab, inference-lab.
- Emitted recommendations and reports (including seeds, input digests, and bundle versions embedded in each).
- fleetlab never mutates its inputs; ingestion is read-only.

## Boundary mechanics (how scope is kept)

- Integration is files-only: inferbench data arrives as files; recommendations leave as files. No shared application library in either direction; no repo imports fleetlab as a library.
- Metric/statistic definitions shared with inferbench live in the `serving-contracts` metric vocabulary — the urge to import an inferbench module signals a contract gap, and the fix is a contract clarification filed against serving-contracts.
- Contract questions are filed against `serving-contracts`, never patched locally.
- Boundary tests applied at every review gate: (1) demonstrable alone with value; (2) no change here forces a same-day source change elsewhere; (3) no code copied between repositories.
