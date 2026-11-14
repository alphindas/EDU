import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, ExternalLink, ImagePlus, Lightbulb, Loader2, Mic, MicOff, Paperclip, Plus, Search, Send, Trash2, Volume2, VolumeX, PlayCircle } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toastError } from "@/components/common/toast";
import { celebrate } from "@/components/fun/Celebrate";
import Chitti, { Bubble } from "@/components/fun/Chitti";
import PracticeQuiz from "@/components/fun/PracticeQuiz";
import TalkTab from "@/pages/shared/ChittiTalk";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { del, get, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AskOut, ChittiStatus, PracticeQ, SolveOut, Source, TopicOut } from "@/lib/v2";
import { canSpeak, speak, stopSpeaking, useListen } from "@/lib/voice";
import { cn } from "@/lib/utils";

const MODE_EMOJI: Record<string, string> = { study_buddy: "📘", doubt_solver: "🧮", english: "🗣️", aptitude: "⚡", puzzle: "🧩", career: "🧭", parent: "👨‍👩‍👧", lesson_plan: "🗂️" };
interface Msg { role: "user" | "assistant"; content: string; sources?: Source[]; provider?: string; pending?: boolean }

/** Tiny safe renderer: **bold**, bullets, ||spoiler|| (no HTML injection: React escapes text). */
function Rich({ text }: { text: string }) {
  return (
    <div className="prose-chat whitespace-pre-wrap break-words">
      {text.split("\n").map((line, i) => {
        const parts: ReactNode[] = [];
        line.split(/(\*\*[^*]+\*\*|\|\|[^|]+\|\|)/g).forEach((p, j) => {
          if (p.startsWith("**") && p.endsWith("**")) parts.push(<b key={j}>{p.slice(2, -2)}</b>);
          else if (p.startsWith("||") && p.endsWith("||")) parts.push(<span key={j} className="spoiler" tabIndex={0}>{p.slice(2, -2)}</span>);
          else parts.push(p);
        });
        return <div key={i} className={line.trim() ? "" : "h-2"}>{parts}</div>;
      })}
    </div>
  );
}

