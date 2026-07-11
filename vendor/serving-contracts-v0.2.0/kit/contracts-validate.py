#!/usr/bin/env python3
"""serving-contracts consumer compatibility kit — validation-only CLI.

This is the SC-T008 validator kit: the mechanism behind milestone I1. It wraps a
standard JSON Schema validator (python-jsonschema, draft 2020-12 per ADR-0002) and
does exactly three things:

  1. `validate` — validate artifact files against a named schema from the bundle;
  2. `selftest` — run the bundle's own golden-fixture sweep: every positive fixture
     under examples/ MUST validate, every fixture under an invalid/ directory MUST
     fail validation (a validator that cannot fail is not evidence);
  3. `check`    — validate a directory of consumer-emitted artifacts, auto-detecting
     the schema from the artifact naming convention (`<anything>.<schema>.json` /
     `.jsonl`) or forced with --schema.

It is VALIDATION-ONLY by design (see docs/architecture.md, "Validator-kit design"):
no request handling, no code generation, no shared helpers for consumers. The
directory→schema mapping lives in kit/validation-map.json (configuration, not code
heuristics — ADR-0004). New schemas dropped into schemas/*.schema.json are picked up
automatically; only fixture rules are per-area configuration.

SSE transcripts (.sse): the kit performs lightweight validation only — SSE framing
(`id:`/`data:`/`event:`/`retry:`/comment lines) plus every embedded JSON payload
validated against the per-event schema (`api.stream-event`, oneOf chunk|error), with
`data: [DONE]` accepted as the terminal sentinel. Ordering, flush, termination and
cancellation semantics are gateway-conformance testing (infergate), out of kit scope.

Exit codes (stable contract surface for CI):
  0 — everything validated as required (selftest: positives green AND negatives failed)
  1 — validation failure (a positive/artifact failed, or a negative fixture passed)
  2 — usage/config/environment error (unknown schema, missing bundle, missing deps)

Machine-readable output: pass --json to emit a single JSON summary object on stdout
(human-readable progress then goes to stderr).

Dependencies: Python 3.9+, jsonschema>=4.18, PyYAML>=6 (PyYAML only needed when an
api.* schema — sourced from openapi/inference-api.yaml — is used).
"""

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2

SUMMARY_FORMAT = 1  # bump only per the compatibility policy (breaking for consumer CI parsers)

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import best_match
    from referencing import Registry
    from referencing.jsonschema import DRAFT202012
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "error: missing dependency ({}). Install kit dependencies with:\n"
        "  pip install -r kit/requirements.txt\n".format(exc)
    )
    sys.exit(EXIT_USAGE)


class KitError(Exception):
    """Usage/config/environment error → exit code 2."""


# ---------------------------------------------------------------------------
# glob matching: '*' and '?' do NOT cross '/', '**' does (deterministic,
# unlike fnmatch, whose '*' crosses path separators)
# ---------------------------------------------------------------------------

def glob_to_regex(pattern):
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out) + r"\Z")


# ---------------------------------------------------------------------------
# schema store
# ---------------------------------------------------------------------------

OPENAPI_URI = "urn:serving-contracts:openapi:inference-api"


