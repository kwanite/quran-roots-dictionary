#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

QAC_MORPHOLOGY_FILE = (
    SCRIPT_DIR / "quranic-corpus-morphology-0.4.txt"
)

QURAN_ROOT_INDEX_FILE = (
    SCRIPT_DIR / "quran_roots_index.json"
)

QF_WBW_CANDIDATES = [
    SCRIPT_DIR
    / "sources"
    / "quran-foundation"
    / "qf_wbw_en_v4.json",

    SCRIPT_DIR
    / "sources"
    / "quran-foundation"
    / "qf_wbw_en.json",
]

QF_WBW_FILE = next(
    (
        path
        for path in QF_WBW_CANDIDATES
        if path.exists()
    ),
    QF_WBW_CANDIDATES[0],
)

OUTPUT_DIR = SCRIPT_DIR / "output"

OUTPUT_FILE = (
    OUTPUT_DIR / "quran_context_glosses_v2.json"
)

REPORT_FILE = (
    OUTPUT_DIR / "quran_context_glosses_report_v2.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR / "quran_context_glosses_sample_v2.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "qwl",
    "Aty",
    "Amn",
    "Hqq",
]


# ============================================================
# Regex / constants
# ============================================================

FEATURE_SPLIT_RE = re.compile(r"\|")
FORM_RE = re.compile(
    r"\((I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\)"
)

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


# ============================================================
# Generic helpers
# ============================================================

def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def normalize_space(
    text: str | None,
) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = WHITESPACE_RE.sub(
        " ",
        text,
    )

    return text.strip()


def clean_gloss_display(
    text: str | None,
) -> str:
    """
    Preserve the supplied English wording while removing only
    presentation noise such as surrounding whitespace and HTML tags.

    We do NOT paraphrase, translate, or alter parentheses.
    """
    text = normalize_space(text)

    if not text:
        return ""

    text = HTML_TAG_RE.sub(
        "",
        text,
    )

    return normalize_space(text)


def normalize_gloss_key(
    text: str | None,
) -> str:
    """
    Case-insensitive aggregation key.

    Exact source variants remain preserved separately.
    """
    return clean_gloss_display(
        text
    ).casefold()


def location_sort_key(
    location: str,
) -> tuple[int, int, int]:
    return tuple(
        int(part)
        for part in location.split(":")
    )


def parse_segment_location(
    location: str,
) -> tuple[int, int, int, int]:
    if not (
        location.startswith("(")
        and location.endswith(")")
    ):
        raise ValueError(
            f"Bad QAC location: {location}"
        )

    parts = (
        location[1:-1]
        .split(":")
    )

    if len(parts) != 4:
        raise ValueError(
            f"Bad QAC location: {location}"
        )

    return tuple(
        int(part)
        for part in parts
    )


def whole_word_location(
    segment_location: str,
) -> str:
    surah, ayah, word, _segment = (
        parse_segment_location(
            segment_location
        )
    )

    return (
        f"{surah}:{ayah}:{word}"
    )


# ============================================================
# QAC feature parsing
# ============================================================

def feature_value(
    features: str,
    prefix: str,
) -> str | None:
    for token in FEATURE_SPLIT_RE.split(
        features
    ):
        if token.startswith(prefix):
            return token[
                len(prefix):
            ]

    return None


def parse_root_segment(
    location: str,
    form: str,
    tag: str,
    features: str,
) -> dict | None:
    root = feature_value(
        features,
        "ROOT:",
    )

    if root is None:
        return None

    lemma_id = feature_value(
        features,
        "LEM:",
    )

    verb_form = None

    if tag == "V":
        match = FORM_RE.search(
            features
        )

        # QAC Form I is implicit/default.
        verb_form = (
            match.group(1)
            if match
            else "I"
        )

    return {
        "segment_location":
            location,

        "segment_form":
            form,

        "tag":
            tag,

        "root":
            root,

        "lemma_id":
            lemma_id,

        "verb_form":
            verb_form,

        "aspect":
            (
                "PERF"
                if "PERF" in features
                else "IMPF"
                if "IMPF" in features
                else "IMPV"
                if "IMPV" in features
                else None
            ),

        "voice":
            (
                "PASSIVE"
                if "PASS" in features
                else "ACTIVE"
                if tag == "V"
                else None
            ),

        "features_raw":
            features,
    }


