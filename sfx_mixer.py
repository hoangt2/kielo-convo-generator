#!/usr/bin/env python3
"""
SFX Mixer for Kielo Convo Generator

Mixes generated sound effects into the dialogue audio with precise timing.
Uses faster-whisper for timestamp alignment and pydub for audio manipulation.

Approach:
1. Whisper detects where each dialogue segment is in the TTS audio
2. Audio is split at segment boundaries
3. Between segments, natural pauses (silence) are inserted
4. SFX clips are placed before or after segments based on their "timing" field
5. Ambient audio is looped under the entire result

Runs AFTER tts_generator.py and BEFORE generate_videos.py.
"""

import json
import os
import sys
import random
from pathlib import Path
from pydub import AudioSegment

# --- Configuration ---
SCRIPTS_DIR = Path("scripts")
SFX_DIR = Path("sfx")
MP3_DIR = Path("mp3")

# Volume adjustments (in dB)
AMBIENT_VOLUME_DB = -22   # Ambient sounds much quieter than dialogue
SFX_VOLUME_DB = -10       # Punctual SFX noticeably quieter than dialogue

# Pause durations (in ms)
PAUSE_MIN_MS = 400        # Minimum pause between dialogue segments
PAUSE_MAX_MS = 900        # Maximum pause between dialogue segments
PAUSE_AFTER_SFX_MS = 200  # Short pause after an SFX clip before next dialogue


def get_dialogue_timestamps(mp3_path: Path) -> list:
    """Use faster-whisper to get timestamps for each dialogue segment."""
    from faster_whisper import WhisperModel
    
    print(f"   🎙️  Transcribing for timestamp alignment...")
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(mp3_path), language="fi", beam_size=5)
    
    timestamps = []
    for seg in segments:
        timestamps.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        })
    
    print(f"   📍 Found {len(timestamps)} dialogue segments")
    return timestamps


def classify_sfx_positions(dialogue_list: list) -> dict:
    """Map SFX entries to the dialogue segments they belong between.
    
    Returns a dict with:
      - "before_segment": {segment_index: [sfx_entries]} — SFX that play before segment N
      - "after_segment": {segment_index: [sfx_entries]} — SFX that play after segment N
      - "pre_conversation": [sfx_entries] — SFX before any dialogue
      - "post_conversation": [sfx_entries] — SFX after all dialogue
    """
    # Build dialogue-only index mapping
    dialogue_positions = []  # (original_index, dialogue_segment_index)
    seg_idx = 0
    for i, item in enumerate(dialogue_list):
        if item.get("type") != "sfx":
            dialogue_positions.append((i, seg_idx))
            seg_idx += 1
    
    total_dialogue_segments = seg_idx
    
    # Map original indices to segment indices
    orig_to_seg = {orig_i: seg_i for orig_i, seg_i in dialogue_positions}
    
    result = {
        "before_segment": {},
        "after_segment": {},
        "pre_conversation": [],
        "post_conversation": [],
    }
    
    for i, item in enumerate(dialogue_list):
        if item.get("type") != "sfx":
            continue
        
        timing = item.get("timing", "after")  # Default: plays after previous line
        sfx_info = {
            "index": i,
            "text": item.get("text", ""),
            "duration": item.get("duration", 2.0),
            "timing": timing,
        }
        
        # Find the nearest dialogue segments before and after this SFX
        prev_seg = None
        next_seg = None
        
        for orig_i, seg_i in dialogue_positions:
            if orig_i < i:
                prev_seg = seg_i
            if orig_i > i and next_seg is None:
                next_seg = seg_i
        
        if timing == "before":
            if next_seg is not None:
                result["before_segment"].setdefault(next_seg, []).append(sfx_info)
            elif prev_seg is not None:
                # SFX at end with "before" timing — treat as post-conversation
                result["post_conversation"].append(sfx_info)
            else:
                result["pre_conversation"].append(sfx_info)
        else:  # "after"
            if prev_seg is not None:
                result["after_segment"].setdefault(prev_seg, []).append(sfx_info)
            elif next_seg is not None:
                # SFX at start with "after" timing — treat as pre-conversation
                result["pre_conversation"].append(sfx_info)
            else:
                result["pre_conversation"].append(sfx_info)
    
    return result, total_dialogue_segments


