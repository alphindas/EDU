import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import hi from "./locales/hi.json";
import te from "./locales/te.json";

export const LANGS = [
  { code: "en", label: "English" },
  { code: "te", label: "తెలుగు" },
  { code: "hi", label: "हिन्दी" },
] as const;

const saved = (() => { try { return localStorage.getItem("edunest-lang"); } catch { return null; } })();

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, te: { translation: te }, hi: { translation: hi } },
  lng: saved ?? "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (l) => {
  try { localStorage.setItem("edunest-lang", l); } catch { /* ignore */ }
  document.documentElement.lang = l;
});

export default i18n;
