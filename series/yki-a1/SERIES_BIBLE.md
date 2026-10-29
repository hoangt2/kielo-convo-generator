# Finnish for Citizenship (YKI): series bible

Story videos for the YKI track (T-tung-1n4 in kielo-work-assistant), one per story lesson. The format is
The Sounds of Finnish's: short (about 60 s), Finnish only, slow and clear. The lesson JSON for the track is
in `lessons/`.

## Story

Linh gets her YKI date (March) in chapter 1, and every chapter moves toward it. She practises at Kaarina's language
café in the library, with Mehmet. Each chapter ends on an unanswered question that the next chapter's first video
answers. A1 ends on test day.

## Format

Tung, 2026-10-29: "the videos should not be English led, because YKI test will always be in Finnish anyway. Just make
the characters speak and explain things slowly and clearly", and "why are all the characters in the same episode
now, no need to... it's so confusing and not natural".

1. Finnish only, slow and clear: short sentences, words the lessons teach. Captions carry the translation.
2. Only the characters the scene needs, usually two, in a real place (home, library, bus, Kela).
3. A small joke or warm moment, from a real situation (Linh freezing, Mai playing teacher).
4. One tool per video, said clearly by the character who would know it (Kaarina, Mai).
5. A hook toward the next lesson.

Rules:
- Every line is Finnish; no English lines.
- Written-test Finnish is standard (minä olen); Mai's spoken Finnish shows the difference later.
- The YKI speaking test is recorded on a computer: never show asking the tester to repeat.
- Check the Finnish with a second model (scratchpad check_fi.py pattern: gemini-2.5-pro as a Finnish teacher).

## Cast (cast.json)

| Character | Who | Voice (ElevenLabs library, first pick) |
|---|---|---|
| Linh | The learner, Vietnamese, ~35, Vantaa, practical nurse student | Ngân Nguyễn (Vietnamese) |
| Mehmet | Turkish bus driver, ~40; says every stop name perfectly and little else | Mehmet Akif (Turkish) |
| Kaarina | Retired teacher and former YKI examiner, ~68, runs the language café; stopwatch | Kaisa (native Finnish) |
| Mai | Linh's daughter, 9 (was the boy Minh until Tung's review, 2026-10-29); "Kukaan ei sano noin!" | Yuna (Vietnamese young girl). No Finnish child voice in the ElevenLabs library, and Voice Design blocks child prompts |

Voices: eleven_v3 only (tts_settings.json). Picked by Tung by ear, 2026-10-29, from `~/Desktop/Kielo/yki-voices-test/round2/`: native voices of each character's home language speaking Finnish, so the accent is real.

## Pictures

- Mehmet's skin: the model drew it greenish, then too dark; the fixed portrait is light olive. Check him in scenes.
- Kaarina is about 68: soft wrinkles; the first portrait looked 40.
- No readable text on letters or signs.

## Building an episode

Same as The Sounds of Finnish: back up the working folders, `series_compile.py <N> --series yki-a1`, write
`scripts/<slug>.json` from ideas.json + `scripts/ep<N>.json`, then generate_illustrations, generate_sfx,
tts_generator, sfx_mixer, generate_videos, music_mixer, and copy the results to `output/`.

## Episodes

| # | Title | Characters | Lesson position | Moment |
|---|---|---|---|---|
| 1 | Kirje tuli! | Linh, Mai (home) | ch1, after "Lue, kuuntele, kirjoita, puhu" | Mai plays the test: "Kerro itsestäsi!" ... "Tiedän." |
| 2 | Ensimmäinen haastattelu | Linh, Kaarina (library) | ch1, before "Esittäydy" | Linh freezes: "Lue! Kuuntele! Kirjoita! Puhu!" |

Mehmet comes in chapter 2 (puoli kaksi).

## Voices live in the scripts

Each line in `scripts/epN.json` carries its own `voice_id`, and the build uses that, not `cast.json`. When a voice changes, change it in every script too (2026-10-29: a rebuild after a cast-only change kept the old voices).

The build drops "clearly" from line cues (`strip_clarity_cues`), so "[slowly, clearly]" is sent as "[slowly]". Ngân Nguyễn (Linh) often blurs "Minun nimeni" when the line starts with it; ep2's take was picked by hand (Scribe heard "Minun nimeni on Ling") and placed in `.tts_cache` under the key the build uses. A line that starts with a short lead-in ("Öö... Minun nimeni on Linh.") comes out clean.
