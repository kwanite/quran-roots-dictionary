#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# Paths / defaults
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

PACKET_CANDIDATES = [
    OUTPUT_DIR / "root_synthesis_packets_pilot_v3.json",
    OUTPUT_DIR / "root_synthesis_packets_sample_v3.json",
    OUTPUT_DIR / "root_synthesis_packets_pilot_v2.json",
    OUTPUT_DIR / "root_synthesis_packets_sample_v2.json",
    OUTPUT_DIR / "root_synthesis_packets_pilot_v1.json",
    OUTPUT_DIR / "root_synthesis_packets_sample_v1.json",
]

DEFAULT_MODEL = "gpt-5.6-luna"
PROMPT_VERSION = 10
DEFAULT_REASONING = "high"
DEFAULT_MAX_OUTPUT_TOKENS = 80_000
DEFAULT_TIMEOUT = 300.0

VALIDATION_LOG_FILE = OUTPUT_DIR / "root_dictionary_validation_findings_v1.jsonl"

# Current GPT-5.6 Luna text-token prices as of 2026-08-23.
# Only used for an estimate when the selected model is exactly gpt-5.6-luna.
LUNA_INPUT_USD_PER_MILLION = 0.20
LUNA_OUTPUT_USD_PER_MILLION = 1.20


# ============================================================
# Final artifact schema
# ============================================================

class RootIdea(BaseModel):
    summary: str
    development: str = ""
    source_refs: list[str] = Field(default_factory=list)


class FormAccounting(BaseModel):
    form_group_id: str
    disposition: Literal[
        "DISPLAY",
        "MERGE",
        "EXCLUDE_WITH_REASON",
    ]
    target_public_form_id: Optional[str] = None
    reason: str = ""


class DictionarySense(BaseModel):
    sense_id: str
    definition: str
    usage_conditions: str = ""
    source_refs: list[str] = Field(default_factory=list)


class QuranExample(BaseModel):
    verse_key: str
    word_location: str
    context_gloss: str = ""
    sense_ids: list[str] = Field(default_factory=list)


class QuranicForm(BaseModel):
    public_form_id: str
    form_group_ids: list[str]
    headword_arabic: str
    public_pos_label: str
    verb_form: Optional[str] = None
    occurrence_count: int
    senses: list[DictionarySense] = Field(default_factory=list)
    quran_examples: list[QuranExample] = Field(default_factory=list)


class ClassicalMeaning(BaseModel):
    meaning_id: str
    headword_arabic: str
    definition: str
    usage_conditions: str = ""
    source_refs: list[str] = Field(default_factory=list)


class LaneUnitCoverage(BaseModel):
    unit_id: str
    status: Literal[
        "REPRESENTED",
        "SUBSUMED",
        "NON_SEMANTIC",
        "AMBIGUOUS",
    ]
    target_ids: list[str] = Field(default_factory=list)
    note: str = ""


class RootDictionaryArtifact(BaseModel):
    root: str
    arabic: str
    root_idea: RootIdea
    qac_form_accounting: list[FormAccounting]
    quranic_forms: list[QuranicForm]
    other_classical_meanings: list[ClassicalMeaning] = Field(
        default_factory=list
    )
    lane_unit_coverage: list[LaneUnitCoverage] = Field(
        default_factory=list
    )
    cautions: list[str] = Field(default_factory=list)
    unassigned_or_ambiguous_evidence: list[str] = Field(
        default_factory=list
    )


# ============================================================
# Prompt
# ============================================================

SYSTEM_PROMPT = r"""
You are producing one final public-facing Quran-root dictionary artifact
from a deterministic evidence packet.

Your job is NOT merely to summarize the evidence. Your job is to review the
supplied evidence systematically, preserve its materially distinct lexical
content, and decide how that content should appear in a clear dictionary.

Use the following decision rules. They are coverage rules, not instructions
to multiply trivial distinctions.

1. QURANIC FORM AND SENSE COVERAGE

For every supplied QAC form group, determine the correct public headword and
the Quranic lexical senses actually supported by the evidence.

For each form, review ALL supplied Mufradat evidence for explicit explanations
of Quranic usages, constructions, or cited verses. Also inspect every Lane
primary source_unit whose flags or text indicate a Quran citation or Quranic
expression. Quran Foundation contextual gloss patterns are supporting
context only.

A Lane Quran citation does not automatically require a new sense when it is
merely an example of an already-covered meaning. But when Lane explicitly
uses a Quran passage to attest a materially distinct lexical meaning or
construction, that meaning is Quran-attested evidence and must not be placed
only under other_classical_meanings.

Lane's printed Quran references use historical citation conventions and may
contain Roman numerals. A transcription such as "[1. 18]" may therefore be
an OCR/transcription of a Roman-numeral reference such as "[l. 18]", not the
modern location "1:18". NEVER convert a Lane bracketed citation directly into
a modern surah:ayah location merely because it resembles digits.

When Lane quotes an Arabic Quran expression:
- treat the quoted expression as genuine Quran-focused lexical evidence;
- use a modern verse_key/word_location only if that location is independently
  supplied by QAC in this packet and the identification is secure;
- otherwise preserve the reported Quranic interpretation without claiming
  that Lane cited a nonexistent or mismatching modern verse location.

Every materially distinct Quran-specific usage explicitly explained by
Mufradat or explicitly attested as such by Lane must be handled in one of two
ways:
- represent it as a distinct numbered sense; OR
- subsume it under a broader numbered sense whose definition and
  usage_conditions genuinely cover that usage.

Do not silently omit such a usage merely because a contextual English gloss
looks similar to a more ordinary sense.

Example of the principle: if a source explicitly explains a form literally
associated with "writing" as meaning "to include, enroll, or place among a
group" in a particular Quranic construction, that semantic use must be
represented or explicitly covered by a broader sense.

Quran Foundation English alone must never create a dictionary sense. A
contextual gloss such as "yielded", "destroyed", "approached", or "gave" may
illustrate a lexical sense only after Lane and/or Mufradat independently
supports that meaning or construction. Do not invent a new sense and then
attach an unrelated Lane source_ref merely to satisfy the schema.

2. WHEN TO SPLIT OR MERGE SENSES

Create separate senses when the evidence supports a materially different
lexical meaning, relation, action, result, or conventional construction that a
reader would need in order to understand why Quran translations differ.

Merge differences that are merely grammatical, inflectional, voice-related,
stylistic, intensifying, or context-specific paraphrases of the same lexical
meaning. Put important constructional restrictions or nuances in
usage_conditions rather than creating unnecessary senses.

Do not turn every English gloss variation into a separate sense.

Do not mistake an illustrative source example for a universal semantic
restriction.

A restriction in definition or usage_conditions on the object's gender,
animacy, class, number, social status, or other semantic category is allowed
ONLY when the lexical evidence explicitly states that restriction.

If a source merely illustrates a meaning with "a woman", "a man", "a camel",
"a thing", or another particular object, do not convert that example into a
general restriction. This is especially important when the same source
explicitly applies the lexical use to a Quran passage whose object differs
from the illustration.

When the evidence supports the construction but not an object-class
restriction, describe the construction neutrally (for example, "to approach
sexually / have sexual intercourse") rather than repeating the accidental
properties of the source's example.

A Quranic sense definition and its usage_conditions must describe the
Quran-attested lexical use or construction. Do not place a broader
Classical-only meaning inside a Quranic sense merely because it belongs to
the same headword. Put such material under other_classical_meanings instead.

3. BROADER CLASSICAL COVERAGE

Review EVERY Lane primary source_unit supplied for the root before writing
the answer. The source_units are deterministic reading boundaries extracted
from Lane's own numbered/subnumbered structure; they are NOT pre-decided
dictionary senses.

For each source_unit, ask whether it states a materially independent lexical
meaning or conventional lexical construction.

If yes, that semantic content must be represented somewhere in the artifact:
either under a Quran-attested form when genuinely Quranic, or under
other_classical_meanings when it is broader Classical Arabic. It may be
omitted only when its meaning is genuinely the same semantic branch already
represented elsewhere.

Do NOT create a bookkeeping table or one output sense per source_unit.
Pointer-only, grammatical, pronunciation, orthographic, etymological,
example-only, and editorial units need not become meanings. Closely related
units may be synthesized into one clear dictionary meaning.

Before placing a meaning under other_classical_meanings, check whether the
supporting Lane passage explicitly identifies that lexical meaning or
construction with a Quran verse. If it does and the corresponding QAC form is
present, classify it under the Quranic form instead (or genuinely subsume it
under an existing Quranic sense). Do not label a Quran-attested lexical use
as "Beyond the Quran."

Under other_classical_meanings, include every materially distinct,
independently attested Classical Arabic lexical branch that is not already
being claimed as a Quran-attested sense.

Rare, archaic, technical, anatomical, idiomatic, or figurative meanings may
belong here when they are genuine independent lexical usages. Do not omit a
meaning merely because it is unusual.

At the same time, do not create separate meanings from:
- grammatical or inflectional information;
- pronunciation, orthographic, dialect, or etymological notes;
- illustrative examples that add no new lexical meaning;
- source commentary or scholarly disagreement by itself;
- a pointer-only cross-reference;
- a synonymic restatement or very narrow subcase already fully covered by a
  broader meaning.

Closely related Classical sub-senses may be grouped into one clear entry when
they belong to the same semantic branch. There is no target number of
classical meanings: include as many as the evidence materially requires, and
no more.

When grouping Classical evidence, preserve lexical identity. Do not map a
meaning stated for one headword or derived form to a different headword or
form merely because the ideas are related. A true synonym or explicit
cross-reference may justify grouping; loose semantic resemblance does not.

Lane source_unit flags such as mentions_quran or
mentions_primary_signification are navigation aids, not conclusions. Read the
unit text itself before deciding what the evidence means.

Lane cross-reference context is interpretive context only. Do not treat a
supplemental context entry as direct evidence that its meaning belongs to this
QAC root unless direct evidence independently supports that assignment.

4. ROOT IDEA VERSUS DIRECT WORD MEANINGS

Use Maqayis and relevant Mufradat discussion to explain the root's semantic
orientation or historical development in root_idea.

A root principle or semantic development is not automatically a direct
Quranic word meaning. Assign it to a Quran form only when Lane and/or Mufradat
independently support that form-level meaning.

Likewise, do not place a general root-development explanation under
other_classical_meanings unless the lexical sources actually attest it as an
independent usage.

5. EVIDENCE AND TRACEABILITY

QAC is authoritative for Quran form identity, morphology, occurrence counts,
and Quran locations.

Every numbered Quran-form sense must cite at least one direct lexical
source_ref from Lane primary evidence and/or unique Mufradat evidence.

Maqayis may support root_idea but is insufficient by itself to establish a
direct Quran-form sense.

Every other_classical_meanings item must have a stable compact meaning_id
with no whitespace and must be supported by genuine lexical evidence,
normally Lane primary evidence.

A source_ref on a Quranic sense or Classical meaning must actually support
that definition or usage. Do not cite a Lane entry merely because its
headword resembles the public form or because it belongs to the same root.

Use only source_ref strings explicitly present on supplied Lane, Maqayis, or
Mufradat evidence objects. Never invent a source_ref.

If materially relevant evidence cannot be assigned confidently, preserve the
issue concisely in unassigned_or_ambiguous_evidence rather than silently
dropping it.

6. PUBLIC FORM ACCOUNTING

Every supplied QAC form_group_id must appear exactly once in
qac_form_accounting.

Every generated public_form_id and sense_id must be a compact stable
machine identifier with no whitespace.

Use:
- DISPLAY when the group should appear as its own public form. For DISPLAY,
  target_public_form_id is REQUIRED and must exactly equal the
  public_form_id of the quranic_forms item that contains this form_group_id.
- MERGE when it belongs under another public dictionary headword.
  target_public_form_id is REQUIRED and must name that public form.
- EXCLUDE_WITH_REASON only when the QAC grouping should intentionally not
  appear as a public lexical form. Give a clear reason and leave
  target_public_form_id empty.

Normalize the Arabic public headword when needed. Do not blindly use a QAC
lemma display candidate when it is an inflected Quran form rather than the
best dictionary citation form.

For derived verbs, use the normal Classical Arabic dictionary citation form
(typically the third-person masculine singular perfect), not an imperative
or other inflected source form. Preserve the correct hamza, vowel pattern,
and derived-form shape. If the supplied source headword is undiacritized or
inflected, normalize it from the identified verb form rather than copying it
mechanically.

For nominal form groups, use the supplied derived_nominal_counts when present.
Normalize an inflected Quran lemma to a useful dictionary citation form when
the evidence supports it: for example, a Quran-only plural active participle
should normally be presented under its singular participial citation form,
unless the lexical item is genuinely plural-only or collective. Do not invent
a singular when the evidence does not support one.

Use informative public_pos_label values:
- verbs: "Verb · Form I", "Verb · Form IV", etc.;
- pure VERBAL_NOUN groups: "Verbal noun";
- pure ACTIVE_PARTICIPLE groups: "Active participle" (or a similarly precise
  public label when substantivized);
- pure PASSIVE_PARTICIPLE groups: "Passive participle";
- ordinary nominals: "Noun", "Adjective", or another accurate public label.
Do not reduce a form known to be a participle or verbal noun to the generic
label "Noun" unless there is a real lexical reason to do so.

7. INTERNAL LANE UNIT COVERAGE LEDGER

lane_unit_coverage is INTERNAL AUDIT METADATA, not public dictionary content.
Its only purpose is to prevent silent loss of Lane meanings while keeping the
pipeline to one synthesis call.

Include exactly one lane_unit_coverage row for every supplied Lane PRIMARY
source_unit and no rows for cross-reference-context entries.

For each unit choose one status:
- REPRESENTED: its material lexical content appears directly in one or more
  Quranic senses and/or other_classical_meanings items.
- SUBSUMED: it adds no separate public item because its lexical content is
  genuinely covered by a broader represented item.
- NON_SEMANTIC: it is only grammatical, pronunciation/orthographic,
  etymological/editorial, pointer-only, or an example that adds no lexical
  meaning.
- AMBIGUOUS: it appears materially lexical but cannot be assigned confidently.

For REPRESENTED or SUBSUMED, target_ids must contain the relevant sense_id
and/or Classical meaning_id. Multiple targets are allowed when one Lane unit
contains more than one material branch.

When a single source_unit contains several materially distinct lexical
branches and more than one of those branches is represented in the artifact,
target_ids must list ALL of those represented targets. Do not omit a target
merely because another branch from the same unit has already been accounted
for.

REPRESENTED or SUBSUMED is valid only when the target definition or
usage_conditions actually states the material lexical content of the Lane
unit. A target is NOT valid merely because it is etymologically related,
belongs to the same root, or expresses a neighboring idea. If the unit says
"a stranger", "an angel", "an energetic man", "to claim kinship", or another
distinct lexical use, that content must be explicitly visible in the target.

A Classical-only specialization of a Quran-attested headword must remain
under other_classical_meanings unless the evidence establishes that
specialization in Quranic usage. Do not swallow a Classical-only meaning into
a broader Quranic sense.

For NON_SEMANTIC or AMBIGUOUS, target_ids must be empty and note must briefly
state why. An AMBIGUOUS material issue must also be preserved in
unassigned_or_ambiguous_evidence.

Do not classify a unit as NON_SEMANTIC merely because its lexical statement
is rare, tentative, bracketed, attributed to one authority, or reported with
phrases such as "app.", "some say", "means", or "signifies". If it states a
lexical meaning, preserve it as a Classical meaning, genuinely subsume it
under an explicit target, or mark it AMBIGUOUS. NON_SEMANTIC is only for
material that contributes no lexical meaning.

Use every supplied unit_id EXACTLY as written in the packet. Never derive,
renumber, or reconstruct a unit_id from lane_marker or sub_number.

This ledger must be concise. Do not restate Lane prose in it and do not create
a separate public sense merely to satisfy the ledger.

8. QURAN EXAMPLES

Choose examples for semantic usefulness: they should demonstrate distinct
senses or constructions rather than merely being the first occurrences.

Prefer representative Quran Foundation occurrences supplied in the packet.

If an especially important Quran verse is explicitly discussed in Mufradat
and its word_location is a valid QAC occurrence for the form, you may use it
even if that location was not included among the compact QF representatives.
In that case, do not invent a Quran Foundation gloss: leave context_gloss as
an empty string unless the exact gloss for that location is supplied.

Each example's sense_ids must refer to senses on that same public form.

9. PUBLIC WRITING STYLE

Definitions should be concise, readable, source-neutral dictionary prose.
Do not mention source names inside definitions; provenance belongs in
source_refs.

Keep Quran-attested meanings clearly separate from broader Classical Arabic
meanings.

Use cautions only for real ambiguity, grammatical restrictions, source
limitations, or genuine disagreement. Do not write generic warnings.

BEFORE RETURNING THE ARTIFACT, SILENTLY CHECK:

- every QAC form group is accounted for exactly once;
- every explicit Mufradat explanation of a materially distinct Quran usage is
  represented or genuinely subsumed under a listed sense;
- every materially distinct Lane meaning explicitly tied by Lane to a Quran
  verse is represented/subsumed under the Quranic form, not only under
  other_classical_meanings;
- every Lane PRIMARY source_unit appears exactly once in lane_unit_coverage;
- every materially lexical Lane source_unit is represented, genuinely
  subsumed, or explicitly marked ambiguous; none is silently dropped;
- every REPRESENTED/SUBSUMED ledger target_id exists in the artifact and
  explicitly covers the unit's lexical content, not merely a related idea;
- when one Lane source_unit produced several represented meanings, its
  target_ids include every represented meaning derived from that unit;
- legacy Lane Quran citation notation has not been misread as a modern
  surah:ayah number;
- no lexical unit was labeled NON_SEMANTIC merely because its attestation is
  rare, tentative, attributed, or bracketed;
- Classical-only specializations have not been swallowed into Quranic senses;
- no source example's gender, class, number, animacy, or social status has
  been turned into a semantic restriction unless the lexical evidence
  explicitly requires that restriction;
- every Lane source_ref attached to a sense/meaning genuinely supports that
  sense/meaning;
- non-semantic units have not been turned into fake senses;
- no broader Classical-only meaning has leaked into the definition or
  usage_conditions of a Quranic sense;
- derived-verb and inflected nominal public headwords use appropriate
  dictionary citation forms;
- public_pos_label reflects supplied derived morphology when available;
- no generated public_form_id or sense_id contains whitespace;
- no Quran sense was created from Quran Foundation English alone;
- no direct Quran sense was created from Maqayis root principle alone;
- no materially distinct evidence was silently discarded merely to keep the
  entry short.

Return only the structured artifact required by the schema.
""".strip()


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


