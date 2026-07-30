"""Language configuration for the conversation generator pipeline.

Single source of truth for language-specific settings. All scripts import from
here instead of hardcoding Finnish.

Usage:
    from language_config import get_language_config, get_iso_code

    cfg = get_language_config("Swedish")
    iso = get_iso_code("Swedish")  # "sv"
"""

# ──────────────────────────────────────────────────────────────────────────────
# Per-language configuration
# ──────────────────────────────────────────────────────────────────────────────

LANGUAGES = {
    "Finnish": {
        "iso": "fi",
        "spoken_label": "spoken Finnish (puhekieli)",
        "formal_label": "formal written Finnish (kirjakieli)",
        "spoken_features": (
            "Colloquial pronouns: 'mä/mun/mua' instead of 'minä/minun/minua', "
            "'sä/sun/sua' instead of 'sinä/sinun/sinua'.\n"
            "Spoken contractions: 'oon' (olen), 'oot' (olet), 'ei oo' (ei ole), "
            "'meen' (menen), 'tuun' (tulen).\n"
            "Dropped endings: 'täs' (tässä), 'siel' (siellä), 'mis' (missä).\n"
            "Natural filler words and interjections."
        ),
        "casual_particles": "joo, nii, tota, niinku, eiku, no, hei",
        "generic_address": "hei, anteeks, moi",
        "learner_style": "Careful Minä/Sinä, asks for clarification.",
        "native_style": "Natural spoken Finnish (puhekieli) with Mä/Sä and contractions.",
    },
    "Swedish": {
        "iso": "sv",
        "spoken_label": "spoken Swedish (talsvenska)",
        "formal_label": "formal written Swedish (skriftsvenska)",
        "spoken_features": (
            "Natural spoken forms: 'ja' for 'jag' in fast speech, "
            "'dom' instead of 'de/dem'.\n"
            "Spoken contractions: 'nåt' (något), 'nån' (någon), "
            "'int' (inte in some dialects).\n"
            "Natural filler words and interjections."
        ),
        "casual_particles": "ja, jo, alltså, liksom, typ, okej, va, asså",
        "generic_address": "hej, ursäkta, tjena",
        "learner_style": "Careful standard Swedish, asks for clarification.",
        "native_style": "Natural spoken Swedish (talsvenska).",
    },
    "Norwegian": {
        "iso": "no",
        "spoken_label": "spoken Norwegian (dagligtale)",
        "formal_label": "formal written Norwegian (bokmål/nynorsk)",
        "spoken_features": (
            "Natural spoken forms using common contractions.\n"
            "Natural filler words and interjections."
        ),
        "casual_particles": "ja, jo, altså, liksom, typ, okei",
        "generic_address": "hei, unnskyld",
        "learner_style": "Careful standard Norwegian, asks for clarification.",
        "native_style": "Natural spoken Norwegian (dagligtale).",
    },
    "German": {
        "iso": "de",
        "spoken_label": "spoken German (Umgangssprache)",
        "formal_label": "formal written German (Schriftdeutsch)",
        "spoken_features": (
            "Natural spoken forms: 'ne' for 'eine', 'hab' for 'habe', "
            "'is' for 'ist'.\n"
            "Contractions: 'geht's', 'gibt's', 'wie's'.\n"
            "Natural filler words and interjections."
        ),
        "casual_particles": "ja, na, also, halt, eben, mal, ne, ach",
        "generic_address": "hallo, entschuldigung, hey",
        "learner_style": "Careful standard German with Sie/du awareness.",
        "native_style": "Natural spoken German (Umgangssprache) with du.",
    },
    "French": {
        "iso": "fr",
        "spoken_label": "spoken French (français parlé)",
        "formal_label": "formal written French (français écrit)",
        "spoken_features": (
            "Dropping 'ne' in negation: 'je sais pas' instead of 'je ne sais pas'.\n"
            "Using 'on' instead of 'nous'.\n"
            "Natural liaison and elision.\n"
            "Natural filler words and interjections."
        ),
        "casual_particles": "ben, bah, euh, quoi, genre, du coup, enfin",
        "generic_address": "bonjour, excusez-moi, salut",
        "learner_style": "Careful standard French, vous/tu awareness.",
        "native_style": "Natural spoken French (français parlé) with tu.",
    },
    "Spanish": {
        "iso": "es",
        "spoken_label": "spoken Spanish (español coloquial)",
        "formal_label": "formal written Spanish (español estándar)",
        "spoken_features": (
            "Natural spoken contractions and elisions.\n"
            "Using 'tú/vos' forms in casual speech.\n"
            "Natural filler words and interjections."
        ),
        "casual_particles": "bueno, pues, o sea, vale, mira, oye",
        "generic_address": "hola, perdona, oye",
        "learner_style": "Careful standard Spanish, usted/tú awareness.",
        "native_style": "Natural spoken Spanish (coloquial) with tú.",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def get_language_config(language: str) -> dict:
    """Return the config dict for a language, or a sensible generic fallback."""
    if language in LANGUAGES:
        return LANGUAGES[language]
    # Generic fallback for unknown languages
    return {
        "iso": language[:2].lower(),
        "spoken_label": f"spoken {language}",
        "formal_label": f"formal written {language}",
        "spoken_features": "Natural spoken forms and contractions.",
        "casual_particles": "natural filler words and interjections",
        "generic_address": "common greetings",
        "learner_style": f"Careful standard {language}, asks for clarification.",
        "native_style": f"Natural spoken {language}.",
    }


def get_iso_code(language: str) -> str:
    """Return the ISO 639-1 code for a language name, or a best guess."""
    cfg = LANGUAGES.get(language)
    if cfg:
        return cfg["iso"]
    # Best-effort: first two letters lowercased
    return language[:2].lower()


def supported_languages() -> list:
    """Return list of languages with full configuration."""
    return sorted(LANGUAGES.keys())
