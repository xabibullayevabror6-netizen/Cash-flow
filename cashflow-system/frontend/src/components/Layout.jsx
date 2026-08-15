import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useI18n } from "../i18n";
import LanguageSwitcher from "./LanguageSwitcher";

export default function Layout() {
  const navigate = useNavigate();
  const { t } = useI18n();

  function logout() {
    localStorage.removeItem("token");
    navigate("/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">₽</div>
          <div className="name">{t("brand.name")}</div>
          <div className="sub">{t("brand.sub")}</div>
        </div>
        <nav className="nav">
          <NavLink to="/bank-accounts" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">01</span> {t("nav.bankAccounts")}
          </NavLink>
          <NavLink to="/import" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">02</span> {t("nav.import")}
          </NavLink>
          <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">03</span> {t("nav.dashboard")}
          </NavLink>
          <NavLink to="/review" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">04</span> {t("nav.review")}
          </NavLink>
          <NavLink to="/forecast" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">05</span> {t("nav.forecast")}
          </NavLink>
          <NavLink to="/categories" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">06</span> {t("nav.categories")}
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
            <span className="n">07</span> {t("nav.settings")}
          </NavLink>
        </nav>
        <div style={{ marginTop: "auto" }}>
          <div className="lang-label">{t("nav.language")}</div>
          <LanguageSwitcher />
          {/* <button>, <p> emas — klaviatura bilan yetib borish va
              ekran o'quvchi uchun to'g'ri semantika kerak */}
          <button type="button" onClick={logout} className="logout">
            {t("nav.logout")}
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
