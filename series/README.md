# Series system

A thin layer on top of the existing pipeline for producing a **recurring-cast** Finnish
conversation series. Same characters, same voices, same faces across every episode.

The existing pipeline is **idea-driven**: `generate_ideas_json.py` invents random characters
and scenarios each run. A series needs the opposite — a fixed cast and a fixed episode list.
This folder provides that, and `series_compile.py` feeds it into the pipeline you already have.

## Files

| File | What it is |
|------|------------|
| `cast.json` | **Character bible.** One canonical entry per character: `voice_id`, personality, `speech_style`, `appearance`, `reference_image`. The `id` keys (e.g. `aisha`) are what episodes reference. |
| `episodes.json` | **The episode list** — title, description, which cast members appear, target phrases, ambient setting, CEFR level. Hand-written or generated from a curriculum. Edit/add/reorder freely. |
| `curriculum.txt` | Raw pasted curriculum (tracks → levels → chapters → lessons). Input to `series_plan.py`. |
| `curriculum.json` | Structured/normalized curriculum produced by `series_plan.py parse` — reviewable before building episodes. |
| `characters/` | One reference portrait per character (see its README). |
| `../series_plan.py` | **Curriculum → episodes** generator (parse + build). One lesson → one episode. |
| `../series_new.py` | Scaffold a brand-new series under `series/<slug>/`. |
| `../generate_cast.py` | AI-generate a cast (with real voice IDs) fitting the series' curriculum. |
| `../series_use.py` | Show or switch the active series. |
| `../series_compile.py` | Bridge: resolves an episode's cast and writes a standard `ideas.json`. |
| `../series_run.py` | One-command end-to-end builder for a single episode. |
| `../generate_character_refs.py` | Generates the reference portraits from `cast.json`. |

## What makes the series consistent

- **Voice** — each character has ONE `voice_id` in `cast.json`. Every episode reuses it, so
  the voice is identical from video to video. (The pipeline already keys TTS on `voice_id`.)
- **Personality / register** — `speech_style` (e.g. Aisha's careful Minä/Sinä vs. Mikko's fast
  Mä/Sä puhekieli) is folded into the script prompt so dialogue stays in character.
- **Face** — one reference portrait per character, reused as an image reference when
  illustrating each episode (see *Visual consistency* below).

## Workflow

```bash
# 0. (once) lock each character's look
python generate_character_refs.py

# 1. pick episode(s) -> writes ideas.json  (replaces generate_ideas_json.py)
python series_compile.py list        # see the menu
python series_compile.py 1           # compile episode 1

# 2. run the rest of the existing pipeline, SKIPPING step 1
python generate_scripts.py
python check_finnish_grammar.py
python generate_illustrations.py
python generate_sfx.py
python tts_generator.py
python sfx_mixer.py
python generate_videos.py
python music_mixer.py
```

> Compile **one episode at a time** for accurate per-episode CEFR level (the pipeline applies
> a single level per `ideas.json`). You can compile several at once for a batch at the series
> default level.

## Series Run (one-command episode builder)

Instead of running each step manually, `series_run.py` builds a **single episode end-to-end** with one command:

```bash
python series_run.py 1            # build episode 1 all the way to a final video
python series_run.py 4 --keep     # don't clean previous outputs first
python series_run.py 1 --no-refs  # skip character-portrait generation
```

Pipeline executed automatically:

0. **Cleanup** — removes previous outputs (safe — never touches `series/characters/`)
1. **Character refs** — generates any missing portraits for this episode's cast
2. **Compile episode** — `series_compile.py` → `ideas.json`
3. **Full pipeline** — scripts → check Finnish → illustrations → SFX → TTS → mix SFX → video → music

| Flag | Effect |
|------|--------|
| `--keep` | Skip the cleanup step (keep previous outputs) |
| `--no-refs` | Skip character-portrait generation |

Final video lands in `output_videos/`.

## Producing episodes from a curriculum

Turn a curriculum outline (tracks → levels → chapters → lessons) into episodes. Rather than one
episode per lesson, each chapter's lessons are grouped into a few combined episodes (2–3 per chapter
by default) — giving the series natural spacing. Groups are **consecutive and follow the original
curriculum order** (decided in code), and the AI authors one scene per group that weaves those
lessons together.

