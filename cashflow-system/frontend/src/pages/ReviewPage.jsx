import { useCallback, useEffect, useState } from "react";
import client from "../api/client";
import { useI18n, formatNumber } from "../i18n";

const PAGE_SIZE = 50;

export default function ReviewPage() {
  const { t, lang } = useI18n();
  const money = (n) => formatNumber(n, lang);

  const [page, setPage] = useState({ items: [], total: 0, pending_total: 0, offset: 0 });
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Filtrlar
  const [status, setStatus] = useState("pending_review");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const [selected, setSelected] = useState(new Set());
  const [busy, setBusy] = useState(false);

  // "Filtrga tushgan hammasi" rejimi: sahifada ko'rinmayotganlari ham qamraladi.
  // Bunda alohida id'lar emas, filtrning o'zi serverga yuboriladi.
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [bulkCategory, setBulkCategory] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset });
    if (status) params.set("review_status", status);
    if (appliedSearch) params.set("search", appliedSearch);

    client.get(`/api/transactions?${params}`)
      .then((r) => { setPage(r.data); setError(""); })
      .catch(() => setError(t("common.error")))
      .finally(() => setLoading(false));
  }, [status, appliedSearch, offset, t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    client.get("/api/categories").then((r) => setCategories(r.data)).catch(() => {});
  }, []);

  // Filtr o'zgarsa birinchi sahifaga qaytamiz va tanlovni tozalaymiz
  useEffect(() => {
    setOffset(0);
    setSelected(new Set());
    setSelectAllMatching(false);
  }, [status, appliedSearch]);

  function toggle(id) {
    setSelectAllMatching(false);
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Kategoriya tasdiqlangan operatsiyada ham o'zgarishi mumkin, shuning uchun
  // belgilash barcha qatorlar uchun ochiq. Tasdiqlash esa faqat kutayotganlarga.
  const pendingOnPage = page.items.filter((i) => i.review_status === "pending_review");
  const allSelected = page.items.length > 0 && page.items.every((i) => selected.has(i.id));

  function toggleAll() {
    setSelectAllMatching(false);
    setSelected(allSelected ? new Set() : new Set(page.items.map((i) => i.id)));
  }

  // Nechta operatsiyaga ta'sir qiladi — foydalanuvchi bosishdan oldin bilishi kerak
  const affected = selectAllMatching ? page.total : selected.size;

  async function applyCategory() {
    if (!bulkCategory || !affected) return;
    setBusy(true);
    setNotice(""); setError("");
    try {
      const body = { category_id: bulkCategory };
      if (selectAllMatching) {
        // Filtrni yuboramiz — server sahifadan tashqaridagilarni ham qamraydi
        if (status) body.review_status = status;
        if (appliedSearch) body.search = appliedSearch;
      } else {
        body.transaction_ids = [...selected];
      }

      const res = await client.post("/api/transactions/bulk-categorize", body);
      setNotice(t("review.categorizedBulk", {
        n: res.data.updated,
        category: res.data.category_name,
        rules: res.data.rules_created,
      }));
      setSelected(new Set());
      setSelectAllMatching(false);
      setBulkCategory("");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function changeCategory(transactionId, categoryId) {
    if (!categoryId) return;
    setBusy(true);
    try {
      await client.patch(`/api/transactions/${transactionId}`, { category_id: categoryId });
      setNotice(t("review.categoryChanged"));
      load();
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmSelected() {
    setBusy(true);
    setNotice("");
    try {
      const body = selectAllMatching
        ? { search: appliedSearch || null }
        : { transaction_ids: [...selected] };
      const res = await client.post("/api/transactions/bulk-confirm", body);
      setNotice(t("review.confirmed", { n: res.data.confirmed }));
      setSelected(new Set());
      setSelectAllMatching(false);
      load();
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmAllFiltered() {
    setBusy(true);
    setNotice("");
    try {
      const res = await client.post("/api/transactions/bulk-confirm", {
        search: appliedSearch || null,
      });
      setNotice(t("review.confirmed", { n: res.data.confirmed }));
      setSelected(new Set());
      load();
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const [confirmAllOpen, setConfirmAllOpen] = useState(false);
  const [recatOpen, setRecatOpen] = useState(false);
  const pageEnd = Math.min(offset + PAGE_SIZE, page.total);

  async function recategorize() {
    setBusy(true);
    setNotice(""); setError("");
    try {
      const res = await client.post("/api/transactions/recategorize");
      setNotice(t("review.recategorized", {
        n: res.data.updated,
        manual: res.data.skipped_manual,
      }));
      setRecatOpen(false);
      load();
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("review.title")}</h1>
          <p>{t("review.subtitle")}</p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", letterSpacing: ".06em" }}>
            {t("review.pendingLabel")}
          </div>
          <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: page.pending_total ? "var(--rust)" : "var(--flow-pos)" }}>
            {page.pending_total}
          </div>
        </div>
      </div>

      {notice && <div className="flag" style={{ marginBottom: 16 }}>{notice}</div>}
      {error && <div className="flag warn" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Filtrlar */}
      <div className="filter-bar">
        <div className="seg">
          {[
            { v: "pending_review", l: t("review.filterPending") },
            { v: "confirmed", l: t("review.filterConfirmed") },
            { v: "", l: t("review.filterAll") },
          ].map((o) => (
            <button key={o.v} className={status === o.v ? "active" : ""} onClick={() => setStatus(o.v)}>
              {o.l}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); setAppliedSearch(search); }}
          style={{ display: "flex", gap: 8, flex: 1, maxWidth: 420 }}
        >
          <input
            className="search-input"
            placeholder={t("review.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="btn-quiet" type="submit">{t("review.search")}</button>
          {appliedSearch && (
            <button className="btn-quiet" type="button" onClick={() => { setSearch(""); setAppliedSearch(""); }}>
              ×
            </button>
          )}
        </form>

        {/* Provodkalar bo'yicha qayta taqsimlash — eski ma'lumotni yangi
            qoidalarga o'tkazish uchun. Yangi importda avtomatik ishlaydi. */}
        {recatOpen ? (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="btn-danger" disabled={busy} onClick={recategorize}>
              {busy ? t("bank.submitting") : t("review.recategorizeYes")}
            </button>
            <button className="btn-quiet" onClick={() => setRecatOpen(false)}>
              {t("import.cancel")}
            </button>
          </div>
        ) : (
          <button className="btn-quiet" title={t("review.recategorizeHint")}
                  onClick={() => { setRecatOpen(true); setNotice(""); }}>
            {t("review.recategorize")}
          </button>
        )}
      </div>

      {recatOpen && (
        <div className="flag" style={{ marginBottom: 16 }}>
          {t("review.recategorizeHint")}
        </div>
      )}

      {/* Guruhli amallar */}
      {page.total > 0 && (
        <div className="bulk-bar">
          <div className="bulk-info">
            <span>
              {affected > 0
                ? t("review.selectedCount", { n: affected })
                : t("review.bulkHint")}
            </span>

            {/* Sahifada hammasi belgilangan, lekin filtrda undan ko'p bor —
                foydalanuvchiga qolganini ham qamrash imkonini beramiz */}
            {allSelected && !selectAllMatching && page.total > page.items.length && (
              <button className="link-btn" style={{ marginTop: 0 }}
                      onClick={() => setSelectAllMatching(true)}>
                {t("review.selectAllMatching", { n: page.total })}
              </button>
            )}
            {selectAllMatching && (
              <button className="link-btn" style={{ marginTop: 0 }}
                      onClick={() => { setSelectAllMatching(false); setSelected(new Set()); }}>
                {t("review.clearSelection")}
              </button>
            )}
          </div>

          <div className="bulk-actions">
            {/* Tanlanganlarni bitta kategoriyaga o'tkazish */}
            {affected > 0 && (
              <>
                <select className="cat-select" value={bulkCategory} disabled={busy}
                        onChange={(e) => setBulkCategory(e.target.value)}
                        aria-label={t("review.chooseCategory")}>
                  <option value="">{t("review.chooseCategory")}</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <button className="btn-primary" style={{ padding: "8px 14px", fontSize: 12.5 }}
                        disabled={busy || !bulkCategory} onClick={applyCategory}>
                  {t("review.applyCategory", { n: affected })}
                </button>
              </>
            )}

            {affected > 0 && status === "pending_review" && (
              <button className="btn-quiet" disabled={busy} onClick={confirmSelected}>
                {t("review.confirmSelected", { n: affected })}
              </button>
            )}

            {status === "pending_review" && (
              confirmAllOpen ? (
                <>
                  <button className="btn-danger" disabled={busy} onClick={confirmAllFiltered}>
                    {t("review.confirmAllYes", { n: page.total })}
                  </button>
                  <button className="btn-quiet" onClick={() => setConfirmAllOpen(false)}>
                    {t("import.cancel")}
                  </button>
                </>
              ) : (
                <button className="btn-quiet" onClick={() => setConfirmAllOpen(true)}>
                  {t("review.confirmAll", { n: page.total })}
                </button>
              )
            )}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-body" style={{ padding: "6px 0" }}>
          {loading ? (
            <div className="empty">{t("common.loading")}</div>
          ) : page.items.length === 0 ? (
            <div className="empty">
              {status === "pending_review" ? t("review.allDone") : t("common.noData")}
            </div>
          ) : (
            <div className="table-scroll review-table-scroll">
              <table className="table review-table">
                <thead>
                  <tr>
                    <th style={{ width: 32 }}>
                      {page.items.length > 0 && (
                        <input type="checkbox" checked={allSelected} onChange={toggleAll}
                               aria-label={t("review.selectAll")} />
                      )}
                    </th>
                    <th>{t("import.colPeriod")}</th>
                    <th>{t("table.counterparty")}</th>
                    <th style={{ textAlign: "right" }}>{t("table.amount")}</th>
                    <th>{t("review.category")}</th>
                    <th>{t("review.confidence")}</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((tx) => {
                    const isPending = tx.review_status === "pending_review";
                    return (
                      <tr key={tx.id} className={selected.has(tx.id) ? "row-selected" : ""}>
                        <td>
                          <input type="checkbox" checked={selected.has(tx.id) || selectAllMatching}
                                 onChange={() => toggle(tx.id)} />
                        </td>
                        <td className="mono" style={{ fontSize: 11.5, whiteSpace: "nowrap" }}>{tx.date}</td>
                        <td>
                          <div style={{ fontWeight: 500 }}>{tx.counterparty}</div>
                          {tx.raw_description && (
                            <div className="desc-line">{tx.raw_description}</div>
                          )}
                        </td>
                        <td className="mono" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                          <span className={tx.direction === "in" ? "amt-in" : "amt-out"}>
                            {tx.direction === "in" ? "+" : "−"}{money(tx.amount)}
                          </span>
                        </td>
                        <td>
                          <select
                            className="cat-select"
                            value={tx.category_id || ""}
                            disabled={busy}
                            onChange={(e) => changeCategory(tx.id, e.target.value)}
                          >
                            <option value="">{t("review.noCategory")}</option>
                            {categories.map((c) => (
                              <option key={c.id} value={c.id}>{c.name}</option>
                            ))}
                          </select>
                        </td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          {isPending ? (
                            <span className="tag pending">
                              {tx.confidence_score != null
                                ? `${Math.round(tx.confidence_score * 100)}%`
                                : t("review.noAi")}
                            </span>
                          ) : (
                            <span className="tag in">{t("review.confirmedTag")}</span>
                          )}
                          {/* Kategoriya qayerdan kelgani — buxgalter nimaga
                              qanchalik ishonish mumkinligini bilishi uchun */}
                          {tx.category_source && (
                            <div className="src-line">
                              {t(`review.source.${tx.category_source}`)}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Sahifalash */}
      {page.total > PAGE_SIZE && (
        <div className="pager">
          <button className="btn-quiet" disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            ← {t("review.prev")}
          </button>
          <span className="mono">
            {offset + 1}–{pageEnd} / {page.total}
          </span>
          <button className="btn-quiet" disabled={pageEnd >= page.total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}>
            {t("review.next")} →
          </button>
        </div>
      )}
    </section>
  );
}
