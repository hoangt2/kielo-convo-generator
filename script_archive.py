"""Archiving for the dialogue scripts behind generated videos.

`cleanup()` wipes `scripts/` before every run, so a script only survives its own
pipeline pass. Whenever a video is rendered we copy its script into
`script_archive/`, named after the video so the two stay paired:

    output_videos/conversation_missa-kirjasto-on.mp4
    script_archive/conversation_missa-kirjasto-on.json

`script_archive/` is never touched by cleanup.
"""

import shutil
from pathlib import Path

BASE = Path(__file__).parent
SCRIPTS_DIR = BASE / "scripts"
ARCHIVE_DIR = BASE / "script_archive"


def slug_for(video_stem):
    """`conversation_foo` -> `foo` (the name generate_scripts.py writes)."""
    return video_stem[len("conversation_"):] if video_stem.startswith("conversation_") else video_stem


def archived_path(video_stem):
    """Where the script for a given video stem lives once archived."""
    return ARCHIVE_DIR / f"{video_stem}.json"


def archive_script(video_stem):
    """Copy the script behind `video_stem` into the archive. Returns the path, or None."""
    source = SCRIPTS_DIR / f"{slug_for(video_stem)}.json"
    if not source.exists():
        return None

    ARCHIVE_DIR.mkdir(exist_ok=True)
    dest = archived_path(video_stem)
    try:
        shutil.copy2(source, dest)
    except OSError as e:
        print(f"   ⚠️  Could not archive script {source.name}: {e}")
        return None
    return dest
