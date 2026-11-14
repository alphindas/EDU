import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import hi from "./locales/hi.json";
import ml from "./locales/ml.json";
import ta from "./locales/ta.json";
import te from "./locales/te.json";
import en2 from "./locales/v2/en.json";
import hi2 from "./locales/v2/hi.json";
import ml2 from "./locales/v2/ml.json";
import ta2 from "./locales/v2/ta.json";
import te2 from "./locales/v2/te.json";

export const LANGS = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "te", label: "తెలుగు", flag: "🌼" },
  { code: "hi", label: "हिन्दी", flag: "🪔" },
  { code: "ml", label: "മലയാളം", flag: "🌴" },
  { code: "ta", label: "தமிழ்", flag: "🌺" },
] as const;

type Json = Record<string, unknown>;
/** Phase 1-4 strings + EduNest 2.0 strings, deep-merged (2.0 wins on overlap). Missing keys fall back to English. */
function merge(a: Json, b: Json): Json {
  const out: Json = { ...a };
  for (const [k, v] of Object.entries(b)) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && typeof a[k] === "object" ? merge(a[k] as Json, v as Json) : v;
  }
  return out;
}

const saved = (() => { try { return localStorage.getItem("edunest-lang"); } catch { return null; } })();

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: merge(en, en2) }, te: { translation: merge(te, te2) }, hi: { translation: merge(hi, hi2) },
    ml: { translation: merge(ml, ml2) }, ta: { translation: merge(ta, ta2) },
  },
  lng: saved ?? "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", (l) => {
  try { localStorage.setItem("edunest-lang", l); } catch { /* ignore */ }
  document.documentElement.lang = l;
});
document.documentElement.lang = i18n.language;

export default i18n;
