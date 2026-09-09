#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import html
import json
import math
import re
from pathlib import Path
from typing import Any


# ============================================================
# Paths / constants
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

COMBINED_FILE = (
    OUTPUT_DIR
    / "quran_root_semantics_combined_v2.json"
)

LANE_FILE = (
    OUTPUT_DIR
    / "lane_complete_root_evidence_v1.json"
)

FORM_INVENTORY_FILE = (
    OUTPUT_DIR
    / "quran_form_inventory_v1.json"
)

PILOT_OUTPUT_FILE = (
    OUTPUT_DIR
    / "root_synthesis_packets_pilot_v3.json"
)

PILOT_REPORT_FILE = (
    OUTPUT_DIR
    / "root_synthesis_packets_pilot_report_v3.json"
)

FULL_OUTPUT_FILE = (
    OUTPUT_DIR
    / "root_synthesis_packets_v3.json"
)

FULL_REPORT_FILE = (
    OUTPUT_DIR
    / "root_synthesis_packets_report_v3.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "root_synthesis_packets_sample_v3.json"
)

PILOT_ROOTS = [
    "rHm",
    "ktb",
    "Aty",
    "Hqq",
    "Slw",
]

PACKET_VERSION = 3

DEFAULT_QF_EXAMPLES_PER_GLOSS = 2
DEFAULT_LARGE_PACKET_CHAR_WARNING = 300_000


# ============================================================
# Final synthesis contract
# ============================================================

FINAL_SYNTHESIS_CONTRACT = {
    "purpose": (
        "Produce the final public Quran-root dictionary artifact for one "
        "canonical QAC root directly from the supplied evidence. This is "
        "not an intermediate Lane/Maqayis/Mufradat normalization pass."
    ),

    "source_roles": {
        "qac_forms": (
            "Canonical Quran morphology, form-group identity, occurrence "
            "counts, and Quran locations."
        ),
        "lane_primary": (
            "Broad Classical Arabic lexical evidence directly attached to "
            "the canonical QAC root."
        ),
        "lane_cross_reference_context": (
            "Interpretive context supplied because Lane explicitly points "
            "to it. It is not by itself proof that the supplemental entry "
            "belongs to this QAC root."
        ),
        "maqayis": (
            "Root-level semantic principle/orientation evidence. A root "
            "principle must not automatically be presented as a direct "
            "meaning of every Quran form."
        ),
        "mufradat": (
            "Quran-focused lexical discussion. shared_ambiguous_entries "
            "must not be treated as wholly unique to this root."
        ),
        "quran_foundation_context": (
            "Contextual English rendering evidence only. It may help map "
            "or illustrate a sense, but it cannot independently create a "
            "lexical dictionary meaning."
        ),
    },

    "hard_rules": [
        (
            "Account for every supplied QAC form_group_id exactly once in "
            "qac_form_accounting."
        ),
        (
            "For each QAC form group use one disposition: DISPLAY, MERGE, "
            "or EXCLUDE_WITH_REASON."
        ),
        (
            "Normalize public Arabic headwords when needed; do not assume "
            "the QAC lemma display candidate is automatically the ideal "
            "classical dictionary citation form."
        ),
        (
            "A Quran-form lexical meaning must have lexical support from "
            "Lane and/or Mufradat. Quran Foundation contextual English "
            "alone is insufficient."
        ),
        (
            "Maqayis may support root_idea and semantic development, but "
            "its root principle is not automatically a direct form sense."
        ),
        (
            "Keep broader Classical Arabic meanings visibly separate from "
            "Quran-attested form/sense meanings."
        ),
        (
            "Use only source_refs present in source_ref_registry."
        ),
        (
            "Use only Quran word/verse locations supplied in the packet."
        ),
        (
            "Examples should demonstrate distinct senses or constructions "
            "when possible rather than merely selecting first occurrences."
        ),
        (
            "Public-facing definitions must be source-neutral. Put "
            "provenance in source_refs rather than phrases such as "
            "'Lane says'."
        ),
        (
            "Review every Lane primary source_unit. If a unit states a "
            "materially independent lexical meaning, represent it or "
            "genuinely subsume it under another represented meaning. "
            "Pointer-only, grammatical, pronunciation, example-only, "
            "and editorial units need not become meanings."
        ),
        (
            "Do not output unit-by-unit Lane disposition bookkeeping. "
            "The source_units are semantic reading boundaries, not a "
            "request for an archival classification table."
        ),
    ],

    "target_output_shape": {
        "root": "canonical QAC root id",
        "arabic": "Arabic root",
        "root_idea": {
            "summary": "short public explanation",
            "development": "brief semantic development if supported",
            "source_refs": [],
        },
        "qac_form_accounting": [
            {
                "form_group_id": "qac-form:...",
                "disposition": "DISPLAY | MERGE | EXCLUDE_WITH_REASON",
                "target_public_form_id": (
                    "required for DISPLAY/MERGE as appropriate"
                ),
                "reason": (
                    "required for merge/exclusion when not self-evident"
                ),
            }
        ],
        "quranic_forms": [
            {
                "public_form_id": "stable root-local id",
                "form_group_ids": [],
                "headword_arabic": "",
                "public_pos_label": "",
                "verb_form": None,
                "occurrence_count": 0,
                "senses": [
                    {
                        "sense_id": "stable root-local id",
                        "definition": "",
                        "usage_conditions": "",
                        "source_refs": [],
                    }
                ],
                "quran_examples": [
                    {
                        "verse_key": "surah:ayah",
                        "word_location": "surah:ayah:word",
                        "context_gloss": "",
                        "sense_ids": [],
                    }
                ],
            }
        ],
        "other_classical_meanings": [
            {
                "headword_arabic": "",
                "definition": "",
                "usage_conditions": "",
                "source_refs": [],
            }
        ],
        "cautions": [],
        "unassigned_or_ambiguous_evidence": [],
    },
}


# ============================================================
# Generic helpers
# ============================================================

WHITESPACE_RE = re.compile(r"\s+")


def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8",
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


def compact_json_chars(
    value: Any,
) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def root_lookup(
    payload: dict,
) -> dict[str, dict]:
    lookup = {}

    for record in payload.get(
        "roots",
        [],
    ):
        root = record.get(
            "root"
        )

        if not root:
            raise RuntimeError(
                "Found root record without a root id."
            )

        if root in lookup:
            raise RuntimeError(
                f"Duplicate root record: {root}"
            )

        lookup[
            root
        ] = record

    return lookup


