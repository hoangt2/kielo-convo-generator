#!/usr/bin/env python3
"""
Show or switch the ACTIVE series.

When a series is active, the other commands (series_compile.py, series_plan.py,
series_run.py, generate_character_refs.py) operate on it without needing --series.

Usage:
    python series_use.py                 # show the active series and list all series
    python series_use.py <slug>          # make series/<slug>/ active
    python series_use.py default         # revert to the default flat series/
"""

import sys

import series_paths


def show():
    active = series_paths.get_active()
    has_default, named = series_paths.list_series()
    print(f"⭐ Active: {active if active else 'default (series/)'}\n")
    print("Available series:")
    if has_default:
        mark = "  " if active else "→ "
        print(f"  {mark}default (series/)")
    for s in named:
        mark = "→ " if s == active else "  "
        print(f"  {mark}{s}")
    if not named:
        print("  (no named sub-series yet — create one with series_new.py)")
    print("\nSwitch with:  python series_use.py <slug> | default")


def main():
    args = sys.argv[1:]
    if not args:
        show()
        return

    target = args[0]
    if target in ("default", "-", "none"):
        series_paths.set_active(None)
        print("✅ Active series: default (series/)")
        return

    if not series_paths._valid_series(target):
        has_default, named = series_paths.list_series()
        opts = ", ".join(named) if named else "(none)"
        sys.exit(f"❌ No series '{target}' (needs series/{target}/cast.json). Available: {opts}")

    series_paths.set_active(target)
    print(f"✅ Active series: {target}")
    print("   Other commands now target it (no --series needed). Revert: python series_use.py default")


if __name__ == "__main__":
    main()
