// static/js/scan.js
import { apiPost } from "./api.js";

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
};

let lastLookup = null; // { kind, value, book, error }
let lookupTimer = null;

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

    const ms = Math.max(50, Math.min(2000, Number(els.scannerDelay?.value || 250)));

    if (lookupTimer) clearTimeout(lookupTimer);
    lookupTimer = setTimeout(() => {
        lookupTimer = null;
        doLookup();
    }, ms);
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
    els.code.value = "";
    clearUI();
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

// ----- Boot -----
window.addEventListener("load", () => {
    clearUI();
    els.code.focus();
});