def normalize_gloss(
    value: str | None,
) -> str:
    if not value:
        return ""

    text = html.unescape(
        value
    )

    text = WHITESPACE_RE.sub(
        " ",
        text,
    ).strip()

    return text.casefold()


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return default


# ============================================================
# Source-reference registry
# ============================================================

def register_ref(
    registry: dict[str, dict],
    *,
    source_ref: str,
    source: str,
    role: str,
    metadata: dict | None = None,
) -> None:
    if not source_ref:
        return

    existing = registry.get(
        source_ref
    )

    if existing is None:
        registry[
            source_ref
        ] = {
            "source":
                source,

            "roles": [
                role
            ],

            "metadata":
                metadata
                or {},
        }

        return

    if existing.get(
        "source"
    ) != source:
        raise RuntimeError(
            "Source-ref collision across different source types: "
            f"{source_ref}"
        )

    roles = existing.setdefault(
        "roles",
        [],
    )

    if role not in roles:
        roles.append(
            role
        )

    if metadata:
        existing_meta = existing.setdefault(
            "metadata",
            {},
        )

        for key, value in (
            metadata.items()
        ):
            if (
                key not in existing_meta
                or existing_meta[
                    key
                ] in {
                    None,
                    "",
                }
            ):
                existing_meta[
                    key
                ] = value


# ============================================================
# QAC form evidence
# ============================================================

def prepare_qac_forms(
    root_record: dict,
    registry: dict[str, dict],
) -> dict:
    prepared = copy.deepcopy(
        root_record
    )

    for form in prepared.get(
        "forms",
        [],
    ):
        ref = form.get(
            "form_group_id"
        )

        register_ref(
            registry,
            source_ref=ref,
            source="qac",
            role="quran_form_group",
            metadata={
                "qac_lemma_arabic_candidate":
                    form.get(
                        "qac_lemma_arabic_candidate"
                    ),

                "public_morphology_hint":
                    form.get(
                        "public_morphology_hint"
                    ),

                "occurrence_count":
                    form.get(
                        "occurrence_count"
                    ),
            },
        )

    return prepared


# ============================================================
# Quran Foundation contextual evidence compaction
# ============================================================

def compact_occurrence(
    occurrence: dict,
    registry: dict[str, dict],
) -> dict:
    word_location = (
        occurrence.get(
            "location"
        )
        or occurrence.get(
            "word_location"
        )
    )

    quran_word = (
        occurrence.get(
            "quran_word"
        )
        or {}
    )

    verse_key = None

    if word_location:
        parts = str(
            word_location
        ).split(
            ":"
        )

        if len(parts) >= 2:
            verse_key = (
                f"{parts[0]}:{parts[1]}"
            )

    source_ref = (
        f"qf:word:{word_location}"
        if word_location
        else ""
    )

    register_ref(
        registry,
        source_ref=source_ref,
        source="quran_foundation",
        role="contextual_english_only",
        metadata={
            "word_location":
                word_location,

            "verse_key":
                verse_key,
        },
    )

    return {
        "source_ref":
            source_ref
            or None,

        "verse_key":
            verse_key,

        "word_location":
            word_location,

        "segment_location":
            occurrence.get(
                "segment_location"
            ),

        "context_gloss_scope":
            occurrence.get(
                "context_gloss_scope"
            ),

        "lexical_frequency_eligible":
            occurrence.get(
                "lexical_frequency_eligible"
            ),

        "repeated_gloss_cluster":
            occurrence.get(
                "repeated_gloss_cluster"
            ),

        "quran_word": {
            "text_uthmani":
                quran_word.get(
                    "text_uthmani"
                ),

            "text_imlaei":
                quran_word.get(
                    "text_imlaei"
                ),

            "translation_en":
                quran_word.get(
                    "translation_en"
                ),

            "transliteration_en":
                quran_word.get(
                    "transliteration_en"
                ),
        },

        "morphology":
            occurrence.get(
                "morphology"
            )
            or {},
    }


def compact_gloss_records(
    gloss_records: list[dict] | None,
) -> list[dict]:
    output = []

    for record in (
        gloss_records
        or []
    ):
        output.append(
            {
                "gloss":
                    record.get(
                        "gloss"
                    ),

                "normalized_gloss":
                    (
                        record.get(
                            "normalized_gloss"
                        )
                        or normalize_gloss(
                            record.get(
                                "gloss"
                            )
                        )
                    ),

                "count":
                    safe_int(
                        record.get(
                            "count"
                        )
                    ),
            }
        )

    return output


