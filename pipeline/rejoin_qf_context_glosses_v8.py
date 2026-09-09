#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_CANONICAL = 1642
SAFE_FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.json$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
ROOT_TOKEN_RE = re.compile(r"(?:^|\|)ROOT:([^|]+)")
KNOWN_REJOIN_CHECKS = [
    ("Erb", "9:97:1"),
    ("Erb", "49:14:2"),
    ("Erb", "12:2:4"),
    ("rHm", "41:50:3"),
]

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")

def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def clean_gloss_display(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(str(text))
    text = WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return ""
    text = HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    return WHITESPACE_RE.sub(" ", text).strip()

def location_verse_key(location: str) -> str:
    parts = location.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid whole-word location {location!r}")
    return f"{int(parts[0])}:{int(parts[1])}"

def load_synth(path: Path):
    spec = importlib.util.spec_from_file_location("quran_roots_qf_rejoin_v8_synth", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import synthesizer from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for model_name in (
        "RootIdea", "FormAccounting", "DictionarySense", "QuranExample",
        "QuranicForm", "ClassicalMeaning", "LaneUnitCoverage",
        "RootDictionaryArtifact",
    ):
        model = getattr(module, model_name, None)
        rebuild = getattr(model, "model_rebuild", None)
        if callable(rebuild):
            rebuild(force=True, _types_namespace=vars(module))
    for name in (
        "RootDictionaryArtifact",
        "apply_deterministic_bookkeeping_repairs",
        "validate_artifact",
    ):
        if not hasattr(module, name):
            raise RuntimeError(f"{path} lacks required symbol {name}")
    return module

def normalize_finding(value: Any) -> dict:
    if not isinstance(value, dict):
        return {"severity": "error", "code": "MALFORMED_FINDING", "message": repr(value)}
    return {
        **value,
        "severity": value.get("severity", "error"),
        "code": value.get("code", "UNKNOWN_FINDING_CODE"),
        "message": value.get("message", ""),
    }

def evaluate(*, synth, packet: dict, artifact: dict) -> dict:
    working = copy.deepcopy(artifact)
    repair_findings = [
        normalize_finding(x)
        for x in (
            synth.apply_deterministic_bookkeeping_repairs(working, packet=packet)
            or []
        )
    ]
    validation_findings = [
        normalize_finding(x)
        for x in (
            synth.validate_artifact(packet=packet, artifact=working)
            or []
        )
    ]
    findings = repair_findings + validation_findings
    errors = [row for row in findings if row.get("severity") == "error"]
    warnings = [row for row in findings if row.get("severity") == "warning"]
    return {
        "working": working,
        "changed": working != artifact,
        "errors": errors,
        "warnings": warnings,
        "error_codes": sorted({row.get("code") for row in errors if row.get("code")}),
        "warning_codes": sorted({row.get("code") for row in warnings if row.get("code")}),
    }

def schema_validate(synth, artifact: dict) -> list[dict]:
    try:
        synth.RootDictionaryArtifact.model_validate(artifact)
        return []
    except Exception as exc:
        method = getattr(exc, "errors", None)
        if callable(method):
            try:
                rows = method()
                return [row if isinstance(row, dict) else {"message": repr(row)} for row in rows]
            except Exception:
                pass
        return [{"type": type(exc).__name__, "message": str(exc)}]

def load_packets(path: Path):
    payload = load_json(path)
    packets = payload.get("packets") if isinstance(payload, dict) else payload
    if not isinstance(packets, list):
        raise RuntimeError(f"No packets list in {path}")
    ordered = []
    by_root = {}
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        root = packet.get("root")
        if not isinstance(root, str) or not root:
            continue
        if root in by_root:
            raise RuntimeError(f"Duplicate canonical packet root {root!r}")
        ordered.append(root)
        by_root[root] = packet
    if len(ordered) != EXPECTED_CANONICAL:
        raise RuntimeError(
            f"Canonical packet root count {len(ordered)} != {EXPECTED_CANONICAL}"
        )
    return ordered, by_root

def load_manifest_rows(path: Path) -> tuple[dict, dict[str, dict]]:
    payload = load_json(path)
    by_root = {
        row["root"]: row
        for row in (payload.get("roots") or [])
        if isinstance(row, dict) and isinstance(row.get("root"), str)
    }
    return payload, by_root

def scan_final(numbered_dir: Path, ordered_roots: list[str]) -> dict[str, Path]:
    found = {}
    for path in sorted(numbered_dir.glob("*.json")):
        match = SAFE_FILENAME_RE.match(path.name)
        if not match:
            raise RuntimeError(f"Unexpected FINAL JSON filename: {path.name}")
        rid = int(match.group(1))
        filename_root = match.group(2)
        if not (1 <= rid <= len(ordered_roots)):
            raise RuntimeError(f"Out-of-range root ID in {path.name}")
        canonical_root = ordered_roots[rid - 1]
        if filename_root != canonical_root:
            raise RuntimeError(
                f"Case-sensitive filename/canonical mismatch: {path.name} vs {canonical_root!r}"
            )
        artifact = load_json(path)
        if artifact.get("root") != canonical_root:
            raise RuntimeError(f"Case-sensitive internal root mismatch: {path.name}")
        if canonical_root in found:
            raise RuntimeError(f"Duplicate exact FINAL root {canonical_root!r}")
        found[canonical_root] = path
    if len(found) != EXPECTED_CANONICAL:
        raise RuntimeError(f"FINAL exact root count {len(found)} != {EXPECTED_CANONICAL}")
    return found

def load_qf_words(path: Path) -> tuple[dict, dict[str, dict]]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise RuntimeError("QF source is not a JSON object")
    words = payload.get("words")
    if not isinstance(words, dict):
        raise RuntimeError(f"{path} lacks the expected top-level 'words' object")
    return payload, words

def load_qac_root_sets_by_word(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if parts == ["LOCATION", "FORM", "TAG", "FEATURES"] or len(parts) != 4:
                continue
            location, _form, _tag, features = parts
            if not (location.startswith("(") and location.endswith(")")):
                continue
            nums = location[1:-1].split(":")
            if len(nums) != 4:
                continue
            match = ROOT_TOKEN_RE.search(features)
            if match is None:
                continue
            surah, ayah, word, _segment = nums
            result[f"{int(surah)}:{int(ayah)}:{int(word)}"].add(match.group(1))
    return dict(result)

def iter_examples(artifact: dict):
    for form_index, form in enumerate(artifact.get("quranic_forms") or []):
        if not isinstance(form, dict):
            continue
        public_form_id = form.get("public_form_id")
        for example_index, example in enumerate(form.get("quran_examples") or []):
            if isinstance(example, dict):
                yield form_index, public_form_id, example_index, example

def context_gloss_map(artifact: dict) -> dict[tuple[int, int], str]:
    return {
        (fi, ei): (ex.get("context_gloss") or "")
        for fi, _pid, ei, ex in iter_examples(artifact)
    }

def restore_old_glosses(candidate: dict, old_map: dict[tuple[int, int], str]) -> dict:
    restored = copy.deepcopy(candidate)
    for fi, _pid, ei, ex in iter_examples(restored):
        key = (fi, ei)
        if key not in old_map:
            raise RuntimeError(f"Candidate example structure changed unexpectedly at {key}")
        ex["context_gloss"] = old_map[key]
    return restored

def analyze_root(*, root: str, artifact: dict, qf_words: dict[str, dict],
                 qac_roots_by_word: dict[str, set[str]]) -> dict:
    baseline = copy.deepcopy(artifact)
    candidate = copy.deepcopy(artifact)
    old_glosses = context_gloss_map(baseline)
    rows = []
    blockers = []

    for fi, public_form_id, ei, example in iter_examples(candidate):
        location = example.get("word_location")
        verse_key = example.get("verse_key")
        old_gloss = example.get("context_gloss") or ""
        base = {
            "root": root,
            "public_form_id": public_form_id,
            "form_index": fi,
            "example_index": ei,
            "verse_key": verse_key,
            "word_location": location,
            "old_context_gloss": old_gloss,
        }

        if not isinstance(location, str) or not location:
            row = {**base, "classification": "INVALID_ARTIFACT_LOCATION",
                   "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
            rows.append(row); blockers.append(row); continue

        try:
            expected_verse = location_verse_key(location)
        except Exception:
            row = {**base, "classification": "INVALID_ARTIFACT_LOCATION",
                   "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
            rows.append(row); blockers.append(row); continue

        if verse_key != expected_verse:
            row = {**base, "classification": "ARTIFACT_VERSE_LOCATION_MISMATCH",
                   "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
            rows.append(row); blockers.append(row); continue

        root_set = qac_roots_by_word.get(location, set())
        if root not in root_set:
            row = {**base, "classification": "QAC_ROOT_NOT_AT_EXAMPLE_LOCATION",
                   "qac_roots_at_location": sorted(root_set),
                   "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
            rows.append(row); blockers.append(row); continue

        if len(root_set) > 1:
            rows.append({
                **base,
                "classification": "MULTI_ROOT_WORD_QUARANTINED",
                "qac_roots_at_location": sorted(root_set),
                "qf_context_gloss": "",
                "new_context_gloss": old_gloss,
                "changed": False,
            })
            continue

        qf = qf_words.get(location)
        if not isinstance(qf, dict):
            row = {**base, "classification": "QF_LOCATION_MISSING",
                   "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
            rows.append(row); blockers.append(row); continue

        qf_verse = qf.get("verse_key")
        if qf_verse != verse_key:
            row = {**base, "classification": "QF_VERSE_KEY_MISMATCH",
                   "qf_verse_key": qf_verse,
                   "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
            rows.append(row); blockers.append(row); continue

        qf_gloss = clean_gloss_display(qf.get("translation_en"))

        if not qf_gloss:
            if old_gloss:
                row = {**base, "classification": "QF_EMPTY_CURRENT_NONEMPTY",
                       "qf_context_gloss": "", "new_context_gloss": old_gloss, "changed": False}
                rows.append(row); blockers.append(row)
            else:
                rows.append({
                    **base,
                    "classification": "QF_EMPTY_BOTH_EMPTY",
                    "qf_context_gloss": "",
                    "new_context_gloss": "",
                    "changed": False,
                })
            continue

        if old_gloss == qf_gloss:
            rows.append({
                **base,
                "classification": "MATCH",
                "qf_context_gloss": qf_gloss,
                "new_context_gloss": old_gloss,
                "changed": False,
            })
            continue

        classification = "EMPTY_REJOINABLE" if not old_gloss else "MISMATCH_REJOINABLE"
        example["context_gloss"] = qf_gloss
        rows.append({
            **base,
            "classification": classification,
            "qf_context_gloss": qf_gloss,
            "new_context_gloss": qf_gloss,
            "changed": True,
        })

    only_context_gloss_changed = (
        canonical_json(restore_old_glosses(candidate, old_glosses))
        == canonical_json(baseline)
    )

    if not only_context_gloss_changed:
        blockers.append({
            "root": root,
            "classification": "NON_CONTEXT_GLOSS_CONTENT_CHANGED",
        })

    return {
        "candidate": candidate,
        "rows": rows,
        "blockers": blockers,
        "only_context_gloss_changed": only_context_gloss_changed,
        "changed_example_count": sum(1 for row in rows if row.get("changed")),
        "changed": candidate != baseline,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synth", default="synthesize_root_dictionary_v11.py")
    parser.add_argument("--packets", default="output/root_synthesis_packets_v3.json")
    parser.add_argument("--qac", default="quranic-corpus-morphology-0.4.txt")
    parser.add_argument("--qf", default="sources/quran-foundation/qf_wbw_en.json")
    parser.add_argument("--numbered-dir", default="final/numbered_roots")
    parser.add_argument("--v7-manifest", default="final/numbered_v7_manifest.json")
    parser.add_argument("--output-dir", default="final/qf_context_rejoin_v8")
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args()

    synth_path = Path(args.synth)
    packets_path = Path(args.packets)
    qac_path = Path(args.qac)
    qf_path = Path(args.qf)
    numbered_dir = Path(args.numbered_dir)
    v7_manifest_path = Path(args.v7_manifest)
    output_dir = Path(args.output_dir)
    candidates_dir = output_dir / "candidates"
    originals_dir = output_dir / "originals"
    per_root_dir = output_dir / "per_root"

    for required in (
        synth_path, packets_path, qac_path, qf_path, numbered_dir, v7_manifest_path,
    ):
        if not required.exists():
            raise SystemExit(f"Required path missing: {required}")

    for directory in (candidates_dir, originals_dir, per_root_dir):
        directory.mkdir(parents=True, exist_ok=True)

    synth = load_synth(synth_path)
    ordered_roots, packet_by_root = load_packets(packets_path)
    root_id = {root: i for i, root in enumerate(ordered_roots, start=1)}
    final_paths = scan_final(numbered_dir, ordered_roots)
    _v7_payload, v7_rows = load_manifest_rows(v7_manifest_path)

    if len(v7_rows) != EXPECTED_CANONICAL:
        raise SystemExit(f"v7 manifest root count {len(v7_rows)} != {EXPECTED_CANONICAL}")

    for root in ordered_roots:
        current_sha = sha256_file(final_paths[root])
        v7_sha = v7_rows[root].get("sha256")
        if current_sha != v7_sha:
            raise SystemExit(
                f"{root}: current FINAL differs from v7 manifest. "
                "Refusing to enrich an unexpected state."
            )

    qf_payload, qf_words = load_qf_words(qf_path)
    qf_sha = sha256_file(qf_path)
    qac_sha = sha256_file(qac_path)
    qac_roots_by_word = load_qac_root_sets_by_word(qac_path)

    qf_snapshot = {
        "qf_path": str(qf_path),
        "qf_sha256": qf_sha,
        "qf_word_count": len(qf_words),
        "qf_metadata": qf_payload.get("metadata"),
        "qf_summary": qf_payload.get("summary"),
        "qac_path": str(qac_path),
        "qac_sha256": qac_sha,
    }
    write_json(output_dir / "qf_source_snapshot.json", qf_snapshot)

    all_change_rows = []
    all_unresolved_rows = []
    root_reports = []
    changed_roots = []
    candidate_sha_by_root = {}
    classification_counts = Counter()
    total_example_count = 0
    all_ready = True

    for index, root in enumerate(ordered_roots, start=1):
        if args.progress_every > 0 and (
            index == 1 or index % args.progress_every == 0 or index == len(ordered_roots)
        ):
            print(
                f"[REJOIN] {index}/{len(ordered_roots)} "
                f"{root_id[root]:04d}_{root}.json",
                flush=True,
            )

        source_path = final_paths[root]
        baseline = load_json(source_path)
        baseline_schema_errors = schema_validate(synth, baseline)
        baseline_eval = evaluate(
            synth=synth,
            packet=packet_by_root[root],
            artifact=baseline,
        )

        if baseline_schema_errors or baseline_eval["errors"] or baseline_eval["changed"]:
            raise SystemExit(
                f"{root}: v7 baseline no longer validates cleanly: "
                f"schema={len(baseline_schema_errors)} "
                f"errors={baseline_eval['error_codes']} "
                f"repair_changed={baseline_eval['changed']}"
            )

        analysis = analyze_root(
            root=root,
            artifact=baseline,
            qf_words=qf_words,
            qac_roots_by_word=qac_roots_by_word,
        )
        candidate = analysis["candidate"]
        total_example_count += len(analysis["rows"])

        for row in analysis["rows"]:
            classification_counts[row["classification"]] += 1
            if row.get("changed"):
                all_change_rows.append({"root_id": root_id[root], **row})
            if row["classification"] in {
                "INVALID_ARTIFACT_LOCATION",
                "ARTIFACT_VERSE_LOCATION_MISMATCH",
                "QAC_ROOT_NOT_AT_EXAMPLE_LOCATION",
                "QF_LOCATION_MISSING",
                "QF_VERSE_KEY_MISMATCH",
                "QF_EMPTY_CURRENT_NONEMPTY",
            }:
                all_unresolved_rows.append({"root_id": root_id[root], **row})

        candidate_schema_errors = schema_validate(synth, candidate)
        candidate_eval = evaluate(
            synth=synth,
            packet=packet_by_root[root],
            artifact=candidate,
        )
        blockers = list(analysis["blockers"])

        if candidate_schema_errors:
            blockers.append({
                "classification": "CANDIDATE_SCHEMA_ERRORS",
                "count": len(candidate_schema_errors),
                "errors": candidate_schema_errors[:20],
            })

        if candidate_eval["errors"]:
            blockers.append({
                "classification": "CANDIDATE_VALIDATOR_ERRORS",
                "error_codes": candidate_eval["error_codes"],
                "errors": candidate_eval["errors"],
            })

        if candidate_eval["changed"]:
            blockers.append({
                "classification": "DETERMINISTIC_REPAIR_WOULD_CHANGE_CANDIDATE",
            })

        ready = (
            not blockers
            and analysis["only_context_gloss_changed"]
            and not candidate_schema_errors
            and not candidate_eval["errors"]
            and not candidate_eval["changed"]
        )

        if not ready:
            all_ready = False

        candidate_path = candidates_dir / f"{root_id[root]:04d}_{root}.json"

        if ready and analysis["changed"]:
            write_json(candidate_path, candidate)
            changed_roots.append(root)
            candidate_sha_by_root[root] = sha256_file(candidate_path)

        root_report = {
            "root_id": root_id[root],
            "root": root,
            "status": "READY" if ready else "BLOCKED",
            "changed": analysis["changed"],
            "changed_example_count": analysis["changed_example_count"],
            "source_path": str(source_path),
            "source_sha256": sha256_file(source_path),
            "candidate_path": str(candidate_path) if ready and analysis["changed"] else None,
            "candidate_sha256": candidate_sha_by_root.get(root),
            "only_context_gloss_changed": analysis["only_context_gloss_changed"],
            "baseline_warning_codes": baseline_eval["warning_codes"],
            "candidate_warning_codes": candidate_eval["warning_codes"],
            "blockers": blockers,
            "examples": analysis["rows"],
        }
        write_json(per_root_dir / f"{root_id[root]:04d}_{root}.json", root_report)
        root_reports.append(root_report)

    report_by_root = {row["root"]: row for row in root_reports}
    known_checks = []

    for root, location in KNOWN_REJOIN_CHECKS:
        match = next(
            (
                row
                for row in report_by_root.get(root, {}).get("examples", [])
                if row.get("word_location") == location
            ),
            None,
        )
        known_checks.append({
            "root": root,
            "word_location": location,
            "found": match is not None,
            "classification": match.get("classification") if match else None,
            "old_context_gloss": match.get("old_context_gloss") if match else None,
            "qf_context_gloss": match.get("qf_context_gloss") if match else None,
            "new_context_gloss": match.get("new_context_gloss") if match else None,
        })

    report = {
        "format": "quran-roots-qf-context-rejoin-v8",
        "status": "READY_TO_WRITE" if all_ready else "BLOCKED",
        "policy": {
            "api_calls": 0,
            "allowed_artifact_change":
                "$.quranic_forms[*].quran_examples[*].context_gloss only",
            "join_key": "exact surah:ayah:word",
            "root_comparison": "case-sensitive exact string equality",
            "multi_root_qac_words": "quarantined; no gloss written",
            "qf_missing_location": "block",
            "qf_empty_current_nonempty": "block",
            "qf_gloss_cleaning":
                "HTML unescape + remove HTML tags + collapse whitespace; "
                "same display-cleaning policy as build_quran_context_glosses_v4.py",
        },
        "source_snapshot": qf_snapshot,
        "summary": {
            "canonical_root_count": len(ordered_roots),
            "final_root_count": len(final_paths),
            "total_quran_examples": total_example_count,
            "changed_root_count": len(changed_roots),
            "changed_example_count": len(all_change_rows),
            "unresolved_blocking_example_count": len(all_unresolved_rows),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "known_regression_checks": known_checks,
        "changed_roots": [
            {
                "root_id": root_id[root],
                "root": root,
                "old_v7_sha256": v7_rows[root].get("sha256"),
                "candidate_v8_sha256": candidate_sha_by_root[root],
                "changed_example_count": report_by_root[root]["changed_example_count"],
            }
            for root in changed_roots
        ],
        "blocked_roots": [
            {
                "root_id": row["root_id"],
                "root": row["root"],
                "blockers": row["blockers"],
            }
            for row in root_reports
            if row["status"] == "BLOCKED"
        ],
    }

    write_json(output_dir / "report.json", report)
    write_csv(
        output_dir / "changes.csv",
        [
            "root_id", "root", "public_form_id", "form_index", "example_index",
            "verse_key", "word_location", "classification",
            "old_context_gloss", "qf_context_gloss", "new_context_gloss", "changed",
        ],
        all_change_rows,
    )
    write_csv(
        output_dir / "unresolved.csv",
        [
            "root_id", "root", "public_form_id", "form_index", "example_index",
            "verse_key", "word_location", "classification",
            "old_context_gloss", "qf_context_gloss", "new_context_gloss", "changed",
        ],
        all_unresolved_rows,
    )

    lines = [
        "=" * 108,
        "QURAN ROOTS — DETERMINISTIC QURAN FOUNDATION CONTEXT-GLOSS REJOIN V8",
        "=" * 108,
        f"Status:                         {report['status']}",
        f"Canonical roots:                {len(ordered_roots)}",
        f"FINAL roots checked:            {len(final_paths)}",
        f"Quran examples checked:         {total_example_count}",
        f"Changed roots:                  {len(changed_roots)}",
        f"Changed examples:               {len(all_change_rows)}",
        f"Blocking unresolved examples:   {len(all_unresolved_rows)}",
        f"QF word records:                {len(qf_words)}",
        f"QF source SHA-256:              {qf_sha}",
        "",
        "CLASSIFICATIONS",
        "-" * 108,
    ]

    for key, count in sorted(classification_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"{key:<60} {count:8}")

    lines += ["", "KNOWN REGRESSION CHECKS", "-" * 108]

    for row in known_checks:
        lines.append(
            f"{row['root']:<6} {row['word_location']:<12} "
            f"{str(row['classification']):<28} "
            f"{row['old_context_gloss']!r} -> {row['new_context_gloss']!r}"
        )

    if report["blocked_roots"]:
        lines += ["", "BLOCKED ROOTS", "-" * 108]
        for row in report["blocked_roots"]:
            lines.append(
                f"{row['root_id']:04d} {row['root']} "
                + ", ".join(item.get("classification", "UNKNOWN") for item in row["blockers"])
            )

    lines += ["", "No API calls were made."]
    (output_dir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print((output_dir / "report.txt").read_text(encoding="utf-8"))

    if not all_ready:
        print("BLOCKED — no FINAL files were modified.")
        return 2

    if not args.confirm_write:
        print(
            "DRY RUN COMPLETE — candidates are ready. "
            "Re-run with --confirm-write after reviewing report.json/changes.csv."
        )
        return 0

    for root in changed_roots:
        rid = root_id[root]
        source = final_paths[root]
        backup = originals_dir / f"{rid:04d}_{root}.json"
        v7_sha = v7_rows[root].get("sha256")

        if sha256_file(source) != v7_sha:
            raise SystemExit(f"{root}: FINAL changed after analysis.")

        if backup.exists():
            if sha256_file(backup) != v7_sha:
                raise SystemExit(f"{root}: conflicting v7 original backup exists: {backup}")
        else:
            shutil.copy2(source, backup)

        if sha256_file(backup) != v7_sha:
            raise SystemExit(f"{root}: v7 original backup hash verification failed.")

    for root in changed_roots:
        rid = root_id[root]
        destination = final_paths[root]
        candidate = candidates_dir / f"{rid:04d}_{root}.json"
        expected_old = v7_rows[root].get("sha256")
        expected_new = candidate_sha_by_root[root]

        if sha256_file(destination) != expected_old:
            raise SystemExit(f"{root}: FINAL changed immediately before install.")

        temp = destination.with_name(destination.name + ".qf-context-v8.tmp")
        if temp.exists():
            raise SystemExit(f"Unexpected temp file exists: {temp}")

        shutil.copy2(candidate, temp)

        if sha256_file(temp) != expected_new:
            raise SystemExit(f"{root}: temporary candidate hash verification failed.")

        os.replace(temp, destination)

        if sha256_file(destination) != expected_new:
            raise SystemExit(f"{root}: installed v8 hash verification failed.")

    final_after = scan_final(numbered_dir, ordered_roots)
    manifest_rows = []
    global_errors = []

    for root in ordered_roots:
        p = final_after[root]
        artifact = load_json(p)
        schema_errors = schema_validate(synth, artifact)
        ev = evaluate(
            synth=synth,
            packet=packet_by_root[root],
            artifact=artifact,
        )

        if schema_errors or ev["errors"] or ev["changed"]:
            global_errors.append({
                "root_id": root_id[root],
                "root": root,
                "schema_error_count": len(schema_errors),
                "validator_error_codes": ev["error_codes"],
                "deterministic_repair_would_change": ev["changed"],
            })

        manifest_rows.append({
            "root_id": root_id[root],
            "root": root,
            "filename": p.name,
            "path": str(p),
            "sha256": sha256_file(p),
            "warning_codes": ev["warning_codes"],
            "release_provenance":
                "qf_context_rejoin_v8"
                if root in candidate_sha_by_root
                else "numbered_v7_unchanged",
            "prior_v7_sha256": v7_rows[root].get("sha256"),
        })

    if global_errors:
        raise SystemExit(
            "Post-write global validation failed:\n"
            + json.dumps(global_errors[:50], ensure_ascii=False, indent=2)
        )

    changes_by_root = defaultdict(list)
    for row in all_change_rows:
        changes_by_root[row["root"]].append(row)

    authorized_changes = []
    for root in changed_roots:
        rid = root_id[root]
        authorized_changes.append({
            "root_id": rid,
            "root": root,
            "old_v7_sha256": v7_rows[root].get("sha256"),
            "new_v8_sha256": sha256_file(final_after[root]),
            "preserved_v7_original": str(originals_dir / f"{rid:04d}_{root}.json"),
            "changed_example_count": len(changes_by_root[root]),
            "changed_examples": [
                {
                    "public_form_id": row["public_form_id"],
                    "form_index": row["form_index"],
                    "example_index": row["example_index"],
                    "verse_key": row["verse_key"],
                    "word_location": row["word_location"],
                    "classification": row["classification"],
                    "old_context_gloss": row["old_context_gloss"],
                    "new_context_gloss": row["new_context_gloss"],
                }
                for row in changes_by_root[root]
            ],
        })

    v8_manifest = {
        "format": "quran-roots-numbered-final-v8-qf-context-gloss-rejoined",
        "release_type": "deterministic contextual enrichment; no lexical synthesis",
        "canonical_root_count": EXPECTED_CANONICAL,
        "completed_root_count": EXPECTED_CANONICAL,
        "unresolved_root_count": 0,
        "complete": True,
        "numbered_final_hard_error_count": 0,
        "allowed_change":
            "$.quranic_forms[*].quran_examples[*].context_gloss only",
        "qf_source": {
            "path": str(qf_path),
            "sha256": qf_sha,
            "word_count": len(qf_words),
            "metadata": qf_payload.get("metadata"),
            "summary": qf_payload.get("summary"),
        },
        "qac_source": {
            "path": str(qac_path),
            "sha256": qac_sha,
        },
        "prior_manifest": str(v7_manifest_path),
        "changed_root_count": len(changed_roots),
        "changed_example_count": len(all_change_rows),
        "classification_counts": dict(sorted(classification_counts.items())),
        "authorized_changed_roots": authorized_changes,
        "roots": manifest_rows,
    }

    write_json(Path("final/numbered_v8_manifest.json"), v8_manifest)
    write_json(
        output_dir / "report_installed.json",
        {
            **report,
            "status": "INSTALLED",
            "v8_manifest": "final/numbered_v8_manifest.json",
            "global_post_write_hard_error_count": 0,
        },
    )

    print()
    print("=" * 108)
    print("QF CONTEXT-GLOSS V8 INSTALLED")
    print("=" * 108)
    print(f"Numbered FINAL:             {EXPECTED_CANONICAL} / {EXPECTED_CANONICAL}")
    print(f"Changed roots:              {len(changed_roots)}")
    print(f"Changed Quran examples:     {len(all_change_rows)}")
    print("Lexical/schema fields changed: 0")
    print("Current validator hard errors: 0")
    print("API calls:                  0")
    print("Manifest:                   final/numbered_v8_manifest.json")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
