#!/usr/bin/env python3
"""
Generate a reference portrait for each character once, in the locked series style.

These portraits are the anchor for visual consistency: feed them back into the episode
illustrator (generate_illustrations.py) as reference images so Aisha, Sari, etc. look the
same in every video. Run this ONCE (or whenever you change a character's `appearance`).

Usage:
    python generate_character_refs.py              # generate any missing portraits
    python generate_character_refs.py --force      # regenerate all
    python generate_character_refs.py aisha mikko  # only these character ids

Output: series/characters/<id>.png  (paths already recorded in cast.json -> reference_image)
"""

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

BASE = Path(__file__).parent
CAST_PATH = BASE / "series" / "cast.json"
OUT_DIR = BASE / "series" / "characters"
MODEL_NAME = "gemini-2.5-flash-image"

import json

# Use the EXACT same art style as the episode illustrator (single source of truth),
# so reference portraits match the videos. Falls back to cast.json `style_lock`.
try:
    from generate_illustrations import ILLUSTRATION_STYLE as ART_STYLE
except Exception:
    ART_STYLE = None

SAFETY = [
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
]


def build_prompt(char, style):
    return (
        f"Full-body character reference sheet, single character, standing, shown head to toe with "
        f"the entire figure visible including legs and feet, neutral relaxed pose, facing the viewer, "
        f"plain background. {style} "
        f"Character: {char['appearance']} "
        f"This is a model sheet for a recurring character in a series — make the design clear, "
        f"distinct and easy to reproduce. Do not include any text, labels, or words."
    )


def generate_portrait(client, char_id, char, style):
    prompt = build_prompt(char, style)
    print(f"\n🎨 {char_id} ({char['name']})")
    config = types.GenerateContentConfig(
        response_modalities=[types.Modality.IMAGE],
        image_config=types.ImageConfig(aspect_ratio="3:4"),
        safety_settings=SAFETY,
    )
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=[prompt], config=config)
    except Exception as e:
        print(f"   ❌ API error: {e}")
        return False

    if not response.candidates or response.candidates[0].content is None:
        print("   ⚠️  No image returned (possible safety block). Skipping.")
        return False

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUT_DIR / f"{char_id}.png"
            Image.open(BytesIO(part.inline_data.data)).save(out_path)
            print(f"   ✅ Saved {out_path.relative_to(BASE)}")
            return True

    print("   ⚠️  No image data in response.")
    return False


def main():
    with open(CAST_PATH, "r", encoding="utf-8") as f:
        cast = json.load(f)
    style = ART_STYLE or cast.get("style_lock", "")
    characters = cast["characters"]

    args = [a for a in sys.argv[1:]]
    force = "--force" in args
    ids = [a for a in args if not a.startswith("--")]
    if not ids:
        ids = list(characters.keys())

    client = genai.Client()
    print(f"✅ Gemini client ready. Generating {len(ids)} reference portrait(s).")

    for char_id in ids:
        if char_id not in characters:
            print(f"⚠️  Skipping unknown id '{char_id}'.")
            continue
        out_path = OUT_DIR / f"{char_id}.png"
        if out_path.exists() and not force:
            print(f"\n⏭️  {char_id}: already exists (use --force to regenerate).")
            continue
        generate_portrait(client, char_id, characters[char_id], style)

    print("\n🏁 Done. Reference portraits are in series/characters/.")


if __name__ == "__main__":
    main()
