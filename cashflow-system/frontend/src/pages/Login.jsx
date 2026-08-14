import { useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import { useI18n } from "../i18n";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { t } = useI18n();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const url = isRegister ? "/api/auth/register" : "/api/auth/login";
      const payload = isRegister
        ? { company_name: companyName, email, password }
        : { email, password };
      const res = await client.post(url, payload);
      localStorage.setItem("token", res.data.access_token);
      navigate("/bank-accounts");
    } catch (err) {
      setError(err.response?.data?.detail || t("common.error"));
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>{t("brand.name")}</h1>
        <p>{isRegister ? t("login.subtitleRegister") : t("login.subtitleLogin")}</p>

        {isRegister && (
          <div className="field">
            <label>{t("login.companyName")}</label>
            <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
          </div>
        )}
        <div className="field">
          <label>{t("login.email")}</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label>{t("login.password")}</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>

        <button className="btn-primary" type="submit" style={{ marginTop: 22, width: "100%" }}>
          {isRegister ? t("login.submitRegister") : t("login.submitLogin")}
        </button>

        {error && <div className="error-msg">{error}</div>}

        <button type="button" className="link-btn"
                onClick={() => setIsRegister(!isRegister)}>
          {isRegister ? t("login.toggleToLogin") : t("login.toggleToRegister")}
        </button>

        <div style={{ marginTop: 26, paddingTop: 18, borderTop: "1px solid var(--line)" }}>
          <LanguageSwitcher variant="login" />
        </div>
      </form>
    </div>
  );
}
