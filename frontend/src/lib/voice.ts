/** Browser speech: recognition (STT) + synthesis (TTS) via the Web Speech API. Works in Chrome/Edge (incl. Android);
 * Telugu/Hindi/Tamil/Malayalam availability depends on the device's installed voices. No audio leaves the browser
 * except through the browser's own speech service. */
import { useCallback, useEffect, useRef, useState } from "react";

export const SPEECH_LANG: Record<string, string> = { en: "en-IN", te: "te-IN", hi: "hi-IN", ml: "ml-IN", ta: "ta-IN" };

type Rec = { lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void; abort(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null };

function recCtor(): (new () => Rec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const canListen = () => typeof window !== "undefined" && !!recCtor();
export const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;

export function useListen(lang: string, onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [started, setStarted] = useState(0);
  const rec = useRef<Rec | null>(null);
  const cb = useRef(onFinal);
  cb.current = onFinal;
  const stop = useCallback(() => { rec.current?.stop(); }, []);
  const start = useCallback(() => {
    const C = recCtor();
    if (!C) return;
    rec.current?.abort();
    const r = new C();
    r.lang = SPEECH_LANG[lang] ?? "en-IN";
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => {
      let fin = "", mid = "";
      for (let i = 0; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) fin += res[0].transcript; else mid += res[0].transcript;
      }
      setInterim(mid);
      if (fin) cb.current(fin.trim());
    };
    r.onend = () => { setListening(false); setInterim(""); };
    r.onerror = () => { setListening(false); };
    rec.current = r;
    setStarted(Date.now());
    setListening(true);
    r.start();
  }, [lang]);
  useEffect(() => () => rec.current?.abort(), []);
  return { listening, interim, start, stop, started, supported: canListen() };
}

/** Text cleaned for speaking: no markdown, spoilers, emoji or links. */
export function spokenText(text: string, maxChars = 0) {
  let t = text
    .replace(/\|\|.*?\|\|/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*_#>`|•]/g, "")
    .replace(/\p{Extended_Pictographic}|\uFE0F|\u200D/gu, "")
    .replace(/\s*\n+\s*/g, ". ")
    .replace(/\.\s*\./g, ".")
    .trim();
  if (maxChars && t.length > maxChars) {
    const cut = t.slice(0, maxChars);
    const end = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("? "), cut.lastIndexOf("! "), cut.lastIndexOf("। "));
    t = end > 40 ? cut.slice(0, end + 1) : cut;
  }
  return t;
}

let voicesReady: Promise<SpeechSynthesisVoice[]> | null = null;
function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!canSpeak()) return Promise.resolve([]);
  const now = window.speechSynthesis.getVoices();
  if (now.length) return Promise.resolve(now);
  voicesReady ??= new Promise((res) => {
    const done = () => res(window.speechSynthesis.getVoices());
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 1200);
  });
  return voicesReady;
}

function pickVoice(voices: SpeechSynthesisVoice[], tag: string) {
  const exact = voices.filter((v) => v.lang?.toLowerCase().replace("_", "-") === tag.toLowerCase());
  const base = voices.filter((v) => v.lang?.toLowerCase().startsWith(tag.slice(0, 2)));
  const pool = exact.length ? exact : base;
  return pool.find((v) => /google|natural|neural/i.test(v.name)) ?? pool[0];
}

/** Speak and resolve when finished (or stopped). Long text is split into sentences, which avoids Chrome's
 *  15-second cut-off and lets the talk mode stop speaking instantly when the user interrupts. */
export async function speakAsync(text: string, lang: string, opts: { rate?: number; pitch?: number; onStart?: () => void } = {}) {
  if (!canSpeak()) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const clean = spokenText(text);
  if (!clean) return;
  const tag = SPEECH_LANG[lang] ?? "en-IN";
  const voice = pickVoice(await loadVoices(), tag);
  const parts = clean.match(/[^.!?।]+[.!?।]*/g)?.map((x) => x.trim()).filter(Boolean) ?? [clean];
  opts.onStart?.();
  await new Promise<void>((resolve) => {
    let left = parts.length;
    parts.forEach((p) => {
      const u = new SpeechSynthesisUtterance(p);
      u.lang = tag;
      if (voice) u.voice = voice;
      u.rate = opts.rate ?? 1;
      u.pitch = opts.pitch ?? 1.1;
      const done = () => { left -= 1; if (left <= 0 || !synth.speaking) resolve(); };
      u.onend = done;
      u.onerror = done;
      synth.speak(u);
    });
    // safety net: never hang the conversation if the browser drops events
    setTimeout(resolve, Math.min(60000, 4000 + clean.length * 90));
  });
}

export function speak(text: string, lang: string, rate = 0.95) {
  void speakAsync(text, lang, { rate });
}

/** Listen for one sentence. Resolves with the final text ("" if nothing was heard). Rejects with "not-allowed"
 *  when the microphone is blocked. Call the returned stop() to cancel. */
export function listenOnce(lang: string, onInterim?: (t: string) => void): { result: Promise<string>; stop: () => void } {
  const C = recCtor();
  if (!C) return { result: Promise.reject(new Error("unsupported")), stop: () => {} };
  const r = new C();
  r.lang = SPEECH_LANG[lang] ?? "en-IN";
  r.interimResults = true;
  r.continuous = false;
  let finalText = "";
  const result = new Promise<string>((resolve, reject) => {
    r.onresult = (e) => {
      let fin = "", mid = "";
      for (let i = 0; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) fin += res[0].transcript; else mid += res[0].transcript;
      }
      if (fin) finalText = fin.trim();
      onInterim?.(fin || mid);
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") reject(new Error("not-allowed"));
    };
    r.onend = () => resolve(finalText);
  });
  try { r.start(); } catch { /* already started */ }
  return { result, stop: () => { try { r.abort(); } catch { /* ignore */ } } };
}

export const stopSpeaking = () => canSpeak() && window.speechSynthesis.cancel();
