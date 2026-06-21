# Series system — "Aisha at the Office"

A thin layer on top of the existing pipeline for producing a **recurring-cast** Finnish
conversation series. Same characters, same voices, same faces across every episode.

The existing pipeline is **idea-driven**: `generate_ideas_json.py` invents random characters
and scenarios each run. A series needs the opposite — a fixed cast and a fixed episode list.
This folder provides that, and `series_compile.py` feeds it into the pipeline you already have.

## Files

| File | What it is |
|------|------------|
| `cast.json` | **Character bible.** One canonical entry per character: `voice_id`, personality, `speech_style`, `appearance`, `reference_image`. The `id` keys (e.g. `aisha`) are what episodes reference. |
| `episodes.json` | **The episode list.** Your 9 scenarios as data — title, description, which cast members appear, target phrases, ambient setting, CEFR level. Edit/add/reorder freely. |
| `characters/` | One reference portrait per character (see its README). |
| `../series_compile.py` | Bridge: resolves an episode's cast and writes a standard `ideas.json`. |
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

## Managing & modifying episodes

- **Add an episode:** append an object to `episodes.json` → `episodes`. Set `characters` to a
  list of cast ids. Done — it shows up in `series_compile.py list`.
- **New recurring character:** add an entry to `cast.json` → `characters`, give it a `voice_id`
  and `appearance`, then `python generate_character_refs.py <id>`.
- **One-off character** (no recurring need): you can inline a full character object directly in
  an episode's `characters` list instead of an id.
- **Change a voice / look:** edit `voice_id` or `appearance` in `cast.json`. Re-run
  `generate_character_refs.py --force` for the look.

## Visual consistency — the one remaining wire-up

`generate_illustrations.py` currently builds each image from a text prompt with **no reference
image**, so faces drift between episodes. To anchor them, pass each present character's
`reference_image` into the model alongside the prompt. `gemini-2.5-flash-image` accepts images
in `contents` and will keep the characters on-model.

Minimal change inside `generate_illustration_from_json(...)`, after the prompt is built:

```python
from PIL import Image

# Collect reference portraits for the characters in this script
ref_images = []
for c in data.get("idea", {}).get("characters", []):
    ref_path = c.get("reference_image")
    if ref_path and os.path.exists(ref_path):
        ref_images.append(Image.open(ref_path))

# Prepend a short instruction so the model treats them as identity references
contents = [prompt]
if ref_images:
    contents = [
        "Use the following reference portrait(s) for the characters' appearance — "
        "keep faces, hair, and clothing consistent with them:",
        *ref_images,
        prompt,
    ]

response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
```

`series_compile.py` already carries `reference_image` onto each character in `ideas.json`, so
once the portraits exist this just works. (Left as an opt-in edit so the current illustrator
keeps behaving exactly as before until you choose to switch it on.)

## Voices to fill in

`cast.json` ships with placeholder `voice_id`s (`REPLACE_WITH_ELEVENLABS_VOICE_ID`) for the new
characters. Sari reuses the existing ID from the old `ideas.json`. Paste your ElevenLabs voice
IDs into `cast.json` and every episode picks them up automatically.
