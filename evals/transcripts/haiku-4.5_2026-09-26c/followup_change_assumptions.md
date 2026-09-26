# followup_change_assumptions — Haiku 4.5, 2026-09-26 (iteration 11, after the "unconfirmed share change" texts), two runs

## Run a
**User (turn 1):** Порівняй інтерес до інтервального голодування в польській та чеській Wikipedia.

**Assistant:**

Порівняння інтересу до інтервального голодування в польській та чеській Wikipedia:

**Результати:**
- **Чеська Wikipedia (Přerušovaný půst)**: інтерес знижується. Зміна -52.7%, частка в трафіку -45.6%, тренд -53.1%/рік. Медіана 231 переглядів/місяць; надійність низька через малий обсяг.
- **Польська Wikipedia**: немає статті на цю тему — це сам по собі сигнал про недостатній розвиток теми в польській мові.

**Висновок**: Порівняння показує різке падіння інтересу в Чехії, але результат ненадійний. Польща не має окремої статті, тому пряме порівняння неможливе. Для надійніших висновків варто розглянути ширші статті про голодування або дієти в обох мовах.

**Виконані команди:**
1. scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs
2. scripts/wi resolve "post przerywany" --search-lang pl
3. scripts/wi resolve "Intermittent fasting" --search-lang pl


**User (turn 2):** Додай ще словацьку і подивись за три роки замість двох.

**Assistant:**

Порівняння інтересу до інтервального голодування: Польща, Чехія, Словаччина (3 роки, вересень 2023 – серпень 2026)

## Результати

**Чеська Wikipedia** («Přerušovaný půst»):
- Тренд: інтерес знижується
- Зміна: -52.7%, тренд -47.3%/рік (p < 0.001)
- Частка трафіку: -45.6%
- Аудиторія: 317 переглядів/місяць
- Надійність: середня (9/10, обмежено малим обсягом)

**Польська Wikipedia**: немає статті на цю тему (сигнал недорозвиненості теми)

**Словацька Wikipedia**: немає статті на цю тему (сигнал недорозвиненості теми)

## Висновок

За три роки чеська Wikipedia показує послідовне падіння інтересу (-47.3%/рік з середньою надійністю). Польща і Словаччина взагалі не мають статей на цю тему. Для надійнішого порівняння варто перевірити ширші пов'язані теми (дієти, голодування).

## Виконані команди

1. scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs
2. scripts/wi resolve "post przerywany" --search-lang pl
3. scripts/wi resolve "Intermittent fasting" --search-lang pl
4. scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs,sk --months 36

## Run b
**User (turn 1):** Порівняй інтерес до інтервального голодування в польській та чеській Wikipedia.

**Assistant:**

Comparison of interest in intermittent fasting / fasting between Polish and Czech Wikipedia:

**Key Finding:** Polish Wikipedia has much stronger engagement with 1,209 views/month compared to Czech's 537 views/month over the 24-month period (Sept 2024 - Aug 2026).

**Polish (pl) - "Post" article:**
- Views: stable, barely changed (-2.4%)
- Share of edition traffic: no confirmed trend (+10.6% unconfirmed)
- Trend: -10.0%/year (not statistically significant, p=0.551)
- Reliability: medium
- Audience size: substantially larger

**Czech (cs) - "Půst" article:**
- Views: -39.6% (unconfirmed decline)
- Share of edition traffic: -29.2% (unconfirmed decline)
- Trend: -31.6%/year (weakly significant, p=0.107)
- Reliability: medium (limited by low volume)
- Audience size: smaller
- Seasonal peaks in April both years suggest periodic interest

**Conclusion:** Neither language shows confirmed growth trends, but Polish offers a significantly larger and more stable audience base for fasting-related content. If expanding to these markets, Polish Wikipedia's 1209 monthly views (vs Czech's 537) indicates better audience potential, though you should validate actual willingness to pay through direct market testing. The data reflects Wikipedia curiosity, not market demand.

Note: "Intermittent fasting" article had no Polish Wikipedia entry and very low Czech traffic (231 views/month), so analysis used the broader "Fasting" concept for more reliable numbers.

Commands executed:
- scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --ui en
- scripts/wi analyze --topic "Fasting" --langs pl,cs --ui en


**User (turn 2):** Додай ще словацьку і подивись за три роки замість двох.

**Assistant:**

Perfect! Here's the **3-year comparison** of fasting interest across Polish, Czech, and Slovak Wikipedia:

## Summary

**All three Central European markets show declining interest in fasting content over the past 3 years (Sept 2023 – Aug 2026):**

### Rankings by Audience Size & Stability:

**🥇 Polish (1,467 views/month) — Best prospect**
- Views declined -17.8% (most modest)
- Share of edition traffic stayed flat (-5.9%) — this is significant
- All trends statistically significant
- Seasonal peaks in March every year

**🥈 Czech (537 views/month) — Caution**
- Views declined -50.0% 
- Share dropped -40.6% (unconfirmed trend)
- No months showed growth in past year
- Multiple seasonal peaks (March + April)

**🥉 Slovak (441 views/month) — Highest risk**
- Views declined -51.2% (steepest)
- Share dropped -36.0% (unconfirmed decline)
- Only 2 months out of 12 grew year-over-year
- Smallest audience

### Key Insight:
**Polish is the only market with stable *relative* interest** — while absolute views decline (Wikipedia traffic overall is declining), Polish's share of Polish-Wikipedia traffic remains flat. Czech and Slovak show worse decline in both absolute and relative terms.

### Bottom Line for B2C:
- **Start with Polish** if you must pick one (2.7–3.3× larger audience)
- **Skip Czech/Slovak** unless you have specific reasons — both show downward momentum
- **Test seasonal peaks (March–April)** when curiosity spikes in all three markets
- **Don't rely on Wikipedia alone** — all three show declining search interest, possibly because people now discover health topics on TikTok/YouTube instead

Interactive visualization: [Open 3-year comparison chart](<artifact link>)

**Commands executed:**
- `scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --ui en`
- `scripts/wi analyze --topic "Fasting" --langs pl,cs --ui en`
- `scripts/wi analyze --topic "Fasting" --langs pl,cs,sk --months 36 --ui en`
