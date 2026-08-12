#!/usr/bin/env python3
"""
AI-generate a cast for a series, fitting its curriculum/theme.

Designs a learner protagonist plus a few recurring native-Finnish-speaking characters suited to
the series' scenarios, with personalities, speech styles (register), and distinct appearances.
Voice IDs are assigned from the project's existing ElevenLabs voice pool (matched by gender/age),
so the cast is immediately usable — no placeholders to fill in.

Operates on the ACTIVE series (or pass --series <slug>). Backs up any existing cast.json.

Usage:
    python generate_cast.py                       # cast for the active series
    python generate_cast.py --count 4             # how many characters (default 5)
    python generate_cast.py "neighbours and shopkeepers"   # extra theme hint
    python generate_cast.py --series doctor-visits

Next:  python series_plan.py all <curriculum.txt>   then   python generate_character_refs.py
"""

import json
import random
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

import series_paths
from generate_ideas_json import VOICES, normalize_age

load_dotenv()
MODEL = "gemini-2.5-pro"

DEFAULT_STYLE_LOCK = (
    "A playful, modern doodle-style 2D illustration. The image must feature bold, thick, uniform "
    "black outlines with flat, naturalistic colors. Do not use gradients, 3D rendering, or complex "
    "shading. Characters should have friendly, exaggerated proportions with simple, clean features. "
    "Any inanimate objects in the scene must remain strictly as normal objects without any faces, "
    "smiles, or anthropomorphic details. Use a soft, cohesive pastel-leaning color palette. "
    "High quality vector-art style. No text, no labels, no words, no letters."
)

try:
    client = genai.Client()
except Exception as e:
    print(f"❌ Error initializing Gemini client: {e}")
    client = None

CAST_SCHEMA = types.Schema(
    type="object",
    properties={
        "characters": types.Schema(
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "id": types.Schema(type="string", description="short lowercase id, e.g. 'aino' or 'shop_clerk'"),
                    "name": types.Schema(type="string", description="Finnish first name (or role name for incidental staff)"),
                    "role": types.Schema(type="string", description="their role in the series"),
                    "is_protagonist": types.Schema(type="boolean", description="true for exactly ONE character: the learner the audience follows"),
                    "gender": types.Schema(type="string", enum=["Male", "Female"]),
                    "age": types.Schema(type="string", description="Young Adult, Adult, or Senior"),
                    "default_tone": types.Schema(type="string"),
                    "speech_style": types.Schema(type="string", description="register & manner, e.g. spoken puhekieli Mä/Sä, or careful Minä/Sinä for the learner"),
                    "personality": types.Schema(type="string"),
                    "appearance": types.Schema(type="string", description="specific, stable visual description for illustration (build, hair, skin, clothing)"),
                },
                required=["id", "name", "role", "is_protagonist", "gender", "age",
                          "default_tone", "speech_style", "personality", "appearance"],
            ),
        ),
    },
    required=["characters"],
)


def slugify_id(s):
    out = "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "char"


def native_voice_pool(language):
    """Voices in the ElevenLabs account whose primary language IS `language`.

    Returns a list of {voice_id, gender, age, name} dicts, or [] if the key is
    missing, the API fails, or no native voices exist. This is what keeps a
    Swedish series from getting French/English voices: we prefer voices the
    provider actually tags as the target language (labels.language == iso).
    """
    try:
        import os
        from elevenlabs.client import ElevenLabs
        from language_config import get_iso_code
    except Exception:
        return []
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return []
    iso = get_iso_code(language)
    try:
        voices = ElevenLabs(api_key=api_key).voices.get_all().voices
    except Exception as e:
        print(f"   ⚠️  Could not fetch ElevenLabs voices ({e}); using generic pool.")
        return []
    pool = []
    for v in voices:
        labels = getattr(v, "labels", {}) or {}
        if (labels.get("language") or "").lower() != iso.lower():
            continue  # native only — a voice merely "verified" in the language isn't enough
        pool.append({
            "voice_id": v.voice_id,
            "gender": (labels.get("gender") or "").lower(),
            "age": labels.get("age", ""),
            "description": labels.get("description", "") or labels.get("use_case", ""),
            "name": getattr(v, "name", ""),
        })
    return pool


