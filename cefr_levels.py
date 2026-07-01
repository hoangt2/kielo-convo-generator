"""CEFR language-level definitions and prompt blocks for the convo generator.

Single source of truth for the A1–C2 levels. The level is detected as a CLI
argument, recorded in the ideas-file metadata, and injected into the
script-generation prompts so that vocabulary, grammar, sentence length and
delivery pace match the target level.
"""

import re

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

_LEVEL_RE = re.compile(r"^[ABC][12]$", re.IGNORECASE)


def is_cefr_level(arg: str) -> bool:
    """Return True if the argument looks like a CEFR level (A1–C2)."""
    return bool(_LEVEL_RE.match(arg.strip())) if arg else False


def normalize_level(arg: str) -> str:
    """Normalize a CEFR level argument to uppercase (e.g. 'a1' -> 'A1')."""
    return arg.strip().upper()


# Per-level guidance covering vocabulary, grammar, sentence length and pace.
LEVEL_GUIDELINES = {
    "A1": (
        "Vocabulary: ONLY the most common everyday words (greetings, small numbers, days, "
        "simple food, family, basic actions). No idioms, no rare or abstract words.\n"
        "Grammar: PRESENT TENSE ONLY. NO conditional — never use -isi- forms; say 'sopiiko' "
        "(not 'sopisiko'), 'voitko' (not 'voisitko'), 'haluan' (not 'haluaisin'). NO past tense. "
        "NO passive/impersonal except the set phrase 'mennään' (let's go); do NOT use forms like "
        "'otetaan' or 'saadaan puhuttua'. Keep cases basic (nominative/partitive and simple "
        "paikallissijat like -ssa/-lla).\n"
        "Sentences: very short — 3–6 words, ONE clause each. NO subordinate clauses (no 'että', "
        "'koska', 'jos', 'kun' clauses); use short separate sentences instead.\n"
        "Numbers & time: keep numbers small; tell time only on the hour or half past "
        "('kello kaksi', 'puoli kolme'). AVOID quarter-to/past, exact minutes, and years.\n"
        "Delivery & pace: speak SLOWLY and clearly. Keep utterances short, leave natural "
        "pauses between lines, and use a calm tone. Repeat key words when natural."
    ),
    "A2": (
        "Vocabulary: common everyday words for familiar topics (shopping, hobbies, daily "
        "routine, weather). A few very common idioms are okay.\n"
        "Grammar: present and basic past (imperfekti). NO conditional (no -isi- forms). Simple "
        "connectors allowed (ja, mutta, koska, sitten) and a single short subordinate clause is OK.\n"
        "Numbers & time: on the hour, half past, and quarter past/to are fine; keep years and "
        "large numbers rare and simple.\n"
        "Sentences: short to medium, mostly one or two clauses.\n"
        "Delivery & pace: still slow and clear, calm tone, with brief pauses between lines."
    ),
    "B1": (
        "Vocabulary: everyday plus opinions, plans and feelings. Common idioms are fine.\n"
        "Grammar: most tenses including conditional (-isi). Compound and simple complex "
        "sentences.\n"
        "Sentences: medium length, multiple clauses allowed.\n"
        "Delivery & pace: normal conversational pace."
    ),
    "B2": (
        "Vocabulary: broad, including abstract topics and many idioms.\n"
        "Grammar: varied and accurate structures, passive, participles, longer "
        "subordinate clauses.\n"
        "Sentences: varied length with natural complexity.\n"
        "Delivery & pace: near-natural, fluent pace."
    ),
    "C1": (
        "Vocabulary: rich, nuanced and idiomatic, including colloquial and figurative "
        "expressions.\n"
        "Grammar: full range of complex structures used naturally.\n"
        "Sentences: complex and varied, as a native speaker would use.\n"
        "Delivery & pace: fully natural pace."
    ),
    "C2": (
        "Vocabulary: sophisticated, precise and register-aware, including rare and "
        "stylistic expressions.\n"
        "Grammar: native-level command of all structures and nuance.\n"
        "Sentences: fully natural, sophisticated and varied.\n"
        "Delivery & pace: fully natural native pace."
    ),
}


def conversation_level_block(level: str) -> str:
    """Prompt section for the conversation (puhekieli) writer, or '' if no level."""
    if not level:
        return ""
    level = normalize_level(level)
    guidance = LEVEL_GUIDELINES.get(level)
    if not guidance:
        return ""
    return (
        f"\n        CEFR LANGUAGE LEVEL: {level}\n"
        f"        The dialogue MUST match this learner level. Follow these constraints strictly.\n"
        f"        IMPORTANT: when natural spoken Finnish would normally use a structure ABOVE this "
        f"level (e.g. conditional politeness like 'sopisiko', a 'että/koska' clause, or an exact "
        f"time like 'varttia vaille'), choose the simpler in-level form instead — even if it sounds "
        f"a little plainer or less polite. Staying within the level is MORE important than sounding "
        f"fully native. Keep it natural spoken Finnish (puhekieli: mä/sä/oon) within those limits.\n"
        f"        {guidance}\n"
    )


def podcast_level_block(level: str) -> str:
    """Prompt section for the podcast scriptwriter, or '' if no level.

    Podcasts are English-led; the level constrains the Finnish phrases that are
    taught and the overall pace/depth of the lesson.
    """
    if not level:
        return ""
    level = normalize_level(level)
    guidance = LEVEL_GUIDELINES.get(level)
    if not guidance:
        return ""
    return (
        f"\n        CEFR LANGUAGE LEVEL: {level}\n"
        f"        The Finnish phrases taught and the lesson depth MUST match this learner "
        f"level. Apply these constraints to the Finnish content (the English explanations "
        f"stay clear and simple):\n"
        f"        {guidance}\n"
    )
