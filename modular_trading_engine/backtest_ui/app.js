document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();

    /* =========================================================================
       THEME TOGGLE LOGIC
       ========================================================================= */
    const themeBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    
    if (themeBtn) {
        const savedTheme = localStorage.getItem('tradebazen-theme') || 'dark';
        if (savedTheme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
            themeIcon.setAttribute('data-lucide', 'moon');
            // Ensure icons catch up
            setTimeout(() => lucide.createIcons(), 50);
        }

        themeBtn.addEventListener('click', () => {
            const isLight = document.documentElement.getAttribute('data-theme') === 'light';
            if (isLight) {
                document.documentElement.removeAttribute('data-theme');
                localStorage.setItem('tradebazen-theme', 'dark');
                themeIcon.setAttribute('data-lucide', 'sun');
            } else {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('tradebazen-theme', 'light');
                themeIcon.setAttribute('data-lucide', 'moon');
            }
            lucide.createIcons();
        });
    }

    /* =========================================================================
       ROUTING (SPA LOGIC)
       ========================================================================= */
    const viewLogin = document.getElementById('view-login');
    const viewConfig = document.getElementById('view-config');
    const viewTerminal = document.getElementById('view-terminal');

    function switchView(targetView) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        if (targetView) targetView.classList.add('active');
    }

    document.getElementById('btn-login').addEventListener('click', () => {
        switchView(viewConfig);
    });

    document.getElementById('btn-back').addEventListener('click', () => {
        switchView(viewConfig);
    });

    /* =========================================================================
       SLIDER SYNC LOGIC
       ========================================================================= */
    function syncSlider(sliderId, inputId) {
        const slider = document.getElementById(sliderId);
        const input = document.getElementById(inputId);
        if (!slider || !input) return;

        slider.addEventListener('input', (e) => {
            input.value = e.target.value;
        });

        input.addEventListener('change', (e) => {
            // Validate bounds
            let val = parseFloat(e.target.value);
            const min = parseFloat(slider.min);
            const max = parseFloat(slider.max);
            if (val < min) val = min;
            if (val > max) val = max;
            e.target.value = val;
            slider.value = val;
        });
    }

    // Sync all config sliders
    syncSlider('slider-sl', 'input-sl');
    syncSlider('slider-tp', 'input-tp');
    syncSlider('slider-bias', 'input-bias');
    syncSlider('slider-ttl', 'input-ttl');


    /* =========================================================================
       DATA PIPELINE (DATASETS & PLAYBOOKS)
       ========================================================================= */
    const paramInstrument = document.getElementById('param-instrument');
    const paramStart = document.getElementById('param-start');
    const paramEnd = document.getElementById('param-end');
    const paramPlaybook = document.getElementById('param-playbook');

    async function loadDatasetInfo() {
        try {
            const res = await fetch(`http://localhost:8000/api/v1/dataset-info/${paramInstrument.value}`);
            if (res.ok) {
                const info = await res.json();
                if (info.min_date) {
                    paramStart.min = info.min_date;
                    paramEnd.min = info.min_date;
                }
                if (info.max_date) {
                    paramStart.max = info.max_date;
                    paramEnd.max = info.max_date;
                }
            }
        } catch (e) {
            console.error("Failed to fetch dataset info:", e);
        }
    }
    
    // Initial fetches
    loadDatasetInfo();
    paramInstrument.addEventListener('change', loadDatasetInfo);

    async function loadPlaybooksList() {
        try {
            const res = await fetch(`http://localhost:8000/api/v1/playbooks`);
            if (res.ok) {
                const playbooks = await res.json();
                playbooks.forEach(pb => {
                    const opt = document.createElement('option');
                    opt.value = pb;
                    opt.textContent = pb.replace('.json', '');
                    paramPlaybook.appendChild(opt);
                });
            }
        } catch (e) {
            console.error("Failed to load playbooks:", e);
        }
    }
    loadPlaybooksList();

    // Auto-fill logic when selecting a playbook
    paramPlaybook.addEventListener('change', async (e) => {
        const file = e.target.value;
        if (!file) return; // Custom
        
        try {
            const res = await fetch(`http://localhost:8000/api/v1/playbooks/${file}`);
            if (res.ok) {
                const data = await res.json();
                if (data.pipeline) {
                    data.pipeline.forEach(mod => {
                        const p = mod.params || {};
                        if (mod.module_type === "ConfirmationHoldLevelTrigger" && p.bias_window_size) {
                            document.getElementById('input-bias').value = p.bias_window_size;
                            document.getElementById('slider-bias').value = p.bias_window_size;
                        }
                        if (mod.module_type === "KillzoneFilter") {
                            if (p.exclude_windows && p.exclude_windows.length > 0) {
                                const w = p.exclude_windows[0];
                                document.getElementById('param-kz-start').value = 
                                    String(w.start_hour).padStart(2, '0') + ':' + String(w.start_minute).padStart(2, '0');
                                document.getElementById('param-kz-end').value = 
                                    String(w.end_hour).padStart(2, '0') + ':' + String(w.end_minute).padStart(2, '0');
                            }
                        }
                        if (mod.module_type === "TTLTimeout" && p.max_candles_open !== undefined) {
                            document.getElementById('input-ttl').value = p.max_candles_open;
                            document.getElementById('slider-ttl').value = p.max_candles_open;
                        }
                        if (mod.module_type === "RATLimitOrder") {
                            if (p.tick_size !== undefined) document.getElementById('input-tick').value = p.tick_size;
                            if (p.entry_frontrun_ticks !== undefined) document.getElementById('input-frontrun').value = p.entry_frontrun_ticks;
                            if (p.stop_loss_padding_ticks !== undefined) document.getElementById('input-slpad').value = p.stop_loss_padding_ticks;
                            if (p.absolute_sl_points !== undefined) {
                                document.getElementById('input-sl').value = p.absolute_sl_points;
                                document.getElementById('slider-sl').value = p.absolute_sl_points;
                            }
                            if (p.absolute_tp_points !== undefined) {
                                document.getElementById('input-tp').value = p.absolute_tp_points;
                                document.getElementById('slider-tp').value = p.absolute_tp_points;
                            }
                        }
                    });
                }
            }
        } catch (e) {
            console.error("Failed to load playbook details:", e);
        }
    });

    /* =========================================================================
       EXECUTE SIMULATION
       ========================================================================= */
    const runBtn = document.getElementById('btn-simulate');
    const loadingBar = document.getElementById('loading-bar');
    const statWinrate = document.getElementById('stat-winrate');
    const statPnl = document.getElementById('stat-pnl');
    const statDd = document.getElementById('stat-dd');
    const statCount = document.getElementById('stat-count');
    const tradesBody = document.getElementById('trades-body');

    runBtn.addEventListener('click', async () => {
        // Collect form data
        const payload = {
            instrument: document.getElementById('param-instrument').value,
            start_date: document.getElementById('param-start').value || null,
            end_date: document.getElementById('param-end').value || null,
            timeframe_minutes: parseInt(document.getElementById('param-tf').value),
            
            // Strategy Params
            sl_points: parseFloat(document.getElementById('input-sl').value),
            tp_points: parseFloat(document.getElementById('input-tp').value),
            tick_size: parseFloat(document.getElementById('input-tick').value),
            bias_window: parseInt(document.getElementById('input-bias').value),
            frontrun_ticks: parseInt(document.getElementById('input-frontrun').value),
            sl_pad_ticks: parseInt(document.getElementById('input-slpad').value),
            ttl_candles: parseInt(document.getElementById('input-ttl').value),
            killzone_start: document.getElementById('param-kz-start').value,
            killzone_end: document.getElementById('param-kz-end').value
        };

        // UI State
        runBtn.innerHTML = '<i data-lucide="loader-2" class="lucide-spin"></i> CALCULATING...';
        runBtn.disabled = true;
        loadingBar.classList.remove('disabled');

        try {
            const res = await fetch('http://localhost:8000/api/v1/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                throw new Error("Server returned " + res.status);
            }

            const data = await res.json();
            
            // Switch to Terminal View to see results
            switchView(viewTerminal);

            // Re-init lucide icons for new layout if needed (not strictly needed, but safe)
            lucide.createIcons();

            // Render stats
            statWinrate.innerText = data.win_rate.toFixed(1) + "%";
            statPnl.innerText = (data.net_pnl > 0 ? "+" : "") + "$" + data.net_pnl.toFixed(2);
            statPnl.style.color = data.net_pnl >= 0 ? "var(--text-success)" : "var(--text-danger)";
            statDd.innerText = "$" + data.max_drawdown.toFixed(2);
            statCount.innerText = data.total_trades;

            // Render execution log
            tradesBody.innerHTML = '';
            if (data.execution_log && data.execution_log.length > 0) {
                // Reverse to show newest first
                data.execution_log.reverse().forEach(t => {
                    const tr = document.createElement('tr');
                    
                    const pnlColor = t.pnl_locked >= 0 ? "var(--text-success)" : "var(--text-danger)";
                    const pnlSign = t.pnl_locked > 0 ? "+" : "";
                    
                    // Style row based on PNL
                    tr.style.color = pnlColor;

                    tr.innerHTML = `
                        <td>${t.entry_time.replace('T', ' ')}</td>
                        <td>${t.direction}</td>
                        <td>${t.entry_price.toFixed(2)}</td>
                        <td>${t.mfe.toFixed(2)} / ${t.mae.toFixed(2)}</td>
                        <td style="font-weight: 700;">${pnlSign}$${t.pnl_locked.toFixed(2)}</td>
                    `;
                    tradesBody.appendChild(tr);
                });
            } else {
                tradesBody.innerHTML = `<tr><td colspan="5" class="empty-state">No executions found for strategy criteria.</td></tr>`;
            }

        } catch (e) {
            console.error(e);
            alert("Error running backtest: " + e.message);
        } finally {
            runBtn.innerHTML = '<i data-lucide="play-circle"></i> RUN BACKTEST';
            runBtn.disabled = false;
            loadingBar.classList.add('disabled');
            lucide.createIcons();
        }
    });
});
