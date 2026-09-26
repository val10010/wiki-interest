"""SKILL.md must not contradict what the tool prints (README, iteration 8)."""
import re
from pathlib import Path

from wiki_interest import interpret

SKILL_MD = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")


def test_decision_rule_does_not_contradict_direction_share(series_with):
    # The rule 'Say "growing" only if `direction` is `growing`' forbade what the verdict itself says when views
    # are flat but the share grows: "relative interest (share of edition traffic) is growing". The rule must
    # send the agent to the verdict and, for relative interest, to `direction (share)`.
    v = interpret.verdict(series_with(direction="flat", growth_pct=-3.0, growth_share_pct=18.0,
                                      direction_share="growing"), "en")
    assert "relative interest (share of edition traffic) is growing" in v
    rules = SKILL_MD[SKILL_MD.index("Decision rules:"):SKILL_MD.index("Method details")]
    assert not re.search(r'Say "growing" only if `direction`', rules)
    assert "`direction (share)`" in rules and "verdict" in rules
    assert re.search(r"name: wiki-interest", SKILL_MD)
