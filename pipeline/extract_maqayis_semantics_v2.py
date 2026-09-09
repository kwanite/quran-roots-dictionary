#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

QAC_ROOT_INDEX_FILE = (
    SCRIPT_DIR
    / "quran_roots_index.json"
)

MAQAYIS_AUDIT_FILE = (
    OUTPUT_DIR
    / "maqayis_root_match_audit_v2.json"
)

DB_FILE = (
    SCRIPT_DIR
    / "sources"
    / "arabic-lexicons"
    / "db.sqlite"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "maqayis_quran_semantics_v2.json"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "maqayis_extraction_report_v2.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "maqayis_semantics_sample_v2.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "qwl",
    "Aty",
    "Hqq",
    "Amn",
    "nwm",

    # Deliberately unmatched in the v2 audit.
    "ydy",
    "ndw",
]


# ============================================================
# Principle-candidate detection
# ============================================================

WHITESPACE_RE = re.compile(r"\s+")

# Sentence-ish boundaries in this digitization.
BOUNDARY_RE = re.compile(
    r"(?<=[\.\!\؟\؛])\s+|\|+"
)

# Arabic combining marks / Quranic marks. Detection is performed on
# a normalized copy only; original source text is always preserved.
ARABIC_MARK_RE = re.compile(
    r"[\u0610-\u061A"
    r"\u064B-\u065F"
    r"\u0670"
    r"\u06D6-\u06ED]"
)

PRINCIPLE_KEYWORD_RE = re.compile(
    r"(?:"
    r"أصل(?:ان|ين|ها|ه)?"
    r"|"
    r"أصول"
    r"|"
    r"يدل"
    r"|"
    r"تدل"
    r"|"
    r"معنى"
    r"|"
    r"يرجع"
    r"|"
    r"ترجع"
    r")"
)

COUNT_SIGNAL_PATTERNS = [
    (
        "one",
        re.compile(
            r"أصل\s+(?:صحيح\s+)?واحد"
        ),
    ),
    (
        "two",
        re.compile(
            r"(?:"
            r"أصلان"
            r"|"
            r"أصلين"
            r"|"
            r"أصل\s+اثنان"
            r"|"
            r"أصل\s+اثنين"
            r")"
        ),
    ),
    (
        "three",
        re.compile(
            r"(?:"
            r"ثلاثة\s+أصول"
            r"|"
            r"أصول\s+ثلاثة"
            r")"
        ),
    ),
]


def normalize_space(
    text: str | None,
) -> str:
    if not text:
        return ""

    return WHITESPACE_RE.sub(
        " ",
        text,
    ).strip()


def strip_arabic_marks_for_detection(
    text: str | None,
) -> str:
    """
    Normalize ONLY for deterministic pattern detection.

    The original Maqayis source text is never replaced by this value.
    """
    if not text:
        return ""

    text = unicodedata.normalize(
        "NFC",
        text,
    )

    text = text.replace(
        "\u0640",
        "",
    )

    text = ARABIC_MARK_RE.sub(
        "",
        text,
    )

    return normalize_space(
        text
    )


def split_source_segments(
    text: str | None,
) -> list[str]:
    """
    Preserve the source text verbatim elsewhere; this segmentation is
    only a convenience layer for later inspection/LLM grounding.

    Dot-only artifacts from visibly truncated source rows are omitted
    from this convenience list, while remaining untouched in
    arabic_text_raw.
    """
    if not text:
        return []

    segments = []

    for piece in BOUNDARY_RE.split(
        text
    ):
        piece = normalize_space(
            piece
        )

        if not piece:
            continue

        # Do not emit dozens of standalone "." fragments as semantic
        # segments when the source digitization contains ellipsis-like
        # truncation. Raw source text remains unchanged.
        if re.fullmatch(
            r"[\.\s…]+",
            piece,
        ):
            continue

        segments.append(
            piece
        )

    return segments