def compact_qf_context(
    context: dict,
    registry: dict[str, dict],
    *,
    examples_per_gloss: int,
) -> dict:
    if not isinstance(
        context,
        dict,
    ):
        return {}

    summary_keys = [
        "root",
        "arabic",
        "arabic_spaced",
        "radicals",
        "qac_occurrence_count",
        "direct_context_occurrence_count",
        "ambiguous_context_occurrence_count",
        "context_coverage_percent",
        "direct_gloss_coverage_percent",
        "pos_counts",
        "verb_form_counts",
    ]

    output = {
        key:
            copy.deepcopy(
                context.get(
                    key
                )
            )
        for key in summary_keys
        if key in context
    }

    # Root-level frequency overview. This is useful orientation only.
    output[
        "root_context_glosses"
    ] = compact_gloss_records(
        context.get(
            "context_glosses"
        )
    )

    compact_lemmas = []

    for lemma in context.get(
        "lemmas",
        [],
    ):
        occurrences = (
            lemma.get(
                "occurrences"
            )
            or []
        )

        occurrences_by_gloss = {}

        for occurrence in occurrences:
            quran_word = (
                occurrence.get(
                    "quran_word"
                )
                or {}
            )

            normalized = normalize_gloss(
                quran_word.get(
                    "translation_en"
                )
            )

            occurrences_by_gloss.setdefault(
                normalized,
                [],
            ).append(
                occurrence
            )

        gloss_evidence = []

        for gloss in lemma.get(
            "context_glosses",
            [],
        ):
            normalized = (
                gloss.get(
                    "normalized_gloss"
                )
                or normalize_gloss(
                    gloss.get(
                        "gloss"
                    )
                )
            )

            candidates = list(
                occurrences_by_gloss.get(
                    normalized,
                    [],
                )
            )

            # Prefer ordinary whole-word/lexical-frequency-eligible
            # examples; keep stable source order otherwise.
            candidates.sort(
                key=lambda item: (
                    0
                    if item.get(
                        "lexical_frequency_eligible"
                    )
                    else 1,

                    str(
                        item.get(
                            "location"
                        )
                        or ""
                    ),
                )
            )

            examples = [
                compact_occurrence(
                    item,
                    registry,
                )
                for item
                in candidates[
                    :examples_per_gloss
                ]
            ]

            gloss_evidence.append(
                {
                    "gloss":
                        gloss.get(
                            "gloss"
                        ),

                    "normalized_gloss":
                        normalized,

                    "count":
                        safe_int(
                            gloss.get(
                                "count"
                            )
                        ),

                    "example_occurrences":
                        examples,
                }
            )

        compact_lemmas.append(
            {
                "id":
                    lemma.get(
                        "id"
                    ),

                "buckwalter":
                    lemma.get(
                        "buckwalter"
                    ),

                "discriminator":
                    lemma.get(
                        "discriminator"
                    ),

                "arabic":
                    lemma.get(
                        "arabic"
                    ),

                "qac_occurrence_count":
                    lemma.get(
                        "qac_occurrence_count"
                    ),

                "direct_context_occurrence_count":
                    lemma.get(
                        "direct_context_occurrence_count"
                    ),

                "pos_counts":
                    copy.deepcopy(
                        lemma.get(
                            "pos_counts"
                        )
                        or {}
                    ),

                "verb_form_counts":
                    copy.deepcopy(
                        lemma.get(
                            "verb_form_counts"
                        )
                        or {}
                    ),

                # Every distinct ordinary contextual gloss is kept.
                # Only repeated occurrence examples are bounded.
                "gloss_evidence":
                    gloss_evidence,

                # Preserve quarantined repeated-gloss categories in
                # compact form without treating them as lexical proof.
                "adjacent_repeated_context_glosses":
                    compact_gloss_records(
                        lemma.get(
                            "adjacent_repeated_context_glosses"
                        )
                    ),
            }
        )

    output[
        "lemmas"
    ] = compact_lemmas

    # Preserve any explicit ambiguous/multi-root contextual metadata
    # without expanding it into lexical claims.
    for key in [
        "ambiguous_multi_root_context",
        "ambiguous_context",
        "multi_root_word_locations",
    ]:
        if key in context:
            output[
                key
            ] = copy.deepcopy(
                context[
                    key
                ]
            )

    return output


# ============================================================
# Lane evidence compaction
# ============================================================

def lane_unit_flags(
    value: dict = None,
) -> dict:
    value = value if isinstance(value, dict) else {}

    return {
        "mentions_quran":
            bool(value.get("mentions_quran")),

        "lane_marks_tropical":
            bool(value.get("lane_marks_tropical")),

        "lane_marks_assumed_tropical":
            bool(value.get("lane_marks_assumed_tropical")),

        "mentions_primary_signification":
            bool(value.get("mentions_primary_signification")),
    }


def build_lane_source_units(
    *,
    qac_root: str,
    entry: dict,
) -> list[dict]:
    """
    Deterministic semantic reading boundaries from Lane's parsed
    sense_groups. A source_unit is NOT assumed to equal one lexical sense.
    No LLM is used and no disposition is assigned.
    """
    entry_id = int(
        entry["entry_id"]
    )

    dictionary = (
        entry.get("dictionary")
        or {}
    )

    sense_groups = (
        dictionary.get("sense_groups")
        or []
    )

    units = []

    for group_index, group in enumerate(
        sense_groups,
        start=1,
    ):
        major_number = group.get(
            "major_number"
        )

        main = (
            group.get("main")
            or {}
        )

        main_text = (
            main.get("text")
            or ""
        ).strip()

        if main_text:
            units.append(
                {
                    "unit_id":
                        (
                            f"lane-unit:{qac_root}:"
                            f"{entry_id}:g{group_index}:main"
                        ),

                    "lane_marker":
                        main.get("lane_marker"),

                    "major_number":
                        major_number,

                    "sub_number":
                        None,

                    "text":
                        main_text,

                    "flags":
                        lane_unit_flags(
                            main.get("flags")
                        ),
                }
            )

        # Lane's parsed sub_number is usually unique within a sense group,
        # but the full corpus contains a few legitimate repeated source
        # numbers. Preserve the source-native number while making the
        # internal unit id collision-safe. The first occurrence keeps the
        # simple id; only later repeats receive :occN.
        sub_id_occurrences = {}

        for sub_index, sub in enumerate(
            (
                group.get("sub_senses")
                or []
            ),
            start=1,
        ):
            sub_text = (
                sub.get("text")
                or ""
            ).strip()

            if not sub_text:
                continue

            source_sub_number = sub.get(
                "sub_number"
            )

            sub_label = (
                source_sub_number
                if source_sub_number is not None
                else sub_index
            )

            base_unit_id = (
                f"lane-unit:{qac_root}:"
                f"{entry_id}:g{group_index}:sub{sub_label}"
            )

            occurrence_index = (
                sub_id_occurrences.get(
                    base_unit_id,
                    0,
                )
                + 1
            )

            sub_id_occurrences[
                base_unit_id
            ] = occurrence_index

            unit_id = base_unit_id

            if occurrence_index > 1:
                unit_id = (
                    f"{base_unit_id}:occ{occurrence_index}"
                )

            units.append(
                {
                    "unit_id":
                        unit_id,

                    "lane_marker":
                        sub.get("lane_marker"),

                    "major_number":
                        major_number,

                    "sub_number":
                        source_sub_number,

                    "text":
                        sub_text,

                    "flags":
                        lane_unit_flags(
                            sub.get("flags")
                        ),
                }
            )

    # Fallback for an entry that did not parse into sense_groups.
    if not units:
        dictionary_text = (
            dictionary.get("plain_text")
            or ""
        ).strip()

        if dictionary_text:
            units.append(
                {
                    "unit_id":
                        (
                            f"lane-unit:{qac_root}:"
                            f"{entry_id}:whole"
                        ),

                    "lane_marker":
                        None,

                    "major_number":
                        None,

                    "sub_number":
                        None,

                    "text":
                        dictionary_text,

                    "flags": {
                        "mentions_quran": False,
                        "lane_marks_tropical": False,
                        "lane_marks_assumed_tropical": False,
                        "mentions_primary_signification": False,
                    },
                }
            )

    return units


