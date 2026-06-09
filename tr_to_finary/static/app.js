/* ── TR to Finary – Web UI ── */

const API = "";

let previewData = null;

// ── Helpers ──
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function show(el) { if (el) el.style.display = ""; }
function hide(el) { if (el) el.style.display = "none"; }

function setStep(n) {
    $$(".step").forEach((el, i) => {
        el.classList.remove("active", "done");
        if (i + 1 === n) el.classList.add("active");
        if (i + 1 < n) el.classList.add("done");
    });
}

function num(v, dec = 2) {
    if (v == null || v === "") return "-";
    return Number(v).toLocaleString("fr-FR", {
        minimumFractionDigits: dec,
        maximumFractionDigits: dec,
    });
}

function badge(type) {
    const cls = { BUY: "badge-buy", SELL: "badge-sell", DIVIDEND: "badge-dividend" }[type] || "badge-ok";
    return `<span class="badge ${cls}">${type}</span>`;
}

function addLog(text, cls = "") {
    const log = $("#sync-log");
    if (!log) return;
    const line = document.createElement("div");
    line.className = cls;
    line.textContent = text;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
}

function clearLog() {
    const log = $("#sync-log");
    if (log) log.innerHTML = "";
}

// ── Upload ──
function initUpload() {
    const zone = $(".upload-zone");
    const input = $("#csv-file");
    if (!zone || !input) return;

    zone.addEventListener("click", () => input.click());
    zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", e => {
        e.preventDefault();
        zone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            onFileSelected();
        }
    });
    input.addEventListener("change", onFileSelected);
}

function onFileSelected() {
    const input = $("#csv-file");
    const zone = $(".upload-zone");
    if (!input.files.length) return;

    const fname = input.files[0].name;
    zone.innerHTML = `
        <div class="upload-icon">&#128196;</div>
        <p><span class="filename">${fname}</span></p>
        <p style="margin-top:.4rem;color:var(--text-muted);font-size:.8rem">Ready to parse</p>
    `;
    const btn = $("#btn-preview-csv");
    if (btn) btn.disabled = false;
}

// ── API ──
async function uploadCSV() {
    const input = $("#csv-file");
    if (!input.files.length) return;

    const btn = $("#btn-preview-csv");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Parsing...';

    const form = new FormData();
    form.append("file", input.files[0]);

    try {
        const resp = await fetch(`${API}/api/upload`, { method: "POST", body: form });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Upload failed");
        showPreview(data);
    } catch (e) {
        showError(e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">&#128269;</span> Preview';
    }
}

async function fetchFromTR() {
    const btn = $("#btn-fetch");
    const lastDays = parseInt($("#fetch-last-days")?.value || "0", 10);
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Fetching...';

    try {
        const resp = await fetch(`${API}/api/fetch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ last_days: lastDays }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Fetch failed");
        showPreview(data);
    } catch (e) {
        showError(e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">&#128268;</span> Fetch from TR';
    }
}

function showError(msg) {
    const el = $("#error-alert");
    if (el) {
        el.textContent = msg;
        show(el.parentElement || el);
    } else {
        alert("Error: " + msg);
    }
}

function showPreview(data) {
    previewData = data;
    setStep(2);

    // Stats
    const stats = $("#preview-stats");
    if (stats) {
        stats.innerHTML = `
            <div class="stat"><div class="stat-label">Transactions</div><div class="stat-value">${data.total_transactions}</div></div>
            <div class="stat"><div class="stat-label">Positions</div><div class="stat-value primary">${data.positions.length}</div></div>
            <div class="stat"><div class="stat-label">New TXs</div><div class="stat-value green">${data.new_tx_count}</div></div>
            <div class="stat"><div class="stat-label">To Sync</div><div class="stat-value">${data.changed_count}</div></div>
        `;
    }

    // Positions table
    const tbody = $("#positions-body");
    if (tbody) {
        tbody.innerHTML = data.positions.map(p => {
            const nc = p.new_tx_count || 0;
            const statusBadge = nc > 0
                ? `<span class="badge badge-new">+${nc} new</span>`
                : `<span class="badge badge-ok">synced</span>`;
            return `<tr>
                <td style="font-weight:500">${p.name}</td>
                <td style="color:var(--text-muted);font-size:.8rem">${p.isin}</td>
                <td class="num">${num(p.quantity, 4)}</td>
                <td class="num">${num(p.average_buy_price)} &euro;</td>
                <td class="num">${num(p.total_invested)} &euro;</td>
                <td class="num">${p.total_dividends ? num(p.total_dividends) + ' &euro;' : '-'}</td>
                <td>${statusBadge}</td>
            </tr>`;
        }).join("");

        const totalInv = data.positions.reduce((s, p) => s + p.total_invested, 0);
        const totalDiv = data.positions.reduce((s, p) => s + p.total_dividends, 0);
        tbody.innerHTML += `<tr class="total">
            <td>Total</td><td></td><td></td><td></td>
            <td class="num">${num(totalInv)} &euro;</td>
            <td class="num">${totalDiv ? num(totalDiv) + ' &euro;' : '-'}</td>
            <td><span class="badge badge-ok">${data.positions.length} pos</span></td>
        </tr>`;
    }

    // Transactions table
    if (data.transactions) {
        const txBody = $("#transactions-body");
        if (txBody) {
            txBody.innerHTML = data.transactions.map(tx => `<tr>
                <td>${tx.date}</td>
                <td>${badge(tx.type)}</td>
                <td style="font-weight:500">${tx.name}</td>
                <td style="color:var(--text-muted);font-size:.8rem">${tx.isin || '-'}</td>
                <td class="num">${tx.shares ? num(tx.shares, 6) : '-'}</td>
                <td class="num">${tx.price ? num(tx.price) + ' &euro;' : '-'}</td>
                <td class="num">${num(tx.amount)} &euro;</td>
                <td class="num">${tx.fee ? num(tx.fee) + ' &euro;' : '-'}</td>
            </tr>`).join("");
        }
    }

    hide($("#section-upload"));
    show($("#section-preview"));

    const syncBtn = $("#btn-sync");
    if (syncBtn) syncBtn.disabled = data.changed_count === 0;
}

// ── Tabs (transactions view) ──
function switchTab(tabName) {
    $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tabName));
    $$(".tab-content").forEach(tc => {
        tc.style.display = tc.id === `tab-${tabName}` ? "" : "none";
    });
}

// ── Sync ──
async function executeSync() {
    if (!previewData) return;

    setStep(3);
    hide($("#section-preview"));
    show($("#section-sync"));
    clearLog();
    addLog("Connecting to Finary...", "line-info");

    const btn = $("#btn-sync-exec");
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Syncing...'; }

    const account = $("#sync-account")?.value || "Trade Republic";

    try {
        const resp = await fetch(`${API}/api/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_name: account }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || "Sync failed");

        for (const log of (data.logs || [])) {
            const cls = log.startsWith("[OK]") ? "line-ok"
                : log.startsWith("[WARN]") ? "line-warn"
                : log.startsWith("[ERR]") ? "line-err" : "line-info";
            addLog(log, cls);
        }

        addLog("", "");
        addLog(`Done: ${data.created} created, ${data.updated} updated, ${data.skipped} skipped, ${data.errors} errors`,
            data.errors ? "line-err" : "line-ok");

        const summary = $("#sync-summary");
        if (summary) {
            summary.innerHTML = `
                <div class="stats">
                    <div class="stat"><div class="stat-label">Created</div><div class="stat-value green">${data.created}</div></div>
                    <div class="stat"><div class="stat-label">Updated</div><div class="stat-value primary">${data.updated}</div></div>
                    <div class="stat"><div class="stat-label">Skipped</div><div class="stat-value">${data.skipped}</div></div>
                    <div class="stat"><div class="stat-label">Errors</div><div class="stat-value" style="color:${data.errors ? 'var(--red)' : 'var(--text-muted)'}">${data.errors}</div></div>
                </div>`;
            show(summary);
        }
    } catch (e) {
        addLog("[ERR] " + e.message, "line-err");
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<span class="btn-icon">&#9889;</span> Sync to Finary'; }
    }
}

