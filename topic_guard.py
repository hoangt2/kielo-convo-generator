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

Tung, 2026-11-23 (T-tung-3g9): "a couple at home choosing Christmas presents for their parents" passed once
and was refused on the next run as the same situation as "Ystävänpäiväkortti (The Friend's Day Card)". One
fast yes/no over hundreds of bare titles is jumpy near the edges. So:
  - a published title gets the script archive's one-line description when the archive has that title;
  - a match from the fast first pass is only a candidate: a second, stronger pass looks at just that pair
    and must confirm it, with a reason, before anything is refused;
  - a person who judged a refusal wrong sets TOPIC_GUARD_ALLOW="<why>"; the clash is then let through and
    written to .topic_guard_overrides.jsonl (local, gitignored), so the override is on record.
"""
import glob
import json
import os
import re
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
MODEL = "gemini-2.5-flash"          # first pass over every past title
CONFIRM_MODEL = "gemini-2.5-pro"     # second pass over the one candidate pair
OVERRIDES = os.path.join(REPO, ".topic_guard_overrides.jsonl")


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
    return _merge(titles)


def _base(title):
    """'💌 Ystävänpäiväkortti (The Friend's Day Card) (2026-02-14): ...' -> 'ystävänpäiväkortti'"""
    t = title.split(":", 1)[0]
    t = re.sub(r"\([^)]*\)", " ", t)
    return " ".join(re.findall(r"\w+", t.lower()))


def _merge(titles):
    """One entry per video: a published title takes the archive's description, and the archive's
    duplicate entry is dropped."""
    desc = {}
    for t in titles:
        if ": " in t and _base(t):
            desc.setdefault(_base(t), t.split(": ", 1)[1])
    seen, out = set(), []
    for t in titles:
        key = _base(t) or t.lower()
        if key in seen:
            continue
        seen.add(key)
        if ": " not in t and desc.get(key):
            t = f"{t}: {desc[key]}"
        out.append(t)
    return out


RULE = (
    "Same situation means the same kind of place AND the same errand or problem (for example two pharmacy "
    "visits for a cold, two haircuts, two library cards), even with different names, wording or language. "
    "A different errand in a similar place is NOT the same (buying a train ticket vs. losing a bag on the "
    "train), and neither is a different problem between the same kind of people (two friends planning a "
    "trip vs. two friends fixing a bike)."
)


def _ask(client, model, prompt):
    r = client.models.generate_content(
        model=model, contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(r.text)


def _confirm(new_text, past_title, language, client):
    """Second pass: is the NEW video really the same situation as this one PAST video? (same, reason)"""
    prompt = (
        f"A language-learning app makes short {language} conversation videos. Each video is one everyday "
        f"situation. Compare one NEW video idea with one PAST video. {RULE} If you only have a past title and "
        "it could be either, answer false: a wrong refusal costs more than a near repeat.\n\n"
        f"NEW: {new_text}\nPAST: {past_title}\n\n"
        'Answer JSON: {"same": true|false, "reason": "<one short sentence: the place and errand of each>"}'
    )
    ans = _ask(client, CONFIRM_MODEL, prompt)
    return bool(ans.get("same")), (ans.get("reason") or "").strip()


def _record_override(new_text, language, past_title, reason, why):
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "language": language,
             "new": new_text, "past": past_title, "guard_reason": reason, "allowed_because": why}
    with open(OVERRIDES, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def find_clash(new_text, language, titles, client=None):
    """Return the past title that is the same situation as new_text, or None."""
    if not titles or not new_text:
        return None
    client = client or genai.Client()
    prompt = (
        f"A language-learning app makes short {language} conversation videos. Each video is one everyday "
        f"situation. Is the NEW video the same situation as any PAST video? {RULE}\n\n"
        f"NEW: {new_text}\n\nPAST:\n" + "\n".join(f"- {t}" for t in titles)
        + '\n\nAnswer JSON: {"same": true|false, "past_title": "<the matching past title, or empty>"}'
    )
    try:
        ans = _ask(client, MODEL, prompt)
        if not ans.get("same"):
            return None
        past = ans.get("past_title") or ""
        match = next((t for t in titles if past and (t == past or t.startswith(past) or past.startswith(t))), past)
        same, reason = _confirm(new_text, match or "a past video", language, client)
    except Exception as e:  # a failed check must not silently pass a repeat: say so
        print(f"⚠️  topic guard: check failed ({e}); not checked")
        return None
    if not same:
        print(f"🧭 topic guard: first pass matched '{match}', second pass says different ({reason})")
        return None
    print(f"🧭 topic guard: same as '{match}': {reason}")
    why = os.environ.get("TOPIC_GUARD_ALLOW", "").strip()
    if why:
        _record_override(new_text, language, match, reason, why)
        print(f"✋ topic guard: allowed anyway (TOPIC_GUARD_ALLOW: {why}); recorded in {os.path.basename(OVERRIDES)}")
        return None
    return match or "a past video"


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
