#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

LANE_DB = SCRIPT_DIR / "sources" / "lane" / "lexicon.sqlite"
MATCH_AUDIT = SCRIPT_DIR / "lane_root_match_audit_v3.json"
QURAN_ROOTS_JSON = SCRIPT_DIR / "quran_roots_index.json"

OUTPUT_DIR = SCRIPT_DIR / "output"

FULL_OUTPUT = OUTPUT_DIR / "lane_quran_semantics_v2.json"
REPORT_OUTPUT = OUTPUT_DIR / "lane_extraction_report_v2.json"
SAMPLE_OUTPUT = OUTPUT_DIR / "lane_semantics_sample_v2.json"


# ============================================================
# Settings
# ============================================================

# Keep raw Lane XML out of the JSON by default because:
#   1. the SQLite file remains the source of truth;
#   2. XML substantially increases output size;
#   3. we extract the semantic content below.
#
# Change to True if you later want a lossless JSON duplicate
# of Lane's XML source text.
INCLUDE_RAW_XML = False

# Roots chosen to give us varied examples for UI/data-model review.
SAMPLE_QAC_ROOTS = [
    "rHm",   # رحم
    "ktb",   # كتب
    "qwl",   # قول
    "Hqq",   # حقق -> Lane حق
    "rbb",   # ربب -> Lane رب
    "Amn",   # أمن
    "rAy",   # رأي
    "Aty",   # still unresolved in the v2 audit
]


# ============================================================
# General helpers
# ============================================================

WHITESPACE_RE = re.compile(r"\s+")


def normalize_space(text: str | None) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = WHITESPACE_RE.sub(" ", text)

    return text.strip()


def unique_strings(values: list[str]) -> list[str]:
    seen = set()
    output = []

    for value in values:
        value = normalize_space(value)

        if not value:
            continue

        if value in seen:
            continue

        seen.add(value)
        output.append(value)

    return output


def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"

    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    return conn


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def roman(number: int) -> str:
    """
    Roman numerals for Arabic derived-form display.
    Supports more than we currently expect from Lane.
    """
    values = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]

    result = ""

    for value, symbol in values:
        while number >= value:
            result += symbol
            number -= value

    return result


# ============================================================
# Lane morphological classification
# ============================================================

NUMERIC_ITYPE_RE = re.compile(r"^\s*(\d+)\s*$")

# Lane also contains several quadriliteral/reduplicative type-code
# families. We preserve the family code instead of pretending that
# these are the same system as the ordinary Forms I-XII.
#
# Observed examples:
#   Q. 1
#   Q. Q. 2
#   R. Q. 1
#
# Spacing is inconsistent in the source, so normalize it here.
SPECIAL_ITYPE_RE = re.compile(
    r"^\s*(R\.\s*Q\.|Q\.\s*Q\.|Q\.)\s*(\d+)\s*$",
    re.IGNORECASE,
)


def normalize_special_family(raw_family: str) -> str:
    compact = re.sub(r"\s+", "", raw_family.upper())

    mapping = {
        "Q.": "Q",
        "Q.Q.": "Q.Q",
        "R.Q.": "R.Q",
    }

    return mapping.get(compact, compact)


def classify_itype(itype: str | None) -> dict:
    """
    Preserve Lane's type code exactly and add a conservative machine
    classification.

    Ordinary numeric values:
        1  -> Arabic derived Form I
        2  -> Arabic derived Form II
        ...
        12 -> Arabic derived Form XII

    Lane's Q / Q.Q / R.Q families are retained as distinct SOURCE
    families. We do not silently translate them into the ordinary
    triliteral Form system.
    """
    raw = normalize_space(itype)

    if not raw:
        return {
            "raw": "",
            "kind": "unclassified",
            "family": None,
            "form_number": None,
            "form_roman": None,
            "display": None,
        }

    numeric = NUMERIC_ITYPE_RE.match(raw)

    if numeric:
        number = int(numeric.group(1))

        return {
            "raw": raw,
            "kind": "derived_verb_form",
            "family": "triliteral",
            "form_number": number,
            "form_roman": roman(number),
            "display": f"Form {roman(number)}",
        }

    special = SPECIAL_ITYPE_RE.match(raw)

    if special:
        family = normalize_special_family(
            special.group(1)
        )
        number = int(special.group(2))

        return {
            "raw": raw,
            "kind": "lane_special_form_family",
            "family": family,
            "form_number": number,
            "form_roman": roman(number),
            "display": f"Lane {family} {roman(number)}",
        }

    return {
        "raw": raw,
        "kind": "other_lane_type",
        "family": None,
        "form_number": None,
        "form_roman": None,
        "display": raw,
    }



