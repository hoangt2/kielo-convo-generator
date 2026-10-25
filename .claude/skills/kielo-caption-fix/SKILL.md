---
name: kielo-caption-fix
description: Compare KieloTV conversation video captions in the production Kielo DB (GCP) against this repo's script JSON and fix the wrong ones, and set a video's title/description. Use when the user uploads a convo video to the Kielo admin/CMS and says the auto-captions are inaccurate, asks to review/fix captions, or wants the Swedish title + English description added to a new video.
---

# Kielo caption fix

The CMS auto-captions uploaded convo videos (ASR + an AI "caption_review" pass that only flags a few cues), so captions drift from what the script says. The **script JSON in this repo is the source of truth**; the DB is what gets fixed. Typical errors: wrong words ("Vad" for "Var", "sju keks" for "sju kex", "Steen"/"Oscar" for "Sten"/"Oskar", "I'm f******"), English lines flipped to Swedish (back-translation in `text_primary`), rewording, bad cue splits.

Everything goes through `scripts/kielo_captions.py` (read-only unless `--yes`). Always run from the repo root.

## Hard rules

- **Never print, echo, log or store credentials.** The script reads `DATABASE_URL` from Secret Manager in-process. Don't `gcloud run services describe` to hunt for secrets and don't print the connection string. Print host/db name only if you must.
- **Don't enable GCP APIs or change infra.** Firestore/Cloud SQL are intentionally off in `kielo-backend-prod`; the DB is PlanetScale Postgres.
- **Show the diff and get the user's approval before any `--yes` write** (production data). A standing "apply directly" from the user for this exact job counts; a review-only request does not.
- **`apply` fixes text only, never timings** (the script asserts it). The one allowed timing edit is `retime`, which only extends a flagged cue's `end_time` (never its start, never within 0.08s of the next cue), and only with the user's explicit approval for that change.
- **`insert` (adding cues / moving a cue's edges) is part of a standing `--yes`.** It also writes `cms_<lang>.occurrences.caption_index`, so it is the one command that touches a table besides `kielotv_captions`: always show the exact dry-run first (new cue times, `N occurrences row(s) get a shifted caption_index`), then apply, and tell the user afterwards. Timings for inserted cues and `adjust` edits must come from STT word times, never guesses (see *Dropped speech*).
- **Don't tell the user to run "Reprocess" in the CMS**: it regenerates captions from audio and overwrites fixes.

## One-time setup

```bash
brew install --cask gcloud-cli          # if `gcloud` is missing
gcloud auth login                       # user does this (interactive); account needs access to kielo-backend-prod
python3 -m venv ~/.cache/kielo-caption-fix/venv && ~/.cache/kielo-caption-fix/venv/bin/pip install -q psycopg2-binary certifi
```

Use `~/.cache/kielo-caption-fix/venv/bin/python` below (`PY`). Connection uses `sslrootcert=certifi` (verify-full); don't weaken TLS.

## Workflow

1. **Find the video.** `PY .claude/skills/kielo-caption-fix/scripts/kielo_captions.py list` shows conversation videos with cue count, description present, and whether a matching script exists (matched by Swedish title, `idea.title`). Every command takes a title, a slug, or the version id prefix from `list` (use the prefix for a new upload still titled `Untitled Video`). Identify an untitled video from its cues (`show <prefix>`), match it to a script in `series/*/output/conversation_*.json` (also `script_archive/`), then set its title with step 2; script lookup by title only works after that.
2. **Title + description (new uploads).** Title = script `idea.title` (Swedish). Description = script `idea.title_en`, Title Case (e.g. "Where Are You From?"). Dry-run, then `--yes`:
   `PY ...kielo_captions.py meta "Untitled Video" --title "Trevligt att träffas" --description "Nice to Meet You"`.
   It updates both `content_versions` and `content_entries` and refuses nothing silently, so confirm the video is the right one first. Don't touch the slug.
3. **Review.** `PY ...kielo_captions.py show "<title>"` prints cues (`index time | text_primary || support_text`) beside the script and saves a rollback snapshot to `~/.cache/kielo-caption-fix/backups/`. Compare cue by cue; script lines are mostly English carrier lines (`lang: en`) with small Swedish chunks (`lang: sv`); one cue may cover several script lines.
4. **Decide what to fix** (keep the bar consistent):
   - Fix: wrong/misheard words, wrong names, dropped words, English text replaced by Swedish, primary/support out of sync, bad splits (stray leading comma, lowercase sentence start), meaning-changing punctuation ("?" vs ".").
   - **Match the script's punctuation exactly**: quotes (`'the glass'`), hyphens (`Kopp-en.`, `Glas-et.`), `?`/`!`/`.`/`...`, commas, em-dashes, and even a lowercase start when the cue is mid-sentence in the script (`how do you think we say 'the glass'?`). Cue boundaries and timings stay; only the text changes. Strip script markup (backticks, `*emphasis*`, `[stage directions]`) and ASR leftovers (leading `–` dialogue dashes, quotes the script doesn't have). Use `scripts/align_to_script.py <prefix> <script.json> fixes.json` to generate the fixes, then review every flagged cue by hand.
   - **`support_text` depends on the video type** (check the script: are there `lang: en` carrier lines?):
     - **Guided / English-carrier videos** (script has `lang: en` lines with Swedish chunks): `support_text` equals `text_primary` (`"s": "same"`) for English and Swedish cues alike. A Swedish chunk like `Jobbar du här?` shows `Jobbar du här?` in both fields, never an English gloss. After the fix `show | grep -c '||'` must be 0.
     - **Fully Swedish videos** (every script line is Swedish; e.g. `Dags för fika`, whose script lines have no `lang` key): keep the **English translation in `support_text`** and the Swedish in `text_primary`. When you change the Swedish wording of a cue, update its English gloss to match (`"s": "<English translation>"`, never `"same"`). `show` should print ` || ` on every cue. Do not run the guided-video "same" rule on these; it wipes the translations the learner sees.
     - The aligner (`align_to_script.py`) finds nothing in a script without `lang` keys; for fully Swedish videos diff by hand.
   - **CMS "cues need attention" (too fast to read / too short)** is a timing problem: the text is right but the audio is very short (e.g. `Hello!` 0.26s). Text fixes don't clear it. The CMS thresholds, calibrated on `Vem är du?`, are > ~23 chars/sec (too fast) and < 0.3s (too short). With the user's approval run `PY ...kielo_captions.py retime "<title>"` (dry-run table, then `--yes`) to extend the end of each flagged cue into the silent gap after it (target 20 chars/sec, min 0.5s, at most +2s). Run `show` first so the snapshot is fresh; `restore` puts it back. Cues with no gap after them stay flagged: report them and suggest merging with the neighbouring cue of the same script line in the CMS editor (merging removes cues and shifts indices, so it is not automated). Without approval, only report the flagged cues.
   - **Dropped speech (fix it; part of `--yes`).** The ASR drops lines, shreds a taught phrase into fragments ("Minns." / "Is the."), or stretches one cue over a time skip so its window hides other lines (e.g. a 15s cue holding 4 lines). Text-only diffing can't see this reliably; use audio:
     1. `venv/bin/python .claude/skills/kielo-caption-fix/scripts/stt_scan.py <prefix> mp3/conversation_<slug>.mp3 <scratchpad>/stt.json`. The mp3 is cleaned up after the video is built; if `mp3/` doesn't have it, extract the audio from the rendered video first: `ffmpeg -v error -y -i series/<series>/output/conversation_<slug>.mp4 -vn -ac 1 -b:a 64k <scratchpad>/audio.mp3` (same clock as the uploaded video) and pass that. (project venv; needs `.env` ElevenLabs key; sends the episode audio to ElevenLabs STT, same as the generator's TTS verification). It lists STT speech with no cue under it, cues >8s whose window holds other speech, and with `--window A Z` the STT stream vs cues for a range. Ignore edge words under ~0.3s.
     2. Fix garbled fragments first with `apply` (text only, STT word order + script punctuation), then `show` again for a fresh snapshot.
     3. Write `insert.json`: `{"after": <cue idx>, "text": "<script text>", "start": s, "end": e}` per missing line (several allowed after one cue, in order; one cue per script line; start = first STT word start -0.05, end = last word end +0.15) and `{"adjust": <cue idx>, "start"?: s, "end"?: e}` to pull a cue's window onto its own words (e.g. a cue whose start sits 10s before its text is spoken, or an end that cuts off the last word). Dry-run `PY ...kielo_captions.py insert "<title>" insert.json`, check no overlaps and chars/sec <= ~20, then `--yes`. It renumbers later cues and shifts `occurrences.caption_index` in the same transaction; `restore` reverses both while the `*.insert.json` record in `backups/` is current (don't re-run `show` before restoring).
     4. Never invent text: inserted text is the script line the STT confirms was spoken. If STT and script disagree on what was said, report it instead.