def detect_principle_candidates(
    text: str | None,
) -> dict:
    """
    Deterministic source hints only.

    Detection runs on a harakat-stripped normalized copy, but every
    returned candidate is the ORIGINAL Arabic source segment.

    These are NOT translated semantic principles and are NOT asserted
    to be a complete or final interpretation of Ibn Faris.
    """
    if not text:
        return {
            "count_signal":
                None,

            "candidate_count":
                0,

            "candidates":
                [],
        }

    detection_text = (
        strip_arabic_marks_for_detection(
            text
        )
    )

    count_signal = None

    for label, pattern in (
        COUNT_SIGNAL_PATTERNS
    ):
        if pattern.search(
            detection_text
        ):
            count_signal = label
            break

    candidates = []

    for original_segment in (
        split_source_segments(
            text
        )
    ):
        normalized_segment = (
            strip_arabic_marks_for_detection(
                original_segment
            )
        )

        if PRINCIPLE_KEYWORD_RE.search(
            normalized_segment
        ):
            candidates.append(
                original_segment
            )

    # Deduplicate without changing source order.
    seen = set()
    deduped = []

    for candidate in candidates:
        if candidate in seen:
            continue

        seen.add(
            candidate
        )

        deduped.append(
            candidate
        )

    return {
        "count_signal":
            count_signal,

        "candidate_count":
            len(
                deduped
            ),

        "candidates":
            deduped,
    }


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


def audit_result_lookup(
    payload: dict,
) -> dict[str, dict]:
    lookup = {}

    for section in [
        "matches",
        "unmatched",
        "ambiguous",
    ]:
        for record in payload.get(
            section,
            []
        ):
            root_id = record.get(
                "qac_root"
            )

            if not root_id:
                continue

            if root_id in lookup:
                raise RuntimeError(
                    "Duplicate QAC root in Maqayis "
                    f"audit: {root_id}"
                )

            lookup[
                root_id
            ] = record

    return lookup


