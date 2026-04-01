---
layout: post
title: "How I Used an AI Team to Research My Grandfather's Holocaust History"
date: 2026-03-31
tags: [ai-agents, squad, github-copilot, holocaust-research, genealogy, family-history]
---

My grandfather Menachem was a Holocaust survivor. He barely talked about it.

He was born Menachem Rot (רוט) in 1929 in Stanisławów, Poland — a city with about 25,000 Jews before the war, and fewer than 1,500 survivors after it. When he was around nine years old, his biological father — a baker — emigrated to America. His mother Genya remarried a man named Dresher, and the family took his name.

Then the war came. His stepfather was killed by Ukrainian collaborators. His mother, his sister Helena, his baby brother Kalman — all murdered. A Ukrainian woman named **Mariya Leshchuk** hid little Menachem in her village of Klubowce for roughly twenty months. He survived. He made it to Israel in 1948.

After he passed away, we had questions. A lot of questions.

**Who was his biological father? What was his first name?** Nobody in the family knew. The name had been lost — swallowed by decades of silence and the chaos of a world war.

I decided to find out.

---

## The First Attempt (and 38 Fabricated "Facts")

Let me start with a confession.

My first attempt at using AI for this research was a disaster.

I took the 55-page testimony my grandfather gave in 1991 — handwritten in Hebrew — and fed it to an AI session. The results looked incredible. Detailed family trees, names, dates, locations. A rich tapestry of a family before the war.

**Almost none of it was real.**

When I fact-checked the output, I found **38+ fabricated claims**. The AI had invented a name for my grandfather's father — "Shlomo" — when the real name is still unknown. It invented a brother named "Yosef." A sister named "Leah." A wife named "Lily." It said the father went to London, when the testimony clearly says America.

Worst of all, it fabricated an entire place — the "Rot forced labor camp" — that **never existed**. It had taken the statistic of 469 Rot-surnamed victims from Yad Vashem and turned it into a fictional concentration camp named after the family.

**There was no "Rot forced labor camp."** There were 469 real people with that surname who were murdered.

I shut the whole thing down. AI hallucinating about your family's groceries is annoying. AI hallucinating about **real people who were murdered in the Holocaust** is something else entirely.

I needed a different approach.

![Squad onboarding — asking about the research subject](/assets/img/posts/holocaust-research/squad-onboarding.png)

*Squad's first interaction — gathering details about Menachem before launching the research*

![Squad setting up the research project](/assets/img/posts/holocaust-research/squad-setup-research.png)

*The fact table confirmed, Seven and Wiesenthal ready to hit the databases in parallel*

---

## Enter Squad

