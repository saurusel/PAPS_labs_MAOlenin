/* Lab 5 client: vanilla JS + Nginx proxy (/api -> server)
   Backend: FastAPI (см. server/app/main.py)
*/

const API = "/api";

const el = (selector) => document.querySelector(selector);

const safeText = (node, value) => {
    if (!node) return;
    node.textContent = value;
};

const on = (selector, event, handler) => {
    const node = el(selector);
    if (!node) {
        console.warn(`[UI] element not found: ${selector}`);
        return;
    }
    node.addEventListener(event, handler);
};

const pretty = (obj) => {
    try {
        return JSON.stringify(obj, null, 2);
    } catch {
        return String(obj);
    }
};

let toastTimer = null;
const toast = (type, title, text) => {
    const t = el("#toast");
    if (!t) return;

    t.className = `toast ${type}`;
    t.innerHTML = `<div class="t-title">${title}</div><div class="t-text">${text}</div>`;
    t.classList.add("show");

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2400);
};

const setBtnBusy = (btn, busy, busyText = "Подождите…") => {
    if (!btn) return;
    if (busy) {
        btn.disabled = true;
        btn.dataset.prevText = btn.textContent;
        btn.textContent = busyText;
    } else {
        btn.disabled = false;
        if (btn.dataset.prevText) btn.textContent = btn.dataset.prevText;
    }
};

// -------- Status helpers (backend uses russian statuses) --------

const OK_STATUSES = [
    "Новый",
    "На проверке",
    "Сборка",
    "Готов к выдаче",
    "Завершен",
];

const statusBadge = (status) => {
    const cls = status === "Отменен" ? "bad" : OK_STATUSES.includes(status) ? "ok" : "";
    return `<span class="badge ${cls}">${status}</span>`;
};

// -------- Log + last response --------

const logEntries = [];

const renderLog = () => {
    const table = el("#logTable");
    if (!table) return;

    table.innerHTML = logEntries
        .map((e) => {
            const badge = e.ok
                ? `<span class="badge ok">${e.status}</span>`
                : `<span class="badge bad">${e.status}</span>`;
            return `
      <tr>
        <td style="width:90px;color:#64748b">${e.time}</td>
        <td style="width:70px">${badge}</td>
        <td><code>${e.method}</code> <code>${e.path}</code></td>
        <td style="width:70px;color:#64748b;text-align:right">${e.ms}ms</td>
      </tr>
    `;
        })
        .join("");
};

const appendLog = (entry) => {
    logEntries.unshift(entry);
    if (logEntries.length > 80) logEntries.pop();
    renderLog();
};

const renderLast = (payload) => {
    const pre = el("#out");
    if (!pre) return;

    pre.textContent = pretty({
        time: payload.time,
        request: {
            method: payload.method,
            path: payload.path,
            headers: payload.headers,
            body: payload.body,
        },
        response: {
            status: payload.status,
            ok: payload.ok,
            body: payload.response,
        },
    });
};

const logAction = (entry) => {
    appendLog({
        time: entry.time,
        status: entry.status,
        method: entry.method,
        path: entry.path,
        ms: entry.ms,
        ok: entry.status >= 200 && entry.status < 300,
    });
};

const errorMessageFromResponse = (status, json) => {
    if (status === -1) return json?.error || "Сетевая ошибка";

    const msg =
        json?.error?.message ||
        json?.detail?.error?.message ||
        json?.message ||
        (typeof json === "string" ? json : "Ошибка запроса");

    return `${msg} (HTTP ${status})`;
};

/**
 * request(method, path, bodyOrOptions, extraHeaders)
 *
 * Поддержка:
 *  1) request("POST", "/x", payload, {"X-Role":"..."})
 *  2) request("POST", "/x", { headers: {...}, body: payload, log: true|false })
 */
