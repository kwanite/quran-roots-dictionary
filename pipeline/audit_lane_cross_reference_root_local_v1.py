#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

PACKETS_FILE = (
    OUTPUT_DIR
    / "lane_complete_sense_packets_v2.json"
)

LANE_DB_FILE = (
    SCRIPT_DIR
    / "sources"
    / "lane"
    / "lexicon.sqlite"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "lane_cross_reference_root_local_audit_v1.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "lane_cross_reference_root_local_audit_sample_v1.json"
)


SAMPLE_ROOTS = [
    "Aty",
    "ktb",
    "rHm",
    "Hqq",
    "Slw",
]


# ============================================================
# Helpers
# ============================================================

def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def write_json(
    path: Path,
    payload: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def fetch_targets(
    conn: sqlite3.Connection,
    node_ids: list[str],
) -> dict[str, list[dict]]:
    result = defaultdict(
        list
    )

    chunk_size = 500

    for start in range(
        0,
        len(
            node_ids
        ),
        chunk_size,
    ):
        chunk = node_ids[
            start:
            start + chunk_size
        ]

        if not chunk:
            continue

        placeholders = ",".join(
            "?"
            for _ in chunk
        )

        rows = conn.execute(
            f"""
            SELECT
                id,
                root,
                broot,
                word,
                bword,
                nodeid,
                bareword,
                headword,
                itype,
                page,
                file,
                supplement,
                type
            FROM entry
            WHERE nodeid IN ({placeholders})
            ORDER BY nodeid, id
            """,
            chunk,
        ).fetchall()

        for row in rows:
            result[
                str(
                    row["nodeid"]
                )
            ].append(
                {
                    "entry_id":
                        int(
                            row["id"]
                        ),

                    "root_id":
                        row["root"],

                    "root_buckwalter":
                        row["broot"],

                    "word":
                        row["word"],

                    "buckwalter_word":
                        row["bword"],

                    "node_id":
                        row["nodeid"],

                    "bareword":
                        row["bareword"],

                    "headword":
                        row["headword"],

                    "itype":
                        row["itype"],

                    "page":
                        row["page"],

                    "file":
                        row["file"],

                    "supplement":
                        row["supplement"],

                    "entry_type":
                        row["type"],
                }
            )

    return dict(
        result
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        PACKETS_FILE,
        LANE_DB_FILE,
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing required input:\n{path}"
            )

    print(
        "Loading complete Lane packets v2..."
    )

    payload = load_json(
        PACKETS_FILE
    )

    packets = payload.get(
        "packets",
        []
    )

    root_to_entry_ids: dict[
        str,
        set[int],
    ] = defaultdict(
        set
    )

    all_packet_entry_ids = set()

    references = []

    for packet in packets:
        root_id = packet.get(
            "root"
        )

        for entry in packet.get(
            "entries",
            []
        ):
            entry_id = int(
                entry[
                    "entry_id"
                ]
            )

            root_to_entry_ids[
                root_id
            ].add(
                entry_id
            )

            all_packet_entry_ids.add(
                entry_id
            )

            for index, ref in enumerate(
                (
                    entry.get(
                        "parser_hints",
                        {}
                    ).get(
                        "cross_references",
                        []
                    )
                    or []
                )
            ):
                references.append(
                    {
                        "source_root":
                            root_id,

                        "source_entry_id":
                            entry_id,

                        "source_headword":
                            entry.get(
                                "headword"
                            ),

                        "reference_index":
                            index,

                        "target_text":
                            ref.get(
                                "target"
                            ),

                        "select":
                            ref.get(
                                "select"
                            ),

                        "type":
                            ref.get(
                                "type"
                            ),

                        "subtype":
                            ref.get(
                                "subtype"
                            ),
                    }
                )

    node_ids = sorted(
        {
            str(
                ref[
                    "select"
                ]
            )
            for ref in references
            if ref.get(
                "select"
            )
        }
    )

    print(
        f"References: {len(references):,}"
    )

    print(
        f"Unique node locators: {len(node_ids):,}"
    )

    conn = sqlite3.connect(
        str(
            LANE_DB_FILE
        )
    )

    conn.row_factory = sqlite3.Row

    try:
        targets_by_node = fetch_targets(
            conn,
            node_ids,
        )
    finally:
        conn.close()

    status_counts = Counter()

    audited = []

    supplemental_pairs = set()
    supplemental_outside_global_pairs = set()
    supplemental_other_root_pairs = set()

    for ref in references:
        item = dict(
            ref
        )

        source_root = ref[
            "source_root"
        ]

        select = ref.get(
            "select"
        )

        if not select:
            item[
                "resolution_status"
            ] = (
                "reference_without_node_locator"
            )

            item[
                "targets"
            ] = []

            status_counts[
                item[
                    "resolution_status"
                ]
            ] += 1

            audited.append(
                item
            )

            continue

        targets = targets_by_node.get(
            str(
                select
            ),
            [],
        )

        if not targets:
            item[
                "resolution_status"
            ] = (
                "node_locator_not_found_in_full_db"
            )

            item[
                "targets"
            ] = []

            status_counts[
                item[
                    "resolution_status"
                ]
            ] += 1

            audited.append(
                item
            )

            continue

        classified_targets = []

        for target in targets:
            target_id = int(
                target[
                    "entry_id"
                ]
            )

            target_item = dict(
                target
            )

            if (
                target_id
                in root_to_entry_ids[
                    source_root
                ]
            ):
                relation = (
                    "already_attached_to_same_qac_root"
                )

            elif (
                target_id
                in all_packet_entry_ids
            ):
                relation = (
                    "packetized_elsewhere_but_not_under_source_root"
                )

                supplemental_pairs.add(
                    (
                        source_root,
                        target_id,
                    )
                )

                supplemental_other_root_pairs.add(
                    (
                        source_root,
                        target_id,
                    )
                )

            else:
                relation = (
                    "outside_quran_root_packet_universe"
                )

                supplemental_pairs.add(
                    (
                        source_root,
                        target_id,
                    )
                )

                supplemental_outside_global_pairs.add(
                    (
                        source_root,
                        target_id,
                    )
                )

            target_item[
                "relation_to_source_root"
            ] = relation

            classified_targets.append(
                target_item
            )

        relations = {
            target[
                "relation_to_source_root"
            ]
            for target in classified_targets
        }

        if relations == {
            "already_attached_to_same_qac_root"
        }:
            status = (
                "resolved_same_root"
            )

        elif relations == {
            "packetized_elsewhere_but_not_under_source_root"
        }:
            status = (
                "resolved_other_quran_root_only"
            )

        elif relations == {
            "outside_quran_root_packet_universe"
        }:
            status = (
                "resolved_outside_quran_root_universe"
            )

        else:
            status = (
                "resolved_mixed_targets"
            )

        item[
            "resolution_status"
        ] = status

        item[
            "targets"
        ] = classified_targets

        status_counts[
            status
        ] += 1

        audited.append(
            item
        )

    roots_needing_supplement = defaultdict(
        set
    )

    for source_root, entry_id in (
        supplemental_pairs
    ):
        roots_needing_supplement[
            source_root
        ].add(
            entry_id
        )

    supplement_manifest = [
        {
            "root":
                root_id,

            "supplemental_target_entry_count":
                len(
                    entry_ids
                ),

            "supplemental_target_entry_ids":
                sorted(
                    entry_ids
                ),
        }
        for root_id, entry_ids
        in sorted(
            roots_needing_supplement.items()
        )
    ]

    summary = {
        "packet_count":
            len(
                packets
            ),

        "qac_roots_with_lane_packets":
            len(
                root_to_entry_ids
            ),

        "cross_reference_count":
            len(
                references
            ),

        "unique_node_locator_count":
            len(
                node_ids
            ),

        "resolution_status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),

        "unique_root_target_pairs_needing_supplement":
            len(
                supplemental_pairs
            ),

        "unique_root_target_pairs_packetized_under_other_qac_root":
            len(
                supplemental_other_root_pairs
            ),

        "unique_root_target_pairs_outside_quran_root_packet_universe":
            len(
                supplemental_outside_global_pairs
            ),

        "qac_roots_needing_cross_reference_supplement":
            len(
                roots_needing_supplement
            ),
    }

    report = {
        "metadata": {
            "dataset":
                (
                    "Root-local Lane cross-reference coverage audit"
                ),

            "version":
                1,

            "source":
                str(
                    PACKETS_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "purpose":
                (
                    "Determine whether each Lane cross-reference target "
                    "is actually available inside the SAME QAC-root "
                    "sense-extraction context. A target can be globally "
                    "packetized yet still be absent from the source "
                    "root's packets."
                ),

            "policy": [
                (
                    "No target is imported or assigned as a direct root "
                    "entry by this audit."
                ),
                (
                    "Targets absent from the source root are candidates "
                    "for supplemental cross-reference context only."
                ),
                (
                    "Source-root membership and cross-reference context "
                    "must remain distinct in later sense extraction."
                ),
            ],
        },

        "summary":
            summary,

        "supplement_manifest":
            supplement_manifest,

        "unresolved_node_locators": [
            item
            for item in audited
            if (
                item[
                    "resolution_status"
                ]
                == "node_locator_not_found_in_full_db"
            )
        ],
    }

    write_json(
        REPORT_FILE,
        report,
    )

    sample_refs = [
        item
        for item in audited
        if item[
            "source_root"
        ] in SAMPLE_ROOTS
    ]

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review root-local Lane cross-reference coverage "
                    "for representative roots"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "summary": {
            "reference_count":
                len(
                    sample_refs
                ),

            "status_counts":
                dict(
                    sorted(
                        Counter(
                            item[
                                "resolution_status"
                            ]
                            for item in sample_refs
                        ).items()
                    )
                ),

            "sample_root_supplement_counts": {
                root_id:
                    len(
                        roots_needing_supplement.get(
                            root_id,
                            set(),
                        )
                    )
                for root_id in SAMPLE_ROOTS
            },
        },

        "references_needing_supplement": [
            item
            for item in sample_refs
            if item[
                "resolution_status"
            ] in {
                "resolved_other_quran_root_only",
                "resolved_outside_quran_root_universe",
                "resolved_mixed_targets",
            }
        ],
    }

    write_json(
        SAMPLE_FILE,
        sample,
    )

    print()
    print("=" * 70)
    print(
        "ROOT-LOCAL LANE CROSS-REFERENCE AUDIT COMPLETE"
    )
    print("=" * 70)

    print(
        f"Cross references:                         "
        f"{len(references):,}"
    )

    print(
        f"Roots needing supplemental target text:   "
        f"{len(roots_needing_supplement):,}"
    )

    print(
        f"Unique root-target supplements needed:    "
        f"{len(supplemental_pairs):,}"
    )

    print(
        f"Targets packetized under another root:    "
        f"{len(supplemental_other_root_pairs):,}"
    )

    print(
        f"Targets outside Quran-root packet set:    "
        f"{len(supplemental_outside_global_pairs):,}"
    )

    print()
    print(
        "Status counts:"
    )

    for status, count in sorted(
        status_counts.items()
    ):
        print(
            f"  {status:<42} {count:,}"
        )

    print()
    print(
        "Report:\n"
        f"{REPORT_FILE}"
    )

    print()
    print(
        "Sample:\n"
        f"{SAMPLE_FILE}"
    )

    print()
    print(
        "NEXT ACTION: upload "
        "lane_cross_reference_root_local_audit_v1.json "
        "and lane_cross_reference_root_local_audit_sample_v1.json."
    )


if __name__ == "__main__":
    main()
