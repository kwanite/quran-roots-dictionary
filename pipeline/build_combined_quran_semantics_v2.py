#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

COMBINED_V1_FILE = (
    OUTPUT_DIR
    / "quran_root_semantics_combined_v1.json"
)

MAQAYIS_FILE = (
    OUTPUT_DIR
    / "maqayis_quran_semantics_v2.json"
)

MUFRADAT_FILE = (
    OUTPUT_DIR
    / "mufradat_quran_semantics_v1.json"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "quran_root_semantics_combined_v2.json"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "quran_root_semantics_combined_report_v2.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "quran_root_semantics_combined_sample_v2.json"
)


SAMPLE_ROOTS = [
    # Rich coverage across all layers.
    "rHm",
    "ktb",
    "qwl",
    "Aty",
    "Hqq",

    # Useful edge cases.
    "ydy",
    "ndw",

    # Shared/composite Mufradat evidence.
    "Slw",
    "zyd",
]


# ============================================================
# Generic helpers
# ============================================================

def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def root_lookup(
    payload: dict,
    *,
    root_key: str = "root",
) -> dict[str, dict]:
    roots = payload.get(
        "roots",
        []
    )

    lookup = {}

    for record in roots:
        root_id = record.get(
            root_key
        )

        if not root_id:
            raise RuntimeError(
                f"Root record missing {root_key!r}"
            )

        if root_id in lookup:
            raise RuntimeError(
                f"Duplicate root record: {root_id}"
            )

        lookup[
            root_id
        ] = record

    return lookup


def lemma_signature_from_qac(
    morphology: dict,
) -> list[
    tuple[
        str | None,
        str | None,
        int | None,
    ]
]:
    output = []

    for lemma in morphology.get(
        "lemmas",
        []
    ):
        output.append(
            (
                lemma.get(
                    "id"
                ),
                lemma.get(
                    "arabic"
                ),
                lemma.get(
                    "occurrence_count"
                ),
            )
        )

    return sorted(
        output,
        key=lambda item: (
            str(
                item[0]
                or ""
            ),
            str(
                item[1]
                or ""
            ),
            int(
                item[2]
                or 0
            ),
        ),
    )


def lemma_signature_from_compact_qac(
    qac: dict,
) -> list[
    tuple[
        str | None,
        str | None,
        int | None,
    ]
]:
    output = []

    for lemma in qac.get(
        "lemmas",
        []
    ):
        output.append(
            (
                lemma.get(
                    "id"
                ),
                lemma.get(
                    "arabic"
                ),
                lemma.get(
                    "occurrence_count"
                ),
            )
        )

    return sorted(
        output,
        key=lambda item: (
            str(
                item[0]
                or ""
            ),
            str(
                item[1]
                or ""
            ),
            int(
                item[2]
                or 0
            ),
        ),
    )


def maqayis_has_content(
    record: dict,
) -> bool:
    maqayis = record.get(
        "maqayis"
    )

    if not isinstance(
        maqayis,
        dict,
    ):
        return False

    return bool(
        maqayis.get(
            "entries"
        )
    )


def mufradat_unique_entries(
    record: dict,
) -> list[dict]:
    mufradat = record.get(
        "mufradat"
    )

    if not isinstance(
        mufradat,
        dict,
    ):
        return []

    entries = mufradat.get(
        "entries",
        []
    )

    return (
        entries
        if isinstance(
            entries,
            list,
        )
        else []
    )


def mufradat_shared_entries(
    record: dict,
) -> list[dict]:
    mufradat = record.get(
        "mufradat"
    )

    if not isinstance(
        mufradat,
        dict,
    ):
        return []

    entries = mufradat.get(
        "shared_ambiguous_entries",
        []
    )

    return (
        entries
        if isinstance(
            entries,
            list,
        )
        else []
    )


def lane_has_content(
    combined_record: dict,
) -> bool:
    classical = combined_record.get(
        "classical_lexicon",
        {}
    )

    if not isinstance(
        classical,
        dict,
    ):
        return False

    lane = classical.get(
        "lane"
    )

    if not lane:
        return False

    # Keep this intentionally tolerant of the exact Lane v2 schema.
    # A truthy Lane payload means the combined v1 already retained
    # lexical evidence for this root.
    return True


