import json

def analyze_topstep(profile, contracts=2):
    # Base multiplier in original run was 40.0 (which is 2 NQ contracts at $20/point)
    # If we want 1 contract, we multiply PnLs by 0.5
    scale = contracts / 2.0
    
    daily_stats = profile.get("daily_stats", [])
    
    high_water_mark = 150000.0
    current_balance = 150000.0
    max_eod_drawdown = 0.0
    max_daily_loss = 0.0
    blown_account = False
    blow_reason = ""
    
    mll_trailing_distance = 4500.0
    daily_loss_limit = 4500.0 # Some sources say 3000, some 4500. Let's use 4500 as the absolute max, but check 3000.
    
    for day in daily_stats:
        pnl = day['pnl'] * scale
        current_balance += pnl
        
        # Check Daily Loss
        if pnl < 0 and abs(pnl) >= daily_loss_limit:
            blown_account = True
            blow_reason = f"Hit Daily Loss Limit ({pnl}) on {day['date']}"
            break
        elif pnl < 0 and abs(pnl) < 0:
            pass
            
        if pnl < 0 and abs(pnl) > max_daily_loss:
            max_daily_loss = abs(pnl)
            
        # Topstep MLL trails highest EOD balance, but never goes above starting balance
        mll_level = high_water_mark - mll_trailing_distance
        if mll_level > 150000.0:
            mll_level = 150000.0
            
        if current_balance <= mll_level:
            blown_account = True
            blow_reason = f"Hit Trailing MLL. Balance {current_balance} <= {mll_level} on {day['date']}"
            break
            
        # Update high water mark at end of day
        if current_balance > high_water_mark:
            high_water_mark = current_balance
            
        # Calc drawdown from HWM
        dd = high_water_mark - current_balance
        if dd > max_eod_drawdown:
            max_eod_drawdown = dd

    return {
        "contracts": contracts,
        "blown": blown_account,
        "blow_reason": blow_reason,
        "max_eod_drawdown": max_eod_drawdown,
        "max_daily_loss": max_daily_loss,
        "final_balance": current_balance
    }

with open('.tmp_optimize/grid_results_extensive.json', 'r') as f:
    results = json.load(f)

for i, profile in enumerate(results[:5]):
    print(f"--- Profile #{i+1} ---")
    print("Params:", profile['params'])
    
    res_2 = analyze_topstep(profile, contracts=2)
    print(f"[2 NQ Contracts] Passed: {not res_2['blown']}")
    if res_2['blown']:
        print(f"  Reason: {res_2['blow_reason']}")
    else:
        print(f"  Max EOD Drawdown: ${res_2['max_eod_drawdown']}")
        print(f"  Max Daily Loss: ${res_2['max_daily_loss']}")
        
    res_1 = analyze_topstep(profile, contracts=1)
    print(f"[1 NQ Contract ] Passed: {not res_1['blown']}")
    if res_1['blown']:
        print(f"  Reason: {res_1['blow_reason']}")
    else:
        print(f"  Max EOD Drawdown: ${res_1['max_eod_drawdown']}")
        print(f"  Max Daily Loss: ${res_1['max_daily_loss']}")
    print()
