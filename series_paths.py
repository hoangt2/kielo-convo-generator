"""Shared path resolution for the series tooling.

A series lives in a folder containing `cast.json`, `episodes.json`, a `characters/`
directory and (optionally) curriculum files. There are two layouts:

  * Default / legacy:  series/            (the original "Aisha at the Office" series)
  * Named series:      series/<slug>/     (any additional series)

All series scripts accept an optional `--series <slug>` (or `--series=<slug>`). When
omitted, they operate on the default flat `series/` folder, so existing commands keep
working unchanged.
"""

from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).parent
SERIES_ROOT = BASE / "series"
# Pointer to the currently-active named series. When set (and valid), commands without an
# explicit --series operate on it instead of the default flat series/.
ACTIVE_FILE = SERIES_ROOT / ".active"


def _valid_series(slug):
    """A slug is usable only if series/<slug>/cast.json exists."""
    return bool(slug) and (SERIES_ROOT / slug / "cast.json").exists()


def get_active():
    """Return the active series slug, or None for the default flat series."""
    if ACTIVE_FILE.exists():
        slug = ACTIVE_FILE.read_text(encoding="utf-8").strip()
        if _valid_series(slug):
            return slug
    return None


def set_active(slug):
    """Set (or clear, when slug is falsy) the active series."""
    SERIES_ROOT.mkdir(parents=True, exist_ok=True)
    if slug:
        ACTIVE_FILE.write_text(slug, encoding="utf-8")
    elif ACTIVE_FILE.exists():
        ACTIVE_FILE.unlink()


def parse_series_arg(argv):
    """Pull `--series <slug>` / `--series=<slug>` out of an args list.

    Returns (slug_or_None, remaining_args).
    """
    slug = None
    out = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--series":
            if i + 1 >= len(argv):
                raise SystemExit("❌ --series needs a value, e.g. --series doctor-visits")
            slug = argv[i + 1]
            i += 2
            continue
        if a.startswith("--series="):
            slug = a.split("=", 1)[1]
            i += 1
            continue
        out.append(a)
        i += 1
    return slug, out


def resolve(slug=None):
    """Resolve all paths for a series.

    Precedence: explicit `slug` (e.g. from --series) > the active series (.active) > the
    default flat series/. `.slug` on the returned object is the effective slug (or None).
    """
    if not slug:
        slug = get_active()
    base = SERIES_ROOT if not slug else SERIES_ROOT / slug
    return SimpleNamespace(
        slug=slug,
        base=base,
        cast=base / "cast.json",
        episodes=base / "episodes.json",
        characters=base / "characters",
        curriculum_txt=base / "curriculum.txt",
        curriculum_json=base / "curriculum.json",
        # reference_image paths stored in cast.json are project-root-relative:
        rel_characters=(base / "characters").relative_to(BASE).as_posix(),
    )


def announce(slug):
    """Print which series a command is operating on (so it's never silent)."""
    name = slug if slug else "default (series/)"
    print(f"📂 Series: {name}")


def list_series():
    """Return available series slugs (named sub-series only) plus whether a default exists."""
    named = []
    if SERIES_ROOT.exists():
        for p in sorted(SERIES_ROOT.iterdir()):
            if p.is_dir() and p.name != "characters" and (p / "cast.json").exists():
                named.append(p.name)
    has_default = (SERIES_ROOT / "cast.json").exists()
    return has_default, named
