// static/js/scan.js
import { apiPost } from "./api.js";
import { getCookie, setCookie } from "./cookies.js";

const COOKIE_SCANNER_MODE = "scanner_mode";
const COOKIE_SCANNER_DELAY = "scanner_delay";

const els = {
    code: document.getElementById("code"),
    btnLookup: document.getElementById("btnLookup"),
    btnSave: document.getElementById("btnSave"),
    btnClear: document.getElementById("btnClear"),

    status: document.getElementById("status"),
    preview: document.getElementById("preview"),
    cover: document.getElementById("cover"),
    title: document.getElementById("title"),
    meta: document.getElementById("meta"),
    provider: document.getElementById("provider"),
    raw: document.getElementById("raw"),

    scannerMode: document.getElementById("scannerMode"),
    scannerDelay: document.getElementById("scannerDelay"),
    scannerDelayInput: document.getElementById("scannerDelayInput"),

    btnRefreshAll: document.getElementById("btnRefreshAll"),
    chkDryRun: document.getElementById("refreshDryRun"),
    refreshReport: document.getElementById("refreshReport"),
    refreshList: document.getElementById("refreshList"),
};


// --- State ---

let lastLookup = null; // { kind, value, book, error }
let lookupTimer = null;


// --- Helpers ---

function clearRefreshReport() {
    if (!els.refreshReport || !els.refreshList) return;
    els.refreshReport.style.display = "none";
    els.refreshList.innerHTML = "";
}

function renderRefreshReport(result) {
    if (!els.refreshReport || !els.refreshList) return;

    const items = result?.updated_items || [];
    if (!items.length) {
        els.refreshReport.style.display = "none";
        return;
    }

    els.refreshReport.style.display = "block";

    els.refreshList.innerHTML = items.map(it => {
        const title = (it.title || "(no title)") + (it.subtitle ? ` — ${it.subtitle}` : "");
        const srcs = (it.sources || []).join(" + ") || "unknown";
        const isbn = it.isbn || "";
        return `
          <label style="display:flex; gap:.5rem; align-items:flex-start; padding:.4rem 0;">
            <input type="checkbox" checked disabled>
            <div>
              <div><strong>${escapeHtml(title)}</strong></div>
              <div style="opacity:.75; font-size:.9em;">
                ISBN: <code>${escapeHtml(isbn)}</code> · Source: ${escapeHtml(srcs)}
              </div>
            </div>
          </label>
        `;
    }).join("");
}

