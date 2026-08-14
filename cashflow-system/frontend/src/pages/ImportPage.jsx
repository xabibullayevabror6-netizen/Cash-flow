import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client";
import { useI18n, formatNumber } from "../i18n";

export default function ImportPage() {
  const { t, lang } = useI18n();
  const money = (n) => formatNumber(n, lang);

  const [bankAccounts, setBankAccounts] = useState([]);
  const [bankAccountId, setBankAccountId] = useState("");
  const [periodDate, setPeriodDate] = useState(new Date().toISOString().slice(0, 10));
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [batches, setBatches] = useState([]);
  const [confirmId, setConfirmId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [notice, setNotice] = useState("");

  function loadBatches() {
    client.get("/api/imports").then((res) => setBatches(res.data)).catch(() => {});
  }

  useEffect(() => {
    client.get("/api/bank-accounts").then((res) => {
      setBankAccounts(res.data);
      if (res.data.length) setBankAccountId(res.data[0].id);
    });
    loadBatches();
  }, []);

  async function handleUpload() {
    if (!file || !bankAccountId) {
      setError(t("import.validation"));
      return;
    }
    setLoading(true);
    setError("");
    setStatus(null);

    const formData = new FormData();
    formData.append("bank_account_id", bankAccountId);
    formData.append("period_date", periodDate);
    formData.append("file", file);

    try {
      const res = await client.post("/api/imports", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setStatus(res.data);
      loadBatches();
    } catch (err) {
      setError(err.response?.data?.detail || t("import.error"));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(batch) {
    setDeletingId(batch.id);
    setNotice("");
    try {
      const res = await client.delete(`/api/imports/${batch.id}`);
      setNotice(t("import.deleted", {
        date: res.data.period_date,
        n: res.data.deleted_transactions,
      }));
      setConfirmId(null);
      loadBatches();
    } catch (err) {
      setError(err.response?.data?.detail || t("import.deleteError"));
    } finally {
      setDeletingId(null);
    }
  }

  if (bankAccounts.length === 0) {
    return (
      <section>
        <div className="page-head">
          <div>
            <h1>{t("import.title")}</h1>
            <p>{t("import.needAccountSubtitle")}</p>
          </div>
        </div>
        <div className="card" style={{ maxWidth: 460, padding: 22 }}>
          <p style={{ fontSize: 13.5, marginBottom: 16 }}>{t("import.needAccountText")}</p>
          <Link to="/bank-accounts" className="btn-primary" style={{ display: "inline-block", textDecoration: "none" }}>
            {t("import.needAccountCta")}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("import.title")}</h1>
          <p>{t("import.subtitle")}</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-head">
          <h3>{t("import.formTitle")}</h3>
        </div>
        <div className="card-body">
          <div className="field">
            <label>{t("import.bankAccount")}</label>
            <select value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
              {bankAccounts.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.bank_name} — {b.account_number} ({b.currency})
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>{t("import.periodDate")}</label>
            <input type="date" value={periodDate} onChange={(e) => setPeriodDate(e.target.value)} />
          </div>

          <div className="field">
            <label>{t("import.excelFile")}</label>
            <input type="file" accept=".xlsx,.xls" onChange={(e) => setFile(e.target.files[0])} />
          </div>

          <button className="btn-primary" style={{ marginTop: 22 }} disabled={loading} onClick={handleUpload}>
            {loading ? t("import.submitting") : t("import.submit")}
          </button>

          {error && <div className="error-msg" style={{ marginTop: 14 }}>{error}</div>}

          {status && (
            <div style={{ marginTop: 18, padding: 12, background: "#EFE3C8", fontSize: 12.5 }}>
              {t("import.result", {
                n: status.row_count,
                date: status.period_date,
                status: t(`status.${status.status}`),
              })}
            </div>
          )}
        </div>
      </div>

      {/* Yuklangan davrlar — ko'rish va o'chirish */}
      <div className="section-head">
        <h2>{t("import.historyTitle")}</h2>
        <span className="hint">
          {batches.length ? t("import.historyCount", { n: batches.length }) : t("import.historyEmptyHint")}
        </span>
      </div>

      {notice && <div className="flag" style={{ marginBottom: 16 }}>{notice}</div>}

      <div className="card">
        <div className="card-body" style={{ padding: "6px 0" }}>
          {batches.length === 0 ? (
            <div className="empty">{t("import.empty")}</div>
          ) : (
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("import.colPeriod")}</th>
                    <th>{t("import.colAccount")}</th>
                    <th>{t("import.colFile")}</th>
                    <th style={{ textAlign: "right" }}>{t("import.colOps")}</th>
                    <th style={{ textAlign: "right" }}>{t("import.colTurnover")}</th>
                    <th>{t("import.colStatus")}</th>
                    <th style={{ textAlign: "right" }}>{t("import.colAction")}</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <tr key={b.id}>
                      <td className="mono"><b>{b.period_date}</b></td>
                      <td>
                        {b.bank_name}
                        <div style={{ fontSize: 11, color: "var(--muted)" }} className="mono">
                          {b.account_number}
                        </div>
                      </td>
                      <td style={{ fontSize: 12 }}>{b.file_name}</td>
                      <td className="mono" style={{ textAlign: "right" }}>{b.transaction_count}</td>
                      <td className="mono" style={{ textAlign: "right", fontSize: 12 }}>
                        +{money(b.cash_in)}
                        <div style={{ color: "var(--muted)" }}>−{money(b.cash_out)}</div>
                      </td>
                      <td>
                        <span className={`tag ${b.status === "completed" ? "in" : b.status === "failed" ? "out" : "pending"}`}>
                          {t(`status.${b.status}`)}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {confirmId === b.id ? (
                          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", alignItems: "center" }}>
                            <button
                              className="btn-danger"
                              disabled={deletingId === b.id}
                              onClick={() => handleDelete(b)}
                            >
                              {deletingId === b.id
                                ? t("import.deleting")
                                : t("import.confirmDelete", { n: b.transaction_count })}
                            </button>
                            <button className="btn-quiet" onClick={() => setConfirmId(null)}>
                              {t("import.cancel")}
                            </button>
                          </div>
                        ) : (
                          <button className="btn-quiet" onClick={() => { setConfirmId(b.id); setNotice(""); }}>
                            {t("import.delete")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {batches.length > 0 && (
        <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 12, lineHeight: 1.6 }}>
          {t("import.footnote")}
        </p>
      )}
    </section>
  );
}
