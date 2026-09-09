#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_quran_root_index import (
    buckwalter_to_arabic,
    location_parts,
    parse_lemma_id,
    root_to_arabic,
)


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

DEFAULT_MORPHOLOGY_FILE = (
    SCRIPT_DIR
    / "quranic-corpus-morphology-0.4.txt"
)

DEFAULT_ROOT_INDEX_FILE = (
    SCRIPT_DIR
    / "quran_roots_index.json"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "quran_form_inventory_v1.json"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "quran_form_inventory_report_v1.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "quran_form_inventory_sample_v1.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "Aty",
    "Hqq",
    "Slw",
    "zyd",
    "qwl",
]


VERB_ASPECTS = {
    "PERF",
    "IMPF",
    "IMPV",
}

DERIVED_TYPES = {
    "ACTIVE_PARTICIPLE":
        lambda tokens:
            (
                "PCPL" in tokens
                and "ACT" in tokens
            ),

    "PASSIVE_PARTICIPLE":
        lambda tokens:
            (
                "PCPL" in tokens
                and "PASS" in tokens
            ),

    "VERBAL_NOUN":
        lambda tokens:
            "VN" in tokens,
}


POS_LABELS = {
    "V":
        "Verb",

    "N":
        "Noun",

    "ADJ":
        "Adjective",

    "PN":
        "Proper noun",
}


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


def sorted_counter(
    counter: Counter,
) -> dict:
    return {
        key:
            counter[
                key
            ]
        for key
        in sorted(
            counter
        )
    }


def lexical_class(
    tag: str,
) -> str:
    if tag == "V":
        return "verb"

    if tag in {
        "N",
        "ADJ",
        "PN",
    }:
        return "nominal"

    return "other"


def verb_form_from_tokens(
    *,
    tag: str,
    tokens: list[str],
) -> str | None:
    if tag != "V":
        return None

    explicit = next(
        (
            token[
                1:
                -1
            ]
            for token
            in tokens
            if re.fullmatch(
                r"\([IVX]+\)",
                token,
            )
        ),
        None,
    )

    return (
        explicit
        or "I"
    )


def verb_aspect_from_tokens(
    *,
    tag: str,
    tokens: list[str],
) -> str | None:
    if tag != "V":
        return None

    return next(
        (
            token
            for token
            in tokens
            if token
            in VERB_ASPECTS
        ),
        None,
    )


def verb_voice_from_tokens(
    *,
    tag: str,
    tokens: list[str],
) -> str | None:
    if tag != "V":
        return None

    return (
        "PASSIVE"
        if "PASS"
        in tokens
        else "ACTIVE"
    )


def derived_types_from_tokens(
    tokens: list[str],
) -> list[str]:
    return [
        name
        for name, predicate
        in DERIVED_TYPES.items()
        if predicate(
            tokens
        )
    ]


def normalize_location(
    location: str,
) -> tuple[
    str,
    str,
    str,
]:
    surah, ayah, word, segment = (
        location_parts(
            location
        )
    )

    return (
        f"{surah}:{ayah}",
        f"{surah}:{ayah}:{word}",
        f"{surah}:{ayah}:{word}:{segment}",
    )


def group_identity_key(
    *,
    lemma: str | None,
    form: str,
    tag: str,
    verb_form: str | None,
) -> tuple[
    str,
    str,
    str,
]:
    """
    This is a QAC inventory grouping, NOT a claim about the ideal
    public dictionary headword.

    - Verb vs non-verb is kept separate.
    - Verb form is kept separate.
    - Nominal N/ADJ/PN usages sharing the same QAC lemma remain one
      QAC form group with POS counts preserved.
    - A ROOT-bearing row lacking LEM is preserved by exact surface FORM.
    """
    cls = lexical_class(
        tag
    )

    identity = (
        lemma
        if lemma is not None
        else f"@surface:{form}"
    )

    return (
        identity,
        cls,
        verb_form
        or "",
    )