export default function ChittiPage() {
  const { t, i18n } = useTranslation();
  const role = useAuth((s) => s.user?.role) ?? "student";
  const status = useQuery({ queryKey: ["chitti-status"], queryFn: () => get<ChittiStatus>("/chitti/status") });
  const [tab, setTab] = useState<"chat" | "talk" | "topic" | "photo">("chat");
  const canPhoto = role === "student" || role === "teacher";
  const st = status.data;

  if (st && !st.consent) {
    return (
      <Card className="mx-auto mt-6 max-w-lg p-8 text-center">
        <Chitti size={130} mood="sleepy" />
        <h1 className="mt-3 font-display text-2xl font-extrabold">{t("chitti.consentTitle")}</h1>
        <p className="mt-2 text-mute">{t("chitti.consentBody")}</p>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Chitti size={64} mood="wave" float={false} />
        <div className="mr-auto">
          <h1 className="font-display text-3xl font-bold leading-none">CHITTI</h1>
          <p className="text-sm font-semibold text-mute">{role === "parent" ? t("chitti.parentSub") : role === "teacher" ? t("chitti.teacherSub") : t("chitti.sub")}</p>
        </div>
        <Button variant="soft" onClick={() => setTab("talk")} className="rounded-full"><Mic size={16} /> {t("talk.start")}</Button>
        {st && <span className={cn("chip", st.online ? "bg-ok/15 text-ok" : "bg-amber-100 text-amber-700")}>{st.online ? `● ${t("chitti.online", { p: st.provider })}` : `● ${t("chitti.offline")}`}</span>}
      </div>
      <div className="flex gap-2 overflow-x-auto no-scrollbar">
        {([["chat", "💬", "chitti.tabChat"], ["talk", "🎙️", "chitti.tabTalk"], ["topic", "🔭", "chitti.tabTopic"], ...(canPhoto ? [["photo", "📸", "chitti.tabPhoto"]] : [])] as [typeof tab, string, string][]).map(([k, e, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("shrink-0 rounded-xl px-4 py-2 text-sm font-semibold transition", tab === k ? "bg-primary text-white shadow-sm" : "bg-card text-mute shadow-card hover:text-ink")}>{e} {t(l)}</button>
        ))}
      </div>
      {tab === "chat" && st && <ChatTab modes={st.modes} lang={i18n.language} />}
      {tab === "talk" && st && <TalkTab modes={st.modes} lang={i18n.language} />}
      {tab === "topic" && <TopicTab lang={i18n.language} />}
      {tab === "photo" && <PhotoTab lang={i18n.language} />}
    </div>
  );
}

function ChatTab({ modes, lang }: { modes: string[]; lang: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [mode, setMode] = useState(modes[0] ?? "study_buddy");
  const [cid, setCid] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [autoRead, setAutoRead] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const convs = useQuery({ queryKey: ["chitti-convs"], queryFn: () => get<{ id: number; title: string }[]>("/chitti/conversations") });
  const listen = useListen(lang, (s) => setText((x) => (x ? `${x} ${s}` : s)));
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);

  const load = async (id: number) => {
    const c = await get<{ messages: Msg[] }>(`/chitti/conversations/${id}`);
    setCid(id); setMsgs(c.messages);
  };
  const ask = useMutation({
    mutationFn: (q: string) => {
      const fd = new FormData();
      fd.append("text", q); fd.append("mode", mode); fd.append("lang", lang);
      if (cid) fd.append("conversation_id", String(cid));
      if (file) fd.append("file", file);
      return upload<AskOut>("POST", "/chitti/ask", fd);
    },
    onMutate: (q) => setMsgs((m) => [...m, { role: "user", content: q + (file ? `\n📎 ${file.name}` : "") }, { role: "assistant", content: "", pending: true }]),
    onSuccess: (r) => {
      setCid(r.conversation_id);
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "assistant", content: r.reply, sources: r.sources, provider: r.provider }]);
      setFile(null);
      celebrate(r.reward);
      if (autoRead) speak(r.reply, lang);
      qc.invalidateQueries({ queryKey: ["chitti-convs"] });
    },
    onError: (e) => { setMsgs((m) => m.filter((x) => !x.pending)); toastError(e); },
  });
  const send = () => { const q = text.trim(); if (!q || ask.isPending) return; setText(""); ask.mutate(q); };
  const removeConv = useMutation({ mutationFn: (id: number) => del(`/chitti/conversations/${id}`), onSuccess: () => { setCid(null); setMsgs([]); qc.invalidateQueries({ queryKey: ["chitti-convs"] }); } });
  const starters = t(`chitti.starters.${mode}`, { returnObjects: true }) as string[];

  return (
    <div className="grid gap-4 lg:grid-cols-[230px_1fr]">
      <Card className="hidden h-fit p-3 lg:block">
        <Button className="w-full" onClick={() => { setCid(null); setMsgs([]); }}><Plus size={16} /> {t("chitti.newChat")}</Button>
        <div className="mt-3 text-[11px] font-extrabold uppercase tracking-wider text-mute">{t("chitti.history")}</div>
        <ul className="mt-1 max-h-[55vh] space-y-1 overflow-y-auto">
          {(convs.data ?? []).map((c) => (
            <li key={c.id} className={cn("group flex items-center rounded-xl", cid === c.id ? "bg-soft" : "hover:bg-soft/60")}>
              <button onClick={() => load(c.id)} className="min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm font-semibold">{c.title || "…"}</button>
              <button onClick={() => removeConv.mutate(c.id)} className="p-1 text-mute opacity-0 hover:text-bad group-hover:opacity-100" aria-label={t("common.delete")}><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
      </Card>
      <Card className="flex min-h-[65vh] flex-col overflow-hidden">
        <div className="flex gap-1.5 overflow-x-auto border-b-2 border-line p-2 no-scrollbar">
          {modes.map((m) => (
            <button key={m} onClick={() => setMode(m)} className={cn("shrink-0 rounded-xl px-3 py-1.5 text-sm font-bold", mode === m ? "bg-soft text-primary ring-2 ring-primary/30" : "text-mute hover:bg-soft/60")}>
              {MODE_EMOJI[m]} {t(`chitti.mode.${m}`)}
            </button>
          ))}
          {canSpeak() && (
            <button onClick={() => { setAutoRead(!autoRead); stopSpeaking(); }} className={cn("ml-auto shrink-0 rounded-xl px-2 text-mute", autoRead && "text-primary")} title={t("chitti.autoRead")} aria-pressed={autoRead}>
              {autoRead ? <Volume2 size={18} /> : <VolumeX size={18} />}
            </button>
          )}
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
          {msgs.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <Chitti size={110} mood="happy" />
              <Bubble className="max-w-md">{t(`chitti.hello.${mode}`)}</Bubble>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {Array.isArray(starters) && starters.map((s) => (
                  <button key={s} onClick={() => ask.mutate(s)} className="rounded-full border border-line bg-card px-3 py-1.5 text-sm hover:border-primary hover:bg-soft">{s}</button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => m.role === "user" ? (
            <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-white shadow-card"><Rich text={m.content} /></div></div>
          ) : (
            <div key={i} className="flex items-start gap-2">
              <Chitti size={36} float={false} mood={m.pending ? "think" : "happy"} className="mt-1" />
              <div className="max-w-[88%] rounded-2xl rounded-tl-sm border border-line bg-card px-4 py-3 text-sm">
                {m.pending ? <span className="flex items-center gap-2 text-mute"><Loader2 className="animate-spin" size={16} /> {t("chitti.thinking")}</span> : <Rich text={m.content} />}
                {!!m.sources?.length && (
                  <div className="mt-2 flex flex-wrap gap-1.5 border-t border-line pt-2">
                    {m.sources.map((s, k) => <span key={k} className="chip bg-soft text-primary" title={s.snippet}>📘 {s.name.slice(0, 48)}</span>)}
                  </div>
                )}
                {!m.pending && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-mute">
                    {canSpeak() && <button onClick={() => speak(m.content, lang)} className="flex items-center gap-1 rounded-lg px-1.5 py-0.5 font-bold hover:bg-soft" aria-label={t("chitti.readAloud")}><Volume2 size={14} /> {t("chitti.readAloud")}</button>}
                    {m.provider === "stub" && <span className="chip bg-amber-50 text-amber-700">{t("chitti.offlineTag")}</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <div className="border-t-2 border-line p-3">
          {file && <div className="mb-2 flex items-center gap-2 text-xs font-bold"><span className="chip bg-soft text-primary">📎 {file.name}</span><button onClick={() => setFile(null)} className="text-bad">✕</button></div>}
          {listen.listening && <div className="mb-2 text-sm font-semibold text-primary">🎙️ {listen.interim || t("chitti.listening")}</div>}
          <div className="flex items-end gap-2">
            <input ref={fileRef} type="file" hidden accept="image/*,application/pdf,text/plain" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <Button variant="outline" size="icon" onClick={() => fileRef.current?.click()} aria-label={t("chitti.attach")} title={t("chitti.attach")}><Paperclip size={18} /></Button>
            {listen.supported && (
              <Button variant={listen.listening ? "danger" : "outline"} size="icon" onClick={() => (listen.listening ? listen.stop() : listen.start())} aria-label={t("chitti.voice")} title={t("chitti.voice")}>
                {listen.listening ? <MicOff size={18} /> : <Mic size={18} />}
              </Button>
            )}
            <Textarea rows={1} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("chitti.placeholder")} className="min-h-[2.75rem] flex-1 resize-none"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <Button onClick={send} disabled={!text.trim() || ask.isPending} aria-label={t("common.send")}><Send size={18} /></Button>
          </div>
          <p className="mt-1.5 text-[11px] text-mute">{t("chitti.safety")}</p>
        </div>
      </Card>
    </div>
  );
}

function TopicTab({ lang }: { lang: string }) {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [practice, setPractice] = useState(false);
  const topic = useMutation({ mutationFn: (s: string) => get<TopicOut>(`/chitti/topic?q=${encodeURIComponent(s)}&lang=${lang}`), onSuccess: (r) => { setPractice(false); celebrate(r.reward); }, onError: toastError });
  const d = topic.data;
  const ideas = t("chitti.topicIdeas", { returnObjects: true }) as string[];
  return (
    <div className="space-y-4">
      <Card className="p-4">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 1) topic.mutate(q.trim()); }}>
          <div className="relative flex-1"><Search className="absolute left-3 top-3.5 text-mute" size={18} /><Input value={q} onChange={(e) => setQ(e.target.value)} className="pl-10" placeholder={t("chitti.topicPlaceholder")} /></div>
          <Button type="submit" disabled={topic.isPending}>{topic.isPending ? <Loader2 className="animate-spin" size={18} /> : t("chitti.explore")}</Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {Array.isArray(ideas) && ideas.map((s) => <button key={s} onClick={() => { setQ(s); topic.mutate(s); }} className="chip bg-soft py-1 text-primary hover:brightness-95">{s}</button>)}
        </div>
      </Card>
      {d && (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <Card className="p-5">
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-display text-2xl font-extrabold">{d.title}</h2>
              {canSpeak() && <Button variant="soft" size="sm" onClick={() => speak(`${d.title}. ${d.explanation} ${d.example}`, lang)}><Volume2 size={16} /> {t("chitti.readAloud")}</Button>}
            </div>
            <p className="mt-2 leading-relaxed">{d.explanation}</p>
            {d.example && <div className="mt-3 flex gap-2 rounded-2xl bg-amber-50 p-3 text-sm dark:bg-soft"><Lightbulb className="shrink-0 text-amber-500" size={18} /><span><b>{t("chitti.example")}</b> {d.example}</span></div>}
            {!!d.points.length && <ul className="mt-3 space-y-1.5">{d.points.map((p) => <li key={p} className="flex gap-2 text-sm"><span className="text-primary">★</span>{p}</li>)}</ul>}
            {!!d.sources.length && <div className="mt-3 flex flex-wrap gap-1.5">{d.sources.map((s, i) => <span key={i} className="chip bg-soft text-primary" title={s.snippet}>📘 {s.name.slice(0, 50)}</span>)}</div>}
            <div className="mt-5">
              {!practice ? <Button variant="sun" onClick={() => setPractice(true)} disabled={!d.practice.length}>🎯 {t("chitti.practiceN", { n: d.practice.length })}</Button>
                : <PracticeQuiz questions={d.practice} />}
            </div>
          </Card>
          <Card className="h-fit p-5">
            <h3 className="mb-3 flex items-center gap-2 font-display text-lg font-extrabold"><PlayCircle className="text-red-500" size={20} /> {t("chitti.videos")}</h3>
            <ul className="space-y-2">
              {d.videos.map((v) => (
                <li key={v.url}><a href={v.url} target="_blank" rel="noreferrer noopener" className="flex items-center gap-2 rounded-2xl border-2 border-line p-2.5 text-sm font-bold hover:border-red-300 hover:bg-red-50 dark:hover:bg-soft">
                  <span className="grid h-9 w-12 place-items-center rounded-lg bg-red-500 text-white">▶</span><span className="flex-1">{v.title}</span><ExternalLink size={14} className="text-mute" /></a></li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-mute">{t("chitti.videoNote")}</p>
          </Card>
        </div>
      )}
    </div>
  );
}

function PhotoTab({ lang }: { lang: string }) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [practice, setPractice] = useState<PracticeQ[] | null>(null);
  const camRef = useRef<HTMLInputElement>(null);
  const galRef = useRef<HTMLInputElement>(null);
  const pick = (f: File | null) => { setFile(f); setPreview(f ? URL.createObjectURL(f) : null); };
  const solve = useMutation({
    mutationFn: () => { const fd = new FormData(); fd.append("text", text); fd.append("lang", lang); if (file) fd.append("file", file); return upload<SolveOut>("POST", "/chitti/photo-doubt", fd); },
    onSuccess: (r) => { setPractice(null); celebrate(r.reward); if (r.ocr_text && !text) setText(r.ocr_text); },
    onError: toastError,
  });
  const sim = useMutation({ mutationFn: (topic: string) => get<{ questions: PracticeQ[] }>(`/chitti/practice-similar?topic=${encodeURIComponent(topic)}&text=${encodeURIComponent(text)}`), onSuccess: (r) => setPractice(r.questions), onError: toastError });
  const r = solve.data;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <h2 className="font-display text-xl font-extrabold">📸 {t("photo.title")}</h2>
        <p className="text-sm text-mute">{t("photo.sub")}</p>
        <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        <input ref={galRef} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        <div className="mt-4 grid grid-cols-2 gap-2">
          <Button variant="outline" size="lg" onClick={() => camRef.current?.click()}><Camera size={18} /> {t("photo.camera")}</Button>
          <Button variant="outline" size="lg" onClick={() => galRef.current?.click()}><ImagePlus size={18} /> {t("photo.gallery")}</Button>
        </div>
        {preview && <img src={preview} alt="" className="mt-3 max-h-60 w-full rounded-2xl border-2 border-line object-contain" />}
        <Textarea className="mt-3" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("photo.typeHint")} />
        <Button className="mt-3 w-full" size="lg" onClick={() => solve.mutate()} disabled={solve.isPending || (!file && !text.trim())}>
          {solve.isPending ? <><Loader2 className="animate-spin" size={18} /> {t("photo.reading")}</> : <>✨ {t("photo.solve")}</>}
        </Button>
      </Card>
      <Card className="p-5">
        {!r ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 py-8 text-center"><Chitti size={110} mood="think" /><p className="max-w-xs text-sm text-mute">{t("photo.empty")}</p></div>
        ) : (
          <div className="space-y-3">
            {r.ocr_text && <div className="rounded-2xl bg-soft/60 p-3 text-xs"><b>{t("photo.readText")}</b> {r.ocr_text}</div>}
            {r.topic && <span className="chip bg-lav/30 text-violet-700">🏷️ {r.topic}</span>}
            <ol className="space-y-2">
              {r.steps.map((s, i) => (
                <li key={i} className="flex gap-3 rounded-2xl border-2 border-line p-3 animate-fade" style={{ animationDelay: `${i * 0.12}s` }}>
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full grad-bg text-xs font-extrabold text-white">{i + 1}</span><span className="text-sm">{s}</span>
                </li>
              ))}
            </ol>
            {r.answer && <div className="rounded-2xl border-2 border-ok bg-ok/10 p-3 font-display text-xl font-extrabold text-ok">🎯 {r.answer}</div>}
            {r.explanation && <p className="text-sm">{r.explanation}</p>}
            <div className="flex flex-wrap gap-2">
              <Button variant="sun" onClick={() => sim.mutate(r.topic)} disabled={sim.isPending}>🎯 {t("photo.practice")}</Button>
              {canSpeak() && <Button variant="soft" onClick={() => speak([...r.steps, r.answer].join(". "), lang)}><Volume2 size={16} /> {t("chitti.readAloud")}</Button>}
            </div>
            {practice && (practice.length ? <PracticeQuiz questions={practice} /> : <p className="text-sm text-mute">{t("practice.none")} <Link className="font-bold text-primary" to="../chitti">{t("chitti.ask")}</Link></p>)}
          </div>
        )}
      </Card>
    </div>
  );
}
