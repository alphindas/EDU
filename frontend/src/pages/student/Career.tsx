import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Info } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toastError } from "@/components/common/toast";
import { celebrate, type Reward } from "@/components/fun/Celebrate";
import Chitti from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/label";
import { Input, Select } from "@/components/ui/input";
import { get, post } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Sugg { area: string; label: string; score: number; careers: { name: string; roadmap: string; emoji: string }[] }
interface Lab {
  stem: { id: string; emoji: string; title: string; time: number; skills: string[]; steps: string[] }[];
  coding: { id: string; emoji: string; title: string; level: number; code: string; options: string[]; answer: number; explain: string }[];
  projects: { emoji: string; title: string; idea: string }[]; courses: { emoji: string; title: string; where: string }[];
}
const FACES = ["😐", "🙂", "😊", "😄", "🤩"];

export default function Career() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"quiz" | "lab" | "code" | "scholar">("quiz");
  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-yellow-100 via-amber-50 to-emerald-100 p-5 shadow-card sm:p-7 dark:from-soft dark:to-soft">
        <div className="flex flex-wrap items-center gap-4"><Chitti size={96} mood="cheer" avatar={{ hat: "hat_grad" }} />
          <div><h1 className="font-display text-3xl font-extrabold text-navy dark:text-ink">🧭 {t("career.title")}</h1><p className="text-sm font-semibold text-navy/70 dark:text-mute">{t("career.sub")}</p></div></div>
      </div>
      <div className="flex gap-2 overflow-x-auto no-scrollbar">
        {([["quiz", "🧩"], ["lab", "🔬"], ["code", "💻"], ["scholar", "🎓"]] as const).map(([k, e]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("shrink-0 rounded-2xl px-4 py-2 text-sm font-extrabold", tab === k ? "grad-bg text-white shadow-chunky" : "bg-card text-mute shadow-card")}>{e} {t(`career.tab.${k}`)}</button>
        ))}
      </div>
      {tab === "quiz" && <InterestQuiz />}
      {tab === "lab" && <LabTab />}
      {tab === "code" && <CodeTab />}
      {tab === "scholar" && <ScholarTab />}
    </div>
  );
}

