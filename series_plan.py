#!/usr/bin/env python3
"""
Curriculum -> episodes planner.

Turns a curriculum (tracks -> levels -> chapters -> lessons) into series episodes that
reuse your fixed cast. One LESSON becomes one EPISODE.

It works in two stages so you can review/edit the middle artifact:

  1. parse  — normalize the (often messy) pasted curriculum text into structured
              `curriculum.json`. Robust to indentation/compact formatting because an
              LLM does the parsing.
  2. build  — GROUP each chapter's lessons into a few combined episodes (2-3 per chapter by
              default, not one-per-lesson) and write `episodes.json`. Each episode weaves several
              related lessons into one natural scene. The CEFR level comes from each level's tag.

Usage:
    # one-shot: parse the pasted curriculum text, then build episodes
    python series_plan.py all series/curriculum.txt
    python series_plan.py all path/to/curriculum.txt --series doctor-visits --append

    # or run the stages separately
    python series_plan.py parse series/curriculum.txt
    python series_plan.py build
    python series_plan.py build --append          # add to existing episodes.json

Options:
    --series <slug>     operate on series/<slug>/ instead of the default series/
    --append            append to existing episodes.json (else overwrite, backing up to .bak)
    --per-chapter 2-3   episodes per chapter: a range (LO-HI) or exact N. Default 2-3.
    --force             re-parse curriculum.txt even if curriculum.json already exists
                        (by default `all` reuses an existing curriculum.json and skips parsing)

Then build videos as usual, e.g.:  python series_run.py <episode_id>
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

import series_paths
from cefr_levels import normalize_level, is_cefr_level

load_dotenv()

MODEL = "gemini-2.5-pro"

# Canonical ambient categories (match presets/ambience for reuse).
AMBIENT_ENUM = [
    "office", "restaurant", "cafe", "home_kitchen", "street", "park", "bus",
    "train", "supermarket", "school", "gym", "library", "hospital", "airport",
    "beach", "quiet",
]

try:
    client = genai.Client()
except Exception as e:
    print(f"❌ Error initializing Gemini client: {e}")
    client = None


# --------------------------------------------------------------------------------------
# Stage 1: parse curriculum text -> structured curriculum.json
# --------------------------------------------------------------------------------------

CURRICULUM_SCHEMA = types.Schema(
    type="object",
    properties={
        "track": types.Schema(type="string"),
        "track_desc": types.Schema(type="string"),
        "levels": types.Schema(
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "name": types.Schema(type="string"),
                    "cefr": types.Schema(type="string", description="A1, A2, B1, B2, C1 or C2 if present, else empty"),
                    "desc": types.Schema(type="string"),
                    "chapters": types.Schema(
                        type="array",
                        items=types.Schema(
                            type="object",
                            properties={
                                "name": types.Schema(type="string"),
                                "desc": types.Schema(type="string"),
                                "lessons": types.Schema(
                                    type="array",
                                    items=types.Schema(
                                        type="object",
                                        properties={
                                            "title": types.Schema(type="string"),
                                            "desc": types.Schema(type="string"),
                                        },
                                        required=["title", "desc"],
                                    ),
                                ),
                            },
                            required=["name", "lessons"],
                        ),
                    ),
                },
                required=["name", "chapters"],
            ),
        ),
    },
    required=["track", "levels"],
)

PARSE_SYSTEM = """You normalize language-learning curriculum outlines into structured JSON.
The input uses markers: (TRK)=track, (LVL)=level (often with a CEFR tag like (A1)),
(CH)=chapter, and '•' bullets for individual lessons. Descriptions may follow a '└─'
arrow or sit on the next indented line. Formatting is inconsistent — some chapters and
lessons are written compactly on a single line; split them correctly anyway.

