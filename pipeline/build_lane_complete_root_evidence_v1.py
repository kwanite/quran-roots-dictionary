#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

# Reuse the exact frozen Lane parser/classifier that produced
# output/lane_quran_semantics_v2.json. This keeps primary and supplemental
# entries structurally consistent.
from extract_lane_semantics_v2 import (
    classify_itype,
    extract_lane_xml,
    load_pos_index,
    open_sqlite_readonly,
)


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

LANE_SEMANTICS_FILE = (
    OUTPUT_DIR
    / "lane_quran_semantics_v2.json"
)

LANE_DB_FILE = (
    SCRIPT_DIR
    / "sources"
    / "lane"
    / "lexicon.sqlite"
)

FULL_OUTPUT = (
    OUTPUT_DIR
    / "lane_complete_root_evidence_v1.json"
)

REPORT_OUTPUT = (
    OUTPUT_DIR
    / "lane_complete_root_evidence_report_v1.json"
)

SAMPLE_OUTPUT = (
    OUTPUT_DIR
    / "lane_complete_root_evidence_sample_v1.json"
)


SAMPLE_ROOTS = [
    "rHm",
    "ktb",
    "Aty",
    "Hqq",
    "Slw",
]


DEFAULT_MAX_SUPPLEMENTAL_ENTRIES_PER_ROOT = 5000


# ============================================================
# General helpers
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


def source_ref(
    entry_id: int,
) -> str:
    return (
        f"lane:entry:{entry_id}"
    )


def entry_text_chars(
    entry: dict,
) -> int:
    return len(
        (
            entry.get(
                "dictionary"
            )
            or {}
        ).get(
            "plain_text"
        )
        or ""
    )


# ============================================================
# Full Lane DB loader/cache
# ============================================================

