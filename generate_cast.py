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


def assign_voices(chars):
    """Pick a distinct voice_id per character from VOICES, matched by gender/age."""
    used = set()
    for c in chars:
        gender = c.get("gender", "").lower()
        age = normalize_age(c.get("age", ""))
        tiers = [
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
        if not chosen:  # all used up — allow reuse
            chosen = random.choice(VOICES)
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

    # options
    count = 5
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
    if paths.episodes.exists():
        try:
            ep = json.loads(paths.episodes.read_text(encoding="utf-8"))
            title = ep.get("series", {}).get("title", title)
            level = ep.get("series", {}).get("default_language_level", level)
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

    system = """You design a small recurring CAST for a Finnish-learning conversation video series.
Return JSON only.

Rules:
- Exactly ONE character has is_protagonist=true: a sympathetic LEARNER of Finnish (the audience
  surrogate) who speaks carefully and asks for help. The rest are native Finnish speakers.
- Give the cast variety in age, gender and personality so many everyday scenes are castable.
- `speech_style` must describe register concretely (spoken puhekieli with Mä/Sä and contractions,
  vs. the learner's careful Minä/Sinä), since it drives the dialogue.
- `appearance` must be specific and STABLE (build, hair, skin tone, typical clothing) so the same
  character can be drawn consistently every episode. Keep ids short and lowercase."""

    prompt = (
        f"Series: {title}\nTarget CEFR level: {level}\n"
        f"{'Extra theme hint: ' + theme_hint + chr(10) if theme_hint else ''}"
        f"Design {count} characters that fit the scenarios in this curriculum:\n\n"
        f"{curriculum_excerpt or '(no curriculum provided — infer from the series title)'}\n\n"
        f"Return exactly {count} characters."
    )

    print(f"🪄 Designing a cast of {count} for '{title}' (level {level})...")
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

    assign_voices(chars)

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
            "finnish_level": level if is_proto else "Native",
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
        tag = " (protagonist)" if c["finnish_level"] == level else ""
        print(f"   • {cid}: {c['name']} — {c['role']}{tag}  [{c['gender']}, {c['age']}, voice {c['voice_id']}]")
    print("\nNext:")
    print("   python series_plan.py all " + (paths.curriculum_txt.as_posix() if paths.curriculum_txt.exists() else "<curriculum.txt>"))
    print("   python generate_character_refs.py")


if __name__ == "__main__":
    main()
