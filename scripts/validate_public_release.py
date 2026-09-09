#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXPECTED_ROOTS = 1642
ROOT_FILE_RE = re.compile(r"^(?P<id>\d{4})_(?P<root>.+)\.json$")

def contains_key(value, key):
    if isinstance(value, dict):
        if key in value:
            return True
        return any(contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(contains_key(v, key) for v in value)
    return False

def fail(errors, message):
    errors.append(message)

def main():
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / "data"
    roots_dir = data_dir / "roots"
    index_path = data_dir / "root-index.json"
    manifest_path = data_dir / "manifest.json"

    errors = []

    required_publication_files = [
        repo / "LICENSE",
        repo / "LICENSE_SCOPE.md",
        repo / "NOTICE",
        repo / "THIRD_PARTY_NOTICES.md",
        repo / "data" / "DATA_LICENSE.md",
        repo / "docs" / "LICENSING.md",
    ]
    for required_path in required_publication_files:
        if not required_path.is_file():
            fail(errors, f"Missing publication/license file: {required_path.relative_to(repo)}")

    if (repo / "LICENSE_PENDING.md").exists():
        fail(errors, "LICENSE_PENDING.md still exists; licensing was not finalized")
    if (repo / "STARTER_CONTENTS.txt").exists():
        fail(errors, "STARTER_CONTENTS.txt is a staging artifact and should not be public")

    files = sorted(roots_dir.glob("*.json")) if roots_dir.exists() else []
    if len(files) != EXPECTED_ROOTS:
        fail(errors, f"Expected {EXPECTED_ROOTS} root files, found {len(files)}")

    ids = set()
    roots = set()
    expected_ids = {f"{i:04d}" for i in range(1, EXPECTED_ROOTS + 1)}
    file_records = {}

    for path in files:
        m = ROOT_FILE_RE.match(path.name)
        if not m:
            fail(errors, f"Invalid filename: {path.name}")
            continue

        root_id = m.group("id")
        filename_root = m.group("root")

        if root_id in ids:
            fail(errors, f"Duplicate root ID: {root_id}")
        ids.add(root_id)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(errors, f"{path.name}: invalid JSON: {exc}")
            continue

        exact_root = data.get("root")
        if exact_root != filename_root:
            fail(errors, f"{path.name}: filename root != JSON root")
        if exact_root in roots:
            fail(errors, f"{path.name}: duplicate exact root {exact_root!r}")
        roots.add(exact_root)

        for required in ("root", "arabic", "root_idea", "quranic_forms"):
            if required not in data:
                fail(errors, f"{path.name}: missing required field {required}")

        if contains_key(data, "context_gloss"):
            fail(errors, f"{path.name}: context_gloss survived public transformation")

        forms = data.get("quranic_forms")
        if not isinstance(forms, list):
            fail(errors, f"{path.name}: quranic_forms must be a list")
            forms = []

        form_ids = set()
        for form in forms:
            if not isinstance(form, dict):
                fail(errors, f"{path.name}: quranic form is not an object")
                continue

            public_form_id = form.get("public_form_id")
            if not isinstance(public_form_id, str) or not public_form_id:
                fail(errors, f"{path.name}: missing/invalid public_form_id")
            elif public_form_id in form_ids:
                fail(errors, f"{path.name}: duplicate public_form_id {public_form_id}")
            else:
                form_ids.add(public_form_id)

            sense_ids = set()
            senses = form.get("senses") or []
            if not isinstance(senses, list):
                fail(errors, f"{path.name}/{public_form_id}: senses must be a list")
                senses = []

            for sense in senses:
                if not isinstance(sense, dict):
                    continue
                sid = sense.get("sense_id")
                if not isinstance(sid, str) or not sid:
                    fail(errors, f"{path.name}/{public_form_id}: missing sense_id")
                elif sid in sense_ids:
                    fail(errors, f"{path.name}/{public_form_id}: duplicate sense_id {sid}")
                else:
                    sense_ids.add(sid)

            examples = form.get("quran_examples") or []
            if not isinstance(examples, list):
                fail(errors, f"{path.name}/{public_form_id}: quran_examples must be a list")
                examples = []

            for ex in examples:
                if not isinstance(ex, dict):
                    continue
                for sid in ex.get("sense_ids") or []:
                    if sid not in sense_ids:
                        fail(
                            errors,
                            f"{path.name}/{public_form_id}: Quran example references "
                            f"unknown sense_id {sid}",
                        )

        file_records[root_id] = {
            "root_id": root_id,
            "root": exact_root,
            "file": path.name,
        }

    if ids != expected_ids:
        fail(
            errors,
            f"ID set mismatch: missing={sorted(expected_ids - ids)} "
            f"extra={sorted(ids - expected_ids)}",
        )

    if not index_path.is_file():
        fail(errors, "Missing data/root-index.json")
    else:
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if index.get("root_count") != EXPECTED_ROOTS:
                fail(errors, "root-index.json root_count mismatch")
            by_id = index.get("by_id") or {}
            if set(by_id) != expected_ids:
                fail(errors, "root-index.json by_id key set mismatch")
            for root_id, rec in file_records.items():
                idx = by_id.get(root_id) or {}
                if idx.get("file") != rec["file"] or idx.get("root") != rec["root"]:
                    fail(errors, f"root-index mismatch for {root_id}")
        except Exception as exc:
            fail(errors, f"Invalid root-index.json: {exc}")

    if not manifest_path.is_file():
        fail(errors, "Missing data/manifest.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("root_count") != EXPECTED_ROOTS:
                fail(errors, "manifest root_count mismatch")
            if manifest.get("complete") is not True:
                fail(errors, "manifest complete must be true")
        except Exception as exc:
            fail(errors, f"Invalid manifest.json: {exc}")

    if errors:
        print("PUBLIC RELEASE VALIDATION: FAIL")
        for err in errors:
            print(f"- {err}")
        sys.exit(1)

    print("PUBLIC RELEASE VALIDATION: PASS")
    print(f"Roots: {EXPECTED_ROOTS}")
    print("No context_gloss fields present.")
    print("Root IDs, exact roots, index, basic semantic references, and licensing files are consistent.")

if __name__ == "__main__":
    main()
