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
- **`insert` (adding cues) also writes `cms_<lang>.occurrences.caption_index`.** Only run it after the user approves the exact dry-run, and never as part of a standing `--yes`. It is the one command that touches a table besides `kielotv_captions`.
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
   - **`support_text` always equals `text_primary`** (`"s": "same"`), for English and Swedish cues alike: a Swedish line like `Jobbar du här?` shows `Jobbar du här?` in both fields, never an English gloss (`Do you work here?`). `show` prints ` || ` only when they differ, so after a fix `show | grep -c '||'` must be 0. Apply this to every cue that still shows ` || `, even ones whose primary text is already right.
   - **CMS "cues need attention" (too fast to read / too short)** is a timing problem: the text is right but the audio is very short (e.g. `Hello!` 0.26s). Text fixes don't clear it. The CMS thresholds, calibrated on `Vem är du?`, are > ~23 chars/sec (too fast) and < 0.3s (too short). With the user's approval run `PY ...kielo_captions.py retime "<title>"` (dry-run table, then `--yes`) to extend the end of each flagged cue into the silent gap after it (target 20 chars/sec, min 0.5s, at most +2s). Run `show` first so the snapshot is fresh; `restore` puts it back. Cues with no gap after them stay flagged: report them and suggest merging with the neighbouring cue of the same script line in the CMS editor (merging removes cues and shifts indices, so it is not automated). Without approval, only report the flagged cues.
   - **Dropped speech** (script text with no cue, shown as a gap > ~1s between cues): list the candidates with `scripts/align_to_script.py`-style alignment (script tokens that match no cue, with the gap before/after). Don't invent cues on your own. If the user asks to fill them in, use `insert`: write `spec.json` = `[{"after": <cue index>, "text": "<script text>"}]`, run `PY ...kielo_captions.py insert "<title>" spec.json` (dry-run), show the new cue timings, and apply only after approval. A new cue spans the whole silent gap (0.08s margin each side), so the timing is an estimate: tell the user, and flag long cues holding a short line (e.g. 5s for `Sju kex.`). Gaps under ~1s are too tight for a cue; report them instead. `insert` renumbers every later cue and shifts `occurrences.caption_index` (word-link rows) in the same transaction; `restore` reverses both using a record saved in `backups/`, as long as `show` was not re-run in between. An alternative to inserting is an audio/STT pass.
5. **Write `fixes.json`** (put it in the session scratchpad) like `{"19": {"p": "Var kommer du ifrån?", "s": "same"}, "7": {"p": "Hej. Jag vill ha... sju kex?", "s": "same"}}`, then `PY ...kielo_captions.py apply "<title>" fixes.json` for a **dry-run diff**. Show it to the user.
6. **Apply** after approval: same command with `--yes`. Never generate the fixes and apply them in one step; show the dry-run first, even under a standing approval. It runs in one transaction, aborts if the live cues no longer equal the snapshot (someone edited in the CMS, e.g. nudged timings: re-run `show`, check what changed, then re-apply; `show` overwrites the snapshot, so copy it to `backups/original/` first if you want to keep the pre-fix state), then re-reads and prints `verified equal: True`.
7. **Report**: cues fixed, timings unchanged (or which ends were extended), rollback available via `restore "<title>" --yes`, possible dropped cues not fixed, and "if the app still shows old text a cache is holding it".

## Bulk review

To audit every video: `list`, then for each `show` + diff + `apply` dry-run; present one combined diff and get one approval before any `--yes`. `daily-word` videos (69 in `cms_sv`) have no script and are out of scope. Finnish: use `--schema cms_fi` (script titles are in `series/everyday-finnish-*`).

## DB facts (verified 2026-10)

- Project `kielo-backend-prod`; DB is PlanetScale Postgres (`DATABASE_URL` secret, port 6432 pgbouncer, `sslmode=verify-full`).
- `cms_sv.kielotv_captions` (also `cms_fi`): one row per video; `cues` jsonb = `[{index, start_time, end_time, text_primary, support_text}]`; join `content_version_id` → `content_versions` (`title`, `description`, `data->>'format_type'` = `conversation` | `daily-word`, `data->'caption_review'`) → `content_entries` (also holds `title`/`description`).
- `cms_sv.occurrences` (also `cms_fi`) links word highlights to a video: `content_version_id`, `caption_index` (index into `cues`), `timestamp_start/end`, `start_index/end_index` (offsets in the cue text). Text edits don't update these (the CMS warns about it); inserting or deleting cues must shift `caption_index`.
- Ingest runs on Cloud Run `kielo-ingest-processor` / `kielo-cms` (europe-north1); the CMS "Save Captions" button is the UI path for the same data.