# ============================================================
# QAC morphology loading
# ============================================================

def load_root_bearing_words(
    path: Path,
) -> tuple[
    dict[str, list[dict]],
    dict[str, list[dict]],
    int,
]:
    """
    Return:
      root-bearing segments grouped by whole Quran word
      all segments grouped by whole Quran word
      data-row count
    """
    root_segments_by_word: dict[
        str,
        list[dict]
    ] = defaultdict(list)

    all_segments_by_word: dict[
        str,
        list[dict]
    ] = defaultdict(list)

    row_count = 0

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for raw_line in handle:
            line = raw_line.rstrip(
                "\r\n"
            )

            if (
                not line
                or line.startswith("#")
            ):
                continue

            parts = line.split("\t")

            # QAC morphology files contain a literal header row:
            # LOCATION<TAB>FORM<TAB>TAG<TAB>FEATURES
            if parts == [
                "LOCATION",
                "FORM",
                "TAG",
                "FEATURES",
            ]:
                continue

            if len(parts) != 4:
                raise RuntimeError(
                    "QAC morphology row did not "
                    "contain exactly 4 TAB-separated "
                    f"columns:\n{line}"
                )

            (
                location,
                form,
                tag,
                features,
            ) = parts

            row_count += 1

            word_location = (
                whole_word_location(
                    location
                )
            )

            segment_record = {
                "segment_location":
                    location,

                "form":
                    form,

                "tag":
                    tag,

                "features":
                    features,
            }

            all_segments_by_word[
                word_location
            ].append(
                segment_record
            )

            root_record = (
                parse_root_segment(
                    location,
                    form,
                    tag,
                    features,
                )
            )

            if root_record is not None:
                root_segments_by_word[
                    word_location
                ].append(
                    root_record
                )

    for rows in all_segments_by_word.values():
        rows.sort(
            key=lambda row:
                parse_segment_location(
                    row[
                        "segment_location"
                    ]
                )[3]
        )

    for rows in root_segments_by_word.values():
        rows.sort(
            key=lambda row:
                parse_segment_location(
                    row[
                        "segment_location"
                    ]
                )[3]
        )

    return (
        root_segments_by_word,
        all_segments_by_word,
        row_count,
    )


# ============================================================
# Root-index metadata
# ============================================================

def load_root_metadata(
    path: Path,
) -> tuple[
    dict[str, dict],
    dict[
        tuple[str, str],
        dict
    ],
]:
    payload = load_json(path)

    roots = payload.get(
        "roots",
        [],
    )

    root_lookup = {}
    lemma_lookup = {}

    for root in roots:
        root_id = root[
            "root"
        ]

        root_lookup[
            root_id
        ] = root

        for lemma in root.get(
            "lemmas",
            []
        ):
            lemma_id = lemma.get(
                "id"
            )

            if lemma_id is not None:
                lemma_lookup[
                    (
                        root_id,
                        lemma_id,
                    )
                ] = lemma

    return (
        root_lookup,
        lemma_lookup,
    )


# ============================================================
# Gloss aggregation
# ============================================================

class GlossCounter:
    def __init__(self) -> None:
        self.normalized_counts = Counter()

        self.variants: dict[
            str,
            Counter
        ] = defaultdict(Counter)

    def add(
        self,
        gloss: str,
    ) -> None:
        display = clean_gloss_display(
            gloss
        )

        if not display:
            return

        key = normalize_gloss_key(
            display
        )

        self.normalized_counts[
            key
        ] += 1

        self.variants[
            key
        ][display] += 1

    def to_json(
        self,
    ) -> list[dict]:
        output = []

        for key, count in (
            self.normalized_counts
            .most_common()
        ):
            variant_counts = (
                self.variants[
                    key
                ]
            )

            variants = [
                {
                    "text":
                        text,

                    "count":
                        variant_count,
                }
                for text, variant_count
                in variant_counts.most_common()
            ]

            preferred = (
                variants[0]["text"]
                if variants
                else key
            )

            output.append(
                {
                    "gloss":
                        preferred,

                    "normalized_gloss":
                        key,

                    "count":
                        count,

                    "source_variants":
                        variants,
                }
            )

        return output


