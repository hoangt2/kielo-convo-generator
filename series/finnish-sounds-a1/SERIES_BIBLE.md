# The Sounds of Finnish: series bible

Agreed with Tung, 2026-10-29. Five short videos (45-75 s), one per lesson of Finnish Grammar A1's first chapter
"The Sounds of Finnish (Äänteet)", made shorter and funnier than a guided scene because "explaining Finnish grammar
can be boring". Task: T-tung-jud in kielo-work-assistant.

## Format

Every episode teaches one sound and follows the same shape:
1. A mishearing joke in the first seconds: Priya says one sound wrong and it means something else.
2. The rule in one English sentence, from Eero.
3. Word pairs: each Finnish word on its own line, its English meaning on the next.
4. "Now you guess": Eero says one word of a pair, a ticking pause (sfx), Priya answers.
5. A callback: Priya says the opening line right, Väinö answers "Hyvä."

Rules:
- Every line is all English or all Finnish (Tung's rule for every series).
- Only Eero and Väinö say the word pairs: theirs are native Finnish voices.
- No guess round where the TTS would have to say a word wrongly on purpose (stress, the rolled r).

## Cast (cast.json)

Totally new cast (Tung: "I want a totally new cast").

| Character | Who | Voice (ElevenLabs library) |
|---|---|---|
| Priya | The learner, from Bangalore, works at a games studio in Tampere, Eero's flatmate | Sweta Priyadarshan (English, Indian accent) |
| Eero | Deadpan Finnish flatmate, a sound engineer | Oskari (native Finnish) |
| Väinö | Eero's grandfather (ukki), downstairs; speaks only short Finnish | Vaino (native Finnish) |
| Kissa | Eero's cat; her name means "cat" | meows only (sfx) |

Voices: eleven_v3 only. Tung, 2026-10-29: "dont use turbo voice" (tts_settings.json).

## Pictures

- Kissa is always a normal-sized house cat in a natural pose. Her reference sheet makes the model draw her
  person-sized and posed upright; say so in the scene (Tung, 2026-10-29: "the cat is not natural").
- Indoors at home: socks or slippers, never shoes (Everyday Finnish rule). Check everyone's feet.
- Check Priya against her portrait: black high ponytail, round tortoiseshell glasses, gold hoops, warm brown
  skin. The model has drawn her with loose brown hair and no glasses; fix with a Gemini edit that passes
  `characters/priya.png`.

## Building an episode

The scripts are hand-written in `scripts/ep<N>.json`. Do not use `series_run.py`: it would regenerate the
script with the guided-lesson prompt, which asks for long scenes.

1. Back up the working folders (scripts mp3 sfx illustrations output_videos); `cleanup.py` wipes them.
2. `venv/bin/python series_compile.py <N> --series finnish-sounds-a1` (writes ideas.json).
3. Write `scripts/<slug>.json` = {metadata, idea} from ideas.json + the dialogue_list of `scripts/ep<N>.json`
   (slug = `generate_scripts.slugify(title)`).
4. Run, with .env loaded: generate_illustrations, generate_sfx, tts_generator, sfx_mixer (grep "not found"),
   generate_videos, music_mixer.
5. Copy the mp4, the script json and the picture to `output/conversation_<slug>.*`.

A lone short word (Yö) can fail the per-line speech check on every try while it is right in the mix: check it
in the finished mp3 with Scribe word timestamps, and let a person listen.

## Episodes

| # | Title | Lesson | Sound | Joke |
|---|---|---|---|---|
| 1 | Tapan vai tapaan? | Short & Long Sounds | length | "Tapan sinut huomenna" (I'll kill you tomorrow) |
| 2 | Ylös vai ulos? | The Extra Vowels (ä, ö, y) | y, ä | "Ulos!" (out) in the lift instead of "Ylös!" (up) |
| 3 | Helsinki, ei HelSINki | Where the Stress Falls | stress | Väinö pretends not to know "HelSINki" |
| 4 | Rrr kuin Kissa | Finnish Consonants | rolled r, soft p t k | "Ask Kissa": purring is a rolled r |
| 5 | Yö, ei yo! | Diphthongs | yö, uo, oi | Priya's "Yo!" heard as "yö" (night) |
