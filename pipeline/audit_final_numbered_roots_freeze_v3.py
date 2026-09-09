#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_CANONICAL = 1642
SAFE_FILENAME_RE = re.compile(r"^(\d{4})_(.+)\.json$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
ROOT_TOKEN_RE = re.compile(r"(?:^|\|)ROOT:([^|]+)")

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

def load_synth(path: Path):
    spec = importlib.util.spec_from_file_location("quran_roots_freeze_v3_synth", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
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

def schema_errors(synth, artifact: dict) -> list:
    try:
        synth.RootDictionaryArtifact.model_validate(artifact)
        return []
    except Exception as exc:
        method = getattr(exc, "errors", None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass
        return [{"message": str(exc)}]

def load_packets(path: Path):
    payload = load_json(path)
    packets = payload.get("packets") if isinstance(payload, dict) else payload
    if not isinstance(packets, list):
        raise RuntimeError("Packet file lacks packets list")
    ordered = []
    by_root = {}
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        root = packet.get("root")
        if isinstance(root, str) and root:
            if root in by_root:
                raise RuntimeError(f"Duplicate canonical root {root!r}")
            ordered.append(root)
            by_root[root] = packet
    return ordered, by_root

def load_manifest(path: Path):
    payload = load_json(path)
    rows = {
        row["root"]: row
        for row in (payload.get("roots") or [])
        if isinstance(row, dict) and isinstance(row.get("root"), str)
    }
    return payload, rows

def load_qf_words(path: Path):
    payload = load_json(path)
    words = payload.get("words")
    if not isinstance(words, dict):
        raise RuntimeError(f"{path} lacks top-level words object")
    return payload, words

def load_qac_root_sets_by_word(path: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 4:
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

def normalize_v8_back_to_v7(*, v8: dict, v7: dict) -> tuple[dict, list[dict]]:
    normalized = copy.deepcopy(v8)
    mismatches = []
    v7_forms = v7.get("quranic_forms") or []
    v8_forms = normalized.get("quranic_forms") or []

    if len(v7_forms) != len(v8_forms):
        return normalized, [{
            "code": "QURANIC_FORM_COUNT_CHANGED",
            "v7": len(v7_forms),
            "v8": len(v8_forms),
        }]

    for fi, (old_form, new_form) in enumerate(zip(v7_forms, v8_forms)):
        old_examples = old_form.get("quran_examples") or []
        new_examples = new_form.get("quran_examples") or []

        if len(old_examples) != len(new_examples):
            mismatches.append({
                "code": "QURAN_EXAMPLE_COUNT_CHANGED",
                "form_index": fi,
                "v7": len(old_examples),
                "v8": len(new_examples),
            })
            continue

        for old_ex, new_ex in zip(old_examples, new_examples):
            new_ex["context_gloss"] = old_ex.get("context_gloss") or ""

    return normalized, mismatches

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synth", default="synthesize_root_dictionary_v11.py")
    parser.add_argument("--packets", default="output/root_synthesis_packets_v3.json")
    parser.add_argument("--qac", default="quranic-corpus-morphology-0.4.txt")
    parser.add_argument("--qf", default="sources/quran-foundation/qf_wbw_en.json")
    parser.add_argument("--numbered-dir", default="final/numbered_roots")
    parser.add_argument("--v8-manifest", default="final/numbered_v8_manifest.json")
    parser.add_argument("--v7-manifest", default="final/numbered_v7_manifest.json")
    parser.add_argument("--v8-rejoin-dir", default="final/qf_context_rejoin_v8")
    parser.add_argument("--output-dir", default="final/audit/final_freeze_v3")
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args()

    synth_path = Path(args.synth)
    packets_path = Path(args.packets)
    qac_path = Path(args.qac)
    qf_path = Path(args.qf)
    numbered_dir = Path(args.numbered_dir)
    v8_manifest_path = Path(args.v8_manifest)
    v7_manifest_path = Path(args.v7_manifest)
    rejoin_dir = Path(args.v8_rejoin_dir)
    output_dir = Path(args.output_dir)

    for required in (
        synth_path, packets_path, qac_path, qf_path, numbered_dir,
        v8_manifest_path, v7_manifest_path, rejoin_dir,
    ):
        if not required.exists():
            raise SystemExit(f"Required path missing: {required}")

    output_dir.mkdir(parents=True, exist_ok=True)

    synth = load_synth(synth_path)
    ordered_roots, packet_by_root = load_packets(packets_path)

    if len(ordered_roots) != EXPECTED_CANONICAL:
        raise SystemExit(
            f"Canonical root count {len(ordered_roots)} != {EXPECTED_CANONICAL}"
        )

    root_id = {root: i for i, root in enumerate(ordered_roots, start=1)}
    v8_payload, v8_rows = load_manifest(v8_manifest_path)
    _v7_payload, v7_rows = load_manifest(v7_manifest_path)

    if len(v8_rows) != EXPECTED_CANONICAL:
        raise SystemExit("v8 manifest does not contain 1642 roots")

    if len(v7_rows) != EXPECTED_CANONICAL:
        raise SystemExit("v7 manifest does not contain 1642 roots")

    authorized_list = v8_payload.get("authorized_changed_roots") or []
    authorized = {
        row["root"]: row
        for row in authorized_list
        if isinstance(row, dict) and isinstance(row.get("root"), str)
    }

    qf_payload, qf_words = load_qf_words(qf_path)
    qf_sha = sha256_file(qf_path)
    qac_sha = sha256_file(qac_path)
    qac_root_sets = load_qac_root_sets_by_word(qac_path)

    hard = []
    qf_checks = []
    warning_counts = Counter()
    current_paths = {}
    final_jsons = sorted(numbered_dir.glob("*.json"))

    if len(final_jsons) != EXPECTED_CANONICAL:
        hard.append({
            "code": "FINAL_JSON_COUNT_MISMATCH",
            "expected": EXPECTED_CANONICAL,
            "actual": len(final_jsons),
        })

    for index, path in enumerate(final_jsons, start=1):
        if args.progress_every > 0 and (
            index == 1 or index % args.progress_every == 0 or index == len(final_jsons)
        ):
            print(f"[AUDIT V3] {index}/{len(final_jsons)} {path.name}", flush=True)

        match = SAFE_FILENAME_RE.match(path.name)
        if not match:
            hard.append({"code": "INVALID_FILENAME", "filename": path.name})
            continue

        rid = int(match.group(1))
        filename_root = match.group(2)

        if not (1 <= rid <= EXPECTED_CANONICAL):
            hard.append({"code": "ROOT_ID_OUT_OF_RANGE", "filename": path.name})
            continue

        canonical_root = ordered_roots[rid - 1]

        if filename_root != canonical_root:
            hard.append({
                "code": "CASE_SENSITIVE_FILENAME_ROOT_MISMATCH",
                "filename": path.name,
                "canonical_root": canonical_root,
            })
            continue

        artifact = load_json(path)

        if artifact.get("root") != canonical_root:
            hard.append({
                "code": "CASE_SENSITIVE_INTERNAL_ROOT_MISMATCH",
                "filename": path.name,
                "json_root": artifact.get("root"),
                "canonical_root": canonical_root,
            })
            continue

        current_paths[canonical_root] = path
        current_sha = sha256_file(path)

        v8_row = v8_rows.get(canonical_root)
        if v8_row is None or v8_row.get("sha256") != current_sha:
            hard.append({
                "code": "V8_MANIFEST_HASH_MISMATCH",
                "root": canonical_root,
                "current_sha256": current_sha,
                "manifest_sha256": v8_row.get("sha256") if v8_row else None,
            })

        schema = schema_errors(synth, artifact)
        ev = evaluate(
            synth=synth,
            packet=packet_by_root[canonical_root],
            artifact=artifact,
        )

        if schema:
            hard.append({
                "code": "CURRENT_SCHEMA_ERRORS",
                "root": canonical_root,
                "count": len(schema),
            })

        if ev["errors"]:
            hard.append({
                "code": "CURRENT_VALIDATOR_HARD_ERRORS",
                "root": canonical_root,
                "error_codes": ev["error_codes"],
            })

        if ev["changed"]:
            hard.append({
                "code": "DETERMINISTIC_REPAIR_WOULD_CHANGE_FINAL",
                "root": canonical_root,
            })

        for code in ev["warning_codes"]:
            warning_counts[code] += 1

        v7_sha = v7_rows[canonical_root].get("sha256")
        auth = authorized.get(canonical_root)

        if auth is None:
            if current_sha != v7_sha:
                hard.append({
                    "code": "UNAUTHORIZED_V7_TO_V8_ROOT_CHANGE",
                    "root": canonical_root,
                    "v7_sha256": v7_sha,
                    "v8_sha256": current_sha,
                })
        else:
            if auth.get("old_v7_sha256") != v7_sha:
                hard.append({
                    "code": "AUTHORIZED_OLD_V7_HASH_MISMATCH",
                    "root": canonical_root,
                })

            if auth.get("new_v8_sha256") != current_sha:
                hard.append({
                    "code": "AUTHORIZED_NEW_V8_HASH_MISMATCH",
                    "root": canonical_root,
                })

            backup_value = auth.get("preserved_v7_original")
            if not isinstance(backup_value, str) or not backup_value:
                hard.append({
                    "code": "PRESERVED_V7_ORIGINAL_PATH_MISSING",
                    "root": canonical_root,
                })
            else:
                backup_path = Path(backup_value)
                if not backup_path.exists():
                    hard.append({
                        "code": "PRESERVED_V7_ORIGINAL_FILE_MISSING",
                        "root": canonical_root,
                        "path": backup_value,
                    })
                else:
                    backup_sha = sha256_file(backup_path)
                    if backup_sha != v7_sha:
                        hard.append({
                            "code": "PRESERVED_V7_ORIGINAL_HASH_MISMATCH",
                            "root": canonical_root,
                            "backup_sha256": backup_sha,
                            "v7_sha256": v7_sha,
                        })
                    else:
                        v7_artifact = load_json(backup_path)
                        normalized, structural_mismatches = normalize_v8_back_to_v7(
                            v8=artifact,
                            v7=v7_artifact,
                        )
                        for item in structural_mismatches:
                            hard.append({"root": canonical_root, **item})

                        if canonical_json(normalized) != canonical_json(v7_artifact):
                            hard.append({
                                "code": "V7_TO_V8_CHANGED_CONTENT_OUTSIDE_CONTEXT_GLOSS",
                                "root": canonical_root,
                            })

        for fi, form in enumerate(artifact.get("quranic_forms") or []):
            if not isinstance(form, dict):
                continue

            public_form_id = form.get("public_form_id")

            for ei, example in enumerate(form.get("quran_examples") or []):
                if not isinstance(example, dict):
                    continue

                location = example.get("word_location")
                actual = example.get("context_gloss") or ""
                root_set = qac_root_sets.get(location, set())

                if canonical_root not in root_set:
                    hard.append({
                        "code": "QAC_ROOT_NOT_AT_EXAMPLE_LOCATION",
                        "root": canonical_root,
                        "word_location": location,
                    })
                    continue

                if len(root_set) > 1:
                    qf_checks.append({
                        "root_id": rid,
                        "root": canonical_root,
                        "public_form_id": public_form_id,
                        "form_index": fi,
                        "example_index": ei,
                        "word_location": location,
                        "status": "MULTI_ROOT_WORD_QUARANTINED",
                        "actual_context_gloss": actual,
                        "expected_qf_gloss": "",
                    })
                    continue

                qf = qf_words.get(location)
                if not isinstance(qf, dict):
                    hard.append({
                        "code": "QF_LOCATION_MISSING",
                        "root": canonical_root,
                        "word_location": location,
                    })
                    continue

                if qf.get("verse_key") != example.get("verse_key"):
                    hard.append({
                        "code": "QF_VERSE_KEY_MISMATCH",
                        "root": canonical_root,
                        "word_location": location,
                    })
                    continue

                expected = clean_gloss_display(qf.get("translation_en"))

                if expected:
                    status = "MATCH" if actual == expected else "MISMATCH"
                    qf_checks.append({
                        "root_id": rid,
                        "root": canonical_root,
                        "public_form_id": public_form_id,
                        "form_index": fi,
                        "example_index": ei,
                        "word_location": location,
                        "status": status,
                        "actual_context_gloss": actual,
                        "expected_qf_gloss": expected,
                    })
                    if actual != expected:
                        hard.append({
                            "code": "FINAL_CONTEXT_GLOSS_DOES_NOT_MATCH_QF",
                            "root": canonical_root,
                            "word_location": location,
                            "actual": actual,
                            "expected": expected,
                        })
                else:
                    status = (
                        "QF_EMPTY_BOTH_EMPTY"
                        if not actual
                        else "QF_EMPTY_CURRENT_NONEMPTY"
                    )
                    qf_checks.append({
                        "root_id": rid,
                        "root": canonical_root,
                        "public_form_id": public_form_id,
                        "form_index": fi,
                        "example_index": ei,
                        "word_location": location,
                        "status": status,
                        "actual_context_gloss": actual,
                        "expected_qf_gloss": "",
                    })
                    if actual:
                        hard.append({
                            "code": "QF_EMPTY_BUT_FINAL_GLOSS_NONEMPTY",
                            "root": canonical_root,
                            "word_location": location,
                            "actual": actual,
                        })

    missing_roots = [root for root in ordered_roots if root not in current_paths]

    if missing_roots:
        hard.append({"code": "MISSING_CANONICAL_ROOTS", "roots": missing_roots})

    if v8_payload.get("qf_source", {}).get("sha256") != qf_sha:
        hard.append({
            "code": "V8_MANIFEST_QF_SOURCE_HASH_MISMATCH",
            "manifest": v8_payload.get("qf_source", {}).get("sha256"),
            "current": qf_sha,
        })

    if v8_payload.get("qac_source", {}).get("sha256") != qac_sha:
        hard.append({
            "code": "V8_MANIFEST_QAC_SOURCE_HASH_MISMATCH",
            "manifest": v8_payload.get("qac_source", {}).get("sha256"),
            "current": qac_sha,
        })

    qf_status_counts = Counter(row["status"] for row in qf_checks)
    freeze_pass = len(hard) == 0 and len(current_paths) == EXPECTED_CANONICAL

    report = {
        "format": "quran-roots-final-freeze-audit-v3",
        "freeze_gate_pass": freeze_pass,
        "summary": {
            "canonical_root_count": len(ordered_roots),
            "final_json_count": len(final_jsons),
            "exact_internal_root_count": len(current_paths),
            "missing_root_count": len(missing_roots),
            "hard_anomaly_count": len(hard),
            "authorized_v8_changed_root_count": len(authorized),
            "unchanged_v7_to_v8_root_count": EXPECTED_CANONICAL - len(authorized),
            "qf_example_status_counts": dict(sorted(qf_status_counts.items())),
            "warning_code_root_counts": dict(sorted(
                warning_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )),
        },
        "release_constraint": {
            "prior_release": "v7",
            "current_release": "v8",
            "only_allowed_content_change":
                "$.quranic_forms[*].quran_examples[*].context_gloss",
            "qf_join_key": "exact surah:ayah:word",
            "multi_root_qac_words":
                "quarantined from whole-word QF gloss assignment",
            "qf_source_sha256": qf_sha,
            "qac_source_sha256": qac_sha,
        },
        "hard_anomalies": hard,
        "review_anomalies": [],
    }

    manifest = {
        "format": "quran-roots-final-freeze-manifest-v3",
        "freeze_gate_pass": freeze_pass,
        "canonical_root_count": len(ordered_roots),
        "final_root_count": len(current_paths),
        "v8_manifest": str(v8_manifest_path),
        "v7_manifest": str(v7_manifest_path),
        "qf_source_sha256": qf_sha,
        "qac_source_sha256": qac_sha,
        "roots": [
            {
                "root_id": root_id[root],
                "root": root,
                "filename": current_paths[root].name,
                "sha256": sha256_file(current_paths[root]),
                "release_provenance":
                    "qf_context_rejoin_v8"
                    if root in authorized
                    else "numbered_v7_unchanged",
            }
            for root in ordered_roots
            if root in current_paths
        ],
    }

    write_json(output_dir / "report.json", report)
    write_json(output_dir / "manifest.json", manifest)
    write_json(
        output_dir / "anomalies.json",
        {
            "format": "quran-roots-final-freeze-anomalies-v3",
            "hard_anomalies": hard,
            "review_anomalies": [],
        },
    )
    write_csv(
        output_dir / "qf_example_verification.csv",
        [
            "root_id", "root", "public_form_id", "form_index",
            "example_index", "word_location", "status",
            "actual_context_gloss", "expected_qf_gloss",
        ],
        qf_checks,
    )

    lines = [
        "=" * 108,
        "QURAN ROOTS — FINAL FREEZE AUDIT V3 (V8 QF CONTEXT ENRICHMENT)",
        "=" * 108,
        "",
        f"FREEZE GATE:                      {'PASS' if freeze_pass else 'FAIL'}",
        "",
        f"Canonical packet roots:           {len(ordered_roots)}",
        f"FINAL JSON artifacts:             {len(final_jsons)}",
        f"Exact internal roots:             {len(current_paths)}",
        f"Missing roots:                    {len(missing_roots)}",
        f"Hard anomalies:                   {len(hard)}",
        f"Authorized v8 changed roots:      {len(authorized)}",
        f"Unchanged v7→v8 roots:            {EXPECTED_CANONICAL - len(authorized)}",
        "",
        "QF EXAMPLE VERIFICATION",
        "-" * 108,
    ]

    for status, count in sorted(qf_status_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"{status:<60} {count:8}")

    lines += ["", "CURRENT VALIDATOR WARNING CODE ROOT COUNTS", "-" * 108]

    for code, count in sorted(warning_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"{code:<80} {count:8}")

    if hard:
        lines += ["", "HARD ANOMALIES", "-" * 108]
        for row in hard[:100]:
            lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))

    lines += [
        "",
        "OUTPUTS",
        "-" * 108,
        str(output_dir / "report.json"),
        str(output_dir / "manifest.json"),
        str(output_dir / "anomalies.json"),
        str(output_dir / "qf_example_verification.csv"),
    ]

    (output_dir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print((output_dir / "report.txt").read_text(encoding="utf-8"))

    return 0 if freeze_pass else 2

if __name__ == "__main__":
    raise SystemExit(main())
