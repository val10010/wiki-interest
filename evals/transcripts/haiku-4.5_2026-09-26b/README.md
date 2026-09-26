# Haiku 4.5 run, 2026-09-26 (iteration 10, after the "no language grows by share" line)

Same setup and cases as `haiku-4.5_2026-09-26/` (iteration 9): Claude Haiku 4.5 as a Claude Code subagent, a fresh
local clone per run, two runs per case, the follow-up case as two turns. The only change between the two runs of the
day is commit `9fe5111`: when no share change reaches +10 %, the comparison line of `answer_skeleton` says so in words.
Local paths are replaced by `<skill>`; two runs (English report b, follow-up b) executed their commands in the main
checkout instead of their clone, which changes nothing in the data. Scoring is in README, iteration 10.