const request = async (method, path, bodyOrOptions = null, extraHeaders = {}) => {
    let body = null;
    let mergedHeaders = { ...extraHeaders };
    let log = true;

    const isOptionsObject =
        bodyOrOptions &&
        typeof bodyOrOptions === "object" &&
        (Object.prototype.hasOwnProperty.call(bodyOrOptions, "headers") ||
            Object.prototype.hasOwnProperty.call(bodyOrOptions, "body") ||
            Object.prototype.hasOwnProperty.call(bodyOrOptions, "log"));

    if (isOptionsObject) {
        const opt = bodyOrOptions;
        if (opt.headers && typeof opt.headers === "object") {
            mergedHeaders = { ...mergedHeaders, ...opt.headers };
        }
        if (Object.prototype.hasOwnProperty.call(opt, "log")) {
            log = Boolean(opt.log);
        }
        body = opt.body ?? null;
    } else {
        body = bodyOrOptions;
    }

    const t0 = performance.now();
    const init = {
        method,
        headers: {
            "Content-Type": "application/json",
            ...mergedHeaders,
        },
    };

    // fetch не разрешает body для GET/HEAD
    if (
        method !== "GET" &&
        method !== "HEAD" &&
        body !== null &&
        body !== undefined
    ) {
        init.body = JSON.stringify(body);
    }

    let status = 0;
    let json = null;

    try {
        const res = await fetch(path, init);
        status = res.status;
        const text = await res.text();
        try {
            json = text ? JSON.parse(text) : null;
        } catch {
            json = { raw: text };
        }
    } catch (e) {
        status = -1;
        json = { error: String(e) };
    }

    const ms = Math.round(performance.now() - t0);
    const ok = status >= 200 && status < 300;

    if (log) {
        renderLast({
            time: new Date().toLocaleTimeString(),
            method,
            path,
            headers: mergedHeaders,
            body,
            status,
            ok,
            response: json,
        });

        logAction({
            time: new Date().toLocaleTimeString(),
            status,
            method,
            path,
            ms,
        });
    }

    if (!ok) {
        throw new Error(errorMessageFromResponse(status, json));
    }

    return json;
};

// -------- Tabs --------

const initTabs = () => {
    const tabs = Array.from(document.querySelectorAll(".tab"));
    const panels = {
        work: el("#tab-work"),
        diag: el("#tab-diag"),
        help: el("#tab-help"),
    };

    const activate = (name) => {
        tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
        Object.entries(panels).forEach(([k, node]) => {
            if (!node) return;
            node.classList.toggle("active", k === name);
        });
    };

    tabs.forEach((t) => {
        t.addEventListener("click", () => activate(t.dataset.tab));
    });

    activate("work");
};

// -------- Health --------

const checkHealth = async () => {
    const dot = el("#healthDot");
    const text = el("#healthText");

    try {
        await request("GET", "/health", { log: false });
        dot?.classList.remove("bad");
        dot?.classList.add("ok");
        safeText(text, "OK");
    } catch {
        dot?.classList.remove("ok");
        dot?.classList.add("bad");
        safeText(text, "DOWN");
    }
};

// -------- Products UI helpers --------

const flattenSkus = (products) => {
    const out = [];
    for (const p of products) {
        const variants = Array.isArray(p?.variants) ? p.variants : [];
        for (const v of variants) {
            if (v?.sku) out.push({ sku: v.sku, productName: p?.name || "" });
        }
    }
    return out;
};

const renderProductsShort = (items) => {
    const host = el("#productsShort");
    if (!host) return;

    if (!items.length) {
        host.innerHTML = `<span class="badge">Пусто</span>`;
        return;
    }

    const skus = flattenSkus(items).slice(0, 10);
    host.innerHTML = skus
        .map((x, idx) => {
            return `<div style="margin:4px 0">
      <strong>#${idx + 1}</strong> ${x.productName} — <span style="color:#64748b">SKU:</span> <code>${x.sku}</code>
    </div>`;
        })
        .join("");
};

