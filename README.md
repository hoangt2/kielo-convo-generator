# Convo Generator

A Python tool for generating Finnish conversation scripts and podcast episodes using Google Gemini AI, with support for TTS, sound effects, video generation, and background music. Scripts can be targeted to a CEFR language level (A1–C2).

## Setup

### 1. Create a virtual environment

**Mac/Linux:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **Note:** Python 3.11 is recommended. Python 3.14 may have compatibility issues with some dependencies.

### 2. Configure environment

Create a `.env` file in the project root with your API keys:
```
GEMINI_API_KEY=your_gemini_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

## Quick Start

### 1. Generate Ideas
```bash
python generate_ideas_json.py                      # 1 conversation idea (default)
python generate_ideas_json.py 5                    # 5 conversation ideas
python generate_ideas_json.py 3 "at the café"     # 3 ideas about a specific topic
python generate_ideas_json.py 3 A1 "at the café"  # 3 A1-level ideas about a topic
python generate_ideas_json.py podcast              # Podcast ideas
python generate_ideas_json.py podcast 5 "greetings"  # 5 podcast ideas about greetings
python generate_ideas_json.py podcast 5 B1 "greetings"  # 5 B1-level podcast ideas
```
Output: `ideas.json` or `podcast_ideas.json`

> **CEFR language level (optional):** Pass a level — `A1`, `A2`, `B1`, `B2`, `C1`, or `C2` (case-insensitive) — as any argument to target a learner level. The level is recorded in the ideas file's `metadata.language_level` and automatically applied when generating scripts. Lower levels use simpler vocabulary and grammar, shorter sentences, and slower delivery; higher levels grow progressively more natural and complex. If omitted, behavior is unchanged.

### 2. Generate Scripts
```bash
python generate_scripts.py                   # Conversation scripts
python generate_scripts.py podcast           # Podcast scripts
```
Output: JSON dialogue files in `scripts/` or `podcast_scripts/`

> The CEFR level is read automatically from the ideas file's `metadata.language_level` (set in step 1) — no extra argument needed here.

### 3. Check Finnish Grammar
```bash
python check_finnish_grammar.py              # Fix grammar & make Finnish natural
```
This step reviews all scripts and fixes unnatural phrasing to sound like spoken Finnish.

### 4. Generate Illustrations
```bash
python generate_illustrations.py             # Generate visual assets for videos
```
Output: Illustration files in `illustrations/`

### 5. Generate Sound Effects
```bash
python generate_sfx.py                       # Generate SFX clips from script cues
```
Reads SFX entries from dialogue scripts and generates audio clips via ElevenLabs. Also generates ambient background loops (stored in `presets/ambience/` for reuse).

Output: SFX clips in `sfx/<script-slug>/`

### 6. Generate Audio
```bash
python tts_generator.py                      # Convert scripts to MP3
```
Output: Audio files in `mp3/`

### 7. Mix Sound Effects
```bash
python sfx_mixer.py                          # Mix SFX & ambient into dialogue audio
```
Uses Whisper for timestamp alignment, inserts natural pauses between dialogue segments, places SFX clips at their scripted positions, and overlays ambient backgrounds.

Output: Updated audio files in `mp3/` (in-place)

### 8. Generate Videos
```bash
python generate_videos.py                    # Create video from audio + illustrations
```
Output: Videos in `output_videos/`

### 9. Add Music
```bash
python music_mixer.py                        # Add background music (randomly selected from presets/)
```
Only adds BGM to videos whose ambient setting is "quiet" or unset. Videos with ambient sounds (e.g. café, street) are skipped.

Output: Final videos with music in `output_videos/`

## Full Pipeline

Run the complete pipeline with a single command:
```bash
python run.py                         # Run with defaults
python run.py 5                       # Generate 5 conversation ideas
python run.py 3 "ordering food"       # Generate 3 ideas about a topic
python run.py 3 A1 "ordering food"    # Generate 3 A1-level ideas about a topic
```

Arguments are auto-detected by shape: a number sets the count, an `A1`–`C2` token sets the CEFR level, and any other string is the topic — order doesn't matter.

This runs all 9 steps in sequence:
1. Generate ideas → 2. Generate scripts → 3. Check Finnish → 4. Generate illustrations → 5. Generate SFX → 6. TTS audio → 7. Mix SFX → 8. Create videos → 9. Add music

**Or run each step manually:**
```bash
python generate_ideas_json.py
python generate_scripts.py
python check_finnish_grammar.py
python generate_illustrations.py
python generate_sfx.py
python tts_generator.py
python sfx_mixer.py
python generate_videos.py
python music_mixer.py
```

## Series Mode (recurring cast & episodes)

The default pipeline is **idea-driven** — `generate_ideas_json.py` invents random characters and scenarios each run. **Series Mode** is the opposite: a fixed cast and a fixed episode list, so the same characters (with the same voices and faces) recur across every video. It lives in the `series/` folder and feeds into the existing pipeline.

### Files

| File | What it is |
|------|------------|
| `series/cast.json` | **Character bible** — one canonical entry per character (`voice_id`, personality, `speech_style`, `appearance`, reference-image path). The `id` keys (e.g. `aisha`) are what episodes reference. |
| `series/episodes.json` | **The episode list** — each scenario as data (title, description, which cast appears, key phrases, ambient setting, CEFR level). Edit/add/reorder freely. |
| `series/characters/` | One reference portrait per character (anchors the visual look). |
| `series_compile.py` | Bridge — turns a chosen episode into the `ideas.json` the pipeline already consumes. |
| `generate_character_refs.py` | Generates the reference portraits from `cast.json`. |

### Workflow

```bash
# 0. (once) lock each character's look — reads appearance from cast.json
python generate_character_refs.py
python generate_character_refs.py --force      # regenerate all
python generate_character_refs.py aisha mikko  # only specific characters