def model_dump(
    value: Any,
) -> dict:
    if hasattr(
        value,
        "model_dump",
    ):
        return value.model_dump()

    if hasattr(
        value,
        "dict",
    ):
        return value.dict()

    raise TypeError(
        f"Cannot serialize {type(value)!r}"
    )


def locate_packet_file(
    explicit: Optional[Path],
) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(
                explicit
            )
        return explicit

    for candidate in PACKET_CANDIDATES:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No synthesis packet file found. Expected one of:\n"
        + "\n".join(
            str(path)
            for path in PACKET_CANDIDATES
        )
    )


def packet_lookup(
    payload: dict,
) -> dict[str, dict]:
    output = {}

    for packet in payload.get(
        "packets",
        [],
    ):
        root = packet.get(
            "root"
        )

        if not root:
            raise RuntimeError(
                "Packet missing root."
            )

        if root in output:
            raise RuntimeError(
                f"Duplicate packet root: {root}"
            )

        output[
            root
        ] = packet

    return output


def compact_chars(
    value: Any,
) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def rough_input_tokens(
    packet: dict,
) -> int:
    # Planning heuristic only; actual API tokenization is recorded afterward.
    return max(
        1,
        round(
            compact_chars(
                packet
            )
            / 3
        ),
    )


def estimated_luna_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Optional[float]:
    if model != "gpt-5.6-luna":
        return None

    return (
        input_tokens
        / 1_000_000
        * LUNA_INPUT_USD_PER_MILLION
        + output_tokens
        / 1_000_000
        * LUNA_OUTPUT_USD_PER_MILLION
    )


def usage_to_dict(
    response: Any,
) -> dict:
    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        return {}

    if hasattr(
        usage,
        "model_dump",
    ):
        return usage.model_dump()

    if hasattr(
        usage,
        "dict",
    ):
        return usage.dict()

    output = {}

    for key in [
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]:
        value = getattr(
            usage,
            key,
            None,
        )

        if value is not None:
            output[
                key
            ] = value

    details = getattr(
        usage,
        "output_tokens_details",
        None,
    )

    if details is not None:
        if hasattr(
            details,
            "model_dump",
        ):
            output[
                "output_tokens_details"
            ] = details.model_dump()

        elif hasattr(
            details,
            "dict",
        ):
            output[
                "output_tokens_details"
            ] = details.dict()

    return output


def collect_evidence_refs(
    packet: dict,
) -> dict[str, set[str]]:
    evidence = packet[
        "evidence"
    ]

    lane = evidence.get(
        "lane"
    ) or {}

    lane_primary = {
        entry.get(
            "source_ref"
        )
        for entry
        in (
            lane.get(
                "primary",
                {}
            ).get(
                "entries",
                []
            )
        )
        if entry.get(
            "source_ref"
        )
    }

    lane_context = set()

    for item in (
        lane.get(
            "cross_reference_context",
            {}
        ).get(
            "entries",
            []
        )
    ):
        entry = (
            item.get(
                "entry"
            )
            if isinstance(
                item,
                dict,
            )
            else None
        )

        if isinstance(
            entry,
            dict,
        ):
            ref = entry.get(
                "source_ref"
            )

            if ref:
                lane_context.add(
                    ref
                )

    maqayis = {
        entry.get(
            "source_ref"
        )
        for entry
        in (
            evidence.get(
                "maqayis",
                {}
            ).get(
                "entries",
                []
            )
        )
        if entry.get(
            "source_ref"
        )
    }

    muf = evidence.get(
        "mufradat"
    ) or {}

    muf_unique = {
        entry.get(
            "source_ref"
        )
        for entry
        in muf.get(
            "unique_entries",
            []
        )
        if entry.get(
            "source_ref"
        )
    }

    muf_shared = {
        entry.get(
            "source_ref"
        )
        for entry
        in muf.get(
            "shared_ambiguous_entries",
            []
        )
        if entry.get(
            "source_ref"
        )
    }

    all_refs = (
        lane_primary
        | lane_context
        | maqayis
        | muf_unique
        | muf_shared
    )

    direct_lexical = (
        lane_primary
        | muf_unique
    )

    return {
        "lane_primary":
            lane_primary,

        "lane_context":
            lane_context,

        "maqayis":
            maqayis,

        "mufradat_unique":
            muf_unique,

        "mufradat_shared":
            muf_shared,

        "all":
            all_refs,

        "direct_lexical":
            direct_lexical,
    }


def collect_qf_examples(
    packet: dict,
) -> dict[str, dict]:
    examples = {}

    qf = (
        packet[
            "evidence"
        ].get(
            "quran_contextual_english"
        )
        or {}
    )

    for lemma in qf.get(
        "lemmas",
        []
    ):
        for gloss in lemma.get(
            "gloss_evidence",
            []
        ):
            for occurrence in gloss.get(
                "example_occurrences",
                []
            ):
                word_location = occurrence.get(
                    "word_location"
                )

                if not word_location:
                    continue

                quran_word = (
                    occurrence.get(
                        "quran_word"
                    )
                    or {}
                )

                examples[
                    word_location
                ] = {
                    "verse_key":
                        occurrence.get(
                            "verse_key"
                        ),

                    "context_gloss":
                        quran_word.get(
                            "translation_en"
                        )
                        or "",
                }

    return examples


def _strip_machine_id_noise(
    value: Any,
) -> Any:
    """
    Remove only characters that are never meaningful in these generated
    machine identifiers: Unicode whitespace and invisible control/format
    characters.

    Deliberately do NOT transliterate letters, repair spelling, or remove
    ordinary punctuation here. This helper is used to make malformed IDs
    compact without guessing what a lexical label was intended to mean.
    """
    if not isinstance(
        value,
        str,
    ):
        return value

    return "".join(
        ch
        for ch in value
        if (
            not ch.isspace()
            and unicodedata.category(ch)
            not in {
                "Cc",
                "Cf",
            }
        )
    )


def _machine_id_fingerprint(
    value: Any,
) -> Optional[str]:
    """
    Conservative comparison fingerprint for already-generated machine IDs.

    This is NOT fuzzy matching. It only ignores:
    - Unicode compatibility/case differences;
    - whitespace and invisible control/format characters;
    - common machine-ID separators: -, _, :, ., /

    It intentionally preserves letters, digits, root symbols, quotation
    marks, and other substantive characters. A repair is allowed only when
    this fingerprint resolves to exactly one existing valid ID.
    """
    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = unicodedata.normalize(
        "NFKC",
        value,
    ).casefold()

    output = []

    for ch in normalized:
        if (
            ch.isspace()
            or unicodedata.category(ch)
            in {
                "Cc",
                "Cf",
            }
        ):
            continue

        if ch in {
            "-",
            "_",
            ":",
            ".",
            "/",
        }:
            continue

        output.append(
            ch
        )

    fingerprint = "".join(
        output
    )

    return (
        fingerprint
        if fingerprint
        else None
    )



def _contains_non_ascii_machine_chars(
    value: Any,
) -> bool:
    """
    Return True only when an ID contains at least one visible non-ASCII
    character.

    This is used solely to detect obvious script-corruption inside generated
    machine IDs. ASCII-only spelling drift is deliberately excluded.
    """
    if not isinstance(
        value,
        str,
    ):
        return False

    return any(
        ord(
            ch
        ) > 127
        and not ch.isspace()
        and unicodedata.category(
            ch
        )
        not in {
            "Cc",
            "Cf",
        }
        for ch in value
    )


def _ascii_machine_id_skeleton(
    value: Any,
) -> Optional[str]:
    """
    Conservative skeleton for detecting mixed-script corruption.

    Preserve every visible ASCII character, including separators, digits,
    punctuation, root symbols, and suffix text. Remove only non-ASCII
    characters plus whitespace/control/format noise.

    A repair may use this skeleton only when BOTH the malformed ID and the
    candidate valid ID contain non-ASCII characters and the skeleton resolves
    uniquely. This is not transliteration and is not fuzzy matching.
    """
    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = unicodedata.normalize(
        "NFKC",
        value,
    ).casefold()

    output = []

    for ch in normalized:
        if (
            ch.isspace()
            or unicodedata.category(
                ch
            )
            in {
                "Cc",
                "Cf",
            }
        ):
            continue

        if ord(
            ch
        ) < 128:
            output.append(
                ch
            )

    skeleton = "".join(
        output
    )

    return (
        skeleton
        if skeleton
        else None
    )


def _build_unique_nonascii_skeleton_index(
    values: list[Any],
) -> dict[str, str]:
    """
    Build ASCII-skeleton -> original-ID mappings only for valid IDs that
    themselves contain visible non-ASCII characters, and only when the
    skeleton is unique among the supplied values.
    """
    buckets: dict[str, set[str]] = {}

    for value in values:
        if not (
            isinstance(
                value,
                str,
            )
            and value
            and _contains_non_ascii_machine_chars(
                value
            )
        ):
            continue

        skeleton = _ascii_machine_id_skeleton(
            value
        )

        if not skeleton:
            continue

        buckets.setdefault(
            skeleton,
            set(),
        ).add(
            value
        )

    return {
        skeleton:
            next(
                iter(
                    originals
                )
            )
        for skeleton, originals in buckets.items()
        if len(
            originals
        ) == 1
    }


def _plan_collision_free_compact_renames(
    values: list[Any],
) -> dict[str, str]:
    """
    Plan compact-ID renames that are provably collision-free.

    Only whitespace/control/format removal is used for the actual rename.
    If two different original IDs would collapse to the same result, or the
    result already belongs to another existing ID, neither ambiguous rename
    is performed.
    """
    string_values = [
        value
        for value in values
        if isinstance(
            value,
            str,
        )
        and value
    ]

    existing = set(
        string_values
    )

    proposed: dict[str, str] = {}
    destination_sources: dict[str, set[str]] = {}

    for old in set(
        string_values
    ):
        new = _strip_machine_id_noise(
            old
        )

        if (
            not isinstance(
                new,
                str,
            )
            or not new
            or new == old
        ):
            continue

        proposed[
            old
        ] = new

        destination_sources.setdefault(
            new,
            set(),
        ).add(
            old
        )

    safe = {}

    for old, new in proposed.items():
        # Do not merge two distinct existing identifiers.
        if (
            new in existing
            and new != old
        ):
            continue

        # Do not let two malformed IDs collapse onto the same new ID.
        if len(
            destination_sources.get(
                new,
                set(),
            )
        ) != 1:
            continue

        safe[
            old
        ] = new

    return safe


def _build_unique_fingerprint_index(
    values: list[str],
) -> dict[str, str]:
    """
    Map a machine-ID fingerprint to an existing ID only when that fingerprint
    identifies exactly one existing ID.
    """
    buckets: dict[str, set[str]] = {}

    for value in values:
        if not isinstance(
            value,
            str,
        ):
            continue

        fingerprint = _machine_id_fingerprint(
            value
        )

        if not fingerprint:
            continue

        buckets.setdefault(
            fingerprint,
            set(),
        ).add(
            value
        )

    return {
        fingerprint:
            next(
                iter(
                    candidates
                )
            )
        for fingerprint, candidates in buckets.items()
        if len(
            candidates
        ) == 1
    }


def _apply_id_rename(
    value: Any,
    rename_map: dict[str, str],
) -> Any:
    if (
        isinstance(
            value,
            str,
        )
        and value in rename_map
    ):
        return rename_map[
            value
        ]

    return value


