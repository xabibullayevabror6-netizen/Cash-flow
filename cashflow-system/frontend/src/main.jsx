import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./index.css";
import { I18nProvider } from "./i18n";

import Login from "./pages/Login";
import Layout from "./components/Layout";
import BankAccountsPage from "./pages/BankAccountsPage";
import ImportPage from "./pages/ImportPage";
import Dashboard from "./pages/Dashboard";
import ReviewPage from "./pages/ReviewPage";
import ForecastPage from "./pages/ForecastPage";
import CategoriesPage from "./pages/CategoriesPage";
import SettingsPage from "./pages/SettingsPage";

function RequireAuth({ children }) {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <I18nProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/bank-accounts" replace />} />
          <Route path="bank-accounts" element={<BankAccountsPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="forecast" element={<ForecastPage />} />
          <Route path="categories" element={<CategoriesPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </I18nProvider>
  </React.StrictMode>
);