def lane_entry_text(
    entry: dict,
) -> str:
    """Return the exact Lane plain text from current or older schemas."""
    dictionary = entry.get(
        "dictionary"
    ) or {}

    if isinstance(
        dictionary,
        dict,
    ):
        value = dictionary.get(
            "plain_text"
        )

        if isinstance(
            value,
            str,
        ) and value:
            return value

    for key in [
        "source_text",
        "text",
        "entry_text",
    ]:
        value = entry.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value:
            return value

    return ""


def lane_entry_cross_refs(
    entry: dict,
) -> list:
    dictionary = entry.get(
        "dictionary"
    ) or {}

    if isinstance(
        dictionary,
        dict,
    ):
        refs = dictionary.get(
            "cross_references"
        )

        if isinstance(
            refs,
            list,
        ):
            return copy.deepcopy(
                refs
            )

    direct = entry.get(
        "cross_references"
    )

    if isinstance(
        direct,
        list,
    ):
        return copy.deepcopy(
            direct
        )

    hints = (
        entry.get(
            "parser_hints"
        )
        or {}
    )

    refs = hints.get(
        "cross_references"
    )

    return (
        copy.deepcopy(
            refs
        )
        if isinstance(
            refs,
            list,
        )
        else []
    )


def compact_lane_entry(
    entry: dict,
    registry: dict[str, dict],
    *,
    role: str,
    qac_root: str,
) -> dict:
    entry_id = entry.get(
        "entry_id",
        entry.get(
            "id"
        ),
    )

    source_ref = (
        entry.get(
            "source_ref"
        )
        or (
            f"lane:entry:{entry_id}"
            if entry_id is not None
            else ""
        )
    )

    register_ref(
        registry,
        source_ref=source_ref,
        source="lane",
        role=role,
        metadata={
            "entry_id":
                entry_id,

            "headword":
                entry.get(
                    "headword"
                ),

            "page":
                (
                    entry.get(
                        "source"
                    )
                    or {}
                ).get(
                    "page"
                )
                if isinstance(
                    entry.get(
                        "source"
                    ),
                    dict,
                )
                else entry.get(
                    "page"
                ),
        },
    )

    text = lane_entry_text(
        entry
    )

    if not text:
        raise RuntimeError(
            "Lane entry is missing source text: "
            f"entry_id={entry_id!r}"
        )

    result = {
        "entry_id":
            entry_id,

        "source_ref":
            source_ref,

        "node_id":
            entry.get(
                "node_id",
                entry.get(
                    "nodeid"
                ),
            ),

        "headword":
            entry.get(
                "headword"
            ),

        "word":
            entry.get(
                "word"
            ),

        "bareword":
            entry.get(
                "bareword"
            ),

        "buckwalter_word":
            entry.get(
                "buckwalter_word",
                entry.get(
                    "bword"
                ),
            ),

        "itype":
            copy.deepcopy(
                entry.get(
                    "itype"
                )
            ),

        "pos_codes":
            copy.deepcopy(
                entry.get(
                    "pos_codes"
                )
                or []
            ),

        "source":
            copy.deepcopy(
                entry.get(
                    "source"
                )
                or {
                    key:
                        entry.get(
                            key
                        )
                    for key in [
                        "page",
                        "file",
                        "nodenum",
                        "supplement",
                        "entry_type",
                        "datasource",
                    ]
                    if key in entry
                }
            ),

        "cross_references":
            lane_entry_cross_refs(
                entry
            ),
    }

    if role == "direct_lexical_evidence":
        # Do not duplicate the giant source_text here. The same primary
        # lexical prose is exposed once through deterministic source_units.
        result["source_units"] = build_lane_source_units(
            qac_root=qac_root,
            entry=entry,
        )

    else:
        # Cross-reference targets are context only; they do not create
        # source-unit coverage obligations for this root.
        result["source_text"] = text

    return result


def prepare_lane(
    lane_root: dict,
    registry: dict[str, dict],
    *,
    qac_root: str,
) -> dict:
    primary = (
        lane_root.get(
            "primary_lane"
        )
        or {}
    )

    primary_entries = [
        compact_lane_entry(
            entry,
            registry,
            role="direct_lexical_evidence",
            qac_root=qac_root,
        )
        for entry in primary.get(
            "entries",
            [],
        )
    ]

    xref_context = (
        lane_root.get(
            "cross_reference_context"
        )
        or {}
    )

    compact_context_items = []

    for item in xref_context.get(
        "entries",
        [],
    ):
        if isinstance(
            item,
            dict,
        ) and isinstance(
            item.get(
                "entry"
            ),
            dict,
        ):
            compacted = {
                key:
                    copy.deepcopy(
                        value
                    )
                for key, value
                in item.items()
                if key != "entry"
            }

            compacted[
                "entry"
            ] = compact_lane_entry(
                item[
                    "entry"
                ],
                registry,
                role="cross_reference_context_only",
                qac_root=qac_root,
            )

            compact_context_items.append(
                compacted
            )

        elif isinstance(
            item,
            dict,
        ):
            compact_context_items.append(
                {
                    "entry":
                        compact_lane_entry(
                            item,
                            registry,
                            role=(
                                "cross_reference_context_only"
                            ),
                            qac_root=qac_root,
                        )
                }
            )

    return {
        "lane_match":
            copy.deepcopy(
                lane_root.get(
                    "lane_match"
                )
            ),

        "primary": {
            "entry_count":
                len(
                    primary_entries
                ),

            "root_context":
                copy.deepcopy(
                    primary.get(
                        "root_context"
                    )
                    or {}
                ),

            "entries":
                primary_entries,
        },

        "cross_reference_context": {
            "policy":
                xref_context.get(
                    "policy"
                )
                or (
                    "Context only. These entries are supplied because "
                    "Lane explicitly references them. They are not direct "
                    "evidence of root membership."
                ),

            "entry_count":
                len(
                    compact_context_items
                ),

            "entries":
                compact_context_items,

            "unresolved_references":
                copy.deepcopy(
                    xref_context.get(
                        "unresolved_references"
                    )
                    or []
                ),
        },

        "closure_audit":
            copy.deepcopy(
                lane_root.get(
                    "closure_audit"
                )
                or {}
            ),
    }