def apply_deterministic_bookkeeping_repairs(
    artifact: dict,
    *,
    packet: Optional[dict] = None,
) -> list[dict]:
    """
    Repair only mechanically inferable bookkeeping inconsistencies.

    Safety policy:
    - Never alter lexical definitions, usage conditions, headwords, semantic
      classifications, or Lane statuses. Source refs may be corrected only by
      an explicitly evidence-proven, owner-scoped deterministic correction
      whose replacement exists in the supplied packet and whose Lane headword
      exactly matches the affected public form.
    - Never use edit distance, prefix matching, substring matching, semantic
      similarity, or any other fuzzy heuristic.
    - Rename malformed generated IDs only by removing whitespace/invisible
      control characters, and only when the rename is collision-free.
    - Propagate those exact renames through internal references.
    - Resolve an invalid reference by a machine-ID fingerprint only when it
      matches exactly one already-existing valid ID.
    - If lane_unit_coverage incorrectly targets a public_form_id, replace it
      with that form's sense_id only when the public form has exactly one
      sense.
    - Keep every ambiguous or non-mechanical case untouched so the validator
      continues to reject it for later review.

    The function returns warning findings describing every deterministic
    repair family that was applied.
    """
    repairs = []

    quranic_forms = (
        artifact.get(
            "quranic_forms"
        )
        or []
    )

    classical_meanings = (
        artifact.get(
            "other_classical_meanings"
        )
        or []
    )

    accounting = (
        artifact.get(
            "qac_form_accounting"
        )
        or []
    )

    coverage_rows = (
        artifact.get(
            "lane_unit_coverage"
        )
        or []
    )

    # --------------------------------------------------------
    # 1. Canonicalize malformed generated IDs conservatively.
    # --------------------------------------------------------

    public_id_values = [
        form.get(
            "public_form_id"
        )
        for form in quranic_forms
    ]

    sense_id_values = [
        sense.get(
            "sense_id"
        )
        for form in quranic_forms
        for sense in (
            form.get(
                "senses"
            )
            or []
        )
    ]

    classical_id_values = [
        meaning.get(
            "meaning_id"
        )
        for meaning in classical_meanings
    ]

    public_id_renames = (
        _plan_collision_free_compact_renames(
            public_id_values
        )
    )

    # sense_id and Classical meaning_id share the Lane target namespace.
    # Plan their compact renames together so a repair cannot create a
    # cross-namespace target collision.
    target_id_renames = (
        _plan_collision_free_compact_renames(
            sense_id_values
            + classical_id_values
        )
    )

    sense_id_set = {
        value
        for value in sense_id_values
        if isinstance(
            value,
            str,
        )
    }

    classical_id_set = {
        value
        for value in classical_id_values
        if isinstance(
            value,
            str,
        )
    }

    sense_id_renames = {
        old:
            new
        for old, new in target_id_renames.items()
        if old in sense_id_set
    }

    classical_id_renames = {
        old:
            new
        for old, new in target_id_renames.items()
        if old in classical_id_set
    }

    id_rename_details = []

    for form in quranic_forms:
        old_public_id = form.get(
            "public_form_id"
        )

        new_public_id = _apply_id_rename(
            old_public_id,
            public_id_renames,
        )

        if new_public_id != old_public_id:
            form[
                "public_form_id"
            ] = new_public_id

            id_rename_details.append(
                {
                    "namespace":
                        "public_form_id",

                    "old":
                        old_public_id,

                    "new":
                        new_public_id,
                }
            )

        for sense in (
            form.get(
                "senses"
            )
            or []
        ):
            old_sense_id = sense.get(
                "sense_id"
            )

            new_sense_id = _apply_id_rename(
                old_sense_id,
                sense_id_renames,
            )

            if new_sense_id != old_sense_id:
                sense[
                    "sense_id"
                ] = new_sense_id

                id_rename_details.append(
                    {
                        "namespace":
                            "sense_id",

                        "old":
                            old_sense_id,

                        "new":
                            new_sense_id,
                    }
                )

    for meaning in classical_meanings:
        old_meaning_id = meaning.get(
            "meaning_id"
        )

        new_meaning_id = _apply_id_rename(
            old_meaning_id,
            classical_id_renames,
        )

        if new_meaning_id != old_meaning_id:
            meaning[
                "meaning_id"
            ] = new_meaning_id

            id_rename_details.append(
                {
                    "namespace":
                        "meaning_id",

                    "old":
                        old_meaning_id,

                    "new":
                        new_meaning_id,
                }
            )

    # Propagate exact public-form ID renames into QAC accounting.
    for row in accounting:
        target = row.get(
            "target_public_form_id"
        )

        replacement = _apply_id_rename(
            target,
            public_id_renames,
        )

        if replacement != target:
            row[
                "target_public_form_id"
            ] = replacement

    # Propagate exact sense-ID renames into Quran example references.
    for form in quranic_forms:
        for example in (
            form.get(
                "quran_examples"
            )
            or []
        ):
            example[
                "sense_ids"
            ] = [
                _apply_id_rename(
                    sense_id,
                    sense_id_renames,
                )
                for sense_id in (
                    example.get(
                        "sense_ids"
                    )
                    or []
                )
            ]

    # Propagate exact target/public-ID renames into Lane ledger references.
    # A public ID is not itself a valid final Lane target, but preserving its
    # exact rename lets the sole-sense repair below recognize it safely.
    for row in coverage_rows:
        repaired_targets = []

        for target in (
            row.get(
                "target_ids"
            )
            or []
        ):
            target = _apply_id_rename(
                target,
                target_id_renames,
            )

            target = _apply_id_rename(
                target,
                public_id_renames,
            )

            repaired_targets.append(
                target
            )

        row[
            "target_ids"
        ] = repaired_targets

    if id_rename_details:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "MACHINE_IDS_CANONICALIZED",

                "message":
                    (
                        "Deterministically removed whitespace/invisible "
                        "control characters from "
                        f"{len(id_rename_details)} generated machine ID(s) "
                        "and propagated the exact rename through internal "
                        "references."
                    ),

                "details":
                    id_rename_details,
            }
        )

    # --------------------------------------------------------
    # 2. Repair generated-ID collisions only when existing provenance
    #    partitions every reference unambiguously.
    #
    # A. Duplicate Classical meaning_id values:
    #    - every colliding object must have exactly one distinct Lane entry;
    #    - every lane_unit_coverage reference to the collided ID must belong
    #      to exactly one of those Lane entries by unit_id;
    #    - every colliding object must be represented by at least one such
    #      ledger row.
    #    If so, every object receives:
    #        <old_id>__lane_<entry_number>
    #    and only the matching Lane ledger rows are retargeted.
    #
    # B. Duplicate public_form_id values:
    #    - every colliding public form must have non-empty, mutually disjoint
    #      QAC form_group_ids;
    #    - every accounting row targeting the collided ID must map by its
    #      form_group_id to exactly one colliding public form;
    #    - every colliding form must own at least one such accounting row;
    #    - the collided public_form_id must not occur as a Lane target,
    #      because such a reference could not be partitioned by QAC group.
    #    If so, every public form receives a deterministic ID derived from
    #    its QAC group set and its accounting references are retargeted.
    #
    # Anything ambiguous remains untouched.
    # --------------------------------------------------------

    # ---- 2A. Classical meaning_id collisions resolved by Lane provenance.
    classical_rows_by_id: dict[str, list[tuple[int, dict]]] = {}

    for index, meaning in enumerate(
        classical_meanings
    ):
        meaning_id = meaning.get(
            "meaning_id"
        )

        if (
            isinstance(
                meaning_id,
                str,
            )
            and meaning_id
        ):
            classical_rows_by_id.setdefault(
                meaning_id,
                [],
            ).append(
                (
                    index,
                    meaning,
                )
            )

    existing_classical_ids = {
        meaning.get(
            "meaning_id"
        )
        for meaning in classical_meanings
        if isinstance(
            meaning.get(
                "meaning_id"
            ),
            str,
        )
    }

    classical_collision_repairs = []

    for collided_id, rows in classical_rows_by_id.items():
        if len(
            rows
        ) <= 1:
            continue

        entry_to_object: dict[str, dict] = {}
        object_entries: dict[int, str] = {}
        safe_collision = True

        for index, meaning in rows:
            lane_entry_numbers = []

            for source_ref in (
                meaning.get(
                    "source_refs"
                )
                or []
            ):
                if not (
                    isinstance(
                        source_ref,
                        str,
                    )
                    and source_ref.startswith(
                        "lane:entry:"
                    )
                ):
                    continue

                entry_number = source_ref.split(
                    ":"
                )[
                    -1
                ]

                if entry_number:
                    lane_entry_numbers.append(
                        entry_number
                    )

            lane_entry_numbers = list(
                dict.fromkeys(
                    lane_entry_numbers
                )
            )

            if len(
                lane_entry_numbers
            ) != 1:
                safe_collision = False
                break

            entry_number = lane_entry_numbers[
                0
            ]

            if entry_number in entry_to_object:
                safe_collision = False
                break

            entry_to_object[
                entry_number
            ] = {
                "index":
                    index,

                "meaning":
                    meaning,
            }

            object_entries[
                index
            ] = entry_number

        if not safe_collision:
            continue

        coverage_matches: list[tuple[dict, str]] = []
        matched_object_indexes: set[int] = set()

        for coverage in coverage_rows:
            targets = (
                coverage.get(
                    "target_ids"
                )
                or []
            )

            if collided_id not in targets:
                continue

            unit_id = coverage.get(
                "unit_id"
            )

            matching_entries = [
                entry_number
                for entry_number in entry_to_object
                if (
                    isinstance(
                        unit_id,
                        str,
                    )
                    and f":{entry_number}:" in unit_id
                )
            ]

            if len(
                matching_entries
            ) != 1:
                safe_collision = False
                break

            entry_number = matching_entries[
                0
            ]

            matched_object_indexes.add(
                entry_to_object[
                    entry_number
                ][
                    "index"
                ]
            )

            coverage_matches.append(
                (
                    coverage,
                    entry_number,
                )
            )

        if (
            not safe_collision
            or not coverage_matches
            or matched_object_indexes
            != set(
                object_entries
            )
        ):
            continue

        planned_new_ids: dict[int, str] = {}

        for index, entry_number in object_entries.items():
            new_id = (
                f"{collided_id}"
                f"__lane_{entry_number}"
            )

            if (
                new_id in existing_classical_ids
                and new_id != collided_id
            ):
                safe_collision = False
                break

            if new_id in planned_new_ids.values():
                safe_collision = False
                break

            planned_new_ids[
                index
            ] = new_id

        if not safe_collision:
            continue

        for index, meaning in rows:
            old_id = meaning.get(
                "meaning_id"
            )

            new_id = planned_new_ids[
                index
            ]

            meaning[
                "meaning_id"
            ] = new_id

            existing_classical_ids.add(
                new_id
            )

            classical_collision_repairs.append(
                {
                    "old_meaning_id":
                        old_id,

                    "new_meaning_id":
                        new_id,

                    "object_index":
                        index,

                    "lane_entry":
                        object_entries[
                            index
                        ],

                    "headword_arabic":
                        meaning.get(
                            "headword_arabic"
                        ),
                }
            )

        entry_to_new_id = {
            object_entries[
                index
            ]:
                new_id
            for index, new_id
            in planned_new_ids.items()
        }

        for coverage, entry_number in coverage_matches:
            coverage[
                "target_ids"
            ] = [
                (
                    entry_to_new_id[
                        entry_number
                    ]
                    if target == collided_id
                    else target
                )
                for target in (
                    coverage.get(
                        "target_ids"
                    )
                    or []
                )
            ]

    if classical_collision_repairs:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "CLASSICAL_MEANING_ID_COLLISIONS_REPAIRED",

                "message":
                    (
                        "Deterministically repaired "
                        f"{len(classical_collision_repairs)} Classical "
                        "meaning object ID(s) involved in duplicate-ID "
                        "collisions by unique Lane-entry provenance and "
                        "retargeted only the matching Lane ledger rows."
                    ),

                "details":
                    classical_collision_repairs,
            }
        )

    # ---- 2B. public_form_id collisions resolved by disjoint QAC groups.
    public_rows_by_collision_id: dict[str, list[tuple[int, dict]]] = {}

    for index, form in enumerate(
        quranic_forms
    ):
        public_id = form.get(
            "public_form_id"
        )

        if (
            isinstance(
                public_id,
                str,
            )
            and public_id
        ):
            public_rows_by_collision_id.setdefault(
                public_id,
                [],
            ).append(
                (
                    index,
                    form,
                )
            )

    existing_public_ids = {
        form.get(
            "public_form_id"
        )
        for form in quranic_forms
        if isinstance(
            form.get(
                "public_form_id"
            ),
            str,
        )
    }

    public_collision_repairs = []

    for collided_id, rows in public_rows_by_collision_id.items():
        if len(
            rows
        ) <= 1:
            continue

        if any(
            collided_id
            in (
                coverage.get(
                    "target_ids"
                )
                or []
            )
            for coverage in coverage_rows
        ):
            continue

        group_to_object_index: dict[str, int] = {}
        object_group_sets: dict[int, tuple[str, ...]] = {}
        safe_collision = True

        for index, form in rows:
            group_ids = [
                group_id
                for group_id in (
                    form.get(
                        "form_group_ids"
                    )
                    or []
                )
                if isinstance(
                    group_id,
                    str,
                )
                and group_id
            ]

            unique_group_ids = tuple(
                sorted(
                    set(
                        group_ids
                    )
                )
            )

            if (
                not unique_group_ids
                or len(
                    unique_group_ids
                )
                != len(
                    group_ids
                )
            ):
                safe_collision = False
                break

            for group_id in unique_group_ids:
                if group_id in group_to_object_index:
                    safe_collision = False
                    break

                group_to_object_index[
                    group_id
                ] = index

            if not safe_collision:
                break

            object_group_sets[
                index
            ] = unique_group_ids

        if not safe_collision:
            continue

        matching_accounting_rows: list[tuple[dict, int]] = []
        matched_object_indexes: set[int] = set()

        for accounting_row in accounting:
            if accounting_row.get(
                "target_public_form_id"
            ) != collided_id:
                continue

            group_id = accounting_row.get(
                "form_group_id"
            )

            object_index = group_to_object_index.get(
                group_id
            )

            if object_index is None:
                safe_collision = False
                break

            matched_object_indexes.add(
                object_index
            )

            matching_accounting_rows.append(
                (
                    accounting_row,
                    object_index,
                )
            )

        if (
            not safe_collision
            or not matching_accounting_rows
            or matched_object_indexes
            != set(
                object_group_sets
            )
        ):
            continue

        planned_new_ids: dict[int, str] = {}

        for index, group_ids in object_group_sets.items():
            digest_source = json.dumps(
                list(
                    group_ids
                ),
                ensure_ascii=False,
                separators=(
                    ",",
                    ":",
                ),
            )

            digest = hashlib.sha1(
                digest_source.encode(
                    "utf-8"
                )
            ).hexdigest()[
                :10
            ]

            new_id = (
                f"{collided_id}"
                f"__qac_{digest}"
            )

            if (
                new_id in existing_public_ids
                and new_id != collided_id
            ):
                safe_collision = False
                break

            if new_id in planned_new_ids.values():
                safe_collision = False
                break

            planned_new_ids[
                index
            ] = new_id

        if not safe_collision:
            continue

        for index, form in rows:
            old_id = form.get(
                "public_form_id"
            )

            new_id = planned_new_ids[
                index
            ]

            form[
                "public_form_id"
            ] = new_id

            existing_public_ids.add(
                new_id
            )

            public_collision_repairs.append(
                {
                    "old_public_form_id":
                        old_id,

                    "new_public_form_id":
                        new_id,

                    "object_index":
                        index,

                    "form_group_ids":
                        list(
                            object_group_sets[
                                index
                            ]
                        ),

                    "headword_arabic":
                        form.get(
                            "headword_arabic"
                        ),

                    "public_pos_label":
                        form.get(
                            "public_pos_label"
                        ),
                }
            )

        for accounting_row, object_index in matching_accounting_rows:
            accounting_row[
                "target_public_form_id"
            ] = planned_new_ids[
                object_index
            ]

    if public_collision_repairs:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "PUBLIC_FORM_ID_COLLISIONS_REPAIRED",

                "message":
                    (
                        "Deterministically repaired "
                        f"{len(public_collision_repairs)} Quranic public-form "
                        "object ID(s) involved in duplicate-ID collisions "
                        "using mutually disjoint QAC form-group identity and "
                        "retargeted only their matching accounting rows."
                    ),

                "details":
                    public_collision_repairs,
            }
        )

    # --------------------------------------------------------
    # 3. Repair only structurally identical duplicate containers.
    #
    # Two conservative cases are allowed:
    #
    # A. Duplicate quranic_forms rows with the same public_form_id may be
    #    merged ONLY when every field except quran_examples is identical.
    #    Their quran_examples are then unioned by exact canonical JSON
    #    identity, preserving first-seen order.
    #
    # B. Duplicate qac_form_accounting rows for the same form_group_id may
    #    be collapsed ONLY when every field except reason is identical.
    #    Distinct non-empty reasons are preserved by joining them.
    #
    # No conflicting senses, headwords, form groups, counts, dispositions,
    # targets, or semantic content are merged here.
    # --------------------------------------------------------

    def _canonical_json_value(
        value: Any,
    ) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

    # ---- 2A. Merge duplicate public-form containers differing only
    #           in quran_examples.
    public_rows_by_id: dict[str, list[tuple[int, dict]]] = {}

    for index, form in enumerate(
        quranic_forms
    ):
        public_id = form.get(
            "public_form_id"
        )

        if (
            isinstance(
                public_id,
                str,
            )
            and public_id
        ):
            public_rows_by_id.setdefault(
                public_id,
                [],
            ).append(
                (
                    index,
                    form,
                )
            )

    mergeable_public_ids: set[str] = set()
    public_merge_details = []

    for public_id, rows in public_rows_by_id.items():
        if len(
            rows
        ) <= 1:
            continue

        comparison_signatures = set()

        for _, form in rows:
            comparison_object = dict(
                form
            )

            comparison_object.pop(
                "quran_examples",
                None,
            )

            comparison_signatures.add(
                _canonical_json_value(
                    comparison_object
                )
            )

        if len(
            comparison_signatures
        ) != 1:
            continue

        mergeable_public_ids.add(
            public_id
        )

        merged_examples = []
        seen_examples = set()

        for _, form in rows:
            for example in (
                form.get(
                    "quran_examples"
                )
                or []
            ):
                signature = _canonical_json_value(
                    example
                )

                if signature in seen_examples:
                    continue

                seen_examples.add(
                    signature
                )

                merged_examples.append(
                    example
                )

        first_index, first_form = rows[
            0
        ]

        first_form[
            "quran_examples"
        ] = merged_examples

        public_merge_details.append(
            {
                "public_form_id":
                    public_id,

                "merged_row_count":
                    len(
                        rows
                    ),

                "retained_index":
                    first_index,

                "merged_quran_example_count":
                    len(
                        merged_examples
                    ),

                "reason":
                    (
                        "duplicate public-form objects were identical in "
                        "all fields except quran_examples"
                    ),
            }
        )

    if mergeable_public_ids:
        retained_public_ids = set()

        repaired_quranic_forms = []

        for form in quranic_forms:
            public_id = form.get(
                "public_form_id"
            )

            if public_id not in mergeable_public_ids:
                repaired_quranic_forms.append(
                    form
                )
                continue

            if public_id in retained_public_ids:
                continue

            retained_public_ids.add(
                public_id
            )

            repaired_quranic_forms.append(
                form
            )

        quranic_forms[:] = repaired_quranic_forms

    if public_merge_details:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "DUPLICATE_PUBLIC_FORM_CONTAINERS_MERGED",

                "message":
                    (
                        "Deterministically merged "
                        f"{len(public_merge_details)} duplicate public-form "
                        "container group(s) whose objects were identical "
                        "except for quran_examples; examples were unioned "
                        "without changing senses or form mappings."
                    ),

                "details":
                    public_merge_details,
            }
        )

    # ---- 2B. Collapse duplicate QAC-accounting rows differing only
    #           in reason text.
    accounting_rows_by_group: dict[str, list[tuple[int, dict]]] = {}

    for index, row in enumerate(
        accounting
    ):
        group_id = row.get(
            "form_group_id"
        )

        if (
            isinstance(
                group_id,
                str,
            )
            and group_id
        ):
            accounting_rows_by_group.setdefault(
                group_id,
                [],
            ).append(
                (
                    index,
                    row,
                )
            )

    collapsible_accounting_groups: set[str] = set()
    accounting_collapse_details = []

    for group_id, rows in accounting_rows_by_group.items():
        if len(
            rows
        ) <= 1:
            continue

        comparison_signatures = set()

        for _, row in rows:
            comparison_object = dict(
                row
            )

            comparison_object.pop(
                "reason",
                None,
            )

            comparison_signatures.add(
                _canonical_json_value(
                    comparison_object
                )
            )

        if len(
            comparison_signatures
        ) != 1:
            continue

        collapsible_accounting_groups.add(
            group_id
        )

        unique_reasons = []

        for _, row in rows:
            reason = row.get(
                "reason"
            )

            if (
                isinstance(
                    reason,
                    str,
                )
                and reason
                and reason
                not in unique_reasons
            ):
                unique_reasons.append(
                    reason
                )

        first_index, first_row = rows[
            0
        ]

        if unique_reasons:
            first_row[
                "reason"
            ] = " | ".join(
                unique_reasons
            )

        accounting_collapse_details.append(
            {
                "form_group_id":
                    group_id,

                "collapsed_row_count":
                    len(
                        rows
                    ),

                "retained_index":
                    first_index,

                "preserved_reason_count":
                    len(
                        unique_reasons
                    ),

                "reason":
                    (
                        "duplicate accounting rows were identical in all "
                        "fields except reason"
                    ),
            }
        )

    if collapsible_accounting_groups:
        retained_accounting_groups = set()

        repaired_accounting = []

        for row in accounting:
            group_id = row.get(
                "form_group_id"
            )

            if group_id not in collapsible_accounting_groups:
                repaired_accounting.append(
                    row
                )
                continue

            if group_id in retained_accounting_groups:
                continue

            retained_accounting_groups.add(
                group_id
            )

            repaired_accounting.append(
                row
            )

        accounting[:] = repaired_accounting

    if accounting_collapse_details:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "DUPLICATE_QAC_ACCOUNTING_ROWS_COLLAPSED",

                "message":
                    (
                        "Deterministically collapsed "
                        f"{len(accounting_collapse_details)} duplicate QAC "
                        "accounting group(s) whose rows differed only in "
                        "reason text; all distinct reason text was preserved."
                    ),

                "details":
                    accounting_collapse_details,
            }
        )

    # --------------------------------------------------------
    # 4. Repair explicitly evidence-proven lexical source-ref corruption.
    #
    # This is NOT a fuzzy source-ref fixer. Each correction is scoped to:
    # - one public_form_id,
    # - one sense_id,
    # - one exact malformed source_ref,
    # - one exact replacement source_ref.
    #
    # The replacement is applied only when:
    # - the malformed ref is present on that exact sense;
    # - the replacement ref exists in packet Lane primary evidence;
    # - the replacement Lane entry's Arabic headword exactly matches the
    #   affected Quranic public-form headword after NFKC + invisible-space
    #   cleanup.
    #
    # Current evidence-proven correction:
    # Twl / طَوِيلٌ / sense-Twl-Tawil-1
    #   lane:entry:11919 -> lane:entry:12019
    #
    # The diagnostic established that 12019 is the exact طَوِيلٌ Lane entry;
    # Mufradat row 921 independently attests temporal use and explicitly cites
    # Quran 73:7. No Lane ledger status or target is changed here.
    # --------------------------------------------------------

    lexical_source_ref_corrections = [
        {
            "public_form_id":
                "form-Twl-Tawil",

            "sense_id":
                "sense-Twl-Tawil-1",

            "old_source_ref":
                "lane:entry:11919",

            "new_source_ref":
                "lane:entry:12019",

            "expected_lane_headword":
                "طَوِيلٌ",
        }
    ]

    lexical_source_ref_repairs = []

    if packet:
        packet_lane_entries = (
            packet.get(
                "evidence",
                {},
            )
            .get(
                "lane",
                {},
            )
            .get(
                "primary",
                {},
            )
            .get(
                "entries",
                [],
            )
            or []
        )

        packet_lane_by_ref = {
            entry.get(
                "source_ref"
            ):
                entry
            for entry in packet_lane_entries
            if isinstance(
                entry,
                dict,
            )
            and isinstance(
                entry.get(
                    "source_ref"
                ),
                str,
            )
        }

        def _exact_visible_text(
            value: Any,
        ) -> Optional[str]:
            if not isinstance(
                value,
                str,
            ):
                return None

            cleaned = unicodedata.normalize(
                "NFKC",
                value,
            )

            cleaned = "".join(
                ch
                for ch in cleaned
                if (
                    not ch.isspace()
                    and unicodedata.category(
                        ch
                    )
                    not in {
                        "Cc",
                        "Cf",
                    }
                )
            )

            return (
                cleaned
                if cleaned
                else None
            )

        for correction in lexical_source_ref_corrections:
            public_form = next(
                (
                    form
                    for form in quranic_forms
                    if form.get(
                        "public_form_id"
                    )
                    ==
                    correction[
                        "public_form_id"
                    ]
                ),
                None,
            )

            if not public_form:
                continue

            sense = next(
                (
                    item
                    for item in (
                        public_form.get(
                            "senses"
                        )
                        or []
                    )
                    if item.get(
                        "sense_id"
                    )
                    ==
                    correction[
                        "sense_id"
                    ]
                ),
                None,
            )

            if not sense:
                continue

            source_refs = (
                sense.get(
                    "source_refs"
                )
                or []
            )

            old_ref = correction[
                "old_source_ref"
            ]

            new_ref = correction[
                "new_source_ref"
            ]

            if old_ref not in source_refs:
                continue

            replacement_entry = packet_lane_by_ref.get(
                new_ref
            )

            if not replacement_entry:
                continue

            form_headword = _exact_visible_text(
                public_form.get(
                    "headword_arabic"
                )
            )

            expected_headword = _exact_visible_text(
                correction[
                    "expected_lane_headword"
                ]
            )

            lane_headword = _exact_visible_text(
                replacement_entry.get(
                    "headword"
                )
            )

            if not (
                form_headword
                and expected_headword
                and lane_headword
                and form_headword
                ==
                expected_headword
                ==
                lane_headword
            ):
                continue

            sense[
                "source_refs"
            ] = [
                (
                    new_ref
                    if source_ref == old_ref
                    else source_ref
                )
                for source_ref in source_refs
            ]

            # Preserve first-seen order while avoiding a duplicate if the
            # corrected ref was already present for some reason.
            sense[
                "source_refs"
            ] = list(
                dict.fromkeys(
                    sense[
                        "source_refs"
                    ]
                )
            )

            lexical_source_ref_repairs.append(
                {
                    "public_form_id":
                        correction[
                            "public_form_id"
                        ],

                    "sense_id":
                        correction[
                            "sense_id"
                        ],

                    "old_source_ref":
                        old_ref,

                    "new_source_ref":
                        new_ref,

                    "lane_headword":
                        replacement_entry.get(
                            "headword"
                        ),

                    "reason":
                        (
                            "owner-scoped evidence-proven correction; "
                            "replacement Lane entry exists in packet and "
                            "its Arabic headword exactly matches the "
                            "Quranic public-form headword"
                        ),
                }
            )

    if lexical_source_ref_repairs:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "LEXICAL_SOURCE_REF_REALIGNED",

                "message":
                    (
                        "Deterministically corrected "
                        f"{len(lexical_source_ref_repairs)} explicitly "
                        "evidence-proven lexical source reference(s) whose "
                        "replacement Lane entry exists in the packet and "
                        "exactly matches the affected public-form headword."
                    ),

                "details":
                    lexical_source_ref_repairs,
            }
        )

    # --------------------------------------------------------
    # 5. Reconcile QAC accounting targets to the artifact's own
    #    unique quranic_forms mapping.
    # --------------------------------------------------------

    group_to_public: dict[str, list[str]] = {}

    for public_form in quranic_forms:
        public_id = public_form.get(
            "public_form_id"
        )

        if not public_id:
            continue

        for group_id in (
            public_form.get(
                "form_group_ids"
            )
            or []
        ):
            group_to_public.setdefault(
                group_id,
                [],
            ).append(
                public_id
            )

    accounting_repairs = []

    for row in accounting:
        if row.get(
            "disposition"
        ) not in {
            "DISPLAY",
            "MERGE",
        }:
            continue

        group_id = row.get(
            "form_group_id"
        )

        mapped_targets = list(
            dict.fromkeys(
                group_to_public.get(
                    group_id,
                    [],
                )
            )
        )

        if len(
            mapped_targets
        ) != 1:
            # Ambiguous or absent quranic_forms mapping: leave untouched.
            continue

        expected_target = mapped_targets[
            0
        ]

        current_target = row.get(
            "target_public_form_id"
        )

        if current_target == expected_target:
            continue

        row[
            "target_public_form_id"
        ] = expected_target

        accounting_repairs.append(
            {
                "form_group_id":
                    group_id,

                "old_target_public_form_id":
                    current_target,

                "new_target_public_form_id":
                    expected_target,

                "reason":
                    (
                        "The artifact itself maps this QAC group to exactly "
                        "one quranic_forms item."
                    ),
            }
        )

    if accounting_repairs:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "PUBLIC_FORM_TARGET_REALIGNED",

                "message":
                    (
                        "Deterministically aligned "
                        f"{len(accounting_repairs)} QAC accounting target(s) "
                        "to the artifact's unique quranic_forms mapping."
                    ),

                "details":
                    accounting_repairs,
            }
        )

    # Rebuild ID inventories after canonicalization/realignment.
    public_by_id = {
        form.get(
            "public_form_id"
        ):
            form
        for form in quranic_forms
        if form.get(
            "public_form_id"
        )
    }

    all_sense_ids = [
        sense.get(
            "sense_id"
        )
        for form in quranic_forms
        for sense in (
            form.get(
                "senses"
            )
            or []
        )
        if sense.get(
            "sense_id"
        )
    ]

    all_classical_ids = [
        meaning.get(
            "meaning_id"
        )
        for meaning in classical_meanings
        if meaning.get(
            "meaning_id"
        )
    ]

    all_valid_lane_targets = list(
        dict.fromkeys(
            all_sense_ids
            + all_classical_ids
        )
    )

    valid_lane_target_set = set(
        all_valid_lane_targets
    )

    lane_target_fingerprint_index = (
        _build_unique_fingerprint_index(
            all_valid_lane_targets
        )
    )


    # Mixed-script machine-ID corruption is handled separately from the
    # normal fingerprint. It is restricted to valid Quranic sense IDs that
    # themselves contain non-ASCII characters.
    lane_sense_nonascii_skeleton_index = (
        _build_unique_nonascii_skeleton_index(
            all_sense_ids
        )
    )

    # --------------------------------------------------------
    # 6. Repair Quran example sense references by unique
    #    separator/case/format-insensitive machine-ID identity.
    # --------------------------------------------------------

    example_repairs = []

    for form in quranic_forms:
        form_sense_ids = [
            sense.get(
                "sense_id"
            )
            for sense in (
                form.get(
                    "senses"
                )
                or []
            )
            if sense.get(
                "sense_id"
            )
        ]

        form_sense_set = set(
            form_sense_ids
        )

        form_fingerprint_index = (
            _build_unique_fingerprint_index(
                form_sense_ids
            )
        )

        form_nonascii_skeleton_index = (
            _build_unique_nonascii_skeleton_index(
                form_sense_ids
            )
        )

        for example in (
            form.get(
                "quran_examples"
            )
            or []
        ):
            repaired_sense_ids = []

            for sense_id in (
                example.get(
                    "sense_ids"
                )
                or []
            ):
                replacement = sense_id

                if sense_id not in form_sense_set:
                    fingerprint = _machine_id_fingerprint(
                        sense_id
                    )

                    candidate = (
                        form_fingerprint_index.get(
                            fingerprint
                        )
                        if fingerprint
                        else None
                    )

                    repair_reason = None

                    if candidate:
                        repair_reason = (
                            "unique_machine_id_fingerprint"
                        )

                    if (
                        candidate is None
                        and _contains_non_ascii_machine_chars(
                            sense_id
                        )
                    ):
                        skeleton = (
                            _ascii_machine_id_skeleton(
                                sense_id
                            )
                        )

                        candidate = (
                            form_nonascii_skeleton_index.get(
                                skeleton
                            )
                            if skeleton
                            else None
                        )

                        if candidate:
                            repair_reason = (
                                "unique_mixed_script_ascii_skeleton_"
                                "within_same_public_form"
                            )

                    if candidate:
                        replacement = candidate

                        example_repairs.append(
                            {
                                "public_form_id":
                                    form.get(
                                        "public_form_id"
                                    ),

                                "word_location":
                                    example.get(
                                        "word_location"
                                    ),

                                "old_sense_id":
                                    sense_id,

                                "new_sense_id":
                                    candidate,

                                "reason":
                                    repair_reason,
                            }
                        )

                repaired_sense_ids.append(
                    replacement
                )

            example[
                "sense_ids"
            ] = repaired_sense_ids

    if example_repairs:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "QURAN_EXAMPLE_SENSE_ID_REALIGNED",

                "message":
                    (
                        "Deterministically repaired "
                        f"{len(example_repairs)} Quran-example sense "
                        "reference(s) using either a unique conservative "
                        "machine-ID fingerprint or a unique mixed-script "
                        "ASCII skeleton within the same public form."
                    ),

                "details":
                    example_repairs,
            }
        )

    # --------------------------------------------------------
    # 7. Repair Lane target IDs conservatively.
    # --------------------------------------------------------

    lane_target_repairs = []

    for row in coverage_rows:
        if row.get(
            "status"
        ) not in {
            "REPRESENTED",
            "SUBSUMED",
        }:
            continue

        repaired_targets = []

        for target in (
            row.get(
                "target_ids"
            )
            or []
        ):
            replacement = target
            repair_reason = None

            if target in valid_lane_target_set:
                repaired_targets.append(
                    target
                )
                continue

            # Schema mistake: the model sometimes used public_form_id where
            # lane_unit_coverage requires a sense_id. This is mechanically
            # resolvable only when that form has exactly one sense.
            public_form = public_by_id.get(
                target
            )

            if public_form is not None:
                form_sense_ids = [
                    sense.get(
                        "sense_id"
                    )
                    for sense in (
                        public_form.get(
                            "senses"
                        )
                        or []
                    )
                    if sense.get(
                        "sense_id"
                    )
                ]

                if len(
                    form_sense_ids
                ) == 1:
                    replacement = form_sense_ids[
                        0
                    ]

                    repair_reason = (
                        "public_form_id_to_sole_sense_id"
                    )

            # Otherwise allow only exact unique machine-ID identity after
            # ignoring formatting/separator/case drift. This is deliberately
            # not fuzzy spelling or semantic matching.
            if (
                replacement == target
            ):
                fingerprint = _machine_id_fingerprint(
                    target
                )

                candidate = (
                    lane_target_fingerprint_index.get(
                        fingerprint
                    )
                    if fingerprint
                    else None
                )

                if candidate:
                    replacement = candidate

                    repair_reason = (
                        "unique_machine_id_fingerprint"
                    )

            if (
                replacement == target
                and _contains_non_ascii_machine_chars(
                    target
                )
            ):
                skeleton = _ascii_machine_id_skeleton(
                    target
                )

                candidate = (
                    lane_sense_nonascii_skeleton_index.get(
                        skeleton
                    )
                    if skeleton
                    else None
                )

                if candidate:
                    replacement = candidate

                    repair_reason = (
                        "unique_mixed_script_ascii_skeleton_"
                        "among_quranic_senses"
                    )

            if replacement != target:
                lane_target_repairs.append(
                    {
                        "unit_id":
                            row.get(
                                "unit_id"
                            ),

                        "old_target_id":
                            target,

                        "new_target_id":
                            replacement,

                        "reason":
                            repair_reason,
                    }
                )

            repaired_targets.append(
                replacement
            )

        row[
            "target_ids"
        ] = repaired_targets

    if lane_target_repairs:
        repairs.append(
            {
                "severity":
                    "warning",

                "code":
                    "LANE_TARGET_ID_REALIGNED",

                "message":
                    (
                        "Deterministically repaired "
                        f"{len(lane_target_repairs)} Lane ledger target "
                        "reference(s) using only sole-sense public-form "
                        "resolution, a unique conservative machine-ID "
                        "fingerprint, or a unique mixed-script ASCII skeleton "
                        "among valid Quranic sense IDs."
                    ),

                "details":
                    lane_target_repairs,
            }
        )


    # --------------------------------------------------------
    # 8. Repair invalid Quran example locations conservatively.
    #
    # Quran examples are illustrative, not accounting records. We therefore
    # permit only two deterministic operations:
    #
    # A. If the supplied word_location is not a QAC occurrence anywhere for
    #    this root, but the current public form has exactly ONE valid QAC
    #    location in the example's verse, replace word_location with that
    #    unique location.
    #
    # B. Otherwise, if the current public form already has at least one other
    #    valid Quran example, remove the invalid example only when either:
    #       - its location belongs unambiguously to another mapped public form,
    #         or
    #       - its location is not a QAC occurrence for this root at all.
    #
    # We deliberately do NOT move examples between public forms, invent a
    # word index, repair structurally-unmapped QAC groups, or remove the sole
    # example from a public form. Those cases remain visible to validation.
    # --------------------------------------------------------

    if packet is not None:
        packet_qac_forms_for_examples = (
            packet.get(
                "evidence",
                {},
            )
            .get(
                "qac_forms",
                {},
            )
            .get(
                "forms",
                [],
            )
            or []
        )

        qac_example_by_group = {
            row.get(
                "form_group_id"
            ):
                row
            for row in packet_qac_forms_for_examples
            if row.get(
                "form_group_id"
            )
        }

        root_location_to_groups = {}

        for qac_row in packet_qac_forms_for_examples:
            group_id = qac_row.get(
                "form_group_id"
            )

            for location in (
                qac_row.get(
                    "word_locations"
                )
                or []
            ):
                root_location_to_groups.setdefault(
                    location,
                    [],
                ).append(
                    group_id
                )

        example_group_to_public = {}

        for form in quranic_forms:
            public_id = form.get(
                "public_form_id"
            )

            for group_id in (
                form.get(
                    "form_group_ids"
                )
                or []
            ):
                example_group_to_public.setdefault(
                    group_id,
                    [],
                ).append(
                    public_id
                )

        def _verse_key_from_word_location(
            value: Any,
        ) -> Optional[str]:
            if not isinstance(
                value,
                str,
            ):
                return None

            parts = value.split(
                ":"
            )

            if len(
                parts
            ) < 3:
                return None

            return ":".join(
                parts[
                    :2
                ]
            )

        quran_example_location_repairs = []
        quran_example_removals = []

        for form in quranic_forms:
            public_id = form.get(
                "public_form_id"
            )

            form_group_ids = (
                form.get(
                    "form_group_ids"
                )
                or []
            )

            valid_locations_for_form = set()

            for group_id in form_group_ids:
                qac_row = qac_example_by_group.get(
                    group_id
                )

                if qac_row is None:
                    continue

                valid_locations_for_form.update(
                    qac_row.get(
                        "word_locations"
                    )
                    or []
                )

            examples = (
                form.get(
                    "quran_examples"
                )
                or []
            )

            valid_example_count = sum(
                1
                for example in examples
                if example.get(
                    "word_location"
                )
                in valid_locations_for_form
            )

            repaired_examples = []

            for example_index, example in enumerate(
                examples
            ):
                old_location = example.get(
                    "word_location"
                )

                if old_location in valid_locations_for_form:
                    repaired_examples.append(
                        example
                    )
                    continue

                verse_key = example.get(
                    "verse_key"
                )

                root_groups_for_location = list(
                    dict.fromkeys(
                        root_location_to_groups.get(
                            old_location,
                            [],
                        )
                    )
                )

                owning_public_forms = []

                for group_id in root_groups_for_location:
                    owning_public_forms.extend(
                        example_group_to_public.get(
                            group_id,
                            [],
                        )
                    )

                owning_public_forms = list(
                    dict.fromkeys(
                        owning_public_forms
                    )
                )

                same_verse_candidates = sorted(
                    location
                    for location
                    in valid_locations_for_form
                    if _verse_key_from_word_location(
                        location
                    )
                    == verse_key
                )

                # Case A: location is not a QAC occurrence for this root,
                # but there is exactly one valid location for this public
                # form in the same verse.
                if (
                    not root_groups_for_location
                    and len(
                        same_verse_candidates
                    ) == 1
                ):
                    new_location = same_verse_candidates[
                        0
                    ]

                    example[
                        "word_location"
                    ] = new_location

                    quran_example_location_repairs.append(
                        {
                            "public_form_id":
                                public_id,

                            "example_index":
                                example_index,

                            "verse_key":
                                verse_key,

                            "old_word_location":
                                old_location,

                            "new_word_location":
                                new_location,

                            "reason":
                                (
                                    "unique_current_form_qac_location_"
                                    "in_same_verse"
                                ),
                        }
                    )

                    repaired_examples.append(
                        example
                    )
                    continue

                # Case B1: the location belongs to another mapped public
                # form, never this one. Since examples are optional and this
                # form already has another valid example, drop it rather than
                # moving it or changing its sense assignment.
                location_belongs_only_elsewhere = (
                    bool(
                        owning_public_forms
                    )
                    and public_id
                    not in owning_public_forms
                )

                # Case B2: location is not in root QAC at all and there is
                # no unique same-verse repair. Again, drop it only if another
                # valid example remains for this form.
                location_not_in_root_qac = (
                    not root_groups_for_location
                )

                if (
                    valid_example_count >= 1
                    and (
                        location_belongs_only_elsewhere
                        or location_not_in_root_qac
                    )
                ):
                    quran_example_removals.append(
                        {
                            "public_form_id":
                                public_id,

                            "example_index":
                                example_index,

                            "verse_key":
                                verse_key,

                            "word_location":
                                old_location,

                            "sense_ids":
                                list(
                                    example.get(
                                        "sense_ids"
                                    )
                                    or []
                                ),

                            "reason":
                                (
                                    "belongs_to_other_public_form"
                                    if location_belongs_only_elsewhere
                                    else
                                    "not_in_root_qac_and_no_unique_"
                                    "same_verse_repair"
                                ),
                        }
                    )

                    continue

                # Structural/ambiguous case: preserve it unchanged so the
                # validator continues to surface the hard error.
                repaired_examples.append(
                    example
                )

            form[
                "quran_examples"
            ] = repaired_examples

        if quran_example_location_repairs:
            repairs.append(
                {
                    "severity":
                        "warning",

                    "code":
                        "QURAN_EXAMPLE_LOCATION_REALIGNED",

                    "message":
                        (
                            "Deterministically repaired "
                            f"{len(quran_example_location_repairs)} Quran "
                            "example word_location value(s) using the unique "
                            "QAC occurrence for the same public form and "
                            "verse."
                        ),

                    "details":
                        quran_example_location_repairs,
                }
            )

        if quran_example_removals:
            repairs.append(
                {
                    "severity":
                        "warning",

                    "code":
                        "INVALID_QURAN_EXAMPLES_REMOVED",

                    "message":
                        (
                            "Deterministically removed "
                            f"{len(quran_example_removals)} invalid optional "
                            "Quran example(s) rather than guessing a different "
                            "public form or word location; each affected public "
                            "form retained at least one independently valid "
                            "example."
                        ),

                    "details":
                        quran_example_removals,
                }
            )

    # --------------------------------------------------------
    # 9. Repair Quranic public-form occurrence_count values from
    #    packet QAC form-group counts, but only when the mapping is
    #    structurally unambiguous.
    #
    # Safe only when:
    # - the public form has at least one form_group_id;
    # - every group exists in packet evidence.qac_forms.forms;
    # - no group is duplicated inside the public form;
    # - no group is shared by multiple public forms;
    # - no group has duplicate qac_form_accounting rows;
    # - each DISPLAY/MERGE accounting row for the group targets
    #   this exact public_form_id.
    #
    # If any structural problem exists, occurrence_count is left
    # untouched so the validator continues to reject it.
    # --------------------------------------------------------

    if packet is not None:
        packet_qac_forms = (
            packet.get(
                "evidence",
                {},
            )
            .get(
                "qac_forms",
                {},
            )
            .get(
                "forms",
                [],
            )
            or []
        )

        qac_by_group = {
            row.get(
                "form_group_id"
            ):
                row
            for row in packet_qac_forms
            if row.get(
                "form_group_id"
            )
        }

        group_to_public_ids = {}

        for form in quranic_forms:
            public_id = form.get(
                "public_form_id"
            )

            for group_id in (
                form.get(
                    "form_group_ids"
                )
                or []
            ):
                group_to_public_ids.setdefault(
                    group_id,
                    [],
                ).append(
                    public_id
                )

        accounting_by_group = {}

        for row in accounting:
            group_id = row.get(
                "form_group_id"
            )

            if group_id:
                accounting_by_group.setdefault(
                    group_id,
                    [],
                ).append(
                    row
                )

        occurrence_count_repairs = []

        for form in quranic_forms:
            public_id = form.get(
                "public_form_id"
            )

            group_ids = (
                form.get(
                    "form_group_ids"
                )
                or []
            )

            if not group_ids:
                continue

            if len(
                group_ids
            ) != len(
                set(
                    group_ids
                )
            ):
                continue

            if any(
                group_id
                not in qac_by_group
                for group_id in group_ids
            ):
                continue

            if any(
                len(
                    set(
                        group_to_public_ids.get(
                            group_id,
                            [],
                        )
                    )
                ) > 1
                for group_id in group_ids
            ):
                continue

            if any(
                len(
                    accounting_by_group.get(
                        group_id,
                        [],
                    )
                ) > 1
                for group_id in group_ids
            ):
                continue

            structurally_valid = True

            for group_id in group_ids:
                for row in accounting_by_group.get(
                    group_id,
                    [],
                ):
                    if row.get(
                        "disposition"
                    ) not in {
                        "DISPLAY",
                        "MERGE",
                    }:
                        continue

                    if row.get(
                        "target_public_form_id"
                    ) != public_id:
                        structurally_valid = False
                        break

                if not structurally_valid:
                    break

            if not structurally_valid:
                continue

            expected_count = sum(
                int(
                    qac_by_group[
                        group_id
                    ].get(
                        "occurrence_count"
                    )
                    or 0
                )
                for group_id in group_ids
            )

            current_count = int(
                form.get(
                    "occurrence_count"
                )
                or 0
            )

            if current_count == expected_count:
                continue

            form[
                "occurrence_count"
            ] = expected_count

            occurrence_count_repairs.append(
                {
                    "public_form_id":
                        public_id,

                    "form_group_ids":
                        list(
                            group_ids
                        ),

                    "old_occurrence_count":
                        current_count,

                    "new_occurrence_count":
                        expected_count,

                    "reason":
                        (
                            "sum_of_packet_qac_form_group_occurrence_counts"
                        ),
                }
            )

        if occurrence_count_repairs:
            repairs.append(
                {
                    "severity":
                        "warning",

                    "code":
                        "OCCURRENCE_COUNT_REALIGNED",

                    "message":
                        (
                            "Deterministically repaired "
                            f"{len(occurrence_count_repairs)} Quranic public-"
                            "form occurrence_count value(s) from packet QAC "
                            "form-group counts after confirming structurally "
                            "unambiguous mappings."
                        ),

                    "details":
                        occurrence_count_repairs,
                }
            )

    # --------------------------------------------------------
    # 10. Repair Lane source-unit IDs against the packet.
    #
    # The packet is authoritative for the allowed source-unit ledger.
    # Only two lossless operations are permitted:
    #
    # A. Prefix-format repair when an unknown artifact unit maps EXACTLY
    #    onto one currently-missing expected unit by changing only:
    #       lane:unit:<...> -> lane-unit:<...>
    #       lane:<...>      -> lane-unit:<...>
    #
    # B. Remove unknown ledger rows only when there are ZERO missing
    #    expected Lane units after prefix repair. In that situation the
    #    unknown row cannot be standing in for an omitted expected unit;
    #    it is necessarily extra bookkeeping not defined by the packet.
    #
    # Ambiguous cases such as :status vs :main, or a different group/subunit,
    # are deliberately left untouched.
    # --------------------------------------------------------

    if packet is not None:
        expected_lane_unit_ids = []

        for entry in (
            packet.get(
                "evidence",
                {},
            )
            .get(
                "lane",
                {},
            )
            .get(
                "primary",
                {},
            )
            .get(
                "entries",
                [],
            )
        ):
            for source_unit in (
                entry.get(
                    "source_units"
                )
                or []
            ):
                unit_id = source_unit.get(
                    "unit_id"
                )

                if (
                    isinstance(
                        unit_id,
                        str,
                    )
                    and unit_id
                ):
                    expected_lane_unit_ids.append(
                        unit_id
                    )

        expected_lane_unit_set = set(
            expected_lane_unit_ids
        )

        def lane_unit_prefix_candidate(
            value: Any,
        ) -> Optional[str]:
            if not isinstance(
                value,
                str,
            ):
                return None

            if value.startswith(
                "lane:unit:"
            ):
                return (
                    "lane-unit:"
                    + value[
                        len(
                            "lane:unit:"
                        ):
                    ]
                )

            if value.startswith(
                "lane:"
            ):
                return (
                    "lane-unit:"
                    + value[
                        len(
                            "lane:"
                        ):
                    ]
                )

            return None

        actual_lane_unit_ids = [
            row.get(
                "unit_id"
            )
            for row in coverage_rows
            if (
                isinstance(
                    row.get(
                        "unit_id"
                    ),
                    str,
                )
                and row.get(
                    "unit_id"
                )
            )
        ]

        actual_lane_unit_set = set(
            actual_lane_unit_ids
        )

        missing_lane_unit_ids = (
            expected_lane_unit_set
            - actual_lane_unit_set
        )

        unknown_lane_unit_ids = (
            actual_lane_unit_set
            - expected_lane_unit_set
        )

        proposed_lane_unit_renames = {}

        for old_unit_id in unknown_lane_unit_ids:
            candidate = lane_unit_prefix_candidate(
                old_unit_id
            )

            if (
                candidate
                and candidate
                in missing_lane_unit_ids
            ):
                proposed_lane_unit_renames[
                    old_unit_id
                ] = candidate

        # Protect against two malformed rows collapsing onto one expected row.
        destination_sources = {}

        for old_unit_id, new_unit_id in (
            proposed_lane_unit_renames.items()
        ):
            destination_sources.setdefault(
                new_unit_id,
                set(),
            ).add(
                old_unit_id
            )

        safe_lane_unit_renames = {
            old_unit_id:
                new_unit_id
            for old_unit_id, new_unit_id
            in proposed_lane_unit_renames.items()
            if len(
                destination_sources.get(
                    new_unit_id,
                    set(),
                )
            ) == 1
        }

        lane_unit_rename_details = []

        if safe_lane_unit_renames:
            for row in coverage_rows:
                old_unit_id = row.get(
                    "unit_id"
                )

                new_unit_id = (
                    safe_lane_unit_renames.get(
                        old_unit_id
                    )
                )

                if (
                    new_unit_id
                    and new_unit_id
                    != old_unit_id
                ):
                    row[
                        "unit_id"
                    ] = new_unit_id

                    lane_unit_rename_details.append(
                        {
                            "old_unit_id":
                                old_unit_id,

                            "new_unit_id":
                                new_unit_id,

                            "reason":
                                "exact_lane_unit_prefix_format_repair",
                        }
                    )

            repairs.append(
                {
                    "severity":
                        "warning",

                    "code":
                        "LANE_UNIT_ID_REALIGNED",

                    "message":
                        (
                            "Deterministically repaired "
                            f"{len(lane_unit_rename_details)} Lane source-unit "
                            "ID(s) by an exact prefix-format correction "
                            "against currently-missing packet unit IDs."
                        ),

                    "details":
                        lane_unit_rename_details,
                }
            )

        # Recompute after safe renames.
        actual_lane_unit_ids = [
            row.get(
                "unit_id"
            )
            for row in coverage_rows
            if (
                isinstance(
                    row.get(
                        "unit_id"
                    ),
                    str,
                )
                and row.get(
                    "unit_id"
                )
            )
        ]

        actual_lane_unit_set = set(
            actual_lane_unit_ids
        )

        missing_lane_unit_ids = (
            expected_lane_unit_set
            - actual_lane_unit_set
        )

        unknown_lane_unit_ids = (
            actual_lane_unit_set
            - expected_lane_unit_set
        )

        # If every expected source unit is already present, any remaining
        # unknown row is necessarily extra ledger bookkeeping. Removing the
        # row does not invent coverage and cannot conceal a missing source
        # unit. Any downstream source-link problem remains visible to the
        # validator.
        if (
            not missing_lane_unit_ids
            and unknown_lane_unit_ids
        ):
            removed_lane_unit_rows = [
                {
                    "unit_id":
                        row.get(
                            "unit_id"
                        ),

                    "status":
                        row.get(
                            "status"
                        ),

                    "target_ids":
                        list(
                            row.get(
                                "target_ids"
                            )
                            or []
                        ),
                }
                for row in coverage_rows
                if row.get(
                    "unit_id"
                )
                in unknown_lane_unit_ids
            ]

            if removed_lane_unit_rows:
                coverage_rows[:] = [
                    row
                    for row in coverage_rows
                    if row.get(
                        "unit_id"
                    )
                    not in unknown_lane_unit_ids
                ]

                repairs.append(
                    {
                        "severity":
                            "warning",

                        "code":
                            "EXTRA_LANE_UNIT_ROWS_REMOVED",

                        "message":
                            (
                                "Deterministically removed "
                                f"{len(removed_lane_unit_rows)} Lane ledger "
                                "row(s) whose unit_id is not defined by the "
                                "packet, after confirming that no expected "
                                "Lane source units are missing."
                            ),

                        "details":
                            removed_lane_unit_rows,
                    }
                )

    return repairs