function InterestQuiz() {
  const { t } = useTranslation();
  const qs = useQuery({ queryKey: ["career-q"], queryFn: () => get<{ id: string; text: string }[]>("/career/questions") });
  const latest = useQuery({ queryKey: ["career-latest"], queryFn: () => get<{ suggestions: Sugg[]; scores: Record<string, number>; labels: Record<string, string> } | null>("/career/latest") });
  const [ans, setAns] = useState<Record<string, number>>({});
  const [redo, setRedo] = useState(false);
  const submit = useMutation({ mutationFn: () => post<{ suggestions: Sugg[]; scores: Record<string, number>; labels: Record<string, string>; note: string }>("/career/submit", { answers: ans }), onError: toastError,
    onSuccess: () => { celebrate({ xp: 15, coins: 5, new_badges: [], level_up: null } as Reward); latest.refetch(); setRedo(false); } });
  const res = submit.data ?? (!redo ? latest.data : null);
  if (res) {
    return (
      <div className="space-y-4">
        <Card className="p-5">
          <div className="mb-3 flex items-start gap-2 rounded-2xl bg-soft p-3 text-sm dark:bg-soft"><Info size={16} className="mt-0.5 shrink-0 text-primary" />{t("career.note")}</div>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(res.scores).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2"><span className="w-44 truncate text-sm font-bold">{t(`career.area.${k}`)}</span>
                <div className="h-4 flex-1 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full grad-sun" style={{ width: `${v}%` }} /></div><span className="w-10 text-right text-xs font-extrabold">{v}</span></div>
            ))}
          </div>
        </Card>
        <div className="grid gap-4 lg:grid-cols-3">
          {res.suggestions.map((s) => (
            <Card key={s.area} className="p-5">
              <div className="chip bg-amber-100 text-amber-700">{t(`career.area.${s.area}`)}</div>
              <div className="mt-3 space-y-3">
                {s.careers.map((c) => (
                  <div key={c.name} className="flex gap-3 rounded-2xl bg-soft/60 p-3"><span className="text-3xl">{c.emoji}</span>
                    <div><div className="font-display text-lg font-extrabold leading-tight">{c.name}</div><div className="text-xs font-semibold text-mute">🛣️ {c.roadmap}</div></div></div>
                ))}
              </div>
            </Card>
          ))}
        </div>
        <Button variant="outline" onClick={() => { setRedo(true); setAns({}); submit.reset(); }}>{t("career.retake")}</Button>
      </div>
    );
  }
  const list = qs.data ?? [];
  const done = Object.keys(ans).length;
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between"><h2 className="font-display text-xl font-extrabold">{t("career.quizTitle")}</h2><span className="chip bg-soft text-primary">{done}/{list.length}</span></div>
      <div className="space-y-3">
        {list.map((q, i) => (
          <div key={q.id} className="rounded-2xl border-2 border-line p-3">
            <div className="mb-2 text-sm font-bold">{i + 1}. {q.text}</div>
            <div className="flex gap-2">
              {FACES.map((f, k) => (
                <button key={k} onClick={() => setAns({ ...ans, [q.id]: k + 1 })} aria-label={`${k + 1}`}
                  className={cn("grid h-11 flex-1 place-items-center rounded-xl border-2 text-2xl transition", ans[q.id] === k + 1 ? "scale-110 border-primary bg-soft" : "border-line hover:bg-soft/60")}>{f}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <Button className="mt-4 w-full" size="lg" variant="sun" disabled={done < 8 || submit.isPending} onClick={() => submit.mutate()}>✨ {t("career.see")}</Button>
    </Card>
  );
}

function LabTab() {
  const { t } = useTranslation();
  const lab = useQuery({ queryKey: ["lab"], queryFn: () => get<Lab>("/career/lab") });
  const [done, setDone] = useState<Record<string, number[]>>({});
  const d = lab.data;
  if (!d) return null;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {d.stem.map((s) => (
          <Card key={s.id} className="p-5">
            <div className="flex items-center gap-3"><span className="text-4xl">{s.emoji}</span><div><div className="font-display text-lg font-extrabold leading-tight">{s.title}</div>
              <div className="text-xs font-bold text-mute">⏱️ {s.time} min · {s.skills.join(", ")}</div></div></div>
            <ol className="mt-3 space-y-1.5">
              {s.steps.map((st, i) => {
                const on = done[s.id]?.includes(i);
                return (
                  <li key={i}><label className={cn("flex cursor-pointer items-start gap-2 rounded-xl p-1.5 text-sm", on && "text-mute line-through")}>
                    <input type="checkbox" className="mt-0.5 h-4 w-4 accent-emerald-500" checked={!!on}
                      onChange={() => setDone({ ...done, [s.id]: on ? done[s.id].filter((x) => x !== i) : [...(done[s.id] ?? []), i] })} />{st}</label></li>
                );
              })}
            </ol>
            {done[s.id]?.length === s.steps.length && <div className="mt-2 chip bg-ok/15 text-ok">🎉 {t("career.labDone")}</div>}
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5"><h3 className="mb-3 font-display text-lg font-extrabold">💡 {t("career.projectIdeas")}</h3>
          <ul className="space-y-2">{d.projects.map((p) => <li key={p.title} className="flex gap-3 rounded-2xl bg-soft/60 p-3"><span className="text-2xl">{p.emoji}</span><div><b>{p.title}</b><p className="text-sm text-mute">{p.idea}</p></div></li>)}</ul></Card>
        <Card className="p-5"><h3 className="mb-3 font-display text-lg font-extrabold">🎒 {t("career.courses")}</h3>
          <ul className="space-y-2">{d.courses.map((p) => <li key={p.title} className="flex gap-3 rounded-2xl bg-soft/60 p-3"><span className="text-2xl">{p.emoji}</span><div><b>{p.title}</b><p className="text-sm text-mute">{p.where}</p></div></li>)}</ul></Card>
      </div>
    </div>
  );
}

function CodeTab() {
  const { t } = useTranslation();
  const lab = useQuery({ queryKey: ["lab"], queryFn: () => get<Lab>("/career/lab") });
  const [res, setRes] = useState<Record<string, { correct: boolean; answer: number; explain: string; pick: number }>>({});
  const ans = useMutation({ mutationFn: (b: { challenge: string; choice: number }) => post<{ correct: boolean; answer: number; explain: string; reward: Reward | null }>("/career/code", b),
    onSuccess: (r, b) => { setRes((x) => ({ ...x, [b.challenge]: { ...r, pick: b.choice } })); celebrate(r.reward); }, onError: toastError });
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {(lab.data?.coding ?? []).map((c) => {
        const r = res[c.id];
        return (
          <Card key={c.id} className="p-5">
            <div className="mb-2 flex items-center justify-between"><span className="font-display text-lg font-extrabold">{c.emoji} {c.title}</span><span className="chip bg-soft text-primary">{"⭐".repeat(c.level)}</span></div>
            <pre className="overflow-x-auto rounded-2xl bg-navy p-3 font-mono text-sm leading-relaxed text-primary"><code>{c.code}</code></pre>
            <p className="mt-2 text-sm font-bold">{t("career.predict")}</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {c.options.map((o, i) => (
                <button key={i} disabled={!!r} onClick={() => ans.mutate({ challenge: c.id, choice: i })}
                  className={cn("rounded-xl border-2 px-3 py-2 font-mono text-sm font-bold", !r && "border-line hover:border-primary", r && i === r.answer && "border-ok bg-ok/10 text-ok", r && r.pick === i && !r.correct && "border-bad bg-bad/10 text-bad")}>{o}</button>
              ))}
            </div>
            {r && <p className="mt-2 text-sm">{r.correct ? "🎉" : "🤔"} {r.explain}</p>}
          </Card>
        );
      })}
    </div>
  );
}

function ScholarTab() {
  const { t } = useTranslation();
  const [marks, setMarks] = useState("80");
  const [category, setCategory] = useState("general");
  const [girl, setGirl] = useState(false);
  const m = useMutation({ mutationFn: () => post<{ matches: { name: string; why: string }[]; official_portal: string; note: string }>("/career/scholarships", { marks: Number(marks), category, girl }), onError: toastError });
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="space-y-3 p-5">
        <h2 className="font-display text-xl font-extrabold">🎓 {t("career.scholarTitle")}</h2>
        <Field label={t("career.marks")}><Input type="number" min={0} max={100} value={marks} onChange={(e) => setMarks(e.target.value)} /></Field>
        <Field label={t("career.category")}><Select value={category} onChange={(e) => setCategory(e.target.value)}>
          {["general", "obc", "sc", "st", "minority", "disabled"].map((c) => <option key={c} value={c}>{t(`career.cat.${c}`)}</option>)}</Select></Field>
        <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" className="h-5 w-5 accent-sky-500" checked={girl} onChange={(e) => setGirl(e.target.checked)} /> {t("career.girl")}</label>
        <Button className="w-full" onClick={() => m.mutate()}>🔎 {t("career.find")}</Button>
      </Card>
      <Card className="p-5">
        {!m.data ? <div className="flex h-full flex-col items-center justify-center gap-2 py-8 text-center"><Chitti size={90} mood="think" /><p className="text-sm text-mute">{t("career.scholarEmpty")}</p></div> : (
          <div className="space-y-2">
            {m.data.matches.map((x) => <div key={x.name} className="rounded-2xl bg-soft/60 p-3"><b>🏅 {x.name}</b><p className="text-xs text-mute">{x.why}</p></div>)}
            {!m.data.matches.length && <p className="text-sm text-mute">{t("career.noMatch")}</p>}
            <p className="mt-2 rounded-2xl bg-amber-50 p-3 text-xs font-semibold dark:bg-soft">⚠️ {m.data.note}</p>
            <a className="flex items-center gap-1 text-sm font-bold text-primary" href={m.data.official_portal} target="_blank" rel="noreferrer noopener">{t("career.portal")} <ExternalLink size={14} /></a>
          </div>
        )}
      </Card>
    </div>
  );
}
