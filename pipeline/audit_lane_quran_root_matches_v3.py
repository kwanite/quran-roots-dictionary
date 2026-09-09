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

QURAN_ROOTS_JSON = SCRIPT_DIR / "quran_roots_index.json"
LANE_DB = SCRIPT_DIR / "sources" / "lane" / "lexicon.sqlite"

OUTPUT_FILE = SCRIPT_DIR / "lane_root_match_audit_v3.json"


# ============================================================
# Arabic normalization
# ============================================================

ARABIC_MARKS_RE = re.compile(
    "["
    "\u0610-\u061A"
    "\u064B-\u065F"
    "\u0670"
    "\u06D6-\u06ED"
    "]"
)


def strip_arabic_marks(text: str) -> str:
    """
    Remove Quranic/Arabic combining marks and tatweel while retaining letters.
    """
    text = unicodedata.normalize("NFC", text or "")
    text = ARABIC_MARKS_RE.sub("", text)
    return text.replace("\u0640", "")


def normalize_root(text: str) -> str:
    """
    Normalize a ROOT for radical-level comparison.

    Root comparison is not ordinary spelling comparison:
      - hamza seat variants represent the same hamza radical;
      - final alif maqsurah and ya are normalized for root matching;
      - Quranic marks/tashkil are removed.

    We deliberately DO NOT:
      - merge waw and ya;
      - infer missing radicals generally;
      - collapse arbitrary roots;
      - use fuzzy matching as an automatic match.
    """
    text = strip_arabic_marks(text)

    replacements = {
        "أ": "ء",
        "إ": "ء",
        "ؤ": "ء",
        "ئ": "ء",
        "آ": "ء",
        "ٱ": "ا",
        "ى": "ي",
    }

    normalized = "".join(replacements.get(ch, ch) for ch in text)

    # Lane's ROOT table often represents an INITIAL hamza radical with
    # bare alif, while QAC ROOT identifiers encode the radical explicitly
    # as hamza.  At root level:
    #
    #   Lane اتى / AtY  <->  QAC أتي / Aty
    #   Lane امن / Amn  <->  QAC أمن / Amn
    #
    # Initial consonantal alif in a lexical ROOT key is therefore treated
    # as the hamza radical. We do NOT rewrite medial/final alif here.
    if normalized.startswith("ا"):
        normalized = "ء" + normalized[1:]

    return normalized


def normalize_word(text: str) -> str:
    """
    Conservative normalization for comparing QAC lemmas to Lane headwords.

    This is used ONLY as supporting evidence for unmatched roots.
    It is never, by itself, allowed to rewrite the canonical QAC root.
    """
    text = strip_arabic_marks(text)

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
    }

    return "".join(replacements.get(ch, ch) for ch in text)


def is_qac_explicit_geminate(root: str) -> bool:
    """
    QAC writes triliteral geminate roots with the repeated final radical
    explicitly, e.g. rbb -> ربب, Hqq -> حقق.

    Lane commonly files these lexicographically in contracted form:
    رب, حق, etc.
    """
    return len(root) == 3 and root[1] == root[2]


def contract_qac_geminate(root: str) -> str | None:
    if not is_qac_explicit_geminate(root):
        return None
    return root[:2]



def is_reduplicated_quadriliteral(root: str) -> bool:
    """
    Some QAC quadriliteral roots explicitly repeat a two-radical base:

        زلزل -> زل + زل
        وسوس -> وس + وس
        دمدم -> دم + دم

    Lane frequently files such lexical families under the contracted
    two-radical root. This rule is deliberately limited to the exact
    ABAB pattern; arbitrary quadriliterals are never contracted.
    """
    return len(root) == 4 and root[:2] == root[2:]


def contract_reduplicated_quadriliteral(root: str) -> str | None:
    if not is_reduplicated_quadriliteral(root):
        return None
    return root[:2]


# ============================================================
# Generic helpers
# ============================================================

def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_quran_roots(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict) or not isinstance(data.get("roots"), list):
        raise ValueError(
            f"{path.name} does not look like quran_roots_index.json"
        )

    return data["roots"]


