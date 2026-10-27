# Everyday Finnish A1: series bible

Agreed with Tung, 2026-10-24 (revised the same day: Maire renamed Anna and moved out of episode 1; Linnea is the first contact). English-led guided episodes (characters speak mainly English; Finnish only in the taught phrases). 34 episodes from the 52 teaching lessons of the production roadmap. The roadmap's old video slots are ignored.

## Story and timeline
Alex has just moved to Helsinki from Brazil for a new job as a programmer at a small tech company. Revised with Tung 2026-10-25: the series runs through one Nordic year, from late August to late May, so the seasons change across the episodes (it was late August to mid-November). Alex is careful and eager; he is the learner in every episode.

## Seasons
| Season | Episodes | When | What changes |
|---|---|---|---|
| Summer | 1-6 | late August to early September | green trees, sunshine, light evenings; everyone in their portrait clothes |
| Autumn | 7-17 | late September to October | yellow and red leaves (ruska), rain, early dusk; rain jackets and wool coats |
| Winter | 18-30 | November to early March | first snow in November, Christmas lights in December (20-22), deep winter January-February; parkas, hats, scarves. Ep 29 (weather, four seasons) looks out at February snow; ep 30 ("It's so cold!") is a hard frost |
| Spring | 31-34 | April to late May | snow melting, light evenings back, first leaves; ep 34 is almost a year since Alex arrived |

- Each episode has `season` and `when` in episodes.json. The season's look and sounds are in `series.seasons`; each character's outfit per season is in their `wardrobe` in cast.json (signature colours kept so they are recognisable; summer = the portrait). Indoors, coats come off.
- The season is felt, not talked about: a wet jacket, the early dark, snow underfoot. Only the weather episodes (29, 30) make it the topic.

## How the scenes sound
The Finnish comes out of the situation, the way a friend helps in passing. Nobody announces a lesson ("this is a perfect time to learn", "our first lesson for today", "your turn", "thanks for the lesson"); the scene starts for a reason of its own (a heavy box, the rain, a party on Saturday), Alex tries each phrase for real, and the scene ends when the situation does. The script generator rewrites a draft that announces the teaching. A Finnish word inside an English line is read the English way, so lines are split by language (the generator does this). A short Finnish word that is also an English word ('sun', 'on', 'Moi') is never said on its own, even as a Finnish line: the voice still reads it as English. Keep it inside a Finnish phrase ('Milloin sun syntymäpäivä on?'). Learned 2026-10-26 from 'Moi' (ep 8) and 'sun' (ep 15).

## Who knows whom, and when
| Character | First meets Alex | How the relationship grows |
|---|---|---|
| Anna (middle-aged neighbour) | Ep 6, the stairs. First names and introductions; Linnea may introduce them. | Friendly neighbours; she is the patient teacher. Invites him for coffee in ep 23. |
| Sanni (barista) | Ep 2, café. She says her name in English. | Stranger, then recognises him (ep 4), regular (ep 16), knows his order (ep 18). |
| Markku (kiosk, shop) | Ep 5, kiosk. No names; a rushed purchase. | Recognises him in ep 11 ("Taas sä!") and gives his name; warmer by ep 19. |
| Linnea (student) | Ep 1, the courtyard: she lives in the same building. Names in English. | First friend: asks where he is from (7), shows him the city (10), study meetings (14), friends by 17. |
| Leo (outgoing friend) | Ep 21, introduced by Linnea. | Invites Alex to things from ep 26 on. |

- Phone numbers are exchanged only in ep 31 (Alex and Linnea live in the same building, so until then they just meet in person), so texting and phoning (ep 32, 33) follow naturally.
- Nobody introduces themselves twice, and nobody uses a name before the episode where they learn it.
- Alex speaks careful standard Finnish (minä/sinä); Linnea and Leo use casual spoken forms (mä/sä); Anna is patient and clear; Sanni efficient; Markku fast and clipped.
- Each episode refers back to earlier ones (a usual coffee, the library Linnea showed him, how long he has been here).

## Episodes
Rule from the script writer: in an English-led (guided) lesson the teacher must be a personal companion (friend or neighbour), never a service worker. So every scene with Sanni or Markku also has a companion guide (Linnea or Anna); Sanni and Markku only have short service lines.

