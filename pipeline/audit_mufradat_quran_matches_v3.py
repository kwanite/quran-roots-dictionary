#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
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

DB_FILE = (
    SCRIPT_DIR
    / "sources"
    / "arabic-lexicons"
    / "db.sqlite"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "mufradat_quran_match_audit_v3.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "mufradat_quran_match_sample_v3.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "qwl",
    "qyl",
    "Aty",
    "Hqq",
    "Amn",
    "nwm",
    "ydy",
    "ndw",
    "smw",
    "jzy",
    "rbb",
    "Amr",
    "Ahl",
    "Abw",
    "Aby",
    "Slw",
    "Sly",
    "ESw",
    "ESy",
    "zwd",
    "zyd",
    "Axr",
    "Amm",
]


# ============================================================
# Arabic normalization
# ============================================================

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

    # For orthographic comparison of Quranic lexeme/headword spellings.
    # QAC commonly writes long alif as ا + maddah mark, while a source
    # heading may use precomposed آ. After mark stripping the QAC side
    # becomes ا, so normalize source آ to ا in this comparison key.
    "آ": "ا",
}


def strip_arabic_marks(
    text: str | None,
) -> str:
    """
    Strip Quranic/Arabic combining marks BEFORE NFC composition.

    Why this order matters:
    QAC can encode a Quranic long-alif sequence as:
        ا + U+0653 ARABIC MADDAH ABOVE

    If NFC is applied first, that sequence can compose to:
        آ

    and then the mark-removal regex can no longer remove the Quranic
    maddah. That caused valid lemma/headword pairs such as:

        جَآءَ  <->  جاء
        مَآء   <->  ماء
        بَآءَ  <->  باء

    to fail exact comparison.

    Precomposed Arabic letters already present in source text, such as
    أ / إ / آ, remain intact because we do not decompose them first.
    """
    if not text:
        return ""

    text = text.replace(
        "\u0640",
        "",
    )

    text = ARABIC_MARK_RE.sub(
        "",
        text,
    )

    text = unicodedata.normalize(
        "NFC",
        text,
    )

    return text.strip()


def basic_key(
    text: str | None,
) -> str:
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
    text = basic_key(
        text
    )

    chars = [
        HAMZA_SEATED.get(
            char,
            char,
        )
        for char in text
    ]

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


def split_source_heading(
    raw_heading: str | None,
) -> list[str]:
    """
    Some bundled lexicons occasionally use | to hold alternate labels.
    Treat such pieces as aliases for matching, while preserving the
    original word field in all output.
    """
    if not raw_heading:
        return []

    pieces = [
        piece.strip()
        for piece in raw_heading.split("|")
        if piece.strip()
    ]

    return pieces or [
        raw_heading
    ]


# ============================================================
# QAC helpers
# ============================================================

def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def radicals(
    root_record: dict,
) -> list[str]:
    value = root_record.get(
        "radicals"
    )

    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        str(item)
        for item in value
    ]


def geminate_contraction(
    root_record: dict,
) -> str | None:
    rads = radicals(
        root_record
    )

    if (
        len(rads) == 3
        and rads[1] == rads[2]
    ):
        return (
            rads[0]
            + rads[1]
        )

    return None


def reduplicated_quadriliteral_contraction(
    root_record: dict,
) -> str | None:
    rads = radicals(
        root_record
    )

    if (
        len(rads) == 4
        and rads[0] == rads[2]
        and rads[1] == rads[3]
    ):
        return (
            rads[0]
            + rads[1]
        )

    return None


# ============================================================
# Source loading
# ============================================================

