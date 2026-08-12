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

    # split an episode whose lessons don't belong in one scene (e.g. lunch + grocery shopping)
    python series_plan.py split 10               # AI decides WHERE to split (or that it shouldn't)
    python series_plan.py split 10 2 1           # force a manual split: [first 2] + [last 1]
    python series_plan.py split all              # AI reviews every episode and splits mashups

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
                    "title": types.Schema(type="string", description="Short episode title in the target language."),
                    "title_en": types.Schema(type="string", description="Short, descriptive English title for the combined episode."),
                    "description": types.Schema(type="string", description="3-5 sentence scene description IN THE TARGET LANGUAGE that naturally covers the combined lessons."),
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
                        description="4-8 target phrases in the target language covering the combined lessons.",
                    ),
                    "notes": types.Schema(type="string", description="Register/direction note for the scriptwriter."),
                    "illustration_layout": types.Schema(
                        type="string", enum=["single", "split"],
                        description="'single' = all characters together in one scene (default). 'split' = characters in separate locations (e.g. phone call) — each gets their own panel.",
                    ),
                },
                required=["lessons_covered", "title", "title_en", "description", "characters",
                          "ambient_setting", "tone", "key_phrases", "notes", "illustration_layout"],
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


def _author_episodes(track, chapter_name, chapter_desc, level_name, cefr, groups, cast, language="Finnish"):
    """Author ONE episode per pre-decided lesson group (LLM writes the scene; grouping is fixed).

    `groups` is a list of lesson lists (each lesson a dict with 'title' and optional 'desc').
    Returns cleaned episode dicts, in group order.
    """
    summary, protagonist = cast_summary(cast)
    valid_ids = set(cast["characters"].keys())

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

    system = f"""You design short {language} conversation video episodes for a fixed cast.

The lessons have ALREADY been grouped for you, in order. Write EXACTLY ONE episode per group, in
the SAME ORDER as the groups. Each episode must teach exactly the lessons of its group — do not
reorder, merge across groups, split, add, or drop lessons. Each episode is ONE believable 1-2
minute scene in ONE place that naturally brings its group's lessons together (do not stitch two
different locations into one scene).

THE CAST (use ONLY these ids in `characters`):
{summary}

Rules:
- {proto_line}
- Pick 2-3 cast members whose role/personality best fit the group's lessons (the IT person for
  tech, the chatty friend for coffee breaks, the reserved senior colleague for formal practice,
  the manager for scheduling). A one-off non-cast role is NOT allowed — map to the closest cast member.
- `lessons_covered`: the exact lesson titles of that group, in order.
- `description`: IN {language.upper()} (spoken style), 3-5 sentences, one concrete scene tying the group together.
- `key_phrases`: 4-8 natural {language} phrases spanning the group's lessons.
- `ambient_setting`: best fit from the allowed list for the scene's single location.
- `notes`: one line on register (formal vs casual) and who mirrors whom.
- `illustration_layout`: set to 'split' when characters are NOT in the same physical location
  (e.g. phone calls, video calls, texting, customer service calls). Otherwise 'single' (default).
- `title` is a short {language} title; `title_en` is a short descriptive English title.
Return the episodes array in group order. Output only the JSON."""

    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=EPISODES_SCHEMA,
        temperature=0.7,
    )
    prompt = (
        f"Track: {track}\nLevel: {level_name} (CEFR {cefr or 'A1'})\n"
        f"Chapter: {chapter_name} — {chapter_desc}\n\n"
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
                ep["track"] = track
                ep["chapter"] = chapter_name
                ep["level"] = level_name
                ep["language_level"] = normalize_level(cefr) if cefr and is_cefr_level(cefr) else "A1"
                cleaned.append(ep)
            return cleaned
        except Exception as e:
            last_err = e
            print(f"   ⚠️  '{chapter_name}' attempt {attempt+1}/3 failed: {e}")
            time.sleep(2 * (attempt + 1))
    print(f"   ❌ Giving up on '{chapter_name}' after retries. ({last_err})")
    return []


def plan_grouping(level_name, cefr, lessons):
    """Ask the LLM which lessons naturally belong together in a single conversation scene.

    Returns (sizes, reason) where sizes is a contiguous partition summing to len(lessons).
    Each group becomes one episode. Closely related lessons are grouped; unrelated ones stay separate.
    """
    n = len(lessons)
    if n <= 1:
        return [1] * n, "single lesson"

    block = "\n".join(f"{i+1}. {l['title']} — {l.get('desc','')}" for i, l in enumerate(lessons))
    system = (
        "You decide how to group lessons from a language-learning curriculum into EPISODES. "
        "Each episode will become a SHORT video (1-2 minutes) with ONE conversation scene in ONE location.\n\n"
        "RULES:\n"
        "- Only group lessons that share a NATURAL conversation scenario (e.g. two lessons about "
        "ordering food can share one café scene). Do NOT force unrelated topics together.\n"
        "- Lessons about fundamentals (alphabet, pronunciation, grammar rules) should usually be "
        "SEPARATE episodes — they need focused practice, not cramming.\n"
        "- A group of 2 is fine when the lessons are truly complementary. Groups of 3+ are rare.\n"
        "- Keep lessons in their given order. Groups must be CONTIGUOUS.\n"
        "- When in doubt, keep lessons SEPARATE — a focused 1-lesson episode is better than a "
        "confusing multi-topic one.\n"
        "- Return group_sizes as an array that sums to the total number of lessons."
    )
    prompt = f"Level {level_name} ({cefr}). Chapter lessons, in order:\n{block}\n\nDecide the contiguous group sizes."
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=SPLIT_SCHEMA,  # reuse the same schema (group_sizes + reason)
        temperature=0.2,
    )
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=MODEL, contents=[prompt], config=config)
            out = json.loads(resp.text)
            sizes = [int(s) for s in out.get("group_sizes", []) if int(s) > 0]
            if sizes and sum(sizes) == n:
                reason = out.get("reason", "")
                return sizes, reason
        except Exception as e:
            print(f"   ⚠️  grouping attempt {attempt+1}/3 failed: {e}")
            time.sleep(2 * (attempt + 1))
    return [1] * n, "grouping planner failed — one lesson per episode"