| # | Lessons | Cast | Place | Relationship status |
|---|---|---|---|---|
| 1 | Saying hello & goodbye | Alex, Linnea | courtyard | first meeting; young neighbour; names in English |
| 2 | Yes, no, thanks; sorry & you're welcome | Alex, Linnea, Sanni | café | Linnea guides; Sanni is a stranger and says her name |
| 3 | Saving the conversation (repeat, slower) | Alex, Linnea | bus | friends; Linnea talks too fast |
| 4 | Basic questions (mikä, missä, kuka) | Alex, Linnea, Sanni | café | Linnea guides; Sanni recognises him; portrait of Sibelius on the wall |
| 5 | Making your first purchase | Alex, Linnea, Markku | street kiosk | Linnea guides; Markku is a stranger, no names |
| 6 | The spoken pronouns; introducing yourself | Alex, Anna | courtyard/stairs | first meeting with the older neighbour |
| 7 | Sharing your origins | Alex, Linnea | library | friends already; rehearsing for a student party |
| 8 | Numbers 0-10 | Alex, Anna | front door, lift | neighbours; the door code she says aloud, then counting apples from her cottage (no lift-button numbers: the buttons show digits) |
| 9 | Talk about work | Alex, Linnea | park | good friends; his team lunch on Monday |
| 10 | Finding where things are; getting around town | Alex, Linnea | street | good friends; Alex has a cold and needs a pharmacy; they walk, then take the tram home |
| 11 | Asking for the price; numbers 10-100 | Alex, Anna, Markku | kiosk | Anna guides; Markku recognises Alex, says his name; Alex loads a month's tram ticket and must understand the price Markku says aloud |
| 12 | What time is it? | Alex, Linnea, Sanni | café | Linnea guides; he is becoming a regular; the morning the clocks went back, his phone is dead and he has a call home at eleven |
| 13 | Days of the week; parts of the day | Alex, Anna | basement laundry room | booking the shared laundry room (morning and evening slots); her sauna evenings |
| 14 | When shall we meet?; bigger numbers in time & dates | Alex, Linnea | library | a weekly study time before her November exam; a two-hour study room |
| 15 | Months; talking about the date | Alex, Anna | her kitchen | her birthday (October, cake and coffee); his is in May |
| 16 | At the café; ordering a meal | Alex, Linnea, Sanni | café | Linnea guides; he is a regular |
| 17 | Likes & dislikes; asking about the food | Alex, Linnea | restaurant | friends |
| 18 | Paying the bill | Alex, Linnea, Sanni | café | Sanni knows his order |
| 19 | At the grocery shop | Alex, Anna, Markku | supermarket | Anna guides; Markku warmer |
| 20 | My family; brothers, sisters & kids | Alex, Linnea | park | friends share family news |
| 21 | This is my friend; describing someone | Alex, Linnea, Leo | street | Leo first meeting |
| 22 | "Do you have...?" | Alex, Leo | park | new acquaintance |
| 23 | Where I live; rooms at home | Alex, Anna | home_kitchen | coffee in her flat |
| 24 | My morning; a normal day | Alex, Linnea | street | friends |
| 25 | "What are you up to?" | Alex, Leo | park | friends |
| 26 | My hobbies; "I like to..." | Alex, Leo | gym or park | Leo's hobby group |
| 27 | At the weekend | Alex, Linnea | cafe | friends |
| 28 | "Shall we...?"; yes, no, or maybe | Alex, Leo, Linnea | park | invitation |
| 29 | The weather; the four seasons | Alex, Anna | home_kitchen | small talk, autumn |
| 30 | "It's so cold!"; easy small talk | Alex, Leo, Linnea | street | late October/November |
| 31 | "What's your number?" | Alex, Linnea | street | first number exchange |
| 32 | A quick message | Alex, Linnea | split (text) | |
| 33 | On the phone | Alex, Linnea | split (call) | |
| 34 | Making plans; "See you soon!" | Alex, Linnea, Leo | park | ends with a goodbye to Anna |

Episodes are written chapter by chapter with Tung. Episodes 1-25 are written (chapters Survival Basics, Asking & Buying, Who Am I?, Out and About, Telling Time & Days, Food & Drink, People & Family, Home & Daily Life); the rest wait for their chapter. Episodes 6-9 settle details for later ones: Alex is from Brazil and a programmer; Linnea is from Oulu and studies biology; Anna lives on floor 4, Alex on floor 6, and she has a summer cottage with an apple tree. Episodes 12-15 add: Alex video-calls home to Brazil; his flat has no washing machine (the building has a laundry room and a sauna); Linnea has an exam in November; Anna's birthday is at the end of October, Alex's in May. Episodes 16-19 add: Linnea and Alex study at Sanni's café, which has evening table service from November; Alex tried karjalanpiirakka (likes it) and salmiakki (does not); the first snow falls in episode 18; Markku also works the till at the neighbourhood supermarket; Alex buys oat drink (kaurajuoma), not milk. Episodes 20-22 add: Alex has one sister (Sofia, who has a new baby) and two brothers; Linnea has a little brother in Oulu; Linnea introduced Leo at the Senaatintori Christmas market (21); Leo lives near the park with the outdoor ice rink and taught Alex to skate (22); Alex and Leo still have no phone numbers. Episodes 23-25 add: Alex spent his first Christmas alone and had coffee and joulutorttu in Anna's flat on 26 December (23); he lives in a studio (yksiö); in January Linnea is back from Oulu on a morning lab course and they walk to the tram together (24); Alex has his own second-hand skates and meets Leo again by chance at the rink (25). Episode 25 is titled 'Mitä sä teet nyt?' because episode 9 is 'Mitä sä teet?' (titles become file names and must differ).

## Cast voices
Linnea = Aurora, Sanni = Aava, Markku = Petteri, Leo = Jussi and Anna = Soili are native Finnish voices from the ElevenLabs library. Alex = Davi Andrei (library voice 2CECaLAGTS5NRGxgbcxr), a young Brazilian Portuguese voice: Alex is from Brazil, so he speaks English and Finnish with a Brazilian accent (Tung, 2026-10-25, picked by ear from six Brazilian voices; it says 'Moi' correctly, unlike the old French voice). He replaced Matias, and episodes 1-9 were revoiced. Anna is middle-aged (the library has no native elderly woman), so she is a friendly neighbour in her fifties, no longer 'retired'.

## Sound
The café scenes from episode 16 on use the ambience `cafe_quiet` (cups, chatter, soft music, no espresso machine): Tung finds the espresso machine's steaming hiss unpleasant under dialogue (2026-10-27). Do not add espresso-machine or milk-steamer sound effects. Older episodes keep the plain `cafe` ambience.
