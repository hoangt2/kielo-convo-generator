# Convo Generator

A Python toolkit for producing short Finnish conversation videos with Google Gemini and
ElevenLabs — dialogue scripts, illustrations, text-to-speech, sound effects, and background
music, assembled into finished videos. Content can be targeted to a CEFR level (A1–C2).

There are **two ways to generate**, both feeding the same media pipeline:

| Mode | Use it for | Driven by |
|------|-----------|-----------|
| **Series Mode** | A recurring cast with consistent voices & faces across many episodes, generated from a curriculum. | `series/` data + `series_*.py` |
| **Idea Mode** | One-off conversations or podcast lessons with random characters/scenarios. | `generate_ideas_json.py` |

---

## Setup

### 1. Virtual environment

**Mac/Linux**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Python 3.11 is recommended. Python 3.14 may have dependency compatibility issues.

### 2. API keys

Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_gemini_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

### 3. FFmpeg

Required for audio/video processing. Install via your package manager (`brew install ffmpeg`,
`apt install ffmpeg`, etc.).

---

## Series Mode

A thin layer over the pipeline for producing a **recurring-cast** series. The same characters
keep the same voice and the same face from one episode to the next, and episodes are generated
from a curriculum outline. Everything lives in `series/`.

### How consistency works

- **Voice** — each character has one `voice_id` in `series/cast.json`; every episode reuses it
  (the pipeline keys TTS on `voice_id`). Replace the `REPLACE_WITH_ELEVENLABS_VOICE_ID`
  placeholders with your ElevenLabs voice IDs.
- **Personality / register** — each character's `speech_style` (e.g. careful `Minä/Sinä` vs.
  spoken `Mä/Sä`) is folded into the script prompt automatically.
- **Face** — one reference portrait per character in `series/characters/`, fed into the
  illustrator as an identity anchor so faces/hair/clothing stay on-model every episode.

### Quick start — build one episode end to end

```bash
python series_compile.py list      # see the episode menu
python series_run.py 1             # build episode 1 → final video in output_videos/
```

`series_run.py` runs the whole chain for a single episode:

0. **Cleanup** — clears previous outputs (never touches `series/characters/` or `output_videos/prod/`)
1. **Character refs** — generates any missing portraits for that episode's cast
2. **Compile** — writes `ideas.json` for that episode
3. **Pipeline** — scripts → Finnish check → illustrations → SFX → TTS → mix SFX → video → music

| Flag | Effect |
|------|--------|
| `--keep` | Skip cleanup (keep previous outputs) |
| `--no-refs` | Skip character-portrait generation |
| `--series <slug>` | Operate on `series/<slug>/` instead of the default series |

### Generate episodes from a curriculum

Turn a curriculum outline (tracks → levels → chapters → lessons) into episodes. Each chapter's
lessons are combined into a few episodes (2–3 per chapter by default), kept in their **original
consecutive order**, each authored as one believable scene using the fixed cast.

```bash
python series_plan.py all series/curriculum.txt     # parse outline + build episodes.json
python series_plan.py all series/curriculum.txt --force   # re-parse even if curriculum.json exists
python series_plan.py parse series/curriculum.txt   # stage 1 only → series/curriculum.json
python series_plan.py build                          # stage 2 only → series/episodes.json
python series_plan.py build --append                 # add to existing episodes instead of replacing
python series_plan.py build --per-chapter 2          # exactly 2 per chapter (or a range like 2-4)
```

1. **parse** — an LLM normalizes the (often messy/compact) curriculum text into structured
   `series/curriculum.json`, which you can review/edit before building. **`all` reuses an existing
   `curriculum.json` and skips parsing** (so your edits survive) — pass `--force` to re-parse.
2. **build** — splits each chapter's lessons into contiguous, in-order groups and writes one
   episode per group into `series/episodes.json`: a Finnish scene, the best-fitting cast members,
   combined target phrases, an ambient setting, and the CEFR level from the level's `(A1)` tag.
   Each episode records the lessons it covers in `lessons_covered`. `build` overwrites
   `episodes.json` (backing up to `episodes.json.bak`) unless you pass `--append`.