class SchemaStore:
    """Named schemas = schemas/*.schema.json (auto-discovered; the schema set grows
    without kit changes) + api.* names mapped to OpenAPI component schemas via
    kit/validation-map.json."""

    def __init__(self, bundle, config):
        self.bundle = bundle
        self.config = config
        schemas_dir = bundle / "schemas"
        self.file_schemas = {}
        if schemas_dir.is_dir():
            for path in sorted(schemas_dir.glob("*.schema.json")):
                self.file_schemas[path.name[: -len(".schema.json")]] = path
        self.api_schemas = {
            k: v for k, v in config.get("api_schemas", {}).items() if not k.startswith("$")
        }
        self._docs = {}
        self._validators = {}
        self._registry = None
        self._openapi_doc = None

    def names(self):
        return sorted(self.file_schemas) + sorted(self.api_schemas)

    def schema_doc(self, name):
        if name not in self._docs:
            self._docs[name] = json.loads(self.file_schemas[name].read_text())
        return self._docs[name]

    def _openapi(self):
        if self._openapi_doc is None:
            try:
                import yaml
            except ImportError:
                raise KitError(
                    "PyYAML is required to validate against api.* schemas "
                    "(pip install -r kit/requirements.txt)"
                )
            spec_path = self.bundle / "openapi" / "inference-api.yaml"
            if not spec_path.is_file():
                raise KitError("bundle has no openapi/inference-api.yaml: {}".format(spec_path))
            self._openapi_doc = yaml.safe_load(spec_path.read_text())
        return self._openapi_doc

    def _build_registry(self, with_openapi):
        resources = []
        for name in self.file_schemas:
            doc = self.schema_doc(name)
            uri = doc.get("$id", "urn:serving-contracts:schema:{}".format(name))
            resources.append((uri, DRAFT202012.create_resource(doc)))
        if with_openapi:
            resources.append((OPENAPI_URI, DRAFT202012.create_resource(self._openapi())))
        return Registry().with_resources(resources)

    def meta_validate(self):
        """Meta-validate every file schema against the pinned draft. Returns names."""
        for name in self.file_schemas:
            Draft202012Validator.check_schema(self.schema_doc(name))
        return sorted(self.file_schemas)

    def validator(self, name):
        if name in self._validators:
            return self._validators[name]
        if name in self.file_schemas:
            doc = self.schema_doc(name)
            registry = self._build_registry(with_openapi=False)
            validator = Draft202012Validator(doc, registry=registry)
        elif name in self.api_schemas:
            entry = self.api_schemas[name]
            if "ref" in entry:
                # entry refs are document-local ("#/components/..."); anchor them to the
                # registered OpenAPI resource URI.
                schema = {"$ref": OPENAPI_URI + entry["ref"]}
            elif "one_of_refs" in entry:
                schema = {"oneOf": [{"$ref": OPENAPI_URI + r} for r in entry["one_of_refs"]]}
            else:
                raise KitError(
                    "validation-map api_schemas entry '{}' needs 'ref' or 'one_of_refs'".format(name)
                )
            registry = self._build_registry(with_openapi=True)
            validator = Draft202012Validator(schema, registry=registry)
        else:
            raise KitError(
                "unknown schema '{}'. Known schemas: {}".format(name, ", ".join(self.names()))
            )
        self._validators[name] = validator
        return validator


# ---------------------------------------------------------------------------
# record extraction (.json / .jsonl / .sse)
# ---------------------------------------------------------------------------

SSE_LINE = re.compile(r"^(id|data|event|retry):( ?)(.*)$")
SSE_DONE = "[DONE]"


class RecordError(Exception):
    """A file whose records cannot even be extracted counts as invalid."""


def iter_records(path):
    """Yield (label, instance) pairs to validate. Raises RecordError on framing/parse
    problems — treated as validation failure (not a kit error): a consumer artifact
    that is not even parseable must fail CI, and a negative fixture may be negative
    precisely because it is malformed."""
    suffix = path.suffix
    text = path.read_text()
    if suffix == ".json":
        try:
            yield "instance", json.loads(text)
        except ValueError as exc:
            raise RecordError("not valid JSON: {}".format(exc))
    elif suffix == ".jsonl":
        for lineno, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                yield "line {}".format(lineno), json.loads(line)
            except ValueError as exc:
                raise RecordError("line {}: not valid JSON: {}".format(lineno, exc))
    elif suffix == ".sse":
        yielded = False
        for lineno, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith(":"):
                continue
            match = SSE_LINE.match(line)
            if not match:
                raise RecordError("line {}: not an SSE field line".format(lineno))
            field, _, value = match.groups()
            if field != "data":
                continue
            if value.strip() == SSE_DONE:
                continue  # terminal sentinel, not a JSON payload
            try:
                yield "line {} (data event)".format(lineno), json.loads(value)
            except ValueError as exc:
                raise RecordError("line {}: data payload is not JSON: {}".format(lineno, exc))
            yielded = True
        if not yielded:
            raise RecordError("SSE transcript contains no JSON data events")
    else:
        raise RecordError("unsupported artifact extension '{}'".format(suffix))


def validate_file(path, validator):
    """Return a list of error strings; empty list == file valid."""
    errors = []
    try:
        for label, instance in iter_records(path):
            err = best_match(validator.iter_errors(instance))
            if err is not None:
                errors.append(
                    "{}: {} (at instance path: /{})".format(
                        label, err.message, "/".join(str(p) for p in err.absolute_path)
                    )
                )
    except RecordError as exc:
        errors.append(str(exc))
    return errors


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