# 1. pick episode(s) -> writes ideas.json  (REPLACES generate_ideas_json.py)
python series_compile.py            # list the episode menu
python series_compile.py list       # same — list episodes
python series_compile.py 1          # compile episode 1
python series_compile.py 1 4 6      # compile several
python series_compile.py all        # compile every episode

# 2. run the rest of the pipeline, SKIPPING step 1 (idea generation)
python generate_scripts.py
python check_finnish_grammar.py
python generate_illustrations.py
python generate_sfx.py
python tts_generator.py
python sfx_mixer.py
python generate_videos.py
python music_mixer.py
```

> **Do not run `generate_ideas_json.py` (or `run.py`) in Series Mode** — `series_compile.py` produces `ideas.json` for you. Running idea generation would overwrite it with random content.

> **CEFR level:** compile **one episode at a time** for accurate per-episode level (the pipeline applies a single level per `ideas.json`). Compiling several uses the series default level from `episodes.json`.

### What keeps it consistent

- **Voice** — each character has one `voice_id` in `cast.json`; every episode reuses it (the pipeline keys TTS on `voice_id`). Fill in the `REPLACE_WITH_ELEVENLABS_VOICE_ID` placeholders with your ElevenLabs voice IDs.
- **Personality / register** — each character's `speech_style` (e.g. careful `Minä/Sinä` vs. spoken `Mä/Sä`) is folded into the script prompt automatically.
- **Face** — one reference portrait per character in `series/characters/`, reused as an image reference per episode.

### Managing episodes

- **Add an episode:** append an object to `series/episodes.json` → `episodes` and set `characters` to a list of cast ids.
- **New recurring character:** add an entry to `series/cast.json` → `characters` (with `voice_id` + `appearance`), then `python generate_character_refs.py <id>`.
- **One-off character:** inline a full character object directly in an episode's `characters` list instead of an id.
- **Change a voice or look:** edit `voice_id` / `appearance` in `cast.json` (re-run `generate_character_refs.py --force` for the look).

### Series Run (one-command episode builder)

Instead of running each step manually, `series_run.py` builds a single episode end-to-end with one command:

```bash
python series_run.py 1            # build episode 1 all the way to a final video
python series_run.py 4 --keep     # don't clean previous outputs first
python series_run.py 1 --no-refs  # skip character-portrait generation
```

Pipeline executed by `series_run.py`:

0. **Cleanup** — removes previous outputs (safe — never touches `series/characters/`)
1. **Character refs** — generates any missing portraits for this episode's cast
2. **Compile episode** — `series_compile.py` → `ideas.json`
3. **Full pipeline** — scripts → check Finnish → illustrations → SFX → TTS → mix SFX → video → music

| Flag | Effect |
|------|--------|
| `--keep` | Skip the cleanup step (keep previous outputs) |
| `--no-refs` | Skip character-portrait generation |

Final video lands in `output_videos/`.

See `series/README.md` for the full design notes, including the one optional edit to wire the reference portraits into episode illustrations.

## Cleanup

Reset the project by removing all generated files:
```bash
python cleanup.py
```
This removes generated ideas, scripts, audio, and video files while preserving `output_videos/prod/`.

## Project Structure

### Pipeline Scripts
- `run.py` - **Full pipeline runner** (runs all steps in sequence)
- `generate_ideas_json.py` - Generate conversation/podcast ideas via Gemini
- `generate_scripts.py` - Convert ideas into dialogue scripts
- `check_finnish_grammar.py` - Check & fix Finnish grammar and naturalness
- `generate_illustrations.py` - Generate visual assets
- `generate_sfx.py` - Generate sound effects & ambient clips (ElevenLabs SFX)
- `tts_generator.py` - Generate audio from scripts (ElevenLabs TTS)
- `sfx_mixer.py` - Mix SFX, pauses & ambient audio into dialogue (Whisper + pydub)
- `generate_videos.py` - Create videos from audio + illustrations
- `music_mixer.py` - Add background music to videos

### Utility Scripts
- `cefr_levels.py` - CEFR level (A1–C2) definitions and per-level prompt guidance
- `cleanup.py` - Reset project by removing generated files
- `subtitle_generator.py` - Subtitle generation helper functions
- `generate_subtitled_videos.py` - Create subtitled videos (optional, run manually)
- `audio_mixer.py` - Audio mixing utilities

## Output Folders

- `scripts/` - Conversation dialogue files
- `podcast_scripts/` - Podcast script files
- `mp3/` - Generated audio files
- `illustrations/` - Generated visual assets
- `sfx/` - Generated sound effects (per-script subfolders)
- `presets/` - Background music files
- `presets/ambience/` - Ambient background loops (shared library, auto-generated)
- `output_videos/` - Final videos with music

## Requirements

- Python 3.11+
- Google Gemini API key
- ElevenLabs API key (for TTS and SFX)
- FFmpeg (for video/audio processing)