def voice_availability_text(native, language):
    """Human-readable summary of castable native voices, for the cast-design prompt.

    Lets the LLM design characters that FIT the voices we actually have (gender, rough
    age), instead of designing first and discovering there's no matching voice.
    """
    if not native:
        return ""
    lines = []
    for label, g in (("Male", "male"), ("Female", "female")):
        vs = [v for v in native if v.get("gender") == g]
        if not vs:
            continue
        items = []
        for v in vs:
            age = v.get("age") or "adult"
            desc = v.get("description") or ""
            items.append(f"{age}{' — ' + desc if desc else ''}")
        lines.append(f"- {label} voices ({len(vs)}): " + "; ".join(items))
    unknown = [v for v in native if v.get("gender") not in ("male", "female")]
    if unknown:
        lines.append(f"- Voices of unspecified gender ({len(unknown)})")
    if not lines:
        return ""
    return (
        f"\n\nCAST TO AVAILABLE VOICES — the series is voiced by these native {language} voices, "
        f"and each character is matched to ONE distinct voice. Design the cast so every character "
        f"fits one of these by gender and rough age:\n" + "\n".join(lines) +
        f"\nDo NOT create a character whose gender or age has no matching voice above (e.g. if there "
        f"is no elderly voice, do not make an elderly character), and do not create more characters "
        f"of a gender than there are voices for it. These are voice constraints only — never name a "
        f"character after a voice."
    )


def assign_voices(chars, language=None, native=None):
    """Pick a distinct voice_id per character, matched by gender/age.

    Prefers voices native to `language` (so a Swedish series gets Swedish voices);
    falls back to the generic project pool when no native voice fits a character.
    Pass `native` to reuse an already-fetched pool and avoid a second API call.
    """
    if native is None:
        native = native_voice_pool(language) if language else []
    if native:
        names = ", ".join(f"{p['name']}" for p in native)
        print(f"   🎙️  {len(native)} native {language} voice(s) available: {names}")
    else:
        print(f"   🎙️  No native {language} voices found; using generic voice pool.")

    used = set()
    for c in chars:
        gender = c.get("gender", "").lower()
        age = normalize_age(c.get("age", ""))
        # Preference order: native+gender+age → native+gender → any native →
        # generic+gender+age → generic+gender → any generic.
        tiers = [
            [v for v in native if v.get("gender") == gender and normalize_age(v.get("age", "")) == age],
            [v for v in native if v.get("gender") == gender],
            list(native),
            [v for v in VOICES if v.get("gender", "").lower() == gender and normalize_age(v.get("age", "")) == age],
            [v for v in VOICES if v.get("gender", "").lower() == gender],
            list(VOICES),
        ]
        chosen = None
        for tier in tiers:
            fresh = [v for v in tier if v["voice_id"] not in used]
            if fresh:
                chosen = random.choice(fresh)
                break
        if not chosen:  # all used up — allow reuse, preferring native
            chosen = random.choice(native or VOICES)
        used.add(chosen["voice_id"])
        c["voice_id"] = chosen["voice_id"]


