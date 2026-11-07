# E4: translation accuracy (SELF-ASSESSMENT)

Model `gemini-4-argon` (live). Gold rule cards drafted before the run (`eval/translation_gold.json`);
a teammate should review the gold set. Thresholds and parameters must match exactly (no tolerance).

| Measure | Result |
|---|---|
| Fully specified hunches that got a rule card (no questions) | 26/30 = 87% (95% CI 70–95%) |
| Field-level exact match (strict ops) | 58/61 = 95% (95% CI 87–98%) |
| Field-level exact match (`<` ≡ `<=`, `>` ≡ `>=`) | 58/61 = 95% (95% CI 87–98%) |
| Whole card exactly right (strict) | 24/26 = 92% (95% CI 76–98%) |
| Whole card exactly right (op-lenient) | 24/26 = 92% (95% CI 76–98%) |
| Ambiguous hunches where the model asked instead of guessing | 10/10 = 100% (95% CI 72–100%) |

## Misses (strict)

- G12 Buy after a 15% drawdown from the 168-bar high; take profit at +6% or stop out at -4%.: 2/3 fields · got `{"entry": {"all": [{"feature": "drawdown_from_high", "op": "<=", "value": -0.15, "lookback": 168, "window": null, "fast": null, "slow": null}]}, "exit": {"hold_bars": null, "take_profit": 0.06, "stop_loss": null, "any": []}, "cooldown_bars": 0}`
- G21 Buy when the 24-bar return is below -8%; exit at +4% or after 72 bars; wait 24 bars before re-entering.: **error**
- G23 Buy a 5% drop over 24 bars only if the 50-bar average is above the 200-bar average; hold 48 bars.: **error**
- G24 Buy when 24-bar volatility is under 0.6% and price is above its 50-bar average; exit after 24 bars or at a 2% stop.: **error**
- G25 Buy when the 12-bar return is above +3%; sell when the 12-bar return turns negative.: **error**
- G27 Buy after a 2% one-bar drop; sell after 3 bars.: 2/4 fields · got `{"entry": {"all": [{"feature": "return", "op": "<=", "value": -0.02, "lookback": 1, "window": null, "fast": null, "slow": null}]}, "exit": {"hold_bars": 3, "take_profit": 0.05, "stop_loss": 0.05, "any": []}, "cooldown_bars": 0}`
