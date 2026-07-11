# profiles/cost/

FL-T008 (cost model + sensitivity) uses `profiles/examples/cost-g5-xlarge-
ondemand.json` (dated 2026-07-10, on-demand + spot rates for
`hardware-a10g-g5-xlarge`, already ingested and covered by FL-T002's golden
tests) rather than duplicating it here. `fleetlab/cost/build_cost_report.py`
reads it directly at `profiles/examples/cost-g5-xlarge-ondemand.json`.

This deliberately avoids shipping two copies of the same provenance-carrying
price data (see `docs/implementation-notes.md`'s Deviations entry for
2026-07-11, FL-T008). If a future task needs a *different* dated cost
profile (a new price snapshot, a different hardware/region), it belongs
under this directory as its own dated, provenance-carrying file — not as an
edit to the existing `profiles/examples/` copy.