# ============================================================
# Main
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    required = [
        COMBINED_V1_FILE,
        MAQAYIS_FILE,
        MUFRADAT_FILE,
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
        "Loading frozen combined evidence v1..."
    )

    combined_v1 = load_json(
        COMBINED_V1_FILE
    )

    print(
        "Loading frozen Maqayis evidence v2..."
    )

    maqayis_payload = load_json(
        MAQAYIS_FILE
    )

    print(
        "Loading frozen Mufradat evidence v1..."
    )

    mufradat_payload = load_json(
        MUFRADAT_FILE
    )

    combined_by_root = root_lookup(
        combined_v1
    )

    maqayis_by_root = root_lookup(
        maqayis_payload
    )

    mufradat_by_root = root_lookup(
        mufradat_payload
    )

    canonical_roots = set(
        combined_by_root
    )

    maqayis_roots = set(
        maqayis_by_root
    )

    mufradat_roots = set(
        mufradat_by_root
    )

    maqayis_missing = sorted(
        canonical_roots
        - maqayis_roots
    )

    maqayis_extra = sorted(
        maqayis_roots
        - canonical_roots
    )

    mufradat_missing = sorted(
        canonical_roots
        - mufradat_roots
    )

    mufradat_extra = sorted(
        mufradat_roots
        - canonical_roots
    )

    if (
        maqayis_missing
        or maqayis_extra
        or mufradat_missing
        or mufradat_extra
    ):
        raise RuntimeError(
            "Root inventory mismatch.\n"
            f"Maqayis missing: {maqayis_missing[:30]}\n"
            f"Maqayis extra: {maqayis_extra[:30]}\n"
            f"Mufradat missing: {mufradat_missing[:30]}\n"
            f"Mufradat extra: {mufradat_extra[:30]}"
        )

    arabic_identity_mismatches = []
    occurrence_mismatches = []
    lemma_mismatches = []

    maqayis_content_count = 0
    mufradat_unique_root_count = 0
    mufradat_shared_root_count = 0

    roots_with_lane = 0
    roots_with_any_lexical_content = 0
    roots_with_all_three_lexical_sources = 0
    roots_with_no_lane_maqayis_mufradat = 0

    mufradat_status_counts = Counter()
    maqayis_status_counts = Counter()

    combined_roots = []

    for root_id in sorted(
        canonical_roots
    ):
        base = combined_by_root[
            root_id
        ]

        maq = maqayis_by_root[
            root_id
        ]

        muf = mufradat_by_root[
            root_id
        ]

        # ----------------------------------------------------
        # Identity / QAC consistency validation
        # ----------------------------------------------------

        base_arabic = base.get(
            "arabic"
        )

        maq_arabic = maq.get(
            "arabic"
        )

        muf_arabic = muf.get(
            "arabic"
        )

        if not (
            base_arabic
            == maq_arabic
            == muf_arabic
        ):
            arabic_identity_mismatches.append(
                {
                    "root":
                        root_id,

                    "combined_v1":
                        base_arabic,

                    "maqayis":
                        maq_arabic,

                    "mufradat":
                        muf_arabic,
                }
            )

        morphology = (
            base.get(
                "quran",
                {}
            ).get(
                "morphology",
                {}
            )
        )

        canonical_occurrence = (
            morphology.get(
                "occurrence_count"
            )
        )

        maq_occurrence = (
            maq.get(
                "qac",
                {}
            ).get(
                "occurrence_count"
            )
        )

        muf_occurrence = (
            muf.get(
                "qac",
                {}
            ).get(
                "occurrence_count"
            )
        )

        if not (
            canonical_occurrence
            == maq_occurrence
            == muf_occurrence
        ):
            occurrence_mismatches.append(
                {
                    "root":
                        root_id,

                    "combined_v1":
                        canonical_occurrence,

                    "maqayis":
                        maq_occurrence,

                    "mufradat":
                        muf_occurrence,
                }
            )

        canonical_lemmas = (
            lemma_signature_from_qac(
                morphology
            )
        )

        maq_lemmas = (
            lemma_signature_from_compact_qac(
                maq.get(
                    "qac",
                    {}
                )
            )
        )

        muf_lemmas = (
            lemma_signature_from_compact_qac(
                muf.get(
                    "qac",
                    {}
                )
            )
        )

        if not (
            canonical_lemmas
            == maq_lemmas
            == muf_lemmas
        ):
            lemma_mismatches.append(
                {
                    "root":
                        root_id,

                    "combined_v1":
                        canonical_lemmas,

                    "maqayis":
                        maq_lemmas,

                    "mufradat":
                        muf_lemmas,
                }
            )

        # ----------------------------------------------------
        # Source presence
        # ----------------------------------------------------

        has_lane = (
            lane_has_content(
                base
            )
        )

        has_maqayis = (
            maqayis_has_content(
                maq
            )
        )

        unique_mufradat = (
            mufradat_unique_entries(
                muf
            )
        )

        shared_mufradat = (
            mufradat_shared_entries(
                muf
            )
        )

        has_mufradat_unique = bool(
            unique_mufradat
        )

        has_mufradat_shared = bool(
            shared_mufradat
        )

        if has_lane:
            roots_with_lane += 1

        if has_maqayis:
            maqayis_content_count += 1

        if has_mufradat_unique:
            mufradat_unique_root_count += 1

        if has_mufradat_shared:
            mufradat_shared_root_count += 1

        maq_status = (
            maq.get(
                "maqayis_match",
                {}
            ).get(
                "status"
            )
        )

        muf_status = (
            muf.get(
                "mufradat_match",
                {}
            ).get(
                "status"
            )
        )

        maqayis_status_counts[
            str(
                maq_status
            )
        ] += 1

        mufradat_status_counts[
            str(
                muf_status
            )
        ] += 1

        any_content = (
            has_lane
            or has_maqayis
            or has_mufradat_unique
            or has_mufradat_shared
        )

        if any_content:
            roots_with_any_lexical_content += 1

        if (
            has_lane
            and has_maqayis
            and has_mufradat_unique
        ):
            roots_with_all_three_lexical_sources += 1

        if not any_content:
            roots_with_no_lane_maqayis_mufradat += 1

        # ----------------------------------------------------
        # Build combined v2 root
        # ----------------------------------------------------

        root_output = dict(
            base
        )

        root_output[
            "root_principles"
        ] = {
            "maqayis": {
                "match":
                    maq.get(
                        "maqayis_match"
                    ),

                "evidence":
                    maq.get(
                        "maqayis"
                    ),
            }
        }

        root_output[
            "quranic_lexicon"
        ] = {
            "mufradat": {
                "match":
                    muf.get(
                        "mufradat_match"
                    ),

                "evidence":
                    muf.get(
                        "mufradat"
                    ),
            }
        }

        source_presence = dict(
            root_output.get(
                "source_presence",
                {}
            )
        )

        source_presence.update(
            {
                "maqayis_semantics_record":
                    True,

                "maqayis_lexical_content":
                    has_maqayis,

                "mufradat_semantics_record":
                    True,

                "mufradat_unique_lexical_content":
                    has_mufradat_unique,

                "mufradat_shared_ambiguous_content":
                    has_mufradat_shared,
            }
        )

        root_output[
            "source_presence"
        ] = source_presence

        combined_roots.append(
            root_output
        )

    # --------------------------------------------------------
    # Hard validation before writing master output
    # --------------------------------------------------------

    if arabic_identity_mismatches:
        raise RuntimeError(
            "Arabic root identity mismatches found; "
            "see report construction logic."
        )

    if occurrence_mismatches:
        raise RuntimeError(
            "QAC occurrence-count mismatches found; "
            "refusing to write combined v2."
        )

    if lemma_mismatches:
        raise RuntimeError(
            "QAC lemma mismatches found; "
            "refusing to write combined v2."
        )

    summary = {
        "canonical_root_count":
            len(
                combined_roots
            ),

        "maqayis_root_record_count":
            len(
                maqayis_by_root
            ),

        "mufradat_root_record_count":
            len(
                mufradat_by_root
            ),

        "roots_with_lane_content":
            roots_with_lane,

        "roots_with_maqayis_content":
            maqayis_content_count,

        "roots_with_mufradat_unique_content":
            mufradat_unique_root_count,

        "roots_with_mufradat_shared_content":
            mufradat_shared_root_count,

        "roots_with_any_lane_maqayis_or_mufradat_content":
            roots_with_any_lexical_content,

        "roots_with_lane_maqayis_and_unique_mufradat":
            roots_with_all_three_lexical_sources,

        "roots_with_no_lane_maqayis_or_mufradat_content":
            roots_with_no_lane_maqayis_mufradat,

        "maqayis_status_counts":
            dict(
                sorted(
                    maqayis_status_counts.items()
                )
            ),

        "mufradat_status_counts":
            dict(
                sorted(
                    mufradat_status_counts.items()
                )
            ),

        "arabic_identity_mismatch_count":
            len(
                arabic_identity_mismatches
            ),

        "occurrence_mismatch_count":
            len(
                occurrence_mismatches
            ),

        "lemma_mismatch_count":
            len(
                lemma_mismatches
            ),
    }

    previous_metadata = combined_v1.get(
        "metadata",
        {}
    )

    output = {
        "metadata": {
            "dataset":
                (
                    "Combined Quran root evidence: "
                    "QAC morphology + Quran Foundation context + "
                    "Lane + Maqayis al-Lugha + Mufradat Alfaz al-Quran"
                ),

            "version":
                2,

            "base_combined_dataset":
                str(
                    COMBINED_V1_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "maqayis_dataset":
                str(
                    MAQAYIS_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "mufradat_dataset":
                str(
                    MUFRADAT_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "canonical_root_count":
                len(
                    combined_roots
                ),

            "architecture": {
                "quran.morphology":
                    "Quranic Arabic Corpus morphology evidence",

                "quran.contextual_english":
                    "Quran Foundation word-by-word contextual English",

                "classical_lexicon.lane":
                    "Lane classical lexical evidence",

                "root_principles.maqayis":
                    (
                        "Ibn Faris Maqayis al-Lugha root-principle "
                        "evidence"
                    ),

                "quranic_lexicon.mufradat":
                    (
                        "Al-Raghib Mufradat Quran-specific lexical "
                        "evidence"
                    ),
            },

            "semantic_policy": [
                (
                    "This remains an evidence dataset. "
                    "It does not collapse the sources into one "
                    "English meaning."
                ),
                (
                    "QAC root IDs remain canonical across all "
                    "joined layers."
                ),
                (
                    "Raw source evidence and source-specific "
                    "matching metadata remain preserved."
                ),
                (
                    "Mufradat shared/composite entries remain "
                    "explicitly marked ambiguous/shared."
                ),
                (
                    "No generated English semantic overview is "
                    "included yet."
                ),
            ],

            "base_metadata":
                previous_metadata,
        },

        "summary":
            summary,

        "roots":
            combined_roots,
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

        "inventory_validation": {
            "maqayis_missing_roots":
                maqayis_missing,

            "maqayis_extra_roots":
                maqayis_extra,

            "mufradat_missing_roots":
                mufradat_missing,

            "mufradat_extra_roots":
                mufradat_extra,
        },

        "identity_validation": {
            "arabic_identity_mismatches":
                arabic_identity_mismatches,

            "occurrence_mismatches":
                occurrence_mismatches,

            "lemma_mismatches":
                lemma_mismatches,
        },
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    by_root = {
        record[
            "root"
        ]:
            record
        for record
        in combined_roots
    }

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review combined evidence architecture "
                    "after adding Maqayis and Mufradat"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            by_root[
                root_id
            ]
            for root_id in SAMPLE_ROOTS
            if root_id in by_root
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
    print("=" * 64)
    print(
        "COMBINED QURAN ROOT SEMANTICS V2 COMPLETE"
    )
    print("=" * 64)

    print(
        f"Canonical roots:                       "
        f"{len(combined_roots):,}"
    )

    print(
        f"Roots with Lane content:               "
        f"{roots_with_lane:,}"
    )

    print(
        f"Roots with Maqayis content:            "
        f"{maqayis_content_count:,}"
    )

    print(
        f"Roots with unique Mufradat content:    "
        f"{mufradat_unique_root_count:,}"
    )

    print(
        f"Roots with shared Mufradat content:    "
        f"{mufradat_shared_root_count:,}"
    )

    print(
        f"Roots with all 3 lexical sources:      "
        f"{roots_with_all_three_lexical_sources:,}"
    )

    print(
        f"Roots with any lexical evidence:       "
        f"{roots_with_any_lexical_content:,}"
    )

    print(
        f"Roots with no lexical evidence:        "
        f"{roots_with_no_lane_maqayis_mufradat:,}"
    )

    print()
    print(
        f"Arabic identity mismatches:            "
        f"{len(arabic_identity_mismatches):,}"
    )

    print(
        f"Occurrence mismatches:                 "
        f"{len(occurrence_mismatches):,}"
    )

    print(
        f"Lemma mismatches:                      "
        f"{len(lemma_mismatches):,}"
    )

    print()
    print(
        "Master dataset:\n"
        f"{OUTPUT_FILE}"
    )

    print()
    print(
        "Audit report:\n"
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
        "quran_root_semantics_combined_report_v2.json "
        "and quran_root_semantics_combined_sample_v2.json."
    )


if __name__ == "__main__":
    main()
