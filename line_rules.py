"""No one-word spoken lines in Finnish scripts.

TTS mis-voices a Finnish line that is a single short word: "Moi." came out as "Moaa"/"Moa"
(2026-11-13 and again 2026-11-16 at the end of "Pyöräkorjaamolla"), "Joo?" as English "You"
(2026-11-14). Tung, 2026-11-16: "we should avoid Moi as standalone".

fix_one_word_lines() rewrites every Finnish line whose spoken part is one word:
  - a greeting near the start becomes "Hei vaan!" (hi there),
  - a greeting or goodbye later on becomes "Hei hei!" (bye-bye),
  - any other word gets the other speaker's name: "Kiitos." -> "Kiitos, Liisa."
It is called when a script is saved and again after the grammar check, so captions and audio
always use the same text.
"""
import re

_TAG = re.compile(r"^\s*(\[[^\]]*\]\s*)*")
_WORD = re.compile(r"[\wåäöÅÄÖ'-]+")
GREETINGS = {"moi", "moikka", "hei", "terve", "heippa", "moro", "morjens", "heips", "moimoi"}


def _spoken(text):
    m = _TAG.match(text or "")
    return (text[:m.end()], text[m.end():]) if m else ("", text or "")


def fix_one_word_lines(dialogue, characters, language="Finnish"):
    """Rewrite one-word Finnish lines in place. Returns a list of 'old -> new' strings."""
    if language != "Finnish":
        return []
    names = {c.get("voice_id"): c.get("name", "") for c in characters or []}
    lines = [e for e in dialogue if e.get("type") != "sfx" and e.get("lang") in (None, "fi")]
    changes = []
    for i, e in enumerate(lines):
        tags, said = _spoken(e.get("text", ""))
        words = _WORD.findall(said)
        if len(words) != 1:
            continue
        word = words[0]
        if word.lower() in GREETINGS:
            new = "Hei vaan!" if i < 2 else "Hei hei!"
        else:
            other = next((n for v, n in names.items() if v != e.get("voice_id") and n), "")
            punct = said.strip()[-1] if said.strip() and said.strip()[-1] in ".!?" else "."
            new = f"{word}, {other}{punct}" if other else f"{word}, {word.lower()}{punct}"
        e["text"] = f"{tags}{new}"
        changes.append(f"{said.strip()} -> {new}")
    return changes


if __name__ == "__main__":
    # python line_rules.py scripts/<slug>.json : fix a saved script in place
    import json
    import sys
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        ch = fix_one_word_lines(d.get("dialogue_list", []), d.get("idea", {}).get("characters", []),
                                d.get("metadata", {}).get("language", "Finnish"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"{path}: " + ("; ".join(ch) if ch else "no one-word lines"))
