#!/usr/bin/env python3
"""
Sound Effects Generator for Kielo Convo Generator

Reads conversation scripts from scripts/ and generates SFX clips
using ElevenLabs text-to-sound-effects API. Also generates ambient
background sounds if the idea has an ambient_setting.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# --- Configuration ---
SCRIPTS_DIR = Path("scripts")
SFX_DIR = Path("sfx")

# --- Load environment variables ---
load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")


def extract_sfx_entries(dialogue_list: list) -> list:
    """Extract all SFX entries from a dialogue list, preserving their index position."""
    sfx_entries = []
    for i, item in enumerate(dialogue_list):
        if item.get("type") == "sfx":
            sfx_entries.append({
                "index": i,
                "text": item.get("text", ""),
                "duration": item.get("duration", 2.0),
            })
    return sfx_entries


def generate_sfx_clip(client: ElevenLabs, text: str, duration: float, output_path: Path) -> bool:
    """Generate a single SFX clip using ElevenLabs API."""
    try:
        # Clamp duration to API limits (0.5-30 seconds)
        duration = max(0.5, min(30.0, duration))
        
        print(f"   🔊 Generating SFX: \"{text}\" ({duration}s)")
        
        audio_stream = client.text_to_sound_effects.convert(
            text=text,
            duration_seconds=duration,
            output_format="mp3_44100_128",
        )
        audio_bytes = b"".join(audio_stream)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        
        print(f"   ✅ Saved: {output_path}")
        return True
        
    except Exception as e:
        print(f"   ❌ SFX generation error: {e}")
        return False


def generate_ambient_clip(client: ElevenLabs, text: str, output_path: Path) -> bool:
    """Generate a loopable ambient background sound."""
    try:
        print(f"   🌍 Generating ambient: \"{text}\" (30s, looped)")
        
        audio_stream = client.text_to_sound_effects.convert(
            text=text,
            duration_seconds=30.0,
            loop=True,
            output_format="mp3_44100_128",
        )
        audio_bytes = b"".join(audio_stream)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        
        print(f"   ✅ Saved ambient: {output_path}")
        return True
        
    except Exception as e:
        print(f"   ❌ Ambient generation error: {e}")
        return False


def process_script(client: ElevenLabs, script_path: Path) -> bool:
    """Process a single script file: extract SFX entries and generate clips."""
    
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"   ❌ Error reading {script_path.name}: {e}")
        return False
    
    dialogue_list = data.get("dialogue_list", [])
    idea = data.get("idea", {})
    ambient_setting = idea.get("ambient_setting", "")
    slug = script_path.stem
    sfx_folder = SFX_DIR / slug
    
    # Extract SFX entries
    sfx_entries = extract_sfx_entries(dialogue_list)
    
    if not sfx_entries and not ambient_setting:
        print(f"   ℹ️  No SFX entries or ambient setting in {script_path.name}, skipping")
        return True
    
    had_errors = False
    
    # Generate punctual SFX clips
    if sfx_entries:
        print(f"   📋 Found {len(sfx_entries)} SFX entries")
        for i, sfx in enumerate(sfx_entries):
            output_path = sfx_folder / f"sfx_{sfx['index']}.mp3"
            if not generate_sfx_clip(client, sfx["text"], sfx["duration"], output_path):
                had_errors = True
    
    # Generate ambient clip if ambient_setting is present
    if ambient_setting:
        ambient_path = sfx_folder / "ambient.mp3"
        if not generate_ambient_clip(client, ambient_setting, ambient_path):
            had_errors = True
    
    return not had_errors


def main():
    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found. Please add it to your .env file.")
        sys.exit(1)
    
    client = ElevenLabs(api_key=api_key)
    
    if not SCRIPTS_DIR.exists():
        print(f"❌ Scripts folder '{SCRIPTS_DIR}' not found.")
        sys.exit(1)
    
    script_files = list(SCRIPTS_DIR.glob("*.json"))
    
    if not script_files:
        print(f"⚠️ No script files found in '{SCRIPTS_DIR}/'")
        sys.exit(1)
    
    print(f"\n🔊 Found {len(script_files)} script(s) for SFX generation\n")
    
    had_errors = False
    for script_file in script_files:
        print(f"🎬 Processing: {script_file.name}")
        if not process_script(client, script_file):
            had_errors = True
        print()
    
    if had_errors:
        print("❌ SFX generation completed with errors!")
        sys.exit(1)
    
    print("✅ All SFX generated successfully!")


if __name__ == "__main__":
    main()
