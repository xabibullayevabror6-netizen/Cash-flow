import { useEffect, useState } from "react";
import client from "../api/client";
import { useI18n } from "../i18n";

export default function SettingsPage() {
  const { t } = useI18n();

  const [me, setMe] = useState(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    client.get("/api/auth/me").then((r) => setMe(r.data)).catch(() => {});
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError(""); setNotice("");

    if (next !== repeat) {
      setError(t("settings.mismatch"));
      return;
    }

    setSaving(true);
    try {
      const res = await client.post("/api/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      // Eski tokenlar bekor qilindi — yangisini saqlaymiz, aks holda
      // shu sahifaning o'zi ham darhol tizimdan chiqib ketadi.
      localStorage.setItem("token", res.data.access_token);
      setNotice(t("settings.changed"));
      setCurrent(""); setNext(""); setRepeat("");
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  const strength = passwordStrength(next);

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{t("settings.title")}</h1>
          <p>{t("settings.subtitle")}</p>
        </div>
      </div>

      {notice && <div className="flag" style={{ marginBottom: 16 }}>{notice}</div>}
      {error && <div className="flag warn" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(280px,380px) 1fr", gap: 20, alignItems: "start" }}>
        <div className="card">
          <div className="card-head"><h3>{t("settings.passwordTitle")}</h3></div>
          <div className="card-body">
            <form onSubmit={submit}>
              <div className="field">
                <label>{t("settings.currentPassword")}</label>
                <input type="password" value={current} autoComplete="current-password"
                       onChange={(e) => setCurrent(e.target.value)} required />
              </div>
              <div className="field">
                <label>{t("settings.newPassword")}</label>
                <input type="password" value={next} autoComplete="new-password"
                       onChange={(e) => setNext(e.target.value)} required />
                {next && (
                  <div className="pw-meter">
                    <div className={`pw-bar ${strength.level}`} style={{ width: `${strength.percent}%` }} />
                    <span className="pw-label">{t(`settings.strength.${strength.level}`)}</span>
                  </div>
                )}
              </div>
              <div className="field">
                <label>{t("settings.repeatPassword")}</label>
                <input type="password" value={repeat} autoComplete="new-password"
                       onChange={(e) => setRepeat(e.target.value)} required />
              </div>
              <button className="btn-primary" type="submit" disabled={saving} style={{ marginTop: 22 }}>
                {saving ? t("bank.submitting") : t("settings.save")}
              </button>
            </form>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3>{t("settings.accountTitle")}</h3></div>
          <div className="card-body">
            {me ? (
              <dl className="info-list">
                <dt>{t("settings.company")}</dt><dd>{me.company_name}</dd>
                <dt>{t("login.email")}</dt><dd className="mono">{me.email}</dd>
                <dt>{t("settings.role")}</dt><dd>{me.role}</dd>
              </dl>
            ) : (
              <div className="empty">{t("common.loading")}</div>
            )}
            <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 18, lineHeight: 1.65 }}>
              {t("settings.footnote")}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Sodda baho: uzunlik va belgilar rang-barangligi. Server baribir o'zi tekshiradi. */
function passwordStrength(pw) {
  if (!pw) return { level: "weak", percent: 0 };
  let score = 0;
  if (pw.length >= 10) score += 1;
  if (pw.length >= 14) score += 1;
  if (new Set(pw).size >= 8) score += 1;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score += 1;
  if (/\d/.test(pw)) score += 1;
  if (/[^\w\s]/.test(pw)) score += 1;

  if (score <= 2) return { level: "weak", percent: 30 };
  if (score <= 4) return { level: "medium", percent: 65 };
  return { level: "strong", percent: 100 };
}
