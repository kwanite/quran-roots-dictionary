#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

QAC_ROOT_INDEX_FILE = (
    SCRIPT_DIR
    / "quran_roots_index.json"
)

DB_FILE = (
    SCRIPT_DIR
    / "sources"
    / "arabic-lexicons"
    / "db.sqlite"
)

OUTPUT_DIR = SCRIPT_DIR / "output"

OUTPUT_FILE = (
    OUTPUT_DIR
    / "maqayis_root_match_audit_v2.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "maqayis_root_match_sample_v2.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "qwl",
    "Aty",
    "Hqq",
    "Amn",
    "ydy",
    "ndw",
    "nwm",
]


# ============================================================
# Arabic normalization
# ============================================================

# Arabic combining marks + Quranic annotation marks.
ARABIC_MARK_RE = re.compile(
    r"[\u0610-\u061A"
    r"\u064B-\u065F"
    r"\u0670"
    r"\u06D6-\u06ED]"
)

NON_ARABIC_LETTER_RE = re.compile(
    r"[^\u0621-\u063A"
    r"\u0641-\u064A"
    r"\u0671-\u06D3]+"
)


HAMZA_SEATED = {
    "أ": "ء",
    "إ": "ء",
    "ؤ": "ء",
    "ئ": "ء",
}


def strip_arabic_marks(
    text: str | None,
) -> str:
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

    return text.strip()


def basic_heading_key(
    text: str | None,
) -> str:
    """
    Conservative cleanup only:
    - strip Arabic diacritics / tatweel
    - remove spaces and punctuation
    - preserve actual Arabic letters
    """
    text = strip_arabic_marks(
        text
    )

    return NON_ARABIC_LETTER_RE.sub(
        "",
        text,
    )


def orthographic_key(
    text: str | None,
) -> str:
    """
    Orthographic comparison key.

    Safe normalizations:
    - seated hamza -> bare hamza
    - final alif maqsura -> ya

    Important:
    - bare alif is NOT globally converted to hamza
    - waw and ya are NOT interchanged
    """
    text = basic_heading_key(
        text
    )

    chars = []

    for char in text:
        chars.append(
            HAMZA_SEATED.get(
                char,
                char,
            )
        )

    text = "".join(
        chars
    )

    if text.endswith(
        "ى"
    ):
        text = (
            text[:-1]
            + "ي"
        )

    return text


def initial_bare_alif_hamza_key(
    text: str | None,
) -> str:
    """
    Candidate normalization used ONLY when the QAC root itself
    begins with a hamza radical.

    This is intentionally not part of global normalization.
    """
    key = orthographic_key(
        text
    )

    if key.startswith(
        "ا"
    ):
        key = (
            "ء"
            + key[1:]
        )

    return key


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


def qident(
    name: str,
) -> str:
    return (
        '"'
        + name.replace(
            '"',
            '""',
        )
        + '"'
    )


def numeric_location_key(
    location: str,
) -> tuple[int, ...]:
    value = location.strip(
        "()"
    )

    return tuple(
        int(part)
        for part in value.split(":")
    )


# ============================================================
# Maqayis loading
# ============================================================