const renderProducts = (items) => {
    const host = el("#productsList");
    if (!host) return;

    if (!items.length) {
        host.innerHTML = `<span class="badge">Каталог пуст</span>`;
        return;
    }

    host.innerHTML = items
        .map((p) => {
            const variants = Array.isArray(p?.variants) ? p.variants : [];
            const vHtml = variants
                .map((v) => {
                    const avail = Number(v.stock_total || 0) - Number(v.reserved || 0);
                    return `<div class="mini-row">
          <div><code>${v.sku}</code></div>
          <div style="color:#64748b">${v.size || "—"} / ${v.color || "—"}</div>
          <div style="text-align:right"><code>${v.price_points}</code> pts</div>
          <div style="text-align:right"><code>${avail}</code> avail</div>
        </div>`;
                })
                .join("");

            return `<div class="p-card">
        <div class="p-title">${p.name} <span class="p-id">#${p.id}</span></div>
        <div class="p-desc">${p.description || ""}</div>
        <div class="mini-head">
          <div>SKU</div>
          <div>Size/Color</div>
          <div style="text-align:right">Price</div>
          <div style="text-align:right">Available</div>
        </div>
        ${vHtml || `<span class="badge">Нет вариантов</span>`}
      </div>`;
        })
        .join("");
};

const fillSkuSelect = (items) => {
    const sel = el("#skuSelect");
    if (!sel) return;

    const skus = flattenSkus(items);
    sel.innerHTML = skus
        .map((x) => `<option value="${x.sku}">${x.sku}</option>`)
        .join("");
};

const loadProducts = async (q = "") => {
    const query = q ? `?q=${encodeURIComponent(q)}` : "";
    const data = await request("GET", `${API}/v1/products${query}`);
    const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];

    renderProducts(items);
    renderProductsShort(items);
    fillSkuSelect(items);

    return items;
};

// -------- Orders --------

const parseItemsText = (text) => {
    const lines = String(text || "")
        .split(/\r?\n/)
        .map((x) => x.trim())
        .filter(Boolean);

    const items = [];
    for (const line of lines) {
        const parts = line.split(/\s+/).filter(Boolean);
        const sku = parts[0];
        const qty = parts.length > 1 ? Number(parts[1]) : 1;
        if (!sku) continue;
        if (!Number.isFinite(qty) || qty <= 0) {
            throw new Error(`Некорректное количество в строке: "${line}"`);
        }
        items.push({ sku, qty: Math.floor(qty) });
    }

    if (!items.length) throw new Error("Не указаны позиции заказа (Items)");
    return items;
};

const loadOrders = async () => {
    const userId = el("#userId")?.value || "u1";
    const status = el("#statusFilter")?.value || "";
    const query = status ? `?status=${encodeURIComponent(status)}` : "";

    const data = await request("GET", `${API}/v1/orders${query}`, {
        headers: { "X-Role": "buyer", "X-User-Id": userId },
    });

    const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];

    const host = el("#ordersList");
    if (host) {
        if (!items.length) {
            host.innerHTML = `<span class="badge">Пока нет заказов</span>`;
        } else {
            host.innerHTML = items
                .slice(0, 30)
                .map((o) => {
                    return `<div style="padding:8px 0;border-bottom:1px solid #e5e7eb">
          <div><strong>ID:</strong> <code>${o.id}</code> &nbsp; ${statusBadge(o.status)}</div>
          <div style="color:#64748b;font-size:13px;margin-top:2px">
            user: <code>${o.user_id}</code>, items: <code>${(o.items || []).length}</code>, total: <code>${o.total_points}</code>
          </div>
        </div>`;
                })
                .join("");
        }
    }

    return items;
};

// -------- App bootstrap --------

