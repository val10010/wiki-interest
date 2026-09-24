---
name: wiki-interest
description: Measure and compare public interest in a topic across Wikipedia language editions (Wikimedia pageviews) to help B2C founders choose which topics, courses or languages/markets to invest in next. Produces trend numbers with a reliability rating, a chart, and a one-page PDF report. Use for questions like "is interest in X growing in Ukrainian?", "compare X in Polish vs Czech", "which language audiences should we explore next?".
license: MIT
compatibility: Requires Python 3.9+, bash and network access to wikimedia.org; the launcher installs requests, numpy and matplotlib into a local .venv on first run.
---

# Wiki Interest

All data work is done by the CLI `scripts/wi`. Run it from this skill's root directory, or by its
full path `<skill dir>/scripts/wi` from anywhere (it creates its own Python venv on first run and resolves
`runs/...` against the skill root). **Never compute statistics yourself — run the tool and quote its numbers.**

## Hard rules (check your answer against them before sending)

1. **Direction and numbers come from `verdicts`.** Quote each language's verdict sentence
   (translate it if the user writes in another language), don't rephrase it. Never call a
   series "growing" unless its verdict says so. Never merge numbers from different columns
   into a range.
2. **No facts outside the tool output.** No market traits, communities, cultural claims or
   languages you did not analyse. If you think something is worth checking, say "worth checking",
   not that it is true.
3. **Proxy = different concept.** If a `PROXY` warning appears, say in the answer that this
   language measures a different concept and the comparison is not like-for-like.
4. **Send `answer_skeleton` whole, with only its slot filled** — it already contains the
   limits line (views ≠ willingness to pay), seasonal peaks and proxy notes.

## Workflow

1. **Translate the request into arguments**
   - `--topic`: the topic as a Wikipedia article name, usually in English
     (`"Intermittent fasting"`, `"Astronomy"`). You may also search in another language
     with `--search-lang uk` (e.g. `--topic "астрономія" --search-lang uk`).
     Several topics → repeat `--topic`. Several related articles counted as one topic → join with `+`
     (`--topic "Astronomy+Astrophysics"`). Already know the Wikidata id → `--topic Q333`.
   - `--langs`: Wikipedia language codes, comma-separated (`uk,pl,cs`), or `top:15`
     (15 largest editions that have the article), or `all`.
     Codes: English en, Ukrainian uk, Polish pl, Czech cs, German de, Spanish es, French fr,
     Portuguese pt, Italian it, Turkish tr, Romanian ro, Hungarian hu, Slovak sk, Japanese ja,
     Korean ko, Chinese zh, Vietnamese vi, Indonesian id, Arabic ar, Hindi hi, Russian ru.
   - Period: default = last 24 full months. "last two years" → default; "three years" →
     `--months 36`; explicit → `--start 2023-01 --end 2025-06`. Use ≥24 months when possible
     (fewer months → seasonality is not controlled).
   - `--ui uk` (default) or `--ui en`: language of chart/PDF labels. Match the user's language.

2. **If the topic is ambiguous or abstract, check it first**
   `scripts/wi resolve "Intermittent fasting" --langs pl,cs`
   Look at `label_en`, the titles per language and `alternatives`. If the wrong
   article was picked, rerun with the correct `Q…` id. For abstract ideas ("learning English")
   pick a concrete proxy article and **tell the user which article you used as a proxy**.
   Prefer the broad general article (`"English language"`): narrow ones
   (`"English as a second or foreign language"`) often get < 100 views/month and are missing
   in many languages, which makes every result "low reliability".

3. **Run the analysis**
   `scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs`
   Output (JSON): `warnings`, `answer_skeleton` (the answer to send, with one slot to fill),
   `verdicts` (one ready sentence per language), `table` (markdown,
   sorted by relative growth; `[proxy]` marks a different concept), `details` per series
   (spikes, seasonal peaks, reasons), `topics[].missing_languages`, `chart` path, `run_dir`, `caveats`.
   After several commands, use the `answer_skeleton` of the **last** `analyze` you ran.
   **Read `warnings` first and follow them before answering.** They say exactly what to run:
   - *no article in language X* → tell the user (a missing article is itself a signal), then
     search in that language: `scripts/wi resolve "<topic in X>" --search-lang X` and rerun with
     `--article X:<Title>` added to the same command. Say which local article you used.
     If the tool then shows a `PROXY` warning, the article is a different concept (rule 3).
   - *low volume* → if the article is a proxy, rerun with a broader one before concluding;
     otherwise the small audience is itself the finding.
   Other options: `--article lang:Title` (repeatable) measures an exact article;
   `--include-redirects` adds views of redirects (helps small editions).

