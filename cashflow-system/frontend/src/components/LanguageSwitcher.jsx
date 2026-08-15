import { LANGUAGES, useI18n } from "../i18n";

export default function LanguageSwitcher({ variant = "sidebar" }) {
  const { lang, setLang } = useI18n();

  return (
    <div className={`lang-switch ${variant}`}>
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          type="button"
          className={l.code === lang ? "active" : ""}
          onClick={() => setLang(l.code)}
          title={l.label}
          aria-label={l.label}
          aria-pressed={l.code === lang}
        >
          {l.short}
        </button>
      ))}
    </div>
  );
}
