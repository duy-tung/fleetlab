.PHONY: test contracts-verify recommendations-verify check

# Program floor (docs/testing.md): deterministic seeded runs + a green
# pytest suite.
test:
	python3 -m pytest tests/ -q

# I1 obligation (docs/testing.md §3, docs/interfaces.md): validate the
# vendored, pinned contract bundle's own golden fixtures. Every positive
# fixture under vendor/serving-contracts-v0.2.0/examples/ must pass; every
# fixture under an invalid/ directory must fail.
contracts-verify:
	python3 vendor/serving-contracts-v0.2.0/kit/contracts-validate.py \
		--bundle vendor/serving-contracts-v0.2.0 selftest

# FL-T009: fleetlab's own emitted Contract-7 files must kit-validate
# against the pinned bundle, not just against fleetlab's own jsonschema
# check (fleetlab/emit/recommendation.py already enforces that at write
# time; this re-checks with the independent vendored kit CLI).
recommendations-verify:
	python3 vendor/serving-contracts-v0.2.0/kit/contracts-validate.py \
		--bundle vendor/serving-contracts-v0.2.0 check examples/recommendations/

check: test contracts-verify recommendations-verify
