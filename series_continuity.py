"""
Series continuity — what the cast, and the learner, already share by a given episode.

Episodes are written one at a time, so without this every episode reads like lesson one:
colleagues who met in episode 3 introduce themselves again in episode 9, and the guide
opens with "your very first lesson". Two helpers fix that:

  script_block()  — appended to the SCRIPT prompt (generate_scripts.py) for one episode.
  planning_block() — appended to the EPISODE-PLANNING prompt (series_plan.py), so new
                     episode descriptions don't restage meetings that already happened.

Both are derived purely from the episode list (who appeared together in earlier episodes,
which phrases were already taught), so they work for every existing series unchanged.
"""

RECENT_EPISODES = 3      # how many preceding episodes to recap
LEARNED_PHRASES = 40     # most recent already-taught phrases to list as callbacks
PLANNING_HISTORY = 12    # how many preceding episodes the planner is shown


def _char_ids(ep):
    return [c for c in ep.get("characters", []) if isinstance(c, str)]


def _name(cast, cid):
    return cast.get("characters", {}).get(cid, {}).get("name", cid)


def _learner(cast, ids):
    """The learner's cast id among `ids` (role mentions 'learner'), else the first id."""
    for cid in ids:
        if "learner" in cast.get("characters", {}).get(cid, {}).get("role", "").lower():
            return cid
    return ids[0] if ids else None


def prior_episodes(episode, episodes):
    """Episodes that come before `episode` in the series order."""
    out = []
    for e in episodes:
        if e is episode or e.get("id") == episode.get("id"):
            break
        out.append(e)
    return out


def pair_history(prior, ids):
    """Split the pairs among `ids` into (known, fresh).

    known = [(a, b, first_episode)] — they already shared an earlier episode.
    fresh = [(a, b)] — they have never appeared together, so a first meeting is plausible.
    """
    known, fresh = [], []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            first = next((e for e in prior if a in _char_ids(e) and b in _char_ids(e)), None)
            if first:
                known.append((a, b, first))
            else:
                fresh.append((a, b))
    return known, fresh


def _learned_phrases(prior):
    seen, out = set(), []
    for e in reversed(prior):
        for p in reversed(e.get("key_phrases", []) or []):
            if p not in seen:
                seen.add(p)
                out.append(p)
    out.reverse()
    return out[-LEARNED_PHRASES:]


def script_block(episode, episodes, cast, language):
    """Continuity brief for one episode's script prompt, or "" for the series opener."""
    prior = prior_episodes(episode, episodes)
    if not prior:
        return ""

    ids = _char_ids(episode)
    learner = _name(cast, _learner(cast, ids)) if ids else "the learner"
    known, fresh = pair_history(prior, ids)
    n = len(prior) + 1

    parts = [
        f"SERIES CONTINUITY — this is episode {n} of {len(episodes)} of an ongoing series with a "
        f"recurring cast. The characters already have history together; this is NOT the start of the story."
    ]
    if known:
        parts.append("Already acquainted (do not restage how they met):\n" + "\n".join(
            f"- {_name(cast, a)} and {_name(cast, b)} have known each other since episode "
            f"{first['id']} (\"{first.get('title_en') or first.get('title')}\")."
            for a, b, first in known
        ))
    if fresh:
        parts.append("Not yet met on screen (a first meeting between ONLY these pairs is fine, e.g. "
                     "one friend introducing another):\n" + "\n".join(
            f"- {_name(cast, a)} and {_name(cast, b)}" for a, b in fresh
        ))

    parts.append(
        "Continuity rules — these OUTRANK any conflicting wording in the scenario description:\n"
        "1. People who already know each other behave like it: first names, an easy familiar tone, "
        "shared history. They never meet \"for the first time\", never introduce themselves to each "
        "other, and never say things like \"you must be " + learner + "\", \"welcome to the team\", "
        "\"is it your first day\" or \"nice to meet you\" to someone they have already met.\n"
        f"2. Never open as if this were lesson one — no \"your very first {language} lesson\", "
        f"\"I know absolutely nothing\", \"let's start from the beginning\". {learner} has already "
        f"been through {n - 1} earlier episode(s). Start in the middle of everyday life, with a "
        f"believable reason for them to be together today (a small callback to something recent is welcome).\n"
        "3. If the scenario description implies a first meeting, a brand-new job, a new neighbour and so "
        "on between people who are already acquainted, treat that wording as out of date: keep the "
        "setting and the lesson content, drop the first-meeting framing."
    )

    recent = prior[-RECENT_EPISODES:]
    parts.append("Most recent episodes:\n" + "\n".join(
        f"- Episode {e['id']}: {e.get('title_en') or e.get('title')} "
        f"({', '.join(_name(cast, c) for c in _char_ids(e))})"
        for e in recent
    ))

    learned = _learned_phrases(prior)
    if learned:
        parts.append(
            f"Already taught in earlier episodes — {learner} may use these as quick callbacks without "
            f"re-teaching them from scratch (new material is still taught one phrase at a time):\n"
            + "; ".join(learned)
        )
    return "\n\n".join(parts)


def planning_block(prior, cast):
    """Continuity brief for the episode PLANNER, or "" when nothing precedes."""
    if not prior:
        return ""

    recent = prior[-PLANNING_HISTORY:]
    lines = [
        f"- Episode {e['id']} ({e.get('chapter', '')}): {e.get('title_en') or e.get('title')} — "
        + ", ".join(_name(cast, c) for c in _char_ids(e))
        for e in recent
    ]

    pairs = {}
    for e in prior:
        ids = _char_ids(e)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                pairs.setdefault(frozenset((a, b)), e["id"])
    known = "; ".join(
        f"{' & '.join(sorted(_name(cast, c) for c in pair))} (since episode {eid})"
        for pair, eid in sorted(pairs.items(), key=lambda kv: kv[1])
    )

    return (
        "SERIES SO FAR — the episodes below already exist and the new ones come AFTER them, so the "
        "story keeps moving forward:\n" + "\n".join(lines) + "\n\n"
        f"Characters who already know each other: {known or 'none yet'}.\n\n"
        "Continuity rules for the descriptions you write:\n"
        "- Characters who already know each other never meet 'for the first time', introduce themselves "
        "as strangers, or get called 'new' (new colleague, new neighbour). Show them as established "
        "friends, colleagues or neighbours in an ordinary moment of their day.\n"
        "- A first meeting is fine ONLY for a pair that has never appeared together, and works best as "
        "one friend introducing another (this is also the natural way to teach introductions).\n"
        "- Within this chapter the episodes also happen in order: a pair that meets in an earlier "
        "episode already knows each other in the later ones.\n"
        "- Don't describe an episode as a beginning ('first lesson', 'first day') — the learner has "
        "already been learning."
    )
