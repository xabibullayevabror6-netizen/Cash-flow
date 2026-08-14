import { useEffect, useState } from "react";
import client from "../api/client";
import { useI18n } from "../i18n";

export default function CategoriesPage() {
  const { t } = useI18n();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [name, setName] = useState("");
  const [type, setType] = useState("expense");
  const [saving, setSaving] = useState(false);

  const [editId, setEditId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState("expense");
  const [deleteId, setDeleteId] = useState(null);

  function load() {
    setLoading(true);
    client.get("/api/categories")
      .then((r) => setItems(r.data))
      .catch(() => setError(t("common.error")))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function create(e) {
    e.preventDefault();
    setError(""); setNotice("");
    setSaving(true);
    try {
      await client.post("/api/categories", { name, type });
      setNotice(t("categories.created", { name }));
      setName("");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  function startEdit(c) {
    setEditId(c.id); setEditName(c.name); setEditType(c.type);
    setError(""); setNotice(""); setDeleteId(null);
  }

  async function saveEdit() {
    setSaving(true); setError("");
    try {
      await client.patch(`/api/categories/${editId}`, { name: editName, type: editType });
      setNotice(t("categories.updated"));
      setEditId(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  async function remove(id) {
    setSaving(true); setError("");
    try {
      await client.delete(`/api/categories/${id}`);
      setNotice(t("categories.deleted"));
      setDeleteId(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("categories.title")}</h1>
          <p>{t("categories.subtitle")}</p>
        </div>
      </div>

      {notice && <div className="flag" style={{ marginBottom: 16 }}>{notice}</div>}
      {error && <div className="flag warn" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 20, alignItems: "start" }}>
        <div className="card">
          <div className="card-head"><h3>{t("categories.addTitle")}</h3></div>
          <div className="card-body">
            <form onSubmit={create}>
              <div className="field">
                <label>{t("categories.name")}</label>
                <input value={name} onChange={(e) => setName(e.target.value)}
                       placeholder={t("categories.namePlaceholder")} required />
              </div>
              <div className="field">
                <label>{t("categories.type")}</label>
                <select value={type} onChange={(e) => setType(e.target.value)}>
                  <option value="expense">{t("categories.expense")}</option>
                  <option value="income">{t("categories.income")}</option>
                </select>
              </div>
              <button className="btn-primary" type="submit" disabled={saving} style={{ marginTop: 22 }}>
                {saving ? t("bank.submitting") : t("categories.add")}
              </button>
            </form>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>{t("categories.listTitle")}</h3>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{items.length}</span>
          </div>
          <div className="card-body" style={{ padding: "6px 0" }}>
            {loading ? (
              <div className="empty">{t("common.loading")}</div>
            ) : (
              <div className="table-scroll">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t("categories.name")}</th>
                      <th>{t("categories.type")}</th>
                      <th style={{ textAlign: "right" }}>{t("categories.usage")}</th>
                      <th style={{ textAlign: "right" }}>{t("import.colAction")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((c) => (
                      <tr key={c.id}>
                        <td>
                          {editId === c.id ? (
                            <input className="search-input" value={editName}
                                   onChange={(e) => setEditName(e.target.value)} />
                          ) : (
                            <>
                              {c.name}
                              {c.is_system && <span className="sys-tag">{t("categories.system")}</span>}
                            </>
                          )}
                        </td>
                        <td>
                          {editId === c.id ? (
                            <select className="cat-select" value={editType}
                                    onChange={(e) => setEditType(e.target.value)}>
                              <option value="expense">{t("categories.expense")}</option>
                              <option value="income">{t("categories.income")}</option>
                            </select>
                          ) : (
                            <span className={`tag ${c.type === "income" ? "in" : "out"}`}>
                              {t(`categories.${c.type}`)}
                            </span>
                          )}
                        </td>
                        <td className="mono" style={{ textAlign: "right" }}>{c.transaction_count}</td>
                        <td style={{ textAlign: "right" }}>
                          {c.is_system ? (
                            <span style={{ fontSize: 11, color: "var(--muted)" }}>—</span>
                          ) : editId === c.id ? (
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                              <button className="btn-primary" style={{ padding: "6px 12px", fontSize: 12 }}
                                      disabled={saving} onClick={saveEdit}>
                                {t("categories.save")}
                              </button>
                              <button className="btn-quiet" onClick={() => setEditId(null)}>
                                {t("import.cancel")}
                              </button>
                            </div>
                          ) : deleteId === c.id ? (
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                              <button className="btn-danger" disabled={saving} onClick={() => remove(c.id)}>
                                {t("categories.deleteYes")}
                              </button>
                              <button className="btn-quiet" onClick={() => setDeleteId(null)}>
                                {t("import.cancel")}
                              </button>
                            </div>
                          ) : (
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                              <button className="btn-quiet" onClick={() => startEdit(c)}>
                                {t("categories.edit")}
                              </button>
                              <button className="btn-quiet" disabled={c.transaction_count > 0}
                                      title={c.transaction_count > 0 ? t("categories.cannotDelete") : ""}
                                      onClick={() => { setDeleteId(c.id); setError(""); setNotice(""); }}>
                                {t("import.delete")}
                              </button>
                            </div>
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
      </div>

      <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 12, lineHeight: 1.6 }}>
        {t("categories.footnote")}
      </p>
    </section>
  );
}