def expand_chapter(track, level_name, cefr, chapter, cast, min_eps=None, max_eps=None, language="Finnish"):
    """Turn a chapter's lessons into episodes.

    Default (min_eps=None): LLM decides which lessons belong together.
    With min_eps/max_eps set: fixed grouping into that many episodes per chapter.
    """
    lessons = chapter.get("lessons", [])
    n_lessons = len(lessons)

    if min_eps is not None and max_eps is not None:
        # Fixed grouping mode (--per-chapter flag)
        lo = min(min_eps, n_lessons) or 1
        hi = min(max_eps, n_lessons) or 1
        groups = chunk_contiguous(lessons, choose_k(n_lessons, lo, hi))
    else:
        # LLM-based intelligent grouping (default)
        sizes, reason = plan_grouping(level_name, cefr, lessons)
        groups = _partition(lessons, sizes)
        n_groups = len(groups)
        if n_groups == n_lessons:
            print(f"      → {n_groups} episodes (all separate): {reason}")
        else:
            group_desc = "+".join(str(s) for s in sizes)
            print(f"      → {n_groups} episodes (grouped {group_desc}): {reason}")

    return _author_episodes(track, chapter["name"], chapter.get("desc", ""),
                            level_name, cefr, groups, cast, language)


# --------------------------------------------------------------------------------------
# Scaffolding fade: which episodes are authored as GUIDED (bilingual, teacher-led) lessons
# for true beginners vs. normal immersive conversations. The first `guided_chapters`
# chapters of a beginner (A1) level get the guided format; difficulty then "fades" into
# full-target-language conversation. Baked in here so recreating a series keeps the fade.
# --------------------------------------------------------------------------------------
GUIDED_FADE_LEVELS = {"A1"}
GUIDED_FADE_CHAPTERS = 4


def _guided_format(cefr, chapter_index, guided_chapters):
    """Return "guided" for early-chapter A1 episodes, else "conversation"."""
    level = normalize_level(cefr) if cefr and is_cefr_level(cefr) else ""
    if guided_chapters > 0 and level in GUIDED_FADE_LEVELS and chapter_index < guided_chapters:
        return "guided"
    return "conversation"


def build_episodes(curriculum, cast, start_id=1, min_eps=None, max_eps=None,
                   language="Finnish", guided_chapters=GUIDED_FADE_CHAPTERS):
    track = curriculum.get("track", "")
    episodes = []
    next_id = start_id
    for level in curriculum.get("levels", []):
        cefr = level.get("cefr", "")
        for chapter_index, chapter in enumerate(level.get("chapters", [])):
            n = len(chapter.get("lessons", []))
            mode = "LLM decides" if min_eps is None else f"{min(min_eps,n)}-{min(max_eps,n)} fixed"
            fmt = _guided_format(cefr, chapter_index, guided_chapters)
            tag = "  🧑‍🏫 guided" if fmt == "guided" else ""
            print(f"🪄 {level.get('name','')} › {chapter['name']} ({n} lessons, {mode}){tag}...")
            for ep in expand_chapter(track, level.get("name", ""), cefr, chapter, cast,
                                     min_eps=min_eps, max_eps=max_eps, language=language):
                ep_out = {"id": next_id, **ep, "format": fmt}
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