def main():
    if not client:
        sys.exit("🛑 GEMINI_API_KEY missing or client init failed.")

    slug, args = series_paths.parse_series_arg(sys.argv[1:])
    paths = series_paths.resolve(slug)
    series_paths.announce(paths.slug)
    if not paths.base.exists():
        sys.exit(f"❌ Series folder not found: {paths.base}. Create it with series_new.py first.")

    # options — count=None means let the LLM decide based on curriculum
    count = None
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--count" and i + 1 < len(args):
            count = int(args[i + 1]); i += 2; continue
        if a.startswith("--count="):
            count = int(a.split("=", 1)[1]); i += 1; continue
        rest.append(a); i += 1
    theme_hint = " ".join(rest).strip()

    # series context
    title = paths.slug or "this series"
    level = "A1"
    language = "Finnish"
    if paths.episodes.exists():
        try:
            ep = json.loads(paths.episodes.read_text(encoding="utf-8"))
            title = ep.get("series", {}).get("title", title)
            level = ep.get("series", {}).get("default_language_level", level)
            language = ep.get("series", {}).get("language", language)
        except Exception:
            pass
    curriculum_excerpt = ""
    if paths.curriculum_txt.exists():
        curriculum_excerpt = paths.curriculum_txt.read_text(encoding="utf-8")[:4000]

    # preserve the series' style_lock if a cast.json already exists
    style_lock = DEFAULT_STYLE_LOCK
    if paths.cast.exists():
        try:
            style_lock = json.loads(paths.cast.read_text(encoding="utf-8")).get("style_lock", style_lock)
        except Exception:
            pass

    # Fetch the castable native voices ONCE, so the design step can shape characters to fit
    # them and assign_voices can reuse the same pool without a second API call.
    native = native_voice_pool(language)

    system = f"""You design a small recurring CAST for a {language}-learning conversation video series.
Return JSON only.

Rules:
- Exactly ONE character has is_protagonist=true: a sympathetic LEARNER of {language} (the audience
  surrogate) who speaks carefully and asks for help. The rest are native {language} speakers.
- Give the cast variety in age, gender and personality so many everyday scenes are castable.
- `speech_style` must describe register concretely (natural spoken {language} with casual forms
  vs. the learner's careful standard {language}), since it drives the dialogue.
- `appearance` must be specific and STABLE (build, hair, skin tone, typical clothing) so the same
  character can be drawn consistently every episode. Keep ids short and lowercase.{voice_availability_text(native, language)}"""

    if count:
        count_instruction = (
            f"Design exactly {count} characters that fit the scenarios in this curriculum:\n\n"
            f"{curriculum_excerpt or '(no curriculum provided — infer from the series title)'}\n\n"
            f"Return exactly {count} characters."
        )
    else:
        count_instruction = (
            f"Read the curriculum below and decide how many recurring characters are needed to "
            f"cover ALL the scenarios naturally (typically 4-8). Include roles that the lessons "
            f"actually require (e.g. a colleague for work scenes, a shopkeeper for shopping, "
            f"a friend for social scenes). Do NOT pad with characters that have no clear role "
            f"in any lesson.\n\n"
            f"{curriculum_excerpt or '(no curriculum provided — infer from the series title)'}\n\n"
            f"Return as many characters as the curriculum needs."
        )

    prompt = (
        f"Series: {title}\nTarget CEFR level: {level}\n"
        f"{'Extra theme hint: ' + theme_hint + chr(10) if theme_hint else ''}"
        f"{count_instruction}"
    )

    count_label = str(count) if count else "auto (based on curriculum)"
    print(f"🪄 Designing cast for '{title}' (level {level}, count: {count_label})...")
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=CAST_SCHEMA,
        temperature=0.8,
    )
    resp = client.models.generate_content(model=MODEL, contents=[prompt], config=config)
    chars = json.loads(resp.text).get("characters", [])
    if not chars:
        sys.exit("❌ Model returned no characters. Try again.")

    assign_voices(chars, language=language, native=native)

    # build cast.json
    characters = {}
    seen = set()
    protagonist_seen = False
    for c in chars:
        cid = slugify_id(c["id"])
        while cid in seen:
            cid += "_2"
        seen.add(cid)
        is_proto = bool(c.get("is_protagonist")) and not protagonist_seen
        if is_proto:
            protagonist_seen = True
        characters[cid] = {
            "name": c["name"],
            "role": c.get("role", ""),
            "voice_id": c["voice_id"],
            "gender": c.get("gender", ""),
            "age": c.get("age", "Adult"),
            "default_tone": c.get("default_tone", ""),
            "language_level": level if is_proto else "Native",
            "speech_style": c.get("speech_style", ""),
            "personality": c.get("personality", ""),
            "appearance": c.get("appearance", ""),
            "reference_image": f"{paths.rel_characters}/{cid}.png",
        }

    cast_out = {
        "_comment": "AI-generated cast. Keep voice_id and appearance STABLE for consistency. "
                    "`id` keys are referenced by episodes and series_plan.py.",
        "style_lock": style_lock,
        "characters": characters,
    }

    if paths.cast.exists():
        bak = paths.cast.with_suffix(".json.bak")
        paths.cast.replace(bak)
        print(f"💾 Backed up existing cast -> {bak.name}")
    paths.cast.write_text(json.dumps(cast_out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Wrote {len(characters)} characters -> {paths.cast}")
    for cid, c in characters.items():
        tag = " (protagonist)" if c["language_level"] == level else ""
        print(f"   • {cid}: {c['name']} — {c['role']}{tag}  [{c['gender']}, {c['age']}, voice {c['voice_id']}]")
    print("\nNext:")
    print("   python series_plan.py all " + (paths.curriculum_txt.as_posix() if paths.curriculum_txt.exists() else "<curriculum.txt>"))
    print("   python generate_character_refs.py")


if __name__ == "__main__":
    main()