def public_pos_labels(
    pos_counts: Counter,
) -> list[str]:
    return [
        POS_LABELS.get(
            tag,
            tag,
        )
        for tag
        in sorted(
            pos_counts
        )
    ]


def public_morphology_hint(
    *,
    pos_counts: Counter,
    verb_form: str | None,
) -> str:
    labels = public_pos_labels(
        pos_counts
    )

    if (
        verb_form
        is not None
    ):
        return (
            f"Verb · Form {verb_form}"
        )

    return " / ".join(
        labels
    )


def form_group_id(
    *,
    root: str,
    identity: str,
    cls: str,
    verb_form: str,
) -> str:
    return (
        f"qac-form:{root}:"
        f"{identity}:"
        f"{cls}:"
        f"{verb_form or '-'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic Quran-attested form inventory "
            "for the user-facing root dictionary pipeline."
        )
    )

    parser.add_argument(
        "--morphology",
        type=Path,
        default=
            DEFAULT_MORPHOLOGY_FILE,
    )

    parser.add_argument(
        "--root-index",
        type=Path,
        default=
            DEFAULT_ROOT_INDEX_FILE,
    )

    args = parser.parse_args()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        args.morphology,
        args.root_index,
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing required input:\n{path}"
            )

    root_index_payload = (
        load_json(
            args.root_index
        )
    )

    root_index = {
        root[
            "root"
        ]:
            root
        for root
        in root_index_payload.get(
            "roots",
            []
        )
    }

    groups = defaultdict(
        lambda:
            {
                "occurrence_count":
                    0,

                "word_locations":
                    set(),

                "segment_locations":
                    [],

                "surahs":
                    set(),

                "pos_counts":
                    Counter(),

                "surface_forms":
                    defaultdict(
                        lambda:
                            {
                                "count":
                                    0,

                                "pos":
                                    Counter(),
                            }
                    ),

                "verb_aspects":
                    Counter(),

                "verb_voice":
                    Counter(),

                "derived":
                    Counter(),

                "occurrences":
                    [],
            }
    )

    root_occurrence_counts = Counter()

    root_lemma_counts = defaultdict(
        Counter
    )

    root_verb_forms = defaultdict(
        Counter
    )

    root_word_locations = defaultdict(
        set
    )

    word_roots = defaultdict(
        set
    )

    seen_segment_locations = set()

    duplicate_segment_locations = []

    root_bearing_rows = 0
    rows_without_lemma = 0

    with args.morphology.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            line = line.rstrip(
                "\r\n"
            )

            if (
                not line
                or line.startswith(
                    "#"
                )
                or line.startswith(
                    "LOCATION\tFORM\tTAG\tFEATURES"
                )
            ):
                continue

            columns = line.split(
                "\t"
            )

            if len(
                columns
            ) != 4:
                raise ValueError(
                    f"Malformed line {line_number}: "
                    f"expected 4 TAB columns, "
                    f"found {len(columns)}"
                )

            (
                raw_location,
                raw_form,
                tag,
                raw_features,
            ) = columns

            tokens = (
                raw_features.split(
                    "|"
                )
            )

            root = next(
                (
                    token[
                        5:
                    ]
                    for token
                    in tokens
                    if token.startswith(
                        "ROOT:"
                    )
                ),
                None,
            )

            if root is None:
                continue

            root_bearing_rows += 1

            if (
                raw_location
                in seen_segment_locations
            ):
                duplicate_segment_locations.append(
                    raw_location
                )

            seen_segment_locations.add(
                raw_location
            )

            lemma = next(
                (
                    token[
                        4:
                    ]
                    for token
                    in tokens
                    if token.startswith(
                        "LEM:"
                    )
                ),
                None,
            )

            if lemma is None:
                rows_without_lemma += 1

            (
                verse_key,
                word_location,
                segment_location,
            ) = normalize_location(
                raw_location
            )

            surah = int(
                verse_key.split(
                    ":",
                    1,
                )[0]
            )

            vform = (
                verb_form_from_tokens(
                    tag=tag,
                    tokens=tokens,
                )
            )

            aspect = (
                verb_aspect_from_tokens(
                    tag=tag,
                    tokens=tokens,
                )
            )

            voice = (
                verb_voice_from_tokens(
                    tag=tag,
                    tokens=tokens,
                )
            )

            derived_types = (
                derived_types_from_tokens(
                    tokens
                )
            )

            (
                identity,
                cls,
                key_vform,
            ) = group_identity_key(
                lemma=lemma,
                form=raw_form,
                tag=tag,
                verb_form=vform,
            )

            key = (
                root,
                identity,
                cls,
                key_vform,
            )

            bucket = groups[
                key
            ]

            bucket[
                "occurrence_count"
            ] += 1

            bucket[
                "word_locations"
            ].add(
                word_location
            )

            bucket[
                "segment_locations"
            ].append(
                segment_location
            )

            bucket[
                "surahs"
            ].add(
                surah
            )

            bucket[
                "pos_counts"
            ][
                tag
            ] += 1

            surface = bucket[
                "surface_forms"
            ][
                raw_form
            ]

            surface[
                "count"
            ] += 1

            surface[
                "pos"
            ][
                tag
            ] += 1

            if aspect:
                bucket[
                    "verb_aspects"
                ][
                    aspect
                ] += 1

            if voice:
                bucket[
                    "verb_voice"
                ][
                    voice
                ] += 1

            for dtype in (
                derived_types
            ):
                bucket[
                    "derived"
                ][
                    dtype
                ] += 1

            bucket[
                "occurrences"
            ].append(
                {
                    "verse_key":
                        verse_key,

                    "word_location":
                        word_location,

                    "segment_location":
                        segment_location,

                    "surface_buckwalter":
                        raw_form,

                    "surface_arabic":
                        buckwalter_to_arabic(
                            raw_form
                        ),

                    "tag":
                        tag,

                    "verb_form":
                        vform,

                    "aspect":
                        aspect,

                    "voice":
                        voice,

                    "derived_nominal_types":
                        derived_types,
                }
            )

            root_occurrence_counts[
                root
            ] += 1

            root_word_locations[
                root
            ].add(
                word_location
            )

            if lemma is not None:
                root_lemma_counts[
                    root
                ][
                    lemma
                ] += 1

            if vform is not None:
                root_verb_forms[
                    root
                ][
                    vform
                ] += 1

            word_roots[
                word_location
            ].add(
                root
            )

    roots_output = []

    form_group_count = 0

    per_root_group_totals = Counter()

    for root in sorted(
        root_occurrence_counts
    ):
        (
            radicals,
            arabic,
            arabic_spaced,
        ) = root_to_arabic(
            root
        )

        root_groups = []

        candidate_keys = [
            key
            for key
            in groups
            if key[
                0
            ] == root
        ]

        candidate_keys.sort(
            key=lambda key: (
                0
                if key[
                    2
                ] == "verb"
                else 1
                if key[
                    2
                ] == "nominal"
                else 2,

                key[
                    3
                ],

                key[
                    1
                ],
            )
        )

        for (
            _root,
            identity,
            cls,
            key_vform,
        ) in candidate_keys:
            bucket = groups[
                (
                    _root,
                    identity,
                    cls,
                    key_vform,
                )
            ]

            lemma_raw = (
                identity
                if not identity.startswith(
                    "@surface:"
                )
                else None
            )

            lemma_meta = (
                parse_lemma_id(
                    lemma_raw
                )
                if lemma_raw
                is not None
                else None
            )

            surfaces = []

            for raw_form in sorted(
                bucket[
                    "surface_forms"
                ]
            ):
                surface = bucket[
                    "surface_forms"
                ][
                    raw_form
                ]

                surfaces.append(
                    {
                        "buckwalter":
                            raw_form,

                        "arabic":
                            buckwalter_to_arabic(
                                raw_form
                            ),

                        "occurrence_count":
                            surface[
                                "count"
                            ],

                        "pos_counts":
                            sorted_counter(
                                surface[
                                    "pos"
                                ]
                            ),
                    }
                )

            occurrences = sorted(
                bucket[
                    "occurrences"
                ],
                key=lambda item:
                    tuple(
                        map(
                            int,
                            item[
                                "segment_location"
                            ].split(
                                ":"
                            ),
                        )
                    ),
            )

            pos_counts = bucket[
                "pos_counts"
            ]

            verb_form = (
                key_vform
                or None
            )

            public_hint = (
                public_morphology_hint(
                    pos_counts=
                        pos_counts,
                    verb_form=
                        verb_form,
                )
            )

            group_record = {
                "form_group_id":
                    form_group_id(
                        root=root,
                        identity=identity,
                        cls=cls,
                        verb_form=
                            key_vform,
                    ),

                "quran_attested":
                    True,

                "identity_basis":
                    (
                        "qac_lemma"
                        if lemma_raw
                        is not None
                        else "surface_fallback_no_lemma"
                    ),

                "lexical_class":
                    cls,

                "qac_lemma":
                    lemma_meta,

                "qac_lemma_arabic_candidate":
                    (
                        lemma_meta[
                            "arabic"
                        ]
                        if lemma_meta
                        else None
                    ),

                "public_headword_status":
                    (
                        "needs_lexical_normalization"
                    ),

                "public_headword_note":
                    (
                        "The QAC lemma is an internal Quran morphology "
                        "identity and is not guaranteed to be the ideal "
                        "classical dictionary citation form."
                    ),

                "public_morphology_hint":
                    public_hint,

                "verb_form":
                    verb_form,

                "occurrence_count":
                    bucket[
                        "occurrence_count"
                    ],

                "word_count":
                    len(
                        bucket[
                            "word_locations"
                        ]
                    ),

                "surah_count":
                    len(
                        bucket[
                            "surahs"
                        ]
                    ),

                "pos_counts":
                    sorted_counter(
                        pos_counts
                    ),

                "public_pos_labels":
                    public_pos_labels(
                        pos_counts
                    ),

                "verb_aspect_counts":
                    sorted_counter(
                        bucket[
                            "verb_aspects"
                        ]
                    ),

                "verb_voice_counts":
                    sorted_counter(
                        bucket[
                            "verb_voice"
                        ]
                    ),

                "derived_nominal_counts":
                    sorted_counter(
                        bucket[
                            "derived"
                        ]
                    ),

                "surface_forms":
                    surfaces,

                "word_locations":
                    sorted(
                        bucket[
                            "word_locations"
                        ],
                        key=lambda value:
                            tuple(
                                map(
                                    int,
                                    value.split(
                                        ":"
                                    ),
                                )
                            ),
                    ),

                "segment_locations":
                    sorted(
                        bucket[
                            "segment_locations"
                        ],
                        key=lambda value:
                            tuple(
                                map(
                                    int,
                                    value.split(
                                        ":"
                                    ),
                                )
                            ),
                    ),

                "occurrences":
                    occurrences,
            }

            root_groups.append(
                group_record
            )

            form_group_count += 1

            per_root_group_totals[
                root
            ] += bucket[
                "occurrence_count"
            ]

        multi_root_locations = sorted(
            [
                location
                for location
                in root_word_locations[
                    root
                ]
                if len(
                    word_roots[
                        location
                    ]
                )
                > 1
            ],
            key=lambda value:
                tuple(
                    map(
                        int,
                        value.split(
                            ":"
                        ),
                    )
                ),
        )

        roots_output.append(
            {
                "root":
                    root,

                "arabic":
                    arabic,

                "arabic_spaced":
                    arabic_spaced,

                "radicals":
                    radicals,

                "qac_occurrence_count":
                    root_occurrence_counts[
                        root
                    ],

                "qac_word_count":
                    len(
                        root_word_locations[
                            root
                        ]
                    ),

                "form_group_count":
                    len(
                        root_groups
                    ),

                "forms":
                    root_groups,

                "multi_root_word_locations":
                    multi_root_locations,
            }
        )

    # --------------------------------------------------------
    # Hard audits against the already-frozen QAC root index.
    # --------------------------------------------------------

    index_roots = set(
        root_index
    )

    inventory_roots = set(
        root_occurrence_counts
    )

    root_set_missing = sorted(
        index_roots
        - inventory_roots
    )

    root_set_extra = sorted(
        inventory_roots
        - index_roots
    )

    occurrence_mismatches = []

    lemma_mismatches = []

    verb_form_mismatches = []

    group_total_mismatches = []

    for root in sorted(
        inventory_roots
        & index_roots
    ):
        index_record = root_index[
            root
        ]

        if (
            root_occurrence_counts[
                root
            ]
            != index_record[
                "occurrence_count"
            ]
        ):
            occurrence_mismatches.append(
                {
                    "root":
                        root,

                    "inventory":
                        root_occurrence_counts[
                            root
                        ],

                    "root_index":
                        index_record[
                            "occurrence_count"
                        ],
                }
            )

        if (
            per_root_group_totals[
                root
            ]
            != root_occurrence_counts[
                root
            ]
        ):
            group_total_mismatches.append(
                {
                    "root":
                        root,

                    "group_total":
                        per_root_group_totals[
                            root
                        ],

                    "root_total":
                        root_occurrence_counts[
                            root
                        ],
                }
            )

        index_lemma_counts = {
            lemma[
                "id"
            ]:
                lemma[
                    "occurrence_count"
                ]
            for lemma
            in index_record.get(
                "lemmas",
                []
            )
        }

        inventory_lemma_counts = dict(
            root_lemma_counts[
                root
            ]
        )

        if (
            index_lemma_counts
            != inventory_lemma_counts
        ):
            lemma_mismatches.append(
                {
                    "root":
                        root,

                    "inventory":
                        inventory_lemma_counts,

                    "root_index":
                        index_lemma_counts,
                }
            )

        index_forms = (
            index_record.get(
                "verb",
                {}
            ).get(
                "forms",
                {}
            )
        )

        inventory_forms = dict(
            sorted(
                root_verb_forms[
                    root
                ].items()
            )
        )

        if (
            index_forms
            != inventory_forms
        ):
            verb_form_mismatches.append(
                {
                    "root":
                        root,

                    "inventory":
                        inventory_forms,

                    "root_index":
                        index_forms,
                }
            )

    multi_root_words = {
        location:
            sorted(
                roots
            )
        for location, roots
        in word_roots.items()
        if len(
            roots
        )
        > 1
    }

    hard_checks = {
        "root_set_matches_frozen_qac_index":
            (
                not root_set_missing
                and not root_set_extra
            ),

        "root_occurrence_counts_match":
            (
                not occurrence_mismatches
            ),

        "lemma_occurrence_counts_match":
            (
                not lemma_mismatches
            ),

        "verb_form_counts_match":
            (
                not verb_form_mismatches
            ),

        "all_root_occurrences_assigned_to_one_form_group":
            (
                not group_total_mismatches
            ),

        "segment_locations_unique":
            (
                not duplicate_segment_locations
            ),
    }

    if not all(
        hard_checks.values()
    ):
        raise RuntimeError(
            "Quran form inventory audit failed.\n"
            f"Hard checks: {hard_checks}\n"
            f"Missing roots: {root_set_missing[:20]}\n"
            f"Extra roots: {root_set_extra[:20]}\n"
            f"Occurrence mismatches: {occurrence_mismatches[:5]}\n"
            f"Lemma mismatches: {lemma_mismatches[:5]}\n"
            f"Verb-form mismatches: {verb_form_mismatches[:5]}\n"
            f"Group-total mismatches: {group_total_mismatches[:5]}\n"
            f"Duplicate segments: {duplicate_segment_locations[:20]}"
        )

    lexical_class_counts = Counter()

    verb_form_group_counts = Counter()

    for root_record in roots_output:
        for group in root_record[
            "forms"
        ]:
            lexical_class_counts[
                group[
                    "lexical_class"
                ]
            ] += 1

            if group[
                "verb_form"
            ]:
                verb_form_group_counts[
                    group[
                        "verb_form"
                    ]
                ] += 1

    summary = {
        "qac_root_count":
            len(
                roots_output
            ),

        "root_bearing_segment_count":
            root_bearing_rows,

        "form_group_count":
            form_group_count,

        "root_bearing_rows_without_lemma":
            rows_without_lemma,

        "lexical_class_group_counts":
            dict(
                sorted(
                    lexical_class_counts.items()
                )
            ),

        "verb_form_group_counts":
            dict(
                sorted(
                    verb_form_group_counts.items()
                )
            ),

        "multi_root_word_count":
            len(
                multi_root_words
            ),

        "multi_root_words":
            multi_root_words,

        **hard_checks,
    }

    output = {
        "metadata": {
            "dataset":
                (
                    "Canonical Quran-attested form inventory for "
                    "dictionary synthesis"
                ),

            "version":
                1,

            "source":
                args.morphology.name,

            "canonical_root_index":
                args.root_index.name,

            "purpose":
                (
                    "Provide the deterministic Quran morphology skeleton "
                    "onto which source-derived lexical senses will later "
                    "be mapped."
                ),

            "semantic_policy": [
                (
                    "QAC root IDs remain canonical."
                ),
                (
                    "QAC lemma identity, Quran surface form, and final "
                    "classical dictionary headword remain separate concepts."
                ),
                (
                    "A QAC lemma is never automatically asserted to be "
                    "the final public dictionary citation form."
                ),
                (
                    "Verb forms are kept separate; Form I is the documented "
                    "default when QAC omits an explicit form token."
                ),
                (
                    "Nominal N/ADJ/PN occurrences sharing one QAC lemma are "
                    "kept in one QAC form group with POS counts preserved."
                ),
                (
                    "ROOT-bearing rows without LEM are preserved by exact "
                    "surface-form fallback rather than discarded."
                ),
                (
                    "This dataset contains morphology only; no lexical "
                    "meaning is generated here."
                ),
            ],
        },

        "summary":
            summary,

        "roots":
            roots_output,
    }

    write_json(
        OUTPUT_FILE,
        output,
    )

    report = {
        "summary":
            summary,

        "hard_checks":
            hard_checks,

        "diagnostics": {
            "root_set_missing":
                root_set_missing,

            "root_set_extra":
                root_set_extra,

            "occurrence_mismatches":
                occurrence_mismatches,

            "lemma_mismatches":
                lemma_mismatches,

            "verb_form_mismatches":
                verb_form_mismatches,

            "group_total_mismatches":
                group_total_mismatches,

            "duplicate_segment_locations":
                duplicate_segment_locations,
        },
    }

    write_json(
        REPORT_FILE,
        report,
    )

    sample_lookup = {
        root[
            "root"
        ]:
            root
        for root
        in roots_output
    }

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review representative Quran form inventories "
                    "before semantic mapping"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            sample_lookup[
                root
            ]
            for root
            in SAMPLE_ROOTS
            if root
            in sample_lookup
        ],
    }

    write_json(
        SAMPLE_FILE,
        sample,
    )

    print()
    print("=" * 72)
    print(
        "QURAN FORM INVENTORY V1 BUILT"
    )
    print("=" * 72)

    for key, value in summary.items():
        if isinstance(
            value,
            dict,
        ):
            continue

        print(
            f"{key:<52} {value}"
        )

    print()
    print(
        "Output:\n"
        f"{OUTPUT_FILE}"
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


if __name__ == "__main__":
    main()