# ============================================================
# Phrase-level duplicate audit
# ============================================================

def build_adjacent_repeated_gloss_clusters(
    qf_words: dict[str, dict],
) -> tuple[dict[str, dict], list[dict]]:
    """
    Find maximal runs of consecutive Quran word positions within a verse
    that carry the same normalized English gloss.

    These are treated conservatively as *possible phrase-level repeated
    renderings*. They are preserved as contextual evidence but excluded
    from the primary lexical-frequency distribution.

    This does NOT assert that every repeated adjacent gloss is erroneous.
    Some may be legitimate identical translations of neighboring words.
    """
    by_verse: dict[
        str,
        list[tuple[int, str, str, str]]
    ] = defaultdict(list)

    for location, record in qf_words.items():
        verse_key = record.get("verse_key")
        position = record.get("position")
        gloss = clean_gloss_display(
            record.get("translation_en")
        )

        if (
            not verse_key
            or position is None
            or not gloss
        ):
            continue

        by_verse[verse_key].append(
            (
                int(position),
                normalize_gloss_key(gloss),
                gloss,
                location,
            )
        )

    location_to_cluster: dict[str, dict] = {}
    clusters: list[dict] = []

    for verse_key, rows in by_verse.items():
        rows.sort(key=lambda item: item[0])

        i = 0

        while i < len(rows):
            (
                start_pos,
                normalized,
                display,
                _start_location,
            ) = rows[i]

            j = i + 1

            while j < len(rows):
                prev = rows[j - 1]
                current = rows[j]

                consecutive = (
                    current[0]
                    == prev[0] + 1
                )

                same_gloss = (
                    current[1]
                    == normalized
                )

                if not (
                    consecutive
                    and same_gloss
                    and normalized
                ):
                    break

                j += 1

            run = rows[i:j]

            if len(run) >= 2:
                cluster_id = (
                    f"{verse_key}:"
                    f"{run[0][0]}-{run[-1][0]}"
                )

                locations = [
                    item[3]
                    for item in run
                ]

                variants = Counter(
                    item[2]
                    for item in run
                )

                cluster = {
                    "cluster_id":
                        cluster_id,

                    "verse_key":
                        verse_key,

                    "start_position":
                        run[0][0],

                    "end_position":
                        run[-1][0],

                    "word_count":
                        len(run),

                    "normalized_gloss":
                        normalized,

                    "source_variants": [
                        {
                            "text":
                                variant,

                            "count":
                                count,
                        }
                        for variant, count
                        in variants.most_common()
                    ],

                    "locations":
                        locations,

                    "classification":
                        (
                            "adjacent_repeated_gloss_candidate"
                        ),

                    "interpretation_note":
                        (
                            "The same English gloss appears on "
                            "two or more consecutive Quran word "
                            "positions. Preserve as contextual "
                            "evidence, but do not assume it is "
                            "an exact lexical gloss for each word."
                        ),
                }

                clusters.append(cluster)

                compact = {
                    "cluster_id":
                        cluster_id,

                    "verse_key":
                        verse_key,

                    "start_position":
                        run[0][0],

                    "end_position":
                        run[-1][0],

                    "word_count":
                        len(run),

                    "normalized_gloss":
                        normalized,
                }

                for location in locations:
                    location_to_cluster[
                        location
                    ] = compact

            i = j

    clusters.sort(
        key=lambda cluster:
            (
                int(
                    cluster[
                        "verse_key"
                    ].split(":")[0]
                ),
                int(
                    cluster[
                        "verse_key"
                    ].split(":")[1]
                ),
                cluster[
                    "start_position"
                ],
            )
    )

    return (
        location_to_cluster,
        clusters,
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    required = [
        QAC_MORPHOLOGY_FILE,
        QURAN_ROOT_INDEX_FILE,
        QF_WBW_FILE,
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

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Loading QAC morphology..."
    )

    (
        root_segments_by_word,
        all_segments_by_word,
        qac_row_count,
    ) = load_root_bearing_words(
        QAC_MORPHOLOGY_FILE
    )

    print(
        f"  morphology rows: "
        f"{qac_row_count:,}"
    )

    print(
        f"  words with root-bearing segments: "
        f"{len(root_segments_by_word):,}"
    )

    print(
        "Loading QAC root metadata..."
    )

    (
        root_lookup,
        lemma_lookup,
    ) = load_root_metadata(
        QURAN_ROOT_INDEX_FILE
    )

    print(
        f"  roots: "
        f"{len(root_lookup):,}"
    )

    print(
        "Loading Quran Foundation WBW data..."
    )

    qf_payload = load_json(
        QF_WBW_FILE
    )

    qf_words = qf_payload.get(
        "words",
        {},
    )

    print(
        f"  QF words: "
        f"{len(qf_words):,}"
    )

    (
        repeated_gloss_cluster_by_location,
        repeated_gloss_clusters,
    ) = build_adjacent_repeated_gloss_clusters(
        qf_words
    )

    repeated_gloss_word_locations = set(
        repeated_gloss_cluster_by_location
    )

    print(
        f"  adjacent repeated-gloss clusters: "
        f"{len(repeated_gloss_clusters):,}"
    )

    print(
        f"  QF words in repeated-gloss clusters: "
        f"{len(repeated_gloss_word_locations):,}"
    )

    # --------------------------------------------------------
    # Containers
    # --------------------------------------------------------

    root_data: dict[
        str,
        dict
    ] = {}

    direct_mapped_segment_count = 0
    direct_mapped_word_count = 0

    ambiguous_multi_root_words = []
    ambiguous_root_segment_count = 0

    root_words_missing_qf = []

    source_gloss_missing_count = 0

    direct_whole_word_gloss_occurrences = 0
    repeated_adjacent_gloss_root_occurrences = 0

    lemma_metadata_missing = []

    # For diagnostics around words with multiple root-bearing stems.
    multi_root_word_count = 0

    # --------------------------------------------------------
    # Initialize all canonical roots
    # --------------------------------------------------------

    for root_id, root_meta in (
        root_lookup.items()
    ):
        root_data[
            root_id
        ] = {
            "root":
                root_id,

            "arabic":
                root_meta.get(
                    "arabic"
                ),

            "arabic_spaced":
                root_meta.get(
                    "arabic_spaced"
                ),

            "radicals":
                root_meta.get(
                    "radicals",
                    []
                ),

            "qac_occurrence_count":
                root_meta.get(
                    "occurrence_count",
                    0
                ),

            "direct_context_occurrence_count":
                0,

            "ambiguous_context_occurrence_count":
                0,

            "_gloss_counter":
                GlossCounter(),

            "_repeated_gloss_counter":
                GlossCounter(),

            "_pos_counts":
                Counter(),

            "_verb_form_counts":
                Counter(),

            "_lemma_data":
                {},

            "ambiguous_word_locations":
                [],
        }

    # --------------------------------------------------------
    # Join word glosses to root-bearing QAC stems
    # --------------------------------------------------------

    for word_location in sorted(
        root_segments_by_word,
        key=location_sort_key,
    ):
        root_segments = (
            root_segments_by_word[
                word_location
            ]
        )

        qf = qf_words.get(
            word_location
        )

        if qf is None:
            root_words_missing_qf.append(
                word_location
            )
            continue

        gloss = clean_gloss_display(
            qf.get(
                "translation_en"
            )
        )

        if not gloss:
            source_gloss_missing_count += 1

        # Distinct root-bearing segment identities, not just root IDs.
        # A whole Quran word with >1 root-bearing segment is semantically
        # ambiguous for whole-word English gloss assignment.
        if len(root_segments) > 1:
            multi_root_word_count += 1

            ambiguous_multi_root_words.append(
                {
                    "location":
                        word_location,

                    "quran_foundation":
                        {
                            "text_uthmani":
                                qf.get(
                                    "text_uthmani"
                                ),

                            "text_imlaei":
                                qf.get(
                                    "text_imlaei"
                                ),

                            "translation_en":
                                qf.get(
                                    "translation_en"
                                ),

                            "transliteration_en":
                                qf.get(
                                    "transliteration_en"
                                ),
                        },

                    "root_segments":
                        root_segments,

                    "all_qac_segments":
                        all_segments_by_word.get(
                            word_location,
                            [],
                        ),

                    "mapping_status":
                        "ambiguous_multi_root_stem",
                }
            )

            ambiguous_root_segment_count += (
                len(root_segments)
            )

            for segment in root_segments:
                root_id = segment[
                    "root"
                ]

                root_bucket = (
                    root_data.get(
                        root_id
                    )
                )

                if root_bucket is None:
                    continue

                root_bucket[
                    "ambiguous_context_occurrence_count"
                ] += 1

                root_bucket[
                    "ambiguous_word_locations"
                ].append(
                    word_location
                )

            # Deliberately DO NOT put this whole-word gloss into either
            # root's or lemma's gloss frequency distribution.
            continue

        # Exactly one root-bearing segment: direct whole-word context mapping.
        segment = root_segments[0]

        root_id = segment[
            "root"
        ]

        root_bucket = root_data.get(
            root_id
        )

        if root_bucket is None:
            # Should never happen if the canonical root index is aligned.
            continue

        direct_mapped_segment_count += 1
        direct_mapped_word_count += 1

        root_bucket[
            "direct_context_occurrence_count"
        ] += 1

        root_bucket[
            "_pos_counts"
        ][
            segment["tag"]
        ] += 1

        if segment[
            "verb_form"
        ]:
            root_bucket[
                "_verb_form_counts"
            ][
                segment[
                    "verb_form"
                ]
            ] += 1

        repeated_cluster = (
            repeated_gloss_cluster_by_location.get(
                word_location
            )
        )

        if repeated_cluster is None:
            context_gloss_scope = "whole_word"
            lexical_frequency_eligible = True

            direct_whole_word_gloss_occurrences += 1

            if gloss:
                root_bucket[
                    "_gloss_counter"
                ].add(
                    gloss
                )

        else:
            context_gloss_scope = (
                "adjacent_repeated_gloss"
            )

            lexical_frequency_eligible = False

            repeated_adjacent_gloss_root_occurrences += 1

            if gloss:
                root_bucket[
                    "_repeated_gloss_counter"
                ].add(
                    gloss
                )

        lemma_id = segment.get(
            "lemma_id"
        )

        lemma_key = (
            lemma_id
            if lemma_id is not None
            else "(missing)"
        )

        lemma_bucket = (
            root_bucket[
                "_lemma_data"
            ].setdefault(
                lemma_key,
                {
                    "id":
                        lemma_id,

                    "direct_context_occurrence_count":
                        0,

                    "_gloss_counter":
                        GlossCounter(),

                    "_repeated_gloss_counter":
                        GlossCounter(),

                    "_pos_counts":
                        Counter(),

                    "_verb_form_counts":
                        Counter(),

                    "occurrences":
                        [],
                },
            )
        )

        lemma_bucket[
            "direct_context_occurrence_count"
        ] += 1

        lemma_bucket[
            "_pos_counts"
        ][
            segment["tag"]
        ] += 1

        if segment[
            "verb_form"
        ]:
            lemma_bucket[
                "_verb_form_counts"
            ][
                segment[
                    "verb_form"
                ]
            ] += 1

        if gloss:
            if lexical_frequency_eligible:
                lemma_bucket[
                    "_gloss_counter"
                ].add(
                    gloss
                )
            else:
                lemma_bucket[
                    "_repeated_gloss_counter"
                ].add(
                    gloss
                )

        lemma_meta = (
            lemma_lookup.get(
                (
                    root_id,
                    lemma_id,
                )
            )
            if lemma_id is not None
            else None
        )

        if (
            lemma_id is not None
            and lemma_meta is None
        ):
            lemma_metadata_missing.append(
                {
                    "root":
                        root_id,

                    "lemma_id":
                        lemma_id,

                    "location":
                        word_location,
                }
            )

        lemma_bucket[
            "occurrences"
        ].append(
            {
                "location":
                    word_location,

                "segment_location":
                    segment[
                        "segment_location"
                    ],

                "context_gloss_scope":
                    context_gloss_scope,

                "lexical_frequency_eligible":
                    lexical_frequency_eligible,

                "repeated_gloss_cluster":
                    repeated_cluster,

                "quran_word":
                    {
                        "text_uthmani":
                            qf.get(
                                "text_uthmani"
                            ),

                        "text_imlaei":
                            qf.get(
                                "text_imlaei"
                            ),

                        "translation_en":
                            qf.get(
                                "translation_en"
                            ),

                        "transliteration_en":
                            qf.get(
                                "transliteration_en"
                            ),
                    },

                "morphology":
                    {
                        "tag":
                            segment[
                                "tag"
                            ],

                        "verb_form":
                            segment[
                                "verb_form"
                            ],

                        "aspect":
                            segment[
                                "aspect"
                            ],

                        "voice":
                            segment[
                                "voice"
                            ],
                    },
            }
        )

    # --------------------------------------------------------
    # Finalize JSON
    # --------------------------------------------------------

    roots_output = []

    total_root_occurrence_count = 0
    total_accounted_root_occurrences = 0

    for root_id in sorted(
        root_data
    ):
        bucket = root_data[
            root_id
        ]

        root_meta = root_lookup[
            root_id
        ]

        qac_occurrence_count = (
            bucket[
                "qac_occurrence_count"
            ]
        )

        direct_count = bucket[
            "direct_context_occurrence_count"
        ]

        ambiguous_count = bucket[
            "ambiguous_context_occurrence_count"
        ]

        total_root_occurrence_count += (
            qac_occurrence_count
        )

        total_accounted_root_occurrences += (
            direct_count
            + ambiguous_count
        )

        lemmas = []

        for lemma_id, lemma_bucket in (
            bucket[
                "_lemma_data"
            ].items()
        ):
            lemma_meta = (
                lemma_lookup.get(
                    (
                        root_id,
                        lemma_bucket["id"],
                    )
                )
                if lemma_bucket["id"] is not None
                else None
            )

            occurrences = (
                lemma_bucket[
                    "occurrences"
                ]
            )

            occurrences.sort(
                key=lambda item:
                    location_sort_key(
                        item[
                            "location"
                        ]
                    )
            )

            lemmas.append(
                {
                    "id":
                        lemma_bucket[
                            "id"
                        ],

                    "buckwalter":
                        (
                            lemma_meta.get(
                                "buckwalter"
                            )
                            if lemma_meta
                            else None
                        ),

                    "discriminator":
                        (
                            lemma_meta.get(
                                "discriminator"
                            )
                            if lemma_meta
                            else None
                        ),

                    "arabic":
                        (
                            lemma_meta.get(
                                "arabic"
                            )
                            if lemma_meta
                            else None
                        ),

                    "qac_occurrence_count":
                        (
                            lemma_meta.get(
                                "occurrence_count"
                            )
                            if lemma_meta
                            else None
                        ),

                    "direct_context_occurrence_count":
                        lemma_bucket[
                            "direct_context_occurrence_count"
                        ],

                    "pos_counts":
                        dict(
                            sorted(
                                lemma_bucket[
                                    "_pos_counts"
                                ].items()
                            )
                        ),

                    "verb_form_counts":
                        dict(
                            sorted(
                                lemma_bucket[
                                    "_verb_form_counts"
                                ].items()
                            )
                        ),

                    "context_glosses":
                        lemma_bucket[
                            "_gloss_counter"
                        ].to_json(),

                    "adjacent_repeated_context_glosses":
                        lemma_bucket[
                            "_repeated_gloss_counter"
                        ].to_json(),

                    "occurrences":
                        occurrences,
                }
            )

        lemmas.sort(
            key=lambda item: (
                -(
                    item[
                        "qac_occurrence_count"
                    ]
                    or 0
                ),
                item[
                    "id"
                ]
                or "",
            )
        )

        roots_output.append(
            {
                "root":
                    root_id,

                "arabic":
                    bucket[
                        "arabic"
                    ],

                "arabic_spaced":
                    bucket[
                        "arabic_spaced"
                    ],

                "radicals":
                    bucket[
                        "radicals"
                    ],

                "qac_occurrence_count":
                    qac_occurrence_count,

                "direct_context_occurrence_count":
                    direct_count,

                "ambiguous_context_occurrence_count":
                    ambiguous_count,

                "context_coverage_percent":
                    (
                        round(
                            (
                                direct_count
                                + ambiguous_count
                            )
                            / qac_occurrence_count
                            * 100,
                            2,
                        )
                        if qac_occurrence_count
                        else 0
                    ),

                "direct_gloss_coverage_percent":
                    (
                        round(
                            direct_count
                            / qac_occurrence_count
                            * 100,
                            2,
                        )
                        if qac_occurrence_count
                        else 0
                    ),

                "pos_counts":
                    dict(
                        sorted(
                            bucket[
                                "_pos_counts"
                            ].items()
                        )
                    ),

                "verb_form_counts":
                    dict(
                        sorted(
                            bucket[
                                "_verb_form_counts"
                            ].items()
                        )
                    ),

                "context_glosses":
                    bucket[
                        "_gloss_counter"
                    ].to_json(),

                "adjacent_repeated_context_glosses":
                    bucket[
                        "_repeated_gloss_counter"
                    ].to_json(),

                "lemmas":
                    lemmas,

                "ambiguous_word_locations":
                    sorted(
                        set(
                            bucket[
                                "ambiguous_word_locations"
                            ]
                        ),
                        key=location_sort_key,
                    ),
            }
        )

    # --------------------------------------------------------
    # QF repeated-adjacent gloss diagnostic
    # --------------------------------------------------------

    repeated_gloss_cluster_lengths = Counter(
        cluster["word_count"]
        for cluster in repeated_gloss_clusters
    )

    # --------------------------------------------------------
    # Main output
    # --------------------------------------------------------

    output = {
        "metadata": {
            "dataset":
                (
                    "Quran contextual English glosses "
                    "joined to QAC roots and lemmas"
                ),

            "context_dataset_version":
                2,

            "qac_morphology_source":
                QAC_MORPHOLOGY_FILE.name,

            "qac_root_index_source":
                QURAN_ROOT_INDEX_FILE.name,

            "quran_foundation_source":
                str(
                    QF_WBW_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "join_key":
                "surah:ayah:word",

            "semantic_policy": [
                (
                    "Quran Foundation word-by-word English "
                    "is treated as contextual gloss evidence, "
                    "not as a root definition."
                ),
                (
                    "A whole-word gloss is directly assigned "
                    "only when the QAC word contains exactly "
                    "one root-bearing segment."
                ),
                (
                    "Words with multiple root-bearing segments "
                    "are preserved as ambiguous and excluded "
                    "from direct root/lemma gloss frequencies."
                ),
                (
                    "Exact Quran Foundation gloss wording is "
                    "preserved; case-insensitive normalization "
                    "is used only for frequency aggregation."
                ),
                (
                    "If identical English glosses occur on "
                    "consecutive Quran word positions, those "
                    "occurrences are preserved separately as "
                    "adjacent repeated-gloss candidates and "
                    "excluded from primary lexical frequencies."
                ),
            ],
        },

        "summary": {
            "qac_root_count":
                len(roots_output),

            "qac_root_occurrence_count":
                total_root_occurrence_count,

            "direct_mapped_root_occurrences":
                direct_mapped_segment_count,

            "ambiguous_multi_root_segment_occurrences":
                ambiguous_root_segment_count,

            "accounted_root_occurrences":
                total_accounted_root_occurrences,

            "accounted_percent":
                round(
                    (
                        total_accounted_root_occurrences
                        / total_root_occurrence_count
                        * 100
                    )
                    if total_root_occurrence_count
                    else 0,
                    4,
                ),

            "words_with_multiple_root_bearing_segments":
                multi_root_word_count,

            "root_words_missing_quran_foundation":
                len(
                    root_words_missing_qf
                ),

            "source_gloss_missing_count":
                source_gloss_missing_count,

            "primary_whole_word_gloss_occurrences":
                direct_whole_word_gloss_occurrences,

            "root_occurrences_in_adjacent_repeated_gloss_clusters":
                repeated_adjacent_gloss_root_occurrences,

            "adjacent_repeated_gloss_cluster_count":
                len(
                    repeated_gloss_clusters
                ),

            "qf_word_locations_in_adjacent_repeated_gloss_clusters":
                len(
                    repeated_gloss_word_locations
                ),

            "lemma_metadata_missing_count":
                len(
                    lemma_metadata_missing
                ),
        },

        "roots":
            roots_output,

        "ambiguous_multi_root_words":
            ambiguous_multi_root_words,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    report = {
        "summary":
            output[
                "summary"
            ],

        "root_words_missing_quran_foundation":
            root_words_missing_qf,

        "lemma_metadata_missing":
            lemma_metadata_missing[
                :500
            ],

        "adjacent_repeated_gloss_audit": {
            "cluster_count":
                len(
                    repeated_gloss_clusters
                ),

            "qf_word_location_count":
                len(
                    repeated_gloss_word_locations
                ),

            "root_occurrence_count":
                repeated_adjacent_gloss_root_occurrences,

            "cluster_length_counts":
                dict(
                    sorted(
                        repeated_gloss_cluster_lengths.items()
                    )
                ),

            "examples":
                repeated_gloss_clusters[:250],

            "note":
                (
                    "These are conservative diagnostic candidates. "
                    "They remain available as contextual evidence "
                    "but are excluded from primary lexical-frequency "
                    "aggregation."
                ),
        },

        "ambiguous_multi_root_word_count":
            len(
                ambiguous_multi_root_words
            ),

        "ambiguous_multi_root_word_examples":
            ambiguous_multi_root_words[
                :100
            ],

        "output_file":
            str(
                OUTPUT_FILE.relative_to(
                    SCRIPT_DIR
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

    # --------------------------------------------------------
    # Sample
    # --------------------------------------------------------

    root_output_lookup = {
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
                    "Review sample of Quran-context "
                    "gloss aggregation"
                ),

            "roots_requested":
                SAMPLE_ROOTS,
        },

        "roots": [
            root_output_lookup[
                root
            ]
            for root in SAMPLE_ROOTS
            if root in root_output_lookup
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
        "QURAN CONTEXT GLOSS JOIN COMPLETE"
    )
    print("=" * 60)

    print(
        f"QAC roots:                     "
        f"{len(roots_output):,}"
    )

    print(
        f"QAC root occurrences:          "
        f"{total_root_occurrence_count:,}"
    )

    print(
        f"Direct gloss assignments:      "
        f"{direct_mapped_segment_count:,}"
    )

    print(
        f"Ambiguous multi-root segments: "
        f"{ambiguous_root_segment_count:,}"
    )

    print(
        f"Accounted occurrences:         "
        f"{total_accounted_root_occurrences:,}"
    )

    print(
        f"Accounted percent:             "
        f"{output['summary']['accounted_percent']:.4f}%"
    )

    print(
        f"Multi-root Quran words:         "
        f"{multi_root_word_count:,}"
    )

    print(
        f"Root words missing QF gloss:    "
        f"{len(root_words_missing_qf):,}"
    )

    print(
        f"Empty source glosses:           "
        f"{source_gloss_missing_count:,}"
    )

    print(
        f"Primary whole-word glosses:     "
        f"{direct_whole_word_gloss_occurrences:,}"
    )

    print(
        f"Repeated-gloss root occs:       "
        f"{repeated_adjacent_gloss_root_occurrences:,}"
    )

    print(
        f"Repeated-gloss clusters:        "
        f"{len(repeated_gloss_clusters):,}"
    )

    print(
        f"Missing lemma metadata:         "
        f"{len(lemma_metadata_missing):,}"
    )

    print()
    print(
        "Context dataset:\n"
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
        "quran_context_glosses_report_v2.json "
        "and quran_context_glosses_sample_v2.json "
        "to ChatGPT."
    )


if __name__ == "__main__":
    main()
