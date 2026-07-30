#!/usr/bin/env python3
"""
Scaffold a brand-new series under series/<slug>/.

Creates the folder, a cast.json (template or a copy of the default cast), an empty
episodes.json, and a characters/ directory — ready for series_plan.py.

Usage:
    python series_new.py doctor-visits "At the Doctor"
    python series_new.py doctor-visits "At the Doctor" --copy-cast   # reuse the default cast

After scaffolding:
    1. Edit series/<slug>/cast.json   (define characters + ElevenLabs voice_ids + appearance)
    2. python series_plan.py all path/to/curriculum.txt --series <slug>
    3. python generate_character_refs.py --series <slug>
    4. python series_run.py <episode_id> --series <slug>
"""

import json
import sys

import series_paths

STYLE_LOCK = (
    "A playful, modern doodle-style 2D illustration. The image must feature bold, thick, "
    "uniform black outlines with flat, naturalistic colors. Do not use gradients, 3D rendering, "
    "or complex shading. Characters should have friendly, exaggerated proportions with simple, "
    "clean features. Any inanimate objects in the scene must remain strictly as normal objects "
    "without any faces, smiles, or anthropomorphic details. Use a soft, cohesive pastel-leaning "
    "color palette. High quality vector-art style. No text, no labels, no words, no letters."
)


def cast_template(rel_characters, language="Finnish"):
    return {
        "_comment": "Character bible. Keep voice_id and appearance STABLE for consistency. "
                    "`id` keys are referenced by episodes and series_plan.py.",
        "style_lock": STYLE_LOCK,
        "characters": {
            "protagonist": {
                "name": "REPLACE_ME",
                "role": "Protagonist",
                "voice_id": "REPLACE_WITH_ELEVENLABS_VOICE_ID",
                "gender": "Female",
                "age": "Young Adult",
                "default_tone": "Eager, polite",
                "language_level": "A1",
                "speech_style": f"A1 learner. Careful standard {language}, asks for clarification.",
                "personality": "The learner the audience follows.",
                "appearance": "Describe height, build, hair, skin tone, clothing — be specific and stable.",
                "reference_image": f"{rel_characters}/protagonist.png",
            },
            "counterpart": {
                "name": "REPLACE_ME",
                "role": "Counterpart",
                "voice_id": "REPLACE_WITH_ELEVENLABS_VOICE_ID",
                "gender": "Male",
                "age": "Adult",
                "default_tone": "Friendly",
                "language_level": "Native",
                "speech_style": f"Natural spoken {language}.",
                "personality": "The other recurring speaker.",
                "appearance": "Describe appearance specifically and keep it stable.",
                "reference_image": f"{rel_characters}/counterpart.png",
            },
        },
    }


def main():
    slug, args = series_paths.parse_series_arg(sys.argv[1:])
    copy_cast = "--copy-cast" in args
    args = [a for a in args if a != "--copy-cast"]

    # Parse --language flag
    language = None
    if "--language" in args:
        idx = args.index("--language")
        if idx + 1 < len(args):
            language = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            sys.exit("❌ --language requires a value (e.g. --language Swedish)")

    # Allow either positional slug or --series slug
    if not slug:
        if not args:
            sys.exit('Usage: python series_new.py <slug> "<Title>" [--language Swedish] [--copy-cast]')
        slug = args.pop(0)
    title = args[0] if args else slug

    # Auto-detect language from slug/title if not explicitly set
    if not language:
        from language_config import supported_languages
        combined = f"{slug} {title}".lower()
        for lang in supported_languages():
            if lang.lower() in combined:
                language = lang
                print(f"🌐 Auto-detected language: {language} (from slug/title)")
                break
        if not language:
            language = "Finnish"
            print(f"🌐 No language detected — defaulting to {language}. Use --language to override.")

    paths = series_paths.resolve(slug)
    if paths.base.exists():
        sys.exit(f"❌ series/{slug}/ already exists — choose another slug or edit it directly.")

    paths.characters.mkdir(parents=True, exist_ok=True)

    # cast.json — template or a copy of the default series cast
    if copy_cast:
        default = series_paths.resolve(None)
        if not default.cast.exists():
            sys.exit("❌ --copy-cast requested but the default series/cast.json doesn't exist.")
        cast = json.loads(default.cast.read_text(encoding="utf-8"))
        # Repoint reference_image paths into the new series folder
        for cid, c in cast.get("characters", {}).items():
            c["reference_image"] = f"{paths.rel_characters}/{cid}.png"
        print(f"📋 Copied cast from default series ({len(cast.get('characters', {}))} characters).")
    else:
        cast = cast_template(paths.rel_characters, language)

    paths.cast.write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")

    # empty episodes.json
    episodes = {
        "_comment": "Run series_plan.py to populate from a curriculum, or add episodes by hand.",
        "series": {"title": title, "language": language,
                   "default_language_level": "A1", "default_length": "Short"},
        "episodes": [],
    }
    paths.episodes.write_text(json.dumps(episodes, ensure_ascii=False, indent=2), encoding="utf-8")

    # curriculum.txt template
    curriculum_template = f"""{title}

Chapter 1 — CHAPTER_TITLE
Focus: key grammar or vocabulary themes for this chapter.
1. Lesson Title — Discovery
   One-line description of what the learner discovers in this lesson.
2. Lesson Title — Scenario
   One-line description of the real-life scenario the learner practises.
3. Lesson Title — Drill
   One-line description of the drill (repetitive practice) in this lesson.

Chapter 2 — CHAPTER_TITLE
Focus: key grammar or vocabulary themes for this chapter.
1. Lesson Title — Discovery
   One-line description of what the learner discovers in this lesson.
2. Lesson Title — Scenario
   One-line description of the real-life scenario the learner practises.
3. Lesson Title — Mixed
   One-line description combining multiple skills from this chapter.
"""
    if not paths.curriculum_txt.exists():
        paths.curriculum_txt.write_text(curriculum_template, encoding="utf-8")

    # Make the new series the active one so following commands target it automatically.
    series_paths.set_active(slug)

    print(f"✅ Created series/{slug}/  (cast.json, episodes.json, curriculum.txt, characters/)")
    print(f"⭐ This is now the ACTIVE series — other commands target it unless you pass --series.")
    print("\nNext:")
    print(f"  1. Edit series/{slug}/curriculum.txt — define chapters and lessons")
    if not copy_cast:
        print(f"  2. Edit series/{slug}/cast.json — define characters (or run: python generate_cast.py)")
    print(f"  3. python series_plan.py all curriculum.txt")
    print(f"  4. python generate_character_refs.py")
    print(f"  5. python series_run.py <id>")
    print(f"\n  (switch series anytime: python series_use.py <slug> | default)")


if __name__ == "__main__":
    main()
