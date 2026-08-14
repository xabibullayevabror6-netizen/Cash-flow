import { createContext, useContext, useEffect, useMemo, useState } from "react";

import uz from "./locales/uz";
import uzCyrl from "./locales/uz_cyrl";
import ru from "./locales/ru";
import en from "./locales/en";

export const LANGUAGES = [
  { code: "uz", label: "O'zbekcha", short: "UZ" },
  { code: "uz-Cyrl", label: "Ўзбекча", short: "ЎЗ" },
  { code: "ru", label: "Русский", short: "RU" },
  { code: "en", label: "English", short: "EN" },
];

const DICTS = { uz, "uz-Cyrl": uzCyrl, ru, en };
const STORAGE_KEY = "lang";
const DEFAULT_LANG = "uz";

function detectInitial() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && DICTS[saved]) return saved;

  const nav = (navigator.language || "").toLowerCase();
  if (nav.startsWith("ru")) return "ru";
  if (nav.startsWith("en")) return "en";
  return DEFAULT_LANG;
}

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(detectInitial);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo(() => {
    const dict = DICTS[lang] || DICTS[DEFAULT_LANG];

    /**
     * t("kalit") yoki o'rin almashtirish bilan: t("kalit", { n: 5 })
     * Kalit topilmasa — o'zbekchaga, u ham bo'lmasa kalitning o'ziga qaytadi,
     * shunda sahifa bo'sh qolmaydi va yetishmayotgan tarjima ko'zga tashlanadi.
     */
    function t(key, vars) {
      let text = dict[key] ?? DICTS[DEFAULT_LANG][key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          text = text.replaceAll(`{${k}}`, String(v));
        }
      }
      return text;
    }

    return { lang, setLang, t };
  }, [lang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n I18nProvider ichida chaqirilishi kerak");
  return ctx;
}

/** Raqam formati tilga bog'liq: ru/uz-Cyrl uchun bo'shliq, en uchun vergul. */
export function formatNumber(n, lang) {
  const locale = lang === "en" ? "en-US" : "ru-RU";
  return Math.round(Math.abs(n)).toLocaleString(locale).replace(/ /g, " ");
}