def load_mufradat_rows(
    conn: sqlite3.Connection,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            id,
            word,
            meanings
        FROM mufradat_alfajul_quran
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


def build_source_indexes(
    rows: list[dict],
) -> tuple[
    dict[str, list[dict]],
    dict[str, list[dict]],
]:
    basic_index = defaultdict(
        list
    )

    ortho_index = defaultdict(
        list
    )

    for row in rows:
        for alias in split_source_heading(
            row.get(
                "word"
            )
        ):
            bkey = basic_key(
                alias
            )

            okey = orthographic_key(
                alias
            )

            if bkey:
                basic_index[
                    bkey
                ].append(
                    row
                )

            if okey:
                ortho_index[
                    okey
                ].append(
                    row
                )

    return (
        basic_index,
        ortho_index,
    )


def final_weak_root_to_alif(
    root_record: dict,
) -> str | None:
    """
    Conservative Mufradat citation-form candidate.

    If the canonical QAC root ends in weak radical و or ي, allow one
    additional source-heading candidate with the final radical surfaced
    as plain alif ا.

    This does NOT interchange و and ي, and it never decides a collision
    by itself. Competing roots that converge on the same source heading
    remain subject to evidence ranking / ambiguity quarantine.
    """
    rads = radicals(
        root_record
    )

    arabic = (
        root_record.get(
            "arabic"
        )
        or ""
    )

    if (
        not rads
        or rads[-1] not in {
            "و",
            "ي",
        }
        or not arabic
    ):
        return None

    if arabic[-1] not in {
        "و",
        "ي",
    }:
        return None

    return (
        arabic[:-1]
        + "ا"
    )


# ============================================================
# Candidate evidence
# ============================================================

METHOD_RANK = {
    "exact_root":
        1,

    "normalized_root":
        2,

    "geminate_root_contraction":
        3,

    "reduplicated_quadriliteral_contraction":
        4,

    "exact_qac_lemma":
        5,

    "normalized_qac_lemma":
        6,

    # Mufradat is a lexeme/headword source, not a strict root list.
    # A final weak radical و / ي can surface as citation-form ا:
    #
    #   سمو -> سما
    #   جزي -> جزا
    #   ندو -> ندا
    #
    # This is deliberately weaker evidence than an exact QAC lemma.
    "final_weak_root_to_alif":
        7,
}


def add_hits(
    evidence_by_row: dict[
        int,
        list[dict]
    ],
    rows: list[dict],
    method: str,
    matched_value: str,
    lemma_id: str | None = None,
) -> None:
    for row in rows:
        evidence_by_row[
            row["id"]
        ].append(
            {
                "method":
                    method,

                "rank":
                    METHOD_RANK[
                        method
                    ],

                "matched_value":
                    matched_value,

                "lemma_id":
                    lemma_id,
            }
        )


def collect_root_candidates(
    root_record: dict,
    basic_index: dict[
        str,
        list[dict]
    ],
    ortho_index: dict[
        str,
        list[dict]
    ],
) -> dict[int, list[dict]]:
    evidence_by_row: dict[
        int,
        list[dict]
    ] = defaultdict(list)

    arabic_root = root_record.get(
        "arabic"
    ) or ""

    root_basic = basic_key(
        arabic_root
    )

    root_ortho = orthographic_key(
        arabic_root
    )

    if root_basic:
        add_hits(
            evidence_by_row,
            basic_index.get(
                root_basic,
                [],
            ),
            "exact_root",
            arabic_root,
        )

    if root_ortho:
        add_hits(
            evidence_by_row,
            ortho_index.get(
                root_ortho,
                [],
            ),
            "normalized_root",
            arabic_root,
        )

    contracted = geminate_contraction(
        root_record
    )

    if contracted:
        add_hits(
            evidence_by_row,
            basic_index.get(
                basic_key(
                    contracted
                ),
                [],
            ),
            "geminate_root_contraction",
            contracted,
        )

    quad_contract = (
        reduplicated_quadriliteral_contraction(
            root_record
        )
    )

    if quad_contract:
        add_hits(
            evidence_by_row,
            basic_index.get(
                basic_key(
                    quad_contract
                ),
                [],
            ),
            "reduplicated_quadriliteral_contraction",
            quad_contract,
        )

    weak_alif = (
        final_weak_root_to_alif(
            root_record
        )
    )

    if weak_alif:
        add_hits(
            evidence_by_row,
            basic_index.get(
                basic_key(
                    weak_alif
                ),
                [],
            ),
            "final_weak_root_to_alif",
            weak_alif,
        )

    for lemma in root_record.get(
        "lemmas",
        []
    ):
        lemma_arabic = (
            lemma.get(
                "arabic"
            )
            or ""
        )

        lemma_id = lemma.get(
            "id"
        )

        lemma_basic = basic_key(
            lemma_arabic
        )

        lemma_ortho = orthographic_key(
            lemma_arabic
        )

        if lemma_basic:
            add_hits(
                evidence_by_row,
                basic_index.get(
                    lemma_basic,
                    [],
                ),
                "exact_qac_lemma",
                lemma_arabic,
                lemma_id,
            )

        if lemma_ortho:
            add_hits(
                evidence_by_row,
                ortho_index.get(
                    lemma_ortho,
                    [],
                ),
                "normalized_qac_lemma",
                lemma_arabic,
                lemma_id,
            )

    # De-duplicate identical evidence and sort by strength.
    for row_id, evidence in list(
        evidence_by_row.items()
    ):
        unique = {}

        for item in evidence:
            key = (
                item[
                    "method"
                ],
                item[
                    "matched_value"
                ],
                item.get(
                    "lemma_id"
                ),
            )

            unique[
                key
            ] = item

        evidence_by_row[
            row_id
        ] = sorted(
            unique.values(),
            key=lambda item: (
                item[
                    "rank"
                ],
                item[
                    "method"
                ],
                item[
                    "matched_value"
                ],
            ),
        )

    return evidence_by_row


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

    conn = sqlite3.connect(
        str(DB_FILE)
    )

    conn.row_factory = (
        sqlite3.Row
    )

    try:
        source_rows = (
            load_mufradat_rows(
                conn
            )
        )
    finally:
        conn.close()

    source_by_id = {
        row[
            "id"
        ]:
            row
        for row in source_rows
    }

    (
        basic_index,
        ortho_index,
    ) = build_source_indexes(
        source_rows
    )

    root_candidate_map = {}

    source_row_to_roots: dict[
        int,
        set[str]
    ] = defaultdict(set)

    for root in qac_roots:
        root_id = root[
            "root"
        ]

        candidates = (
            collect_root_candidates(
                root,
                basic_index,
                ortho_index,
            )
        )

        root_candidate_map[
            root_id
        ] = candidates

        for row_id in candidates:
            source_row_to_roots[
                row_id
            ].add(
                root_id
            )

    # --------------------------------------------------------
    # Resolve source-row competition by evidence strength.
    #
    # v1/v2 quarantined ANY source row touched by >1 QAC root.
    # That was too conservative. Example:
    #
    #   source: أمر
    #   QAC root أمر -> exact_root (rank 1)
    #   root مرر      -> lemma أَمَرّ (rank 5)
    #
    # These are not equally strong claims. v3 assigns a source row when
    # exactly one candidate root has the best (lowest) evidence rank.
    # Only a tie at the strongest rank remains ambiguous.
    # --------------------------------------------------------

    source_row_competition = {}

    for row_id, root_ids in (
        source_row_to_roots.items()
    ):
        candidate_ranks = {}

        for root_id in root_ids:
            evidence = (
                root_candidate_map[
                    root_id
                ][
                    row_id
                ]
            )

            candidate_ranks[
                root_id
            ] = min(
                item[
                    "rank"
                ]
                for item in evidence
            )

        best_rank = min(
            candidate_ranks.values()
        )

        strongest_roots = sorted(
            root_id
            for root_id, rank
            in candidate_ranks.items()
            if rank == best_rank
        )

        if len(
            strongest_roots
        ) == 1:
            source_row_competition[
                row_id
            ] = {
                "status":
                    "assigned",

                "assigned_root":
                    strongest_roots[0],

                "best_rank":
                    best_rank,

                "candidate_ranks":
                    dict(
                        sorted(
                            candidate_ranks.items()
                        )
                    ),

                "resolution":
                    (
                        "sole_candidate"
                        if len(
                            candidate_ranks
                        ) == 1
                        else
                        "unique_strongest_evidence"
                    ),
            }

        else:
            source_row_competition[
                row_id
            ] = {
                "status":
                    "ambiguous",

                "assigned_root":
                    None,

                "best_rank":
                    best_rank,

                "strongest_roots":
                    strongest_roots,

                "candidate_ranks":
                    dict(
                        sorted(
                            candidate_ranks.items()
                        )
                    ),

                "resolution":
                    "tied_strongest_evidence",
            }

    assigned_source_rows = {
        row_id:
            info
        for row_id, info
        in source_row_competition.items()
        if info[
            "status"
        ] == "assigned"
    }

    ambiguous_source_rows = {
        row_id:
            info
        for row_id, info
        in source_row_competition.items()
        if info[
            "status"
        ] == "ambiguous"
    }

    resolved_competitions = {
        row_id:
            info
        for row_id, info
        in assigned_source_rows.items()
        if info[
            "resolution"
        ] == "unique_strongest_evidence"
    }

    results = []

    matched_root_count = 0
    unmatched_root_count = 0
    roots_with_ambiguous_extra = 0

    method_primary_counts = Counter()

    automatically_assigned_source_rows = set()

    for root in qac_roots:
        root_id = root[
            "root"
        ]

        candidates = root_candidate_map[
            root_id
        ]

        accepted_entries = []
        ambiguous_entries = []

        for row_id, evidence in sorted(
            candidates.items()
        ):
            source = source_by_id[
                row_id
            ]

            competition = (
                source_row_competition[
                    row_id
                ]
            )

            record = {
                "row_id":
                    row_id,

                "heading":
                    source.get(
                        "word"
                    ),

                "evidence":
                    evidence,

                "best_method":
                    evidence[0][
                        "method"
                    ],

                "best_rank":
                    evidence[0][
                        "rank"
                    ],
            }

            if (
                competition[
                    "status"
                ]
                == "assigned"
                and competition[
                    "assigned_root"
                ]
                == root_id
            ):
                record[
                    "assignment_resolution"
                ] = competition[
                    "resolution"
                ]

                if (
                    competition[
                        "resolution"
                    ]
                    == "unique_strongest_evidence"
                ):
                    record[
                        "competing_qac_root_ranks"
                    ] = competition[
                        "candidate_ranks"
                    ]

                accepted_entries.append(
                    record
                )

                automatically_assigned_source_rows.add(
                    row_id
                )

                method_primary_counts[
                    evidence[0][
                        "method"
                    ]
                ] += 1

            elif (
                competition[
                    "status"
                ]
                == "ambiguous"
                and root_id
                in competition[
                    "strongest_roots"
                ]
            ):
                record[
                    "candidate_qac_roots"
                ] = competition[
                    "strongest_roots"
                ]

                record[
                    "candidate_qac_root_ranks"
                ] = competition[
                    "candidate_ranks"
                ]

                ambiguous_entries.append(
                    record
                )

            # If this root was only a weaker competing candidate and a
            # stronger root won, do not attach the row to this root.

        if accepted_entries:
            status = "matched"
            matched_root_count += 1

        elif ambiguous_entries:
            status = "ambiguous_only"

        else:
            status = "unmatched"
            unmatched_root_count += 1

        if ambiguous_entries:
            roots_with_ambiguous_extra += 1

        results.append(
            {
                "status":
                    status,

                "qac_root":
                    root_id,

                "qac_arabic":
                    root.get(
                        "arabic"
                    ),

                "qac_radicals":
                    root.get(
                        "radicals",
                        []
                    ),

                "qac_occurrence_count":
                    root.get(
                        "occurrence_count",
                        0
                    ),

                "qac_lemma_count":
                    root.get(
                        "lemma_count",
                        0
                    ),

                "qac_lemmas":
                    [
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
                        for lemma
                        in root.get(
                            "lemmas",
                            []
                        )
                    ],

                "matched_entries":
                    accepted_entries,

                "ambiguous_entries":
                    ambiguous_entries,
            }
        )

    unmatched = [
        record
        for record in results
        if record[
            "status"
        ] == "unmatched"
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

    ambiguous_only = [
        record
        for record in results
        if record[
            "status"
        ] == "ambiguous_only"
    ]

    source_unassigned = [
        {
            "row_id":
                row["id"],

            "heading":
                row.get(
                    "word"
                ),

            "has_meanings":
                bool(
                    (
                        row.get(
                            "meanings"
                        )
                        or ""
                    ).strip()
                ),
        }
        for row in source_rows
        if (
            row["id"]
            not in automatically_assigned_source_rows
            and row["id"]
            not in ambiguous_source_rows
        )
    ]

    audit = {
        "metadata": {
            "source_database":
                str(
                    DB_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "source_table":
                "mufradat_alfajul_quran",

            "qac_source":
                QAC_ROOT_INDEX_FILE.name,

            "matcher_version":
                3,

            "policy": [
                (
                    "QAC root IDs remain canonical."
                ),
                (
                    "Mufradat is treated as a Quranic "
                    "lexeme/headword source, not as a "
                    "strict root-heading dictionary."
                ),
                (
                    "Matching therefore uses both the "
                    "canonical QAC root spelling and the "
                    "Arabic spellings of QAC lemmas."
                ),
                (
                    "Quranic combining marks are stripped before "
                    "Unicode NFC composition so sequences such as "
                    "جَآءَ correctly compare with source جاء."
                ),
                (
                    "Precomposed آ is normalized to ا only in the "
                    "orthographic comparison key; raw source and QAC "
                    "spellings remain unchanged in output."
                ),
                (
                    "Geminate and exact ABAB contractions "
                    "are allowed conservatively."
                ),
                (
                    "No general weak-letter substitution "
                    "or waw/ya interchange is performed."
                ),
                (
                    "If a source row has multiple QAC candidates, "
                    "v3 compares evidence ranks. A unique strongest "
                    "candidate is assigned; only a tie at the strongest "
                    "rank remains ambiguous."
                ),
                (
                    "A final weak QAC radical و or ي may generate a "
                    "lower-priority Mufradat citation-form candidate "
                    "ending in ا. This does not interchange و and ي; "
                    "collisions remain subject to ambiguity handling."
                ),
                (
                    "One QAC root may legitimately receive "
                    "multiple Mufradat headword rows."
                ),
            ],
        },

        "summary": {
            "qac_root_count":
                len(
                    qac_roots
                ),

            "mufradat_row_count":
                len(
                    source_rows
                ),

            "matched_qac_root_count":
                matched_root_count,

            "matched_qac_root_percent":
                round(
                    (
                        matched_root_count
                        / len(
                            qac_roots
                        )
                        * 100
                    )
                    if qac_roots
                    else 0,
                    2,
                ),

            "unmatched_qac_root_count":
                unmatched_root_count,

            "ambiguous_only_qac_root_count":
                len(
                    ambiguous_only
                ),

            "roots_with_any_ambiguous_entry":
                roots_with_ambiguous_extra,

            "automatically_assigned_source_row_count":
                len(
                    automatically_assigned_source_rows
                ),

            "ambiguous_source_row_count":
                len(
                    ambiguous_source_rows
                ),

            "resolved_competition_source_row_count":
                len(
                    resolved_competitions
                ),

            "unassigned_source_row_count":
                len(
                    source_unassigned
                ),

            "primary_match_method_counts":
                dict(
                    sorted(
                        method_primary_counts.items()
                    )
                ),
        },

        "roots":
            results,

        "unmatched":
            unmatched,

        "ambiguous_only":
            ambiguous_only,

        "source_diagnostics": {
            "resolved_competitions": [
                {
                    "row_id":
                        row_id,

                    "heading":
                        source_by_id[
                            row_id
                        ].get(
                            "word"
                        ),

                    "assigned_root":
                        info[
                            "assigned_root"
                        ],

                    "best_rank":
                        info[
                            "best_rank"
                        ],

                    "candidate_qac_root_ranks":
                        info[
                            "candidate_ranks"
                        ],
                }
                for row_id, info
                in sorted(
                    resolved_competitions.items()
                )
            ],

            "ambiguous_source_rows": [
                {
                    "row_id":
                        row_id,

                    "heading":
                        source_by_id[
                            row_id
                        ].get(
                            "word"
                        ),

                    "best_rank":
                        info[
                            "best_rank"
                        ],

                    "candidate_qac_roots":
                        info[
                            "strongest_roots"
                        ],

                    "candidate_qac_root_ranks":
                        info[
                            "candidate_ranks"
                        ],

                    # Only a handful should remain after evidence ranking.
                    # Include the raw source text so they can be reviewed
                    # without another database probe.
                    "meanings":
                        source_by_id[
                            row_id
                        ].get(
                            "meanings"
                        ),
                }
                for row_id, info
                in sorted(
                    ambiguous_source_rows.items()
                )
            ],

            "unassigned_source_rows":
                source_unassigned,
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

    by_root = {
        record[
            "qac_root"
        ]:
            record
        for record in results
    }

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review representative QAC root/lemma "
                    "to Mufradat headword matches"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            by_root[
                root_id
            ]
            for root_id
            in SAMPLE_ROOTS
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
    print("=" * 60)
    print(
        "MUFRADAT QURAN MATCH AUDIT"
    )
    print("=" * 60)

    print(
        f"QAC roots:                     "
        f"{len(qac_roots):,}"
    )

    print(
        f"Mufradat rows:                 "
        f"{len(source_rows):,}"
    )

    print(
        f"Matched QAC roots:             "
        f"{matched_root_count:,}"
    )

    print(
        f"Matched percent:               "
        f"{audit['summary']['matched_qac_root_percent']:.2f}%"
    )

    print(
        f"Unmatched QAC roots:           "
        f"{unmatched_root_count:,}"
    )

    print(
        f"Ambiguous-only QAC roots:      "
        f"{len(ambiguous_only):,}"
    )

    print(
        f"Assigned Mufradat rows:        "
        f"{len(automatically_assigned_source_rows):,}"
    )

    print(
        f"Resolved row competitions:     "
        f"{len(resolved_competitions):,}"
    )

    print(
        f"Ambiguous Mufradat rows:       "
        f"{len(ambiguous_source_rows):,}"
    )

    print(
        f"Unassigned Mufradat rows:      "
        f"{len(source_unassigned):,}"
    )

    print()
    print(
        "Primary matching methods:"
    )

    for method, count in (
        method_primary_counts
        .most_common()
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
        "mufradat_quran_match_audit_v3.json "
        "and mufradat_quran_match_sample_v3.json."
    )


if __name__ == "__main__":
    main()