def finding(
    severity: str,
    code: str,
    message: str,
) -> dict:
    return {
        "severity":
            severity,

        "code":
            code,

        "message":
            message,
    }


def validate_artifact(
    *,
    packet: dict,
    artifact: dict,
) -> list[dict]:
    """
    High-value final-artifact validation.

    "error" means the artifact should not be promoted automatically.
    "warning" means the finding is preserved for later review but the
    artifact may still be usable.

    In particular, the synthesis packet intentionally contains only a small
    representative subset of QF occurrences. Therefore, a Quran example that
    is a genuine QAC location but was not included in the compact QF subset is
    a WARNING, not an error.
    """
    findings = []

    root = packet[
        "root"
    ]

    if artifact.get(
        "root"
    ) != root:
        findings.append(
            finding(
                "error",
                "ROOT_MISMATCH",
                (
                    f"root mismatch: expected {root!r}, "
                    f"got {artifact.get('root')!r}"
                ),
            )
        )

    qac_forms = (
        packet[
            "evidence"
        ][
            "qac_forms"
        ].get(
            "forms",
            []
        )
    )

    qac_by_id = {
        form[
            "form_group_id"
        ]:
            form
        for form in qac_forms
    }

    expected_ids = set(
        qac_by_id
    )

    accounting = (
        artifact.get(
            "qac_form_accounting"
        )
        or []
    )

    accounting_ids = [
        item.get(
            "form_group_id"
        )
        for item in accounting
    ]

    if (
        len(
            accounting_ids
        )
        != len(
            set(
                accounting_ids
            )
        )
    ):
        findings.append(
            finding(
                "error",
                "DUPLICATE_QAC_FORM_ACCOUNTING",
                (
                    "qac_form_accounting contains duplicate "
                    "form_group_id values."
                ),
            )
        )

    returned_accounting_ids = set(
        accounting_ids
    )

    missing = sorted(
        expected_ids
        - returned_accounting_ids
    )

    extra = sorted(
        returned_accounting_ids
        - expected_ids
    )

    if missing:
        findings.append(
            finding(
                "error",
                "MISSING_QAC_FORM_ACCOUNTING",
                f"missing QAC form accounting: {missing}",
            )
        )

    if extra:
        findings.append(
            finding(
                "error",
                "UNKNOWN_QAC_FORM_ACCOUNTING",
                f"unknown QAC form accounting: {extra}",
            )
        )

    public_forms = (
        artifact.get(
            "quranic_forms"
        )
        or []
    )

    public_ids = [
        form.get(
            "public_form_id"
        )
        for form in public_forms
    ]

    if (
        len(
            public_ids
        )
        != len(
            set(
                public_ids
            )
        )
    ):
        findings.append(
            finding(
                "error",
                "DUPLICATE_PUBLIC_FORM_ID",
                "duplicate public_form_id values.",
            )
        )

    public_by_id = {
        form.get(
            "public_form_id"
        ):
            form
        for form in public_forms
        if form.get(
            "public_form_id"
        )
    }

    for public_id in public_ids:
        if (
            isinstance(
                public_id,
                str,
            )
            and any(
                ch.isspace()
                for ch in public_id
            )
        ):
            findings.append(
                finding(
                    "error",
                    "PUBLIC_FORM_ID_CONTAINS_WHITESPACE",
                    (
                        f"public_form_id {public_id!r} contains "
                        "whitespace."
                    ),
                )
            )

    qac_public_mapping = {}

    for public_form in public_forms:
        public_id = public_form.get(
            "public_form_id"
        )

        group_ids = (
            public_form.get(
                "form_group_ids"
            )
            or []
        )

        for group_id in group_ids:
            if group_id not in expected_ids:
                findings.append(
                    finding(
                        "error",
                        "UNKNOWN_PUBLIC_FORM_QAC_GROUP",
                        (
                            f"{public_id}: unknown form_group_id "
                            f"{group_id!r}"
                        ),
                    )
                )
                continue

            if group_id in qac_public_mapping:
                findings.append(
                    finding(
                        "error",
                        "QAC_GROUP_IN_MULTIPLE_PUBLIC_FORMS",
                        (
                            f"{group_id}: appears in multiple "
                            "public forms."
                        ),
                    )
                )
            else:
                qac_public_mapping[
                    group_id
                ] = public_id

        expected_count = sum(
            int(
                qac_by_id[
                    group_id
                ].get(
                    "occurrence_count"
                )
                or 0
            )
            for group_id in group_ids
            if group_id in qac_by_id
        )

        # Public morphology-label quality checks. These are warnings rather
        # than hard errors because the semantic artifact can still be valid
        # and the UI can deterministically join the canonical QAC layer.
        label = str(
            public_form.get(
                "public_pos_label"
            )
            or ""
        ).casefold()

        verb_form = public_form.get(
            "verb_form"
        )

        if verb_form:
            if (
                "verb" not in label
                or str(
                    verb_form
                ).casefold()
                not in label
            ):
                findings.append(
                    finding(
                        "warning",
                        "PUBLIC_VERB_LABEL_TOO_GENERIC",
                        (
                            f"{public_id}: public_pos_label "
                            f"{public_form.get('public_pos_label')!r} "
                            f"does not expose verb form {verb_form}."
                        ),
                    )
                )

        derived_types = set()
        derived_total = 0

        for group_id in group_ids:
            group = qac_by_id.get(
                group_id
            )

            if not group:
                continue

            counts = (
                group.get(
                    "derived_nominal_counts"
                )
                or {}
            )

            for dtype, count in counts.items():
                count_int = int(
                    count
                    or 0
                )

                if count_int > 0:
                    derived_types.add(
                        dtype
                    )
                    derived_total += (
                        count_int
                    )

        if (
            len(
                derived_types
            ) == 1
            and derived_total == expected_count
            and expected_count > 0
        ):
            dtype = next(
                iter(
                    derived_types
                )
            )

            expected_phrase = {
                "VERBAL_NOUN":
                    "verbal noun",

                "ACTIVE_PARTICIPLE":
                    "participle",

                "PASSIVE_PARTICIPLE":
                    "participle",
            }.get(
                dtype
            )

            if (
                expected_phrase
                and expected_phrase
                not in label
            ):
                findings.append(
                    finding(
                        "warning",
                        "PUBLIC_DERIVED_NOMINAL_LABEL_TOO_GENERIC",
                        (
                            f"{public_id}: all underlying QAC "
                            f"occurrences are {dtype}, but "
                            f"public_pos_label is "
                            f"{public_form.get('public_pos_label')!r}."
                        ),
                    )
                )

        actual_count = int(
            public_form.get(
                "occurrence_count"
            )
            or 0
        )

        if actual_count != expected_count:
            findings.append(
                finding(
                    "error",
                    "OCCURRENCE_COUNT_MISMATCH",
                    (
                        f"{public_id}: occurrence_count "
                        f"{actual_count} != underlying QAC sum "
                        f"{expected_count}"
                    ),
                )
            )

    accounting_by_id = {
        item.get(
            "form_group_id"
        ):
            item
        for item in accounting
        if item.get(
            "form_group_id"
        )
    }

    for group_id in expected_ids:
        item = accounting_by_id.get(
            group_id
        )

        if item is None:
            continue

        disposition = item.get(
            "disposition"
        )

        target = item.get(
            "target_public_form_id"
        )

        mapped = qac_public_mapping.get(
            group_id
        )

        if disposition in {
            "DISPLAY",
            "MERGE",
        }:
            if not target:
                findings.append(
                    finding(
                        "error",
                        "MISSING_PUBLIC_FORM_TARGET",
                        (
                            f"{group_id}: {disposition} requires "
                            "target_public_form_id."
                        ),
                    )
                )
            elif target not in public_by_id:
                findings.append(
                    finding(
                        "error",
                        "UNKNOWN_PUBLIC_FORM_TARGET",
                        (
                            f"{group_id}: target public form "
                            f"{target!r} does not exist."
                        ),
                    )
                )
            elif mapped != target:
                findings.append(
                    finding(
                        "error",
                        "PUBLIC_FORM_MAPPING_MISMATCH",
                        (
                            f"{group_id}: accounting target "
                            f"{target!r} does not match "
                            f"quranic_forms mapping {mapped!r}."
                        ),
                    )
                )

            if (
                disposition
                == "MERGE"
                and not str(
                    item.get(
                        "reason"
                    )
                    or ""
                ).strip()
            ):
                findings.append(
                    finding(
                        "error",
                        "MERGE_WITHOUT_REASON",
                        f"{group_id}: MERGE requires a reason.",
                    )
                )

        elif disposition == "EXCLUDE_WITH_REASON":
            if mapped is not None:
                findings.append(
                    finding(
                        "error",
                        "EXCLUDED_FORM_STILL_DISPLAYED",
                        (
                            f"{group_id}: excluded form is still "
                            f"present under public form {mapped!r}."
                        ),
                    )
                )

            if not str(
                item.get(
                    "reason"
                )
                or ""
            ).strip():
                findings.append(
                    finding(
                        "error",
                        "EXCLUSION_WITHOUT_REASON",
                        (
                            f"{group_id}: EXCLUDE_WITH_REASON "
                            "requires a reason."
                        ),
                    )
                )

    refs = collect_evidence_refs(
        packet
    )

    qf_examples = collect_qf_examples(
        packet
    )

    for public_form in public_forms:
        public_id = public_form.get(
            "public_form_id"
        )

        sense_ids = set()

        for sense in public_form.get(
            "senses",
            []
        ):
            sense_id = sense.get(
                "sense_id"
            )

            if not sense_id:
                findings.append(
                    finding(
                        "error",
                        "MISSING_SENSE_ID",
                        f"{public_id}: sense missing sense_id.",
                    )
                )
                continue

            if (
                isinstance(
                    sense_id,
                    str,
                )
                and any(
                    ch.isspace()
                    for ch in sense_id
                )
            ):
                findings.append(
                    finding(
                        "error",
                        "SENSE_ID_CONTAINS_WHITESPACE",
                        (
                            f"{public_id}: sense_id {sense_id!r} "
                            "contains whitespace."
                        ),
                    )
                )

            if sense_id in sense_ids:
                findings.append(
                    finding(
                        "error",
                        "DUPLICATE_SENSE_ID",
                        (
                            f"{public_id}: duplicate sense_id "
                            f"{sense_id!r}."
                        ),
                    )
                )

            sense_ids.add(
                sense_id
            )

            source_refs = set(
                sense.get(
                    "source_refs"
                )
                or []
            )

            bad_refs = sorted(
                source_refs
                - refs[
                    "all"
                ]
            )

            if bad_refs:
                findings.append(
                    finding(
                        "error",
                        "UNKNOWN_LEXICAL_SOURCE_REF",
                        (
                            f"{public_id}/{sense_id}: unknown "
                            f"source_refs {bad_refs}"
                        ),
                    )
                )

            if not (
                source_refs
                & refs[
                    "direct_lexical"
                ]
            ):
                findings.append(
                    finding(
                        "error",
                        "NO_DIRECT_LEXICAL_SUPPORT",
                        (
                            f"{public_id}/{sense_id}: no direct "
                            "lexical support from Lane primary or "
                            "unique Mufradat evidence."
                        ),
                    )
                )

        group_location_set = set()

        for group_id in (
            public_form.get(
                "form_group_ids"
            )
            or []
        ):
            if group_id in qac_by_id:
                group_location_set.update(
                    qac_by_id[
                        group_id
                    ].get(
                        "word_locations",
                        []
                    )
                )

        for example in public_form.get(
            "quran_examples",
            []
        ):
            location = example.get(
                "word_location"
            )

            if location not in group_location_set:
                findings.append(
                    finding(
                        "error",
                        "INVALID_QURAN_EXAMPLE_LOCATION",
                        (
                            f"{public_id}: Quran example location "
                            f"{location!r} is not in its QAC form "
                            "groups."
                        ),
                    )
                )
                # If the QAC location itself is invalid, further QF
                # verification is not useful.
                continue

            qf = qf_examples.get(
                location
            )

            if qf is None:
                findings.append(
                    finding(
                        "warning",
                        "QF_REPRESENTATIVE_NOT_SUPPLIED",
                        (
                            f"{public_id}: Quran example "
                            f"{location!r} is a valid QAC occurrence "
                            "but was not one of the compact packet's "
                            "representative QF occurrences; its "
                            "context_gloss was therefore not verified "
                            "against QF in this pass."
                        ),
                    )
                )
            else:
                expected_verse = qf.get(
                    "verse_key"
                )

                if example.get(
                    "verse_key"
                ) != expected_verse:
                    findings.append(
                        finding(
                            "error",
                            "QURAN_EXAMPLE_VERSE_KEY_MISMATCH",
                            (
                                f"{public_id}: example "
                                f"{location!r} verse_key does not "
                                "match supplied QF evidence."
                            ),
                        )
                    )

                expected_gloss = (
                    qf.get(
                        "context_gloss"
                    )
                    or ""
                )

                actual_gloss = (
                    example.get(
                        "context_gloss"
                    )
                    or ""
                )

                if actual_gloss != expected_gloss:
                    findings.append(
                        finding(
                            "warning",
                            "QF_GLOSS_MISMATCH",
                            (
                                f"{public_id}: example "
                                f"{location!r} context_gloss differs "
                                "from supplied QF wording. This can be "
                                "rejoined deterministically later."
                            ),
                        )
                    )

            for sense_id in (
                example.get(
                    "sense_ids"
                )
                or []
            ):
                if sense_id not in sense_ids:
                    findings.append(
                        finding(
                            "error",
                            "UNKNOWN_EXAMPLE_SENSE_ID",
                            (
                                f"{public_id}: example "
                                f"{location!r} references unknown "
                                f"sense_id {sense_id!r}."
                            ),
                        )
                    )

    # --------------------------------------------------------
    # Lane primary source-unit coverage ledger
    # --------------------------------------------------------
    lane_primary_entries = (
        packet.get(
            "evidence",
            {}
        ).get(
            "lane",
            {}
        ).get(
            "primary",
            {}
        ).get(
            "entries",
            []
        )
    )

    expected_lane_units = {}
    lane_unit_entry_ref = {}

    for lane_entry in lane_primary_entries:
        entry_ref = lane_entry.get(
            "source_ref"
        )

        for unit in (
            lane_entry.get(
                "source_units"
            )
            or []
        ):
            unit_id = unit.get(
                "unit_id"
            )

            if unit_id:
                expected_lane_units[
                    unit_id
                ] = unit

                lane_unit_entry_ref[
                    unit_id
                ] = entry_ref

    coverage_rows = (
        artifact.get(
            "lane_unit_coverage"
        )
        or []
    )

    coverage_by_unit = {}

    for row in coverage_rows:
        unit_id = row.get(
            "unit_id"
        )

        if not unit_id:
            findings.append(
                finding(
                    "error",
                    "LANE_COVERAGE_UNIT_ID_MISSING",
                    "lane_unit_coverage row is missing unit_id.",
                )
            )
            continue

        if unit_id in coverage_by_unit:
            findings.append(
                finding(
                    "error",
                    "DUPLICATE_LANE_UNIT_COVERAGE",
                    (
                        f"Lane source unit {unit_id!r} appears more "
                        "than once in lane_unit_coverage."
                    ),
                )
            )
            continue

        coverage_by_unit[
            unit_id
        ] = row

    expected_unit_ids = set(
        expected_lane_units
    )

    actual_unit_ids = set(
        coverage_by_unit
    )

    missing_unit_ids = sorted(
        expected_unit_ids
        - actual_unit_ids
    )

    unknown_unit_ids = sorted(
        actual_unit_ids
        - expected_unit_ids
    )

    if missing_unit_ids:
        findings.append(
            finding(
                "error",
                "MISSING_LANE_UNIT_COVERAGE",
                (
                    f"{len(missing_unit_ids)} Lane PRIMARY source "
                    "unit(s) are missing from lane_unit_coverage: "
                    f"{missing_unit_ids[:20]}"
                ),
            )
        )

    if unknown_unit_ids:
        findings.append(
            finding(
                "error",
                "UNKNOWN_LANE_UNIT_COVERAGE",
                (
                    "lane_unit_coverage contains unknown/non-primary "
                    f"unit ids: {unknown_unit_ids[:20]}"
                ),
            )
        )

    # Stable IDs for Classical meanings.
    classical_ids = []

    for index, meaning in enumerate(
        artifact.get(
            "other_classical_meanings"
        )
        or [],
        start=1,
    ):
        meaning_id = meaning.get(
            "meaning_id"
        )

        if not meaning_id:
            findings.append(
                finding(
                    "error",
                    "MISSING_CLASSICAL_MEANING_ID",
                    (
                        "other_classical_meanings"
                        f"[{index}] is missing meaning_id."
                    ),
                )
            )
            continue

        if any(
            ch.isspace()
            for ch in str(
                meaning_id
            )
        ):
            findings.append(
                finding(
                    "error",
                    "CLASSICAL_MEANING_ID_CONTAINS_WHITESPACE",
                    (
                        f"Classical meaning_id {meaning_id!r} "
                        "contains whitespace."
                    ),
                )
            )

        classical_ids.append(
            meaning_id
        )

    if len(
        classical_ids
    ) != len(
        set(
            classical_ids
        )
    ):
        findings.append(
            finding(
                "error",
                "DUPLICATE_CLASSICAL_MEANING_ID",
                "Duplicate Classical meaning_id values exist.",
            )
        )

    all_sense_ids_global = {
        sense.get(
            "sense_id"
        )
        for public_form in public_forms
        for sense in (
            public_form.get(
                "senses"
            )
            or []
        )
        if sense.get(
            "sense_id"
        )
    }

    all_target_ids = (
        set(
            classical_ids
        )
        | all_sense_ids_global
    )

    # Track which Lane units the model says support each target.
    target_to_unit_ids = {}

    for unit_id, row in coverage_by_unit.items():
        status = row.get(
            "status"
        )

        target_ids = (
            row.get(
                "target_ids"
            )
            or []
        )

        note = (
            row.get(
                "note"
            )
            or ""
        ).strip()

        if status in {
            "REPRESENTED",
            "SUBSUMED",
        }:
            if not target_ids:
                findings.append(
                    finding(
                        "error",
                        "LANE_COVERAGE_TARGET_MISSING",
                        (
                            f"{unit_id}: {status} requires at least "
                            "one target_id."
                        ),
                    )
                )

            bad_targets = sorted(
                set(
                    target_ids
                )
                - all_target_ids
            )

            if bad_targets:
                findings.append(
                    finding(
                        "error",
                        "UNKNOWN_LANE_COVERAGE_TARGET",
                        (
                            f"{unit_id}: unknown target_ids "
                            f"{bad_targets}."
                        ),
                    )
                )

            for target_id in target_ids:
                target_to_unit_ids.setdefault(
                    target_id,
                    set(),
                ).add(
                    unit_id
                )

        elif status in {
            "NON_SEMANTIC",
            "AMBIGUOUS",
        }:
            if target_ids:
                findings.append(
                    finding(
                        "error",
                        "LANE_COVERAGE_UNEXPECTED_TARGET",
                        (
                            f"{unit_id}: {status} must not have "
                            "target_ids."
                        ),
                    )
                )

            if not note:
                findings.append(
                    finding(
                        "error",
                        "LANE_COVERAGE_NOTE_MISSING",
                        (
                            f"{unit_id}: {status} requires a short "
                            "note."
                        ),
                    )
                )

    # If a target cites Lane entry X, require at least one source_unit
    # from Lane entry X to point to that target in the coverage ledger.
    target_lane_refs = {}

    for public_form in public_forms:
        for sense in (
            public_form.get(
                "senses"
            )
            or []
        ):
            target_id = sense.get(
                "sense_id"
            )

            if not target_id:
                continue

            target_lane_refs[
                target_id
            ] = {
                ref
                for ref in (
                    sense.get(
                        "source_refs"
                    )
                    or []
                )
                if str(
                    ref
                ).startswith(
                    "lane:entry:"
                )
            }

    for meaning in (
        artifact.get(
            "other_classical_meanings"
        )
        or []
    ):
        target_id = meaning.get(
            "meaning_id"
        )

        if not target_id:
            continue

        target_lane_refs[
            target_id
        ] = {
            ref
            for ref in (
                meaning.get(
                    "source_refs"
                )
                or []
            )
            if str(
                ref
            ).startswith(
                "lane:entry:"
            )
        }

    quran_sense_direct_refs = {}

    for public_form in public_forms:
        for sense in (
            public_form.get(
                "senses"
            )
            or []
        ):
            target_id = sense.get(
                "sense_id"
            )

            if not target_id:
                continue

            quran_sense_direct_refs[
                target_id
            ] = {
                ref
                for ref in (
                    sense.get(
                        "source_refs"
                    )
                    or []
                )
                if (
                    str(ref).startswith("lane:entry:")
                    or str(ref).startswith("mufradat:")
                )
            }

    for target_id, lane_refs in target_lane_refs.items():
        if not lane_refs:
            continue

        linked_units = target_to_unit_ids.get(
            target_id,
            set(),
        )

        linked_entry_refs = {
            lane_unit_entry_ref.get(
                unit_id
            )
            for unit_id in linked_units
        }

        direct_refs = quran_sense_direct_refs.get(
            target_id,
            set(),
        )

        has_mufradat_support = any(
            str(ref).startswith(
                "mufradat:"
            )
            for ref in direct_refs
        )

        if (
            target_id in quran_sense_direct_refs
            and not has_mufradat_support
            and lane_refs
            and not (
                lane_refs
                & linked_entry_refs
            )
        ):
            # A Quran form that QAC identifies entirely as a transparent
            # derived nominal (verbal noun / active participle / passive
            # participle) may legitimately inherit the lexical branch of
            # its parent verb even when Lane does not give that derivative
            # a separate source_unit. Keep this visible as a warning rather
            # than rejecting an otherwise valid artifact.
            target_public_form = None

            for public_form in public_forms:
                if any(
                    sense.get("sense_id") == target_id
                    for sense in (
                        public_form.get("senses")
                        or []
                    )
                ):
                    target_public_form = public_form
                    break

            transparent_derived_nominal = False

            if target_public_form is not None:
                group_ids = (
                    target_public_form.get(
                        "form_group_ids"
                    )
                    or []
                )

                expected_total = 0
                derived_total = 0
                derived_types = set()

                for group_id in group_ids:
                    qac_group = qac_by_id.get(
                        group_id
                    )

                    if not qac_group:
                        continue

                    group_count = int(
                        qac_group.get(
                            "occurrence_count"
                        )
                        or 0
                    )
                    expected_total += group_count

                    counts = (
                        qac_group.get(
                            "derived_nominal_counts"
                        )
                        or {}
                    )

                    for dtype, count in counts.items():
                        count_int = int(
                            count
                            or 0
                        )

                        if count_int > 0:
                            derived_total += count_int
                            derived_types.add(dtype)

                transparent_derived_nominal = (
                    expected_total > 0
                    and derived_total == expected_total
                    and len(derived_types) == 1
                    and next(iter(derived_types)) in {
                        "VERBAL_NOUN",
                        "ACTIVE_PARTICIPLE",
                        "PASSIVE_PARTICIPLE",
                    }
                )

            if transparent_derived_nominal:
                findings.append(
                    finding(
                        "warning",
                        "DERIVED_NOMINAL_PARENT_LEXICAL_SUPPORT",
                        (
                            f"{target_id}: no Lane source_unit is "
                            "linked directly to this Quranic derived "
                            "nominal sense, but QAC identifies the "
                            "entire public form as a transparent "
                            f"{next(iter(derived_types))}; parent-verb "
                            "lexical support is therefore acceptable "
                            "for this pass."
                        ),
                    )
                )

            else:
                findings.append(
                    finding(
                        "error",
                        "QURAN_SENSE_LANE_SUPPORT_NOT_LINKED",
                        (
                            f"{target_id}: Quranic sense relies on Lane "
                            "for direct lexical support, but no "
                            "source_unit from its cited Lane entry is "
                            "linked to that sense in "
                            "lane_unit_coverage."
                        ),
                    )
                )

        for lane_ref in lane_refs:
            if lane_ref not in linked_entry_refs:
                findings.append(
                    finding(
                        "warning",
                        "LANE_SOURCE_REF_NOT_LINKED_BY_UNIT_LEDGER",
                        (
                            f"{target_id}: cites {lane_ref}, but no "
                            "source_unit from that Lane entry targets "
                            "this sense/meaning in lane_unit_coverage."
                        ),
                    )
                )

    # An ambiguous Lane unit should not disappear silently.
    ambiguous_rows = [
        row
        for row in coverage_rows
        if row.get(
            "status"
        ) == "AMBIGUOUS"
    ]

    if (
        ambiguous_rows
        and not (
            artifact.get(
                "unassigned_or_ambiguous_evidence"
            )
            or []
        )
    ):
        findings.append(
            finding(
                "error",
                "AMBIGUOUS_LANE_UNITS_NOT_PRESERVED",
                (
                    "lane_unit_coverage contains AMBIGUOUS units but "
                    "unassigned_or_ambiguous_evidence is empty."
                ),
            )
        )

    root_idea_refs = set(
        (
            artifact.get(
                "root_idea"
            )
            or {}
        ).get(
            "source_refs"
        )
        or []
    )

    bad_root_refs = sorted(
        root_idea_refs
        - refs[
            "all"
        ]
    )

    if bad_root_refs:
        findings.append(
            finding(
                "error",
                "UNKNOWN_ROOT_IDEA_SOURCE_REF",
                (
                    "root_idea contains unknown source_refs "
                    f"{bad_root_refs}"
                ),
            )
        )

    for index, meaning in enumerate(
        artifact.get(
            "other_classical_meanings"
        )
        or [],
        start=1,
    ):
        source_refs = set(
            meaning.get(
                "source_refs"
            )
            or []
        )

        bad_refs = sorted(
            source_refs
            - refs[
                "all"
            ]
        )

        if bad_refs:
            findings.append(
                finding(
                    "error",
                    "UNKNOWN_CLASSICAL_SOURCE_REF",
                    (
                        "other_classical_meanings"
                        f"[{index}] has unknown refs {bad_refs}"
                    ),
                )
            )

        if not source_refs:
            findings.append(
                finding(
                    "error",
                    "CLASSICAL_MEANING_WITHOUT_SOURCE",
                    (
                        "other_classical_meanings"
                        f"[{index}] has no source_refs."
                    ),
                )
            )

    return findings


