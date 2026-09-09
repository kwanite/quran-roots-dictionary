#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

QAC_ROOT_INDEX_FILE = (
    SCRIPT_DIR
    / "quran_roots_index.json"
)

MUFRADAT_AUDIT_FILE = (
    OUTPUT_DIR
    / "mufradat_quran_match_audit_v3.json"
)

DB_FILE = (
    SCRIPT_DIR
    / "sources"
    / "arabic-lexicons"
    / "db.sqlite"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "mufradat_quran_semantics_v1.json"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "mufradat_extraction_report_v1.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "mufradat_semantics_sample_v1.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "qwl",
    "qyl",
    "Aty",
    "Amn",
    "ydy",
    "ndw",
    "smw",

    # Composite / ambiguity-review cases.
    "Abw",
    "Aby",
    "zwd",
    "zyd",
    "Slw",
    "Sly",
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


def qac_root_lookup(
    payload: dict,
) -> dict[str, dict]:
    roots = payload.get(
        "roots",
        []
    )

    return {
        root["root"]:
            root
        for root in roots
    }


def audit_root_lookup(
    payload: dict,
) -> dict[str, dict]:
    roots = payload.get(
        "roots",
        []
    )

    lookup = {}

    for record in roots:
        root_id = record.get(
            "qac_root"
        )

        if not root_id:
            continue

        if root_id in lookup:
            raise RuntimeError(
                "Duplicate root in Mufradat audit: "
                f"{root_id}"
            )

        lookup[
            root_id
        ] = record

    return lookup


def fetch_rows_by_ids(
    conn: sqlite3.Connection,
    ids: list[int],
) -> dict[int, dict]:
    if not ids:
        return {}

    unique_ids = sorted(
        set(
            int(value)
            for value in ids
        )
    )

    placeholders = ",".join(
        "?"
        for _ in unique_ids
    )

    rows = conn.execute(
        f"""
        SELECT
            id,
            word,
            meanings
        FROM mufradat_alfajul_quran
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        unique_ids,
    ).fetchall()

    return {
        int(row["id"]): {
            "id":
                int(row["id"]),

            "word":
                row["word"],

            "meanings":
                row["meanings"],
        }
        for row in rows
    }


def split_top_level_pipe_segments(
    text: str | None,
) -> list[str]:
    """
    Split the bundled Mufradat text on | separators, but do NOT split
    inside editorial [[ ... ]] notes.

    The exact source remains preserved separately in arabic_text_raw.
    This function only creates a convenience view.

    Example shape in the source:

        main text | next section [[note part 1 | note part 2]] | next

    A naive text.split("|") would incorrectly fragment the note.
    """
    if not text:
        return []

    segments = []
    current = []
    bracket_depth = 0
    i = 0

    while i < len(
        text
    ):
        pair = text[
            i:i + 2
        ]

        if pair == "[[":
            bracket_depth += 1
            current.append(
                pair
            )
            i += 2
            continue

        if (
            pair == "]]"
            and bracket_depth > 0
        ):
            bracket_depth -= 1
            current.append(
                pair
            )
            i += 2
            continue

        char = text[
            i
        ]

        if (
            char == "|"
            and bracket_depth == 0
        ):
            segment = "".join(
                current
            ).strip()

            if segment:
                segments.append(
                    segment
                )

            current = []
            i += 1
            continue

        current.append(
            char
        )
        i += 1

    final = "".join(
        current
    ).strip()

    if final:
        segments.append(
            final
        )

    return segments


def compact_qac_summary(
    root: dict,
) -> dict:
    return {
        "root":
            root.get(
                "root"
            ),

        "arabic":
            root.get(
                "arabic"
            ),

        "arabic_spaced":
            root.get(
                "arabic_spaced"
            ),

        "radicals":
            root.get(
                "radicals",
                []
            ),

        "occurrence_count":
            root.get(
                "occurrence_count"
            ),

        "word_count":
            root.get(
                "word_count"
            ),

        "surah_count":
            root.get(
                "surah_count"
            ),

        "pos_counts":
            root.get(
                "pos_counts",
                {}
            ),

        "lemma_count":
            root.get(
                "lemma_count"
            ),

        "lemmas":
            root.get(
                "lemmas",
                []
            ),
    }


def build_source_entry(
    source_row: dict,
    match_record: dict,
    assignment_type: str,
) -> dict:
    text = (
        source_row.get(
            "meanings"
        )
        or ""
    )

    result = {
        "source":
            "mufradat_alfaz_al_quran",

        "table":
            "mufradat_alfajul_quran",

        "row_id":
            source_row[
                "id"
            ],

        "heading":
            source_row.get(
                "word"
            ),

        # Preserve exact DB text.
        "arabic_text_raw":
            text,

        # Convenience segmentation only.
        "source_segments":
            split_top_level_pipe_segments(
                text
            ),

        "assignment_type":
            assignment_type,

        "matching_evidence":
            match_record.get(
                "evidence",
                []
            ),

        "best_method":
            match_record.get(
                "best_method"
            ),

        "best_rank":
            match_record.get(
                "best_rank"
            ),
    }

    if assignment_type == "unique":
        result[
            "assignment_resolution"
        ] = match_record.get(
            "assignment_resolution"
        )

        competing = match_record.get(
            "competing_qac_root_ranks"
        )

        if competing:
            result[
                "competing_qac_root_ranks"
            ] = competing

    else:
        result[
            "candidate_qac_roots"
        ] = match_record.get(
            "candidate_qac_roots",
            []
        )

        result[
            "candidate_qac_root_ranks"
        ] = match_record.get(
            "candidate_qac_root_ranks",
            {}
        )

        result[
            "semantic_use_policy"
        ] = (
            "Preserved as shared/composite source evidence. "
            "Do not treat the full row as uniquely belonging "
            "to this root without further segmentation or review."
        )

    return result


# ============================================================
# Main
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    required = [
        QAC_ROOT_INDEX_FILE,
        MUFRADAT_AUDIT_FILE,
        DB_FILE,
    ]

    missing = [
        path
        for path in required
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required input(s):\n"
            + "\n".join(
                str(path)
                for path in missing
            )
        )

    qac_payload = load_json(
        QAC_ROOT_INDEX_FILE
    )

    audit_payload = load_json(
        MUFRADAT_AUDIT_FILE
    )

    qac_by_root = qac_root_lookup(
        qac_payload
    )

    audit_by_root = audit_root_lookup(
        audit_payload
    )

    if set(
        qac_by_root
    ) != set(
        audit_by_root
    ):
        missing_in_audit = sorted(
            set(
                qac_by_root
            )
            - set(
                audit_by_root
            )
        )

        extra_in_audit = sorted(
            set(
                audit_by_root
            )
            - set(
                qac_by_root
            )
        )

        raise RuntimeError(
            "QAC/audit root inventory mismatch.\n"
            f"Missing in audit: {missing_in_audit[:30]}\n"
            f"Extra in audit: {extra_in_audit[:30]}"
        )

    all_referenced_row_ids = []

    for record in audit_by_root.values():
        for entry in record.get(
            "matched_entries",
            []
        ):
            all_referenced_row_ids.append(
                int(
                    entry[
                        "row_id"
                    ]
                )
            )

        for entry in record.get(
            "ambiguous_entries",
            []
        ):
            all_referenced_row_ids.append(
                int(
                    entry[
                        "row_id"
                    ]
                )
            )

    distinct_referenced_row_ids = sorted(
        set(
            all_referenced_row_ids
        )
    )

    conn = sqlite3.connect(
        str(
            DB_FILE
        )
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        source_by_id = (
            fetch_rows_by_ids(
                conn,
                distinct_referenced_row_ids,
            )
        )
    finally:
        conn.close()

    missing_source_row_ids = sorted(
        set(
            distinct_referenced_row_ids
        )
        - set(
            source_by_id
        )
    )

    if missing_source_row_ids:
        raise RuntimeError(
            "Referenced Mufradat rows missing from DB: "
            + ", ".join(
                str(value)
                for value
                in missing_source_row_ids[:50]
            )
        )

    roots_output = []

    status_counts = Counter()
    unique_assignment_method_counts = Counter()

    unique_attachment_count = 0
    shared_attachment_count = 0

    unique_source_row_ids = set()
    shared_source_row_ids = set()

    heading_mismatches = []
    empty_meanings = []

    for root_id in sorted(
        qac_by_root
    ):
        qac_root = qac_by_root[
            root_id
        ]

        audit_record = (
            audit_by_root[
                root_id
            ]
        )

        status = audit_record.get(
            "status"
        )

        status_counts[
            status
        ] += 1

        unique_entries = []

        for match in audit_record.get(
            "matched_entries",
            []
        ):
            row_id = int(
                match[
                    "row_id"
                ]
            )

            source_row = source_by_id[
                row_id
            ]

            if (
                match.get(
                    "heading"
                )
                != source_row.get(
                    "word"
                )
            ):
                heading_mismatches.append(
                    {
                        "qac_root":
                            root_id,

                        "row_id":
                            row_id,

                        "audit_heading":
                            match.get(
                                "heading"
                            ),

                        "database_heading":
                            source_row.get(
                                "word"
                            ),
                    }
                )

            if not (
                source_row.get(
                    "meanings"
                )
                or ""
            ).strip():
                empty_meanings.append(
                    {
                        "qac_root":
                            root_id,

                        "row_id":
                            row_id,
                    }
                )

            unique_entry = (
                build_source_entry(
                    source_row,
                    match,
                    "unique",
                )
            )

            unique_entries.append(
                unique_entry
            )

            unique_attachment_count += 1
            unique_source_row_ids.add(
                row_id
            )

            method = match.get(
                "best_method"
            )

            if method:
                unique_assignment_method_counts[
                    method
                ] += 1

        shared_entries = []

        for match in audit_record.get(
            "ambiguous_entries",
            []
        ):
            row_id = int(
                match[
                    "row_id"
                ]
            )

            source_row = source_by_id[
                row_id
            ]

            if (
                match.get(
                    "heading"
                )
                != source_row.get(
                    "word"
                )
            ):
                heading_mismatches.append(
                    {
                        "qac_root":
                            root_id,

                        "row_id":
                            row_id,

                        "audit_heading":
                            match.get(
                                "heading"
                            ),

                        "database_heading":
                            source_row.get(
                                "word"
                            ),
                    }
                )

            if not (
                source_row.get(
                    "meanings"
                )
                or ""
            ).strip():
                empty_meanings.append(
                    {
                        "qac_root":
                            root_id,

                        "row_id":
                            row_id,
                    }
                )

            shared_entry = (
                build_source_entry(
                    source_row,
                    match,
                    "shared_ambiguous",
                )
            )

            shared_entries.append(
                shared_entry
            )

            shared_attachment_count += 1
            shared_source_row_ids.add(
                row_id
            )

        roots_output.append(
            {
                "root":
                    root_id,

                "arabic":
                    qac_root.get(
                        "arabic"
                    ),

                "qac":
                    compact_qac_summary(
                        qac_root
                    ),

                "mufradat_match": {
                    "status":
                        status,

                    "unique_entry_count":
                        len(
                            unique_entries
                        ),

                    "shared_ambiguous_entry_count":
                        len(
                            shared_entries
                        ),
                },

                "mufradat": {
                    "entries":
                        unique_entries,

                    "shared_ambiguous_entries":
                        shared_entries,
                },
            }
        )

    roots_with_unique_entries = sum(
        1
        for root in roots_output
        if root[
            "mufradat_match"
        ][
            "unique_entry_count"
        ] > 0
    )

    roots_with_shared_entries = sum(
        1
        for root in roots_output
        if root[
            "mufradat_match"
        ][
            "shared_ambiguous_entry_count"
        ] > 0
    )

    roots_without_any_mufradat_evidence = sum(
        1
        for root in roots_output
        if (
            root[
                "mufradat_match"
            ][
                "unique_entry_count"
            ] == 0
            and root[
                "mufradat_match"
            ][
                "shared_ambiguous_entry_count"
            ] == 0
        )
    )

    summary = {
        "qac_root_count":
            len(
                roots_output
            ),

        "matched_qac_roots_with_unique_entries":
            roots_with_unique_entries,

        "matched_qac_root_percent":
            round(
                (
                    roots_with_unique_entries
                    / len(
                        roots_output
                    )
                    * 100
                )
                if roots_output
                else 0,
                2,
            ),

        "roots_with_shared_ambiguous_entries":
            roots_with_shared_entries,

        "roots_without_any_mufradat_evidence":
            roots_without_any_mufradat_evidence,

        "audit_status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),

        "unique_entry_attachment_count":
            unique_attachment_count,

        "distinct_unique_source_row_count":
            len(
                unique_source_row_ids
            ),

        "shared_ambiguous_entry_attachment_count":
            shared_attachment_count,

        "distinct_shared_ambiguous_source_row_count":
            len(
                shared_source_row_ids
            ),

        "distinct_source_rows_fetched":
            len(
                source_by_id
            ),

        "missing_source_row_id_count":
            len(
                missing_source_row_ids
            ),

        "heading_mismatch_count":
            len(
                heading_mismatches
            ),

        "empty_meanings_count":
            len(
                empty_meanings
            ),

        "unique_assignment_method_counts":
            dict(
                sorted(
                    unique_assignment_method_counts.items()
                )
            ),
    }

    output = {
        "metadata": {
            "dataset":
                (
                    "Al-Raghib al-Isfahani Mufradat "
                    "evidence aligned to canonical Quran roots"
                ),

            "version":
                1,

            "canonical_root_source":
                QAC_ROOT_INDEX_FILE.name,

            "match_audit_source":
                str(
                    MUFRADAT_AUDIT_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "source_database":
                str(
                    DB_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "source_table":
                "mufradat_alfajul_quran",

            "semantic_policy": [
                (
                    "QAC root IDs remain canonical."
                ),
                (
                    "Only v3 audit entries assigned uniquely "
                    "to a QAC root are stored under entries."
                ),
                (
                    "The five genuinely composite/tied source rows "
                    "remain preserved under shared_ambiguous_entries "
                    "for their candidate roots rather than being "
                    "forced to one root."
                ),
                (
                    "Arabic source text is preserved exactly in "
                    "arabic_text_raw."
                ),
                (
                    "source_segments are deterministic convenience "
                    "splits on top-level | separators only; pipes "
                    "inside [[...]] editorial notes are preserved."
                ),
                (
                    "No LLM-generated content, English translation, "
                    "or semantic paraphrase is present in this layer."
                ),
            ],
        },

        "summary":
            summary,

        "roots":
            roots_output,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    unresolved = [
        {
            "root":
                root[
                    "root"
                ],

            "arabic":
                root[
                    "arabic"
                ],

            "qac_occurrence_count":
                root[
                    "qac"
                ].get(
                    "occurrence_count"
                ),

            "status":
                root[
                    "mufradat_match"
                ][
                    "status"
                ],
        }
        for root in roots_output
        if (
            root[
                "mufradat_match"
            ][
                "unique_entry_count"
            ] == 0
        )
    ]

    unresolved.sort(
        key=lambda item: (
            -int(
                item.get(
                    "qac_occurrence_count"
                )
                or 0
            ),
            item[
                "root"
            ],
        )
    )

    report = {
        "summary":
            summary,

        "heading_mismatches":
            heading_mismatches,

        "empty_meanings":
            empty_meanings,

        "roots_without_unique_mufradat_entry":
            unresolved,

        "shared_ambiguous_source_rows": (
            audit_payload.get(
                "source_diagnostics",
                {}
            ).get(
                "ambiguous_source_rows",
                []
            )
        ),
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    root_lookup = {
        root[
            "root"
        ]:
            root
        for root in roots_output
    }

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review representative Mufradat "
                    "semantic extraction, including "
                    "shared/composite source rows"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            root_lookup[
                root_id
            ]
            for root_id in SAMPLE_ROOTS
            if root_id
            in root_lookup
        ],
    }

    SAMPLE_FILE.write_text(
        json.dumps(
            sample,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(
        "MUFRADAT SEMANTIC EXTRACTION COMPLETE"
    )
    print("=" * 60)

    print(
        f"QAC roots:                         "
        f"{len(roots_output):,}"
    )

    print(
        f"Roots with unique Mufradat entry: "
        f"{roots_with_unique_entries:,}"
    )

    print(
        f"Unique-match coverage:             "
        f"{summary['matched_qac_root_percent']:.2f}%"
    )

    print(
        f"Roots with shared entries:         "
        f"{roots_with_shared_entries:,}"
    )

    print(
        f"Unique source rows:                "
        f"{len(unique_source_row_ids):,}"
    )

    print(
        f"Shared ambiguous source rows:      "
        f"{len(shared_source_row_ids):,}"
    )

    print(
        f"Unique entry attachments:          "
        f"{unique_attachment_count:,}"
    )

    print(
        f"Shared entry attachments:          "
        f"{shared_attachment_count:,}"
    )

    print(
        f"Missing source rows:               "
        f"{len(missing_source_row_ids):,}"
    )

    print(
        f"Heading mismatches:                "
        f"{len(heading_mismatches):,}"
    )

    print(
        f"Empty meanings:                    "
        f"{len(empty_meanings):,}"
    )

    print()
    print(
        "Semantic dataset:\n"
        f"{OUTPUT_FILE}"
    )

    print()
    print(
        "Extraction report:\n"
        f"{REPORT_FILE}"
    )

    print()
    print(
        "Review sample:\n"
        f"{SAMPLE_FILE}"
    )

    print()
    print(
        "NEXT ACTION: upload "
        "mufradat_extraction_report_v1.json "
        "and mufradat_semantics_sample_v1.json."
    )


if __name__ == "__main__":
    main()