For each lesson capture a short `title` and its one-line `desc`. Preserve original order.
Extract the CEFR tag (A1–C2) into each level's `cefr`. Do not invent lessons. Output only
the requested JSON."""


def parse_curriculum(text):
    config = types.GenerateContentConfig(
        system_instruction=PARSE_SYSTEM,
        response_mime_type="application/json",
        response_schema=CURRICULUM_SCHEMA,
        temperature=0.1,
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents=[f"Normalize this curriculum into the JSON schema:\n\n{text}"],
        config=config,
    )
    return json.loads(resp.text)


# --------------------------------------------------------------------------------------
# Stage 2: expand lessons -> episodes (per chapter, reusing the fixed cast)
# --------------------------------------------------------------------------------------

EPISODES_SCHEMA = types.Schema(
    type="object",
    properties={
        "episodes": types.Schema(
            type="array",
            items=types.Schema(
                type="object",
                properties={
                    "lessons_covered": types.Schema(
                        type="array", items=types.Schema(type="string"), min_items=1,
                        description="The lesson titles (verbatim) this episode teaches — usually 2-3 combined.",
                    ),
                    "title": types.Schema(type="string", description="Short Finnish episode title."),
                    "title_en": types.Schema(type="string", description="Short, descriptive English title for the combined episode."),
                    "description": types.Schema(type="string", description="3-5 sentence scene description IN FINNISH that naturally covers the combined lessons."),
                    "characters": types.Schema(
                        type="array",
                        min_items=2,
                        items=types.Schema(type="string"),
                        description="Cast ids that appear (from the provided cast). Always include the learner protagonist.",
                    ),
                    "ambient_setting": types.Schema(type="string", enum=AMBIENT_ENUM),
                    "tone": types.Schema(type="string"),
                    "key_phrases": types.Schema(
                        type="array", items=types.Schema(type="string"),
                        description="4-8 target Finnish phrases covering the combined lessons.",
                    ),
                    "notes": types.Schema(type="string", description="Register/direction note for the scriptwriter."),
                },
                required=["lessons_covered", "title", "title_en", "description", "characters",
                          "ambient_setting", "tone", "key_phrases", "notes"],
            ),
        ),
    },
    required=["episodes"],
)


def cast_summary(cast):
    chars = cast["characters"]
    protagonist = next((cid for cid, c in chars.items() if "protagonist" in c.get("role", "").lower()), None)
    lines = []
    for cid, c in chars.items():
        lines.append(
            f"- id: {cid} | {c['name']} ({c.get('role','')}) | tone: {c.get('default_tone','')} | "
            f"{c.get('personality','')} Speech: {c.get('speech_style','')}"
        )
    return "\n".join(lines), protagonist


import math


def choose_k(n, lo, hi):
    """How many episodes for n lessons: aim for <=3 lessons each, clamped to [lo, hi]."""
    k = max(lo, math.ceil(n / 3))
    return max(1, min(k, hi, n))


def chunk_contiguous(items, k):
    """Split a list into k contiguous, order-preserving groups, as evenly as possible."""
    k = max(1, min(k, len(items)))
    n = len(items)
    base, rem = divmod(n, k)
    groups, idx = [], 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        groups.append(items[idx:idx + size])
        idx += size
    return groups


def expand_chapter(track, level_name, cefr, chapter, cast, min_eps=2, max_eps=3):
    """Combine a chapter's lessons into a few episodes, preserving the ORIGINAL ORDER.

    Groupings are decided in code (contiguous, ordered) so episodes always follow the
    curriculum sequence; the model only authors the scene for each pre-set group.
    """
    summary, protagonist = cast_summary(cast)
    valid_ids = set(cast["characters"].keys())
    lessons = chapter.get("lessons", [])
    n_lessons = len(lessons)
    lo = min(min_eps, n_lessons) or 1
    hi = min(max_eps, n_lessons) or 1

    groups = chunk_contiguous(lessons, choose_k(n_lessons, lo, hi))

    groups_block = "\n\n".join(
        f"GROUP {gi+1} (episode {gi+1}):\n" + "\n".join(
            f"  - {l['title']} — {l.get('desc','')}" for l in g
        )
        for gi, g in enumerate(groups)
    )
    proto_line = (
        f"The protagonist/learner is '{protagonist}' — include them in EVERY episode."
        if protagonist else "Include the main learner character in every episode."
    )

    system = f"""You design short Finnish conversation video episodes for a fixed cast.

The lessons have ALREADY been grouped for you, in curriculum order. Write EXACTLY ONE episode per
group, in the SAME ORDER as the groups. Each episode must teach exactly the lessons of its group —
do not reorder, merge across groups, split, add, or drop lessons. Each episode is one believable
1-2 minute scene that naturally brings its group's lessons together.