# ============================================================
# Maqayis / Mufradat compaction
# ============================================================

def compact_maqayis(
    maq: dict | None,
    registry: dict[str, dict],
) -> dict:
    if not isinstance(
        maq,
        dict,
    ):
        return {
            "match": None,
            "entries": [],
        }

    evidence = maq.get(
        "evidence"
    )

    entries = []

    if isinstance(
        evidence,
        dict,
    ):
        source_entries = (
            evidence.get(
                "entries"
            )
            or []
        )
    else:
        source_entries = []

    for entry in source_entries:
        row_id = entry.get(
            "row_id"
        )

        ref = (
            f"maqayis:row:{row_id}"
            if row_id is not None
            else ""
        )

        register_ref(
            registry,
            source_ref=ref,
            source="maqayis",
            role="root_principle_evidence",
            metadata={
                "row_id":
                    row_id,

                "heading":
                    entry.get(
                        "heading"
                    ),
            },
        )

        entries.append(
            {
                "source_ref":
                    ref
                    or None,

                "row_id":
                    row_id,

                "heading":
                    entry.get(
                        "heading"
                    ),

                "arabic_text_raw":
                    entry.get(
                        "arabic_text_raw"
                    ),

                "principle_candidates":
                    copy.deepcopy(
                        entry.get(
                            "principle_candidates"
                        )
                        or {}
                    ),
            }
        )

    return {
        "match":
            copy.deepcopy(
                maq.get(
                    "match"
                )
            ),

        "entries":
            entries,
    }


def compact_mufradat_entry(
    entry: dict,
    registry: dict[str, dict],
    *,
    role: str,
) -> dict:
    row_id = entry.get(
        "row_id",
        entry.get(
            "id"
        ),
    )

    ref = (
        f"mufradat:row:{row_id}"
        if row_id is not None
        else ""
    )

    register_ref(
        registry,
        source_ref=ref,
        source="mufradat",
        role=role,
        metadata={
            "row_id":
                row_id,

            "heading":
                entry.get(
                    "heading",
                    entry.get(
                        "word"
                    ),
                ),
        },
    )

    return {
        "source_ref":
            ref
            or None,

        "row_id":
            row_id,

        "heading":
            entry.get(
                "heading",
                entry.get(
                    "word"
                ),
            ),

        "best_method":
            entry.get(
                "best_method"
            ),

        "assignment":
            entry.get(
                "assignment"
            ),

        "candidate_qac_roots":
            copy.deepcopy(
                entry.get(
                    "candidate_qac_roots"
                )
                or []
            ),

        "semantic_use_policy":
            entry.get(
                "semantic_use_policy"
            ),

        "arabic_text_raw":
            (
                entry.get(
                    "arabic_text_raw"
                )
                or entry.get(
                    "meanings"
                )
            ),
    }


def compact_mufradat(
    muf: dict | None,
    registry: dict[str, dict],
) -> dict:
    if not isinstance(
        muf,
        dict,
    ):
        return {
            "match": None,
            "unique_entries": [],
            "shared_ambiguous_entries": [],
        }

    evidence = muf.get(
        "evidence"
    )

    if isinstance(
        evidence,
        dict,
    ):
        unique_source = (
            evidence.get(
                "entries"
            )
            or []
        )

        shared_source = (
            evidence.get(
                "shared_ambiguous_entries"
            )
            or []
        )

    else:
        unique_source = []
        shared_source = []

    unique_entries = [
        compact_mufradat_entry(
            entry,
            registry,
            role="quran_focused_lexical_evidence",
        )
        for entry in unique_source
    ]

    shared_entries = [
        compact_mufradat_entry(
            entry,
            registry,
            role="shared_ambiguous_context",
        )
        for entry in shared_source
    ]

    return {
        "match":
            copy.deepcopy(
                muf.get(
                    "match"
                )
            ),

        "unique_entries":
            unique_entries,

        "shared_ambiguous_entries":
            shared_entries,
    }


# ============================================================
# Packet construction / reporting
# ============================================================

def source_text_char_counts(
    packet: dict,
) -> dict:
    evidence = packet[
        "evidence"
    ]

    lane = evidence[
        "lane"
    ]

    lane_primary_chars = sum(
        len(
            unit.get(
                "text"
            )
            or ""
        )
        for entry
        in lane[
            "primary"
        ][
            "entries"
        ]
        for unit
        in entry.get(
            "source_units",
            []
        )
    )

    lane_context_chars = sum(
        len(
            (
                item.get(
                    "entry"
                )
                or {}
            ).get(
                "source_text"
            )
            or ""
        )
        for item
        in lane[
            "cross_reference_context"
        ][
            "entries"
        ]
    )

    maqayis_chars = sum(
        len(
            entry.get(
                "arabic_text_raw"
            )
            or ""
        )
        for entry
        in evidence[
            "maqayis"
        ][
            "entries"
        ]
    )

    muf_unique_chars = sum(
        len(
            entry.get(
                "arabic_text_raw"
            )
            or ""
        )
        for entry
        in evidence[
            "mufradat"
        ][
            "unique_entries"
        ]
    )

    muf_shared_chars = sum(
        len(
            entry.get(
                "arabic_text_raw"
            )
            or ""
        )
        for entry
        in evidence[
            "mufradat"
        ][
            "shared_ambiguous_entries"
        ]
    )

    return {
        "lane_primary_source_text_chars":
            lane_primary_chars,

        "lane_cross_reference_context_text_chars":
            lane_context_chars,

        "maqayis_source_text_chars":
            maqayis_chars,

        "mufradat_unique_source_text_chars":
            muf_unique_chars,

        "mufradat_shared_source_text_chars":
            muf_shared_chars,

        "qac_forms_json_chars":
            compact_json_chars(
                evidence[
                    "qac_forms"
                ]
            ),

        "qf_compact_json_chars":
            compact_json_chars(
                evidence[
                    "quran_contextual_english"
                ]
            ),
    }


