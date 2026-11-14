import { Keyboard, Mic, PhoneOff, Send, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { celebrate } from "@/components/fun/Celebrate";
import Chitti from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LANGS } from "@/i18n";
import { upload } from "@/lib/api";
import type { AskOut } from "@/lib/v2";
import { canListen, canSpeak, listenOnce, speakAsync, spokenText, stopSpeaking } from "@/lib/voice";
import { cn } from "@/lib/utils";

type Phase = "idle" | "listening" | "thinking" | "speaking";
interface Turn { who: "you" | "chitti"; text: string }

/** "Talk with CHITTI": a hands-free voice conversation, like a phone call.
 *  Loop: listen -> send to /chitti/ask (voice=1 asks for short spoken answers) -> speak the reply -> listen again.
 *  Tap CHITTI (or Stop) while it speaks to interrupt and talk. Uses the browser's Web Speech API (Chrome / Edge). */
export default function TalkTab({ modes, lang }: { modes: string[]; lang: string }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState(modes[0] ?? "study_buddy");
  const [phase, setPhase] = useState<Phase>("idle");
  const [active, setActive] = useState(false);
  const [heard, setHeard] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [note, setNote] = useState<string>("");
  const [rate, setRate] = useState(1);
  const [typed, setTyped] = useState("");
  const [showType, setShowType] = useState(!canListen());
  const activeRef = useRef(false);
  const cidRef = useRef<number | null>(null);
  const stopListen = useRef<() => void>(() => {});
  const endRef = useRef<HTMLDivElement>(null);
  const rateRef = useRef(rate);
  rateRef.current = rate;

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, heard]);
  useEffect(() => () => { activeRef.current = false; stopListen.current(); stopSpeaking(); }, []);
  useEffect(() => { cidRef.current = null; }, [mode]);

  const askChitti = async (q: string): Promise<string> => {
    const fd = new FormData();
    fd.append("text", q); fd.append("mode", mode); fd.append("lang", lang); fd.append("voice", "true");
    if (cidRef.current) fd.append("conversation_id", String(cidRef.current));
    try {
      const r = await upload<AskOut>("POST", "/chitti/ask", fd);
      cidRef.current = r.conversation_id;
      celebrate(r.reward);
      return r.reply;
    } catch {
      return t("talk.error");
    }
  };

  const reply = async (q: string) => {
    setTurns((x) => [...x, { who: "you", text: q }]);
    setPhase("thinking");
    const answer = await askChitti(q);
    setTurns((x) => [...x, { who: "chitti", text: answer }]);
    setPhase("speaking");
    await speakAsync(spokenText(answer, 500), lang, { rate: rateRef.current });
  };

  const loop = async () => {
    let misses = 0;
    while (activeRef.current) {
      setPhase("listening"); setHeard("");
      const l = listenOnce(lang, setHeard);
      stopListen.current = l.stop;
      let said = "";
      try { said = await l.result; } catch {
        setNote(t("talk.micBlocked")); end(); return;
      }
      if (!activeRef.current) return;
      setHeard("");
      if (!said) {
        misses += 1;
        if (misses >= 3) { setNote(t("talk.noHear")); end(); return; }
        continue;
      }
      misses = 0;
      await reply(said);
    }
    setPhase("idle");
  };

  const start = () => {
    if (activeRef.current) return;
    setNote("");
    activeRef.current = true;
    setActive(true);
    void loop();
  };
  const end = () => {
    activeRef.current = false;
    setActive(false);
    stopListen.current();
    stopSpeaking();
    setPhase("idle");
    setHeard("");
  };
  /** Tap CHITTI: interrupt speech (the loop then listens), or start the call. */
  const tapChitti = () => {
    if (phase === "speaking") stopSpeaking();
    else if (!active && canListen()) start();
  };
  const sendTyped = async () => {
    const q = typed.trim();
    if (!q || phase === "thinking") return;
    setTyped("");
    stopSpeaking();
    await reply(q);
    setPhase(activeRef.current ? "listening" : "idle");
  };

  const langName = LANGS.find((l) => l.code === lang)?.label ?? lang;
  const status = phase === "listening" ? t("talk.listening") : phase === "thinking" ? t("talk.thinking")
    : phase === "speaking" ? t("talk.speaking") : t("talk.idle");
  const last = [...turns].reverse().find((x) => x.who === "chitti");

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <Card className="flex flex-col items-center p-6 text-center sm:p-8">
        <div className="flex w-full flex-wrap items-center justify-between gap-2 text-left">
          <div>
            <h2 className="font-display text-xl font-bold">{t("talk.title")}</h2>
            <p className="text-sm text-mute">{t("talk.sub")}</p>
          </div>
          <select value={mode} onChange={(e) => setMode(e.target.value)} disabled={active}
            className="h-9 rounded-xl border border-line bg-card px-2 text-sm" aria-label={t("talk.mode")}>
            {modes.map((m) => <option key={m} value={m}>{t(`chitti.mode.${m}`)}</option>)}
          </select>
        </div>

        <button type="button" onClick={tapChitti} className="mt-6 rounded-[30%] focus-visible:ring-4" aria-label={phase === "speaking" ? t("talk.interrupt") : t("talk.start")}>
          <Chitti size={190} float={phase === "idle"} speaking={phase === "speaking"} listening={phase === "listening"}
            mood={phase === "thinking" ? "think" : phase === "idle" ? "wave" : "happy"} />
        </button>

        <div className="mt-5 min-h-[1.5rem] text-sm font-semibold text-primary" aria-live="polite">{status}</div>
        <div className="mt-2 min-h-[3.5rem] max-w-xl text-base">
          {phase === "listening" && heard ? <span className="text-ink">“{heard}”</span>
            : last ? <span className="text-mute">{spokenText(last.text, 260)}</span> : null}
        </div>

        {/* simple sound bars while listening/speaking */}
        <div className="mt-1 flex h-6 items-end gap-1" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className={cn("w-1.5 rounded-full bg-primary/60 transition-all",
              phase === "listening" || phase === "speaking" ? "animate-talk" : "")}
              style={{ height: phase === "listening" || phase === "speaking" ? `${8 + ((i * 7) % 16)}px` : "4px", animationDelay: `${i * 0.12}s` }} />
          ))}
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {canListen() && (!active ? (
            <Button size="lg" onClick={start} className="rounded-full px-7"><Mic size={18} /> {t("talk.start")}</Button>
          ) : (
            <>
              {phase === "speaking" && <Button variant="outline" size="lg" className="rounded-full" onClick={() => stopSpeaking()}><Square size={16} /> {t("talk.stop")}</Button>}
              <Button variant="danger" size="lg" className="rounded-full px-7" onClick={end}><PhoneOff size={18} /> {t("talk.end")}</Button>
            </>
          ))}
          <Button variant="ghost" size="lg" className="rounded-full" onClick={() => setShowType((s) => !s)} aria-pressed={showType}><Keyboard size={18} /> {t("talk.type")}</Button>
        </div>

        {showType && (
          <form className="mt-4 flex w-full max-w-lg gap-2" onSubmit={(e) => { e.preventDefault(); void sendTyped(); }}>
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={t("talk.typeHere")} />
            <Button type="submit" disabled={!typed.trim() || phase === "thinking"} aria-label={t("common.send")}><Send size={18} /></Button>
          </form>
        )}

        {note && <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-soft dark:text-ink">{note}</p>}
        {!canListen() && <p className="mt-4 text-sm text-mute">{t("talk.unsupported")}</p>}
        {!canSpeak() && <p className="mt-2 text-sm text-mute">{t("talk.noSpeaker")}</p>}

        <div className="mt-6 flex w-full flex-wrap items-center justify-center gap-4 text-xs text-mute">
          <span className="chip bg-soft text-primary">🗣️ {langName}</span>
          <label className="flex items-center gap-2">{t("talk.speed")}
            <input type="range" min={0.7} max={1.3} step={0.1} value={rate} onChange={(e) => setRate(Number(e.target.value))} className="accent-[hsl(var(--ac))]" />
            <span className="w-8 tabular-nums">{rate.toFixed(1)}×</span>
          </label>
        </div>
        <p className="mt-3 max-w-md text-[11px] text-mute">{t("talk.tip", { lang: langName })}</p>
      </Card>

      <Card className="flex max-h-[75vh] flex-col p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-bold">{t("talk.transcript")}</h3>
          {!!turns.length && <button onClick={() => { setTurns([]); cidRef.current = null; }} className="flex items-center gap-1 text-xs text-mute hover:text-bad"><Trash2 size={13} /> {t("talk.clear")}</button>}
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto pr-1 text-sm">
          {!turns.length && <p className="py-8 text-center text-mute">{t("talk.empty")}</p>}
          {turns.map((x, i) => x.who === "you" ? (
            <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-white">{x.text}</div></div>
          ) : (
            <div key={i} className="flex items-start gap-2">
              <Chitti size={30} float={false} />
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tl-sm border border-line bg-card px-3 py-2">{x.text}</div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </Card>
    </div>
  );
}