THE CAST (use ONLY these ids in `characters`):
{summary}

Rules:
- {proto_line}
- Pick 2-3 cast members whose role/personality best fit the group's lessons (the IT person for
  tech, the chatty friend for coffee breaks, the reserved senior colleague for formal practice,
  the manager for scheduling). A one-off non-cast role is NOT allowed — map to the closest cast member.
- `lessons_covered`: the exact lesson titles of that group, in order.
- `description`: IN FINNISH (spoken style), 3-5 sentences, one concrete scene tying the group together.
- `key_phrases`: 4-8 natural Finnish phrases spanning the group's lessons.
- `ambient_setting`: best fit from the allowed list for a workplace setting.
- `notes`: one line on register (formal Minä/Sinä vs spoken Mä/Sä) and who mirrors whom.
- `title` is a short Finnish title; `title_en` is a short descriptive English title.
Return the episodes array in group order. Output only the JSON."""

    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=EPISODES_SCHEMA,
        temperature=0.7,
    )
    prompt = (
        f"Track: {track}\nLevel: {level_name} (CEFR {cefr or 'A1'})\n"
        f"Chapter: {chapter['name']} — {chapter.get('desc','')}\n\n"
        f"Write one episode per group, in order:\n\n{groups_block}"
    )

    last_err = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=MODEL, contents=[prompt], config=config)
            eps = json.loads(resp.text).get("episodes", [])
            if len(eps) != len(groups):
                raise ValueError(f"expected {len(groups)} episodes, got {len(eps)}")
            cleaned = []
            for gi, ep in enumerate(eps):
                ids = [c for c in ep.get("characters", []) if c in valid_ids]
                if protagonist and protagonist not in ids:
                    ids.insert(0, protagonist)
                if len(ids) < 2:
                    for cid in valid_ids:
                        if cid not in ids:
                            ids.append(cid)
                        if len(ids) >= 2:
                            break
                ep["characters"] = ids
                # Force exact, order-preserving lesson coverage from the code-side grouping.
                ep["lessons_covered"] = [l["title"] for l in groups[gi]]
                ep["track"] = chapter["name"]
                ep["chapter"] = chapter["name"]
                ep["level"] = level_name
                ep["language_level"] = normalize_level(cefr) if cefr and is_cefr_level(cefr) else "A1"
                cleaned.append(ep)
            return cleaned
        except Exception as e:
            last_err = e
            print(f"   ⚠️  chapter '{chapter['name']}' attempt {attempt+1}/3 failed: {e}")
            time.sleep(2 * (attempt + 1))
    print(f"   ❌ Skipping chapter '{chapter['name']}' after retries. ({last_err})")
    return []


def build_episodes(curriculum, cast, start_id=1, min_eps=2, max_eps=3):
    track = curriculum.get("track", "")
    episodes = []
    next_id = start_id
    for level in curriculum.get("levels", []):
        cefr = level.get("cefr", "")
        for chapter in level.get("chapters", []):
            n = len(chapter.get("lessons", []))
            print(f"🪄 {level.get('name','')} › {chapter['name']} ({n} lesson(s) → {min(min_eps,n)}-{min(max_eps,n)} episodes)...")
            for ep in expand_chapter(track, level.get("name", ""), cefr, chapter, cast,
                                     min_eps=min_eps, max_eps=max_eps):
                ep_out = {"id": next_id, **ep}
                episodes.append(ep_out)
                next_id += 1
    return episodes


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_parse(paths, curriculum_txt):
    src = Path(curriculum_txt)
    if not src.exists():
        sys.exit(f"❌ Curriculum file not found: {src}")
    text = src.read_text(encoding="utf-8")
    print(f"📖 Parsing curriculum: {src}")
    curriculum = parse_curriculum(text)
    paths.base.mkdir(parents=True, exist_ok=True)
    with open(paths.curriculum_json, "w", encoding="utf-8") as f:
        json.dump(curriculum, f, ensure_ascii=False, indent=2)
    n_lessons = sum(len(ch.get("lessons", [])) for lv in curriculum.get("levels", []) for ch in lv.get("chapters", []))
    print(f"✅ Wrote {paths.curriculum_json}  ({n_lessons} lessons across "
          f"{sum(len(lv.get('chapters', [])) for lv in curriculum.get('levels', []))} chapters)")
    return curriculum


def cmd_build(paths, append=False, min_eps=2, max_eps=3):
    if not paths.curriculum_json.exists():
        sys.exit(f"❌ {paths.curriculum_json} not found. Run `parse` first.")
    if not paths.cast.exists():
        sys.exit(f"❌ {paths.cast} not found. (For a new series, run series_new.py first.)")
    curriculum = load_json(paths.curriculum_json)
    cast = load_json(paths.cast)

    start_id = 1
    existing = []
    if paths.episodes.exists():
        prev = load_json(paths.episodes)
        existing = prev.get("episodes", [])
        if append and existing:
            start_id = max(e["id"] for e in existing) + 1
        elif not append:
            bak = paths.episodes.with_suffix(".json.bak")
            paths.episodes.replace(bak)
            print(f"💾 Backed up existing episodes -> {bak.name}")
            existing = []

    new_eps = build_episodes(curriculum, cast, start_id=start_id, min_eps=min_eps, max_eps=max_eps)
    all_eps = existing + new_eps

    series_block = {
        "title": curriculum.get("track", "Series"),
        "language": "Finnish",
        "default_language_level": (curriculum.get("levels", [{}])[0].get("cefr") or "A1"),
        "default_length": "Short",
    }
    out = {
        "_comment": "Generated by series_plan.py from curriculum.json. Edit freely; ids must stay unique.",
        "series": series_block,
        "episodes": all_eps,
    }
    with open(paths.episodes, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Wrote {len(new_eps)} new episode(s) ({len(all_eps)} total) -> {paths.episodes}")
    print(f"   Next:  python series_run.py <id>" + (f" --series {paths.slug}" if paths.slug else ""))


def main():
    if not client:
        sys.exit("🛑 GEMINI_API_KEY missing or client init failed.")

    slug, args = series_paths.parse_series_arg(sys.argv[1:])
    paths = series_paths.resolve(slug)
    series_paths.announce(paths.slug)
    append = "--append" in args
    force = "--force" in args
    args = [a for a in args if a not in ("--append", "--force")]

    # --per-chapter <n> (exact) or <lo-hi> (range). Default 2-3.
    min_eps, max_eps = 2, 3
    pc = None
    for i, a in enumerate(args):
        if a == "--per-chapter" and i + 1 < len(args):
            pc = args[i + 1]
        elif a.startswith("--per-chapter="):
            pc = a.split("=", 1)[1]
    if pc:
        try:
            if "-" in pc:
                min_eps, max_eps = (int(x) for x in pc.split("-", 1))
            else:
                min_eps = max_eps = int(pc)
        except ValueError:
            sys.exit("❌ --per-chapter expects N or LO-HI, e.g. --per-chapter 2 or --per-chapter 2-3")
        # drop the flag (and its separate value) from positional args
        cleaned = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == "--per-chapter":
                skip = True
                continue
            if a.startswith("--per-chapter="):
                continue
            cleaned.append(a)
        args = cleaned

    if not args:
        sys.exit(__doc__)
    cmd = args[0].lower()

    if cmd == "parse":
        if len(args) < 2:
            sys.exit("Usage: python series_plan.py parse <curriculum.txt> [--series slug]")
        if paths.curriculum_json.exists() and not force:
            sys.exit(f"ℹ️  {paths.curriculum_json.name} already exists — pass --force to re-parse "
                     f"(this would overwrite any edits).")
        cmd_parse(paths, args[1])
    elif cmd == "build":
        cmd_build(paths, append=append, min_eps=min_eps, max_eps=max_eps)
    elif cmd == "all":
        if len(args) < 2:
            sys.exit("Usage: python series_plan.py all <curriculum.txt> [--series slug] [--append] [--per-chapter 2-3] [--force]")
        if paths.curriculum_json.exists() and not force:
            print(f"ℹ️  Using existing {paths.curriculum_json.name} (pass --force to re-parse {Path(args[1]).name}).")
        else:
            cmd_parse(paths, args[1])
        cmd_build(paths, append=append, min_eps=min_eps, max_eps=max_eps)
    else:
        sys.exit(f"Unknown command '{cmd}'. Use: parse | build | all")


if __name__ == "__main__":
    main()
