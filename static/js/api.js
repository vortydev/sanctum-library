// static/js/api.js
export async function apiPost(path, payload) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload ?? {}),
    });

    const text = await res.text();
    let data;
    try { data = text ? JSON.parse(text) : null; }
    catch { data = { error: "Non-JSON response", raw: text }; }

    if (!res.ok) {
        const msg = (data && data.error) ? data.error : `HTTP ${res.status}`;
        throw new Error(msg);
    }
    return data;
}
