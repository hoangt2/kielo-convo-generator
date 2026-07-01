#!/usr/bin/env python3
"""
Series compiler — the bridge between the series definitions and the existing pipeline.

Reads series/cast.json + series/episodes.json, resolves each episode's character ids
to the canonical cast (voice_id, tone, appearance, speech style), and writes a standard
`ideas.json` that the rest of the pipeline (generate_scripts.py onward) already understands.

This is what keeps the cast and voices CONSISTENT: every episode pulls the same voice_id
and personality from cast.json, so Sari always sounds like Sari.

Usage:
    python series_compile.py                 # list all episodes
    python series_compile.py list            # list all episodes
    python series_compile.py 1               # compile episode 1 -> ideas.json
    python series_compile.py 1 4 6           # compile several episodes -> ideas.json
    python series_compile.py all             # compile every episode -> ideas.json

Then run the normal pipeline, SKIPPING step 1 (idea generation):
    python generate_scripts.py
    python check_finnish_grammar.py
    ... etc.

Note on CEFR: generate_scripts.py reads ONE language level from ideas.json metadata.
For per-episode accuracy, compile a single episode at a time. When compiling several,
the series default level is used (a per-episode level is still recorded on each idea).
"""

import json
import sys
from pathlib import Path

import series_paths

BASE = Path(__file__).parent
IDEAS_OUT = BASE / "ideas.json"


def load_json(path):
    if not path.exists():
        sys.exit(f"❌ Not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_character(char_ref, cast):
    """A character entry in an episode is a cast id (str) or an inline dict."""
    if isinstance(char_ref, dict):
        return char_ref
    char = cast["characters"].get(char_ref)
    if not char:
        sys.exit(f"❌ Unknown character id '{char_ref}' (not in cast.json).")
    return char


def build_idea(episode, cast):
    """Turn one episode definition into a pipeline `idea` object."""
    chars = [resolve_character(ref, cast) for ref in episode["characters"]]

    # Characters in the shape generate_scripts.py / generate_illustrations.py expect.
    idea_characters = [
        {
            "id": ref if isinstance(ref, str) else c.get("name"),
            "name": c["name"],
            "gender": c.get("gender", "unknown"),
            "age": c.get("age", "Adult"),
            "default_tone": c.get("default_tone", "neutral"),
            "voice_id": c.get("voice_id", "REPLACE_WITH_ELEVENLABS_VOICE_ID"),
            "role": c.get("role", ""),
            "reference_image": c.get("reference_image", ""),
        }
        for ref, c in zip(episode["characters"], chars)
    ]

    # Fold register, per-character speech style and target phrases into the description,
    # so the existing script-generation prompt honours them without code changes.
    extra = []
    if episode.get("key_phrases"):
        extra.append(
            "Teaching ideas (OPTIONAL — these are example phrases for the lesson, NOT a checklist). "
            "A logical, natural, engaging conversation comes FIRST; only use the few of these that "
            "fit organically, adapt them, and skip the rest. Never sacrifice coherence to include a "
            "phrase: " + "; ".join(episode["key_phrases"])
        )
    styles = [f"- {c['name']}: {c.get('speech_style', '')}".rstrip() for c in chars if c.get("speech_style")]
    if styles:
        extra.append("Character speech styles:\n" + "\n".join(styles))
    if episode.get("notes"):
        extra.append("Register / direction: " + episode["notes"])

    description = episode["description"]
    if extra:
        description = description + "\n\n" + "\n\n".join(extra)

    return {
        "episode_id": episode["id"],
        "track": episode.get("track", ""),
        "title": episode["title"],
        "title_en": episode.get("title_en", ""),
        "description": description,
        "ambient_setting": episode.get("ambient_setting", ""),
        "language_level": episode.get("language_level", ""),
        "characters": idea_characters,
    }


def list_episodes(episodes_data):
    series = episodes_data.get("series", {})
    print(f"\n📺 {series.get('title', 'Series')} — {len(episodes_data['episodes'])} episodes\n")
    track = None
    for ep in episodes_data["episodes"]:
        if ep.get("track") != track:
            track = ep.get("track")
            print(f"  ── {track} ──")
        cast_list = ", ".join(
            c if isinstance(c, str) else c.get("name", "?") for c in ep["characters"]
        )
        print(f"  {ep['id']:>2}. {ep['title']}  ({ep.get('title_en','')})")
        print(f"      [{ep.get('language_level','')}] {cast_list}")
    print("\n  Compile with:  python series_compile.py <id> [<id> ...]   |   all\n")


def main():
    slug, args = series_paths.parse_series_arg(sys.argv[1:])
    paths = series_paths.resolve(slug)
    series_paths.announce(paths.slug)
    cast = load_json(paths.cast)
    episodes_data = load_json(paths.episodes)
    episodes = {ep["id"]: ep for ep in episodes_data["episodes"]}
    series = episodes_data.get("series", {})

    if not args or args[0].lower() == "list":
        list_episodes(episodes_data)
        return

    if args[0].lower() == "all":
        selected = list(episodes.values())
    else:
        selected = []
        for a in args:
            if not a.isdigit() or int(a) not in episodes:
                sys.exit(f"❌ '{a}' is not a valid episode id. Run `python series_compile.py list`.")
            selected.append(episodes[int(a)])

    ideas = [build_idea(ep, cast) for ep in selected]

    # One shared level for the run (single episode = that episode's level).
    if len(selected) == 1 and selected[0].get("language_level"):
        level = selected[0]["language_level"]
    else:
        level = series.get("default_language_level", "A1")

    out = {
        "metadata": {
            "language": series.get("language", "Finnish"),
            "tone": "Mixed (see per-episode direction)",
            "length": series.get("default_length", "Short"),
            "language_level": level,
            "series": series.get("title", ""),
        },
        "ideas": ideas,
    }

    with open(IDEAS_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    titles = ", ".join(f"#{ep['id']} {ep['title']}" for ep in selected)
    print(f"✅ Compiled {len(ideas)} episode(s) -> {IDEAS_OUT.name}  (level: {level})")
    print(f"   {titles}")
    print("\n   Next:  python generate_scripts.py   (then check_finnish_grammar.py, etc.)")
    print("   ⚠️  Skip generate_ideas_json.py — series_compile.py replaces it.\n")


if __name__ == "__main__":
    main()