The curriculum format uses `(TRK)` / `(LVL)` / `(CH)` markers and `•` bullets for lessons — see
`series/curriculum.txt` for the working example.

### Creating a new series

Each series lives in its own folder. Creating one makes it the **active series**, so the
following commands target it automatically — no `--series` needed.

```bash
python series_new.py doctor-visits "At the Doctor"               # fresh cast template (now active)
python series_new.py doctor-visits "At the Doctor" --copy-cast   # reuse the current cast

# define the cast — three options:
python generate_cast.py                            # AI-design a cast from the curriculum/theme
#   ...or edit series/<slug>/cast.json by hand, or use --copy-cast above

python series_plan.py all path/to/curriculum.txt   # targets the active series
python generate_character_refs.py
python series_run.py 1
```

`generate_cast.py` reads the series' curriculum/theme, designs a learner protagonist plus a few
recurring characters (personalities, speech styles, appearances), and assigns real ElevenLabs
voice IDs from the project's voice pool by gender/age. Options: `--count N`, a free-text theme
hint, `--series <slug>`. It backs up any existing `cast.json`.

**Switching series.** The active series is remembered in `series/.active`. Every command prints
which series it's using (`📂 Series: …`).

```bash
python series_use.py                       # show the active series + list all
python series_use.py everyday-spoken-finnish-a1   # switch to a named series
python series_use.py default               # back to the default flat series/
```

You can still override per-command with `--series <slug>` (it wins over the active series).

### Managing the cast & episodes

- **Add an episode:** append an object to `series/episodes.json` → `episodes`; set `characters`
  to a list of cast ids.
- **New recurring character:** add an entry to `series/cast.json` → `characters` (with `voice_id`
  + `appearance`), then `python generate_character_refs.py <id>`.
- **One-off character:** inline a full character object directly in an episode's `characters`
  list instead of an id.
- **Change a voice or look:** edit `voice_id` / `appearance` in `cast.json` (re-run
  `generate_character_refs.py --force` for the look).
- **Lock character looks (once):** `python generate_character_refs.py` generates a portrait per
  character from its `appearance`; `--force` regenerates, or pass specific ids.

### Advanced: run series steps manually

`series_run.py` is just a wrapper. To run steps individually, compile an episode and then run the
pipeline stages, **skipping idea generation**:

```bash
python series_compile.py 1          # episode 1 → ideas.json (also: list | all | "1 4 6")
python generate_scripts.py
python check_finnish_grammar.py
python generate_illustrations.py
python generate_sfx.py
python tts_generator.py
python sfx_mixer.py
python generate_videos.py
python music_mixer.py
```

> **Don't run `generate_ideas_json.py` or `run.py` in Series Mode** — `series_compile.py`
> produces `ideas.json` for you; idea generation would overwrite it with random content.

> **CEFR:** compile **one episode at a time** for accurate per-episode level (the pipeline applies
> a single level per `ideas.json`). Compiling several uses the series default level.

See `series/README.md` for the full design notes.

---

## Idea Mode (one-off)

Generate random conversation or podcast ideas, then run the pipeline.

### 1. Generate ideas
```bash
python generate_ideas_json.py                       # 1 conversation idea (default)
python generate_ideas_json.py 5                     # 5 conversation ideas
python generate_ideas_json.py 3 "at the café"       # 3 ideas about a topic
python generate_ideas_json.py 3 A1 "at the café"    # 3 A1-level ideas about a topic
python generate_ideas_json.py podcast               # podcast ideas
python generate_ideas_json.py podcast 5 B1 "greetings"  # 5 B1-level podcast ideas
```
Output: `ideas.json` or `podcast_ideas.json`.

> **CEFR (optional):** pass `A1`–`C2` (case-insensitive) as any argument. It's recorded in the
> ideas file's `metadata.language_level` and applied automatically during script generation. Lower
> levels use simpler vocabulary/grammar, shorter sentences, and slower delivery.

### 2. Full pipeline in one command
```bash
python run.py                       # defaults
python run.py 5                     # 5 conversation ideas
python run.py 3 A1 "ordering food"  # 3 A1-level ideas about a topic
```
Arguments are auto-detected by shape: a number sets the count, an `A1`–`C2` token sets the level,
any other string is the topic — order doesn't matter. This runs all stages below in sequence.

