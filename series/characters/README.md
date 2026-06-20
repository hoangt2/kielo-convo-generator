# Character reference portraits

This folder holds **one reference image per character**. They are the visual anchor that
keeps each character looking the same in every episode.

Expected files (paths are set in `../cast.json` → `reference_image`):

| File | Character |
|------|-----------|
| `aisha.png` | Aisha (protagonist) |
| `sari.png` | Sari (manager) |
| `mikko.png` | Mikko (IT) |
| `elina.png` | Elina (work friend) |
| `kari.png` | Kari (senior colleague) |
| `restaurant_worker.png` | Staff restaurant worker |

## Two ways to fill this folder

**A. Generate them (recommended, matches the locked doodle style):**
```bash
python generate_character_refs.py            # generate any missing
python generate_character_refs.py --force    # regenerate all
python generate_character_refs.py aisha      # just one
```
The look comes from each character's `appearance` text in `cast.json`, rendered in the
**exact same art style as the episode illustrations** (pulled from `generate_illustrations.py`).
Portraits are **full body** (head to toe, 3:4). Edit `appearance`, rerun with `--force` to iterate.

**B. Drop in your own images:** just save a square-ish PNG with the exact filename above.
If you already have art for Aisha and Sari, put them here and only generate the rest.

## How these get used

`series_compile.py` carries each character's `reference_image` path through to the script.
To make the **episode** illustrations actually reference them, wire `generate_illustrations.py`
to pass these images alongside the prompt — see `../README.md` ("Visual consistency").