def cmd_build(paths, append=False, min_eps=2, max_eps=3, guided_chapters=GUIDED_FADE_CHAPTERS):
    if not paths.curriculum_json.exists():
        sys.exit(f"❌ {paths.curriculum_json} not found. Run `parse` first.")
    if not paths.cast.exists():
        sys.exit(f"❌ {paths.cast} not found. (For a new series, run series_new.py first.)")
    curriculum = load_json(paths.curriculum_json)
    cast = load_json(paths.cast)

    start_id = 1
    existing = []
    language = "Finnish"
    if paths.episodes.exists():
        prev = load_json(paths.episodes)
        existing = prev.get("episodes", [])
        language = prev.get("series", {}).get("language", "Finnish")
        if append and existing:
            start_id = max(e["id"] for e in existing) + 1
        elif not append:
            bak = paths.episodes.with_suffix(".json.bak")
            paths.episodes.replace(bak)
            print(f"💾 Backed up existing episodes -> {bak.name}")
            existing = []

    # Auto-detect language from slug/title if episodes.json defaulted to Finnish
    # but the series name clearly indicates another language
    from language_config import supported_languages
    track = curriculum.get("track", "")
    combined = f"{paths.slug or ''} {track}".lower()
    for lang in supported_languages():
        if lang.lower() != "finnish" and lang.lower() in combined:
            if language == "Finnish":
                print(f"🌐 Auto-detected language: {lang} (from series name, overriding default Finnish)")
            language = lang
            break

    print(f"🌐 Language: {language}")
    if guided_chapters > 0:
        print(f"🧑‍🏫 Guided fade: first {guided_chapters} chapter(s) of each "
              f"{'/'.join(sorted(GUIDED_FADE_LEVELS))} level use the guided (bilingual) format.")
    new_eps = build_episodes(curriculum, cast, start_id=start_id, min_eps=min_eps, max_eps=max_eps,
                             language=language, guided_chapters=guided_chapters)
    all_eps = existing + new_eps

    series_block = {
        "title": curriculum.get("track", "Series"),
        "language": language,
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


def _lesson_desc_lookup(curriculum):
    """Map lesson title -> description from curriculum.json (best effort)."""
    m = {}
    for lv in (curriculum or {}).get("levels", []):
        for ch in lv.get("chapters", []):
            for l in ch.get("lessons", []):
                m[l.get("title", "")] = l.get("desc", "")
    return m


SPLIT_SCHEMA = types.Schema(
    type="object",
    properties={
        "needs_split": types.Schema(type="boolean"),
        "reason": types.Schema(type="string", description="Brief reason (one line)."),
        "group_sizes": types.Schema(
            type="array", items=types.Schema(type="integer"),
            description="Contiguous group sizes covering the lessons in order; must sum to the "
                        "number of lessons. A single value (the total) means no split.",
        ),
    },
    required=["needs_split", "reason", "group_sizes"],
)


def plan_split(level_name, cefr, lessons):
    """Ask the model where (if anywhere) an episode should be split. Returns (sizes, reason).

    `sizes` is a contiguous partition summing to len(lessons); [len(lessons)] means no split.
    """
    n = len(lessons)
    block = "\n".join(f"{i+1}. {l['title']} — {l.get('desc','')}" for i, l in enumerate(lessons))
    system = (
        "You decide how to split a language-learning video episode into coherent scenes. "
        "An episode must be ONE believable conversation happening in ONE location and continuous "
        "moment. If the lessons would force different locations or clearly separate interactions "
        "(e.g. a café lunch AND grocery shopping; or a phone call AND a face-to-face chat), split "
        "them into separate CONTIGUOUS groups, each of which is a single coherent scene. Keep the "
        "lessons in their given order; groups must be contiguous and together cover every lesson "
        "exactly once. If they all fit one natural scene, do NOT split (return one group). Prefer "
        "the FEWEST splits that keep each scene believable — do not over-split closely related lessons."
    )
    prompt = f"Level {level_name} {cefr}. Episode lessons, in order:\n{block}\n\nDecide the contiguous group sizes."
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=SPLIT_SCHEMA,
        temperature=0.2,
    )
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=MODEL, contents=[prompt], config=config)
            out = json.loads(resp.text)
            sizes = [int(s) for s in out.get("group_sizes", []) if int(s) > 0]
            if sizes and sum(sizes) == n:
                return sizes, out.get("reason", "")
        except Exception as e:
            print(f"   ⚠️  split-planning attempt {attempt+1}/3 failed: {e}")
            time.sleep(2 * (attempt + 1))
    return [n], "planner failed — no split"


