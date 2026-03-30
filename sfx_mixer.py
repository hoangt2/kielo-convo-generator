#!/usr/bin/env python3
"""
SFX Mixer for Kielo Convo Generator

Mixes generated sound effects into the dialogue audio with precise timing.
Uses faster-whisper for timestamp alignment and pydub for audio manipulation.

Approach (overlay — never slices the original audio):
1. Whisper detects where each dialogue segment is in the TTS audio
2. Gaps between segments are identified as SFX overlay positions
3. SFX clips are overlaid at gap midpoints (never replacing speech)
4. Pre/post-conversation SFX are prepended/appended
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
    """Overlay SFX onto the original audio without slicing or rearranging speech.
    
    The original TTS audio is kept completely intact. SFX clips are overlaid
    at the midpoints of gaps between Whisper-detected segments. Pre/post
    conversation SFX are prepended/appended as separate audio.
    """
    
    # --- Pre-conversation SFX (prepended before the original audio) ---
    pre_audio = AudioSegment.empty()
    for sfx_info in sfx_positions.get("pre_conversation", []):
        clip = load_sfx_clip(sfx_folder, sfx_info)
        if len(clip) > 0:
            print(f"   🔊 [PRE] \"{sfx_info['text'][:40]}\"")
            pre_audio += clip
            pre_audio += AudioSegment.silent(duration=PAUSE_AFTER_SFX_MS)
    
    # --- Build a map of gap midpoints between dialogue segments ---
    # gap_positions[seg_idx] = midpoint (ms) of the gap BEFORE segment seg_idx
    gap_positions = {}
    for seg_idx in range(1, len(timestamps)):
        prev_end_ms = int(timestamps[seg_idx - 1]["end"] * 1000)
        curr_start_ms = int(timestamps[seg_idx]["start"] * 1000)
        midpoint = (prev_end_ms + curr_start_ms) // 2
        gap_positions[seg_idx] = midpoint
    
    # --- Overlay SFX onto the original audio at gap positions ---
    mixed = original_audio  # start with the intact original
    
    # "before" SFX: overlay at the gap before the target segment
    for seg_idx, sfx_list in sfx_positions.get("before_segment", {}).items():
        if seg_idx in gap_positions:
            pos_ms = gap_positions[seg_idx]
            for sfx_info in sfx_list:
                clip = load_sfx_clip(sfx_folder, sfx_info)
                if len(clip) > 0:
                    # Center the SFX on the gap midpoint
                    overlay_at = max(0, pos_ms - len(clip) // 2)
                    print(f"   🔊 [BEFORE seg {seg_idx}] \"{sfx_info['text'][:40]}\" at {overlay_at}ms")
                    mixed = mixed.overlay(clip, position=overlay_at)
    
    # "after" SFX: overlay at the gap after the target segment
    for seg_idx, sfx_list in sfx_positions.get("after_segment", {}).items():
        next_seg = seg_idx + 1
        if next_seg in gap_positions:
            pos_ms = gap_positions[next_seg]
        else:
            # SFX after the last segment — place at segment end
            pos_ms = int(timestamps[seg_idx]["end"] * 1000)
        for sfx_info in sfx_list:
            clip = load_sfx_clip(sfx_folder, sfx_info)
            if len(clip) > 0:
                overlay_at = max(0, pos_ms - len(clip) // 2)
                # Don't overlay past the audio length
                overlay_at = min(overlay_at, max(0, len(mixed) - len(clip)))
                print(f"   🔊 [AFTER seg {seg_idx}] \"{sfx_info['text'][:40]}\" at {overlay_at}ms")
                mixed = mixed.overlay(clip, position=overlay_at)
    
    # --- Post-conversation SFX (appended after the original audio) ---
    post_audio = AudioSegment.empty()
    for sfx_info in sfx_positions.get("post_conversation", []):
        post_audio += AudioSegment.silent(duration=PAUSE_AFTER_SFX_MS)
        clip = load_sfx_clip(sfx_folder, sfx_info)
        if len(clip) > 0:
            print(f"   🔊 [POST] \"{sfx_info['text'][:40]}\"")
            post_audio += clip
    
    # --- Assemble: pre + original (with overlays) + post ---
    result = AudioSegment.empty()
    if len(pre_audio) > 0:
        result += pre_audio
    result += mixed
    if len(post_audio) > 0:
        result += post_audio
    
    return result


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
    AMBIENCE_DIR = Path("presets") / "ambience"
    if ambient_setting and ambient_setting != "quiet":
        ambient_path = AMBIENCE_DIR / f"{ambient_setting}.mp3"
        if ambient_path.exists():
            print(f"   🌍 Mixing ambient [{ambient_setting}] from library")
            ambient_clip = AudioSegment.from_mp3(str(ambient_path))
            
            # Loop ambient to match mixed audio length
            loops_needed = (len(mixed) // len(ambient_clip)) + 1
            ambient_looped = ambient_clip * loops_needed
            ambient_looped = ambient_looped[:len(mixed)]
            
            # Normalize ambient relative to dialogue volume, then reduce
            # This ensures ambient is always audible regardless of source clip volume
            dialogue_dbfs = mixed.dBFS
            ambient_dbfs = ambient_looped.dBFS
            volume_adjustment = (dialogue_dbfs - ambient_dbfs) + AMBIENT_VOLUME_DB
            ambient_looped = ambient_looped + volume_adjustment
            
            mixed = mixed.overlay(ambient_looped)
            print(f"   ✅ Ambient mixed at {AMBIENT_VOLUME_DB}dB below dialogue (adjusted {volume_adjustment:+.1f}dB)")
        else:
            print(f"   ⚠️  Ambient clip not found: {ambient_path}")
    
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
