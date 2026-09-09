#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

LANE_FILE = (
    OUTPUT_DIR
    / "lane_quran_semantics_v2.json"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "lane_complete_sense_packets_v2.json"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "lane_complete_sense_packets_report_v2.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "lane_complete_sense_packets_sample_v2.json"
)


SAMPLE_ROOTS = [
    # rich / representative
    "rHm",
    "ktb",

    # form-sensitive
    "Aty",

    # polysemous
    "Hqq",

    # useful Quran-specific ambiguity case later
    "Slw",
]


DEFAULT_CHUNK_SOURCE_CHAR_BUDGET = 30000


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


def json_char_size(
    value: Any,
) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )
    )


def compact_qac(
    qac: dict,
) -> dict:
    return {
        "root":
            qac.get(
                "root"
            ),

        "arabic":
            qac.get(
                "arabic"
            ),

        "arabic_spaced":
            qac.get(
                "arabic_spaced"
            ),

        "radicals":
            qac.get(
                "radicals",
                []
            ),

        "occurrence_count":
            qac.get(
                "occurrence_count"
            ),

        "pos_counts":
            qac.get(
                "pos_counts",
                {}
            ),

        "lemmas": [
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

                "pos_counts":
                    lemma.get(
                        "pos_counts",
                        {}
                    ),
            }
            for lemma
            in qac.get(
                "lemmas",
                []
            )
        ],

        "verb": {
            "occurrence_count":
                (
                    qac.get(
                        "verb",
                        {}
                    ).get(
                        "occurrence_count"
                    )
                ),

            "forms":
                (
                    qac.get(
                        "verb",
                        {}
                    ).get(
                        "forms",
                        {}
                    )
                ),
        },

        "derived_nominals":
            qac.get(
                "derived_nominals",
                {}
            ),
    }


# ============================================================
# Cross-reference resolution
# ============================================================

def build_node_lookup(
    roots: list[dict],
) -> dict[str, list[dict]]:
    """
    Build a lossless Lane node-id lookup.

    IMPORTANT:
    Lane `node_id` is a cross-reference locator, but the frozen dataset
    demonstrates that it is NOT guaranteed to be globally unique.

    Therefore:
      node_id -> [one or more candidate entry targets]

    Exact duplicate target records are deduplicated, but multiple distinct
    targets are preserved rather than causing the pipeline to fail.
    """
    lookup: dict[
        str,
        list[dict],
    ] = defaultdict(
        list
    )

    seen = defaultdict(
        set
    )

    for root_record in roots:
        qac = root_record.get(
            "qac",
            {}
        )

        root_id = qac.get(
            "root"
        )

        lane = root_record.get(
            "lane"
        ) or {}

        for entry in lane.get(
            "entries",
            []
        ):
            node_id = entry.get(
                "node_id"
            )

            if not node_id:
                continue

            target = {
                "root":
                    root_id,

                "entry_id":
                    entry.get(
                        "entry_id"
                    ),

                "headword":
                    entry.get(
                        "headword"
                    ),
            }

            identity = (
                target[
                    "root"
                ],
                target[
                    "entry_id"
                ],
                target[
                    "headword"
                ],
            )

            if identity in seen[
                node_id
            ]:
                continue

            seen[
                node_id
            ].add(
                identity
            )

            lookup[
                node_id
            ].append(
                target
            )

    # Deterministic ordering when a node resolves to multiple targets.
    for node_id in lookup:
        lookup[
            node_id
        ].sort(
            key=lambda item: (
                str(
                    item.get(
                        "root"
                    )
                    or ""
                ),
                int(
                    item.get(
                        "entry_id"
                    )
                    or 0
                ),
                str(
                    item.get(
                        "headword"
                    )
                    or ""
                ),
            )
        )

    return dict(
        lookup
    )