---

## The media pipeline (shared by both modes)

Both modes produce an `ideas.json` (Series Mode via `series_compile.py`, Idea Mode via
`generate_ideas_json.py`), then run these stages. They can be run individually for debugging.

| # | Command | Does | Output |
|---|---------|------|--------|
| 1 | `python generate_scripts.py` | Convert ideas → spoken-Finnish dialogue (add `podcast` for podcasts). CEFR read from ideas metadata. | `scripts/` (or `podcast_scripts/`) |
| 2 | `python check_finnish_grammar.py` | Fix grammar & make phrasing sound like natural spoken Finnish. | `scripts/` (in place) |
| 3 | `python generate_illustrations.py` | One illustration per script. In Series Mode, uses character reference portraits for consistency. | `illustrations/` |
| 4 | `python generate_sfx.py` | Generate SFX clips from script cues + ambient loops. | `sfx/<slug>/`, `presets/ambience/` |
| 5 | `python tts_generator.py` | Text-to-speech per dialogue line via ElevenLabs (`podcast` / `all` modes available). | `mp3/` |
| 6 | `python sfx_mixer.py` | Whisper-align timestamps, insert pauses, place SFX, overlay ambience. | `mp3/` (in place) |
| 7 | `python generate_videos.py` | Combine audio + illustration into video. | `output_videos/` |
| 8 | `python music_mixer.py` | Add background music — only to videos whose ambient is `quiet`/unset (others keep their ambience). | `output_videos/` |

Optional subtitles: `python generate_subtitled_videos.py` (run manually).

---

## Project structure

### Series scripts
- `series_plan.py` — curriculum → episodes (parse + build, order-preserving grouping)
- `series_new.py` — scaffold a new series under `series/<slug>/` (and make it active)
- `generate_cast.py` — AI-generate a cast (with real voice IDs) fitting the series' curriculum
- `series_use.py` — show or switch the active series
- `series_compile.py` — compile a chosen episode into `ideas.json`
- `series_run.py` — one-command end-to-end builder for a single episode
- `generate_character_refs.py` — generate character reference portraits from `cast.json`
- `series_paths.py` — shared `--series` path resolution

### Pipeline scripts
- `run.py` — full Idea-Mode pipeline runner
- `generate_ideas_json.py` — generate conversation/podcast ideas
- `generate_scripts.py` — ideas → dialogue scripts
- `check_finnish_grammar.py` — fix Finnish grammar & naturalness
- `generate_illustrations.py` — generate illustrations
- `generate_sfx.py` — generate sound effects & ambience (ElevenLabs)
- `tts_generator.py` — text-to-speech (ElevenLabs)
- `sfx_mixer.py` — mix SFX, pauses & ambience (Whisper + pydub)
- `generate_videos.py` — build videos from audio + illustrations
- `music_mixer.py` — add background music

### Utility scripts
- `cefr_levels.py` — CEFR (A1–C2) definitions and per-level prompt guidance
- `cleanup.py` — reset the project by removing generated files
- `subtitle_generator.py` / `generate_subtitled_videos.py` — optional subtitles
- `audio_mixer.py` — audio mixing helpers

### Series data (`series/`)
- `cast.json` — character bible (voice, personality, speech style, appearance, portrait path)
- `episodes.json` — the episode list (generated or hand-written)
- `curriculum.txt` / `curriculum.json` — curriculum input and its normalized form
- `characters/` — one reference portrait per character

## Output folders
- `scripts/`, `podcast_scripts/` — dialogue scripts
- `mp3/` — generated audio
- `illustrations/` — generated illustrations
- `sfx/` — sound effects (per-script subfolders)
- `presets/` — background music; `presets/ambience/` — shared ambient loops (auto-generated)
- `output_videos/` — finished videos (`output_videos/prod/` is preserved by cleanup)

## Cleanup
```bash
python cleanup.py
```
Removes generated ideas, scripts, audio, illustrations, SFX and videos, preserving
`output_videos/prod/` and the series character portraits.

## Requirements
- Python 3.11+
- Google Gemini API key
- ElevenLabs API key (TTS + SFX)
- FFmpeg