def fetch_rows_by_ids(
    conn: sqlite3.Connection,
    ids: list[int],
) -> list[dict]:
    if not ids:
        return []

    placeholders = ",".join(
        "?"
        for _ in ids
    )

    rows = conn.execute(
        f"""
        SELECT
            id,
            word,
            meanings
        FROM maqayeesul_luga
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        ids,
    ).fetchall()

    return [
        {
            "id":
                int(row["id"]),

            "word":
                row["word"],

            "meanings":
                row["meanings"],
        }
        for row in rows
    ]


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


def compact_match_record(
    audit_record: dict,
) -> dict:
    output = {
        "status":
            audit_record.get(
                "status"
            ),

        "method":
            audit_record.get(
                "method"
            ),
    }

    if audit_record.get(
        "status"
    ) == "matched":
        output.update(
            {
                "maqayis_heading":
                    audit_record.get(
                        "maqayis_heading"
                    ),

                "maqayis_heading_basic":
                    audit_record.get(
                        "maqayis_heading_basic"
                    ),

                "maqayis_row_ids":
                    audit_record.get(
                        "maqayis_row_ids",
                        []
                    ),
            }
        )

    elif audit_record.get(
        "status"
    ) == "ambiguous":
        output[
            "candidates"
        ] = audit_record.get(
            "candidates",
            []
        )

    return output


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
        MAQAYIS_AUDIT_FILE,
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

    print(
        "Loading canonical QAC root index..."
    )

    qac_payload = load_json(
        QAC_ROOT_INDEX_FILE
    )

    qac_by_root = qac_root_lookup(
        qac_payload
    )

    print(
        f"  QAC roots: "
        f"{len(qac_by_root):,}"
    )

    print(
        "Loading Maqayis root match audit v2..."
    )

    audit_payload = load_json(
        MAQAYIS_AUDIT_FILE
    )

    audit_by_root = audit_result_lookup(
        audit_payload
    )

    print(
        f"  audit root records: "
        f"{len(audit_by_root):,}"
    )

    missing_audit_roots = sorted(
        set(
            qac_by_root
        )
        - set(
            audit_by_root
        )
    )

    extra_audit_roots = sorted(
        set(
            audit_by_root
        )
        - set(
            qac_by_root
        )
    )

    if missing_audit_roots:
        raise RuntimeError(
            "Maqayis audit is missing QAC roots: "
            + ", ".join(
                missing_audit_roots[:50]
            )
        )

    if extra_audit_roots:
        raise RuntimeError(
            "Maqayis audit contains non-QAC roots: "
            + ", ".join(
                extra_audit_roots[:50]
            )
        )

    conn = sqlite3.connect(
        str(DB_FILE)
    )

    conn.row_factory = (
        sqlite3.Row
    )

    roots_output = []

    status_counts = Counter()
    method_counts = Counter()

    fetched_row_count = 0
    missing_source_row_ids = []
    heading_mismatches = []
    empty_meanings_count = 0

    roots_with_principle_candidates = 0
    principle_candidate_count = 0
    count_signal_counts = Counter()

    try:
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

            method = audit_record.get(
                "method"
            )

            status_counts[
                status
            ] += 1

            if method:
                method_counts[
                    method
                ] += 1

            maqayis_entries = []

            if status == "matched":
                expected_ids = [
                    int(value)
                    for value
                    in audit_record.get(
                        "maqayis_row_ids",
                        []
                    )
                ]

                rows = fetch_rows_by_ids(
                    conn,
                    expected_ids,
                )

                fetched_row_count += len(
                    rows
                )

                returned_ids = {
                    row["id"]
                    for row in rows
                }

                for expected_id in (
                    expected_ids
                ):
                    if (
                        expected_id
                        not in returned_ids
                    ):
                        missing_source_row_ids.append(
                            {
                                "qac_root":
                                    root_id,

                                "row_id":
                                    expected_id,
                            }
                        )

                expected_heading = (
                    audit_record.get(
                        "maqayis_heading"
                    )
                )

                for row in rows:
                    if (
                        expected_heading
                        and row["word"]
                        != expected_heading
                    ):
                        heading_mismatches.append(
                            {
                                "qac_root":
                                    root_id,

                                "row_id":
                                    row["id"],

                                "audit_heading":
                                    expected_heading,

                                "database_heading":
                                    row["word"],
                            }
                        )

                    meanings = (
                        row.get(
                            "meanings"
                        )
                        or ""
                    )

                    if not meanings.strip():
                        empty_meanings_count += 1

                    principle_hints = (
                        detect_principle_candidates(
                            meanings
                        )
                    )

                    if (
                        principle_hints[
                            "candidate_count"
                        ]
                        > 0
                    ):
                        roots_with_principle_candidates += 1

                        principle_candidate_count += (
                            principle_hints[
                                "candidate_count"
                            ]
                        )

                    count_signal = (
                        principle_hints[
                            "count_signal"
                        ]
                    )

                    if count_signal:
                        count_signal_counts[
                            count_signal
                        ] += 1

                    maqayis_entries.append(
                        {
                            "source":
                                "maqayis_al_lugha",

                            "table":
                                "maqayeesul_luga",

                            "row_id":
                                row["id"],

                            "heading":
                                row["word"],

                            # Exact database text preserved.
                            "arabic_text_raw":
                                meanings,

                            # Convenience segmentation only.
                            "source_segments":
                                split_source_segments(
                                    meanings
                                ),

                            # Deterministic hints, explicitly not final
                            # semantic interpretation.
                            "principle_candidates":
                                principle_hints,
                        }
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

                    "maqayis_match":
                        compact_match_record(
                            audit_record
                        ),

                    "maqayis":
                        (
                            {
                                "entries":
                                    maqayis_entries,

                                "entry_count":
                                    len(
                                        maqayis_entries
                                    ),
                            }
                            if maqayis_entries
                            else None
                        ),
                }
            )

    finally:
        conn.close()

    matched_count = (
        status_counts[
            "matched"
        ]
    )

    unmatched_count = (
        status_counts[
            "unmatched"
        ]
    )

    ambiguous_count = (
        status_counts[
            "ambiguous"
        ]
    )

    unresolved_roots = [
        {
            "root":
                record["root"],

            "arabic":
                record["arabic"],

            "qac_occurrence_count":
                record[
                    "qac"
                ].get(
                    "occurrence_count"
                ),

            "status":
                record[
                    "maqayis_match"
                ].get(
                    "status"
                ),
        }
        for record in roots_output
        if (
            record[
                "maqayis_match"
            ].get(
                "status"
            )
            != "matched"
        )
    ]

    unresolved_roots.sort(
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

    summary = {
        "qac_root_count":
            len(
                roots_output
            ),

        "matched_qac_roots":
            matched_count,

        "matched_percent":
            round(
                (
                    matched_count
                    / len(
                        roots_output
                    )
                    * 100
                )
                if roots_output
                else 0,
                2,
            ),

        "unmatched_qac_roots":
            unmatched_count,

        "ambiguous_qac_roots":
            ambiguous_count,

        "maqayis_rows_fetched":
            fetched_row_count,

        "missing_source_row_id_count":
            len(
                missing_source_row_ids
            ),

        "heading_mismatch_count":
            len(
                heading_mismatches
            ),

        "empty_meanings_count":
            empty_meanings_count,

        "roots_with_principle_candidates":
            roots_with_principle_candidates,

        "principle_candidate_count":
            principle_candidate_count,

        "principle_count_signal_counts":
            dict(
                sorted(
                    count_signal_counts.items()
                )
            ),

        "method_counts":
            dict(
                sorted(
                    method_counts.items()
                )
            ),
    }

    output = {
        "metadata": {
            "dataset":
                (
                    "Maqayis al-Lugha evidence "
                    "aligned to canonical Quran roots"
                ),

            "version":
                2,

            "canonical_root_source":
                QAC_ROOT_INDEX_FILE.name,

            "match_audit_source":
                str(
                    MAQAYIS_AUDIT_FILE.relative_to(
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
                "maqayeesul_luga",

            "semantic_policy": [
                (
                    "QAC root IDs remain canonical."
                ),
                (
                    "Only roots marked matched by "
                    "maqayis_root_match_audit_v2 are "
                    "assigned Maqayis source text."
                ),
                (
                    "The Arabic source text is preserved "
                    "exactly in arabic_text_raw."
                ),
                (
                    "source_segments are deterministic "
                    "convenience splits and are not a "
                    "semantic reinterpretation."
                ),
                (
                    "principle_candidates are keyword-based "
                    "source hints only; they are not final "
                    "translations or semantic principles."
                ),
                (
                    "No LLM-generated content is present "
                    "in this dataset."
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

    report = {
        "summary":
            summary,

        "missing_source_row_ids":
            missing_source_row_ids,

        "heading_mismatches":
            heading_mismatches,

        "unresolved_roots":
            unresolved_roots,
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    root_output_lookup = {
        record[
            "root"
        ]:
            record
        for record
        in roots_output
    }

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review representative Maqayis "
                    "source extraction and principle "
                    "candidate detection"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            root_output_lookup[
                root_id
            ]
            for root_id
            in SAMPLE_ROOTS
            if root_id
            in root_output_lookup
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
        "MAQAYIS SEMANTIC EXTRACTION COMPLETE"
    )
    print("=" * 60)

    print(
        f"QAC roots:                    "
        f"{len(roots_output):,}"
    )

    print(
        f"Matched Maqayis roots:        "
        f"{matched_count:,}"
    )

    print(
        f"Matched percent:              "
        f"{summary['matched_percent']:.2f}%"
    )

    print(
        f"Unmatched QAC roots:          "
        f"{unmatched_count:,}"
    )

    print(
        f"Ambiguous QAC roots:          "
        f"{ambiguous_count:,}"
    )

    print(
        f"Maqayis rows fetched:         "
        f"{fetched_row_count:,}"
    )

    print(
        f"Missing source rows:          "
        f"{len(missing_source_row_ids):,}"
    )

    print(
        f"Heading mismatches:           "
        f"{len(heading_mismatches):,}"
    )

    print(
        f"Empty meanings:               "
        f"{empty_meanings_count:,}"
    )

    print(
        f"Roots with principle hints:   "
        f"{roots_with_principle_candidates:,}"
    )

    print(
        f"Principle candidate clauses:  "
        f"{principle_candidate_count:,}"
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
        "maqayis_extraction_report_v2.json "
        "and maqayis_semantics_sample_v2.json."
    )


if __name__ == "__main__":
    main()