def resolve_cross_references(
    *,
    dictionary: dict,
    node_lookup: dict[
        str,
        list[dict],
    ],
) -> tuple[
    list[dict],
    int,
    int,
    int,
]:
    raw_refs = dictionary.get(
        "cross_references",
        []
    ) or []

    output = []
    resolved_count = 0
    unresolved_count = 0
    multi_target_count = 0

    for raw in raw_refs:
        item = dict(
            raw
        )

        select = raw.get(
            "select"
        )

        targets = (
            node_lookup.get(
                select,
                [],
            )
            if select
            else []
        )

        if not targets:
            item[
                "resolution_status"
            ] = "unresolved"

            item[
                "resolved_targets"
            ] = []

            unresolved_count += 1

        elif len(
            targets
        ) == 1:
            item[
                "resolution_status"
            ] = "resolved_unique"

            item[
                "resolved_targets"
            ] = targets

            resolved_count += 1

        else:
            # Do not guess which duplicate node target Lane intended.
            # Preserve every candidate for later lexical review.
            item[
                "resolution_status"
            ] = "resolved_multiple"

            item[
                "resolved_targets"
            ] = targets

            resolved_count += 1
            multi_target_count += 1

        output.append(
            item
        )

    return (
        output,
        resolved_count,
        unresolved_count,
        multi_target_count,
    )



# ============================================================
# Complete Lane-entry payload
# ============================================================

def entry_payload(
    *,
    entry: dict,
    node_lookup: dict[str, dict],
) -> tuple[
    dict,
    int,
    int,
    int,
]:
    dictionary = (
        entry.get(
            "dictionary"
        )
        or {}
    )

    (
        cross_refs,
        resolved_count,
        unresolved_count,
        multi_target_count,
    ) = resolve_cross_references(
        dictionary=dictionary,
        node_lookup=node_lookup,
    )

    text = (
        dictionary.get(
            "plain_text"
        )
        or ""
    )

    payload = {
        "source_ref":
            (
                "lane:entry:"
                f"{entry.get('entry_id')}"
            ),

        "entry_id":
            entry.get(
                "entry_id"
            ),

        "node_id":
            entry.get(
                "node_id"
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
                "buckwalter_word"
            ),

        "itype":
            entry.get(
                "itype",
                {}
            ),

        "pos_codes":
            entry.get(
                "pos_codes",
                []
            ),

        "source":
            entry.get(
                "source",
                {}
            ),

        # Exact extracted Lane prose. Never truncated in this stage.
        "text":
            text,

        "text_char_count":
            len(
                text
            ),

        # Deterministic parser hints from the frozen Lane extractor.
        # These are hints, not replacements for the exact text.
        "parser_hints": {
            "sense_markers":
                dictionary.get(
                    "sense_markers",
                    []
                ),

            "emphasized_fragments":
                dictionary.get(
                    "emphasized_fragments",
                    []
                ),

            "foreign_terms":
                dictionary.get(
                    "foreign_terms",
                    []
                ),

            "orthographic_forms":
                dictionary.get(
                    "orthographic_forms",
                    []
                ),

            "cross_references":
                cross_refs,
        },
    }

    return (
        payload,
        resolved_count,
        unresolved_count,
        multi_target_count,
    )


# ============================================================
# Chunking
# ============================================================

