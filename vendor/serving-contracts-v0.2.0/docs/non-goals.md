# Non-goals — serving-contracts

The program plan states these verbatim; each carries its reason. Every item below is checked at
every review gate.

> No gateway logic. No load generator. No Kubernetes manifests. No capacity/planner models. No
> database. No provider SDKs. No generated service frameworks (schema-validation tooling only).
> No runtime business logic of any kind. No speculative contract surface for single-consumer
> interfaces (infergate's admin API stays repo-private to infergate). No shared application
> library for consumers.

| Non-goal | Reason |
|---|---|
| **No gateway logic** | `infergate` is the program's only gateway (single-owner rule). This repo defines the semantics the gateway must satisfy; implementing any of them here would duplicate ownership and turn specs into code with behavior to maintain. |
| **No load generator** | `inferbench` is the program's only load-generation system. This repo owns the workload *schema*; generating load from it is inferbench's job. |
| **No Kubernetes manifests** | `inferops` is the program's only deployment stack. This repo ships the deployment *contract* (descriptor schema); rendering manifests from it belongs to inferops. |
| **No capacity/planner models** | `fleetlab` owns simulation and capacity modeling. This repo defines the capacity-recommendation *shape* (Contract 7) and the fleet input schemas, never the models that produce them. |
| **No database** | The repo is stateless by design. All state is versioned files in git; the release tag is the unit of truth. A database would create runtime state with no owner. |
| **No provider SDKs** | The repo must remain dependency-free so consumers can trust it as a neutral root of the dependency graph. Validation tooling may use standard schema validators only. |
| **No generated service frameworks** | Consumers must never link against this repo or receive generated code from it; they validate against fixtures. Code generation would create an implicit shared library and couple consumer builds to this repo's source. |
| **No runtime business logic of any kind** | The permitted code surface is exactly one minimal validation kit. Anything more makes the contract repo a runtime dependency and violates the ownership matrix. |
| **No speculative contract surface for single-consumer interfaces** | A schema with only one real consumer is not a shared contract — it is premature surface that must then be versioned and maintained. infergate's admin API (`/admin/v1/...`) stays repo-private to infergate (program assumption A4); it is promoted here only if a second consumer appears. The same test applies to any new schema proposal. |
| **No shared application library for consumers** | Program hard rule 1: repositories integrate only via versioned contracts, released artifacts, files, or documented network protocols. A shared library is the canonical violation and is forbidden even when convenient. |