def load_sfx_clip(sfx_folder: Path, sfx_info: dict) -> AudioSegment:
    """Load and volume-adjust an SFX clip."""
    sfx_file = sfx_folder / f"sfx_{sfx_info['index']}.mp3"
    
    if not sfx_file.exists():
        print(f"   ⚠️  SFX file not found: {sfx_file.name}")
        return AudioSegment.silent(duration=0)
    
    clip = AudioSegment.from_mp3(str(sfx_file))
    clip = clip + SFX_VOLUME_DB
    return clip


def build_mixed_audio(
    original_audio: AudioSegment,
    timestamps: list,
    sfx_positions: dict,
    sfx_folder: Path,
) -> AudioSegment:
    """Reconstruct audio with pauses between segments and SFX placed precisely."""
    
    new_audio = AudioSegment.empty()
    
    # --- Pre-conversation SFX ---
    for sfx_info in sfx_positions.get("pre_conversation", []):
        clip = load_sfx_clip(sfx_folder, sfx_info)
        if len(clip) > 0:
            print(f"   🔊 [PRE] \"{sfx_info['text'][:40]}\"")
            new_audio += clip
            new_audio += AudioSegment.silent(duration=PAUSE_AFTER_SFX_MS)
    
    # --- Process each dialogue segment ---
    for seg_idx, seg in enumerate(timestamps):
        start_ms = int(seg["start"] * 1000)
        end_ms = int(seg["end"] * 1000)
        
        # Clamp to audio bounds
        start_ms = max(0, start_ms)
        end_ms = min(len(original_audio), end_ms)
        
        segment_audio = original_audio[start_ms:end_ms]
        
        # --- SFX with timing "before" this segment ---
        before_sfx = sfx_positions.get("before_segment", {}).get(seg_idx, [])
        for sfx_info in before_sfx:
            clip = load_sfx_clip(sfx_folder, sfx_info)
            if len(clip) > 0:
                print(f"   🔊 [BEFORE seg {seg_idx}] \"{sfx_info['text'][:40]}\"")
                new_audio += clip
                new_audio += AudioSegment.silent(duration=PAUSE_AFTER_SFX_MS)
        
        # --- Add natural pause between segments (not before the first one) ---
        if seg_idx > 0 and not before_sfx:
            pause_ms = random.randint(PAUSE_MIN_MS, PAUSE_MAX_MS)
            new_audio += AudioSegment.silent(duration=pause_ms)
        
        # --- Add the dialogue segment ---
        new_audio += segment_audio
        
        # --- SFX with timing "after" this segment ---
        after_sfx = sfx_positions.get("after_segment", {}).get(seg_idx, [])
        for sfx_info in after_sfx:
            # Small pause before the SFX
            new_audio += AudioSegment.silent(duration=PAUSE_AFTER_SFX_MS)
            clip = load_sfx_clip(sfx_folder, sfx_info)
            if len(clip) > 0:
                print(f"   🔊 [AFTER seg {seg_idx}] \"{sfx_info['text'][:40]}\"")
                new_audio += clip
    
    # --- Post-conversation SFX ---
    for sfx_info in sfx_positions.get("post_conversation", []):
        new_audio += AudioSegment.silent(duration=PAUSE_AFTER_SFX_MS)
        clip = load_sfx_clip(sfx_folder, sfx_info)
        if len(clip) > 0:
            print(f"   🔊 [POST] \"{sfx_info['text'][:40]}\"")
            new_audio += clip
    
    return new_audio