[Squad](https://bradygaster.github.io/squad/) is an open-source framework created by [Brady Gaster](https://github.com/bradygaster) for building specialized AI teams on top of GitHub Copilot. I joined Brady as CTO, and together we've been pushing it forward. Each agent has a charter — a strict set of rules about what it does, what it doesn't do, and what standards it has to meet.

For this research, I assembled a team of nine agents:

![The Holocaust Research Squad — 9 specialized agents](/assets/img/posts/holocaust-research/squad-team-roster.png)

*The full squad — 9 agents, each with a specific expertise, all running claude-opus-4.6*

| Agent | Role |
|-------|------|
| **Seven** | Lead Holocaust Researcher — coordinates priorities, specializes in Yad Vashem and testimony analysis |
| **Wiesenthal** | Archive & Database Specialist — searches Holocaust databases, captures screenshots, logs results |
| **Q** | Devil's Advocate & Fact Checker — verifies every claim, catches hallucinations, blocks unverified content |
| **Scribe** | Documentation & Record Keeper — maintains the research timeline and family tree |
| **Galicia** | Galician Records Specialist — navigates Polish, Ukrainian, and Austrian archives |
| **Ellis** | Immigration & Diaspora Researcher — Ellis Island, NARA, NYC records |
| **Sofer** | Hebrew/Yiddish Paleographer — reads handwritten Hebrew testimony, character-by-character analysis |
| **Miriam** | Professional Genealogist — family tree construction, living relatives, DNA matching |
| **Gutenberg** | Book Designer & Publisher — generates illustrated memorial books in multiple languages |

The critical difference from my first attempt? **The workflow.**

Every single finding must pass through Q before it enters any document. Q doesn't just check sources — Q actively challenges conclusions, looks for logical gaps, and flags anything that isn't backed by a primary source.

The verification framework uses a color-coded system:

- 🟢 **FROM TESTIMONY** — directly stated in Menachem's own words
- 🔵 **NEW FROM YAD VASHEM DB** — found in Yad Vashem's database
- 🟣 **NEW FROM OTHER ARCHIVES** — Arolsen, JewishGen, FamilySearch, etc.
- 🟡 **CROSS-REFERENCED** — confirmed by multiple independent sources
- ⚠️ **UNVERIFIED** — plausible but not confirmed

**No color code, no entry in the report.** Period.

![Squad searching databases](/assets/img/posts/holocaust-research/squad-searching.png)

*The squad running parallel database searches across Yad Vashem, Arolsen Archives, and JewishGen*

---

## What the Squad Actually Found

The team searched over 20 databases in parallel: Yad Vashem, Arolsen Archives, JewishGen, FamilySearch, Gesher Galicia, USC Shoah Foundation, Steve Morse One-Step Tools, USHMM, the National Library of Israel, historical Jewish newspaper archives, and more.

Here's what they uncovered.

### The 1939 Polish Census

Wiesenthal and Galicia found the family in the **1939 Stanislawow Census**.

At **Roguskiego 10**, they identified a household:

```
Head of household: Adolf Drescher (born 1906-08-01, candle factory worker)
Wife: Genia Roth (born 1905-05-21)
Daughter: Helena (born 1928-09-25)
Son: Michał [Menachem] (born 1930-02-07)
```

This was huge. A bureaucratic record from August 1939 — one month before the German invasion — confirming the family existed at that address, with those names, at those ages.

But Seven's initial analysis drew a conclusion: Adolf Drescher was the biological father.

**Q disagreed.**

### The Q Moment

This is the part that convinced me the whole approach was worth it.

Q reviewed the census data against the verified facts from Menachem's testimony and flagged a critical error:

> "The census finding is **GENUINE AND HIGHLY SIGNIFICANT** — but Adolf DRESCHER is **the stepfather**, not the biological father."

The logic was airtight:

- The testimony says the biological father was a **baker** who emigrated to **America** around 1938
- Adolf Drescher was a **candle factory worker** still in Stanisławów in August 1939
- The biological father's surname was **Rot/Roth** — Genia's maiden name
- Adolf's surname was **Drescher** — the surname the family adopted **after** the remarriage
- If Adolf were the biological father, the children would have been born with the name Drescher, not Rot

Every single piece of evidence pointed the same way. **Adolf was the stepfather who married Genia in 1939, not the biological father who left for America in 1938.**

Without Q catching this, that misidentification would have been embedded in every report. In my first attempt — with no fact-checker — it would have become "fact."

![Q fact-check](/assets/img/posts/holocaust-research/q-factcheck.png)

*Q's analysis proving Adolf Drescher was the stepfather, not the biological father*

---

### Pages of Testimony — Character by Character

Yad Vashem's Pages of Testimony are one-page forms filled out by survivors and relatives to memorialize those who were murdered. They're handwritten — often in Hebrew or Yiddish — and the penmanship ranges from careful to barely legible.

Sofer analyzed multiple Pages of Testimony connected to the family, producing over 70 image crops with character-by-character Hebrew analysis:

**Form 1: Tzili Berg née Rot** — A relative. Seamstress, born 1906 in Stanisławów. Murdered in 1943. The maiden name **רוט (Rot)** was the critical link connecting her to Menachem's family.

**Form 2: Helena Dresher** — Menachem's older sister. Student, born 1928 in Stanisławów. Murdered in 1943. Mother's name listed as Elka (likely a variant of Genya/Genia).

**Form 3: Baby brother** — Born around 1939. No first name recorded anywhere. Murdered in 1943. He was an infant.

The hardest part was the father's name field. Sofer found a possible reading — but rated it at **medium confidence** only. The handwriting was ambiguous. Rather than guess, the team flagged it as ⚠️ **UNVERIFIED** and identified archival records that could provide definitive confirmation.

That restraint — the willingness to say "we don't know yet" instead of making something up — was exactly what the first attempt lacked.

![Pages of Testimony](/assets/img/posts/holocaust-research/pot-forms.png)

*Analyzing handwritten Pages of Testimony — Hebrew character-by-character extraction*

---

### 469 Victims, 73 Submitters, 8 Survivors

Miriam's search of Yad Vashem revealed the scale of the Rot family's loss:

- **469 Holocaust victims** with the Rot/Roth surname from the Stanisławów area
- **73 people submitted Pages of Testimony** for Rot family members
- **8 confirmed survivors** in the records

Those 73 submitters are leads to living relatives. Each one is a person who, at some point after the war, walked into Yad Vashem (or mailed a form) to memorialize someone they lost. They are survivors, or children of survivors, or relatives who emigrated before the war.

Ellis and Miriam traced 26 of those submitters through online records — Google, Facebook, Geni.com, MyHeritage, Israeli film databases, genealogy projects. One name kept surfacing as a high-confidence lead: **Yafa Shnir**, a submitter connected to multiple Rot family testimonies.

---

### The Open Question

After all of this research — across 20+ databases, hundreds of records, thousands of data points — one question remains at the top of the list:

**What was Menachem's biological father's first name?**

The team identified two leads that could answer it:

1. **Ancestry Collection 62571** — Stanislawow passport applications from the interwar period. If the father applied for a passport before emigrating to America, his full name would be on file.

2. **Jewish marriage records from 1924–1930** — If Genia Rot married the baker in a Jewish ceremony in Stanisławów, the record would name both parties. These records **exist** in the Ukrainian state archives.

Neither has been searched yet. The leads are documented, prioritized, and ready.

---

## The Memorial Books

Gutenberg took everything the team verified and produced **trilingual illustrated memorial books** — in English, Spanish, and Hebrew — with embedded archival images, custom maps, and source citations on every claim.

Four custom maps show the journey:

- The Rot family's region in Eastern Galicia
- Menachem's route: **Stanisławów → Klubowce → Lwów → Kraków → Warsaw → Haifa**
- The Stanisławów ghetto
- The deportation route to the Bełżec death camp

The books follow the same dignity-preserving rules as the rest of the research: maps for context, testimony in the subject's own words, no graphic imagery. Every fact has a source. Every unknown is labeled as unknown.

The final output: six HTML books, six PDFs, three styled research reports, and a comprehensive fact-check audit.

📥 **Download the memorial books:**
- [**English** (PDF)](https://drive.google.com/file/d/1lQef3b0CL2xna9LfmK_kyWs5CKebgRbU/view?usp=sharing)
- [**Hebrew / עברית** (PDF)](https://drive.google.com/file/d/1AOt6Tl7H3BXtI8dVwf_lJLn7RQ_ZCL-b/view?usp=drive_link)
- [**Spanish / Español** (PDF)](https://drive.google.com/file/d/1FkypokrhcraRcrC8xJa9r3DIb7Xrqrqd/view?usp=sharing)

![Illustrated book](/assets/img/posts/holocaust-research/book-cover.png)

*The generated memorial book — navy and gold design with embedded archival images and custom maps*

---

## What I Learned

**AI doesn't solve the problem. The team design solves the problem.**

A single AI session — no matter how capable — will hallucinate about Holocaust victims just as readily as it hallucinates about anything else. The difference is that hallucinating about dead people isn't a minor inaccuracy. It's an injury to memory.

What worked was not better prompting. It was **structure**:

- Separate the researcher from the fact-checker
- Give the fact-checker a veto
- Require source attribution on every claim
- Treat "we don't know" as a valid, dignified answer
- Document what you *didn't* find as carefully as what you did

The Squad framework let me encode those rules into agent charters that persisted across every session. Q wasn't occasionally rigorous — Q was **always** rigorous, because the charter demanded it.

---

## The Template

I open-sourced the squad configuration as a template so other families can do this.

🔗 **[holocaust-research-squad-template](https://github.com/tamirdresher/holocaust-research-squad-template)**

The template includes:

- All nine agent charters with built-in anti-hallucination protocols
- The verification framework (🟢🔵🟣🟡⚠️)
- Routing rules that enforce the Q fact-check gate
- Research templates for Yad Vashem, Arolsen, JewishGen, immigration records
- Book generation scripts for trilingual memorial books
- The workflow ceremonies and documentation standards

Fork it. Customize the agents for your family. Point Wiesenthal at the archives where your family's records might be. Let Q catch the errors before they become "facts."

![Template repo](/assets/img/posts/holocaust-research/template-repo.png)

*The open-source template on GitHub — fork it and start researching your family's history*

---

## A Call to Action

If you have Holocaust survivors in your family, you probably have the same questions I did. Names that were never spoken. Places that were never described. Relatives that were never mentioned.

Those records exist. They're in Yad Vashem, in the Arolsen Archives, in Polish and Ukrainian state archives, in immigration records at Ellis Island, in passport applications gathering dust in a folder somewhere. They're written in Hebrew and Yiddish and Polish and German, scattered across institutions on three continents.

No single person can search all of those in a lifetime. But a well-designed AI team — with the right protocols, the right fact-checking, and the right respect for the subject matter — can cover extraordinary ground.

My grandfather's biological father's first name is still out there. The marriage records exist. The passport applications exist. We just haven't searched them yet.

**We will.**

---

*The research described in this post used [Squad](https://github.com/tamirdresher/squad), an AI team framework built on GitHub Copilot. The research repository is private to protect family information. The template is available at [holocaust-research-squad-template](https://github.com/tamirdresher/holocaust-research-squad-template).*

*If you'd like to use this approach for your own family research, or if you have experience with Holocaust genealogy and want to help improve the template, reach out. This work is too important to do alone.*
