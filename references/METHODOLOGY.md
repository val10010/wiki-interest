# Methodology

## Data

- **Source:** Wikimedia Pageviews REST API, `agent=user` (automated/spider traffic excluded by Wikimedia), `all-access` (desktop + mobile web + app), monthly granularity. Data exists from July 2015 onwards. The current, incomplete month is never used.
- **Topic → articles:** full-text search on the chosen Wikipedia returns candidates. Disambiguation pages and items without a Wikidata id are skipped. The Wikidata item's sitelinks give the title in every language, so all languages refer to *the same concept*, not to a translated keyword.
- **Normalisation:** for each language edition the total monthly views of the whole edition (`aggregate` endpoint) are fetched. `share = article views / edition views`. This removes platform-level effects (e.g. traffic lost to AI answers or search snippets, or a whole edition growing).
- **Cache:** every HTTP response is stored in `.cache/`. Closed months are cached forever; ranges that end within ~70 days are refreshed after 24 h.
- **Runs:** each distinct question (topics × languages × period × redirects) is saved to its own `runs/<name>/`. Follow-ups never overwrite earlier results. Re-running the same question replaces its `analysis.json` and deletes the now-stale `report.pdf`.

## Per-series statistics (`scripts/wiki_interest/stats.py`)

1. **Spike detection.** log(views) is compared to a centred 5-month rolling median. A month is a spike if its robust z-score (residual / 1.4826·MAD) > 3.5 **and** it is ≥ 1.8× the local median. Spikes are replaced by the rolling median (the "clean" series). They are reported, not hidden.
   **Seasonal peaks are not spikes:** if the same calendar month one year earlier or later is also ≥ 1.5× its own baseline, the peak is recurring (school start, New-year diets). It is reported as `seasonal_peaks` and kept in the data, because the year-over-year comparison already cancels it. Needs ≥ 13 months to see the repeat. A one-off event that happens to hit the same month twice would be misread as seasonal.
2. **Growth (headline).** Mean of the last 12 months vs the previous 12 months on the clean series. Same calendar months are compared, so seasonality (January diets, September school start) cancels. With < 24 months the halves are compared and a caveat is added.
3. **Relative growth.** The same comparison on `share`.
4. **Trend.** Theil–Sen slope of log(views), annualised. Robust to outliers.
5. **Significance.** Mann–Kendall test on log(clean views). Note: monthly series are autocorrelated, which makes p-values somewhat optimistic. That is why p is only one of five reliability components.
6. **Consistency.** Number of the last 12 months that beat the same month a year earlier.

## Reliability score (0–10)

| component | points |
|---|---|
| volume: median ≥ 3000 views/mo → 2, ≥ 300 → 1 | 0–2 |
| trend significance: p < 0.05 → 2, p < 0.2 → 1 | 0–2 |
| consistency: ≥ 9 or ≤ 3 of 12 months up → 2, 7–8 / 4–5 → 1 | 0–2 |
| spike robustness: spikes < 25 % of views and raw vs clean growth have the same sign | 0–2 |
| normalisation agrees with raw growth direction | 0–1 |
| ≥ 24 months of data | 0–1 |

≥ 8 → high, 5–7 → medium, else low. **Caps:** median < 300 views/mo → always low. Median < 3000 → at most medium. A cap is stored in `reliability_cap`, shown in the table as `(…, volume cap)` and explained in `reasons`, so "low (8/10)" is never left unexplained. Every lost point adds a human-readable reason.

**Direction:** `growing` if clean growth ≥ +10 %, trend > 0 and p < 0.2. `declining` is the mirror case. `flat` if |growth| < 10 %. Otherwise `unclear`.

## Measurement warnings

`analyze` returns `warnings` when the measurement itself is questionable, each with the exact next command:
- a requested language has no article linked to the Wikidata item → search locally and add it with `--article lang:Title` (merged into the same topic);
- at least half of the series have median < 300 views/mo → percentages are noise; a proxy article is too narrow (use a broader one), otherwise the small audience is the finding;
- an article added with `--article` belongs to a different Wikidata item than the topic → `PROXY` warning, `[proxy]` in the table, and a caveat added to the PDF automatically. Example: for "Intermittent fasting" Polish has only `Post` (= fasting). Its seasonal peaks fall in March (Lent), which confirms it measures religious fasting, not the diet.

## Verdicts

For each series the tool writes one sentence (`verdicts`, in the report language): direction, change, share change, trend, volume, reliability with cap, seasonal peaks, excluded spikes, and the proxy flag. The direction wording comes straight from `direction`. If views moved ≥ 10 % but the share of the edition moved < 10 %, the verdict says the change is edition-wide traffic. The agent quotes verdicts instead of phrasing conclusions, because in a Haiku 4.5 run the model called a `flat` series "growing" and merged numbers from different columns.


## Known limitations

- Views measure curiosity or information need, not purchase intent. Students doing homework, news readers and professionals all look the same.
- Language ≠ country. Many readers use English Wikipedia. Ukrainian readers were split between uk and ru editions, with a strong shift to uk after 2022, so uk growth partly reflects language switching. Compare with the edition total (`rel. change`) and consider checking `ru` as well.
- One article ≠ one topic. Use `A+B` to sum related articles and `--include-redirects` to add redirect views (up to 30 redirects per article).
- Article renames or creation inside the period produce zeros at the start. This is flagged as "no views before …".
- `agent=user` still contains some undetected bots. Spike filtering removes the most obvious cases. Sustained bot traffic is not detected.
- Mann–Kendall p-values are approximate (autocorrelation, n = 24).