# ============================================================
# Lane structural sense segmentation
# ============================================================

LANE_SENSE_MARKER_RE = re.compile(
    r"-(?P<kind>A|b)(?P<number>\d+)-"
)

QURAN_REFERENCE_RE = re.compile(
    r"\bKur(?:\.|\b)",
    re.IGNORECASE,
)


def _block_flags(text: str) -> dict:
    lower = text.lower()

    return {
        "mentions_quran": bool(
            QURAN_REFERENCE_RE.search(text)
        ),
        "lane_marks_tropical":
            "tropical:" in lower,
        "lane_marks_assumed_tropical":
            "assumed tropical:" in lower,
        "mentions_primary_signification":
            "primary signification" in lower,
    }


def _fragments_for_block(
    block_text: str,
    emphasized_fragments: list[dict],
) -> list[dict]:
    """
    Attach Lane's emphasized source fragments to the structural block
    that visibly contains them.

    These fragments are NOT declared to be final glosses. They often
    contain the English definitional wording, but Lane also italicizes
    other material.
    """
    normalized_block = normalize_space(
        block_text
    )

    output = []
    seen = set()

    for fragment in emphasized_fragments:
        fragment_text = normalize_space(
            fragment.get("text")
        )

        if not fragment_text:
            continue

        if fragment_text not in normalized_block:
            continue

        key = (
            fragment.get("rend"),
            fragment_text,
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(
            {
                "rend":
                    fragment.get("rend"),
                "text":
                    fragment_text,
            }
        )

    return output


def build_lane_sense_groups(
    plain_text: str,
    emphasized_fragments: list[dict],
) -> list[dict]:
    """
    Convert Lane's inline milestone markers into a deterministic
    hierarchy.

    Lane entries frequently look conceptually like:

        main text
        -b2- subordinate sense
        -b3- subordinate sense
        -A2- next major sense
        -b2- subordinate sense under A2
        -A3- next major sense

    We DO NOT interpret these as modern semantic ontology labels.
    We merely preserve Lane's own structural divisions in a
    machine-friendly form.

    Output:
        [
          {
            "major_number": 1,
            "lane_marker": null,
            "main": {...},
            "sub_senses": [...]
          },
          {
            "major_number": 2,
            "lane_marker": "-A2-",
            "main": {...},
            "sub_senses": [...]
          }
        ]
    """
    plain_text = normalize_space(
        plain_text
    )

    if not plain_text:
        return []

    matches = list(
        LANE_SENSE_MARKER_RE.finditer(
            plain_text
        )
    )

    raw_blocks = []

    start = 0
    current_major = 1
    current_sub = None
    current_marker = None

    for match in matches:
        chunk = normalize_space(
            plain_text[
                start:match.start()
            ]
        )

        if chunk:
            raw_blocks.append(
                {
                    "major_number":
                        current_major,
                    "sub_number":
                        current_sub,
                    "lane_marker":
                        current_marker,
                    "text":
                        chunk,
                }
            )

        kind = match.group("kind")
        number = int(
            match.group("number")
        )

        if kind == "A":
            current_major = number
            current_sub = None
        else:
            current_sub = number

        current_marker = match.group(0)
        start = match.end()

    final_chunk = normalize_space(
        plain_text[start:]
    )

    if final_chunk:
        raw_blocks.append(
            {
                "major_number":
                    current_major,
                "sub_number":
                    current_sub,
                "lane_marker":
                    current_marker,
                "text":
                    final_chunk,
            }
        )

    groups_by_major = {}
    major_order = []

    for block in raw_blocks:
        major = block[
            "major_number"
        ]

        if major not in groups_by_major:
            groups_by_major[major] = {
                "major_number":
                    major,

                # A1 is normally implicit in Lane's text.
                "lane_marker":
                    (
                        block["lane_marker"]
                        if block[
                            "lane_marker"
                        ]
                        and block[
                            "lane_marker"
                        ].startswith("-A")
                        else None
                    ),

                "main":
                    None,

                "sub_senses":
                    [],
            }

            major_order.append(
                major
            )

        block_output = {
            "lane_marker":
                block[
                    "lane_marker"
                ],

            "text":
                block[
                    "text"
                ],

            "source_emphasis_fragments":
                _fragments_for_block(
                    block["text"],
                    emphasized_fragments,
                ),

            "flags":
                _block_flags(
                    block["text"]
                ),
        }

        group = groups_by_major[
            major
        ]

        if block[
            "sub_number"
        ] is None:
            # If multiple major-main pieces ever occur, preserve them
            # instead of replacing source text.
            if group["main"] is None:
                group["main"] = (
                    block_output
                )
            else:
                group[
                    "sub_senses"
                ].append(
                    {
                        "sub_number":
                            None,
                        **block_output,
                    }
                )

        else:
            group[
                "sub_senses"
            ].append(
                {
                    "sub_number":
                        block[
                            "sub_number"
                        ],
                    **block_output,
                }
            )

    return [
        groups_by_major[major]
        for major in major_order
    ]


# ============================================================
# Lane XML semantic extraction
# ============================================================

def local_tag(tag: str) -> str:
    """
    Strip an XML namespace if one ever appears.
    """
    return tag.rsplit("}", 1)[-1]


def element_text(element: ET.Element) -> str:
    return normalize_space("".join(element.itertext()))


def extract_lane_xml(xml_text: str | None) -> dict:
    """
    Extract semantic structure WITHOUT pretending to know more than Lane says.

    We keep:
      - full readable entry prose;
      - <sense> boundary/number markers;
      - emphasized/italic phrases;
      - Arabic/foreign terms;
      - cross references;
      - orthographic forms.

    Important:
    `emphasized_fragments` are NOT automatically called "meanings".
    Lane uses italics for many semantic/grammatical purposes. They are
    simply useful source fragments for later human/LLM analysis.
    """
    if not xml_text:
        return {
            "plain_text": "",
            "parse_ok": True,
            "parse_error": None,
            "sense_markers": [],
            "sense_groups": [],
            "emphasized_fragments": [],
            "foreign_terms": [],
            "orthographic_forms": [],
            "cross_references": [],
        }

    try:
        root = ET.fromstring(xml_text)

    except ET.ParseError as exc:
        # Fall back to a readable text representation instead of dropping
        # the entry. We surface the parse error explicitly.
        stripped = re.sub(r"<[^>]+>", " ", xml_text)

        result = {
            "plain_text": normalize_space(stripped),
            "parse_ok": False,
            "parse_error": str(exc),
            "sense_markers": [],
            "sense_groups": [],
            "emphasized_fragments": [],
            "foreign_terms": [],
            "orthographic_forms": [],
            "cross_references": [],
        }

        if INCLUDE_RAW_XML:
            result["raw_xml"] = xml_text

        return result

    sense_markers = []
    emphasized = []
    foreign_terms = []
    orthographic_forms = []
    cross_references = []

    for element in root.iter():
        tag = local_tag(element.tag)
        text = element_text(element)

        if tag == "sense":
            sense_markers.append(
                {
                    "type": element.attrib.get("type"),
                    "number": element.attrib.get("n"),
                    "label": text or None,
                }
            )

        elif tag == "hi":
            if text:
                emphasized.append(
                    {
                        "rend": element.attrib.get("rend"),
                        "text": text,
                    }
                )

        elif tag == "foreign":
            if text:
                foreign_terms.append(
                    {
                        "lang": element.attrib.get("lang"),
                        "text": text,
                    }
                )

        elif tag == "orth":
            if text:
                orthographic_forms.append(
                    {
                        "lang": element.attrib.get("lang"),
                        "type": element.attrib.get("type"),
                        "extent": element.attrib.get("extent"),
                        "text": text,
                    }
                )

        elif tag == "ref":
            cross_references.append(
                {
                    "text": text or None,
                    "cref": element.attrib.get("cref"),
                    "target": element.attrib.get("target"),
                    "select": element.attrib.get("select"),
                    "type": element.attrib.get("type"),
                    "subtype": element.attrib.get("subtype"),
                    "number": element.attrib.get("n"),
                }
            )

    # De-duplicate simple repeated fragments while preserving order.
    emphasized_output = []
    emphasized_seen = set()

    for item in emphasized:
        key = (item["rend"], item["text"])

        if key in emphasized_seen:
            continue

        emphasized_seen.add(key)
        emphasized_output.append(item)

    foreign_output = []
    foreign_seen = set()

    for item in foreign_terms:
        key = (item["lang"], item["text"])

        if key in foreign_seen:
            continue

        foreign_seen.add(key)
        foreign_output.append(item)

    ortho_output = []
    ortho_seen = set()

    for item in orthographic_forms:
        key = (
            item["lang"],
            item["type"],
            item["extent"],
            item["text"],
        )

        if key in ortho_seen:
            continue

        ortho_seen.add(key)
        ortho_output.append(item)

    plain_text = element_text(root)

    result = {
        "plain_text": plain_text,
        "parse_ok": True,
        "parse_error": None,
        "sense_markers": sense_markers,

        # New in v2: Lane's own A/b sense structure, preserved
        # deterministically rather than flattened.
        "sense_groups": build_lane_sense_groups(
            plain_text,
            emphasized_output,
        ),

        "emphasized_fragments": emphasized_output,
        "foreign_terms": foreign_output,
        "orthographic_forms": ortho_output,
        "cross_references": cross_references,
    }

    if INCLUDE_RAW_XML:
        result["raw_xml"] = xml_text

    return result


# ============================================================
# Lane POS table
# ============================================================

def load_pos_index(
    conn: sqlite3.Connection,
) -> tuple[dict[str, list[str]], Counter]:
    """
    Lane's POS table uses its own raw codes.

    We preserve those codes instead of prematurely translating every code
    into modern grammatical terminology. The report shows the complete
    code inventory so we can map it carefully in the next pass.
    """
    index: dict[str, list[str]] = defaultdict(list)
    inventory = Counter()

    rows = conn.execute(
        """
        SELECT nodeid, pos
        FROM pos
        WHERE nodeid IS NOT NULL
          AND pos IS NOT NULL
        ORDER BY id
        """
    )

    for row in rows:
        nodeid = row["nodeid"]
        pos = normalize_space(row["pos"])

        if not nodeid or not pos:
            continue

        inventory[pos] += 1

        if pos not in index[nodeid]:
            index[nodeid].append(pos)

    return index, inventory


# ============================================================
# Lane entry loading
# ============================================================

def load_entries_for_lane_roots(
    conn: sqlite3.Connection,
    allowed_root_spellings: set[str],
    pos_index: dict[str, list[str]],
) -> tuple[
    dict[str, list[dict]],
    Counter,
    Counter,
    int,
]:
    """
    Scan Lane's ~48k entry table once.

    Returns entries indexed by EXACT Lane Arabic root spelling.
    """
    by_root: dict[str, list[dict]] = defaultdict(list)

    itype_inventory = Counter()
    parse_failures = 0
    selected_entry_count = 0

    rows = conn.execute(
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
        ORDER BY nodenum, id
        """
    )

    for row in rows:
        lane_root = row["root"]

        if lane_root not in allowed_root_spellings:
            continue

        selected_entry_count += 1

        itype = normalize_space(row["itype"])
        itype_inventory[itype or "(empty)"] += 1

        semantic = extract_lane_xml(row["xml"])

        if not semantic["parse_ok"]:
            parse_failures += 1

        entry = {
            "entry_id": row["id"],
            "node_id": row["nodeid"],

            "lane_root_arabic": lane_root,
            "lane_root_buckwalter": row["broot"],

            "headword": row["headword"],
            "word": row["word"],
            "bareword": row["bareword"],
            "buckwalter_word": row["bword"],

            "itype": classify_itype(row["itype"]),

            # Raw Lane POS codes. We interpret these later, after seeing
            # the complete inventory.
            "pos_codes": pos_index.get(
                row["nodeid"],
                [],
            ),

            "source": {
                "page": row["page"],
                "file": row["file"],
                "nodenum": row["nodenum"],
                "supplement": bool(row["supplement"]),
                "entry_type": row["type"],
                "datasource": row["datasource"],
            },

            "dictionary": semantic,
        }

        by_root[lane_root].append(entry)

    for entries in by_root.values():
        entries.sort(
            key=lambda entry: (
                entry["source"]["nodenum"]
                if entry["source"]["nodenum"] is not None
                else float("inf"),

                entry["entry_id"],
            )
        )

    return (
        by_root,
        itype_inventory,
        Counter(),  # retained for backward-safe return structure
        parse_failures,
    )


# ============================================================
# Audit/match preparation
# ============================================================

def get_lane_spellings_from_result(
    result: dict,
) -> list[str]:
    lane = result.get("lane")

    if not lane:
        return []

    return [
        spelling
        for spelling in lane.get("arabic_spellings", [])
        if spelling
    ]


def qac_summary_from_audit_result(
    result: dict,
    quran_root_lookup: dict[str, dict],
) -> dict:
    qac_root = result["qac_root"]
    full = quran_root_lookup.get(
        qac_root,
        {}
    )

    return {
        "root":
            qac_root,

        "arabic":
            result["qac_arabic"],

        "arabic_spaced":
            full.get(
                "arabic_spaced"
            ),

        "radicals":
            full.get(
                "radicals",
                [],
            ),

        "occurrence_count":
            result.get(
                "qac_occurrence_count"
            ),

        "word_count":
            full.get(
                "word_count"
            ),

        "surah_count":
            full.get(
                "surah_count"
            ),

        "pos_counts":
            full.get(
                "pos_counts",
                {}
            ),

        "lemma_count":
            result.get(
                "qac_lemma_count"
            ),

        # These are the Quran lexemes we will later connect to
        # contextual word-by-word English glosses.
        "lemmas":
            full.get(
                "lemmas",
                []
            ),

        "verb":
            full.get(
                "verb",
                {}
            ),

        "derived_nominals":
            full.get(
                "derived_nominals",
                {}
            ),
    }


# ============================================================
# Main extraction
# ============================================================

def main() -> None:
    if not LANE_DB.exists():
        raise FileNotFoundError(
            f"Lane database not found:\n{LANE_DB}"
        )

    if not MATCH_AUDIT.exists():
        raise FileNotFoundError(
            f"Match audit not found:\n{MATCH_AUDIT}\n\n"
            "Run audit_lane_quran_root_matches_v3.py first."
        )

    if not QURAN_ROOTS_JSON.exists():
        raise FileNotFoundError(
            f"Quran root index not found:\n{QURAN_ROOTS_JSON}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading Lane/QAC match audit...")
    audit = load_json(MATCH_AUDIT)

    print("Loading Quran morphology root index...")
    quran_index = load_json(
        QURAN_ROOTS_JSON
    )

    quran_root_lookup = {
        root["root"]: root
        for root in quran_index[
            "roots"
        ]
    }

    results = audit["results"]

    print(f"QAC roots in audit: {len(results):,}")

    matched_results = [
        result
        for result in results
        if result.get("status") == "matched"
    ]

    unmatched_results = [
        result
        for result in results
        if result.get("status") != "matched"
    ]

    print(f"Matched roots:      {len(matched_results):,}")
    print(f"Unresolved roots:   {len(unmatched_results):,}")

    all_lane_spellings: set[str] = set()

    for result in matched_results:
        all_lane_spellings.update(
            get_lane_spellings_from_result(result)
        )

    print(
        f"Distinct Lane root spellings needed: "
        f"{len(all_lane_spellings):,}"
    )

    print("\nOpening Lane database read-only...")
    conn = open_sqlite_readonly(LANE_DB)

    try:
        print("Loading Lane POS index...")
        pos_index, pos_inventory = load_pos_index(conn)

        print(
            f"Distinct Lane POS codes: "
            f"{len(pos_inventory):,}"
        )

        print("\nExtracting relevant Lane entries...")

        (
            entries_by_root,
            itype_inventory,
            _unused,
            parse_failures,
        ) = load_entries_for_lane_roots(
            conn,
            all_lane_spellings,
            pos_index,
        )

    finally:
        conn.close()

    root_output = []

    total_extracted_entries = 0
    roots_with_zero_entries = []

    print("\nBuilding per-Quran-root semantic records...")

    for index, result in enumerate(results, start=1):
        qac = qac_summary_from_audit_result(result, quran_root_lookup)

        if result.get("status") != "matched":
            # Do NOT manufacture a Lane match.
            root_record = {
                "qac": qac,

                "lane_match": {
                    "status": result.get("status"),
                    "method": result.get(
                        "match_method"
                    ),
                },

                "lane": None,

                # Preserve diagnostic evidence from the matcher.
                # This is explicitly NOT treated as dictionary truth.
                "related_lane_candidates": {
                    "lemma_evidence":
                        result.get(
                            "lemma_evidence_candidates",
                            [],
                        ),

                    "nearest_root_candidates":
                        result.get(
                            "nearest_lane_root_candidates",
                            [],
                        ),
                },
            }

            root_output.append(root_record)
            continue

        lane_info = result["lane"]
        spellings = lane_info.get(
            "arabic_spellings",
            [],
        )

        entries = []

        for spelling in spellings:
            entries.extend(
                entries_by_root.get(
                    spelling,
                    [],
                )
            )

        # De-duplicate by Lane entry ID in case a group ever contains
        # spellings that converge on the same stored entry.
        dedup = {}
        for entry in entries:
            dedup[entry["entry_id"]] = entry

        entries = list(dedup.values())

        entries.sort(
            key=lambda entry: (
                entry["source"]["nodenum"]
                if entry["source"]["nodenum"] is not None
                else float("inf"),
                entry["entry_id"],
            )
        )

        total_extracted_entries += len(entries)

        if not entries:
            roots_with_zero_entries.append(
                qac["root"]
            )

        # This grouping is intentionally mechanical and source-driven.
        # It is NOT yet a semantic classification.
        form_groups: dict[str, list[int]] = defaultdict(list)
        unclassified_entry_ids = []

        for entry in entries:
            classification = entry["itype"]

            if (
                classification["kind"]
                == "derived_verb_form"
            ):
                label = (
                    f"Form "
                    f"{classification['form_roman']}"
                )

                form_groups[label].append(
                    entry["entry_id"]
                )

            elif (
                classification["kind"]
                == "lane_special_form_family"
            ):
                label = (
                    classification[
                        "display"
                    ]
                )

                form_groups[label].append(
                    entry["entry_id"]
                )

            else:
                unclassified_entry_ids.append(
                    entry["entry_id"]
                )

        root_record = {
            "qac": qac,

            "lane_match": {
                "status": "matched",
                "method":
                    result["match_method"],

                "qac_canonical_root":
                    result.get(
                        "qac_canonical_root"
                    ),

                "contracted_qac_root":
                    result.get(
                        "contracted_qac_root"
                    ),
            },

            "lane": {
                "canonical_root":
                    lane_info[
                        "canonical_root"
                    ],

                "arabic_spellings":
                    spellings,

                "buckwalter_spellings":
                    lane_info.get(
                        "buckwalter_spellings",
                        [],
                    ),

                "root_records":
                    lane_info.get(
                        "records",
                        [],
                    ),

                "has_main_record":
                    lane_info.get(
                        "has_main_record",
                        False,
                    ),

                "has_supplement_record":
                    lane_info.get(
                        "has_supplement_record",
                        False,
                    ),

                "entry_count":
                    len(entries),

                # Useful first-pass organization for the UI.
                # Do not treat "unclassified" as a linguistic category;
                # it simply means Lane's `itype` did not identify a
                # numbered verb form.
                "entry_groups": {
                    "derived_forms": {
                        key: value
                        for key, value in sorted(
                            form_groups.items()
                        )
                    },

                    "unclassified_entry_ids":
                        unclassified_entry_ids,
                },

                "entries":
                    entries,
            },
        }

        root_output.append(root_record)

        if index % 200 == 0:
            print(
                f"  prepared {index:,}/"
                f"{len(results):,} roots..."
            )

    # Ensure QAC root ordering remains deterministic.
    root_output.sort(
        key=lambda item: item["qac"]["root"]
    )

    full_dataset = {
        "metadata": {
            "dataset":
                "Quran roots enriched with Lane's Arabic-English Lexicon — semantic source v2",

            "source_qac_match_audit":
                MATCH_AUDIT.name,

            "source_qac_morphology_index":
                QURAN_ROOTS_JSON.name,

            "source_lane":
                str(
                    LANE_DB.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "lane_database_opened_read_only":
                True,

            "raw_xml_included":
                INCLUDE_RAW_XML,

            "semantic_source_version": 2,

            "principles": [
                "QAC is the canonical Quran root inventory.",
                "Lane is preserved as a separate lexical-semantic source.",
                "Lane entries are not flattened into one root definition.",
                "Numbered Lane itype values are grouped as derived verb forms.",
                "Lane Q / Q.Q / R.Q type families are preserved as separate source families.",
                "Unclassified entries are not guessed to be nouns.",
                "Lane POS codes are retained raw for later mapping.",
                "Lane A/b sense markers are converted into source-faithful structural sense groups.",
                "Emphasized Lane text is preserved as source fragments, not automatically labeled as a gloss.",
                "Unmatched QAC roots remain unmatched rather than receiving fuzzy automatic assignments.",
                "Main and supplement material are both retained.",
            ],
        },

        "summary": {
            "qac_root_count":
                len(results),

            "matched_qac_roots":
                len(matched_results),

            "unresolved_qac_roots":
                len(unmatched_results),

            "distinct_lane_root_spellings_extracted":
                len(all_lane_spellings),

            "lane_entries_extracted":
                total_extracted_entries,

            "lane_xml_parse_failures":
                parse_failures,

            "matched_roots_with_zero_lane_entries":
                len(
                    roots_with_zero_entries
                ),
        },

        "roots":
            root_output,
    }

    FULL_OUTPUT.write_text(
        json.dumps(
            full_dataset,
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
            full_dataset["summary"],

        "lane_pos_code_inventory": {
            key: pos_inventory[key]
            for key in sorted(
                pos_inventory
            )
        },

        "lane_itype_inventory_for_extracted_entries": {
            key: itype_inventory[key]
            for key in sorted(
                itype_inventory
            )
        },

        "matched_roots_with_zero_lane_entries":
            roots_with_zero_entries,

        "output_files": {
            "full":
                str(
                    FULL_OUTPUT.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "sample":
                str(
                    SAMPLE_OUTPUT.relative_to(
                        SCRIPT_DIR
                    )
                ),
        },
    }

    REPORT_OUTPUT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Small review sample
    # --------------------------------------------------------

    root_lookup = {
        item["qac"]["root"]: item
        for item in root_output
    }

    sample_roots = []

    for qac_root in SAMPLE_QAC_ROOTS:
        if qac_root in root_lookup:
            sample_roots.append(
                root_lookup[qac_root]
            )

    sample_dataset = {
        "metadata": {
            "purpose":
                "Small review sample from lane_quran_semantics_v2.json",

            "roots_requested":
                SAMPLE_QAC_ROOTS,
        },

        "roots":
            sample_roots,
    }

    SAMPLE_OUTPUT.write_text(
        json.dumps(
            sample_dataset,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 58)
    print("LANE SEMANTIC EXTRACTION COMPLETE")
    print("=" * 58)

    print(
        f"QAC roots:                      "
        f"{len(results):,}"
    )

    print(
        f"Matched roots with Lane source: "
        f"{len(matched_results):,}"
    )

    print(
        f"Unresolved roots retained:      "
        f"{len(unmatched_results):,}"
    )

    print(
        f"Lane entries extracted:         "
        f"{total_extracted_entries:,}"
    )

    print(
        f"XML parse failures:             "
        f"{parse_failures:,}"
    )

    print(
        f"Matched roots with 0 entries:   "
        f"{len(roots_with_zero_entries):,}"
    )

    print()
    print(
        "Full semantic source dataset:\n"
        f"{FULL_OUTPUT}"
    )

    print()
    print(
        "Extraction report:\n"
        f"{REPORT_OUTPUT}"
    )

    print()
    print(
        "Small sample to upload to ChatGPT:\n"
        f"{SAMPLE_OUTPUT}"
    )

    print()
    print(
        f"Full JSON size: "
        f"{FULL_OUTPUT.stat().st_size / (1024 * 1024):.2f} MB"
    )

    print(
        f"Sample JSON size: "
        f"{SAMPLE_OUTPUT.stat().st_size / 1024:.1f} KB"
    )

    print()
    print(
        "NEXT ACTION: upload BOTH "
        "lane_extraction_report_v2.json and "
        "lane_semantics_sample_v2.json to ChatGPT."
    )


if __name__ == "__main__":
    main()
