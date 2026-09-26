# Haiku 4.5 run, 2026-09-26 (iteration 11, after the "unconfirmed share change" texts)

Same setup and cases as iterations 9 and 10 (`haiku-4.5_2026-09-26/`, `…26b/`): Claude Haiku 4.5 as a Claude Code
subagent, a fresh local clone per run, two runs per case, the follow-up case as two turns. The change since
iteration 10 is commit `5208024`: a share change beyond ±10 % with `direction (share) = unclear` is named "not a
confirmed growth" in the verdict and marked "(unconfirmed)" in the comparison line. Local paths are replaced by
`<skill>`. Follow-up run b answered in English to a Ukrainian request, used `--ui en`, ran in the main checkout and
drew an extra interactive chart of its own; its second answer was recovered from the subagent log because the
hand-back did not arrive. Scoring is in README, iteration 11.
