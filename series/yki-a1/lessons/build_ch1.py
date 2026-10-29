"""YKI track, A1 chapter 1 "Minä ja YKI": the seven teaching lessons as roadmap lesson JSON (T-tung-1n4).

Run: python3 build_ch1.py  ->  ch1_<n>_<slug>.json next to this file. Step shapes follow kielo-admin-ui
src/components/curriculum/stepSchema.ts. The two video lessons of the chapter are made later with the
convo generator. Finnish is written standard Finnish (kirjakieli), as YKI expects.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent
FI = {"tts_language": "fi", "learning_language_code": "fi"}


def opts(correct, *wrong):
    return [{"text": correct, "is_correct": True}] + [{"text": w, "is_correct": False} for w in wrong]


def info(emoji, title, html, tts=""):
    return {"type": "info_card", "emoji": emoji, "title": title, "content_html": html, "tts_text": tts, **FI}


def expl(title, html, tts=""):
    return {"type": "explanation", "title": title, "content_html": html, "tts_text": tts, **FI}


def repeat(title, phrase, translation):
    return {"type": "listen_repeat", "title": title, "phrase": phrase, "translation": translation, "tts_text": phrase, **FI}


def quiz(title, question, options, ok, bad):
    return {"type": "quiz", "title": title, "question": question, "options": options,
            "correct_feedback": ok, "incorrect_feedback": bad, **FI}


def gap(title, template, hint, options, ok, bad):
    return {"type": "fill_blank", "title": title, "sentence_template": template, "translation_hint": hint,
            "options": options, "correct_feedback": ok, "incorrect_feedback": bad, **FI}


def build(title, prompt, target, tiles, translation, ok, bad):
    return {"type": "sentence_builder", "title": title, "prompt": prompt, "target_phrase": target, "tts_text": target,
            "word_tiles": tiles, "translation": translation, "correct_feedback": ok, "incorrect_feedback": bad, **FI}


def pairs(title, instruction, ps):
    return {"type": "match_pairs", "title": title, "instruction": instruction,
            "pairs": [{"left": l, "right": r} for l, r in ps], **FI}


def tf(title, statement, is_true, why):
    return {"type": "true_false", "title": title, "statement": statement, "is_true": is_true, "explanation": why}


def scene(title, scenario, prompt, options, ok, bad):
    return {"type": "scenario_prompt", "title": title, "scenario": scenario, "prompt": prompt, "options": options,
            "correct_feedback": ok, "incorrect_feedback": bad, **FI}


def spot(title, context, sentence, options, ok, bad):
    return {"type": "spot_error", "title": title, "context": context, "sentence": sentence, "options": options,
            "correct_feedback": ok, "incorrect_feedback": bad, **FI}


def listen(title, audio, question, options, ok, bad):
    return {"type": "listening_comprehension", "title": title, "tts_text": audio, "question": question,
            "options": options, "correct_feedback": ok, "incorrect_feedback": bad, **FI}


def cats(title, instruction, categories, items):
    return {"type": "categorization", "title": title, "instruction": instruction,
            "categories": [{"id": i, "label": l} for i, l in categories],
            "items": [{"text": t, "category_id": c} for t, c in items]}


def dialogue(title, scenario, persona, turns):
    out = []
    for n, (phrase, translation, choices) in enumerate(turns, 1):
        out.append({"turn_id": f"t{n}", "speaker": persona["name"], "phrase": phrase, "translation": translation,
                    "options": [{"text": t, "is_correct": c, "feedback": f} for t, c, f in choices]})
    return {"type": "branching_dialogue", "title": title, "scenario": scenario, "persona": persona, "turns": out, **FI}


TESTER = {"name": "YKI-testi", "age": 50, "context": "The recorded YKI speaking test: a voice on the computer asks each question once, clearly, then records the answer."}

LESSONS = [
    dict(
        slug="testin-sanat", title="Lue, kuuntele, kirjoita, puhu", shape="discovery", minutes=5,
        description="The seven instruction words of every YKI task. Read a real task instruction in five minutes.",
        practice_words=["lukea", "kuunnella", "kirjoittaa", "puhua", "vastata", "valita", "kertoa"],
        grammar=["imperatiivi"],
        steps=[
            info("🎯", "Your first YKI words",
                 "Every YKI task starts with an instruction in Finnish. Learn seven words today and you can read a real task."),
            expl("Four parts, four words",
                 "YKI has four parts, and each one has its word: <fi>Lue</fi> (read), <fi>Kuuntele</fi> (listen), "
                 "<fi>Kirjoita</fi> (write), <fi>Puhu</fi> (speak). They are commands: the test speaks to you directly.",
                 "Lue. Kuuntele. Kirjoita. Puhu."),
            pairs("Four parts", "Match each word with its meaning.",
                  [("Lue", "Read"), ("Kuuntele", "Listen"), ("Kirjoita", "Write"), ("Puhu", "Speak")]),
            repeat("Read the text", "Lue teksti.", "Read the text."),
            repeat("Listen to the conversation", "Kuuntele keskustelu.", "Listen to the conversation."),
            expl("Answer, choose, tell",
                 "Three more words tell you what to do: <fi>Vastaa</fi> (answer), <fi>Valitse</fi> (choose), "
                 "<fi>Kerro</fi> (tell). You will see them in full instructions: <fi>Vastaa kysymyksiin.</fi> "
                 "Answer the questions. <fi>Valitse oikea vaihtoehto.</fi> Choose the right option.",
                 "Vastaa kysymyksiin. Valitse oikea vaihtoehto. Kerro itsestäsi."),
            quiz("What do you do?", "The task says: Valitse oikea vaihtoehto. What do you do?",
                 opts("Choose the right option", "Write a message", "Listen twice"),
                 "Right: valitse = choose, oikea vaihtoehto = the right option.",
                 "Valitse means choose. Oikea vaihtoehto is the right option."),
            gap("Complete the instruction", "___ teksti ja vastaa kysymyksiin.",
                "Read the text and answer the questions.", opts("Lue", "Puhu", "Kuuntele"),
                "Yes. Lue teksti: read the text.", "A text is read: Lue teksti."),
            scene("A writing task", "The instruction says: Kirjoita viesti ystävälle.", "What is the task?",
                  opts("Write a message to a friend", "Read a message from a friend", "Call a friend"),
                  "Right: kirjoita = write, viesti = message, ystävälle = to a friend.",
                  "Kirjoita means write. The task is to write a message."),
            listen("Listen to the instruction", "Kerro itsestäsi.", "What does the test ask you to do?",
                   opts("Tell about yourself", "Read about yourself", "Write your name"),
                   "Yes. Kerro itsestäsi: tell about yourself. It is the first speaking task.",
                   "Kerro means tell. Itsestäsi means about yourself."),
            info("✅", "You can read YKI instructions",
                 "Lue, kuuntele, kirjoita, puhu, vastaa, valitse, kerro. Seven words, and every YKI task now tells you what to do."),
        ]),
    dict(
        slug="mina-olen", title="Minä olen ...", shape="discovery", minutes=6,
        description="Say who you are, where you are from and which languages you speak, in standard Finnish.",
        practice_words=["nimi", "kotoisin", "puhua", "äidinkieli", "suomi", "englanti", "vähän"],
        grammar=["olla", "elatiivi"],
        steps=[
            info("🙋", "The first question",
                 "The YKI speaking test and every form start the same way: who are you? Today you say your name, your country "
                 "and your languages."),
            expl("Your name",
                 "<fi>Minun nimeni on Linh.</fi> My name is Linh. <fi>Minä olen Linh.</fi> I am Linh. In writing and in "
                 "the test, use <fi>minä olen</fi>. Friends say <fi>mä oon</fi>; that comes later.",
                 "Minun nimeni on Linh. Minä olen Linh."),
            repeat("My name is ...", "Minun nimeni on Linh.", "My name is Linh."),
            expl("Where you are from",
                 "<fi>Mistä sinä olet kotoisin?</fi> Where are you from? <fi>Olen kotoisin Vietnamista.</fi> "
                 "I am from Vietnam. The country gets <fi>-sta</fi>, or <fi>-stä</fi> when the word has ä, ö or y: "
                 "<fi>Turkista, Ukrainasta, Egyptistä</fi>.",
                 "Mistä sinä olet kotoisin? Olen kotoisin Vietnamista."),
            pairs("From which country?", "Match the country with 'from the country'.",
                  [("Vietnam", "Vietnamista"), ("Turkki", "Turkista"), ("Ukraina", "Ukrainasta"), ("Egypti", "Egyptistä")]),
            repeat("I am from ...", "Olen kotoisin Turkista.", "I am from Turkey."),
            expl("Your languages",
                 "<fi>Minun äidinkieleni on turkki.</fi> My mother tongue is Turkish. <fi>Puhun turkkia ja vähän "
                 "suomea.</fi> I speak Turkish and a little Finnish. After <fi>puhun</fi> the language gets -a or -ä: "
                 "<fi>suomea, englantia, turkkia</fi>. Language names are written in small letters.",
                 "Minun äidinkieleni on turkki. Puhun turkkia ja vähän suomea."),
            gap("A little Finnish", "Puhun englantia ja vähän ___.", "I speak English and a little Finnish.",
                opts("suomea", "suomi", "Suomessa"), "Yes: puhun suomea.",
                "After puhun the language ends in -a: suomea."),
            build("Build it", "Say: I am from Vietnam.", "Olen kotoisin Vietnamista.",
                  ["Olen", "kotoisin", "Vietnamista", "Vietnam", "olet"], "I am from Vietnam.",
                  "Perfect.", "Olen first, then kotoisin, then the country with -sta."),
            dialogue("The test begins", "The YKI speaking test asks the first questions on the computer.", TESTER, [
                ("Mikä sinun nimesi on?", "What is your name?", [
                    ("Minun nimeni on Linh.", True, "Good: a full sentence."),
                    ("Olen kotoisin Vietnamista.", False, "That says where you are from. The question is your name.")]),
                ("Mistä sinä olet kotoisin?", "Where are you from?", [
                    ("Olen kotoisin Vietnamista.", True, "Good."),
                    ("Puhun vietnamia.", False, "That is your language. The question is where you are from.")]),
                ("Mitä kieliä sinä puhut?", "Which languages do you speak?", [
                    ("Puhun vietnamia, englantia ja vähän suomea.", True, "Excellent."),
                    ("Minun nimeni on Linh.", False, "The question is about languages: Puhun ...")]),
            ]),
            info("🗣️", "Your three sentences",
                 "Minun nimeni on ... Olen kotoisin ...sta. Puhun ...a ja vähän suomea. Say them about yourself, out loud."),
        ]),
    dict(
        slug="asun-suomessa", title="Asun Suomessa", shape="discovery", minutes=6,
        description="Say where you live and how long you have lived in Finland.",
        practice_words=["asua", "vuosi", "Suomi", "kauan"],
        grammar=["inessiivi", "adessiivi", "perfekti"],
        steps=[
            info("🏠", "Where you live",
                 "YKI and every office ask where you live and how long you have lived in Finland. Two sentences answer both."),
            expl("asua: to live",
                 "<fi>Minä asun</fi>, <fi>sinä asut</fi>, <fi>hän asuu</fi>. <fi>Asun Suomessa.</fi> I live in Finland. "
                 "Most places get <fi>-ssa/-ssä</fi>, some get <fi>-lla/-llä</fi>. Learn your own town as one word.",
                 "Minä asun. Sinä asut. Hän asuu. Asun Suomessa."),
            pairs("Where?", "Match the town with 'in the town'.",
                  [("Helsinki", "Helsingissä"), ("Espoo", "Espoossa"), ("Vantaa", "Vantaalla"), ("Tampere", "Tampereella")]),
            repeat("I live in Vantaa", "Asun Vantaalla.", "I live in Vantaa."),
            quiz("In Finland", "How do you say 'I live in Finland'?",
                 opts("Asun Suomessa.", "Asun Suomi.", "Asun Suomesta."),
                 "Right: Suomessa = in Finland.", "In Finland is Suomessa."),
            expl("How long?",
                 "<fi>Olen asunut Suomessa viisi vuotta.</fi> I have lived in Finland for five years. Learn it as one block: "
                 "<fi>olen asunut</fi> + place + number + <fi>vuotta</fi>. One year is <fi>vuoden</fi>: "
                 "<fi>Olen asunut Suomessa vuoden.</fi>",
                 "Olen asunut Suomessa viisi vuotta. Olen asunut Suomessa vuoden."),
            gap("Three years", "Olen asunut Suomessa kolme ___.", "I have lived in Finland for three years.",
                opts("vuotta", "vuosi", "vuoden"), "Yes: kolme vuotta.",
                "After a number from two up, vuosi becomes vuotta."),
            repeat("Five years", "Olen asunut Suomessa viisi vuotta.", "I have lived in Finland for five years."),
            scene("At the service point", "At the Kela service point the clerk asks: Kauanko olet asunut Suomessa?",
                  "Answer: two years.",
                  opts("Olen asunut Suomessa kaksi vuotta.", "Asun Suomessa.", "Kaksi vuosi."),
                  "Right. A full sentence with olen asunut.",
                  "The clerk asks how long. Answer with olen asunut ... kaksi vuotta."),
            build("Build it", "Say: I live in Tampere.", "Asun Tampereella.",
                  ["Asun", "Tampereella", "Tampere", "asut"], "I live in Tampere.",
                  "Good.", "Asun + Tampereella."),
            info("🧩", "Add it to your answer",
                 "Minun nimeni on ... Olen kotoisin ... Asun ... Olen asunut Suomessa ... vuotta. That already answers the first "
                 "speaking questions."),
        ]),
    dict(
        slug="perhe", title="Perhe", shape="discovery", minutes=6,
        description="Talk about your family with minulla on, and count from one to ten.",
        practice_words=["perhe", "mies", "vaimo", "poika", "tytär", "lapsi", "minulla"],
        grammar=["omistusrakenne", "partitiivi"],
        steps=[
            info("👨‍👩‍👧", "Family",
                 "The speaking test and many forms ask about your family. Finnish has no verb 'to have', so you learn a new pattern."),
            expl("minulla on: I have",
                 "<fi>Minulla on tytär.</fi> I have a daughter. <fi>Minulla on mies ja tytär.</fi> I have a husband and a daughter. "
                 "Literally: at me is a daughter.", "Minulla on tytär. Minulla on mies ja tytär."),
            pairs("The family", "Match each word with its meaning.",
                  [("mies", "husband"), ("vaimo", "wife"), ("poika", "son"), ("tytär", "daughter")]),
            expl("One to ten",
                 "<fi>yksi, kaksi, kolme, neljä, viisi, kuusi, seitsemän, kahdeksan, yhdeksän, kymmenen</fi>. After two or "
                 "more the word gets -a or -ä: <fi>kaksi lasta</fi> (two children), <fi>kolme veljeä</fi> (three brothers).",
                 "yksi, kaksi, kolme, neljä, viisi, kuusi, seitsemän, kahdeksan, yhdeksän, kymmenen"),
            repeat("I have a daughter", "Minulla on yksi tytär.", "I have one daughter."),
            gap("Two children", "Minulla on kaksi ___.", "I have two children.",
                opts("lasta", "lapsi", "lapset"), "Yes: kaksi lasta.",
                "After kaksi, lapsi becomes lasta."),
            listen("Listen", "Minulla on mies ja kaksi lasta.", "How many people are in her family, with her?",
                   opts("Four", "Three", "Two"), "Right: she, her husband and two children.",
                   "Mies is one, kaksi lasta is two, and she is one more: four."),
            build("Build it", "Say: I have three children.", "Minulla on kolme lasta.",
                  ["Minulla", "on", "kolme", "lasta", "lapsi", "Minä"], "I have three children.",
                  "Good.", "Minulla on, then the number, then lasta."),
            dialogue("Family questions", "The YKI speaking test asks about your family.", TESTER, [
                ("Onko sinulla perhettä?", "Do you have a family?", [
                    ("On. Minulla on mies ja tytär.", True, "Good: on (yes) and then the family."),
                    ("Olen kotoisin Vietnamista.", False, "The question is about your family.")]),
                ("Kuinka vanha tyttäresi on?", "How old is your daughter?", [
                    ("Hän on yhdeksän vuotta vanha.", True, "Excellent."),
                    ("Minulla on yhdeksän.", False, "Say her age: Hän on yhdeksän vuotta vanha.")]),
            ]),
            info("🧩", "Your answer grows",
                 "Name, country, languages, home, years in Finland, and now family. Next: the forms you fill in Finland."),
        ]),
    dict(
        slug="lomake", title="Lomake", shape="drill", minutes=6,
        description="Read and fill the personal details of a Finnish form: Kela, the health centre, the YKI registration.",
        practice_words=["etunimi", "sukunimi", "syntymäaika", "osoite", "puhelinnumero", "sähköposti", "kansalaisuus"],
        grammar=["sanasto"],
        steps=[
            info("📝", "Forms everywhere",
                 "Kela, the health centre, the library and the YKI registration ask the same details. Learn the form words once."),
            expl("Name and birth",
                 "<fi>etunimi</fi> first name, <fi>sukunimi</fi> surname, <fi>syntymäaika</fi> date of birth, "
                 "<fi>kansalaisuus</fi> citizenship, <fi>äidinkieli</fi> mother tongue.",
                 "etunimi, sukunimi, syntymäaika, kansalaisuus, äidinkieli"),
            pairs("Who are you?", "Match the form word with its meaning.",
                  [("etunimi", "first name"), ("sukunimi", "surname"), ("syntymäaika", "date of birth"),
                   ("äidinkieli", "mother tongue")]),
            expl("Contact details",
                 "<fi>osoite</fi> address, <fi>postinumero</fi> postal code, <fi>puhelinnumero</fi> phone number, "
                 "<fi>sähköposti</fi> email. Together they are <fi>yhteystiedot</fi>, contact details.",
                 "osoite, postinumero, puhelinnumero, sähköposti, yhteystiedot"),
            cats("Sort the form", "Sort the form words.", [("nimi", "Name"), ("yhteys", "Contact details")],
                 [("etunimi", "nimi"), ("sukunimi", "nimi"), ("osoite", "yhteys"), ("puhelinnumero", "yhteys"),
                  ("sähköposti", "yhteys")]),
            expl("Dates",
                 "Finnish dates go day, month, year: <fi>5.11.1991</fi> is 5 November 1991.", ""),
            quiz("Born when?", "The form says: Syntymäaika 5.11.1991. When was the person born?",
                 opts("5 November 1991", "11 May 1991"), "Right: day first, then month.",
                 "Finnish dates start with the day: 5 is the day, 11 is the month."),
            tf("First name?", "On a Finnish form, sukunimi means your first name.", False,
               "Sukunimi is the surname. Your first name is etunimi."),
            scene("Mehmet's form", "Mehmet is a citizen of Turkey. His mother tongue is Turkish. The form asks: Äidinkieli.",
                  "What does he write?", opts("turkki", "Turkki", "suomi"),
                  "Right: the language, in small letters.",
                  "Äidinkieli asks for the language, written in small letters: turkki. Turkki with a capital is the country."),
            info("✍️", "Fill it in for yourself",
                 "Write your own etunimi, sukunimi, syntymäaika, osoite and puhelinnumero on paper. You will meet these words "
                 "in every office."),
        ]),
    dict(
        slug="esittaydy", title="Esittäydy", shape="drill", minutes=7,
        description="Put it together: answer the first YKI speaking questions in full sentences, and never stay silent.",
        practice_words=["asua", "kauan", "kotoisin", "puhua"],
        grammar=["persoonamuodot"],
        steps=[
            info("🎤", "The speaking test",
                 "In YKI you speak to a computer. A voice asks a question once, then records your answer. Nobody can repeat "
                 "it for you, so never stay silent: answer in a full sentence."),
            expl("Answer with the question's verb",
                 "<fi>Missä sinä asut?</fi> <fi>Asun Vantaalla.</fi> Take the verb from the question and answer in a full "
                 "sentence, not one word. Full sentences show the examiners what you can do.",
                 "Missä sinä asut? Asun Vantaalla."),
            pairs("Question and answer", "Match each question with its answer.",
                  [("Mikä sinun nimesi on?", "Minun nimeni on Linh."), ("Mistä olet kotoisin?", "Olen kotoisin Vietnamista."),
                   ("Missä asut?", "Asun Vantaalla."), ("Mitä kieliä puhut?", "Puhun vietnamia ja suomea.")]),
            expl("If your head goes empty",
                 "Start with the question's own verb and say what you can. <fi>Missä sinä asut?</fi> <fi>Asun ...</fi> "
                 "<fi>Mistä sinä olet kotoisin?</fi> <fi>Olen kotoisin ...</fi> A short sentence gets points. Silence gets none.",
                 "Missä sinä asut? Asun Vantaalla. Mistä sinä olet kotoisin? Olen kotoisin Vietnamista."),
            quiz("How do you start?", "The computer asks: Kauanko olet asunut Suomessa? How do you start your answer?",
                 opts("Olen asunut ...", "Asun ...", "Anteeksi, voitteko toistaa?"),
                 "Right: the question says olet asunut, so you say olen asunut.",
                 "The computer does not repeat the question. Give the verb back: Olen asunut ..."),
            repeat("Name and country", "Minun nimeni on Linh ja olen kotoisin Vietnamista.",
                   "My name is Linh and I am from Vietnam."),
            repeat("Home and years", "Asun Vantaalla ja olen asunut Suomessa viisi vuotta.",
                   "I live in Vantaa and I have lived in Finland for five years."),
            repeat("Family", "Minulla on mies ja yksi tytär.", "I have a husband and one daughter."),
            spot("Find the mistake", "Linh wants to say 'I live in Vantaa'.", "Minä asun Vantaa.",
                 opts("Vantaa needs an ending: Vantaalla.", "Minä is wrong.", "Asun is wrong."),
                 "Right: Asun Vantaalla.", "Minä and asun are fine. In Vantaa is Vantaalla."),
            dialogue("The whole speaking test", "The YKI test asks four questions on the computer. Answer each in a full sentence.", TESTER, [
                ("Mikä sinun nimesi on?", "What is your name?", [
                    ("Minun nimeni on Linh.", True, "Good."), ("Linh.", False, "Use a full sentence.")]),
                ("Missä sinä asut?", "Where do you live?", [
                    ("Asun Vantaalla.", True, "Good."), ("Vantaa.", False, "Use a full sentence: Asun Vantaalla.")]),
                ("Kauanko olet asunut Suomessa?", "How long have you lived in Finland?", [
                    ("Olen asunut Suomessa viisi vuotta.", True, "Excellent."),
                    ("Viisi.", False, "A full sentence: Olen asunut Suomessa viisi vuotta.")]),
                ("Mitä kieliä sinä puhut?", "Which languages do you speak?", [
                    ("Puhun vietnamia, englantia ja vähän suomea.", True, "Excellent."),
                    ("Suomea.", False, "One word. Give the verb back: Puhun vietnamia, englantia ja vähän suomea.")]),
            ]),
            info("🏁", "Your 30-second introduction",
                 "Say your four sentences in a row, out loud, without stopping. Next is the checkpoint: one small task from "
                 "each part of YKI."),
        ]),
    dict(
        slug="tarkistus-1", title="Tarkistus 1: mini-YKI", shape="drill", minutes=7,
        description="Checkpoint: one small task from each YKI part. Reading, listening, writing and speaking.",
        practice_words=["teksti", "kysymys", "viesti"],
        grammar=["kertaus"],
        steps=[
            info("⏱️", "Checkpoint 1",
                 "One small task from each part of YKI: lue, kuuntele, kirjoita, puhu. No new words. Show what you can do."),
            expl("Lue: read the text",
                 "<fi>Hei! Minun nimeni on Mehmet. Olen kotoisin Turkista. Asun Vantaalla. Olen asunut Suomessa kuusi vuotta. "
                 "Minulla on vaimo ja kaksi lasta. Puhun turkkia, englantia ja vähän suomea.</fi>",
                 "Hei! Minun nimeni on Mehmet. Olen kotoisin Turkista. Asun Vantaalla. Olen asunut Suomessa kuusi vuotta. "
                 "Minulla on vaimo ja kaksi lasta. Puhun turkkia, englantia ja vähän suomea."),
            tf("Lue: true or false?", "Mehmet asuu Helsingissä.", False, "Mehmet asuu Vantaalla."),
            quiz("Lue: answer the question", "Kauanko Mehmet on asunut Suomessa?",
                 opts("Kuusi vuotta", "Kaksi vuotta", "Viisi vuotta"), "Right: kuusi vuotta.",
                 "The text says: Olen asunut Suomessa kuusi vuotta."),
            listen("Kuuntele", "Hei, minä olen Anna. Olen kotoisin Ukrainasta. Asun Espoossa. Minulla on yksi tytär.",
                   "Missä Anna asuu?", opts("Espoossa", "Ukrainassa", "Vantaalla"), "Right: Asun Espoossa.",
                   "Anna is from Ukraine, but she lives in Espoo: Asun Espoossa."),
            listen("Kuuntele uudelleen", "Hei, minä olen Anna. Olen kotoisin Ukrainasta. Asun Espoossa. Minulla on yksi tytär.",
                   "Onko Annalla lapsia?", opts("On, yksi tytär.", "On, kaksi poikaa.", "Ei ole."), "Right: Minulla on yksi tytär.",
                   "Listen for minulla on: yksi tytär."),
            gap("Kirjoita: a message to the teacher", "Hei! Minun nimeni on Linh. Olen ___ Vietnamista.",
                "Hi! My name is Linh. I am from Vietnam.", opts("kotoisin", "asun", "puhun"),
                "Right: olen kotoisin Vietnamista.", "From a country: olen kotoisin ...sta."),
            gap("Kirjoita: continue the message", "Asun Vantaalla. Puhun vietnamia ja vähän ___.",
                "I live in Vantaa. I speak Vietnamese and a little Finnish.", opts("suomea", "suomi", "Suomessa"),
                "Right: vähän suomea.", "After puhun: suomea."),
            spot("Kirjoita: check the message", "The last sentence of Linh's message.", "Minulla on kaksi lapsi.",
                 opts("lapsi should be lasta.", "Minulla should be Minä.", "kaksi should be kahden."),
                 "Right: kaksi lasta.", "After a number from two up: lasta."),
            repeat("Puhu: your introduction", "Minun nimeni on Linh. Asun Vantaalla. Olen asunut Suomessa viisi vuotta.",
                   "My name is Linh. I live in Vantaa. I have lived in Finland for five years."),
            info("🎉", "Checkpoint 1 done",
                 "You can now read YKI instructions, answer the first speaking questions, fill a form and write three "
                 "sentences about yourself. Next: a Juka call where you introduce yourself, out loud and freely."),
        ]),
]


def main():
    for n, l in enumerate(LESSONS, 1):
        steps = [dict(s, id=f"step-{i}") for i, s in enumerate(l["steps"], 1)]
        content = {"kind": "lesson", "shape": l["shape"], "steps": steps, "practice_words": l["practice_words"],
                   "grammar_concepts": l["grammar"], "learning_language_code": "fi"}
        doc = {"title": l["title"], "description": l["description"], "category": "YKI: Minä ja YKI",
               "difficulty_level": "beginner", "cefr_level": "A1", "estimated_duration_minutes": l["minutes"],
               "lesson_content": content}
        path = HERE / f"ch1_{n}_{l['slug']}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        print(path.name, len(steps), "steps")


if __name__ == "__main__":
    main()