def levenshtein(a: str, b: str) -> int:
    """
    Small deterministic edit-distance helper for REVIEW SUGGESTIONS ONLY.
    It is never used to auto-match roots.
    """
    if a == b:
        return 0

    if not a:
        return len(b)

    if not b:
        return len(a)

    previous = list(range(len(b) + 1))

    for i, ca in enumerate(a, start=1):
        current = [i]

        for j, cb in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (ca != cb)

            current.append(min(insert, delete, replace))

        previous = current

    return previous[-1]


def unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    output = []

    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)

    return output


# ============================================================
# Lane root grouping
# ============================================================

def fetch_lane_root_records(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            id,
            datasource,
            word,
            bword,
            letter,
            bletter,
            supplement,
            quasi,
            alternates,
            page
        FROM root
        ORDER BY id
        """
    ).fetchall()

    return [dict(row) for row in rows]


def build_lane_root_groups(
    root_records: list[dict],
) -> dict[str, dict]:
    """
    Collapse Lane rows that represent the same lexical root into one group.

    This intentionally merges, for example:
      - Lane main root row (supplement=0)
      - Lane supplement root row (supplement=1)

    It also merges repeated root-table rows whose Arabic root normalizes
    to the same radical identity.

    The ORIGINAL rows remain preserved inside `records`.
    """
    groups: dict[str, dict] = {}

    for record in root_records:
        arabic = record.get("word") or ""

        if not arabic:
            continue

        canonical = normalize_root(arabic)

        group = groups.setdefault(
            canonical,
            {
                "canonical_root": canonical,
                "arabic_spellings": [],
                "buckwalter_spellings": [],
                "records": [],
            },
        )

        if arabic not in group["arabic_spellings"]:
            group["arabic_spellings"].append(arabic)

        bword = record.get("bword")
        if bword and bword not in group["buckwalter_spellings"]:
            group["buckwalter_spellings"].append(bword)

        group["records"].append(record)

    for group in groups.values():
        group["arabic_spellings"].sort()
        group["buckwalter_spellings"].sort()
        group["records"].sort(key=lambda row: row["id"])

    return groups


def build_lane_indexes(
    groups: dict[str, dict],
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    """
    Return indexes mapping:
      exact unmarked Arabic spelling -> Lane canonical group keys
      Lane bword                 -> Lane canonical group keys
      normalized radical form    -> Lane canonical group keys
    """
    exact_arabic: dict[str, set[str]] = defaultdict(set)
    exact_bword: dict[str, set[str]] = defaultdict(set)
    canonical: dict[str, set[str]] = defaultdict(set)

    for group_key, group in groups.items():
        canonical[group_key].add(group_key)

        for spelling in group["arabic_spellings"]:
            exact_arabic[strip_arabic_marks(spelling)].add(group_key)

        for bword in group["buckwalter_spellings"]:
            exact_bword[bword].add(group_key)

    return exact_arabic, exact_bword, canonical


# ============================================================
# Lane entries
# ============================================================

def fetch_entry_metadata(conn: sqlite3.Connection) -> list[dict]:
    """
    47k-ish rows: small enough to load once locally.

    We intentionally DO NOT export Lane XML at this stage.
    """
    rows = conn.execute(
        """
        SELECT
            id,
            root,
            broot,
            word,
            bword,
            bareword,
            headword,
            itype,
            nodeid,
            page,
            supplement,
            type
        FROM entry
        ORDER BY id
        """
    ).fetchall()

    return [dict(row) for row in rows]


def build_entry_indexes(
    entries: list[dict],
) -> tuple[
    dict[str, Counter],
    dict[str, Counter],
    dict[str, int],
    dict[str, list[dict]],
]:
    """
    Build:
      normalized lexical word -> Counter of Lane canonical roots
      Lane canonical root     -> Counter of normalized lexical words
      Lane canonical root     -> number of entries
      Lane canonical root     -> representative entry metadata

    The lexical-word index is used only as evidence for unresolved QAC roots.
    """
    word_to_roots: dict[str, Counter] = defaultdict(Counter)
    root_to_words: dict[str, Counter] = defaultdict(Counter)
    entry_counts: dict[str, int] = defaultdict(int)
    samples: dict[str, list[dict]] = defaultdict(list)

    for entry in entries:
        root = entry.get("root") or ""

        if not root:
            continue

        lane_root = normalize_root(root)
        entry_counts[lane_root] += 1

        if len(samples[lane_root]) < 8:
            samples[lane_root].append(
                {
                    "id": entry["id"],
                    "root": entry.get("root"),
                    "broot": entry.get("broot"),
                    "word": entry.get("word"),
                    "bword": entry.get("bword"),
                    "bareword": entry.get("bareword"),
                    "headword": entry.get("headword"),
                    "itype": entry.get("itype"),
                    "nodeid": entry.get("nodeid"),
                    "page": entry.get("page"),
                    "supplement": entry.get("supplement"),
                    "type": entry.get("type"),
                }
            )

        lexical_candidates = [
            entry.get("bareword"),
            entry.get("headword"),
            entry.get("word"),
        ]

        for value in lexical_candidates:
            if not value:
                continue

            normalized = normalize_word(value)

            if not normalized:
                continue

            word_to_roots[normalized][lane_root] += 1
            root_to_words[lane_root][normalized] += 1

    return word_to_roots, root_to_words, entry_counts, samples


# ============================================================
# QAC lemma evidence
# ============================================================

def qac_lemma_evidence(
    qroot: dict,
    word_to_lane_roots: dict[str, Counter],
    lane_groups: dict[str, dict],
) -> list[dict]:
    """
    Find Lane roots whose lexical entries overlap QAC lemmas.

    IMPORTANT:
    This is supporting evidence only. It does NOT automatically match a
    previously unresolved root, because one Arabic lexical form can be
    semantically or historically ambiguous.
    """
    candidate_data: dict[str, dict] = {}

    for lemma in qroot.get("lemmas", []):
        arabic = lemma.get("arabic")

        if not arabic:
            continue

        normalized_lemma = normalize_word(arabic)
        lane_candidates = word_to_lane_roots.get(normalized_lemma)

        if not lane_candidates:
            continue

        qac_occurrences = lemma.get("occurrence_count") or 0

        for lane_root, lane_entry_hits in lane_candidates.items():
            if lane_root not in lane_groups:
                # The entry table can theoretically contain a root not present
                # in the root table. Keep it visible instead of crashing.
                lane_display = {
                    "canonical_root": lane_root,
                    "arabic_spellings": [],
                    "buckwalter_spellings": [],
                    "records": [],
                }
            else:
                lane_display = lane_groups[lane_root]

            bucket = candidate_data.setdefault(
                lane_root,
                {
                    "lane_canonical_root": lane_root,
                    "lane_arabic_spellings":
                        lane_display["arabic_spellings"],
                    "lane_buckwalter_spellings":
                        lane_display["buckwalter_spellings"],
                    "matched_qac_lemmas": [],
                    "distinct_lemma_matches": 0,
                    "qac_occurrence_weight": 0,
                    "lane_entry_hits": 0,
                },
            )

            bucket["matched_qac_lemmas"].append(
                {
                    "lemma_id": lemma.get("id"),
                    "lemma_arabic": arabic,
                    "normalized_lemma": normalized_lemma,
                    "qac_occurrence_count": qac_occurrences,
                    "matching_lane_entry_count": lane_entry_hits,
                }
            )

            bucket["distinct_lemma_matches"] += 1
            bucket["qac_occurrence_weight"] += qac_occurrences
            bucket["lane_entry_hits"] += lane_entry_hits

    candidates = list(candidate_data.values())

    candidates.sort(
        key=lambda row: (
            -row["distinct_lemma_matches"],
            -row["qac_occurrence_weight"],
            -row["lane_entry_hits"],
            row["lane_canonical_root"],
        )
    )

    return candidates[:12]


# ============================================================
# Review suggestions
# ============================================================

def nearest_lane_roots(
    qac_canonical_root: str,
    lane_groups: dict[str, dict],
    limit: int = 8,
) -> list[dict]:
    """
    Fuzzy suggestions for human review only.

    They are NEVER automatically promoted to a match.
    """
    scored = []

    for lane_root, group in lane_groups.items():
        distance = levenshtein(qac_canonical_root, lane_root)

        # Only retain reasonably close roots.
        if distance <= 2:
            scored.append(
                (
                    distance,
                    abs(len(qac_canonical_root) - len(lane_root)),
                    lane_root,
                    group,
                )
            )

    scored.sort(key=lambda row: (row[0], row[1], row[2]))

    output = []

    for distance, _, lane_root, group in scored[:limit]:
        output.append(
            {
                "edit_distance": distance,
                "lane_canonical_root": lane_root,
                "arabic_spellings": group["arabic_spellings"],
                "buckwalter_spellings": group["buckwalter_spellings"],
            }
        )

    return output


# ============================================================
# Match logic
# ============================================================

def choose_candidate(
    candidate_keys: set[str],
) -> tuple[str | None, str]:
    """
    Convert candidate-set size into a result status.
    """
    if not candidate_keys:
        return None, "none"

    if len(candidate_keys) == 1:
        return next(iter(candidate_keys)), "unique"

    return None, "ambiguous"


def group_public(
    group_key: str,
    groups: dict[str, dict],
    entry_counts: dict[str, int],
    entry_samples: dict[str, list[dict]],
) -> dict:
    group = groups[group_key]

    records = []

    for row in group["records"]:
        records.append(
            {
                "id": row["id"],
                "arabic": row.get("word"),
                "buckwalter": row.get("bword"),
                "page": row.get("page"),
                "supplement": row.get("supplement"),
                "quasi": row.get("quasi"),
                "alternates": row.get("alternates"),
            }
        )

    return {
        "canonical_root": group_key,
        "arabic_spellings": group["arabic_spellings"],
        "buckwalter_spellings": group["buckwalter_spellings"],
        "root_record_count": len(records),
        "has_main_record": any(
            row.get("supplement") == 0
            for row in group["records"]
        ),
        "has_supplement_record": any(
            row.get("supplement") == 1
            for row in group["records"]
        ),
        "records": records,
        "lane_entry_count": entry_counts.get(group_key, 0),
        "entry_samples": entry_samples.get(group_key, []),
    }


def match_one_root(
    qroot: dict,
    groups: dict[str, dict],
    exact_arabic_index: dict[str, set[str]],
    exact_bword_index: dict[str, set[str]],
    canonical_index: dict[str, set[str]],
) -> dict:
    qac_root = qroot["root"]
    qac_arabic = qroot["arabic"]

    qac_exact_arabic = strip_arabic_marks(qac_arabic)
    qac_canonical = normalize_root(qac_arabic)

    # --------------------------------------------------------
    # Rule 1: exact Arabic root spelling
    # --------------------------------------------------------
    candidate_keys = exact_arabic_index.get(
        qac_exact_arabic,
        set(),
    )

    candidate, status = choose_candidate(candidate_keys)

    if status == "unique":
        return {
            "status": "matched",
            "match_method": "exact_arabic",
            "lane_group_key": candidate,
            "qac_canonical_root": qac_canonical,
        }

    if status == "ambiguous":
        return {
            "status": "ambiguous",
            "match_method": "exact_arabic",
            "candidate_group_keys": sorted(candidate_keys),
            "qac_canonical_root": qac_canonical,
        }

    # --------------------------------------------------------
    # Rule 2: exact transliteration identity
    # --------------------------------------------------------
    candidate_keys = exact_bword_index.get(
        qac_root,
        set(),
    )

    candidate, status = choose_candidate(candidate_keys)

    if status == "unique":
        return {
            "status": "matched",
            "match_method": "exact_buckwalter",
            "lane_group_key": candidate,
            "qac_canonical_root": qac_canonical,
        }

    if status == "ambiguous":
        return {
            "status": "ambiguous",
            "match_method": "exact_buckwalter",
            "candidate_group_keys": sorted(candidate_keys),
            "qac_canonical_root": qac_canonical,
        }

    # --------------------------------------------------------
    # Rule 3: canonical radical identity
    #         (hamza seats + final maqsura/ya normalization)
    # --------------------------------------------------------
    candidate_keys = canonical_index.get(
        qac_canonical,
        set(),
    )

    candidate, status = choose_candidate(candidate_keys)

    if status == "unique":
        return {
            "status": "matched",
            "match_method": "normalized_radicals",
            "lane_group_key": candidate,
            "qac_canonical_root": qac_canonical,
        }

    if status == "ambiguous":
        return {
            "status": "ambiguous",
            "match_method": "normalized_radicals",
            "candidate_group_keys": sorted(candidate_keys),
            "qac_canonical_root": qac_canonical,
        }

    # --------------------------------------------------------
    # Rule 4: QAC explicit geminate -> Lane contracted root
    #
    #   QAC: ربب / rbb
    #   Lane: رب
    #
    # This rule is intentionally limited to a three-radical QAC root
    # whose second and third radicals are identical.
    # --------------------------------------------------------
    contracted = contract_qac_geminate(qac_canonical)

    if contracted:
        candidate_keys = canonical_index.get(
            contracted,
            set(),
        )

        candidate, status = choose_candidate(candidate_keys)

        if status == "unique":
            return {
                "status": "matched",
                "match_method": "geminate_contraction",
                "lane_group_key": candidate,
                "qac_canonical_root": qac_canonical,
                "contracted_qac_root": contracted,
            }

        if status == "ambiguous":
            return {
                "status": "ambiguous",
                "match_method": "geminate_contraction",
                "candidate_group_keys": sorted(candidate_keys),
                "qac_canonical_root": qac_canonical,
                "contracted_qac_root": contracted,
            }

    # --------------------------------------------------------
    # Rule 5: exact ABAB reduplicated quadriliteral contraction
    #
    #   QAC: زلزل
    #   Lane: زل
    #
    # No other four-radical pattern is contracted.
    # --------------------------------------------------------
    reduplicated = contract_reduplicated_quadriliteral(
        qac_canonical
    )

    if reduplicated:
        candidate_keys = canonical_index.get(
            reduplicated,
            set(),
        )

        candidate, status = choose_candidate(candidate_keys)

        if status == "unique":
            return {
                "status": "matched",
                "match_method": "reduplicated_quadriliteral_contraction",
                "lane_group_key": candidate,
                "qac_canonical_root": qac_canonical,
                "contracted_qac_root": reduplicated,
            }

        if status == "ambiguous":
            return {
                "status": "ambiguous",
                "match_method": "reduplicated_quadriliteral_contraction",
                "candidate_group_keys": sorted(candidate_keys),
                "qac_canonical_root": qac_canonical,
                "contracted_qac_root": reduplicated,
            }

    return {
        "status": "unmatched",
        "match_method": None,
        "qac_canonical_root": qac_canonical,
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    if not QURAN_ROOTS_JSON.exists():
        raise FileNotFoundError(
            f"Missing:\n{QURAN_ROOTS_JSON}"
        )

    if not LANE_DB.exists():
        raise FileNotFoundError(
            f"Missing:\n{LANE_DB}"
        )

    print("Loading QAC root index...")
    quran_roots = load_quran_roots(QURAN_ROOTS_JSON)

    print(f"QAC roots: {len(quran_roots):,}")

    print("\nOpening Lane SQLite database read-only...")
    conn = open_sqlite_readonly(LANE_DB)

    try:
        print("Loading Lane root table...")
        root_records = fetch_lane_root_records(conn)

        print(f"Lane root records: {len(root_records):,}")

        groups = build_lane_root_groups(root_records)

        print(
            f"Lane lexical root groups after merging duplicate/"
            f"supplement spellings: {len(groups):,}"
        )

        (
            exact_arabic_index,
            exact_bword_index,
            canonical_index,
        ) = build_lane_indexes(groups)

        print("\nLoading Lane entry metadata...")
        entries = fetch_entry_metadata(conn)

        print(f"Lane lexical entries: {len(entries):,}")

        (
            word_to_lane_roots,
            _root_to_words,
            entry_counts,
            entry_samples,
        ) = build_entry_indexes(entries)

        method_counts = Counter()
        results = []
        unmatched = []
        ambiguous = []
        non_exact_review = []

        merged_main_supplement_matches = 0

        print("\nMatching QAC roots to Lane...")

        for index, qroot in enumerate(quran_roots, start=1):
            base = {
                "qac_root": qroot["root"],
                "qac_arabic": qroot["arabic"],
                "qac_occurrence_count":
                    qroot.get("occurrence_count"),
                "qac_lemma_count":
                    qroot.get("lemma_count"),
            }

            match = match_one_root(
                qroot,
                groups,
                exact_arabic_index,
                exact_bword_index,
                canonical_index,
            )

            status = match["status"]

            if status == "matched":
                lane_key = match["lane_group_key"]
                lane_info = group_public(
                    lane_key,
                    groups,
                    entry_counts,
                    entry_samples,
                )

                method = match["match_method"]
                method_counts[method] += 1
                method_counts["matched"] += 1

                if (
                    lane_info["has_main_record"]
                    and lane_info["has_supplement_record"]
                ):
                    merged_main_supplement_matches += 1

                result = {
                    **base,
                    **match,
                    "lane": lane_info,
                }

                results.append(result)

                if method != "exact_arabic":
                    non_exact_review.append(result)

            elif status == "ambiguous":
                method_counts["ambiguous"] += 1

                candidates = [
                    group_public(
                        key,
                        groups,
                        entry_counts,
                        entry_samples,
                    )
                    for key in match["candidate_group_keys"]
                ]

                result = {
                    **base,
                    **match,
                    "lane_candidates": candidates,
                }

                ambiguous.append(result)
                results.append(result)

            else:
                method_counts["unmatched"] += 1

                qac_canonical = match[
                    "qac_canonical_root"
                ]

                lemma_evidence = qac_lemma_evidence(
                    qroot,
                    word_to_lane_roots,
                    groups,
                )

                nearest = nearest_lane_roots(
                    qac_canonical,
                    groups,
                    limit=8,
                )

                result = {
                    **base,
                    **match,

                    # Diagnostic only:
                    "lemma_evidence_candidates":
                        lemma_evidence,

                    # Diagnostic only:
                    "nearest_lane_root_candidates":
                        nearest,
                }

                unmatched.append(result)
                results.append(result)

            if index % 200 == 0:
                print(
                    f"  processed {index:,}/"
                    f"{len(quran_roots):,}"
                )

        # Most important unresolved Quran roots first.
        unmatched.sort(
            key=lambda row: (
                -(row.get("qac_occurrence_count") or 0),
                row["qac_root"],
            )
        )

        ambiguous.sort(
            key=lambda row: (
                -(row.get("qac_occurrence_count") or 0),
                row["qac_root"],
            )
        )

        non_exact_review.sort(
            key=lambda row: (
                -(row.get("qac_occurrence_count") or 0),
                row["qac_root"],
            )
        )

        total = len(quran_roots)
        matched = method_counts["matched"]

        unmatched_with_lemma_evidence = sum(
            bool(row["lemma_evidence_candidates"])
            for row in unmatched
        )

        high_confidence_single_lemma_candidate = 0

        for row in unmatched:
            evidence = row[
                "lemma_evidence_candidates"
            ]

            if len(evidence) == 1:
                high_confidence_single_lemma_candidate += 1

        report = {
            "metadata": {
                "version": 3,
                "quran_source":
                    QURAN_ROOTS_JSON.name,
                "lane_source":
                    str(LANE_DB.relative_to(SCRIPT_DIR)),
                "lane_opened_read_only": True,
                "purpose": (
                    "Lexicographic-equivalence audit between "
                    "Quranic Arabic Corpus v0.4 roots and "
                    "Lane's Arabic-English Lexicon."
                ),
            },

            "summary": {
                "qac_root_count": total,
                "lane_root_record_count":
                    len(root_records),

                "lane_root_group_count_after_merging":
                    len(groups),

                "lane_entry_count":
                    len(entries),

                "matched": matched,
                "matched_percent":
                    round(matched / total * 100, 2),

                "unmatched":
                    method_counts["unmatched"],

                "ambiguous":
                    method_counts["ambiguous"],

                "match_methods": {
                    "exact_arabic":
                        method_counts[
                            "exact_arabic"
                        ],

                    "exact_buckwalter":
                        method_counts[
                            "exact_buckwalter"
                        ],

                    "normalized_radicals":
                        method_counts[
                            "normalized_radicals"
                        ],

                    "geminate_contraction":
                        method_counts[
                            "geminate_contraction"
                        ],

                    "reduplicated_quadriliteral_contraction":
                        method_counts[
                            "reduplicated_quadriliteral_contraction"
                        ],
                },

                "matched_lane_groups_with_both_main_and_supplement":
                    merged_main_supplement_matches,

                "unmatched_with_any_lemma_evidence":
                    unmatched_with_lemma_evidence,

                "unmatched_with_exactly_one_lemma_evidence_candidate":
                    high_confidence_single_lemma_candidate,
            },

            "matching_policy": {
                "automatic_match_rules_in_priority_order": [
                    {
                        "rule": "exact_arabic",
                        "description":
                            "Exact unvocalized Arabic root spelling."
                    },
                    {
                        "rule": "exact_buckwalter",
                        "description":
                            "Exact QAC root code equals a Lane root bword."
                    },
                    {
                        "rule": "normalized_radicals",
                        "description":
                            "Hamza-seat normalization, Lane initial bare-alif "
                            "to hamza-radical normalization, and final "
                            "alif-maqsura/ya normalization."
                    },
                    {
                        "rule": "geminate_contraction",
                        "description":
                            "Only when QAC explicitly has a triliteral "
                            "root with identical radicals 2 and 3; "
                            "compare its contracted two-radical form "
                            "to Lane."
                    },
                    {
                        "rule": "reduplicated_quadriliteral_contraction",
                        "description":
                            "Only for an exact ABAB quadriliteral QAC "
                            "root; compare the contracted AB form to Lane."
                    },
                ],

                "non_automatic_evidence": [
                    {
                        "type": "lemma_evidence_candidates",
                        "description":
                            "QAC lemma forms that also occur as Lane "
                            "lexical entries. Evidence only; never "
                            "silently promoted to a root match."
                    },
                    {
                        "type": "nearest_lane_root_candidates",
                        "description":
                            "Edit-distance suggestions for review only."
                    },
                ],

                "important_principles": [
                    "QAC remains the canonical Quran root inventory.",
                    "Lane main and supplement rows are merged into one lexical root family.",
                    "Original Lane root rows/pages remain preserved.",
                    "No fuzzy match is accepted automatically.",
                    "Initial bare alif in a Lane ROOT key may normalize to the hamza radical.",
                    "Only exact ABAB quadriliterals may use reduplicative contraction.",
                    "No waw/ya interchange is inferred automatically.",
                    "A missing Lane match is allowed; it is not treated as a data error.",
                ],
            },

            # All non-exact matches are convenient to inspect.
            "non_exact_matches_for_review":
                non_exact_review,

            "unmatched_roots":
                unmatched,

            "ambiguous_roots":
                ambiguous,

            # Complete result set for later scripts.
            "results":
                results,
        }

        OUTPUT_FILE.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        print()
        print("=" * 54)
        print("LANE ↔ QAC ROOT MATCH AUDIT V3")
        print("=" * 54)

        print(f"QAC roots:                {total:,}")
        print(
            f"Lane root records:        "
            f"{len(root_records):,}"
        )
        print(
            f"Lane root groups:         "
            f"{len(groups):,}"
        )
        print(
            f"Lane lexical entries:     "
            f"{len(entries):,}"
        )
        print()

        print(f"Matched:                  {matched:,}")
        print(
            f"Coverage:                 "
            f"{matched / total * 100:.2f}%"
        )
        print(
            f"Unmatched:                "
            f"{method_counts['unmatched']:,}"
        )
        print(
            f"Ambiguous:                "
            f"{method_counts['ambiguous']:,}"
        )
        print()

        print("Match methods:")
        print(
            f"  exact Arabic:           "
            f"{method_counts['exact_arabic']:,}"
        )
        print(
            f"  exact Buckwalter:       "
            f"{method_counts['exact_buckwalter']:,}"
        )
        print(
            f"  normalized radicals:    "
            f"{method_counts['normalized_radicals']:,}"
        )
        print(
            f"  geminate contraction:   "
            f"{method_counts['geminate_contraction']:,}"
        )
        print(
            f"  ABAB contraction:       "
            f"{method_counts['reduplicated_quadriliteral_contraction']:,}"
        )
        print()

        print(
            "Matched root families containing BOTH Lane "
            "main + supplement records:"
        )
        print(
            f"  {merged_main_supplement_matches:,}"
        )
        print()

        print("Still-unmatched diagnostic evidence:")
        print(
            f"  with lemma evidence:    "
            f"{unmatched_with_lemma_evidence:,}"
        )
        print(
            f"  exactly one lemma-root candidate: "
            f"{high_confidence_single_lemma_candidate:,}"
        )
        print()

        print(f"Report written to:\n{OUTPUT_FILE}")
        print(
            f"Report size: "
            f"{OUTPUT_FILE.stat().st_size / (1024 * 1024):.2f} MB"
        )
        print()
        print(
            "Upload lane_root_match_audit_v3.json "
            "to ChatGPT for the next review."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
