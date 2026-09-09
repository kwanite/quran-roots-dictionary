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
    / "lane_cross_reference_target_audit_v1.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "lane_cross_reference_target_audit_sample_v1.json"
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


def fetch_db_targets(
    conn: sqlite3.Connection,
    node_ids: list[str],
) -> dict[str, list[dict]]:
    """
    Query the FULL Lane entry table by nodeid.

    We preserve all rows because nodeid is demonstrably not globally unique.
    """
    result: dict[
        str,
        list[dict],
    ] = defaultdict(
        list
    )

    if not node_ids:
        return {}

    # Stay well below SQLite's variable limit.
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
                    row[
                        "nodeid"
                    ]
                )
            ].append(
                {
                    "entry_id":
                        int(
                            row[
                                "id"
                            ]
                        ),

                    "root_id":
                        row[
                            "root"
                        ],

                    "root_buckwalter":
                        row[
                            "broot"
                        ],

                    "word":
                        row[
                            "word"
                        ],

                    "buckwalter_word":
                        row[
                            "bword"
                        ],

                    "node_id":
                        row[
                            "nodeid"
                        ],

                    "bareword":
                        row[
                            "bareword"
                        ],

                    "headword":
                        row[
                            "headword"
                        ],

                    "itype":
                        row[
                            "itype"
                        ],

                    "page":
                        row[
                            "page"
                        ],

                    "file":
                        row[
                            "file"
                        ],

                    "supplement":
                        row[
                            "supplement"
                        ],

                    "entry_type":
                        row[
                            "type"
                        ],
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

    # All Lane entry IDs already attached to Quran roots.
    packet_entry_ids = {
        int(
            entry[
                "entry_id"
            ]
        )
        for packet in packets
        for entry in packet.get(
            "entries",
            []
        )
    }

    refs = []

    refs_without_locator = []
    refs_with_locator = []

    for packet in packets:
        root_id = packet.get(
            "root"
        )

        for entry in packet.get(
            "entries",
            []
        ):
            source_entry_id = int(
                entry[
                    "entry_id"
                ]
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
                record = {
                    "source_root":
                        root_id,

                    "source_entry_id":
                        source_entry_id,

                    "source_headword":
                        entry.get(
                            "headword"
                        ),

                    "reference_index":
                        index,

                    "reference_text":
                        ref.get(
                            "text"
                        ),

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

                    "packet_resolution_status":
                        ref.get(
                            "resolution_status"
                        ),

                    "packet_resolved_targets":
                        ref.get(
                            "resolved_targets",
                            []
                        ),
                }

                refs.append(
                    record
                )

                if record[
                    "select"
                ]:
                    refs_with_locator.append(
                        record
                    )
                else:
                    refs_without_locator.append(
                        record
                    )

    unique_selects = sorted(
        {
            str(
                ref[
                    "select"
                ]
            )
            for ref in refs_with_locator
        }
    )

    print(
        f"Cross references: {len(refs):,}"
    )

    print(
        f"With node locator: {len(refs_with_locator):,}"
    )

    print(
        f"Without locator: {len(refs_without_locator):,}"
    )

    print(
        "Querying full Lane DB for all referenced node IDs..."
    )

    conn = sqlite3.connect(
        str(
            LANE_DB_FILE
        )
    )

    conn.row_factory = sqlite3.Row

    try:
        db_targets = fetch_db_targets(
            conn,
            unique_selects,
        )
    finally:
        conn.close()

    status_counts = Counter()

    external_target_entry_ids = set()

    audited_refs = []

    for record in refs:
        select = record.get(
            "select"
        )

        item = dict(
            record
        )

        if not select:
            # These may be word/form references in Lane markup but they
            # cannot be followed to an entry node deterministically.
            status = (
                "reference_without_node_locator"
            )

            item[
                "full_db_targets"
            ] = []

        else:
            targets = db_targets.get(
                str(
                    select
                ),
                [],
            )

            item[
                "full_db_targets"
            ] = targets

            if not targets:
                status = (
                    "node_locator_not_found_in_full_db"
                )

            else:
                target_ids = {
                    int(
                        target[
                            "entry_id"
                        ]
                    )
                    for target in targets
                }

                external_ids = (
                    target_ids
                    - packet_entry_ids
                )

                for entry_id in external_ids:
                    external_target_entry_ids.add(
                        entry_id
                    )

                if external_ids:
                    if len(
                        targets
                    ) == 1:
                        status = (
                            "resolved_external_unique"
                        )
                    else:
                        status = (
                            "resolved_external_multiple"
                        )

                else:
                    if len(
                        targets
                    ) == 1:
                        status = (
                            "resolved_already_packetized_unique"
                        )
                    else:
                        status = (
                            "resolved_already_packetized_multiple"
                        )

        item[
            "full_db_resolution_status"
        ] = status

        status_counts[
            status
        ] += 1

        audited_refs.append(
            item
        )

    unique_external_targets = {}

    for ref in audited_refs:
        for target in ref.get(
            "full_db_targets",
            []
        ):
            entry_id = int(
                target[
                    "entry_id"
                ]
            )

            if (
                entry_id
                not in packet_entry_ids
            ):
                unique_external_targets[
                    entry_id
                ] = target

    # Which Quran-root source entries depend on at least one external
    # cross-reference target?
    source_entries_with_external_refs = {
        (
            ref[
                "source_root"
            ],
            ref[
                "source_entry_id"
            ],
        )
        for ref in audited_refs
        if (
            ref[
                "full_db_resolution_status"
            ].startswith(
                "resolved_external_"
            )
        )
    }

    summary = {
        "packet_count":
            len(
                packets
            ),

        "packetized_lane_entry_id_count":
            len(
                packet_entry_ids
            ),

        "cross_reference_count":
            len(
                refs
            ),

        "reference_without_node_locator_count":
            len(
                refs_without_locator
            ),

        "reference_with_node_locator_count":
            len(
                refs_with_locator
            ),

        "unique_node_locator_count":
            len(
                unique_selects
            ),

        "full_db_resolution_status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),

        "unique_external_target_entry_count":
            len(
                unique_external_targets
            ),

        "quran_root_lane_entries_with_external_target_refs":
            len(
                source_entries_with_external_refs
            ),
    }

    report = {
        "metadata": {
            "dataset":
                (
                    "Audit of Lane cross-reference targets against "
                    "the full Lane SQLite entry table"
                ),

            "version":
                1,

            "packet_source":
                str(
                    PACKETS_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "lane_database":
                str(
                    LANE_DB_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "purpose":
                (
                    "Determine whether cross-references from Quran-root "
                    "Lane entries point to relevant Lane entries that "
                    "are outside the current 25,940-entry Quran-root "
                    "attachment set."
                ),

            "policy": [
                (
                    "A cross-reference without a node locator is not "
                    "counted as a failed node resolution."
                ),
                (
                    "Node IDs are treated as one-to-many."
                ),
                (
                    "No external target is automatically imported or "
                    "assigned to a Quran root in this audit."
                ),
            ],
        },

        "summary":
            summary,

        "external_target_entries": [
            unique_external_targets[
                entry_id
            ]
            for entry_id in sorted(
                unique_external_targets
            )
        ],

        "references_with_locator_not_found_in_full_db": [
            ref
            for ref in audited_refs
            if (
                ref[
                    "full_db_resolution_status"
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
        ref
        for ref in audited_refs
        if ref[
            "source_root"
        ] in SAMPLE_ROOTS
    ]

    sample_output = {
        "metadata": {
            "purpose":
                (
                    "Review full-DB cross-reference behavior for "
                    "representative Quran roots"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "summary": {
            "sample_reference_count":
                len(
                    sample_refs
                ),

            "status_counts":
                dict(
                    sorted(
                        Counter(
                            ref[
                                "full_db_resolution_status"
                            ]
                            for ref in sample_refs
                        ).items()
                    )
                ),
        },

        "references":
            sample_refs,
    }

    write_json(
        SAMPLE_FILE,
        sample_output,
    )

    print()
    print("=" * 68)
    print(
        "LANE CROSS-REFERENCE TARGET AUDIT COMPLETE"
    )
    print("=" * 68)

    for key, value in summary.items():
        if isinstance(
            value,
            dict,
        ):
            continue

        print(
            f"{key}: {value:,}"
            if isinstance(
                value,
                int,
            )
            else f"{key}: {value}"
        )

    print()
    print(
        "Status counts:"
    )

    for status, count in sorted(
        status_counts.items()
    ):
        print(
            f"  {status:<38} {count:,}"
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
        "lane_cross_reference_target_audit_v1.json "
        "and lane_cross_reference_target_audit_sample_v1.json."
    )


if __name__ == "__main__":
    main()