def summarize_findings(
    findings: list[dict],
) -> tuple[list[dict], list[dict]]:
    errors = [
        item
        for item in findings
        if item.get(
            "severity"
        ) == "error"
    ]

    warnings = [
        item
        for item in findings
        if item.get(
            "severity"
        ) == "warning"
    ]

    return errors, warnings


def append_validation_log(
    *,
    root: str,
    run_label: str,
    response_id: Optional[str],
    source: str,
    findings: list[dict],
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    errors, warnings = summarize_findings(
        findings
    )

    record = {
        "timestamp_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "root":
            root,

        "run_label":
            run_label,

        "response_id":
            response_id,

        "source":
            source,

        "status":
            (
                "failed"
                if errors
                else (
                    "passed_with_warnings"
                    if warnings
                    else "passed"
                )
            ),

        "error_count":
            len(
                errors
            ),

        "warning_count":
            len(
                warnings
            ),

        "findings":
            findings,
    }

    with VALIDATION_LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as handle:
        # Multiple batch workers may finish validation at the same time.
        # Serialize this one shared append without changing any per-root
        # artifact/report behavior.
        fcntl.flock(
            handle.fileno(),
            fcntl.LOCK_EX,
        )

        try:
            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
            handle.flush()

        finally:
            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_UN,
            )



