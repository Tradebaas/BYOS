import re

with open("modular_trading_engine/scripts/test_premium_discount_strategy.py", "r") as f:
    code = f.read()

# Make sure we clean origins length
code = code.replace(
    "# 5. ALERT state logic",
    "origins = [o for o in origins if not o.invalidated]\n    # 5. ALERT state logic"
)

with open("modular_trading_engine/scripts/test_premium_discount_strategy.py", "w") as f:
    f.write(code)