def _partition(lessons, sizes):
    groups, idx = [], 0
    for sz in sizes:
        groups.append(lessons[idx:idx + sz])
        idx += sz
    return groups


def _episode_lessons(ep, desc_map):
    return [{"title": t, "desc": desc_map.get(t, "")} for t in ep.get("lessons_covered", [])]


def _author_split(ep, groups, cast):
    return _author_episodes(
        ep.get("track", ""), ep.get("chapter", ep.get("track", "")), "",
        ep.get("level", ""), ep.get("language_level", ""), groups, cast,
    )


def cmd_split(paths, ep_id, sizes):
    """Split one episode's lessons into new episodes. With no sizes, the AI decides where to split."""
    if not paths.episodes.exists():
        sys.exit(f"❌ {paths.episodes} not found.")
    if not paths.cast.exists():
        sys.exit(f"❌ {paths.cast} not found.")
    data = load_json(paths.episodes)
    cast = load_json(paths.cast)
    episodes = data.get("episodes", [])

    pos = next((i for i, e in enumerate(episodes) if e.get("id") == ep_id), None)
    if pos is None:
        sys.exit(f"❌ Episode {ep_id} not found. Run: python series_compile.py list")
    ep = episodes[pos]
    titles = ep.get("lessons_covered", [])
    if len(titles) < 2:
        sys.exit(f"❌ Episode {ep_id} covers <2 lessons — nothing to split.\n   Lessons: {titles}")

    desc_map = _lesson_desc_lookup(load_json(paths.curriculum_json) if paths.curriculum_json.exists() else {})
    lessons = _episode_lessons(ep, desc_map)

    # Decide the partition: manual sizes if given, otherwise let the AI find the split points.
    if sizes:
        if sum(sizes) != len(titles):
            sys.exit(f"❌ Sizes {sizes} sum to {sum(sizes)}, but episode {ep_id} has "
                     f"{len(titles)} lessons: {titles}")
        cut_sizes = sizes
    else:
        print(f"🤖 Asking the AI where to split episode {ep_id} ({ep.get('title_en','')})...")
        cut_sizes, reason = plan_split(ep.get("level", ""), ep.get("language_level", ""), lessons)
        print(f"   → {reason}")
        if len(cut_sizes) <= 1:
            print("✅ AI judged this is already one coherent scene — not splitting.\n"
                  "   (Force a split with explicit sizes, e.g. `split "
                  f"{ep_id} {' '.join(['1'] * len(titles))}`.)")
            return

    groups = _partition(lessons, cut_sizes)
    print(f"✂️  Splitting episode {ep_id} ({ep.get('title_en','')}) into {len(groups)} episode(s):")
    for gi, g in enumerate(groups):
        print(f"   {gi+1}. {', '.join(l['title'] for l in g)}")

    new_eps = _author_split(ep, groups, cast)
    if len(new_eps) != len(groups):
        sys.exit("❌ Authoring failed — no changes made.")

    bak = paths.episodes.with_suffix(".json.bak")
    paths.episodes.replace(bak)
    print(f"💾 Backed up episodes -> {bak.name}")

    episodes[pos:pos + 1] = new_eps
    for i, e in enumerate(episodes, start=1):
        e["id"] = i
    data["episodes"] = episodes
    with open(paths.episodes, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Split done. Episodes renumbered; total now {len(episodes)}.")
    print("   (ids were resequenced — check `python series_compile.py list`)")


def cmd_split_all(paths):
    """Scan every episode; let the AI split any that fuse multiple scenes."""
    if not paths.episodes.exists():
        sys.exit(f"❌ {paths.episodes} not found.")
    if not paths.cast.exists():
        sys.exit(f"❌ {paths.cast} not found.")
    data = load_json(paths.episodes)
    cast = load_json(paths.cast)
    episodes = data.get("episodes", [])
    desc_map = _lesson_desc_lookup(load_json(paths.curriculum_json) if paths.curriculum_json.exists() else {})

    print(f"🤖 Reviewing {len(episodes)} episode(s) for scene splits...\n")
    new_list = []
    n_split = 0
    for ep in episodes:
        titles = ep.get("lessons_covered", [])
        if len(titles) < 2:
            new_list.append(ep)
            continue
        lessons = _episode_lessons(ep, desc_map)
        sizes, reason = plan_split(ep.get("level", ""), ep.get("language_level", ""), lessons)
        if len(sizes) <= 1:
            print(f"   ✔  #{ep.get('id')} {ep.get('title_en','')}: keep as one scene.")
            new_list.append(ep)
            continue
        print(f"   ✂️  #{ep.get('id')} {ep.get('title_en','')}: split into {len(sizes)} — {reason}")
        groups = _partition(lessons, sizes)
        authored = _author_split(ep, groups, cast)
        if len(authored) == len(groups):
            new_list.extend(authored)
            n_split += 1
        else:
            print(f"      ⚠️  authoring failed — keeping original.")
            new_list.append(ep)

    if n_split == 0:
        print("\n✅ No episodes needed splitting.")
        return

    bak = paths.episodes.with_suffix(".json.bak")
    paths.episodes.replace(bak)
    print(f"\n💾 Backed up episodes -> {bak.name}")
    for i, e in enumerate(new_list, start=1):
        e["id"] = i
    data["episodes"] = new_list
    with open(paths.episodes, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Split {n_split} episode(s); total now {len(new_list)}. IDs resequenced.")


def main():
    if not client:
        sys.exit("🛑 GEMINI_API_KEY missing or client init failed.")

    slug, args = series_paths.parse_series_arg(sys.argv[1:])
    paths = series_paths.resolve(slug)
    series_paths.announce(paths.slug)
    append = "--append" in args
    force = "--force" in args
    no_guided = "--no-guided" in args
    args = [a for a in args if a not in ("--append", "--force", "--no-guided")]

    # --guided-chapters <n>: how many early chapters per A1 level use the guided format
    # (0 disables). --no-guided is shorthand for 0. Default GUIDED_FADE_CHAPTERS.
    guided_chapters = 0 if no_guided else GUIDED_FADE_CHAPTERS
    gc = None
    for i, a in enumerate(args):
        if a == "--guided-chapters" and i + 1 < len(args):
            gc = args[i + 1]
        elif a.startswith("--guided-chapters="):
            gc = a.split("=", 1)[1]
    if gc is not None:
        try:
            guided_chapters = max(0, int(gc))
        except ValueError:
            sys.exit("❌ --guided-chapters expects a non-negative integer, e.g. --guided-chapters 4")
        cleaned, skip = [], False
        for a in args:
            if skip:
                skip = False
                continue
            if a == "--guided-chapters":
                skip = True
                continue
            if a.startswith("--guided-chapters="):
                continue
            cleaned.append(a)
        args = cleaned

    # --per-chapter <n> (exact) or <lo-hi> (range). Default: LLM decides grouping.
    min_eps, max_eps = None, None
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
        cmd_build(paths, append=append, min_eps=min_eps, max_eps=max_eps, guided_chapters=guided_chapters)
    elif cmd == "all":
        if len(args) < 2:
            sys.exit("Usage: python series_plan.py all <curriculum.txt> [--series slug] [--append] [--per-chapter 2-3] [--force]")
        if paths.curriculum_json.exists() and not force:
            print(f"ℹ️  Using existing {paths.curriculum_json.name} (pass --force to re-parse {Path(args[1]).name}).")
        else:
            cmd_parse(paths, args[1])
        cmd_build(paths, append=append, min_eps=min_eps, max_eps=max_eps, guided_chapters=guided_chapters)
    elif cmd == "split":
        if len(args) >= 2 and args[1].lower() == "all":
            cmd_split_all(paths)
        elif len(args) >= 2 and args[1].isdigit():
            ep_id = int(args[1])
            sizes = [int(a) for a in args[2:] if a.isdigit()]
            cmd_split(paths, ep_id, sizes)
        else:
            sys.exit("Usage: python series_plan.py split <episode_id> [size1 size2 ...]\n"
                     "       python series_plan.py split all\n"
                     "  split <id>            AI decides where (if anywhere) to split.\n"
                     "  split <id> 2 1        force a manual contiguous partition.\n"
                     "  split all             AI reviews every episode and splits scene-mashups.")
    else:
        sys.exit(f"Unknown command '{cmd}'. Use: parse | build | split | all")


if __name__ == "__main__":
    main()