5. **Write `fixes.json`** (put it in the session scratchpad) like `{"19": {"p": "Var kommer du ifrån?", "s": "same"}, "7": {"p": "Hej. Jag vill ha... sju kex?", "s": "same"}}`, then `PY ...kielo_captions.py apply "<title>" fixes.json` for a **dry-run diff**. Show it to the user.
6. **Apply** after approval: same command with `--yes`. Never generate the fixes and apply them in one step; show the dry-run first, even under a standing approval. It runs in one transaction, aborts if the live cues no longer equal the snapshot (someone edited in the CMS, e.g. nudged timings: re-run `show`, check what changed, then re-apply; `show` overwrites the snapshot, so copy it to `backups/original/` first if you want to keep the pre-fix state), then re-reads and prints `verified equal: True`.
7. **Report**: cues fixed, timings unchanged (or which ends were extended), rollback available via `restore "<title>" --yes`, dropped speech inserted (with the STT-derived times and how many occurrences rows shifted), any left unresolved, and "if the app still shows old text a cache is holding it".

## Bulk review

To audit every video: `list`, then for each `show` + diff + `apply` dry-run; present one combined diff and get one approval before any `--yes`. `daily-word` videos (69 in `cms_sv`) have no script and are out of scope. Finnish: use `--schema cms_fi` (script titles are in `series/everyday-finnish-*`).

## DB facts (verified 2026-10)

- Project `kielo-backend-prod`; DB is PlanetScale Postgres (`DATABASE_URL` secret, port 6432 pgbouncer, `sslmode=verify-full`).
- `cms_sv.kielotv_captions` (also `cms_fi`): one row per video; `cues` jsonb = `[{index, start_time, end_time, text_primary, support_text}]`; join `content_version_id` → `content_versions` (`title`, `description`, `data->>'format_type'` = `conversation` | `daily-word`, `data->'caption_review'`) → `content_entries` (also holds `title`/`description`).
- `cms_sv.occurrences` (also `cms_fi`) links word highlights to a video: `content_version_id`, `caption_index` (index into `cues`), `timestamp_start/end`, `start_index/end_index` (offsets in the cue text). Text edits don't update these (the CMS warns about it); inserting or deleting cues must shift `caption_index`.
- Ingest runs on Cloud Run `kielo-ingest-processor` / `kielo-cms` (europe-north1); the CMS "Save Captions" button is the UI path for the same data.