class LaneEntryStore:
    def __init__(
        self,
        conn: sqlite3.Connection,
        pos_index: dict[
            str,
            list[str],
        ],
    ) -> None:
        self.conn = conn
        self.pos_index = pos_index

        self.entry_cache: dict[
            int,
            dict,
        ] = {}

        self.node_cache: dict[
            str,
            list[int],
        ] = {}

    def entry_from_row(
        self,
        row: sqlite3.Row,
    ) -> dict:
        entry_id = int(
            row[
                "id"
            ]
        )

        if (
            entry_id
            in self.entry_cache
        ):
            return self.entry_cache[
                entry_id
            ]

        semantic = extract_lane_xml(
            row[
                "xml"
            ]
        )

        entry = {
            "entry_id":
                entry_id,

            "node_id":
                row[
                    "nodeid"
                ],

            "lane_root_arabic":
                row[
                    "root"
                ],

            "lane_root_buckwalter":
                row[
                    "broot"
                ],

            "headword":
                row[
                    "headword"
                ],

            "word":
                row[
                    "word"
                ],

            "bareword":
                row[
                    "bareword"
                ],

            "buckwalter_word":
                row[
                    "bword"
                ],

            "itype":
                classify_itype(
                    row[
                        "itype"
                    ]
                ),

            "pos_codes":
                self.pos_index.get(
                    row[
                        "nodeid"
                    ],
                    [],
                ),

            "source": {
                "page":
                    row[
                        "page"
                    ],

                "file":
                    row[
                        "file"
                    ],

                "nodenum":
                    row[
                        "nodenum"
                    ],

                "supplement":
                    bool(
                        row[
                            "supplement"
                        ]
                    ),

                "entry_type":
                    row[
                        "type"
                    ],

                "datasource":
                    row[
                        "datasource"
                    ],
            },

            "dictionary":
                semantic,
        }

        self.entry_cache[
            entry_id
        ] = entry

        return entry

    def get_by_id(
        self,
        entry_id: int,
    ) -> dict | None:
        if (
            entry_id
            in self.entry_cache
        ):
            return self.entry_cache[
                entry_id
            ]

        row = self.conn.execute(
            """
            SELECT
                id,
                datasource,
                root,
                broot,
                word,
                bword,
                itype,
                nodeid,
                xml,
                supplement,
                file,
                page,
                nodenum,
                bareword,
                headword,
                type
            FROM entry
            WHERE id = ?
            """,
            (
                entry_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return self.entry_from_row(
            row
        )

    def get_by_node(
        self,
        node_id: str,
    ) -> list[dict]:
        if (
            node_id
            in self.node_cache
        ):
            ids = self.node_cache[
                node_id
            ]

            output = []

            for entry_id in ids:
                entry = self.get_by_id(
                    entry_id
                )

                if entry is not None:
                    output.append(
                        entry
                    )

            return output

        rows = self.conn.execute(
            """
            SELECT
                id,
                datasource,
                root,
                broot,
                word,
                bword,
                itype,
                nodeid,
                xml,
                supplement,
                file,
                page,
                nodenum,
                bareword,
                headword,
                type
            FROM entry
            WHERE nodeid = ?
            ORDER BY id
            """,
            (
                node_id,
            ),
        ).fetchall()

        ids = []

        output = []

        for row in rows:
            entry = self.entry_from_row(
                row
            )

            ids.append(
                int(
                    entry[
                        "entry_id"
                    ]
                )
            )

            output.append(
                entry
            )

        self.node_cache[
            node_id
        ] = ids

        return output


# ============================================================
# Root-local cross-reference closure
# ============================================================

def cross_references(
    entry: dict,
) -> list[dict]:
    return (
        (
            entry.get(
                "dictionary"
            )
            or {}
        ).get(
            "cross_references",
            []
        )
        or []
    )


def reference_identity(
    *,
    source_entry_id: int,
    target_entry_id: int,
    ref: dict,
) -> tuple:
    return (
        source_entry_id,
        target_entry_id,
        ref.get(
            "cref"
        ),
        ref.get(
            "select"
        ),
        ref.get(
            "target"
        ),
        ref.get(
            "type"
        ),
        ref.get(
            "subtype"
        ),
        ref.get(
            "number"
        ),
    )


def build_root_closure(
    *,
    qac_root: str,
    primary_entries: list[dict],
    direct_roots_by_entry_id: dict[
        int,
        list[str],
    ],
    store: LaneEntryStore,
    max_supplemental_entries: int,
) -> tuple[
    list[dict],
    list[dict],
    dict,
]:
    """
    Follow Lane's explicit node-based cross references transitively.

    IMPORTANT:
    - Primary entries remain the only entries directly attached to the QAC root.
    - Followed entries are contextual aids only.
    - We NEVER infer root membership from a cross-reference.
    - References with no node locator remain preserved in the source entry,
      but are not fuzzily guessed/followed.
    """
    primary_by_id = {
        int(
            entry[
                "entry_id"
            ]
        ):
            entry
        for entry
        in primary_entries
    }

    included_by_id = dict(
        primary_by_id
    )

    role_by_id = {
        entry_id:
            "primary"
        for entry_id
        in primary_by_id
    }

    # For every supplemental target, preserve every discovered path/edge
    # that led to it.
    provenance_by_target: dict[
        int,
        list[dict],
    ] = defaultdict(
        list
    )

    provenance_seen = set()

    # Each queue item says: inspect cross-refs inside this included entry.
    # depth 0 means a primary entry; a target reached from it has depth 1.
    queue = deque(
        (
            entry_id,
            entry,
            0,
        )
        for entry_id, entry
        in primary_by_id.items()
    )

    inspected = set()

    unresolved_locators = []

    no_locator_reference_count = 0
    locatable_reference_count = 0

    same_root_reference_count = 0
    supplemental_reference_count = 0

    max_depth_reached = 0

    while queue:
        (
            source_entry_id,
            source_entry,
            source_depth,
        ) = queue.popleft()

        if (
            source_entry_id
            in inspected
        ):
            continue

        inspected.add(
            source_entry_id
        )

        source_role = role_by_id[
            source_entry_id
        ]

        for ref_index, ref in enumerate(
            cross_references(
                source_entry
            )
        ):
            node_id = ref.get(
                "select"
            )

            if not node_id:
                no_locator_reference_count += 1
                continue

            locatable_reference_count += 1

            targets = store.get_by_node(
                str(
                    node_id
                )
            )

            if not targets:
                unresolved_locators.append(
                    {
                        "source_entry_id":
                            source_entry_id,

                        "source_ref":
                            source_ref(
                                source_entry_id
                            ),

                        "source_role":
                            source_role,

                        "source_depth":
                            source_depth,

                        "reference_index":
                            ref_index,

                        "reference":
                            ref,
                    }
                )

                continue

            for target in targets:
                target_id = int(
                    target[
                        "entry_id"
                    ]
                )

                target_depth = (
                    source_depth
                    + 1
                )

                max_depth_reached = max(
                    max_depth_reached,
                    target_depth,
                )

                if (
                    target_id
                    in primary_by_id
                ):
                    target_role = (
                        "primary_same_qac_root"
                    )

                    same_root_reference_count += 1

                else:
                    target_role = (
                        "supplemental_cross_reference_context"
                    )

                    supplemental_reference_count += 1

                edge = {
                    "from_entry_id":
                        source_entry_id,

                    "from_source_ref":
                        source_ref(
                            source_entry_id
                        ),

                    "from_role":
                        source_role,

                    "from_depth":
                        source_depth,

                    "reference_index":
                        ref_index,

                    "reference":
                        ref,

                    "to_entry_id":
                        target_id,

                    "to_source_ref":
                        source_ref(
                            target_id
                        ),

                    "to_role":
                        target_role,

                    "to_depth":
                        target_depth,
                }

                identity = reference_identity(
                    source_entry_id=
                        source_entry_id,

                    target_entry_id=
                        target_id,

                    ref=
                        ref,
                )

                if (
                    target_role
                    == "supplemental_cross_reference_context"
                    and identity
                    not in provenance_seen
                ):
                    provenance_seen.add(
                        identity
                    )

                    provenance_by_target[
                        target_id
                    ].append(
                        edge
                    )

                if (
                    target_id
                    not in included_by_id
                ):
                    included_by_id[
                        target_id
                    ] = target

                    role_by_id[
                        target_id
                    ] = (
                        "supplemental"
                    )

                    supplemental_count = (
                        len(
                            included_by_id
                        )
                        - len(
                            primary_by_id
                        )
                    )

                    if (
                        supplemental_count
                        > max_supplemental_entries
                    ):
                        raise RuntimeError(
                            "Cross-reference closure exceeded safety "
                            f"limit for QAC root {qac_root}: "
                            f"{supplemental_count:,} supplemental entries. "
                            "Nothing was truncated; rerun with a higher "
                            "--max-supplemental-entries-per-root only after "
                            "reviewing why this root's Lane graph is so large."
                        )

                    queue.append(
                        (
                            target_id,
                            target,
                            target_depth,
                        )
                    )

                elif (
                    role_by_id.get(
                        target_id
                    )
                    == "supplemental"
                    and target_id
                    not in inspected
                ):
                    # It may have been discovered through another path first.
                    queue.append(
                        (
                            target_id,
                            included_by_id[
                                target_id
                            ],
                            target_depth,
                        )
                    )

    supplemental_output = []

    for target_id in sorted(
        (
            entry_id
            for entry_id
            in included_by_id
            if entry_id
            not in primary_by_id
        ),
        key=lambda entry_id: (
            (
                included_by_id[
                    entry_id
                ].get(
                    "source"
                )
                or {}
            ).get(
                "nodenum"
            )
            if (
                included_by_id[
                    entry_id
                ].get(
                    "source"
                )
                or {}
            ).get(
                "nodenum"
            )
            is not None
            else float(
                "inf"
            ),
            entry_id,
        ),
    ):
        target = included_by_id[
            target_id
        ]

        direct_memberships = (
            direct_roots_by_entry_id.get(
                target_id,
                [],
            )
        )

        paths = provenance_by_target.get(
            target_id,
            [],
        )

        min_depth = min(
            (
                int(
                    path[
                        "to_depth"
                    ]
                )
                for path in paths
            ),
            default=None,
        )

        supplemental_output.append(
            {
                "context_role":
                    (
                        "cross_reference_context_only"
                    ),

                "semantic_use_policy":
                    (
                        "Use this entry only to understand or resolve "
                        "a Lane cross-reference made by an included entry. "
                        "Do not treat this supplemental entry as an "
                        "independent sense of the QAC root unless primary "
                        "evidence separately supports that mapping."
                    ),

                "direct_qac_root_memberships":
                    direct_memberships,

                "minimum_reference_depth":
                    min_depth,

                "referenced_from":
                    paths,

                "entry":
                    target,
            }
        )

    audit = {
        "primary_entry_count":
            len(
                primary_entries
            ),

        "supplemental_entry_count":
            len(
                supplemental_output
            ),

        "included_entry_count":
            len(
                included_by_id
            ),

        "primary_text_char_count":
            sum(
                entry_text_chars(
                    entry
                )
                for entry
                in primary_entries
            ),

        "supplemental_text_char_count":
            sum(
                entry_text_chars(
                    item[
                        "entry"
                    ]
                )
                for item
                in supplemental_output
            ),

        "locatable_cross_reference_count":
            locatable_reference_count,

        "reference_without_node_locator_count":
            no_locator_reference_count,

        "references_to_primary_same_root_count":
            same_root_reference_count,

        "references_to_supplemental_context_count":
            supplemental_reference_count,

        "unresolved_node_locator_count":
            len(
                unresolved_locators
            ),

        "max_cross_reference_depth":
            max_depth_reached,

        "closure_complete_for_all_locatable_references":
            (
                len(
                    unresolved_locators
                )
                == 0
            ),
    }

    return (
        supplemental_output,
        unresolved_locators,
        audit,
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build complete root-local Lane evidence with transitive "
            "cross-reference context, while preserving the distinction "
            "between direct root entries and referenced supplemental entries."
        )
    )

    parser.add_argument(
        "--max-supplemental-entries-per-root",
        type=int,
        default=DEFAULT_MAX_SUPPLEMENTAL_ENTRIES_PER_ROOT,
        help=(
            "Safety guard only. The script fails rather than truncates if "
            "a root's explicit Lane cross-reference closure exceeds this "
            "number. Default: 5000."
        ),
    )

    args = parser.parse_args()

    if (
        args.max_supplemental_entries_per_root
        <= 0
    ):
        raise ValueError(
            "--max-supplemental-entries-per-root must be > 0"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        LANE_SEMANTICS_FILE,
        LANE_DB_FILE,
    ]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing required input:\n{path}"
            )

    print(
        "Loading frozen Lane/QAC semantics v2..."
    )

    source = load_json(
        LANE_SEMANTICS_FILE
    )

    roots = source.get(
        "roots",
        []
    )

    # --------------------------------------------------------
    # Global direct-entry membership index
    # --------------------------------------------------------

    direct_roots_by_entry_id: dict[
        int,
        set[str],
    ] = defaultdict(
        set
    )

    primary_attachment_count = 0
    primary_source_text_chars = 0

    for root_record in roots:
        qac = root_record.get(
            "qac",
            {}
        )

        root_id = qac.get(
            "root"
        )

        lane = (
            root_record.get(
                "lane"
            )
            or {}
        )

        for entry in lane.get(
            "entries",
            []
        ):
            entry_id = int(
                entry[
                    "entry_id"
                ]
            )

            direct_roots_by_entry_id[
                entry_id
            ].add(
                root_id
            )

            primary_attachment_count += 1

            primary_source_text_chars += (
                entry_text_chars(
                    entry
                )
            )

    direct_roots_by_entry_id_sorted = {
        entry_id:
            sorted(
                root_ids
            )
        for entry_id, root_ids
        in direct_roots_by_entry_id.items()
    }

    print(
        f"QAC root records: {len(roots):,}"
    )

    print(
        f"Primary Lane attachments: "
        f"{primary_attachment_count:,}"
    )

    # --------------------------------------------------------
    # DB connection + exact Lane parser
    # --------------------------------------------------------

    conn = open_sqlite_readonly(
        LANE_DB_FILE
    )

    try:
        pos_index, _ = load_pos_index(
            conn
        )

        store = LaneEntryStore(
            conn,
            pos_index,
        )

        output_roots = []

        roots_with_primary = 0
        roots_without_primary = 0

        roots_with_supplement = 0

        supplemental_root_target_pairs = 0
        unique_supplemental_entry_ids = set()

        total_supplemental_text_chars = 0

        unresolved_all = []

        max_depth_global = 0
        largest_supplement_roots = []

        sample_lookup = {}

        for root_index, root_record in enumerate(
            roots,
            start=1,
        ):
            qac = root_record.get(
                "qac",
                {}
            )

            root_id = qac.get(
                "root"
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

            primary_entries = (
                lane.get(
                    "entries",
                    []
                )
                or []
            )

            if not primary_entries:
                roots_without_primary += 1

                output_record = {
                    "root":
                        root_id,

                    "arabic":
                        qac.get(
                            "arabic"
                        ),

                    "qac":
                        qac,

                    "lane_match":
                        lane_match,

                    "primary_lane": {
                        "entry_count":
                            0,

                        "root_context":
                            lane,

                        "entries":
                            [],
                    },

                    "cross_reference_context": {
                        "policy":
                            (
                                "No supplemental context because this "
                                "QAC root has no directly matched Lane "
                                "entries in the frozen conservative match."
                            ),

                        "entry_count":
                            0,

                        "entries":
                            [],

                        "unresolved_references":
                            [],
                    },

                    "closure_audit": {
                        "primary_entry_count":
                            0,

                        "supplemental_entry_count":
                            0,

                        "included_entry_count":
                            0,

                        "primary_text_char_count":
                            0,

                        "supplemental_text_char_count":
                            0,

                        "locatable_cross_reference_count":
                            0,

                        "reference_without_node_locator_count":
                            0,

                        "references_to_primary_same_root_count":
                            0,

                        "references_to_supplemental_context_count":
                            0,

                        "unresolved_node_locator_count":
                            0,

                        "max_cross_reference_depth":
                            0,

                        "closure_complete_for_all_locatable_references":
                            True,
                    },
                }

                output_roots.append(
                    output_record
                )

                if root_id in SAMPLE_ROOTS:
                    sample_lookup[
                        root_id
                    ] = output_record

                continue

            roots_with_primary += 1

            (
                supplemental,
                unresolved,
                closure_audit,
            ) = build_root_closure(
                qac_root=root_id,
                primary_entries=primary_entries,
                direct_roots_by_entry_id=
                    direct_roots_by_entry_id_sorted,
                store=store,
                max_supplemental_entries=
                    args.max_supplemental_entries_per_root,
            )

            if supplemental:
                roots_with_supplement += 1

            supplemental_root_target_pairs += (
                len(
                    supplemental
                )
            )

            for item in supplemental:
                entry_id = int(
                    item[
                        "entry"
                    ][
                        "entry_id"
                    ]
                )

                unique_supplemental_entry_ids.add(
                    entry_id
                )

                total_supplemental_text_chars += (
                    entry_text_chars(
                        item[
                            "entry"
                        ]
                    )
                )

            if unresolved:
                unresolved_all.extend(
                    {
                        "root":
                            root_id,
                        **item,
                    }
                    for item
                    in unresolved
                )

            max_depth_global = max(
                max_depth_global,
                int(
                    closure_audit[
                        "max_cross_reference_depth"
                    ]
                ),
            )

            largest_supplement_roots.append(
                {
                    "root":
                        root_id,

                    "arabic":
                        qac.get(
                            "arabic"
                        ),

                    "primary_entry_count":
                        len(
                            primary_entries
                        ),

                    "supplemental_entry_count":
                        len(
                            supplemental
                        ),

                    "max_cross_reference_depth":
                        closure_audit[
                            "max_cross_reference_depth"
                        ],

                    "supplemental_text_char_count":
                        closure_audit[
                            "supplemental_text_char_count"
                        ],
                }
            )

            # Keep Lane's original root context metadata, but avoid
            # duplicating the full entry list inside root_context.
            lane_root_context = {
                key:
                    value
                for key, value
                in lane.items()
                if key
                != "entries"
            }

            output_record = {
                "root":
                    root_id,

                "arabic":
                    qac.get(
                        "arabic"
                    ),

                "qac":
                    qac,

                "lane_match":
                    lane_match,

                "primary_lane": {
                    "entry_count":
                        len(
                            primary_entries
                        ),

                    "root_context":
                        lane_root_context,

                    "entries":
                        primary_entries,
                },

                "cross_reference_context": {
                    "policy":
                        (
                            "These entries are included only because "
                            "a primary or already-followed Lane entry "
                            "explicitly references them. They are context "
                            "for resolving Lane's lexical discussion, not "
                            "direct evidence that the supplemental entry "
                            "belongs to this QAC root."
                        ),

                    "entry_count":
                        len(
                            supplemental
                        ),

                    "entries":
                        supplemental,

                    "unresolved_references":
                        unresolved,
                },

                "closure_audit":
                    closure_audit,
            }

            output_roots.append(
                output_record
            )

            if root_id in SAMPLE_ROOTS:
                sample_lookup[
                    root_id
                ] = output_record

            if (
                root_index
                % 100
                == 0
            ):
                print(
                    f"Processed {root_index:,}/"
                    f"{len(roots):,} roots..."
                )

    finally:
        conn.close()

    # --------------------------------------------------------
    # Hard primary-evidence completeness audit
    # --------------------------------------------------------

    output_primary_attachments = [
        (
            root_record[
                "root"
            ],
            int(
                entry[
                    "entry_id"
                ]
            ),
        )
        for root_record
        in output_roots
        for entry
        in root_record[
            "primary_lane"
        ][
            "entries"
        ]
    ]

    source_primary_attachments = [
        (
            (
                root_record.get(
                    "qac",
                    {}
                )
            ).get(
                "root"
            ),
            int(
                entry[
                    "entry_id"
                ]
            ),
        )
        for root_record
        in roots
        for entry
        in (
            (
                root_record.get(
                    "lane"
                )
                or {}
            ).get(
                "entries",
                []
            )
            or []
        )
    ]

    source_counter = Counter(
        source_primary_attachments
    )

    output_counter = Counter(
        output_primary_attachments
    )

    missing_primary = sorted(
        set(
            source_counter
        )
        - set(
            output_counter
        )
    )

    extra_primary = sorted(
        set(
            output_counter
        )
        - set(
            source_counter
        )
    )

    duplicate_output_primary = sorted(
        attachment
        for attachment, count
        in output_counter.items()
        if count
        != 1
    )

    output_primary_text_chars = sum(
        entry_text_chars(
            entry
        )
        for root_record
        in output_roots
        for entry
        in root_record[
            "primary_lane"
        ][
            "entries"
        ]
    )

    hard_primary_complete = (
        not missing_primary
        and not extra_primary
        and not duplicate_output_primary
        and (
            output_primary_text_chars
            == primary_source_text_chars
        )
    )

    if not hard_primary_complete:
        raise RuntimeError(
            "Primary Lane evidence completeness audit failed.\n"
            f"Missing primary attachments: {missing_primary[:50]}\n"
            f"Extra primary attachments: {extra_primary[:50]}\n"
            f"Duplicate output primary attachments: "
            f"{duplicate_output_primary[:50]}\n"
            f"Source text chars: {primary_source_text_chars}\n"
            f"Output text chars: {output_primary_text_chars}"
        )

    summary = {
        "qac_root_count":
            len(
                output_roots
            ),

        "roots_with_primary_lane_entries":
            roots_with_primary,

        "roots_without_primary_lane_entries":
            roots_without_primary,

        "primary_lane_attachment_count":
            len(
                output_primary_attachments
            ),

        "unique_primary_lane_entry_id_count":
            len(
                {
                    entry_id
                    for _, entry_id
                    in output_primary_attachments
                }
            ),

        "primary_source_text_char_count":
            primary_source_text_chars,

        "primary_output_text_char_count":
            output_primary_text_chars,

        "roots_with_cross_reference_supplement":
            roots_with_supplement,

        "supplemental_root_entry_pair_count":
            supplemental_root_target_pairs,

        "unique_supplemental_lane_entry_id_count":
            len(
                unique_supplemental_entry_ids
            ),

        "supplemental_text_char_count":
            total_supplemental_text_chars,

        "unresolved_locatable_cross_reference_count":
            len(
                unresolved_all
            ),

        "maximum_cross_reference_depth":
            max_depth_global,

        "hard_primary_evidence_complete":
            hard_primary_complete,

        "all_locatable_cross_references_closed":
            (
                len(
                    unresolved_all
                )
                == 0
            ),
    }

    output = {
        "metadata": {
            "dataset":
                (
                    "Complete root-local Lane lexical evidence with "
                    "transitive explicit cross-reference context"
                ),

            "version":
                1,

            "primary_source":
                str(
                    LANE_SEMANTICS_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "lane_database":
                str(
                    LANE_DB_FILE.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "parser":
                "extract_lane_semantics_v2",

            "purpose":
                (
                    "Final deterministic Lane evidence layer for Stage A2 "
                    "structured sense extraction. Direct root entries are "
                    "losslessly preserved; explicit node-based Lane "
                    "cross-references are followed transitively and stored "
                    "as clearly separated supplemental context."
                ),

            "semantic_rules": [
                (
                    "Primary Lane entries are direct evidence attached by "
                    "the frozen conservative QAC-to-Lane root match."
                ),
                (
                    "Supplemental cross-reference entries are NOT direct "
                    "root senses. They may only clarify a reference made "
                    "by a primary or followed Lane entry."
                ),
                (
                    "Cross-reference following never changes QAC root "
                    "membership."
                ),
                (
                    "References with no explicit Lane node locator are "
                    "preserved inside source entries but are not guessed "
                    "or fuzzily resolved."
                ),
                (
                    "No Lane source text is ranked, truncated, or omitted "
                    "from primary entries."
                ),
            ],
        },

        "summary":
            summary,

        "roots":
            output_roots,
    }

    write_json(
        FULL_OUTPUT,
        output,
    )

    report = {
        "summary":
            summary,

        "hard_checks": {
            "all_primary_attachments_present_exactly_once":
                (
                    not missing_primary
                    and not extra_primary
                    and not duplicate_output_primary
                ),

            "primary_source_text_character_accounting_exact":
                (
                    primary_source_text_chars
                    == output_primary_text_chars
                ),

            "all_locatable_cross_references_closed":
                (
                    len(
                        unresolved_all
                    )
                    == 0
                ),
        },

        "unresolved_locatable_cross_references":
            unresolved_all,

        "largest_cross_reference_supplements": sorted(
            largest_supplement_roots,
            key=lambda item: (
                -int(
                    item[
                        "supplemental_entry_count"
                    ]
                ),
                -int(
                    item[
                        "max_cross_reference_depth"
                    ]
                ),
                item[
                    "root"
                ],
            ),
        )[:100],
    }

    write_json(
        REPORT_OUTPUT,
        report,
    )

    sample = {
        "metadata": {
            "purpose":
                (
                    "Review final complete Lane evidence architecture "
                    "before Stage A2 structured sense extraction"
                ),

            "sample_roots":
                SAMPLE_ROOTS,
        },

        "roots": [
            sample_lookup[
                root_id
            ]
            for root_id
            in SAMPLE_ROOTS
            if root_id
            in sample_lookup
        ],
    }

    write_json(
        SAMPLE_OUTPUT,
        sample,
    )

    print()
    print("=" * 72)
    print(
        "COMPLETE ROOT-LOCAL LANE EVIDENCE V1 BUILT"
    )
    print("=" * 72)

    for key, value in summary.items():
        if isinstance(
            value,
            bool,
        ):
            display = str(
                value
            )

        elif isinstance(
            value,
            int,
        ):
            display = f"{value:,}"

        else:
            display = str(
                value
            )

        print(
            f"{key:<48} {display}"
        )

    print()
    print(
        "Full evidence:\n"
        f"{FULL_OUTPUT}"
    )

    print()
    print(
        "Audit report:\n"
        f"{REPORT_OUTPUT}"
    )

    print()
    print(
        "Review sample:\n"
        f"{SAMPLE_OUTPUT}"
    )

    print()
    print(
        "NEXT ACTION: upload "
        "lane_complete_root_evidence_report_v1.json "
        "and lane_complete_root_evidence_sample_v1.json."
    )


if __name__ == "__main__":
    main()