def load_maqayis_rows(
    conn: sqlite3.Connection,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            id,
            word,
            meanings
        FROM maqayeesul_luga
        ORDER BY id
        """
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


def build_heading_groups(
    rows: list[dict],
) -> dict[str, dict]:
    """
    Group duplicate source rows under their literal cleaned heading.

    Multiple rows sharing the exact same source heading are one source
    heading group, not an ambiguity by themselves.
    """
    groups: dict[
        str,
        dict
    ] = {}

    for row in rows:
        raw_word = (
            row.get(
                "word"
            )
            or ""
        )

        basic = basic_heading_key(
            raw_word
        )

        if not basic:
            continue

        group = groups.setdefault(
            basic,
            {
                "heading":
                    raw_word,

                "heading_basic":
                    basic,

                "heading_orthographic":
                    orthographic_key(
                        raw_word
                    ),

                "row_ids":
                    [],

                "row_count":
                    0,
            },
        )

        group[
            "row_ids"
        ].append(
            row["id"]
        )

        group[
            "row_count"
        ] += 1

    return groups


def make_reverse_index(
    groups: dict[str, dict],
    key_name: str,
) -> dict[str, list[dict]]:
    index: dict[
        str,
        list[dict]
    ] = defaultdict(list)

    for group in groups.values():
        key = group.get(
            key_name
        )

        if key:
            index[
                key
            ].append(
                group
            )

    return index


def make_initial_hamza_index(
    groups: dict[str, dict],
) -> dict[str, list[dict]]:
    """
    Special-purpose source index.

    Only the FIRST source letter is normalized from bare alif ا
    to hamza ء. This index is consulted only for QAC roots whose
    first radical is genuinely hamza.
    """
    index: dict[
        str,
        list[dict]
    ] = defaultdict(list)

    for group in groups.values():
        key = group.get(
            "heading_orthographic"
        )

        if not key:
            continue

        if key.startswith(
            "ا"
        ):
            key = (
                "ء"
                + key[1:]
            )

        index[
            key
        ].append(
            group
        )

    return index


# ============================================================
# Candidate generation
# ============================================================

def root_radicals(
    root_record: dict,
) -> list[str]:
    radicals = root_record.get(
        "radicals"
    )

    if isinstance(
        radicals,
        list,
    ):
        return [
            str(radical)
            for radical in radicals
        ]

    return []


def geminate_contraction(
    root_record: dict,
) -> str | None:
    radicals = root_radicals(
        root_record
    )

    if (
        len(radicals) == 3
        and radicals[1]
        == radicals[2]
    ):
        return (
            radicals[0]
            + radicals[1]
        )

    return None


def reduplicated_quadriliteral_contraction(
    root_record: dict,
) -> str | None:
    radicals = root_radicals(
        root_record
    )

    if (
        len(radicals) == 4
        and radicals[0]
        == radicals[2]
        and radicals[1]
        == radicals[3]
    ):
        return (
            radicals[0]
            + radicals[1]
        )

    return None


def candidate_methods(
    root_record: dict,
) -> list[
    tuple[str, str, str]
]:
    """
    Return ordered candidate lookups as:
        (method, key, index_kind)

    index_kind:
        basic
        orthographic
        initial_hamza

    v2 correction:
    Always attempt the orthographic index after an exact-basic miss,
    even when the QAC spelling itself is unchanged by normalization.
    This allows safe source-only spelling differences such as final
    alif maqsura ى versus ya ي to match.
    """
    arabic = root_record.get(
        "arabic"
    ) or ""

    radicals = root_radicals(
        root_record
    )

    candidates: list[
        tuple[str, str, str]
    ] = []

    exact_key = basic_heading_key(
        arabic
    )

    if exact_key:
        candidates.append(
            (
                "exact_arabic",
                exact_key,
                "basic",
            )
        )

    # Always try the orthographic source index.
    ortho_key = orthographic_key(
        arabic
    )

    if ortho_key:
        candidates.append(
            (
                "normalized_orthography",
                ortho_key,
                "orthographic",
            )
        )

    # For a true initial hamza radical only, allow a source heading
    # written with initial bare alif to compare as hamza.
    if (
        radicals
        and orthographic_key(
            radicals[0]
        ) == "ء"
    ):
        candidates.append(
            (
                "initial_alif_hamza_normalization",
                ortho_key,
                "initial_hamza",
            )
        )

    contracted = (
        geminate_contraction(
            root_record
        )
    )

    if contracted:
        contracted_basic = (
            basic_heading_key(
                contracted
            )
        )

        if contracted_basic:
            candidates.append(
                (
                    "geminate_contraction",
                    contracted_basic,
                    "basic",
                )
            )

        contracted_ortho = (
            orthographic_key(
                contracted
            )
        )

        if contracted_ortho:
            candidates.append(
                (
                    "geminate_contraction_normalized",
                    contracted_ortho,
                    "orthographic",
                )
            )

    quad_contract = (
        reduplicated_quadriliteral_contraction(
            root_record
        )
    )

    if quad_contract:
        quad_basic = (
            basic_heading_key(
                quad_contract
            )
        )

        if quad_basic:
            candidates.append(
                (
                    "reduplicated_quadriliteral_contraction",
                    quad_basic,
                    "basic",
                )
            )

        quad_ortho = (
            orthographic_key(
                quad_contract
            )
        )

        if quad_ortho:
            candidates.append(
                (
                    "reduplicated_quadriliteral_contraction_normalized",
                    quad_ortho,
                    "orthographic",
                )
            )

    seen = set()
    output = []

    for (
        method,
        key,
        index_kind,
    ) in candidates:
        identity = (
            method,
            key,
            index_kind,
        )

        if (
            not key
            or identity in seen
        ):
            continue

        seen.add(
            identity
        )

        output.append(
            (
                method,
                key,
                index_kind,
            )
        )

    return output


# ============================================================
# Matching
# ============================================================

def match_root(
    root_record: dict,
    basic_index: dict[
        str,
        list[dict]
    ],
    orthographic_index: dict[
        str,
        list[dict]
    ],
    initial_hamza_index: dict[
        str,
        list[dict]
    ],
) -> dict:
    arabic = root_record.get(
        "arabic"
    ) or ""

    radicals = root_radicals(
        root_record
    )

    attempted = []

    for (
        method,
        key,
        index_kind,
    ) in candidate_methods(
        root_record
    ):
        if index_kind == "basic":
            index = basic_index

            lookup_key = (
                basic_heading_key(
                    key
                )
            )

        elif (
            index_kind
            == "initial_hamza"
        ):
            index = (
                initial_hamza_index
            )

            lookup_key = (
                orthographic_key(
                    key
                )
            )

        else:
            index = (
                orthographic_index
            )

            lookup_key = (
                orthographic_key(
                    key
                )
            )

        candidates = index.get(
            lookup_key,
            [],
        )

        attempted.append(
            {
                "method":
                    method,

                "lookup_key":
                    lookup_key,

                "candidate_headings":
                    [
                        group[
                            "heading"
                        ]
                        for group
                        in candidates
                    ],
            }
        )

        # One heading group = deterministic match.
        if len(candidates) == 1:
            group = candidates[0]

            return {
                "status":
                    "matched",

                "method":
                    method,

                "qac_root":
                    root_record[
                        "root"
                    ],

                "qac_arabic":
                    arabic,

                "qac_radicals":
                    radicals,

                "maqayis_heading":
                    group[
                        "heading"
                    ],

                "maqayis_heading_basic":
                    group[
                        "heading_basic"
                    ],

                "maqayis_row_ids":
                    group[
                        "row_ids"
                    ],

                "maqayis_row_count":
                    group[
                        "row_count"
                    ],

                "attempted":
                    attempted,
            }

        # Multiple distinct source heading groups under the same
        # comparison key are not auto-resolved.
        if len(candidates) > 1:
            return {
                "status":
                    "ambiguous",

                "method":
                    method,

                "qac_root":
                    root_record[
                        "root"
                    ],

                "qac_arabic":
                    arabic,

                "qac_radicals":
                    radicals,

                "candidates":
                    [
                        {
                            "heading":
                                group[
                                    "heading"
                                ],

                            "row_ids":
                                group[
                                    "row_ids"
                                ],
                        }
                        for group in candidates
                    ],

                "attempted":
                    attempted,
            }

    return {
        "status":
            "unmatched",

        "method":
            None,

        "qac_root":
            root_record[
                "root"
            ],

        "qac_arabic":
            arabic,

        "qac_radicals":
            radicals,

        "attempted":
            attempted,
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        QAC_ROOT_INDEX_FILE,
        DB_FILE,
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing required input:\n{path}"
            )

    qac_payload = load_json(
        QAC_ROOT_INDEX_FILE
    )

    qac_roots = qac_payload.get(
        "roots",
        []
    )

    if len(qac_roots) != 1642:
        print(
            "WARNING: expected 1,642 canonical "
            f"QAC roots, got {len(qac_roots):,}"
        )

    conn = sqlite3.connect(
        str(DB_FILE)
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        maqayis_rows = (
            load_maqayis_rows(
                conn
            )
        )
    finally:
        conn.close()

    heading_groups = (
        build_heading_groups(
            maqayis_rows
        )
    )

    basic_index = (
        make_reverse_index(
            heading_groups,
            "heading_basic",
        )
    )

    orthographic_index = (
        make_reverse_index(
            heading_groups,
            "heading_orthographic",
        )
    )

    initial_hamza_index = (
        make_initial_hamza_index(
            heading_groups
        )
    )

    results = []

    method_counts = Counter()
    status_counts = Counter()

    qac_lookup = {}

    for root_record in qac_roots:
        root_id = root_record[
            "root"
        ]

        qac_lookup[
            root_id
        ] = root_record

        result = match_root(
            root_record,
            basic_index,
            orthographic_index,
            initial_hamza_index,
        )

        result[
            "qac_occurrence_count"
        ] = root_record.get(
            "occurrence_count",
            0,
        )

        result[
            "qac_lemma_count"
        ] = root_record.get(
            "lemma_count",
            0,
        )

        result[
            "qac_lemmas"
        ] = [
            {
                "id":
                    lemma.get(
                        "id"
                    ),

                "arabic":
                    lemma.get(
                        "arabic"
                    ),

                "occurrence_count":
                    lemma.get(
                        "occurrence_count"
                    ),
            }
            for lemma in root_record.get(
                "lemmas",
                []
            )
        ]

        results.append(
            result
        )

        status_counts[
            result["status"]
        ] += 1

        if result[
            "method"
        ]:
            method_counts[
                result["method"]
            ] += 1

    matched = [
        result
        for result in results
        if result[
            "status"
        ] == "matched"
    ]

    unmatched = [
        result
        for result in results
        if result[
            "status"
        ] == "unmatched"
    ]

    ambiguous = [
        result
        for result in results
        if result[
            "status"
        ] == "ambiguous"
    ]

    unmatched.sort(
        key=lambda item: (
            -int(
                item.get(
                    "qac_occurrence_count",
                    0,
                )
            ),
            item[
                "qac_root"
            ],
        )
    )

    ambiguous.sort(
        key=lambda item:
            item[
                "qac_root"
            ]
    )

    # Source heading diagnostics.
    source_duplicate_heading_groups = [
        group
        for group
        in heading_groups.values()
        if group[
            "row_count"
        ] > 1
    ]

    orthographic_collisions = {
        key: [
            {
                "heading":
                    group[
                        "heading"
                    ],

                "row_ids":
                    group[
                        "row_ids"
                    ],
            }
            for group in groups
        ]
        for key, groups
        in orthographic_index.items()
        if len(groups) > 1
    }

    audit = {
        "metadata": {
            "source_database":
                str(
                    DB_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "source_table":
                "maqayeesul_luga",

            "qac_source":
                QAC_ROOT_INDEX_FILE.name,

            "matcher_version":
                2,

            "policy": [
                (
                    "QAC root IDs remain canonical."
                ),
                (
                    "Exact Arabic heading match is preferred."
                ),
                (
                    "Only conservative orthographic normalization "
                    "is allowed automatically."
                ),
                (
                    "The orthographic source index is always checked "
                    "after an exact miss, so source-only differences "
                    "such as final ى versus ي can match safely."
                ),
                (
                    "Geminate contraction ABC where B=C may map "
                    "to AB."
                ),
                (
                    "Only exact ABAB quadriliterals may attempt "
                    "AB contraction."
                ),
                (
                    "No automatic waw/ya interchange."
                ),
                (
                    "No general weak-root substitution."
                ),
                (
                    "Unmatched roots are allowed and must not be "
                    "forced into a source heading."
                ),
            ],
        },

        "summary": {
            "qac_root_count":
                len(
                    qac_roots
                ),

            "maqayis_row_count":
                len(
                    maqayis_rows
                ),

            "maqayis_distinct_heading_count":
                len(
                    heading_groups
                ),

            "matched_root_count":
                len(
                    matched
                ),

            "matched_percent":
                round(
                    (
                        len(matched)
                        / len(qac_roots)
                        * 100
                    )
                    if qac_roots
                    else 0,
                    2,
                ),

            "unmatched_root_count":
                len(
                    unmatched
                ),

            "ambiguous_root_count":
                len(
                    ambiguous
                ),

            "method_counts":
                dict(
                    sorted(
                        method_counts.items()
                    )
                ),

            "source_duplicate_heading_group_count":
                len(
                    source_duplicate_heading_groups
                ),

            "orthographic_collision_count":
                len(
                    orthographic_collisions
                ),
        },

        "matches":
            matched,

        "unmatched":
            unmatched,

        "ambiguous":
            ambiguous,

        "source_diagnostics": {
            "duplicate_heading_groups":
                source_duplicate_heading_groups,

            "orthographic_collisions":
                orthographic_collisions,
        },
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            audit,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    result_by_root = {
        result[
            "qac_root"
        ]:
            result
        for result
        in results
    }

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review representative QAC -> "
                    "Maqayis root matches"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            result_by_root[
                root_id
            ]
            for root_id
            in SAMPLE_ROOTS
            if root_id
            in result_by_root
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
        "MAQAYIS ROOT MATCH AUDIT"
    )
    print("=" * 60)

    print(
        f"QAC roots:                   "
        f"{len(qac_roots):,}"
    )

    print(
        f"Maqayis rows:                "
        f"{len(maqayis_rows):,}"
    )

    print(
        f"Maqayis distinct headings:   "
        f"{len(heading_groups):,}"
    )

    print(
        f"Matched QAC roots:           "
        f"{len(matched):,}"
    )

    print(
        f"Matched percent:             "
        f"{audit['summary']['matched_percent']:.2f}%"
    )

    print(
        f"Unmatched QAC roots:         "
        f"{len(unmatched):,}"
    )

    print(
        f"Ambiguous QAC roots:         "
        f"{len(ambiguous):,}"
    )

    print()
    print(
        "Methods:"
    )

    for method, count in (
        method_counts.most_common()
    ):
        print(
            f"  {method}: {count:,}"
        )

    print()
    print(
        f"Audit written to:\n"
        f"{OUTPUT_FILE}"
    )

    print()
    print(
        f"Sample written to:\n"
        f"{SAMPLE_FILE}"
    )

    print()

    if unmatched:
        print(
            "Top unmatched roots by Quran occurrence count:"
        )

        for item in unmatched[:30]:
            print(
                f"  {item['qac_root']:<8} "
                f"{item['qac_arabic']:<8} "
                f"{item['qac_occurrence_count']:,}"
            )

    print()
    print(
        "NEXT ACTION: upload "
        "maqayis_root_match_audit_v2.json "
        "and maqayis_root_match_sample_v2.json."
    )


if __name__ == "__main__":
    main()
