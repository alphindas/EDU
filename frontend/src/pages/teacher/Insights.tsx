import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { get, post } from "@/lib/api";
import { sectionLabel, subjectName, useClasses, useSections, useSubjects } from "@/lib/queries";
import { useAuth } from "@/lib/auth";
import type { Assignment } from "@/lib/types";
import { pctText } from "@/lib/v2";
import { cn } from "@/lib/utils";

interface TI {
  section: string;
  summary: { students: number; quiz_avg: number | null; attendance: number | null; completion: number | null; exam_avg: number | null; improvement: number | null; attention: number };
  students: { id: number; name: string; roll_no: number | null; attendance: number | null; quiz_avg: number | null; exam_avg: number | null; attempts: number; weak_topics: string[]; flags: string[] }[];
  quizzes: { id: number; title: string; avg: number | null; completion: number; attempts: number }[];
  missed: { question_id: number; quiz: string; text: string; topic: string; wrong_pct: number }[];
  topics: { topic: string; mastery: number; answers: number }[];
  exam_trend: { exam: string; avg: number | null }[];
}
const FLAG_TONE: Record<string, string> = { needs_support: "bg-amber-100 text-amber-700", low_attendance: "bg-rose-100 text-rose-700", stopped_quizzes: "bg-violet-100 text-violet-700", improving: "bg-ok/15 text-ok" };

