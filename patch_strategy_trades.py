import re

with open("modular_trading_engine/scripts/test_premium_discount_strategy.py", "r") as f:
    code = f.read()

# Make sure we declare completed_trades
code = code.replace(
    "stats = {",
    "completed_trades = []\nstats = {"
)

# Record when a limit is placed
code = code.replace(
    "pending_limit = {",
    "pending_limit = {\n                        'o': o,"
)

# Record when trade is entered
code = code.replace(
    "active_trade = pending_limit",
    "active_trade = pending_limit\n            completed_trades.append({'entered_at': cj, 'trade': active_trade})"
)

# Print last 3 at the end
print_code = """
print("\n--- LAATSTE 3 EXECUTIONS ---")
for t in completed_trades[-3:]:
    o = t['trade']['o']
    exec_c = t['entered_at']
    print(f"[{o.type} TRADE]")
    print(f" Hold Level Tijd:    {o.hold_open_time if hasattr(o, 'hold_open_time') else 'UNKNOWN'}") # We need to add timestamps to OriginGroup!
"""

# Let's completely rewrite the script to be clean instead of regex patching.
