import { useEffect, useState } from "react";
import client from "../api/client";
import { useI18n } from "../i18n";

export default function BankAccountsPage() {
  const { t } = useI18n();
  const [accounts, setAccounts] = useState([]);
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [currency, setCurrency] = useState("UZS");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  // Boshlang'ich qoldiq tahriri — prognoz likvidlikni shundan hisoblaydi
  const [editId, setEditId] = useState(null);
  const [balance, setBalance] = useState("");
  const [balanceDate, setBalanceDate] = useState("");

  function startEditBalance(a) {
    setEditId(a.id);
    setBalance(a.opening_balance ?? "");
    setBalanceDate(a.opening_balance_date ?? "");
    setError(""); setNotice("");
  }

  async function saveBalance() {
    setLoading(true); setError("");
    try {
      await client.patch(`/api/bank-accounts/${editId}`, {
        opening_balance: balance === "" ? null : Number(balance),
        opening_balance_date: balanceDate || null,
      });
      setNotice(t("bank.balanceSaved"));
      setEditId(null);
      loadAccounts();
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  function loadAccounts() {
    client.get("/api/bank-accounts").then((res) => setAccounts(res.data));
  }

  useEffect(() => {
    loadAccounts();
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setError("");
    if (!bankName.trim() || !accountNumber.trim()) {
      setError(t("bank.validation"));
      return;
    }
    setLoading(true);
    try {
      await client.post("/api/bank-accounts", {
        bank_name: bankName,
        account_number: accountNumber,
        currency,
      });
      setBankName("");
      setAccountNumber("");
      setCurrency("UZS");
      loadAccounts();
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("bank.title")}</h1>
          <p>{t("bank.subtitle")}</p>
        </div>
      </div>

      {notice && <div className="flag" style={{ marginBottom: 16 }}>{notice}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: 20 }}>
        <div className="card">
          <div className="card-head"><h3>{t("bank.addTitle")}</h3></div>
          <div className="card-body">
            <form onSubmit={handleAdd}>
              <div className="field">
                <label>{t("bank.bankName")}</label>
                <input
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder={t("bank.bankNamePlaceholder")}
                />
              </div>
              <div className="field">
                <label>{t("bank.accountNumber")}</label>
                <input
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  placeholder="20208000..."
                />
              </div>
              <div className="field">
                <label>{t("bank.currency")}</label>
                <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                  <option value="UZS">UZS</option>
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
              <button className="btn-primary" type="submit" disabled={loading} style={{ marginTop: 22 }}>
                {loading ? t("bank.submitting") : t("bank.submit")}
              </button>
              {error && <div className="error-msg" style={{ marginTop: 12 }}>{error}</div>}
            </form>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3>{t("bank.existing")}</h3></div>
          <div className="card-body" style={{ padding: accounts.length ? "14px 0 6px" : 22 }}>
            {accounts.length === 0 ? (
              <p style={{ fontSize: 13, color: "#6B675C" }}>
                {t("bank.emptyHint")}
              </p>
            ) : (
              <div className="table-scroll">
                <table className="table">
                  <thead>
                    <tr>
                    <th>{t("table.bank")}</th>
                    <th>{t("table.accountNumber")}</th>
                    <th>{t("table.currency")}</th>
                    <th style={{ textAlign: "right" }}>{t("bank.openingBalance")}</th>
                    <th style={{ textAlign: "right" }}>{t("import.colAction")}</th>
                  </tr>
                  </thead>
                  <tbody>
                    {accounts.map((a) => (
                      <tr key={a.id}>
                        <td>{a.bank_name}</td>
                        <td className="mono">{a.account_number}</td>
                        <td>{a.currency}</td>
                        {editId === a.id ? (
                          <>
                            <td>
                              <input className="search-input" type="number" value={balance}
                                     placeholder={t("bank.openingBalance")}
                                     onChange={(e) => setBalance(e.target.value)} />
                              <input className="search-input" type="date" value={balanceDate}
                                     style={{ marginTop: 5 }}
                                     onChange={(e) => setBalanceDate(e.target.value)} />
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                                <button className="btn-primary"
                                        style={{ padding: "6px 12px", fontSize: 12 }}
                                        disabled={loading} onClick={saveBalance}>
                                  {t("categories.save")}
                                </button>
                                <button className="btn-quiet" onClick={() => setEditId(null)}>
                                  {t("import.cancel")}
                                </button>
                              </div>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="mono" style={{ textAlign: "right" }}>
                              {a.opening_balance != null ? (
                                <>
                                  {Number(a.opening_balance).toLocaleString("ru-RU")}
                                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                                    {a.opening_balance_date}
                                  </div>
                                </>
                              ) : (
                                <span style={{ color: "var(--muted)", fontSize: 11 }}>
                                  {t("bank.noBalance")}
                                </span>
                              )}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button className="btn-quiet" onClick={() => startEditBalance(a)}>
                                {a.opening_balance != null
                                  ? t("categories.edit")
                                  : t("bank.setBalance")}
                              </button>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