def build_packet(
    *,
    root: str,
    combined_root: dict,
    lane_root: dict,
    form_root: dict,
    qf_examples_per_gloss: int,
) -> dict:
    registry: dict[
        str,
        dict
    ] = {}

    qac_forms = prepare_qac_forms(
        form_root,
        registry,
    )

    qf_context = (
        combined_root.get(
            "quran",
            {}
        ).get(
            "contextual_english",
            {}
        )
        or {}
    )

    compact_qf = compact_qf_context(
        qf_context,
        registry,
        examples_per_gloss=
            qf_examples_per_gloss,
    )

    lane = prepare_lane(
        lane_root,
        registry,
        qac_root=root,
    )

    maqayis = compact_maqayis(
        (
            combined_root.get(
                "root_principles",
                {}
            ).get(
                "maqayis"
            )
        ),
        registry,
    )

    mufradat = compact_mufradat(
        (
            combined_root.get(
                "quranic_lexicon",
                {}
            ).get(
                "mufradat"
            )
        ),
        registry,
    )

    packet = {
        "packet_id":
            (
                f"root-synthesis:{root}:v{PACKET_VERSION}"
            ),

        "version":
            PACKET_VERSION,

        "root":
            root,

        "arabic":
            form_root.get(
                "arabic"
            )
            or combined_root.get(
                "arabic"
            )
            or lane_root.get(
                "arabic"
            ),

        "generation_contract":
            copy.deepcopy(
                FINAL_SYNTHESIS_CONTRACT
            ),

        "evidence": {
            "qac_forms":
                qac_forms,

            "quran_contextual_english":
                compact_qf,

            "lane":
                lane,

            "maqayis":
                maqayis,

            "mufradat":
                mufradat,
        },

        "source_ref_registry":
            {
                ref:
                    registry[
                        ref
                    ]
                for ref
                in sorted(
                    registry
                )
            },
    }

    packet[
        "input_integrity"
    ] = {
        "qac_form_group_count":
            len(
                qac_forms.get(
                    "forms",
                    []
                )
            ),

        "qac_occurrence_count":
            qac_forms.get(
                "qac_occurrence_count"
            ),

        "qac_form_occurrence_sum":
            sum(
                safe_int(
                    form.get(
                        "occurrence_count"
                    )
                )
                for form
                in qac_forms.get(
                    "forms",
                    []
                )
            ),

        "lane_primary_entry_count":
            len(
                lane[
                    "primary"
                ][
                    "entries"
                ]
            ),

        "lane_primary_source_unit_count":
            sum(
                len(
                    entry.get(
                        "source_units",
                        []
                    )
                )
                for entry
                in lane[
                    "primary"
                ][
                    "entries"
                ]
            ),

        "lane_cross_reference_context_entry_count":
            len(
                lane[
                    "cross_reference_context"
                ][
                    "entries"
                ]
            ),

        "lane_unresolved_reference_count":
            len(
                lane[
                    "cross_reference_context"
                ][
                    "unresolved_references"
                ]
            ),

        "maqayis_entry_count":
            len(
                maqayis[
                    "entries"
                ]
            ),

        "mufradat_unique_entry_count":
            len(
                mufradat[
                    "unique_entries"
                ]
            ),

        "mufradat_shared_ambiguous_entry_count":
            len(
                mufradat[
                    "shared_ambiguous_entries"
                ]
            ),

        "source_ref_count":
            len(
                registry
            ),
    }

    packet[
        "source_text_char_counts"
    ] = source_text_char_counts(
        packet
    )

    return packet


def validate_packet_inputs(
    packet: dict,
) -> list[str]:
    errors = []

    integrity = packet[
        "input_integrity"
    ]

    if (
        integrity[
            "qac_form_occurrence_sum"
        ]
        != integrity[
            "qac_occurrence_count"
        ]
    ):
        errors.append(
            "QAC form-group occurrence sum does not match root "
            "occurrence count."
        )

    forms = (
        packet[
            "evidence"
        ][
            "qac_forms"
        ].get(
            "forms",
            []
        )
    )

    form_ids = [
        form.get(
            "form_group_id"
        )
        for form in forms
    ]

    if (
        len(
            form_ids
        )
        != len(
            set(
                form_ids
            )
        )
    ):
        errors.append(
            "Duplicate QAC form_group_id values."
        )

    if any(
        not value
        for value in form_ids
    ):
        errors.append(
            "QAC form without form_group_id."
        )

    if (
        integrity[
            "lane_unresolved_reference_count"
        ]
        > 0
    ):
        errors.append(
            "Lane complete evidence unexpectedly contains unresolved "
            "cross-reference context."
        )

    primary_entries = (
        packet[
            "evidence"
        ][
            "lane"
        ][
            "primary"
        ][
            "entries"
        ]
    )

    seen_unit_ids = set()

    for entry in primary_entries:
        units = (
            entry.get(
                "source_units"
            )
            or []
        )

        if not units:
            errors.append(
                "Lane primary entry has no source_units: "
                f"entry_id={entry.get('entry_id')!r}"
            )

        for unit in units:
            unit_id = unit.get(
                "unit_id"
            )

            if not unit_id:
                errors.append(
                    "Lane source_unit is missing unit_id: "
                    f"entry_id={entry.get('entry_id')!r}"
                )

            elif unit_id in seen_unit_ids:
                errors.append(
                    f"Duplicate Lane source unit id: {unit_id}"
                )

            else:
                seen_unit_ids.add(
                    unit_id
                )

            if not str(
                unit.get(
                    "text"
                )
                or ""
            ).strip():
                errors.append(
                    "Lane source_unit has empty text: "
                    f"{unit_id!r}"
                )

    return errors


