import re

with open("modular_trading_engine/scripts/test_premium_discount_strategy.py", "r") as f:
    code = f.read()

# Add alert_ts to tracking
code = code.replace("alert_start_idx = 0", "alert_start_idx = 0\nalert_ts = None\nalert_eq = 0.0")

code = code.replace(
    "stats['activations'] += 1",
    "stats['activations'] += 1\n                            alert_ts = cj.timestamp\n                            alert_eq = eq"
)

code = code.replace(
    "'tp': tp,",
    "'tp': tp,\n                        'alert_ts': alert_ts,\n                        'alert_eq': alert_eq,"
)

code = code.replace(
    "print(f\"  > Take Profit: {t['trade']['tp']:.2f}\")",
    "print(f\"  > Take Profit: {t['trade']['tp']:.2f}\")\n    print(f\"  > Alert TS (P/D Check): {t['trade']['alert_ts']} (Eq: {t['trade']['alert_eq']:.2f})\")"
)

with open("modular_trading_engine/scripts/test_premium_discount_strategy.py", "w") as f:
    f.write(code)
