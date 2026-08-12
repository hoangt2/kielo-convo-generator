#!/usr/bin/env python3
"""
Rebuild an ENTIRE series from scratch, one episode at a time.

Loops series_run.py over every episode id in the series' episodes.json (or a
subset you pass), so each episode goes through the full pipeline
(compile -> script -> grammar -> illustration -> sfx -> tts -> mix -> video -> music)
and lands in series/<slug>/output/. A failure in one episode is logged and the
rebuild continues with the next one.

Usage:
    python rebuild_series.py --series everyday-swedish-a1            # all episodes
    python rebuild_series.py --series everyday-swedish-a1 1 2 3      # only these ids
    python rebuild_series.py --series everyday-swedish-a1 --from 9   # ids >= 9
"""

import json
import subprocess
import sys
from pathlib import Path

import series_paths

BASE = Path(__file__).parent


def main():
    slug, raw = series_paths.parse_series_arg(sys.argv[1:])
    paths = series_paths.resolve(slug)
    series_paths.announce(paths.slug)

    episodes = json.loads(paths.episodes.read_text(encoding="utf-8"))["episodes"]
    all_ids = [ep["id"] for ep in episodes]

    # Optional --from N lower bound
    start_from = None
    ids_arg = []
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == "--from" and i + 1 < len(raw):
            start_from = int(raw[i + 1]); i += 2; continue
        if a.isdigit():
            ids_arg.append(int(a))
        i += 1

    if ids_arg:
        ids = [i for i in ids_arg if i in all_ids]
    elif start_from is not None:
        ids = [i for i in all_ids if i >= start_from]
    else:
        ids = all_ids

    print(f"\n🎬 Rebuilding {len(ids)} episode(s): {ids}\n")

    results = []
    for ep_id in ids:
        print("\n" + "#" * 70)
        print(f"# EPISODE {ep_id}  ({ids.index(ep_id)+1}/{len(ids)})")
        print("#" * 70)
        cmd = [sys.executable, "series_run.py", str(ep_id), "--series", paths.slug]
        rc = subprocess.run(cmd, cwd=BASE).returncode
        results.append((ep_id, rc))
        print(f"{'✅' if rc == 0 else '❌'} Episode {ep_id} finished (exit {rc}).")

    print("\n" + "=" * 70)
    print("REBUILD SUMMARY")
    print("=" * 70)
    ok = [e for e, rc in results if rc == 0]
    bad = [e for e, rc in results if rc != 0]
    print(f"✅ Succeeded ({len(ok)}): {ok}")
    if bad:
        print(f"❌ Failed ({len(bad)}): {bad}")
    print(f"\nVideos in: {(paths.base / 'output').relative_to(BASE)}/")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
