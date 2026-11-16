"""Stop a convo video from repeating a situation we already made.

Tung, 2026-11-16: on 11-16 the Finnish video was a pharmacy visit for a sore throat and the
Swedish one a haircut, but 11-12 already had "Lääkettä yskään ja kurkkukipuun" and "Bara topparna!".
The freestyle history only held recent Swedish titles from this Mac, and a topic given on the
command line was never compared with anything.

past_titles() gathers every title we know of, for one language:
  - the published KieloTV videos (the work assistant's kielo_captions.py `list`, cached for a day),
  - script_archive/*.json (every script this clone made),
  - series/*/episodes.json,
  - the freestyle history (.freestyle_history.json).
find_clash() asks Gemini whether a new topic or idea is the same everyday situation (same kind of
place and errand) as any of them, and returns the clashing title or None.
"""
import glob
import json
import os
import subprocess
import sys
import time

from google import genai
from google.genai import types

REPO = os.path.dirname(os.path.abspath(__file__))
CAPTIONS_TOOL = os.environ.get(
    "KIELO_CAPTIONS",
    os.path.expanduser("~/Desktop/Kielo/kielo-work-assistant/.claude/skills/kielo-caption-fix/scripts/kielo_captions.py"),
)
PROD_CACHE = os.path.join(REPO, ".prod_titles_cache.json")  # gitignored (*.json is local state)
CACHE_SECONDS = 24 * 3600
LANG_CODE = {"Finnish": "fi", "Swedish": "sv"}
MODEL = "gemini-2.5-flash"


def _prod_titles(language):
    code = LANG_CODE.get(language)
    if not code:
        return []
    try:
        with open(PROD_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(code)
    if hit and time.time() - hit.get("at", 0) < CACHE_SECONDS:
        return hit["titles"]
    if not os.path.exists(CAPTIONS_TOOL):
        print(f"⚠️  topic guard: {CAPTIONS_TOOL} not found, published titles not checked")
        return hit["titles"] if hit else []
    try:
        out = subprocess.run(["python3", CAPTIONS_TOOL,
                              "--lang", code, "list"], cwd=REPO, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"⚠️  topic guard: could not list published videos ({e})")
        return hit["titles"] if hit else []
    titles = []
    for line in out.stdout.splitlines():
        # "<id8> <date> <status> cues=N review=... desc=... script=...  <title>"
        if "cues=" in line and "script=" in line:
            title = line.split("script=", 1)[1].split(None, 1)
            if len(title) == 2 and title[1].strip():
                titles.append(f"{title[1].strip()} ({line.split()[1]})")
    if not titles:
        print("⚠️  topic guard: the published list came back empty " + (out.stderr.strip().splitlines() or [""])[-1])
        return hit["titles"] if hit else []
    cache[code] = {"at": time.time(), "titles": titles}
    with open(PROD_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    return titles


def past_titles(language):
    titles = list(_prod_titles(language))
    for path in glob.glob(os.path.join(REPO, "script_archive", "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if (d.get("metadata", {}).get("language") or "Finnish") != language:
            continue
        idea = d.get("idea", {})
        if idea.get("title"):
            titles.append(f"{idea['title']}: {idea.get('description', '')[:120]}")
    for path in glob.glob(os.path.join(REPO, "series", "*", "episodes.json")):
        try:
            with open(path, encoding="utf-8") as f:
                eps = json.load(f)
        except (OSError, ValueError):
            continue
        eps = eps.get("episodes", eps) if isinstance(eps, dict) else eps
        for ep in eps if isinstance(eps, list) else []:
            if isinstance(ep, dict) and ep.get("title") and (ep.get("language") or "Finnish") == language:
                titles.append(ep["title"])
    try:
        with open(os.path.join(REPO, ".freestyle_history.json"), encoding="utf-8") as f:
            titles += json.load(f).get(language, [])
    except (OSError, ValueError):
        pass
    seen, out = set(), []
    for t in titles:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def find_clash(new_text, language, titles, client=None):
    """Return the past title that is the same situation as new_text, or None."""
    if not titles or not new_text:
        return None
    client = client or genai.Client()
    prompt = (
        f"A language-learning app makes short {language} conversation videos. Each video is one everyday "
        "situation. Is the NEW video the same situation as any PAST video? Same situation means the same kind "
        "of place AND the same errand or problem (for example two pharmacy visits for a cold, two haircuts, "
        "two library cards), even with different names, wording or language. A different errand in a similar "
        "place is NOT the same (buying a train ticket vs. losing a bag on the train).\n\n"
        f"NEW: {new_text}\n\nPAST:\n" + "\n".join(f"- {t}" for t in titles)
        + '\n\nAnswer JSON: {"same": true|false, "past_title": "<the matching past title, or empty>"}'
    )
    try:
        r = client.models.generate_content(
            model=MODEL, contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
        )
        ans = json.loads(r.text)
    except Exception as e:  # a failed check must not silently pass a repeat: say so
        print(f"⚠️  topic guard: check failed ({e}); not checked")
        return None
    return (ans.get("past_title") or "a past video") if ans.get("same") else None


if __name__ == "__main__":
    # python topic_guard.py Finnish "At the pharmacy, buying something for a sore throat"
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO, ".env"))
    lang, text = sys.argv[1].capitalize(), " ".join(sys.argv[2:])
    ts = past_titles(lang)
    print(f"{len(ts)} past {lang} titles")
    clash = find_clash(text, lang, ts)
    print(f"❌ same as: {clash}" if clash else "✅ new topic")
    sys.exit(1 if clash else 0)
