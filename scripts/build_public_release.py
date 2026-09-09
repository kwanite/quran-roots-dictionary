#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT_FILE_RE = re.compile(r"^(?P<id>\d{4})_(?P<root>.+)\.json$")
EXPECTED_ROOTS = 1642

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def strip_publication_restricted_fields(value):
    if isinstance(value, dict):
        return {
            k: strip_publication_restricted_fields(v)
            for k, v in value.items()
            if k != "context_gloss"
        }
    if isinstance(value, list):
        return [strip_publication_restricted_fields(v) for v in value]
    return value

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-roots", type=Path, required=True)
    p.add_argument("--source-manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("data"))
    p.add_argument("--replace-generated", action="store_true")
    args = p.parse_args()

    source_roots = args.source_roots.resolve()
    source_manifest = args.source_manifest.resolve()
    out = args.output.resolve()
    roots_out = out / "roots"

    if not source_roots.is_dir():
        raise SystemExit(f"Source root directory not found: {source_roots}")
    if not source_manifest.is_file():
        raise SystemExit(f"Source manifest not found: {source_manifest}")

    source_files = sorted(source_roots.glob("*.json"))
    if len(source_files) != EXPECTED_ROOTS:
        raise SystemExit(
            f"Expected {EXPECTED_ROOTS} source root files, found {len(source_files)}"
        )

    if roots_out.exists() and any(roots_out.iterdir()):
        if not args.replace_generated:
            raise SystemExit(
                f"{roots_out} is non-empty. Re-run with --replace-generated "
                "only if you intend to replace generated PUBLIC copies."
            )
        shutil.rmtree(roots_out)

    roots_out.mkdir(parents=True, exist_ok=True)

    seen_ids = set()
    seen_roots = set()
    index_records = []
    removed_context_gloss_fields = 0

    def count_context_gloss(value):
        if isinstance(value, dict):
            return (
                (1 if "context_gloss" in value else 0)
                + sum(count_context_gloss(v) for v in value.values())
            )
        if isinstance(value, list):
            return sum(count_context_gloss(v) for v in value)
        return 0

    for source in source_files:
        match = ROOT_FILE_RE.match(source.name)
        if not match:
            raise SystemExit(f"Unexpected root filename: {source.name}")

        root_id = match.group("id")
        filename_root = match.group("root")

        if root_id in seen_ids:
            raise SystemExit(f"Duplicate root ID in filenames: {root_id}")
        seen_ids.add(root_id)

        data = json.loads(source.read_text(encoding="utf-8"))
        exact_root = data.get("root")
        if not isinstance(exact_root, str) or not exact_root:
            raise SystemExit(f"{source.name}: missing/invalid top-level root")
        if exact_root != filename_root:
            raise SystemExit(
                f"{source.name}: filename root {filename_root!r} "
                f"!= JSON root {exact_root!r}"
            )
        if exact_root in seen_roots:
            raise SystemExit(f"Duplicate exact root: {exact_root}")
        seen_roots.add(exact_root)

        removed_context_gloss_fields += count_context_gloss(data)
        public_data = strip_publication_restricted_fields(data)

        dest = roots_out / source.name
        dest.write_text(
            json.dumps(public_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        index_records.append(
            {
                "root_id": root_id,
                "root": exact_root,
                "arabic": public_data.get("arabic", ""),
                "file": source.name,
            }
        )

    expected_ids = {f"{i:04d}" for i in range(1, EXPECTED_ROOTS + 1)}
    if seen_ids != expected_ids:
        missing = sorted(expected_ids - seen_ids)
        extra = sorted(seen_ids - expected_ids)
        raise SystemExit(f"Root ID set mismatch. missing={missing} extra={extra}")

    by_id = {r["root_id"]: r for r in index_records}
    by_exact_qac_root = {r["root"]: r for r in index_records}
    root_index = {
        "root_count": EXPECTED_ROOTS,
        "root_order": [f"{i:04d}" for i in range(1, EXPECTED_ROOTS + 1)],
        "by_id": by_id,
        "by_exact_qac_root": by_exact_qac_root,
    }
    (out / "root-index.json").write_text(
        json.dumps(root_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    source_manifest_sha256 = sha256_file(source_manifest)
    manifest = {
        "release_format": "quran-roots-public-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root_count": EXPECTED_ROOTS,
        "source_corpus": "frozen numbered_roots_v8",
        "source_manifest_filename": source_manifest.name,
        "source_manifest_sha256": source_manifest_sha256,
        "publication_transform": {
            "source_files_modified": False,
            "removed_field_name": "context_gloss",
            "removed_field_count": removed_context_gloss_fields,
            "reason": (
                "Conservative public-publication boundary pending independent "
                "review of Quran Foundation redistribution rights."
            ),
        },
        "complete": True,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    checksum_paths = [out / "manifest.json", out / "root-index.json"] + sorted(roots_out.glob("*.json"))
    lines = []
    for path in checksum_paths:
        rel = path.relative_to(out.parent)
        lines.append(f"{sha256_file(path)}  {rel.as_posix()}")
    (out / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Public roots written: {len(source_files)}")
    print(f"context_gloss fields removed: {removed_context_gloss_fields}")
    print(f"Output: {out}")

if __name__ == "__main__":
    main()