def chunk_entries(
    *,
    entries: list[dict],
    budget: int,
) -> list[list[dict]]:
    """
    Entry-atomic, lossless chunking.

    - Entries are never ranked or omitted.
    - Entries are never truncated.
    - Entry order from the frozen Lane dataset is preserved.
    - If one entry alone exceeds the target budget, it forms one oversize
      chunk instead of being cut or discarded.
    """
    chunks = []
    current = []
    current_chars = 0

    for entry in entries:
        chars = int(
            entry.get(
                "text_char_count"
            )
            or 0
        )

        if (
            current
            and (
                current_chars
                + chars
                > budget
            )
        ):
            chunks.append(
                current
            )

            current = []
            current_chars = 0

        current.append(
            entry
        )

        current_chars += chars

    if current:
        chunks.append(
            current
        )

    return chunks


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build lossless, complete Lane sense-extraction packets "
            "for every Quran root matched to Lane."
        )
    )

    parser.add_argument(
        "--chunk-source-char-budget",
        type=int,
        default=DEFAULT_CHUNK_SOURCE_CHAR_BUDGET,
        help=(
            "Target Lane source-text characters per packet. "
            "Entries remain atomic and are never truncated."
        ),
    )

    args = parser.parse_args()

    if (
        args.chunk_source_char_budget
        <= 0
    ):
        raise ValueError(
            "--chunk-source-char-budget must be > 0"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not LANE_FILE.exists():
        raise FileNotFoundError(
            "Missing frozen Lane dataset:\n"
            f"{LANE_FILE}"
        )

    print(
        "Loading frozen Lane/QAC evidence..."
    )

    source = load_json(
        LANE_FILE
    )

    roots = source.get(
        "roots",
        []
    )

    node_lookup = build_node_lookup(
        roots
    )

    duplicate_node_ids = {
        node_id:
            targets
        for node_id, targets
        in node_lookup.items()
        if len(
            targets
        ) > 1
    }

    packets = []

    matched_root_count = 0
    unmatched_root_count = 0

    source_entry_ids = []
    packet_entry_ids = []

    # Hard completeness uses root-scoped attachment identities rather
    # than assuming Lane entry_id itself can occur under only one QAC root.
    source_entry_attachments = []
    packet_entry_attachments = []

    source_text_chars = 0
    packet_text_chars = 0

    total_cross_refs = 0
    resolved_cross_refs = 0
    unresolved_cross_refs = 0
    multi_target_cross_refs = 0

    oversize_entry_count = 0
    oversize_entries = []

    packet_count_by_root = {}
    entry_count_by_root = {}

    root_manifest = []

    for root_record in roots:
        qac = root_record.get(
            "qac",
            {}
        )

        root_id = qac.get(
            "root"
        )

        if not root_id:
            raise RuntimeError(
                "Lane semantic root record has no QAC root ID."
            )

        lane_match = (
            root_record.get(
                "lane_match"
            )
            or {}
        )

        lane = (
            root_record.get(
                "lane"
            )
            or {}
        )

        raw_entries = lane.get(
            "entries",
            []
        ) or []

        if not raw_entries:
            unmatched_root_count += 1

            root_manifest.append(
                {
                    "root":
                        root_id,

                    "arabic":
                        qac.get(
                            "arabic"
                        ),

                    "lane_status":
                        lane_match.get(
                            "status"
                        ),

                    "source_entry_count":
                        0,

                    "packet_count":
                        0,
                }
            )

            continue

        matched_root_count += 1

        prepared_entries = []

        for entry in raw_entries:
            entry_id = entry.get(
                "entry_id"
            )

            if entry_id is None:
                raise RuntimeError(
                    f"Lane entry without entry_id under root {root_id}"
                )

            source_entry_ids.append(
                int(
                    entry_id
                )
            )

            source_entry_attachments.append(
                (
                    root_id,
                    int(
                        entry_id
                    ),
                )
            )

            dictionary = (
                entry.get(
                    "dictionary"
                )
                or {}
            )

            source_text = (
                dictionary.get(
                    "plain_text"
                )
                or ""
            )

            source_text_chars += len(
                source_text
            )

            (
                prepared,
                resolved,
                unresolved,
                multi_target,
            ) = entry_payload(
                entry=entry,
                node_lookup=node_lookup,
            )

            prepared_entries.append(
                prepared
            )

            total_cross_refs += (
                resolved
                + unresolved
            )

            resolved_cross_refs += (
                resolved
            )

            unresolved_cross_refs += (
                unresolved
            )

            multi_target_cross_refs += (
                multi_target
            )

            if (
                prepared[
                    "text_char_count"
                ]
                > args.chunk_source_char_budget
            ):
                oversize_entry_count += 1

                oversize_entries.append(
                    {
                        "root":
                            root_id,

                        "entry_id":
                            entry_id,

                        "headword":
                            entry.get(
                                "headword"
                            ),

                        "text_char_count":
                            prepared[
                                "text_char_count"
                            ],
                    }
                )

        root_chunks = chunk_entries(
            entries=prepared_entries,
            budget=args.chunk_source_char_budget,
        )

        packet_count_by_root[
            root_id
        ] = len(
            root_chunks
        )

        entry_count_by_root[
            root_id
        ] = len(
            prepared_entries
        )

        qac_packet = compact_qac(
            qac
        )

        total_chunks = len(
            root_chunks
        )

        for index, chunk in enumerate(
            root_chunks,
            start=1,
        ):
            for entry in chunk:
                packet_entry_ids.append(
                    int(
                        entry[
                            "entry_id"
                        ]
                    )
                )

                packet_entry_attachments.append(
                    (
                        root_id,
                        int(
                            entry[
                                "entry_id"
                            ]
                        ),
                    )
                )

                packet_text_chars += int(
                    entry[
                        "text_char_count"
                    ]
                )

            chunk_text_chars = sum(
                int(
                    entry[
                        "text_char_count"
                    ]
                )
                for entry in chunk
            )

            packet = {
                "packet_id":
                    (
                        f"lane-senses:{root_id}:"
                        f"{index}-of-{total_chunks}"
                    ),

                "root":
                    root_id,

                "arabic":
                    qac.get(
                        "arabic"
                    ),

                "chunk_index":
                    index,

                "chunk_count":
                    total_chunks,

                "source_text_char_count":
                    chunk_text_chars,

                "target_chunk_source_char_budget":
                    args.chunk_source_char_budget,

                "oversize_single_entry_packet":
                    (
                        len(
                            chunk
                        ) == 1
                        and chunk[
                            0
                        ][
                            "text_char_count"
                        ]
                        > args.chunk_source_char_budget
                    ),

                "qac_context":
                    qac_packet,

                "lane_match":
                    lane_match,

                "lane_root_context": {
                    "canonical_root":
                        lane.get(
                            "canonical_root"
                        ),

                    "arabic_spellings":
                        lane.get(
                            "arabic_spellings",
                            []
                        ),

                    "buckwalter_spellings":
                        lane.get(
                            "buckwalter_spellings",
                            []
                        ),

                    "root_records":
                        lane.get(
                            "root_records",
                            []
                        ),

                    "entry_count":
                        lane.get(
                            "entry_count"
                        ),

                    "entry_groups":
                        lane.get(
                            "entry_groups",
                            {}
                        ),
                },

                "entries":
                    chunk,
            }

            packets.append(
                packet
            )

        root_manifest.append(
            {
                "root":
                    root_id,

                "arabic":
                    qac.get(
                        "arabic"
                    ),

                "lane_status":
                    lane_match.get(
                        "status"
                    ),

                "source_entry_count":
                    len(
                        prepared_entries
                    ),

                "packet_count":
                    total_chunks,
            }
        )

    # --------------------------------------------------------
    # Hard completeness audit
    # --------------------------------------------------------

    source_counter = Counter(
        source_entry_attachments
    )

    packet_counter = Counter(
        packet_entry_attachments
    )

    # Duplicate within the same QAC-root attachment is a real problem.
    duplicate_source_attachments = sorted(
        identity
        for identity, count
        in source_counter.items()
        if count != 1
    )

    duplicate_packet_attachments = sorted(
        identity
        for identity, count
        in packet_counter.items()
        if count != 1
    )

    missing_from_packets = sorted(
        set(
            source_counter
        )
        - set(
            packet_counter
        )
    )

    extra_in_packets = sorted(
        set(
            packet_counter
        )
        - set(
            source_counter
        )
    )

    # This is diagnostic only: the same underlying Lane entry ID may be
    # attached to multiple QAC roots. We preserve and report that rather
    # than assuming global uniqueness.
    entry_id_to_roots = defaultdict(
        set
    )

    for root_id, entry_id in (
        source_entry_attachments
    ):
        entry_id_to_roots[
            entry_id
        ].add(
            root_id
        )

    multi_root_entry_ids = {
        entry_id:
            sorted(
                root_ids
            )
        for entry_id, root_ids
        in entry_id_to_roots.items()
        if len(
            root_ids
        ) > 1
    }

    if duplicate_source_attachments:
        raise RuntimeError(
            "Frozen Lane source unexpectedly repeats the same "
            "(QAC root, Lane entry_id) attachment: "
            + ", ".join(
                f"{root}:{entry_id}"
                for root, entry_id
                in duplicate_source_attachments[:50]
            )
        )

    if (
        duplicate_packet_attachments
        or missing_from_packets
        or extra_in_packets
    ):
        raise RuntimeError(
            "Lossless packet audit failed.\n"
            f"Duplicate packet attachments: "
            f"{duplicate_packet_attachments[:50]}\n"
            f"Missing: {missing_from_packets[:50]}\n"
            f"Extra: {extra_in_packets[:50]}"
        )

    if (
        source_text_chars
        != packet_text_chars
    ):
        raise RuntimeError(
            "Lane source-text character accounting mismatch: "
            f"{source_text_chars} source vs "
            f"{packet_text_chars} packetized"
        )

    summary = {
        "qac_root_record_count":
            len(
                roots
            ),

        "matched_root_count":
            matched_root_count,

        "unmatched_or_zero_entry_root_count":
            unmatched_root_count,

        "source_lane_entry_count":
            len(
                source_entry_ids
            ),

        "unique_source_lane_entry_id_count":
            len(
                set(
                    source_entry_ids
                )
            ),

        "source_lane_entry_attachment_count":
            len(
                source_entry_attachments
            ),

        "lane_entry_ids_attached_to_multiple_qac_roots":
            len(
                multi_root_entry_ids
            ),

        "duplicate_lane_node_id_count":
            len(
                duplicate_node_ids
            ),

        "packet_count":
            len(
                packets
            ),

        "packetized_lane_entry_count":
            len(
                packet_entry_ids
            ),

        "missing_lane_entry_count":
            len(
                missing_from_packets
            ),

        "duplicate_packet_attachment_count":
            len(
                duplicate_packet_attachments
            ),

        "source_text_char_count":
            source_text_chars,

        "packetized_text_char_count":
            packet_text_chars,

        "target_chunk_source_char_budget":
            args.chunk_source_char_budget,

        "oversize_entry_count":
            oversize_entry_count,

        "cross_reference_count":
            total_cross_refs,

        "resolved_cross_reference_count":
            resolved_cross_refs,

        "unresolved_cross_reference_count":
            unresolved_cross_refs,

        "multi_target_cross_reference_count":
            multi_target_cross_refs,
    }

    output = {
        "metadata": {
            "dataset":
                (
                    "Complete lossless Lane sense-extraction packets "
                    "for Quranic root lexical processing"
                ),

            "version":
                2,

            "source":
                str(
                    LANE_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "purpose":
                (
                    "Stage A input for structured Lane sense extraction. "
                    "Every frozen Lane entry is retained exactly once. "
                    "No relevance ranking, omission, or text truncation "
                    "is permitted."
                ),

            "policy": [
                (
                    "Every Lane entry attached to a matched QAC root "
                    "must appear in exactly one packet."
                ),
                (
                    "Lane source prose is copied exactly from "
                    "dictionary.plain_text and is never truncated."
                ),
                (
                    "Chunking is entry-atomic. An entry larger than the "
                    "target budget becomes an oversize packet rather "
                    "than being cut or discarded."
                ),
                (
                    "QAC morphology is included only as root/form context "
                    "for later mapping. It does not alter Lane meanings."
                ),
                (
                    "Cross-reference metadata is preserved and resolved "
                    "to Lane entry IDs where the target node exists."
                ),
                (
                    "This dataset contains no generated semantic "
                    "interpretation."
                ),
            ],
        },

        "summary":
            summary,

        "root_manifest":
            root_manifest,

        "packets":
            packets,
    }

    write_json(
        OUTPUT_FILE,
        output,
    )

    roots_by_packet_count = sorted(
        (
            {
                "root":
                    root_id,

                "entry_count":
                    entry_count_by_root[
                        root_id
                    ],

                "packet_count":
                    packet_count,
            }
            for root_id, packet_count
            in packet_count_by_root.items()
        ),
        key=lambda item: (
            -item[
                "packet_count"
            ],
            -item[
                "entry_count"
            ],
            item[
                "root"
            ],
        ),
    )

    report = {
        "summary":
            summary,

        "hard_completeness_checks": {
            "all_source_entries_present_exactly_once":
                (
                    not duplicate_packet_attachments
                    and not missing_from_packets
                    and not extra_in_packets
                ),

            "source_text_character_accounting_exact":
                (
                    source_text_chars
                    == packet_text_chars
                ),
        },

        "duplicate_node_id_diagnostics": {
            "count":
                len(
                    duplicate_node_ids
                ),

            "examples": [
                {
                    "node_id":
                        node_id,

                    "targets":
                        targets,
                }
                for node_id, targets
                in list(
                    sorted(
                        duplicate_node_ids.items()
                    )
                )[:100]
            ],
        },

        "multi_root_lane_entry_id_diagnostics": {
            "count":
                len(
                    multi_root_entry_ids
                ),

            "examples": [
                {
                    "entry_id":
                        entry_id,

                    "qac_roots":
                        roots_list,
                }
                for entry_id, roots_list
                in list(
                    sorted(
                        multi_root_entry_ids.items()
                    )
                )[:100]
            ],
        },

        "oversize_entries":
            sorted(
                oversize_entries,
                key=lambda item: (
                    -item[
                        "text_char_count"
                    ],
                    item[
                        "root"
                    ],
                    item[
                        "entry_id"
                    ],
                ),
            ),

        "roots_by_packet_count":
            roots_by_packet_count,

        "unmatched_or_zero_entry_roots": [
            item
            for item
            in root_manifest
            if item[
                "source_entry_count"
            ] == 0
        ],
    }

    write_json(
        REPORT_FILE,
        report,
    )

    sample_packets = [
        packet
        for packet in packets
        if packet[
            "root"
        ] in SAMPLE_ROOTS
    ]

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review complete lossless Lane packetization before "
                    "any LLM sense extraction"
                ),

            "sample_roots":
                SAMPLE_ROOTS,

            "note":
                (
                    "All packets for each requested sample root are "
                    "included, not only the first packet."
                ),
        },

        "packets":
            sample_packets,
    }

    write_json(
        SAMPLE_FILE,
        sample,
    )

    print()
    print("=" * 68)
    print(
        "COMPLETE LANE SENSE PACKETS V1 BUILT"
    )
    print("=" * 68)

    print(
        f"QAC root records:                 "
        f"{len(roots):,}"
    )

    print(
        f"Matched roots with Lane entries: "
        f"{matched_root_count:,}"
    )

    print(
        f"Roots without Lane entries:       "
        f"{unmatched_root_count:,}"
    )

    print(
        f"Lane source entries:              "
        f"{len(source_entry_ids):,}"
    )

    print(
        f"Entries packetized:               "
        f"{len(packet_entry_ids):,}"
    )

    print(
        f"Packets:                          "
        f"{len(packets):,}"
    )

    print(
        f"Missing entries:                  "
        f"{len(missing_from_packets):,}"
    )

    print(
        f"Duplicate packet attachments:     "
        f"{len(duplicate_packet_attachments):,}"
    )

    print(
        f"Source text chars:                "
        f"{source_text_chars:,}"
    )

    print(
        f"Packetized text chars:            "
        f"{packet_text_chars:,}"
    )

    print(
        f"Oversize entries:                 "
        f"{oversize_entry_count:,}"
    )

    print(
        f"Duplicate Lane node IDs:          "
        f"{len(duplicate_node_ids):,}"
    )

    print(
        f"Lane IDs attached to >1 root:     "
        f"{len(multi_root_entry_ids):,}"
    )

    print(
        f"Cross references:                 "
        f"{total_cross_refs:,}"
    )

    print(
        f"Resolved cross references:        "
        f"{resolved_cross_refs:,}"
    )

    print(
        f"Unresolved cross references:      "
        f"{unresolved_cross_refs:,}"
    )

    print(
        f"Multi-target cross references:    "
        f"{multi_target_cross_refs:,}"
    )

    print()
    print(
        "Complete packets:\n"
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
        "lane_complete_sense_packets_report_v2.json "
        "and lane_complete_sense_packets_sample_v2.json."
    )


if __name__ == "__main__":
    main()
