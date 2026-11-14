import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Mic, MicOff, RefreshCw, Volume2 } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toastError } from "@/components/common/toast";
import { celebrate, type Reward } from "@/components/fun/Celebrate";
import Chitti, { Bubble } from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { get, post } from "@/lib/api";
import { canSpeak, speak, useListen } from "@/lib/voice";
import { cn } from "@/lib/utils";

interface Check { corrected: string; issues: { wrong: string; right: string; why: string }[]; vocab: { word: string; better: string }[]; tips: string[];
  words: number; fillers: number; wpm: number; score: number; coach: string; reward: Reward | null }
interface Challenges { speaking: { id: string; level: number; prompt: string }[]; pronounce: string[]; interview: string[] }

export default function English() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"speak" | "write" | "pronounce" | "interview">("speak");
  const ch = useQuery({ queryKey: ["eng-ch"], queryFn: () => get<Challenges>("/english/challenges") });
  const prog = useQuery({ queryKey: ["eng-prog"], queryFn: () => get<{ sessions: { id: number; kind: string; score: number; wpm: number; at: string }[]; average: number }>("/english/progress") });
  const [idx, setIdx] = useState(0);
  const [text, setText] = useState("");
  const startAt = useRef(0);
  const [secs, setSecs] = useState(0);
  const listen = useListen("en", (s) => { setText((x) => (x ? `${x} ${s}` : s)); setSecs((Date.now() - startAt.current) / 1000); });
  const c = ch.data;
  const currentPrompt = () => {
    if (!c) return "";
    if (tab === "speak") return c.speaking[idx % c.speaking.length].prompt;
    if (tab === "interview") return c.interview[idx % c.interview.length];
    return "";
  };
  const check = useMutation({
    mutationFn: (kind: string) => post<Check>("/english/check", { text, seconds: kind === "grammar" ? 0 : secs, kind, prompt: currentPrompt(), lang: i18n.language }),
    onSuccess: (r) => { celebrate(r.reward); qc.invalidateQueries({ queryKey: ["eng-prog"] }); }, onError: toastError,
  });
  const pron = useMutation({
    mutationFn: (heard: string) => post<{ score: number; words: { word: string; ok: boolean }[]; heard: string; reward: Reward | null }>("/english/pronounce", { target: c!.pronounce[idx % c!.pronounce.length], heard }),
    onSuccess: (r) => { celebrate(r.reward); qc.invalidateQueries({ queryKey: ["eng-prog"] }); }, onError: toastError,
  });
  const pListen = useListen("en", (s) => pron.mutate(s));
  const reset = (k: typeof tab) => { setTab(k); setText(""); setSecs(0); check.reset(); pron.reset(); };
  const r = check.data;
  const mic = (
    <Button size="lg" variant={listen.listening ? "danger" : "default"} onClick={() => { if (listen.listening) listen.stop(); else { startAt.current = Date.now(); listen.start(); } }} disabled={!listen.supported}>
      {listen.listening ? <><MicOff size={18} /> {t("eng.stop")}</> : <><Mic size={18} /> {t("eng.speak")}</>}
    </Button>
  );

  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-100 via-cyan-50 to-emerald-100 p-5 shadow-card sm:p-7 dark:from-soft dark:to-soft">
        <div className="flex flex-wrap items-center gap-4">
          <Chitti size={100} mood="wave" />
          <div className="flex-1">
            <h1 className="font-display text-3xl font-extrabold text-navy dark:text-ink">🗣️ {t("eng.title")}</h1>
            <p className="text-sm font-semibold text-navy/70 dark:text-mute">{t("eng.sub")}</p>
            <p className="mt-1 flex items-center gap-1 text-xs text-mute"><Lock size={12} /> {t("eng.private")}</p>
          </div>
          <div className="rounded-3xl bg-white/80 px-5 py-3 text-center dark:bg-card"><div className="text-xs font-bold uppercase text-mute">{t("eng.avg")}</div><div className="font-display text-3xl font-extrabold text-primary">{prog.data?.average ?? 0}</div></div>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto no-scrollbar">
        {([["speak", "🎤"], ["write", "✍️"], ["pronounce", "👄"], ["interview", "💼"]] as const).map(([k, e]) => (
          <button key={k} onClick={() => reset(k)} className={cn("shrink-0 rounded-2xl px-4 py-2 text-sm font-extrabold", tab === k ? "grad-bg text-white shadow-chunky" : "bg-card text-mute shadow-card")}>{e} {t(`eng.tab.${k}`)}</button>
        ))}
      </div>
      {!listen.supported && tab !== "write" && <p className="rounded-2xl bg-amber-50 p-3 text-sm font-semibold dark:bg-soft">{t("eng.noMic")}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          {c && (tab === "speak" || tab === "interview") && (
            <>
              <div className="mb-2 flex items-center justify-between"><span className="chip bg-soft text-primary">{tab === "speak" ? t("eng.challenge", { n: (idx % c.speaking.length) + 1 }) : t("eng.question")}</span>
                <Button variant="ghost" size="sm" onClick={() => { setIdx(idx + 1); setText(""); check.reset(); }}><RefreshCw size={14} /> {t("eng.another")}</Button></div>
              <div className="flex items-start gap-3"><Chitti size={56} float={false} /><Bubble className="flex-1 text-base">{currentPrompt()}</Bubble></div>
              <div className="mt-4 flex flex-wrap items-center gap-2">{mic}{canSpeak() && <Button variant="soft" onClick={() => speak(currentPrompt(), "en")} aria-label={t("chitti.readAloud")}><Volume2 size={16} /></Button>}
                {listen.listening && <span className="animate-pulse text-sm font-bold text-bad">● {listen.interim || t("chitti.listening")}</span>}</div>
              <Textarea className="mt-3" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("eng.orType")} />
              <Button className="mt-3 w-full" onClick={() => check.mutate(tab === "speak" ? "speaking" : "interview")} disabled={!text.trim() || check.isPending}>✨ {t("eng.feedback")}</Button>
            </>
          )}
          {tab === "write" && (
            <>
              <h3 className="font-display text-lg font-extrabold">{t("eng.writeTitle")}</h3>
              <Textarea className="mt-3" rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("eng.writeHint")} />
              <Button className="mt-3 w-full" onClick={() => check.mutate("grammar")} disabled={!text.trim() || check.isPending}>✅ {t("eng.checkGrammar")}</Button>
            </>
          )}
          {c && tab === "pronounce" && (
            <>
              <h3 className="font-display text-lg font-extrabold">{t("eng.pronTitle")}</h3>
              <div className="my-4 rounded-3xl bg-soft p-5 text-center font-display text-2xl font-extrabold leading-snug">
                {pron.data ? pron.data.words.map((w, i) => <span key={i} className={cn("mx-1", w.ok ? "text-ok" : "text-bad underline decoration-wavy")}>{w.word}</span>) : c.pronounce[idx % c.pronounce.length]}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {canSpeak() && <Button variant="soft" onClick={() => speak(c.pronounce[idx % c.pronounce.length], "en", 0.8)}><Volume2 size={16} /> {t("eng.listenFirst")}</Button>}
                <Button variant={pListen.listening ? "danger" : "default"} onClick={() => (pListen.listening ? pListen.stop() : pListen.start())} disabled={!pListen.supported}><Mic size={16} /> {t("eng.sayIt")}</Button>
                <Button variant="ghost" onClick={() => { setIdx(idx + 1); pron.reset(); }}><RefreshCw size={14} /> {t("eng.another")}</Button>
              </div>
              {pron.data && <div className="mt-4 flex items-center gap-3 animate-fade"><Chitti size={56} mood={pron.data.score > 80 ? "cheer" : "happy"} float={false} /><Bubble>{t("eng.pronScore", { n: Math.round(pron.data.score) })} <span className="text-mute">“{pron.data.heard}”</span></Bubble></div>}
            </>
          )}
        </Card>

        <Card className="p-5">
          {!r ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 py-10 text-center text-mute"><Chitti size={90} mood="think" /><p className="max-w-xs text-sm">{t("eng.waiting")}</p></div>
          ) : (
            <div className="space-y-3 animate-fade">
              <div className="flex flex-wrap gap-2">
                <span className="chip bg-primary/10 text-base text-primary">⭐ {r.score}/100</span>
                <span className="chip bg-soft">{t("eng.words", { n: r.words })}</span>
                {r.wpm > 0 && <span className="chip bg-soft">⏱️ {r.wpm} {t("eng.wpm")}</span>}
                <span className="chip bg-soft">🙊 {t("eng.fillers", { n: r.fillers })}</span>
              </div>
              <div className="rounded-2xl border-2 border-ok/40 bg-ok/5 p-3"><div className="text-xs font-extrabold uppercase text-ok">{t("eng.corrected")}</div><p className="mt-1 font-semibold">{r.corrected}</p>
                {canSpeak() && <button onClick={() => speak(r.corrected, "en")} className="mt-1 flex items-center gap-1 text-xs font-bold text-primary"><Volume2 size={13} /> {t("chitti.readAloud")}</button>}</div>
              {r.issues.map((x, i) => (
                <div key={i} className="flex flex-wrap items-start gap-2 rounded-2xl bg-soft/60 p-2.5 text-sm"><span className="font-bold text-bad line-through">{x.wrong}</span><span>→</span><span className="font-bold text-ok">{x.right}</span><span className="text-mute">· {x.why}</span></div>
              ))}
              {!!r.vocab.length && <div className="text-sm"><b>💎 {t("eng.betterWords")}</b> {r.vocab.map((v) => <span key={v.word} className="chip ml-1 bg-lav/30 text-violet-700">{v.word} → {v.better}</span>)}</div>}
              {r.tips.map((tip) => <p key={tip} className="text-sm">💡 {tip}</p>)}
              {r.coach && <div className="rounded-2xl bg-soft p-3 text-sm dark:bg-soft"><b>🤖 CHITTI:</b> <span className="whitespace-pre-wrap">{r.coach}</span></div>}
            </div>
          )}
        </Card>
      </div>

      {(prog.data?.sessions.length ?? 0) > 1 && (
        <Card className="p-5">
          <h3 className="mb-3 font-display text-lg font-extrabold">📈 {t("eng.progress")}</h3>
          <div className="h-48"><ResponsiveContainer><LineChart data={prog.data!.sessions.map((x, i) => ({ n: i + 1, score: x.score }))}>
            <XAxis dataKey="n" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 11 }} /><Tooltip /><Line type="monotone" dataKey="score" stroke="#0EA5E9" strokeWidth={3} dot={{ r: 4 }} /></LineChart></ResponsiveContainer></div>
        </Card>
      )}
    </div>
  );
}
