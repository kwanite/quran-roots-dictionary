#!/usr/bin/env python3
"""
Quran Roots — build the canonical numbered flat FINAL root set.

NON-DESTRUCTIVE:
- Does not delete or modify anything under output/.
- Does not modify attempt files.
- Does not modify promoted artifacts.
- Does not modify the existing final/roots staging directory.
- Writes only under final/numbered_roots/ plus numbered-manifest/report files.

Stable root IDs:
    root_id = 1-based position in output/root_synthesis_packets_v3.json
    filename = <4-digit-root-id>_<exact-root>.json

Examples:
    0012_Slw.json
    0013_slw.json

The QAC root string inside the dictionary remains unchanged.

Source precedence for each canonical root:
1. Current promoted artifact, if available.
2. Current parsed_artifact from saved attempt(s).

Each candidate is deep-copied, CURRENT deterministic repairs are applied IN
MEMORY only, and the result is validated with the CURRENT
synthesize_root_dictionary_v11.py validator.

A root is written into final/numbered_roots/ only if the resulting artifact has
ZERO hard validation errors.

If a deterministic repair is needed to make an already-promoted artifact or
attempt current, the repaired in-memory dictionary is written ONLY to the final
folder. The source file is left untouched. The manifest records the repair
codes and exact source path.

This version deliberately does NOT reconstruct missing per-root data from the
raw Batch JSONL. Any root lacking a usable promoted artifact or parsed attempt
is reported separately so raw-Batch recovery can be handled as a controlled
next step rather than silently guessed here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional


EXPECTED_CANONICAL_ROOTS = 1642
DEFAULT_RUN_LABEL = "luna-high-unit-ledger-v11"

ATTEMPT_RE = re.compile(
    r"^(?P<filename_root>.+)__attempt-(?P<number>\d+)\.json$"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_synth_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "quran_roots_current_synth_for_numbered_final",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Could not import synthesizer from {path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in (
        "apply_deterministic_bookkeeping_repairs",
        "validate_artifact",
    ):
        if not hasattr(module, name):
            raise RuntimeError(
                f"{path} does not expose required function {name}"
            )

    return module


def normalize_finding(value: Any) -> dict:
    if not isinstance(value, dict):
        return {
            "severity": "error",
            "code": "MALFORMED_FINDING",
            "message": repr(value),
        }

    return {
        **value,
        "severity": value.get("severity", "error"),
        "code": value.get("code", "UNKNOWN_FINDING_CODE"),
        "message": value.get("message", ""),
    }


def evaluate_candidate(
    *,
    synth,
    packet: dict,
    artifact: dict,
) -> dict:
    working = copy.deepcopy(artifact)

    repair_findings = [
        normalize_finding(x)
        for x in (
            synth.apply_deterministic_bookkeeping_repairs(
                working,
                packet=packet,
            )
            or []
        )
    ]

    validation_findings = [
        normalize_finding(x)
        for x in (
            synth.validate_artifact(
                packet=packet,
                artifact=working,
            )
            or []
        )
    ]

    all_findings = (
        repair_findings
        + validation_findings
    )

    errors = [
        x
        for x in all_findings
        if x.get("severity") == "error"
    ]

    warnings = [
        x
        for x in all_findings
        if x.get("severity") == "warning"
    ]

    repair_codes = sorted({
        x.get("code")
        for x in repair_findings
        if x.get("code")
    })

    return {
        "working_artifact": working,
        "repair_findings": repair_findings,
        "validation_findings": validation_findings,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "error_codes": sorted({
            x.get("code")
            for x in errors
            if x.get("code")
        }),
        "warning_codes": sorted({
            x.get("code")
            for x in warnings
            if x.get("code")
        }),
        "repair_codes": repair_codes,
        "changed_by_current_repairs": (
            working != artifact
        ),
    }


def load_canonical_packets(
    path: Path,
) -> tuple[list[str], dict[str, dict]]:
    payload = load_json(path)

    packets = (
        payload.get("packets")
        if isinstance(payload, dict)
        else payload
    )

    if not isinstance(packets, list):
        raise RuntimeError(
            f"Could not find packets list in {path}"
        )

    ordered_roots = []
    by_root = {}

    for packet in packets:
        if not isinstance(packet, dict):
            continue

        root = packet.get("root")

        if not isinstance(root, str) or not root:
            continue

        if root in by_root:
            raise RuntimeError(
                f"Duplicate canonical root in packet file: {root!r}"
            )

        ordered_roots.append(root)
        by_root[root] = packet

    if len(ordered_roots) != EXPECTED_CANONICAL_ROOTS:
        raise RuntimeError(
            f"Canonical root count is {len(ordered_roots)}, "
            f"expected {EXPECTED_CANONICAL_ROOTS}"
        )

    return ordered_roots, by_root


def promoted_artifact_path(
    *,
    output_dir: Path,
    run_label: str,
    root: str,
) -> Path:
    return (
        output_dir
        / (
            "root_dictionary_artifact_v11__"
            f"{run_label}__{root}.json"
        )
    )


def determine_attempt_root(
    payload: dict,
    path: Path,
) -> Optional[str]:
    metadata = payload.get("metadata")

    if isinstance(metadata, dict):
        root = metadata.get("root")
        if isinstance(root, str) and root:
            return root

    parsed = payload.get("parsed_artifact")

    if isinstance(parsed, dict):
        root = parsed.get("root")
        if isinstance(root, str) and root:
            return root

    match = ATTEMPT_RE.match(path.name)

    if match:
        return match.group("filename_root")

    return None


def index_attempts(
    attempt_dir: Path,
) -> tuple[dict[str, list[dict]], list[dict]]:
    by_root: dict[str, list[dict]] = defaultdict(list)
    bad = []

    for path in sorted(
        attempt_dir.glob("*__attempt-*.json")
    ):
        try:
            payload = load_json(path)

            if not isinstance(payload, dict):
                bad.append({
                    "path": str(path),
                    "reason": "Attempt JSON is not an object.",
                })
                continue

            root = determine_attempt_root(
                payload,
                path,
            )

            if not root:
                bad.append({
                    "path": str(path),
                    "reason": (
                        "Could not determine root from metadata, "
                        "parsed_artifact, or filename."
                    ),
                })
                continue

            match = ATTEMPT_RE.match(path.name)

            attempt_number = (
                int(match.group("number"))
                if match
                else None
            )

            by_root[root].append({
                "path": path,
                "payload": payload,
                "attempt_number": attempt_number,
            })

        except Exception as exc:
            bad.append({
                "path": str(path),
                "reason": (
                    f"{type(exc).__name__}: {exc}"
                ),
            })

    for root in by_root:
        by_root[root].sort(
            key=lambda x: (
                x["attempt_number"]
                if x["attempt_number"] is not None
                else -1,
                str(x["path"]),
            )
        )

    return by_root, bad


def write_final_artifact(
    path: Path,
    artifact: dict,
) -> str:
    """
    Write canonical pretty JSON for the FINAL folder.

    We intentionally serialize the validated in-memory artifact because a
    parsed attempt may need current deterministic repairs. No source file is
    changed.
    """
    text = json.dumps(
        artifact,
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    data = text.encode("utf-8")

    path.write_bytes(data)

    return sha256_bytes(data)


def choose_candidate(
    *,
    root: str,
    packet: dict,
    synth,
    output_dir: Path,
    run_label: str,
    attempts_by_root: dict[str, list[dict]],
) -> tuple[Optional[dict], list[dict]]:
    """
    Returns (best_passing_candidate, evaluated_candidates).

    Promoted artifact has priority when it passes.
    Otherwise evaluate every parsed saved attempt and choose:
      - zero hard errors
      - fewest warnings
      - highest attempt number
    """

    evaluated = []

    artifact_path = promoted_artifact_path(
        output_dir=output_dir,
        run_label=run_label,
        root=root,
    )

    if artifact_path.exists():
        try:
            artifact = load_json(artifact_path)

            if (
                isinstance(artifact, dict)
                and artifact.get("root") == root
            ):
                ev = evaluate_candidate(
                    synth=synth,
                    packet=packet,
                    artifact=artifact,
                )

                item = {
                    "source_kind": "promoted_artifact",
                    "source_path": str(artifact_path),
                    "attempt_number": None,
                    "evaluation": ev,
                }

                evaluated.append(item)

                if ev["error_count"] == 0:
                    return item, evaluated

            else:
                evaluated.append({
                    "source_kind": "promoted_artifact",
                    "source_path": str(artifact_path),
                    "attempt_number": None,
                    "evaluation": {
                        "error_count": 1,
                        "warning_count": 0,
                        "error_codes": ["ROOT_FIELD_MISMATCH"],
                        "warning_codes": [],
                        "repair_codes": [],
                        "changed_by_current_repairs": False,
                        "errors": [{
                            "severity": "error",
                            "code": "ROOT_FIELD_MISMATCH",
                            "message": (
                                f"Expected root {root!r}, got "
                                f"{artifact.get('root')!r}"
                            ),
                        }],
                        "warnings": [],
                    },
                })

        except Exception as exc:
            evaluated.append({
                "source_kind": "promoted_artifact",
                "source_path": str(artifact_path),
                "attempt_number": None,
                "evaluation": {
                    "error_count": 1,
                    "warning_count": 0,
                    "error_codes": ["SOURCE_READ_ERROR"],
                    "warning_codes": [],
                    "repair_codes": [],
                    "changed_by_current_repairs": False,
                    "errors": [{
                        "severity": "error",
                        "code": "SOURCE_READ_ERROR",
                        "message": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    }],
                    "warnings": [],
                },
            })

    passing_attempts = []

    for attempt in attempts_by_root.get(root, []):
        payload = attempt["payload"]
        parsed = payload.get("parsed_artifact")

        if not isinstance(parsed, dict):
            evaluated.append({
                "source_kind": "saved_attempt",
                "source_path": str(attempt["path"]),
                "attempt_number": attempt["attempt_number"],
                "evaluation": {
                    "error_count": 1,
                    "warning_count": 0,
                    "error_codes": ["NO_PARSED_ARTIFACT"],
                    "warning_codes": [],
                    "repair_codes": [],
                    "changed_by_current_repairs": False,
                    "errors": [{
                        "severity": "error",
                        "code": "NO_PARSED_ARTIFACT",
                        "message": (
                            "Saved attempt has no parsed_artifact."
                        ),
                    }],
                    "warnings": [],
                },
            })
            continue

        if parsed.get("root") != root:
            evaluated.append({
                "source_kind": "saved_attempt",
                "source_path": str(attempt["path"]),
                "attempt_number": attempt["attempt_number"],
                "evaluation": {
                    "error_count": 1,
                    "warning_count": 0,
                    "error_codes": ["ROOT_FIELD_MISMATCH"],
                    "warning_codes": [],
                    "repair_codes": [],
                    "changed_by_current_repairs": False,
                    "errors": [{
                        "severity": "error",
                        "code": "ROOT_FIELD_MISMATCH",
                        "message": (
                            f"Expected root {root!r}, got "
                            f"{parsed.get('root')!r}"
                        ),
                    }],
                    "warnings": [],
                },
            })
            continue

        try:
            ev = evaluate_candidate(
                synth=synth,
                packet=packet,
                artifact=parsed,
            )

        except Exception as exc:
            ev = {
                "error_count": 1,
                "warning_count": 0,
                "error_codes": ["VALIDATION_EXCEPTION"],
                "warning_codes": [],
                "repair_codes": [],
                "changed_by_current_repairs": False,
                "errors": [{
                    "severity": "error",
                    "code": "VALIDATION_EXCEPTION",
                    "message": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                }],
                "warnings": [],
            }

        item = {
            "source_kind": "saved_attempt",
            "source_path": str(attempt["path"]),
            "attempt_number": attempt["attempt_number"],
            "evaluation": ev,
        }

        evaluated.append(item)

        if ev["error_count"] == 0:
            passing_attempts.append(item)

    if passing_attempts:
        passing_attempts.sort(
            key=lambda x: (
                x["evaluation"]["warning_count"],
                -(
                    x["attempt_number"]
                    if x["attempt_number"] is not None
                    else -1
                ),
                x["source_path"],
            )
        )

        return passing_attempts[0], evaluated

    return None, evaluated


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build final/numbered_roots as a flat, case-safe FINAL set "
            "using the canonical packet order as stable root IDs."
        )
    )

    parser.add_argument(
        "--synth",
        default="synthesize_root_dictionary_v11.py",
    )

    parser.add_argument(
        "--packets",
        default="output/root_synthesis_packets_v3.json",
    )

    parser.add_argument(
        "--output-dir",
        default="output",
    )

    parser.add_argument(
        "--run-label",
        default=DEFAULT_RUN_LABEL,
    )

    parser.add_argument(
        "--attempt-dir",
        default=None,
    )

    parser.add_argument(
        "--final-dir",
        default="final",
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Allow overwriting existing files under final/numbered_roots. "
            "No source/output files are changed."
        ),
    )

    args = parser.parse_args()

    synth_path = Path(args.synth)
    packets_path = Path(args.packets)
    output_dir = Path(args.output_dir)
    final_dir = Path(args.final_dir)

    attempt_dir = (
        Path(args.attempt_dir)
        if args.attempt_dir
        else (
            output_dir
            / "root-dictionary-synthesis-attempts"
            / args.run_label
        )
    )

    numbered_dir = final_dir / "numbered_roots"

    for required in (
        synth_path,
        packets_path,
        output_dir,
        attempt_dir,
    ):
        if not required.exists():
            raise SystemExit(
                f"Required path does not exist: {required}"
            )

    if numbered_dir.exists() and not args.refresh:
        raise SystemExit(
            f"{numbered_dir} already exists. Refusing to overwrite it. "
            "Use --refresh only if you intentionally want to rebuild "
            "the numbered FINAL copies."
        )

    numbered_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    synth = load_synth_module(
        synth_path
    )

    ordered_roots, packet_by_root = (
        load_canonical_packets(
            packets_path
        )
    )

    attempts_by_root, bad_attempt_files = (
        index_attempts(
            attempt_dir
        )
    )

    manifest_rows = []
    unresolved_rows = []

    source_counts = defaultdict(int)
    repair_code_counts = defaultdict(int)
    hard_error_code_counts = defaultdict(int)

    for root_id, root in enumerate(
        ordered_roots,
        start=1,
    ):
        filename = (
            f"{root_id:04d}_{root}.json"
        )

        destination = (
            numbered_dir
            / filename
        )

        candidate, evaluated = choose_candidate(
            root=root,
            packet=packet_by_root[root],
            synth=synth,
            output_dir=output_dir,
            run_label=args.run_label,
            attempts_by_root=attempts_by_root,
        )

        if candidate is None:
            codes = sorted({
                code
                for item in evaluated
                for code in (
                    item.get(
                        "evaluation",
                        {}
                    ).get(
                        "error_codes",
                        []
                    )
                    or []
                )
            })

            for code in codes:
                hard_error_code_counts[code] += 1

            unresolved_rows.append({
                "root_id": root_id,
                "root": root,
                "expected_filename": filename,
                "candidate_count": len(evaluated),
                "current_error_codes": codes,
                "candidates": [
                    {
                        "source_kind": item.get("source_kind"),
                        "source_path": item.get("source_path"),
                        "attempt_number": item.get("attempt_number"),
                        "error_count": item.get(
                            "evaluation",
                            {}
                        ).get(
                            "error_count"
                        ),
                        "warning_count": item.get(
                            "evaluation",
                            {}
                        ).get(
                            "warning_count"
                        ),
                        "error_codes": item.get(
                            "evaluation",
                            {}
                        ).get(
                            "error_codes",
                            []
                        ),
                        "warning_codes": item.get(
                            "evaluation",
                            {}
                        ).get(
                            "warning_codes",
                            []
                        ),
                    }
                    for item in evaluated
                ],
            })

            continue

        ev = candidate["evaluation"]

        final_artifact = ev[
            "working_artifact"
        ]

        # Final sanity check: the root identity itself is never changed.
        if final_artifact.get("root") != root:
            raise RuntimeError(
                f"Internal safety failure: root changed for {root!r}"
            )

        final_sha = write_final_artifact(
            destination,
            final_artifact,
        )

        source_kind = candidate[
            "source_kind"
        ]

        source_counts[
            source_kind
        ] += 1

        for code in ev[
            "repair_codes"
        ]:
            repair_code_counts[
                code
            ] += 1

        manifest_rows.append({
            "root_id": root_id,
            "root": root,
            "filename": filename,
            "destination": str(destination),
            "sha256": final_sha,
            "source_kind": source_kind,
            "source_path": candidate[
                "source_path"
            ],
            "source_attempt_number": candidate[
                "attempt_number"
            ],
            "current_deterministic_repairs_applied_in_final_copy": (
                ev[
                    "changed_by_current_repairs"
                ]
            ),
            "repair_codes": ev[
                "repair_codes"
            ],
            "warning_count": ev[
                "warning_count"
            ],
            "warning_codes": ev[
                "warning_codes"
            ],
        })

        if root_id % 100 == 0:
            print(
                f"Processed {root_id}/"
                f"{len(ordered_roots)} canonical roots..."
            )

    complete_count = len(
        manifest_rows
    )

    unresolved_count = len(
        unresolved_rows
    )

    manifest = {
        "format": "quran-roots-numbered-final-v2",
        "canonical_order_source": str(packets_path),
        "root_id_rule": (
            "1-based position in root_synthesis_packets_v3.json packets array"
        ),
        "filename_rule": (
            "<4-digit-root-id>_<exact-QAC-root>.json"
        ),
        "root_json_schema_changed": False,
        "root_string_preserved_exactly": True,
        "canonical_root_count": len(ordered_roots),
        "completed_root_count": complete_count,
        "unresolved_root_count": unresolved_count,
        "complete": unresolved_count == 0,
        "no_source_files_deleted_or_modified": True,
        "source_counts": dict(
            sorted(
                source_counts.items()
            )
        ),
        "roots": manifest_rows,
    }

    unresolved = {
        "canonical_root_count": len(ordered_roots),
        "completed_root_count": complete_count,
        "unresolved_root_count": unresolved_count,
        "unresolved": unresolved_rows,
        "unresolved_root_ids": [
            x["root_id"]
            for x in unresolved_rows
        ],
        "unresolved_roots": [
            x["root"]
            for x in unresolved_rows
        ],
        "hard_error_code_root_counts": dict(
            sorted(
                hard_error_code_counts.items(),
                key=lambda x: (
                    -x[1],
                    x[0],
                )
            )
        ),
        "bad_attempt_files": bad_attempt_files,
    }

    report = {
        "manifest_summary": {
            key: value
            for key, value in manifest.items()
            if key != "roots"
        },
        "repair_code_root_counts": dict(
            sorted(
                repair_code_counts.items(),
                key=lambda x: (
                    -x[1],
                    x[0],
                )
            )
        ),
        "unresolved_summary": {
            key: value
            for key, value in unresolved.items()
            if key not in (
                "unresolved",
                "bad_attempt_files",
            )
        },
        "bad_attempt_files": bad_attempt_files,
    }

    write_json(
        final_dir / "numbered_manifest.json",
        manifest,
    )

    write_json(
        final_dir / "numbered_unresolved.json",
        unresolved,
    )

    write_json(
        final_dir / "numbered_build_report.json",
        report,
    )

    lines = [
        "=" * 86,
        "QURAN ROOTS — NUMBERED FLAT FINAL BUILD V2",
        "=" * 86,
        "",
        f"Canonical roots:                    {len(ordered_roots)}",
        f"Completed numbered final roots:     {complete_count}",
        f"Unresolved roots:                   {unresolved_count}",
        "",
        "Source counts:",
    ]

    for key, value in sorted(
        source_counts.items()
    ):
        lines.append(
            f"  {key:<30} {value}"
        )

    lines += [
        "",
        "Current deterministic repairs applied only to FINAL copies:",
    ]

    if repair_code_counts:
        for key, value in sorted(
            repair_code_counts.items(),
            key=lambda x: (
                -x[1],
                x[0],
            )
        ):
            lines.append(
                f"  {key:<44} {value}"
            )
    else:
        lines.append(
            "  none"
        )

    lines += [
        "",
        "Unresolved hard-error families:",
    ]

    if hard_error_code_counts:
        for key, value in sorted(
            hard_error_code_counts.items(),
            key=lambda x: (
                -x[1],
                x[0],
            )
        ):
            lines.append(
                f"  {key:<44} {value}"
            )
    else:
        lines.append(
            "  none"
        )

    lines += [
        "",
        "Nothing under output/ was deleted or modified.",
        "Existing final/roots/ staging copies were left untouched.",
        "",
        "Outputs:",
        f"  {numbered_dir}/",
        f"  {final_dir / 'numbered_manifest.json'}",
        f"  {final_dir / 'numbered_unresolved.json'}",
        f"  {final_dir / 'numbered_build_report.json'}",
        f"  {final_dir / 'numbered_build_report.txt'}",
        "",
    ]

    if unresolved_rows:
        lines += [
            "UNRESOLVED ROOTS",
            "-" * 86,
            " ".join(
                x["root"]
                for x in unresolved_rows
            ),
            "",
        ]

    text = "\n".join(
        lines
    )

    (
        final_dir
        / "numbered_build_report.txt"
    ).write_text(
        text,
        encoding="utf-8",
    )

    print()
    print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
