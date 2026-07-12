#!/usr/bin/env python3
"""
One-command, end-to-end runner for a SINGLE series episode.

Usage:
    python series_run.py 1            # build episode 1 all the way to a final video
    python series_run.py 4 --keep     # don't clean previous outputs first
    python series_run.py 1 --no-refs  # skip character-portrait generation

Pipeline:
    0. cleanup            (safe — never touches series/characters/)
    1. character refs     (generate any MISSING portraits for this episode's cast)
    2. compile episode    (series_compile.py -> ideas.json)
    3. scripts -> check Finnish -> illustrations -> sfx -> tts -> mix sfx -> video -> music

Final video lands in output_videos/.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from cleanup import cleanup
import series_paths

BASE = Path(__file__).parent


def run_step(script, description, args=None):
    """Run one pipeline step; return True on success."""
    cmd = [sys.executable, script] + (args or [])
    print(f"\n{'='*60}\n🚀 {description}\n   Running: {' '.join(cmd[1:])}\n{'='*60}")
    result = subprocess.run(cmd, cwd=BASE)
    if result.returncode != 0:
        print(f"\n❌ {script} failed (exit {result.returncode}).")
        return False
    print(f"✅ {script} done.")
    return True


def load_episode(episodes_path, ep_id):
    if not episodes_path.exists():
        sys.exit(f"❌ Not found: {episodes_path}")
    data = json.loads(episodes_path.read_text(encoding="utf-8"))
    for ep in data["episodes"]:
        if ep["id"] == ep_id:
            return ep
    sys.exit(f"❌ Episode {ep_id} not in {episodes_path.name}. Run: python series_compile.py list")


def main():
    slug, raw = series_paths.parse_series_arg(sys.argv[1:])
    paths = series_paths.resolve(slug)
    series_paths.announce(paths.slug)
    # Forward the EFFECTIVE slug (explicit or active) to the subprocess steps.
    series_flag = ["--series", paths.slug] if paths.slug else []

    keep = "--keep" in raw
    do_refs = "--no-refs" not in raw
    ids = [a for a in raw if not a.startswith("--")]

    if len(ids) != 1 or not ids[0].isdigit():
        sys.exit("Usage: python series_run.py <episode_id> [--series slug] [--keep] [--no-refs]")
    ep_id = int(ids[0])
    episode = load_episode(paths.episodes, ep_id)

    print("\n" + "=" * 60)
    print(f"🎬 SERIES EPISODE {ep_id}: {episode['title']} ({episode.get('title_en','')})")
    print("=" * 60)

    # 0. Fresh start (keeps character portraits and output_videos/prod/)
    if not keep:
        cleanup()

    # 1. Ensure reference portraits exist for this episode's recurring cast
    if do_refs:
        cast_ids = [c for c in episode["characters"] if isinstance(c, str)]
        if cast_ids and not run_step(
            "generate_character_refs.py",
            "Step 1: Ensuring character reference portraits",
            cast_ids + series_flag,
        ):
            sys.exit(1)

    # 2. Compile this episode into ideas.json
    if not run_step("series_compile.py", f"Step 2: Compiling episode {ep_id}", [str(ep_id)] + series_flag):
        sys.exit(1)

    # 3. The existing pipeline (idea generation is replaced by the compile step above)
    pipeline = [
        ("generate_scripts.py", "Step 3: Generating dialogue script", []),
        ("check_finnish_grammar.py", "Step 4: Checking Finnish grammar & naturalness", []),
        ("generate_illustrations.py", "Step 5: Generating illustration (uses references)", []),
        ("generate_sfx.py", "Step 6: Generating sound effects", []),
        ("tts_generator.py", "Step 7: Generating audio (TTS)", []),
        ("sfx_mixer.py", "Step 8: Mixing sound effects into audio", []),
        ("generate_videos.py", "Step 9: Creating video", []),
        ("music_mixer.py", "Step 10: Adding background music", []),
    ]
    for script, desc, args in pipeline:
        if not run_step(script, desc, args):
            print(f"\n❌ Pipeline stopped at {script}.")
            sys.exit(1)

    # Copy result video(s) into the series output folder
    series_output = paths.base / "output"
    series_output.mkdir(exist_ok=True)
    output_videos = BASE / "output_videos"
    copied = []
    for vid in output_videos.glob("*.mp4"):
        dest = series_output / vid.name
        shutil.copy2(vid, dest)
        copied.append(dest)
        print(f"📦 Copied to series: {dest.relative_to(BASE)}")

    print("\n" + "=" * 60)
    if copied:
        print(f"🎉 EPISODE {ep_id} COMPLETE — see {series_output.relative_to(BASE)}/")
    else:
        print(f"🎉 EPISODE {ep_id} COMPLETE — see output_videos/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