def extract_parse_failure_output_text(
    exc: Exception,
) -> str:
    """
    Best-effort recovery of the raw model text from a local Pydantic
    ValidationError raised by responses.parse().

    When the server returned text but the SDK could not parse it as the
    requested structured object, Pydantic usually retains that raw text in
    the validation error's `input` field. Preserve it so a paid response is
    never silently lost merely because local parsing failed.
    """
    errors_method = getattr(
        exc,
        "errors",
        None,
    )

    if not callable(
        errors_method
    ):
        return ""

    try:
        errors = errors_method(
            include_input=True
        )

    except TypeError:
        try:
            errors = errors_method()

        except Exception:
            return ""

    except Exception:
        return ""

    for item in (
        errors
        or []
    ):
        value = (
            item.get(
                "input"
            )
            if isinstance(
                item,
                dict,
            )
            else None
        )

        if isinstance(
            value,
            str,
        ):
            return value

    return ""


def make_api_response_summary(
    response: Any,
) -> dict:
    """
    Store the useful API metadata without serializing the entire generic
    Responses SDK object. This avoids noisy Pydantic serializer warnings and
    avoids storing large encrypted reasoning blobs that are not needed for
    this project.
    """
    return {
        "id":
            getattr(
                response,
                "id",
                None,
            ),

        "model":
            getattr(
                response,
                "model",
                None,
            ),

        "status":
            getattr(
                response,
                "status",
                None,
            ),

        "error":
            getattr(
                response,
                "error",
                None,
            ),

        "incomplete_details":
            getattr(
                response,
                "incomplete_details",
                None,
            ),

        "output_text":
            getattr(
                response,
                "output_text",
                "",
            ),
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one final root-dictionary synthesis call. "
            "No automatic retries."
        )
    )

    parser.add_argument(
        "--root",
        required=False,
        help=(
            "Canonical QAC root id, e.g. rHm. Required for a new API "
            "call; optional with --revalidate-attempt."
        ),
    )

    parser.add_argument(
        "--revalidate-attempt",
        type=Path,
        default=None,
        help=(
            "Revalidate/promote an already-saved attempt with the current "
            "validator. Makes NO API call."
        ),
    )

    parser.add_argument(
        "--packets",
        type=Path,
        default=None,
        help=(
            "Optional synthesis packet file. Default: pilot v3, "
            "falling back to sample v3/v2/v1."
        ),
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )

    parser.add_argument(
        "--reasoning",
        choices=[
            "none",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ],
        default=DEFAULT_REASONING,
    )

    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )

    parser.add_argument(
        "--request-timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
    )

    parser.add_argument(
        "--run-label",
        default="luna-high-unit-ledger-v11",
    )

    parser.add_argument(
        "--confirm-api",
        action="store_true",
        help=(
            "Required to make the paid API call. Without this flag, "
            "the script only prints a dry-run estimate."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing successful artifact for this run/root.",
    )

    args = parser.parse_args()

    if (
        args.root is None
        and args.revalidate_attempt is None
    ):
        parser.error(
            "--root is required unless --revalidate-attempt is used."
        )

    packet_file = locate_packet_file(
        args.packets
    )

    payload = load_json(
        packet_file
    )

    packets = packet_lookup(
        payload
    )

    if args.revalidate_attempt is not None:
        saved_attempt = load_json(
            args.revalidate_attempt
        )

        attempt_root = (
            saved_attempt.get(
                "metadata",
                {}
            ).get(
                "root"
            )
            or (
                saved_attempt.get(
                    "parsed_artifact"
                )
                or {}
            ).get(
                "root"
            )
        )

        if args.root is None:
            args.root = attempt_root

        elif (
            attempt_root
            and args.root != attempt_root
        ):
            raise ValueError(
                "Root supplied on command line does not match "
                "saved attempt root."
            )

    if args.root not in packets:
        raise ValueError(
            f"Root {args.root!r} not found in {packet_file}"
        )

    packet = packets[
        args.root
    ]

    estimated_input = rough_input_tokens(
        packet
    )

    max_estimated_cost = estimated_luna_cost(
        model=args.model,
        input_tokens=estimated_input,
        output_tokens=args.max_output_tokens,
    )

    print()
    print("=" * 72)
    print("FINAL ROOT DICTIONARY SYNTHESIS — ONE CALL, NO AUTO-RETRY")
    print("=" * 72)
    print(f"Root:        {args.root}")
    print(f"Packet:      {packet_file}")
    print(f"Model:       {args.model}")
    print(f"Prompt:      v{PROMPT_VERSION}")
    print(f"Reasoning:   {args.reasoning}")
    print(
        f"Packet size: {compact_chars(packet):,} chars "
        f"(~{estimated_input:,} rough input tokens)"
    )
    print(
        f"Max output:  {args.max_output_tokens:,} tokens"
    )

    if max_estimated_cost is not None:
        input_only = estimated_luna_cost(
            model=args.model,
            input_tokens=estimated_input,
            output_tokens=0,
        )

        print(
            f"Approx input cost: ${input_only:.4f}"
        )
        print(
            "Worst-case text-token cost at max_output_tokens: "
            f"${max_estimated_cost:.4f}"
        )

    if args.revalidate_attempt is not None:
        saved_attempt = load_json(
            args.revalidate_attempt
        )

        parsed_dict = saved_attempt.get(
            "parsed_artifact"
        )

        if not isinstance(
            parsed_dict,
            dict,
        ):
            raise RuntimeError(
                "Saved attempt has no parsed_artifact to revalidate."
            )

        repair_findings = apply_deterministic_bookkeeping_repairs(
            parsed_dict,
            packet=packet,
        )

        findings = (
            repair_findings
            + validate_artifact(
                packet=packet,
                artifact=parsed_dict,
            )
        )

        errors, warnings = summarize_findings(
            findings
        )

        response_id = (
            saved_attempt.get(
                "metadata",
                {}
            ).get(
                "response_id"
            )
        )

        append_validation_log(
            root=args.root,
            run_label=args.run_label,
            response_id=response_id,
            source=(
                "revalidate:"
                + str(
                    args.revalidate_attempt
                )
            ),
            findings=findings,
        )

        status = (
            "failed"
            if errors
            else (
                "passed_with_warnings"
                if warnings
                else "passed"
            )
        )

        saved_attempt[
            "validation_status"
        ] = status

        saved_attempt[
            "validation_findings"
        ] = findings

        # Retain backwards-readable simple errors list too.
        saved_attempt[
            "validation_errors"
        ] = [
            item[
                "message"
            ]
            for item in errors
        ]

        saved_attempt[
            "validation_warnings"
        ] = [
            item[
                "message"
            ]
            for item in warnings
        ]

        write_json(
            args.revalidate_attempt,
            saved_attempt,
        )

        print()
        print(
            "REVALIDATION COMPLETE — NO API CALL MADE"
        )
        print(
            f"Errors:   {len(errors)}"
        )
        print(
            f"Warnings: {len(warnings)}"
        )

        for item in findings:
            print(
                f"  [{item['severity'].upper()}] "
                f"{item['code']}: {item['message']}"
            )

        if errors:
            print()
            print(
                "Artifact was NOT promoted because hard errors remain."
            )
            return

        artifact_path = (
            OUTPUT_DIR
            / (
                "root_dictionary_artifact_v11"
                f"__{args.run_label}"
                f"__{args.root}.json"
            )
        )

        report_path = (
            OUTPUT_DIR
            / (
                "root_dictionary_artifact_report_v11"
                f"__{args.run_label}"
                f"__{args.root}.json"
            )
        )

        write_json(
            artifact_path,
            parsed_dict,
        )

        report = {
            "metadata": {
                "root":
                    args.root,

                "run_label":
                    args.run_label,

                "response_id":
                    response_id,

                "validation_source":
                    "saved_attempt_revalidation",
            },

            "hard_checks": {
                "passed":
                    True,

                "error_count":
                    0,

                "warning_count":
                    len(
                        warnings
                    ),
            },

            "validation_findings":
                findings,

            "artifact_file":
                str(
                    artifact_path.relative_to(
                        SCRIPT_DIR
                    )
                ),

            "attempt_file":
                str(
                    args.revalidate_attempt
                ),
        }

        write_json(
            report_path,
            report,
        )

        print()
        print(
            "Artifact promoted from saved response."
        )
        print(
            f"Artifact: {artifact_path}"
        )
        print(
            f"Report:   {report_path}"
        )
        print(
            f"Audit log: {VALIDATION_LOG_FILE}"
        )
        return

    if not args.confirm_api:
        print()
        print(
            "DRY RUN ONLY — no API call made."
        )
        print(
            "Add --confirm-api when you are ready to make exactly one call."
        )
        return

    attempts_dir = (
        OUTPUT_DIR
        / "root-dictionary-synthesis-attempts"
        / args.run_label
    )

    attempts_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact_path = (
        OUTPUT_DIR
        / (
            "root_dictionary_artifact_v11"
            f"__{args.run_label}"
            f"__{args.root}.json"
        )
    )

    report_path = (
        OUTPUT_DIR
        / (
            "root_dictionary_artifact_report_v11"
            f"__{args.run_label}"
            f"__{args.root}.json"
        )
    )

    attempt_path = (
        attempts_dir
        / f"{args.root}__attempt-1.json"
    )

    if (
        artifact_path.exists()
        and not args.force
    ):
        raise FileExistsError(
            f"Successful artifact already exists:\n{artifact_path}\n"
            "Use --force only if you intentionally want another paid call."
        )

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(
            "OpenAI Python SDK is required. Install/update with:\n"
            "python3 -m pip install -U openai pydantic"
        ) from exc

    client = OpenAI(
        timeout=args.request_timeout,
        max_retries=0,
    )

    user_prompt = (
        "Synthesize the final dictionary artifact for this root.\n\n"
        "EVIDENCE PACKET JSON:\n"
        + json.dumps(
            packet,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    print()
    print("Calling API once...")

    started = time.monotonic()

    try:
        response = client.responses.parse(
            model=args.model,
            input=[
                {
                    "role":
                        "system",

                    "content":
                        SYSTEM_PROMPT,
                },
                {
                    "role":
                        "user",

                    "content":
                        user_prompt,
                },
            ],
            text_format=RootDictionaryArtifact,
            reasoning={
                "effort":
                    args.reasoning,
            },
            max_output_tokens=
                args.max_output_tokens,
        )

    except Exception as exc:
        elapsed = (
            time.monotonic()
            - started
        )

        recovered_text = extract_parse_failure_output_text(
            exc
        )

        stripped = recovered_text.rstrip()

        likely_incomplete_json = bool(
            recovered_text
            and not (
                stripped.endswith(
                    "}"
                )
                or stripped.endswith(
                    "]"
                )
            )
        )

        parse_failure_record = {
            "metadata": {
                "root":
                    args.root,

                "run_label":
                    args.run_label,

                "model":
                    args.model,

                "prompt_version":
                    PROMPT_VERSION,

                "reasoning":
                    args.reasoning,

                "max_output_tokens":
                    args.max_output_tokens,

                "elapsed_seconds":
                    elapsed,

                "response_id":
                    None,

                "usage":
                    None,
            },

            "parsed_artifact":
                None,

            "deterministic_repairs":
                [],

            "api_response": {
                "id":
                    None,

                "model":
                    args.model,

                "status":
                    "local_parse_failed",

                "error": {
                    "type":
                        type(
                            exc
                        ).__name__,

                    "message":
                        str(
                            exc
                        ),
                },

                "incomplete_details":
                    None,

                "output_text":
                    recovered_text,
            },

            "parse_failure": {
                "raw_output_recovered":
                    bool(
                        recovered_text
                    ),

                "raw_output_char_count":
                    len(
                        recovered_text
                    ),

                "likely_incomplete_json":
                    likely_incomplete_json,

                "note":
                    (
                        "The API request returned far enough for the "
                        "SDK's local structured-output parser to run, "
                        "but local parsing failed. No automatic retry "
                        "was made."
                    ),
            },

            "validation_status":
                "parse_failed",

            "validation_errors": [
                (
                    "Structured output could not be parsed locally; "
                    "see parse_failure and api_response.output_text."
                )
            ],

            "validation_findings":
                [],
        }

        write_json(
            attempt_path,
            parse_failure_record,
        )

        print()
        print(
            "PAID CALL RETURNED, BUT LOCAL STRUCTURED PARSING FAILED."
        )
        print(
            "No automatic retry was made."
        )
        print(
            f"Elapsed: {elapsed:.1f}s"
        )
        print(
            "Recovered raw output: "
            f"{len(recovered_text):,} chars"
        )

        if likely_incomplete_json:
            print(
                "The recovered text appears incomplete/truncated."
            )

        print(
            f"Failure record saved: {attempt_path}"
        )

        raise SystemExit(
            2
        )

    elapsed = (
        time.monotonic()
        - started
    )

    usage = usage_to_dict(
        response
    )

    raw_response = make_api_response_summary(
        response
    )


    parsed = getattr(
        response,
        "output_parsed",
        None,
    )

    parsed_dict = (
        model_dump(
            parsed
        )
        if parsed is not None
        else None
    )

    # Save the paid response BEFORE semantic validation.
    attempt_record = {
        "metadata": {
            "root":
                args.root,

            "run_label":
                args.run_label,

            "model":
                args.model,

            "prompt_version":
                PROMPT_VERSION,

            "reasoning":
                args.reasoning,

            "max_output_tokens":
                args.max_output_tokens,

            "response_id":
                getattr(
                    response,
                    "id",
                    None,
                ),

            "elapsed_seconds":
                elapsed,

            "usage":
                usage,
        },

        "parsed_artifact":
            parsed_dict,

        "deterministic_repairs":
            [],

        "api_response":
            raw_response,

        "validation_status":
            "not_yet_validated",

        "validation_errors":
            [],
    }

    write_json(
        attempt_path,
        attempt_record,
    )

    if parsed_dict is None:
        attempt_record[
            "validation_status"
        ] = "failed"

        attempt_record[
            "validation_errors"
        ] = [
            "API response did not contain parsed structured output."
        ]

        write_json(
            attempt_path,
            attempt_record,
        )

        raise RuntimeError(
            "API response did not contain parsed structured output. "
            f"Paid response saved at:\n{attempt_path}"
        )

    repair_findings = apply_deterministic_bookkeeping_repairs(
        parsed_dict,
        packet=packet,
    )

    findings = (
        repair_findings
        + validate_artifact(
            packet=packet,
            artifact=parsed_dict,
        )
    )

    errors, warnings = summarize_findings(
        findings
    )

    attempt_record[
        "deterministic_repairs"
    ] = repair_findings

    attempt_record[
        "parsed_artifact"
    ] = parsed_dict

    attempt_record[
        "validation_status"
    ] = (
        "failed"
        if errors
        else (
            "passed_with_warnings"
            if warnings
            else "passed"
        )
    )

    attempt_record[
        "validation_findings"
    ] = findings

    attempt_record[
        "validation_errors"
    ] = [
        item[
            "message"
        ]
        for item in errors
    ]

    attempt_record[
        "validation_warnings"
    ] = [
        item[
            "message"
        ]
        for item in warnings
    ]

    write_json(
        attempt_path,
        attempt_record,
    )

    append_validation_log(
        root=args.root,
        run_label=args.run_label,
        response_id=getattr(
            response,
            "id",
            None,
        ),
        source="api_call",
        findings=findings,
    )

    input_tokens = int(
        usage.get(
            "input_tokens"
        )
        or 0
    )

    output_tokens = int(
        usage.get(
            "output_tokens"
        )
        or 0
    )

    actual_cost = estimated_luna_cost(
        model=args.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    print()
    print(
        f"Elapsed:       {elapsed:.1f}s"
    )
    print(
        f"Input tokens:  {input_tokens:,}"
    )
    print(
        f"Output tokens: {output_tokens:,}"
    )

    details = (
        usage.get(
            "output_tokens_details"
        )
        or {}
    )

    reasoning_tokens = details.get(
        "reasoning_tokens"
    )

    if reasoning_tokens is not None:
        print(
            f"Reasoning:     {int(reasoning_tokens):,} tokens"
        )

    if actual_cost is not None:
        print(
            f"Estimated cost: ${actual_cost:.4f}"
        )

    print(
        f"Paid response saved: {attempt_path}"
    )

    if errors:
        print()
        print(
            f"VALIDATION FAILED — {len(errors)} hard error(s), "
            f"{len(warnings)} warning(s). No retry was made."
        )

        for item in findings:
            print(
                f"  [{item['severity'].upper()}] "
                f"{item['code']}: {item['message']}"
            )

        print()
        print(
            "Review/fix the artifact or prompt before spending on "
            "another call."
        )
        print(
            f"Validation audit log: {VALIDATION_LOG_FILE}"
        )

        return

    if warnings:
        print()
        print(
            f"VALIDATION PASSED WITH {len(warnings)} WARNING(S)."
        )

        for item in warnings:
            print(
                f"  [WARNING] {item['code']}: {item['message']}"
            )

    write_json(
        artifact_path,
        parsed_dict,
    )

    report = {
        "metadata": {
            "root":
                args.root,

            "run_label":
                args.run_label,

            "model":
                args.model,

            "prompt_version":
                PROMPT_VERSION,

            "reasoning":
                args.reasoning,

            "response_id":
                getattr(
                    response,
                    "id",
                    None,
                ),
        },

        "usage":
            usage,

        "elapsed_seconds":
            elapsed,

        "estimated_cost_usd":
            actual_cost,

        "hard_checks": {
            "passed":
                True,

            "error_count":
                0,

            "warning_count":
                len(
                    warnings
                ),
        },

        "validation_findings":
            findings,

        "artifact_file":
            str(
                artifact_path.relative_to(
                    SCRIPT_DIR
                )
            ),

        "attempt_file":
            str(
                attempt_path.relative_to(
                    SCRIPT_DIR
                )
            ),
    }

    write_json(
        report_path,
        report,
    )

    print()
    print(
        (
            "VALIDATION PASSED WITH WARNINGS."
            if warnings
            else "VALIDATION PASSED."
        )
    )
    print(
        f"Artifact: {artifact_path}"
    )
    print(
        f"Report:   {report_path}"
    )


if __name__ == "__main__":
    main()