4. **Answer = `answer_skeleton` with its one slot filled.** The skeleton is already the full
   answer: data, one verdict per language, missing languages, the language comparison, limits,
   chart. Copy it **whole**, replace only the `<ЗАПОВНИ: …>` / `<FILL: …>` slot with 1–3 sentences
   built from the lines above, and translate if the user writes in another language.
   Do not delete or shorten any other line. For "which audiences next" questions, use the
   **Порівняння мов / Languages compared** line: share of edition traffic = momentum, volume = size.
   You may add reliability reasons from `details` after the verdicts. Causes of spikes or peaks
   only as hypotheses ("possibly …").

5. **Shareable report (PDF, 1 page)** — when asked for a report/summary to share:
   `scripts/wi report RUN_DIR --title "…" --conclusion "…" [--caveat "…"]`
   `--conclusion`: your filled slot, expanded to 3–6 sentences with numbers copied from
   `verdicts`, ending with a recommendation
   (what to explore next and why). Hard rules apply. Proxy and low-reliability caveats are added
   to the PDF automatically. Use `@file.txt` for long text. Give the user the PDF path.
   The output says what fitted on the page: with more than 10 series the PDF shows the 10 with the largest
   share change (`note`); a conclusion that did not fit is cut (`conclusion_truncated`, follow the `hint`).

6. **Follow-up questions** (other languages, longer period, another topic, different assumptions):
   just rerun `analyze` with changed arguments — downloads are cached, so it is fast.
   Each distinct question (topic × languages × period) gets its own `run_dir`, so earlier
   results stay available for comparison. `scripts/wi runs` lists previous runs;
   `scripts/wi show RUN_DIR` reprints one without network.

## How to read the numbers

| field | meaning |
|---|---|
| `change %` | mean views of last 12 months vs previous 12 (same calendar months, so seasonality cancels), spikes removed. **Headline number.** |
| `rel. change %` | same, for the article's share of all views of that language edition. Use it to compare languages: it removes "the whole Wikipedia got more/less traffic". If `change` and `rel. change` disagree, say so. |
| `trend/yr %`, `p` | robust (Theil–Sen) annualised trend and Mann–Kendall p-value (`<0.001` = very strong). p < 0.05 = statistically clear trend. |
| `months up` | how many of the last 12 months beat the same month a year earlier (12/12 = very consistent). |
| `median/mo` | typical monthly views = audience size signal. < 300: percentages are noise. |
| `reliability` | score 0–10 → high / medium / low. Low volume caps it: `low (8/10, volume cap)` means the trend itself is clean but there are too few views to trust percentages. Reasons are in `details[].reasons`. |
| `direction` | growing / declining / flat / unclear (unclear = growth number not backed by a significant trend). |

Decision rules:
- Say "growing" only if `direction` is `growing`. For `unclear`, say the data does not confirm a trend.
- Never recommend a market on a `low` reliability series alone; say what extra check is needed.
- Comparing audiences: consider both growth (`rel. change %`) and size (`median/mo`,
  `per_million_views_last12`). A small fast-growing edition and a large flat one are different bets — say which is which.
- Language edition ≠ country; views ≠ willingness to pay. Mention when relevant.

Method details and limitations: `references/METHODOLOGY.md` (read only if the user asks how numbers are computed).

## Examples

```bash
# growth comparison, two languages, 2 years
scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs
# single language + trust question
scripts/wi analyze --topic "Astronomy" --langs uk
# language missing (warning) -> find a local article, check it is the same concept, add it
scripts/wi resolve "post przerywany" --search-lang pl
scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --article "pl:<title from resolve>"
# which audiences next: many languages, then report
scripts/wi analyze --topic "English language" --langs top:15 --months 36
scripts/wi report runs/<run_name> --title "Інтерес до вивчення англійської" --conclusion "…"
# two topics in one language
scripts/wi analyze --topic "Astronomy" --topic "Astrology" --langs uk
```

Errors come back as `{"error": …, "hint": …}`. "No article found" → try another wording,
`--search-lang` of the user's language, or `resolve` to find the Q-id.