document.addEventListener("DOMContentLoaded", async () => {
    initTabs();

    on("#btnHealth", "click", async () => {
        const btn = el("#btnHealth");
        setBtnBusy(btn, true, "Проверяю…");
        try {
            await checkHealth();
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#btnClearLog", "click", () => {
        logEntries.length = 0;
        renderLog();
        toast("success", "Готово", "Лента действий очищена");
    });

    on("#btnCopySku", "click", async () => {
        const sku = el("#skuSelect")?.value || "";
        if (!sku) return;
        try {
            await navigator.clipboard.writeText(sku);
            toast("success", "Скопировано", `SKU: ${sku}`);
        } catch {
            toast("error", "Не удалось", "Браузер не дал доступ к буферу обмена");
        }
    });

    on("#btnLoadProducts", "click", async () => {
        const btn = el("#btnLoadProducts");
        setBtnBusy(btn, true, "Обновляю…");
        try {
            await loadProducts("");
            toast("success", "Ок", "Список товаров обновлён");
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#btnSearchProducts", "click", async () => {
        const btn = el("#btnSearchProducts");
        const q = el("#pSearch")?.value || "";
        setBtnBusy(btn, true, "Ищу…");
        try {
            await loadProducts(q);
            toast("success", "Ок", q ? `Поиск: ${q}` : "Показаны все товары");
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#btnCreateProduct", "click", async () => {
        const btn = el("#btnCreateProduct");
        setBtnBusy(btn, true, "Создаю…");
        try {
            const name = el("#pName")?.value || "";
            if (!name.trim()) throw new Error("Укажи название товара");

            const skuInput = (el("#pSku")?.value || "").trim();
            const sku = skuInput || `SKU-${Date.now().toString(36).toUpperCase()}`;

            const payload = {
                name: name.trim(),
                description: (el("#pDesc")?.value || "").trim(),
                images: [],
                variants: [
                    {
                        sku,
                        size: (el("#pSize")?.value || "").trim() || null,
                        color: (el("#pColor")?.value || "").trim() || null,
                        price_points: Number(el("#pPrice")?.value || 0),
                        stock_total: Number(el("#pStock")?.value || 0),
                    },
                ],
            };

            await request("POST", `${API}/v1/products`, {
                headers: { "X-Role": "content_admin" },
                body: payload,
            });

            toast("success", "Создано", `Товар создан (SKU: ${sku})`);
            await loadProducts("");
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#btnCreateOrder", "click", async () => {
        const btn = el("#btnCreateOrder");
        setBtnBusy(btn, true, "Отправляю…");

        try {
            const userId = el("#userId")?.value || "u1";
            const text = el("#itemsText")?.value || "";
            const items = parseItemsText(text);

            await request("POST", `${API}/v1/orders`, {
                headers: { "X-Role": "buyer", "X-User-Id": userId },
                body: { items },
            });

            toast("success", "Ок", "Заказ создан");
            await loadOrders();
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#btnLoadOrders", "click", async () => {
        const btn = el("#btnLoadOrders");
        setBtnBusy(btn, true, "Загружаю…");
        try {
            await loadOrders();
            toast("success", "Ок", "Список заказов обновлён");
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#statusFilter", "change", async () => {
        try {
            await loadOrders();
        } catch {}
    });

    on("#userId", "change", async () => {
        try {
            await loadOrders();
        } catch {}
    });

    on("#btnUpdateStatus", "click", async () => {
        const btn = el("#btnUpdateStatus");
        setBtnBusy(btn, true, "Меняю…");
        try {
            const id = Number(el("#orderId")?.value || 0);
            const st = el("#newStatus")?.value || "На проверке";
            if (!id) throw new Error("Укажи Order ID");

            await request("PUT", `${API}/v1/orders/${id}/status`, {
                headers: { "X-Role": "fulfillment_admin" },
                body: { status: st },
            });

            toast("success", "Ок", "Статус обновлён");
            await loadOrders();
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    on("#btnCancelOrder", "click", async () => {
        const btn = el("#btnCancelOrder");
        setBtnBusy(btn, true, "Отменяю…");
        try {
            const id = Number(el("#orderId")?.value || 0);
            if (!id) throw new Error("Укажи Order ID");

            await request("DELETE", `${API}/v1/orders/${id}`, {
                headers: { "X-Role": "fulfillment_admin" },
            });

            toast("success", "Ок", "Заказ отменён");
            await loadOrders();
        } catch (e) {
            toast("error", "Ошибка", e.message);
        } finally {
            setBtnBusy(btn, false);
        }
    });

    // стартовые загрузки
    await checkHealth();
    try {
        await loadProducts("");
    } catch {}
    try {
        await loadOrders();
    } catch {}
});