```bash
# one-shot: normalize the pasted curriculum, then generate grouped episodes
python series_plan.py all series/curriculum.txt
python series_plan.py all series/curriculum.txt --force   # re-parse even if curriculum.json exists

# or run the two stages separately (review curriculum.json in between)
python series_plan.py parse series/curriculum.txt    # -> series/curriculum.json
python series_plan.py build                           # -> series/episodes.json
python series_plan.py build --append                  # add to existing episodes instead of replacing
python series_plan.py build --per-chapter 2           # exactly 2 per chapter
python series_plan.py build --per-chapter 2-4         # a wider range
python series_plan.py split 10                        # AI decides where to split (or not)
python series_plan.py split 10 2 1                    # force a manual split: [first 2] + [last 1]
python series_plan.py split all                       # AI reviews every episode, splits mashups
```

**Splitting an episode** when it fuses lessons that shouldn't share a scene (e.g. a café lunch and
grocery shopping): `split <id>` lets the **AI find the split points** (contiguous, order-preserving)
and re-authors each part as its own single-location scene with its own setting/cast. It won't split a
genuinely coherent episode. Pass explicit sizes to force a partition (they must sum to the lesson
count), or `split all` to auto-scan the whole series. IDs are resequenced (files are slug-named, so
unaffected).

1. **parse** — an LLM normalizes the (often messy/compact) curriculum text into structured
   `curriculum.json`. Edit it if you want before building. **`all` reuses an existing
   `curriculum.json` and skips parsing** (preserving your edits) — pass `--force` to re-parse.
2. **build** — splits each chapter's lessons into 2–3 **contiguous, in-order** groups (configurable
   with `--per-chapter`), covering **every** lesson with none reordered or duplicated. Each episode gets a Finnish
   scene, the cast members that best fit (IT person for tech, the chatty friend for coffee, the
   reserved senior for formal practice, the manager for scheduling…), combined target phrases, an
   ambient setting, and the CEFR level from the level's `(A1)` tag. Each episode lists the lessons
   it covers in `lessons_covered`, and the protagonist appears in every episode.

`build` overwrites `episodes.json` (backing the old one up to `episodes.json.bak`) unless you pass
`--append`. Then build videos as usual: `python series_run.py <id>`.

## Creating a new series

Each series lives in its own folder. Creating one makes it the **active series** (stored in
`series/.active`), so the following commands target it automatically — no `--series` needed.
Every command prints which series it's using (`📂 Series: …`).

```bash
python series_new.py doctor-visits "At the Doctor"               # fresh cast template (now active)
python series_new.py doctor-visits "At the Doctor" --copy-cast   # reuse the current cast

# define the cast — AI-generate it, or edit cast.json by hand, or use --copy-cast above:
python generate_cast.py            # designs a cast from the curriculum + assigns real voice IDs

# these now target the active series automatically:
python series_plan.py all path/to/curriculum.txt
python generate_character_refs.py
python series_run.py 1
```

`generate_cast.py` reads the series' curriculum/theme and writes a `cast.json` with a learner
protagonist plus recurring characters (personalities, speech styles, appearances) and real
ElevenLabs voice IDs matched by gender/age. Options: `--count N`, a free-text theme hint,
`--series <slug>`.

Switch the active series anytime (or override per-command with `--series <slug>`):

```bash
python series_use.py                 # show active + list all series
python series_use.py doctor-visits   # switch
python series_use.py default         # back to the default flat series/
```

`series_new.py` creates `series/<slug>/` with a `cast.json` (template, or a copy of this series'
cast via `--copy-cast`), an empty `episodes.json`, and a `characters/` folder. Fill in voice IDs
and appearances, then generate.

## Managing & modifying episodes

- **Add an episode:** append an object to `episodes.json` → `episodes`. Set `characters` to a
  list of cast ids. Done — it shows up in `series_compile.py list`.
- **New recurring character:** add an entry to `cast.json` → `characters`, give it a `voice_id`
  and `appearance`, then `python generate_character_refs.py <id>`.
- **One-off character** (no recurring need): you can inline a full character object directly in
  an episode's `characters` list instead of an id.
- **Change a voice / look:** edit `voice_id` or `appearance` in `cast.json`. Re-run
  `generate_character_refs.py --force` for the look.

## Visual consistency (wired in)

`generate_illustrations.py` feeds each present character's `reference_image` into the image model
as an identity anchor, so faces/hair/clothing stay consistent across episodes. `series_compile.py`
carries the `reference_image` paths onto each character in `ideas.json`, and the illustrator opens
any that exist and prepends them to the request. So: generate the portraits once
(`generate_character_refs.py`) and every episode illustration stays on-model automatically. If a
portrait is missing, that character is simply illustrated from its text description as before.

## Voices to fill in

`cast.json` ships with placeholder `voice_id`s (`REPLACE_WITH_ELEVENLABS_VOICE_ID`) for the new
characters. Sari reuses the existing ID from the old `ideas.json`. Paste your ElevenLabs voice
IDs into `cast.json` and every episode picks them up automatically.