def report_record(
    packet: dict,
    *,
    large_packet_char_warning: int,
) -> dict:
    chars = compact_json_chars(
        packet
    )

    # Only a rough planning heuristic. Arabic/JSON tokenization varies.
    rough_tokens = math.ceil(
        chars
        / 3
    )

    integrity = packet[
        "input_integrity"
    ]

    return {
        "root":
            packet[
                "root"
            ],

        "arabic":
            packet[
                "arabic"
            ],

        "packet_json_char_count":
            chars,

        "rough_token_estimate_from_chars":
            rough_tokens,

        "large_packet_warning":
            (
                chars
                > large_packet_char_warning
            ),

        "qac_form_group_count":
            integrity[
                "qac_form_group_count"
            ],

        "qac_occurrence_count":
            integrity[
                "qac_occurrence_count"
            ],

        "lane_primary_entry_count":
            integrity[
                "lane_primary_entry_count"
            ],

        "lane_primary_source_unit_count":
            integrity[
                "lane_primary_source_unit_count"
            ],

        "lane_cross_reference_context_entry_count":
            integrity[
                "lane_cross_reference_context_entry_count"
            ],

        "maqayis_entry_count":
            integrity[
                "maqayis_entry_count"
            ],

        "mufradat_unique_entry_count":
            integrity[
                "mufradat_unique_entry_count"
            ],

        "mufradat_shared_ambiguous_entry_count":
            integrity[
                "mufradat_shared_ambiguous_entry_count"
            ],

        "source_ref_count":
            integrity[
                "source_ref_count"
            ],

        "source_text_char_counts":
            packet[
                "source_text_char_counts"
            ],
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic one-call final dictionary synthesis "
            "evidence packets. No API calls are made."
        )
    )

    parser.add_argument(
        "--mode",
        choices=[
            "pilot",
            "full",
        ],
        default="pilot",
        help=(
            "pilot = five review roots only; full = all roots."
        ),
    )

    parser.add_argument(
        "--roots",
        nargs="+",
        default=None,
        help=(
            "Optional explicit root selection. Intended for local packet "
            "inspection; overrides the normal pilot root list."
        ),
    )

    parser.add_argument(
        "--qf-examples-per-gloss",
        type=int,
        default=
            DEFAULT_QF_EXAMPLES_PER_GLOSS,
        help=(
            "Maximum representative QF occurrences retained for each "
            "distinct lemma-level contextual gloss. Default: 2."
        ),
    )

    parser.add_argument(
        "--large-packet-char-warning",
        type=int,
        default=
            DEFAULT_LARGE_PACKET_CHAR_WARNING,
        help=(
            "Flag packets larger than this compact-JSON character count. "
            "This does not truncate or reject them."
        ),
    )

    parser.add_argument(
        "--confirm-full",
        action="store_true",
        help=(
            "Required with --mode full when --roots is not supplied."
        ),
    )

    args = parser.parse_args()

    if (
        args.qf_examples_per_gloss
        < 0
    ):
        raise ValueError(
            "--qf-examples-per-gloss must be >= 0"
        )

    if (
        args.large_packet_char_warning
        <= 0
    ):
        raise ValueError(
            "--large-packet-char-warning must be > 0"
        )

    if (
        args.mode
        == "full"
        and not args.roots
        and not args.confirm_full
    ):
        raise SystemExit(
            "Refusing accidental full packet build.\n"
            "Use --mode full --confirm-full when ready."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    required_files = [
        COMBINED_FILE,
        LANE_FILE,
        FORM_INVENTORY_FILE,
    ]

    missing = [
        path
        for path
        in required_files
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required input(s):\n"
            + "\n".join(
                str(path)
                for path
                in missing
            )
        )

    print()
    print("=" * 76)
    print(
        "ROOT SYNTHESIS PACKETS V3 — SOURCE-NATIVE LANE UNIT IDS — DETERMINISTIC ONLY"
    )
    print("=" * 76)

    print(
        "Loading combined v2 for Maqayis, Mufradat, and QF context..."
    )

    combined = root_lookup(
        load_json(
            COMBINED_FILE
        )
    )

    print(
        f"  roots: {len(combined):,}"
    )

    print(
        "Loading complete root-local Lane evidence..."
    )

    lane = root_lookup(
        load_json(
            LANE_FILE
        )
    )

    print(
        f"  roots: {len(lane):,}"
    )

    print(
        "Loading canonical Quran form inventory..."
    )

    forms = root_lookup(
        load_json(
            FORM_INVENTORY_FILE
        )
    )

    print(
        f"  roots: {len(forms):,}"
    )

    # Root-set equality is a cheap and high-value upstream check.
    root_sets_equal = (
        set(
            combined
        )
        == set(
            lane
        )
        == set(
            forms
        )
    )

    if not root_sets_equal:
        raise RuntimeError(
            "The three synthesis inputs do not have the same root set."
        )

    if args.roots:
        selected_roots = list(
            dict.fromkeys(
                args.roots
            )
        )

    elif args.mode == "pilot":
        selected_roots = list(
            PILOT_ROOTS
        )

    else:
        selected_roots = sorted(
            forms
        )

    unknown = [
        root
        for root
        in selected_roots
        if root not in forms
    ]

    if unknown:
        raise ValueError(
            "Unknown root(s): "
            + ", ".join(
                unknown
            )
        )

    packets = []

    packet_reports = []

    errors_by_root = {}

    for index, root in enumerate(
        selected_roots,
        start=1,
    ):
        packet = build_packet(
            root=root,
            combined_root=
                combined[
                    root
                ],
            lane_root=
                lane[
                    root
                ],
            form_root=
                forms[
                    root
                ],
            qf_examples_per_gloss=
                args.qf_examples_per_gloss,
        )

        # Identity / occurrence consistency across the three newer
        # deterministic layers.
        arabics = {
            str(
                value
            )
            for value in [
                combined[
                    root
                ].get(
                    "arabic"
                ),

                lane[
                    root
                ].get(
                    "arabic"
                ),

                forms[
                    root
                ].get(
                    "arabic"
                ),
            ]
            if value
            not in {
                None,
                "",
            }
        }

        if len(
            arabics
        ) > 1:
            errors_by_root.setdefault(
                root,
                [],
            ).append(
                "Arabic root identity mismatch across inputs."
            )

        form_count = (
            forms[
                root
            ].get(
                "qac_occurrence_count"
            )
        )

        lane_count = (
            lane[
                root
            ].get(
                "qac",
                {}
            ).get(
                "occurrence_count"
            )
        )

        qf_count = (
            combined[
                root
            ].get(
                "quran",
                {}
            ).get(
                "contextual_english",
                {}
            ).get(
                "qac_occurrence_count"
            )
        )

        known_counts = {
            safe_int(
                value
            )
            for value in [
                form_count,
                lane_count,
                qf_count,
            ]
            if value
            is not None
        }

        if len(
            known_counts
        ) > 1:
            errors_by_root.setdefault(
                root,
                [],
            ).append(
                "QAC occurrence-count mismatch across inputs."
            )

        packet_errors = (
            validate_packet_inputs(
                packet
            )
        )

        if packet_errors:
            errors_by_root.setdefault(
                root,
                [],
            ).extend(
                packet_errors
            )

        packets.append(
            packet
        )

        report = report_record(
            packet,
            large_packet_char_warning=
                args.large_packet_char_warning,
        )

        packet_reports.append(
            report
        )

        print(
            f"[{index}/{len(selected_roots)}] "
            f"{root:<5} "
            f"{report['packet_json_char_count']:,} chars "
            f"(~{report['rough_token_estimate_from_chars']:,} rough tokens)"
        )

    if errors_by_root:
        raise RuntimeError(
            "Synthesis packet input audit failed:\n"
            + json.dumps(
                errors_by_root,
                ensure_ascii=False,
                indent=2,
            )
        )

    output = {
        "metadata": {
            "dataset":
                (
                    "One-call final Quran root dictionary synthesis "
                    "evidence packets"
                ),

            "version":
                PACKET_VERSION,

            "mode":
                args.mode,

            "llm_calls_made":
                0,

            "architecture":
                (
                    "Deterministic multi-source evidence preparation "
                    "followed by one final synthesis call per root."
                ),

            "inputs": {
                "combined_v2":
                    str(
                        COMBINED_FILE.relative_to(
                            SCRIPT_DIR
                        )
                    ),

                "lane_complete_root_evidence":
                    str(
                        LANE_FILE.relative_to(
                            SCRIPT_DIR
                        )
                    ),

                "quran_form_inventory":
                    str(
                        FORM_INVENTORY_FILE.relative_to(
                            SCRIPT_DIR
                        )
                    ),
            },

            "important_input_policy": [
                (
                    "combined_v2 supplies Maqayis, Mufradat, and Quran "
                    "Foundation context only."
                ),
                (
                    "Lane comes from lane_complete_root_evidence_v1, "
                    "not the older combined-v2 Lane payload and not the "
                    "experimental Lane LLM sense inventory."
                ),
                (
                    "Lane primary evidence is exposed as deterministic "
                    "source_units derived from its already-parsed "
                    "sense_groups. No LLM extraction/disposition stage "
                    "is involved. Cross-reference context remains "
                    "context-only prose."
                ),
                (
                    "Quran form identity/count/location comes from "
                    "quran_form_inventory_v1."
                ),
                (
                    "QF contextual English is compacted by distinct "
                    "lemma-level gloss; repeated examples are bounded, "
                    "but distinct gloss categories are retained."
                ),
            ],
        },

        "summary": {
            "selected_root_count":
                len(
                    packets
                ),

            "packet_count":
                len(
                    packets
                ),

            "total_packet_json_chars":
                sum(
                    item[
                        "packet_json_char_count"
                    ]
                    for item
                    in packet_reports
                ),

            "maximum_packet_json_chars":
                max(
                    (
                        item[
                            "packet_json_char_count"
                        ]
                        for item
                        in packet_reports
                    ),
                    default=0,
                ),

            "large_packet_count":
                sum(
                    1
                    for item
                    in packet_reports
                    if item[
                        "large_packet_warning"
                    ]
                ),

            "qf_examples_per_gloss":
                args.qf_examples_per_gloss,

            "large_packet_char_warning":
                args.large_packet_char_warning,
        },

        "packets":
            packets,
    }

    report = {
        "metadata": {
            "dataset":
                "Root synthesis packet build report",

            "version":
                PACKET_VERSION,

            "mode":
                args.mode,

            "llm_calls_made":
                0,
        },

        "summary":
            output[
                "summary"
            ],

        "hard_checks": {
            "input_root_sets_equal":
                root_sets_equal,

            "selected_roots_all_present":
                True,

            "all_qac_form_occurrences_accounted":
                True,

            "all_lane_locatable_cross_reference_context_closed":
                True,

            "packet_input_audits_pass":
                True,
        },

        "packet_reports":
            packet_reports,
    }

    if (
        args.mode
        == "pilot"
        or args.roots
    ):
        output_file = (
            PILOT_OUTPUT_FILE
            if not args.roots
            else OUTPUT_DIR
            / "root_synthesis_packets_selected_v3.json"
        )

        report_file = (
            PILOT_REPORT_FILE
            if not args.roots
            else OUTPUT_DIR
            / "root_synthesis_packets_selected_report_v3.json"
        )

    else:
        output_file = (
            FULL_OUTPUT_FILE
        )

        report_file = (
            FULL_REPORT_FILE
        )

    write_json(
        output_file,
        output,
    )

    write_json(
        report_file,
        report,
    )

    # Sample is always the canonical five pilot roots when they were
    # built in this run. In pilot mode that is intentionally the same
    # packet set under a review-oriented filename.
    packet_by_root = {
        packet[
            "root"
        ]:
            packet
        for packet
        in packets
    }

    sample_roots_available = [
        root
        for root in PILOT_ROOTS
        if root in packet_by_root
    ]

    if sample_roots_available:
        sample = {
            "metadata": {
                "purpose":
                    (
                        "Review sample for one-call final dictionary "
                        "synthesis packet design"
                    ),

                "roots":
                    sample_roots_available,

                "llm_calls_made":
                    0,
            },

            "packets": [
                packet_by_root[
                    root
                ]
                for root
                in sample_roots_available
            ],
        }

        write_json(
            SAMPLE_FILE,
            sample,
        )

    print()
    print("=" * 76)
    print(
        "ROOT SYNTHESIS PACKET BUILD COMPLETE — NO API CALLS MADE"
    )
    print("=" * 76)
    print(
        f"Output: {output_file}"
    )
    print(
        f"Report: {report_file}"
    )

    if sample_roots_available:
        print(
            f"Sample: {SAMPLE_FILE}"
        )

    print()
    print(
        "NEXT ACTION: inspect/upload the report and pilot/sample packet "
        "files. Do not make synthesis API calls yet."
    )


if __name__ == "__main__":
    main()