function resetFlow() {
    previewData = null;
    setStep(1);
    show($("#section-upload"));
    hide($("#section-preview"));
    hide($("#section-sync"));

    const zone = $(".upload-zone");
    if (zone) {
        zone.innerHTML = `
            <div class="upload-icon">&#128228;</div>
            <p>Drop your Trade Republic CSV here</p>
            <p style="margin-top:.4rem;font-size:.8rem;color:var(--text-muted)">or click to browse</p>
        `;
    }
    const btn = $("#btn-preview-csv");
    if (btn) btn.disabled = true;
}

// ── Settings ──
async function loadSettings() {
    try {
        const resp = await fetch(`${API}/api/settings`);
        const data = await resp.json();
        if ($("#set-account")) $("#set-account").value = data.account_name || "Trade Republic";
        if ($("#set-email")) $("#set-email").value = data.email || "";
        if (data.has_credentials && $("#cred-status")) {
            $("#cred-status").innerHTML = '<span style="color:var(--green)">&#10003;</span> credentials.json found';
        }
    } catch {}
}

async function saveSettings() {
    const account = $("#set-account")?.value || "Trade Republic";
    const btn = $("#btn-save-settings");
    btn.disabled = true;

    try {
        const resp = await fetch(`${API}/api/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_name: account }),
        });
        if (!resp.ok) throw new Error("Save failed");
        btn.textContent = "Saved!";
        btn.classList.add("btn-success");
        setTimeout(() => { btn.textContent = "Save"; btn.classList.remove("btn-success"); btn.disabled = false; }, 1500);
    } catch (e) {
        alert(e.message);
        btn.disabled = false;
    }
}

async function resetSyncState() {
    if (!confirm("Reset sync state? All transactions will be treated as new on next sync.")) return;
    try {
        const resp = await fetch(`${API}/api/reset`, { method: "POST" });
        if (!resp.ok) throw new Error("Reset failed");
        location.reload();
    } catch (e) { alert(e.message); }
}

// ── Dashboard ──
async function loadDashboard() {
    try {
        const resp = await fetch(`${API}/api/status`);
        const data = await resp.json();
        if ($("#dash-synced")) $("#dash-synced").textContent = data.synced_count;
        if ($("#dash-last-sync")) {
            if (data.last_sync) {
                const d = new Date(data.last_sync);
                $("#dash-last-sync").textContent = d.toLocaleDateString("fr-FR") + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
            } else {
                $("#dash-last-sync").textContent = "Never";
            }
        }
        if ($("#dash-account")) $("#dash-account").textContent = data.account || "-";

        // Update status dot
        const dot = $("#status-dot");
        if (dot) {
            dot.className = "dot " + (data.synced_count > 0 ? "dot-ok" : "dot-warn");
        }
        const statusText = $("#status-text");
        if (statusText) {
            statusText.textContent = data.synced_count > 0 ? "Connected" : "Not synced yet";
        }
    } catch {}
}

// ── Init ──
document.addEventListener("DOMContentLoaded", () => {
    initUpload();
    const page = document.body.dataset.page;
    if (page === "dashboard") loadDashboard();
    if (page === "settings") loadSettings();
});