class Reporter:
    def __init__(self, machine):
        self.machine = machine
        self.stream = sys.stderr if machine else sys.stdout

    def line(self, text=""):
        self.stream.write(text + "\n")

    def summary(self, payload):
        if self.machine:
            sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def make_summary(command, bundle, ok, exit_code, counts, failures):
    return {
        "kit": "serving-contracts-compatibility-kit",
        "summary_format": SUMMARY_FORMAT,
        "command": command,
        "bundle": str(bundle),
        "ok": ok,
        "exit_code": exit_code,
        "counts": counts,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_list_schemas(store, args, rep):
    for name in store.names():
        origin = "schemas/" if name in store.file_schemas else "openapi/"
        rep.line("{}  ({})".format(name, origin))
    rep.summary(
        make_summary(
            "list-schemas", store.bundle, True, EXIT_OK,
            {"schemas": len(store.names())},
            [],
        )
        | {"schemas": store.names()}
    )
    return EXIT_OK


def cmd_validate(store, args, rep):
    validator = store.validator(args.schema)
    failures = []
    checked = 0
    for raw in args.files:
        path = Path(raw)
        if not path.is_file():
            raise KitError("no such file: {}".format(path))
        checked += 1
        errors = validate_file(path, validator)
        if errors:
            rep.line("FAIL  {}  [{}]".format(path, args.schema))
            for e in errors:
                rep.line("      {}".format(e))
            failures.append({"file": str(path), "schema": args.schema, "errors": errors})
        else:
            rep.line("PASS  {}  [{}]".format(path, args.schema))
    ok = not failures
    code = EXIT_OK if ok else EXIT_VALIDATION
    rep.line()
    rep.line("validate: {}/{} file(s) valid against '{}'".format(
        checked - len(failures), checked, args.schema))
    rep.summary(make_summary(
        "validate", store.bundle, ok, code,
        {"files_checked": checked, "passed": checked - len(failures), "failed": len(failures)},
        failures,
    ))
    return code


def load_fixture_rules(config):
    rules = []
    for rule in config.get("fixture_rules", []):
        if not isinstance(rule, dict) or "glob" not in rule:
            continue
        rules.append((rule["glob"], glob_to_regex(rule["glob"]), rule["schema"]))
    return rules


def cmd_selftest(store, args, rep):
    examples = store.bundle / "examples"
    if not examples.is_dir():
        raise KitError("bundle has no examples/ directory: {}".format(examples))

    failures = []

    # 1. meta-validate every schema in the bundle
    meta_names = store.meta_validate()
    rep.line("schemas: {} meta-validated against JSON Schema 2020-12: {}".format(
        len(meta_names), ", ".join(meta_names)))

    # 2. sweep the golden fixtures
    ignore = [glob_to_regex(g) for g in store.config.get("ignore", [])]
    rules = load_fixture_rules(store.config)
    pos_total = pos_passed = neg_total = neg_failed = 0

    for path in sorted(p for p in examples.rglob("*") if p.is_file()):
        rel = path.relative_to(examples).as_posix()
        if any(rx.match(rel) for rx in ignore):
            continue
        schema = next((s for g, rx, s in rules if rx.match(rel)), None)
        if schema is None:
            failures.append({
                "file": rel, "schema": None, "kind": "unmatched-fixture",
                "errors": ["no fixture rule in kit/validation-map.json matches this file"],
            })
            rep.line("FAIL  {}  [no rule]".format(rel))
            continue
        negative = "invalid" in path.relative_to(examples).parts
        validator = store.validator(schema)
        errors = validate_file(path, validator)
        if negative:
            neg_total += 1
            reason = path.parent / (path.stem + ".reason.txt")
            if errors:
                neg_failed += 1
                if not reason.is_file():
                    failures.append({
                        "file": rel, "schema": schema, "kind": "missing-reason-note",
                        "errors": ["negative fixture lacks adjacent {} (ADR-0004)".format(reason.name)],
                    })
                    rep.line("FAIL  {}  [missing {}]".format(rel, reason.name))
                elif args.verbose:
                    rep.line("ok    {}  [negative fails as required: {}]".format(rel, errors[0]))
            else:
                failures.append({
                    "file": rel, "schema": schema, "kind": "negative-passed",
                    "errors": ["fixture under invalid/ validated successfully — it MUST fail"],
                })
                rep.line("FAIL  {}  [negative fixture PASSED validation]".format(rel))
        else:
            pos_total += 1
            if errors:
                failures.append({"file": rel, "schema": schema, "kind": "positive-failed",
                                 "errors": errors})
                rep.line("FAIL  {}  [{}]".format(rel, schema))
                for e in errors:
                    rep.line("      {}".format(e))
            else:
                pos_passed += 1
                if args.verbose:
                    rep.line("ok    {}  [{}]".format(rel, schema))

    ok = not failures
    code = EXIT_OK if ok else EXIT_VALIDATION
    rep.line()
    rep.line("selftest: {} schemas meta-validated".format(len(meta_names)))
    rep.line("selftest: positives {}/{} passed".format(pos_passed, pos_total))
    rep.line("selftest: negatives {}/{} failed-as-required".format(neg_failed, neg_total))
    rep.line("selftest: {}".format("GREEN" if ok else "RED ({} problem(s))".format(len(failures))))
    rep.summary(make_summary(
        "selftest", store.bundle, ok, code,
        {
            "schemas_meta_validated": len(meta_names),
            "positives_total": pos_total,
            "positives_passed": pos_passed,
            "negatives_total": neg_total,
            "negatives_failed_as_required": neg_failed,
        },
        failures,
    ))
    return code


def detect_schema(path, names):
    """Artifact naming convention: <anything>.<schema>.json|jsonl; bare .sse maps to
    api.stream-event."""
    if path.suffix == ".sse":
        return "api.stream-event" if "api.stream-event" in names else None
    stem = path.name[: -len(path.suffix)]
    candidates = [n for n in names if stem == n or stem.endswith("." + n)]
    return max(candidates, key=len) if candidates else None


def cmd_check(store, args, rep):
    root = Path(args.directory)
    if not root.is_dir():
        raise KitError("no such directory: {}".format(root))
    names = store.names()
    failures = []
    checked = 0
    skipped = []
    artifacts = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix in (".json", ".jsonl", ".sse")
    )
    if not artifacts:
        raise KitError("no artifacts (*.json, *.jsonl, *.sse) under {}".format(root))
    for path in artifacts:
        schema = args.schema or detect_schema(path, names)
        rel = path.relative_to(root).as_posix()
        if schema is None:
            if args.ignore_unmatched:
                skipped.append(rel)
                rep.line("skip  {}  [no schema detectable from name]".format(rel))
                continue
            raise KitError(
                "cannot detect schema for '{}' — name artifacts '<name>.<schema>.json|jsonl' "
                "or pass --schema / --ignore-unmatched (known schemas: {})".format(
                    rel, ", ".join(names))
            )
        checked += 1
        errors = validate_file(path, store.validator(schema))
        if errors:
            failures.append({"file": rel, "schema": schema, "errors": errors})
            rep.line("FAIL  {}  [{}]".format(rel, schema))
            for e in errors:
                rep.line("      {}".format(e))
        else:
            rep.line("PASS  {}  [{}]".format(rel, schema))
    ok = not failures
    code = EXIT_OK if ok else EXIT_VALIDATION
    rep.line()
    rep.line("check: {}/{} artifact(s) valid{}".format(
        checked - len(failures), checked,
        ", {} skipped".format(len(skipped)) if skipped else ""))
    rep.summary(make_summary(
        "check", store.bundle, ok, code,
        {"artifacts_checked": checked, "passed": checked - len(failures),
         "failed": len(failures), "skipped": len(skipped)},
        failures,
    ))
    return code


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="contracts-validate",
        description="serving-contracts consumer compatibility kit (validation-only).",
    )
    parser.add_argument(
        "--bundle",
        default=None,
        help="path to the contract bundle root (default: the bundle this kit ships in)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="emit a machine-readable JSON summary on stdout (human output moves to stderr)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-schemas", help="list schema names available in this bundle")

    p_validate = sub.add_parser("validate", help="validate files against a named schema")
    p_validate.add_argument("--schema", required=True, help="schema name (see list-schemas)")
    p_validate.add_argument("files", nargs="+", help="artifact files (.json, .jsonl, .sse)")

    p_selftest = sub.add_parser(
        "selftest",
        help="full golden-fixture sweep: positives MUST pass, invalid/ MUST fail",
    )
    p_selftest.add_argument("--verbose", action="store_true", help="print every fixture result")

    p_check = sub.add_parser(
        "check", help="validate a directory of consumer-emitted artifacts",
    )
    p_check.add_argument("directory", help="directory containing artifacts")
    p_check.add_argument("--schema", help="force one schema for every artifact in the directory")
    p_check.add_argument(
        "--ignore-unmatched", action="store_true",
        help="skip artifacts whose schema cannot be detected instead of erroring",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    rep = Reporter(machine=args.json)
    try:
        bundle = Path(args.bundle).resolve() if args.bundle else Path(__file__).resolve().parent.parent
        map_path = bundle / "kit" / "validation-map.json"
        if not map_path.is_file():
            raise KitError(
                "not a contract bundle (missing kit/validation-map.json): {}".format(bundle)
            )
        config = json.loads(map_path.read_text())
        store = SchemaStore(bundle, config)
        handler = {
            "list-schemas": cmd_list_schemas,
            "validate": cmd_validate,
            "selftest": cmd_selftest,
            "check": cmd_check,
        }[args.command]
        return handler(store, args, rep)
    except KitError as exc:
        rep.line("error: {}".format(exc))
        rep.summary(make_summary(
            args.command, args.bundle or "", False, EXIT_USAGE, {}, [
                {"file": None, "schema": None, "kind": "kit-error", "errors": [str(exc)]}
            ],
        ))
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
