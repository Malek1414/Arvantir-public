# Arvantir pitch v2 (about 2:00 spoken)

A = Sami, B = Malek. Shots: face, `arvantir-demo-v3.mp4` (demo 0:00 to 0:27, animation 0:27 to 0:48).

| time | who | says | shot |
|---|---|---|---|
| 0:00 | A | On Thursday, Arvana told us something honest. Sorting leads with agents does not work. So they do it by hand. We wanted to build the machine you can actually trust. | face |
| 0:10 | A | In Munich there is a butcher called Emin Fleisch. A real business, with a real person in charge. Today, Arvantir found it, named that person, scored it 100 out of 100, and said: send a letter, not an email. | demo, Emin Fleisch card |
| 0:25 | B | Here is how. You type any niche. Arvantir runs eight steps. Discover finds where these firms really live: guild directories, member lists, trade fairs. Harvest reads every firm. Normalize merges branches into one row. Darkcheck asks if any database already knows them. Enrich reads the legal notice and finds the person in charge. Signals looks for fresh news. Rank scores the fit. Channel picks the way in. | animation |
| 0:55 | B | Rank is our own model. We fine-tuned a small reranker on 3,327 labelled pairs from 1,212 companies. Training took 13 minutes. On 330 hand-checked leads, it agrees with a human 98 percent of the time. A fixed scoring formula reaches 80. And it costs nothing per lead. | animation, bars |
| 1:12 | B | And this is not a slide. The whole pipeline runs today, end to end, and plugs straight into what you already use: a Clay table by CSV or webhook, a Supabase database, a Claude Code skill. No migration, no new tool for your team. | demo, table |
| 1:25 | A | Today it ran on six niches. 347 ranked leads. 134 with the name of the person in charge, straight from the company's own legal notice. | demo, table |
| 1:38 | A | Emin Fleisch is not in a database of 17 million companies. Neither are 186 other firms we found today. For doctors and pharmacies, that is 86 percent. Every one of them ranked, with a reason it fits. | face |
| 1:53 | A | Give us the niche you gave up on. On Monday, you get the list nobody else has. | face |

About 300 words, roughly 2:00 at 150 words a minute.

## Facts behind the lines

- Arvana told Sami that sorting leads with agents does not work well and they would rather sort by hand (interview, `context/sami-notizen.md`)
- Emin Fleisch GmbH, München 80337: score 100, tier A, channel letter, decision maker from the legal notice (`data/run_143435.json`)
- Eight steps discover, harvest, normalize, darkcheck, enrich, signals, rank, channel (`docs/ARCHITECTURE.md`, `bench/RUNS.md`)
- Re-ranker arvantir-rr-v1: 3,327 train pairs, 1,212 companies, 758.9 s training (`models/arvantir-rr-v1/arvantir_train.json`)
- 98 % vs 80 % agreement on 330 gold pairs, 0.00 USD per 1,000 leads (`bench/results.md`)
- Running end to end: pipeline `arvantir/pipeline.py`, Clay export and webhook `adapters/clay.py`, Supabase schema `adapters/supabase.sql` + `adapters/supabase.py`, Claude Code skill `skills/arvantir/SKILL.md`
- 6 niches, 347 ranked leads, 134 with named decision maker (`bench/RUNS.md`)
- 187 firms not found in BigPicture (17,154,017 companies): 84 by domain plus 103 by name and city (name and city is weaker evidence); Emin Fleisch checked by domain, not found (knowncheck lookup, 31.10. 16:35); doctors and pharmacies 38 of 44 by domain = 86 % (`bench/RUNS.md`, knowncheck)

Left out on purpose: how Arvana works today, Stephan's skills, prices.
