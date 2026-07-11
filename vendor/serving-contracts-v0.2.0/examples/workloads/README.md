# Workload example fixtures — NON-NORMATIVE

These eight files are **non-normative example fixtures** for
`schemas/workload.schema.json` (Contract 3). They exist so consumer CIs can
validate that the schema expresses all eight named workload archetypes:

| File | Archetype |
|---|---|
| `chat-short.json` | short interactive chat turns |
| `rag-long-in.json` | retrieval-augmented: long inputs, short outputs |
| `gen-long-out.json` | generation-heavy: short inputs, long outputs |
| `shared-prefix.json` | high prefix-sharing ratio (system-prompt reuse) |
| `mixed.json` | mixture of chat-like and RAG-like traffic |
| `bursty.json` | time-varying open-loop rate (burst phases) |
| `cancel-storm.json` | high client-cancellation rate |
| `slow-client.json` | throttled-read clients |

**The canonical, versioned workload suite is authored and owned by
`inferbench` (IB-T003), not by this repository.** fleetlab and reports consume
inferbench's suite; these fixtures only demonstrate schema expressiveness and
back compatibility tests. Parameter values here (rates, lengths, durations)
are illustrative, carry no measurement claims, and must not be cited as the
program's benchmark configuration.

Negative fixtures live in `invalid/` and MUST fail validation; each has an
adjacent `<name>.reason.txt` naming the violated rule (ADR-0004).