export default function Insights() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const tid = useAuth((s) => s.user?.teacher_id);
  const asg = useQuery({ queryKey: ["my-asg", tid], queryFn: () => get<Assignment[]>(`/assignments?teacher_id=${tid}`), enabled: !!tid });
  const secs = useSections(); const classes = useClasses(); const subs = useSubjects();
  const mySecs = [...new Set((asg.data ?? []).map((a) => a.section_id))];
  const [sec, setSec] = useState<number | null>(null);
  const [sub, setSub] = useState<string>("");
  const [tab, setTab] = useState<"class" | "ai">("class");
  useEffect(() => { if (!sec && mySecs.length) setSec(mySecs[0]); }, [mySecs.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const q = useQuery({ queryKey: ["ti", sec, sub], queryFn: () => get<TI>(`/insights/teacher?section_id=${sec}${sub ? `&subject_id=${sub}` : ""}`), enabled: !!sec });
  const ov = useQuery({ queryKey: ["oversight"], queryFn: () => get<{ id: number; student: string; path: string; question: string; at: string }[]>("/chitti/oversight"), enabled: tab === "ai" });
  const mySubs = (asg.data ?? []).filter((a) => a.section_id === sec).map((a) => a.subject_id);
  const rev = useMutation({ mutationFn: () => post<{ quiz_id: number; questions: number; topics: string[] }>("/insights/revision-quiz", { section_id: sec, subject_id: Number(sub || mySubs[0]) }),
    onSuccess: (r) => { toast(t("ins.revMade", { n: r.questions })); nav("/teacher/quizzes"); }, onError: toastError });
  const d = q.data;
  return (
    <div>
      <PageHero title={t("ins.title")} subtitle={t("ins.sub")} emoji="📊">
        <div className="flex flex-wrap gap-2">
          <Select className="w-32 bg-white" value={sec ?? ""} onChange={(e) => setSec(Number(e.target.value))}>{mySecs.map((s) => <option key={s} value={s}>{sectionLabel(secs.data, classes.data, s)}</option>)}</Select>
          <Select className="w-40 bg-white" value={sub} onChange={(e) => setSub(e.target.value)}><option value="">{t("ins.allSubjects")}</option>{[...new Set(mySubs)].map((s) => <option key={s} value={s}>{subjectName(subs.data, s)}</option>)}</Select>
        </div>
      </PageHero>
      <div className="mb-4 flex gap-2">{(["class", "ai"] as const).map((k) => <button key={k} onClick={() => setTab(k)} className={cn("rounded-2xl px-4 py-2 text-sm font-extrabold", tab === k ? "grad-bg text-white shadow-chunky" : "bg-card text-mute shadow-card")}>{t(`ins.tab.${k}`)}</button>)}</div>
      {tab === "ai" ? (
        <Card className="p-5">
          <p className="mb-3 text-sm text-mute">{t("ins.aiSub")}</p>
          {!ov.data?.length ? <EmptyState /> : <ul className="divide-y divide-line">{ov.data.map((r) => <li key={r.id} className="py-2 text-sm"><b>{r.student}</b> <span className="chip bg-soft text-primary">{r.path.replace("/chitti/", "")}</span><span className="ml-2 text-xs text-mute">{new Date(r.at).toLocaleString(i18n.language)}</span><p className="text-mute">{r.question}</p></li>)}</ul>}
        </Card>
      ) : !sec ? <EmptyState text={t("ins.noSections")} /> : q.isLoading || !d ? <Loading /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
            {[["ins.quizAvg", pctText(d.summary.quiz_avg), "📝"], ["ins.attendance", pctText(d.summary.attendance), "📅"], ["ins.completion", pctText(d.summary.completion), "✅"],
              ["ins.examAvg", pctText(d.summary.exam_avg), "🏁"], ["ins.improvement", d.summary.improvement == null ? "—" : `${d.summary.improvement > 0 ? "+" : ""}${d.summary.improvement}`, "📈"],
              ["ins.attention", String(d.summary.attention), "🤝"]].map(([k, v, e]) => (
              <Card key={k} className="p-4"><div className="text-2xl">{e}</div><div className="font-display text-2xl font-extrabold">{v}</div><div className="text-xs font-bold text-mute">{t(k)}</div></Card>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <div className="mb-3 flex items-center justify-between"><h3 className="font-display text-lg font-extrabold">🎯 {t("ins.topics")}</h3>
                <Button size="sm" variant="sun" onClick={() => rev.mutate()} disabled={rev.isPending || !mySubs.length}><Sparkles size={15} /> {t("ins.revisionQuiz")}</Button></div>
              {!d.topics.length ? <EmptyState /> : <div className="h-60"><ResponsiveContainer><BarChart data={d.topics} layout="vertical" margin={{ left: 20 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} /><YAxis type="category" dataKey="topic" width={110} tick={{ fontSize: 11 }} /><Tooltip />
                <Bar dataKey="mastery" radius={[0, 8, 8, 0]}>{d.topics.map((x) => <Cell key={x.topic} fill={x.mastery < 50 ? "#FB923C" : x.mastery < 70 ? "#FACC15" : "#34D399"} />)}</Bar></BarChart></ResponsiveContainer></div>}
            </Card>
            <Card className="p-5">
              <h3 className="mb-3 font-display text-lg font-extrabold">❗ {t("ins.missed")}</h3>
              {!d.missed.length ? <EmptyState /> : <ul className="space-y-2">{d.missed.slice(0, 6).map((m) => (
                <li key={m.question_id} className="flex items-center gap-3 rounded-2xl bg-soft/60 p-2.5"><span className="grid h-10 w-12 shrink-0 place-items-center rounded-xl bg-orange-100 text-sm font-extrabold text-orange-700">{Math.round(m.wrong_pct)}%</span>
                  <div className="min-w-0"><div className="truncate text-sm font-bold">{m.text}</div><div className="text-xs text-mute">{m.quiz} · {m.topic}</div></div></li>))}</ul>}
            </Card>
          </div>
          <Card className="overflow-x-auto p-5">
            <h3 className="mb-3 flex items-center gap-2 font-display text-lg font-extrabold"><Users size={18} /> {t("ins.students")}</h3>
            <table className="w-full min-w-[720px] text-sm">
              <thead><tr className="text-left text-xs uppercase text-mute"><th className="pb-2">{t("ins.student")}</th><th>{t("ins.attendance")}</th><th>{t("ins.quizAvg")}</th><th>{t("ins.examAvg")}</th><th>{t("ins.weak")}</th><th>{t("ins.signals")}</th></tr></thead>
              <tbody>{d.students.map((s) => (
                <tr key={s.id} className="border-t border-line">
                  <td className="py-2 font-bold">{s.roll_no ? `${s.roll_no}. ` : ""}{s.name}</td>
                  <td>{pctText(s.attendance)}</td><td>{pctText(s.quiz_avg)}</td><td>{pctText(s.exam_avg)}</td>
                  <td className="text-xs">{s.weak_topics.join(", ") || "—"}</td>
                  <td><div className="flex flex-wrap gap-1">{s.flags.map((f) => <span key={f} className={cn("chip", FLAG_TONE[f])}>{t(`ins.flag.${f}`)}</span>)}</div></td>
                </tr>
              ))}</tbody>
            </table>
            <p className="mt-3 text-xs text-mute">{t("ins.kindNote")}</p>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-3 font-display text-lg font-extrabold">📝 {t("ins.quizzes")}</h3>
              <ul className="space-y-2">{d.quizzes.map((x) => (
                <li key={x.id} className="rounded-2xl bg-soft/60 p-3"><div className="flex justify-between text-sm font-bold"><span className="truncate">{x.title}</span><span>{pctText(x.avg)}</span></div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-mute"><div className="h-2 flex-1 overflow-hidden rounded-full bg-line"><div className="h-full grad-mint" style={{ width: `${x.completion}%` }} /></div>{t("ins.done", { n: Math.round(x.completion) })}</div></li>))}</ul>
            </Card>
            <Card className="p-5">
              <h3 className="mb-3 font-display text-lg font-extrabold">🏁 {t("ins.examTrend")}</h3>
              {d.exam_trend.length < 2 ? <EmptyState /> : <div className="h-56"><ResponsiveContainer><LineChart data={d.exam_trend}><XAxis dataKey="exam" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 11 }} /><Tooltip />
                <Line dataKey="avg" stroke="#8B5CF6" strokeWidth={3} dot={{ r: 5 }} /></LineChart></ResponsiveContainer></div>}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
