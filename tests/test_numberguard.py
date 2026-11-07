from skeptic.numberguard import allowed_numbers, check, extract, strip_violations

BUNDLE = {
    "attacks": {
        "A1": {"numbers": {"median_excess_bps": 59, "sign_p": 0.2726, "wins": 160, "losses": 140,
                           "median_excess_ci95_bps": [-32, 151], "exposure_pct": 29.7, "mean_excess_bps": -87},
               "summary": "Median excess 59 bps (95% CI -32 to 151); sign-test p = 0.2726"},
        "A2": {"numbers": {"p_perm": 0.004, "K": 1000}},
        "A4": {"numbers": {"median_excess_x2_bps": 16}},
    },
    "rules": ["ENTER when return(lookback=12) <= -0.03", "EXIT when held 24 bars"],
}


def test_extract_ignores_citations_and_ids():
    toks = [t["value"] for t in extract("Per [A2] and [D1], A1 had 160 wins at x2 costs.")]
    assert toks == [160]


def test_exact_and_rounded_numbers_pass():
    text = ("The rule won 160 of 300 paths [A1]; median excess 59 bps with a 95% CI of -32 to 151 bps, "
            "sign-test p = 0.27 [A1]. Random entries gave p_perm = 0.004 over 1,000 shuffles [A2]. "
            "Doubling costs left 16 bps [A4]. It was in the market 30% of the time; the median is 0.59%.")
    # 300 is not in the bundle -> flagged; everything else is a formatting of a bundle value
    assert check(text, BUNDLE) == ["300"]


def test_rule_numbers_and_fraction_to_percent():
    assert check("It buys after a 3% drop over 12 bars and holds for 24 bars.", BUNDLE) == []


def test_invented_number_is_caught():
    assert check("This strategy would make 12.5% a year.", BUNDLE) == ["12.5%"]
    assert check("The p-value is 0.03.", BUNDLE) == ["0.03"]


def test_sign_flip_is_caught_unless_words_say_down():
    assert check("The mean excess was 87 bps.", BUNDLE) == ["87 bps"]
    assert check("The mean excess was -87 bps.", BUNDLE) == []
    assert check("The mean fell by 87 bps once outliers were dropped.", BUNDLE) == []


def test_strip_removes_only_offending_sentence():
    text = "Median excess was 59 bps [A1]. It returns 40% a year. Costs x2 left 16 bps [A4]."
    res = strip_violations(text, BUNDLE)
    assert res.removed_sentences == ["It returns 40% a year."]
    assert "40%" not in res.text and "59 bps" in res.text
    assert res.violations == ["40%"]


def test_allowed_numbers_walks_strings_and_lists():
    vals = allowed_numbers(BUNDLE)
    assert {59.0, -32.0, 151.0, 0.2726, 12.0, -0.03, 24.0} <= vals