def mix_sfx_into_audio(mp3_path: Path, script_path: Path, sfx_folder: Path) -> bool:
    """Mix SFX clips and ambient audio into the dialogue MP3."""
    
    # Load the dialogue audio
    original_audio = AudioSegment.from_mp3(str(mp3_path))
    print(f"   🎵 Original dialogue duration: {len(original_audio) / 1000:.1f}s")
    
    # Load script data
    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    dialogue_list = data.get("dialogue_list", [])
    idea = data.get("idea", {})
    ambient_setting = idea.get("ambient_setting", "")
    
    # Check if there are any SFX entries
    has_sfx = any(item.get("type") == "sfx" for item in dialogue_list)
    
    if has_sfx:
        # Get Whisper timestamps
        timestamps = get_dialogue_timestamps(mp3_path)
        
        if timestamps:
            # Classify SFX positions
            sfx_positions, total_segments = classify_sfx_positions(dialogue_list)
            
            # Reconstruct audio with pauses and SFX
            mixed = build_mixed_audio(original_audio, timestamps, sfx_positions, sfx_folder)
            print(f"   ⏱️  New duration with pauses+SFX: {len(mixed) / 1000:.1f}s")
        else:
            print("   ⚠️  No timestamps found, adding pauses only")
            mixed = original_audio
    else:
        # No SFX entries, but still add basic pauses
        print("   ℹ️  No SFX entries, using original audio")
        mixed = original_audio
    
    # --- Overlay ambient background if available ---
    ambient_path = sfx_folder / "ambient.mp3"
    if ambient_setting and ambient_path.exists():
        print(f"   🌍 Mixing ambient: \"{ambient_setting[:50]}...\"")
        ambient_clip = AudioSegment.from_mp3(str(ambient_path))
        
        # Loop ambient to match mixed audio length
        loops_needed = (len(mixed) // len(ambient_clip)) + 1
        ambient_looped = ambient_clip * loops_needed
        ambient_looped = ambient_looped[:len(mixed)]
        
        # Reduce volume and overlay
        ambient_looped = ambient_looped + AMBIENT_VOLUME_DB
        mixed = mixed.overlay(ambient_looped)
        print(f"   ✅ Ambient mixed at {AMBIENT_VOLUME_DB}dB")
    
    # --- Export ---
    mixed.export(str(mp3_path), format="mp3", bitrate="128k")
    print(f"   ✅ Saved mixed audio: {mp3_path.name} ({len(mixed) / 1000:.1f}s)")
    
    return True


def main():
    if not SCRIPTS_DIR.exists() or not MP3_DIR.exists():
        print("❌ Required folders (scripts/, mp3/) not found.")
        sys.exit(1)
    
    script_files = list(SCRIPTS_DIR.glob("*.json"))
    
    if not script_files:
        print("⚠️ No script files found.")
        sys.exit(1)
    
    print(f"\n🎚️  SFX Mixer — Processing {len(script_files)} script(s)\n")
    
    had_errors = False
    processed = 0
    
    for script_file in script_files:
        slug = script_file.stem
        sfx_folder = SFX_DIR / slug
        
        # Find the matching MP3 (conversation_<slug>.mp3)
        mp3_path = MP3_DIR / f"conversation_{slug}.mp3"
        
        if not mp3_path.exists():
            print(f"⚠️  No MP3 found for {script_file.name} (expected {mp3_path.name}), skipping")
            continue
        
        print(f"🎬 Mixing SFX for: {script_file.name}")
        try:
            if not mix_sfx_into_audio(mp3_path, script_file, sfx_folder):
                had_errors = True
            processed += 1
        except Exception as e:
            print(f"   ❌ Error mixing SFX for {script_file.name}: {e}")
            had_errors = True
        print()
    
    if processed == 0:
        print("ℹ️  No scripts required SFX mixing.")
    elif had_errors:
        print("❌ SFX mixing completed with errors!")
        sys.exit(1)
    else:
        print(f"✅ SFX mixing complete for {processed} script(s)!")


if __name__ == "__main__":
    main()