function escapeHtml(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// UI
function showStatus(msg, isError = false) {
    els.status.style.display = "block";
    els.status.style.borderColor = isError ? "#d33" : "#ddd";
    els.status.textContent = msg;
}

function clearUI() {
    els.status.style.display = "none";
    els.preview.style.display = "none";
    els.cover.style.display = "none";
    els.cover.src = "";
    els.title.textContent = "";
    els.meta.textContent = "";
    els.provider.textContent = "";
    els.raw.textContent = "{}";
    els.btnSave.disabled = true;
    lastLookup = null;
}

function renderLookup(result) {
    lastLookup = result;
    els.raw.textContent = JSON.stringify(result, null, 2);

    if (result.error) {
        showStatus(result.error, true);
        els.preview.style.display = "none";
        els.btnSave.disabled = true;
        return;
    }

    showStatus(`OK: ${result.kind.toUpperCase()} ${result.value}`);

    const book = result.book;
    if (!book) {
        els.preview.style.display = "none";
        els.btnSave.disabled = true;
        return;
    }

    els.preview.style.display = "block";
    // els.title.textContent = book.title || "(no title)";

    const subtitle = book.subtitle ? ` — ${book.subtitle}` : "";
    els.title.textContent = (book.title || "(no title)") + subtitle;

    const authors = (book.authors || []).join(", ");
    els.meta.textContent = [
        authors || "(no authors)",
        book.publish_date || "(no date)",
        book.nb_pages ? `${book.nb_pages} pages` : null,
        book.language ? book.language.toUpperCase() : null,
    ].filter(Boolean).join(" · ");

    const srcs = (book.sources || []).map(s => s?.provider).filter(Boolean);
    els.provider.textContent = `Source: ${srcs.length ? srcs.join(" + ") : "unknown"}`;

    const cover = book.cover_image;
    if (cover) {
        els.cover.src = cover;
        els.cover.style.display = "block";
    } else {
        els.cover.style.display = "none";
    }

    els.btnSave.disabled = false;
}

function updateScannerUI() {
    if (!els.scannerMode || !els.scannerDelay) return;
    els.scannerDelayInput.disabled = !els.scannerMode.checked;
    els.scannerDelay.classList.toggle("hidden", !els.scannerMode.checked);
}


// ----- API -----

async function doLookup() {
    const code = els.code.value.trim();
    if (!code) return;

    clearUI();
    showStatus("Looking up...");

    try {
        const result = await apiPost("/api/scan/lookup", { code });
        renderLookup(result);
    } catch (e) {
        showStatus(e.message || "Lookup failed", true);
        els.raw.textContent = JSON.stringify({ error: String(e) }, null, 2);
    }
}

async function doSave() {
    if (!lastLookup?.book) return;

    showStatus("Saving...");

    try {
        const result = await apiPost("/api/books", { book: lastLookup.book });
        els.raw.textContent = JSON.stringify(result, null, 2);
        showStatus(`Saved ✅  (${result.saved?.id || "no id"})`);
        els.btnSave.disabled = true;
    } catch (e) {
        showStatus(e.message || "Save failed", true);
    }
}

function scheduleLookup() {
    if (!els.scannerMode?.checked) return;

    const ms = Math.max(50, Math.min(2000, Number(els.scannerDelayInput?.value || 250)));

    if (lookupTimer) clearTimeout(lookupTimer);
    lookupTimer = setTimeout(() => {
        lookupTimer = null;
        doLookup();
    }, ms);
}

async function refreshAllBooks() {
    if (!confirm("Refresh all books from OpenLibrary / Google Books?")) return;

    showStatus("Refreshing all books...");

    try {
        const result = await apiPost("/api/books/refresh", {
            dry_run: els.chkDryRun?.checked ?? false,
            only_missing: false,
        });

        els.raw.textContent = JSON.stringify(result, null, 2);
        renderRefreshReport(result);

        showStatus(
            `Done: ${result.counts.updated} updated · ` +
            `${result.counts.skipped} skipped · ` +
            `${result.counts.failed} failed`
        );
    } catch (e) {
        showStatus(e.message || "Refresh failed", true);
    }
}


// ----- Events -----

// Buttons
els.btnLookup.addEventListener("click", doLookup);
els.btnSave.addEventListener("click", () => {
    doSave();
    els.code.value = "";
    els.code.focus();
});
els.btnClear.addEventListener("click", () => {
    clearUI();
    els.code.value = "";
    els.code.focus();

    if (lookupTimer) {
        clearTimeout(lookupTimer);
        lookupTimer = null;
    }
});

els.code.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
        // manual immediate lookup always works
        if (lookupTimer) {
            clearTimeout(lookupTimer);
            lookupTimer = null;
        }
        doLookup();
    }
});

els.code.addEventListener("input", () => {
    // In scanner mode, scanners typically "type" quickly then stop.
    // We wait a bit after last character then auto-lookup.
    scheduleLookup();
});

els.scannerMode?.addEventListener("change", () => {
    setCookie(COOKIE_SCANNER_MODE, els.scannerMode.checked ? "1" : "0");
    updateScannerUI();
});

els.scannerDelayInput?.addEventListener("change", () => {
    setCookie(COOKIE_SCANNER_DELAY, els.scannerDelayInput.value);
});

els.btnRefreshAll?.addEventListener("click", refreshAllBooks);



// ----- Boot -----
window.addEventListener("load", () => {
    clearUI();

    const mode = getCookie(COOKIE_SCANNER_MODE);
    if (mode !== null && els.scannerMode) {
        els.scannerMode.checked = mode === "1";
    }

    const delay = getCookie(COOKIE_SCANNER_DELAY);
    if (delay && els.scannerDelayInput) {
        els.scannerDelayInput.value = delay;
    }

    updateScannerUI();

    els.code.focus();
});
