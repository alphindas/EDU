import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, Loading } from "@/components/common/bits";
import { PageHero } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { get } from "@/lib/api";
import { useSubjects } from "@/lib/queries";
import { type Pattern, pctText } from "@/lib/v2";
import { cn } from "@/lib/utils";

interface SI {
  cards: { school_avg: number | null; attendance: number | null; quiz_completion: number | null; classes_monitored: number; students: number };
  today: Record<string, number>;
  sections: { section_id: number; section: string; students: number; attendance: number | null; quiz_avg: number | null; exam_avg: number | null; completion: number | null }[];
  subjects: { subject: string; quiz_avg: number | null; exam_avg: number | null }[];
  reteach: { topic: string; mastery: number; answers: number }[];
  growth: { week: string; avg: number | null }[];
  patterns: Pattern[]; classes: { id: number; name: string }[];
}
const SEV: Record<string, string> = { high: "border-orange-300 bg-orange-50", medium: "border-amber-200 bg-amber-50", good: "border-emerald-200 bg-emerald-50" };
const SEV_E: Record<string, string> = { high: "🔶", medium: "💡", good: "🌟" };

export default function Intelligence() {
  const { t } = useTranslation();
  const subs = useSubjects();
  const [f, setF] = useState({ class_id: "", subject_id: "", date_from: "", date_to: "" });
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const q = useQuery({ queryKey: ["si", qs], queryFn: () => get<SI>(`/insights/school?${qs}`) });
  const d = q.data;
  return (
    <div>
      <PageHero title={t("si.title")} subtitle={t("si.sub")} emoji="🧠" />
      <Card className="mb-4 grid gap-2 p-3 sm:grid-cols-4">
        <Select value={f.class_id} onChange={(e) => setF({ ...f, class_id: e.target.value })}><option value="">{t("si.allClasses")}</option>{d?.classes.map((c) => <option key={c.id} value={c.id}>{t("si.class", { n: c.name })}</option>)}</Select>
        <Select value={f.subject_id} onChange={(e) => setF({ ...f, subject_id: e.target.value })}><option value="">{t("ins.allSubjects")}</option>{subs.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
        <Input type="date" value={f.date_from} onChange={(e) => setF({ ...f, date_from: e.target.value })} aria-label={t("si.from")} />
        <Input type="date" value={f.date_to} onChange={(e) => setF({ ...f, date_to: e.target.value })} aria-label={t("si.to")} />
      </Card>
      {q.isLoading || !d ? <Loading /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[["si.schoolAvg", pctText(d.cards.school_avg), "🏫", "from-sky-100 to-sky-50"], ["si.attendance", pctText(d.cards.attendance), "📅", "from-emerald-100 to-emerald-50"],
              ["si.completion", pctText(d.cards.quiz_completion), "✅", "from-amber-100 to-amber-50"], ["si.monitored", String(d.cards.classes_monitored), "👀", "from-violet-100 to-violet-50"]].map(([k, v, e, c]) => (
              <div key={k} className={cn("rounded-3xl bg-gradient-to-br p-5 shadow-card dark:from-soft dark:to-soft", c)}><div className="text-3xl">{e}</div><div className="font-display text-3xl font-extrabold text-navy dark:text-ink">{v}</div><div className="text-xs font-bold text-navy/60 dark:text-mute">{t(k)}</div></div>
            ))}
          </div>
          <p className="text-xs text-mute">ⓘ {t("si.demoNote")}</p>
          <Card className="p-5">
            <h3 className="mb-1 font-display text-lg font-extrabold">🔍 {t("si.patterns")}</h3>
            <p className="mb-3 text-sm text-mute">{t("si.patternsSub")}</p>
            {!d.patterns.length ? <EmptyState text={t("si.noPatterns")} /> : (
              <div className="grid gap-3 md:grid-cols-2">{d.patterns.map((p, i) => (
                <div key={i} className={cn("rounded-2xl border-2 p-3 dark:bg-soft", SEV[p.severity])}>
                  <div className="font-bold text-navy dark:text-ink">{SEV_E[p.severity]} {t(p.key, p.params)}</div>
                  <div className="mt-1 text-sm text-navy/75 dark:text-mute">➜ {t(p.action, p.params)}</div>
                </div>))}</div>
            )}
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-5"><h3 className="mb-3 font-display text-lg font-extrabold">🏫 {t("si.sections")}</h3>
              <div className="h-64"><ResponsiveContainer><BarChart data={d.sections}><CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" /><XAxis dataKey="section" /><YAxis domain={[0, 100]} /><Tooltip /><Legend />
                <Bar dataKey="quiz_avg" name={t("ins.quizAvg")} fill="#0EA5E9" radius={[6, 6, 0, 0]} /><Bar dataKey="attendance" name={t("ins.attendance")} fill="#34D399" radius={[6, 6, 0, 0]} />
                <Bar dataKey="completion" name={t("ins.completion")} fill="#FACC15" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
            <Card className="p-5"><h3 className="mb-3 font-display text-lg font-extrabold">📚 {t("si.subjects")}</h3>
              {!d.subjects.length ? <EmptyState /> : <div className="h-64"><ResponsiveContainer><BarChart data={d.subjects}><CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" /><XAxis dataKey="subject" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} /><Tooltip /><Legend />
                <Bar dataKey="quiz_avg" name={t("ins.quizAvg")} fill="#8B5CF6" radius={[6, 6, 0, 0]} /><Bar dataKey="exam_avg" name={t("ins.examAvg")} fill="#FB923C" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div>}</Card>
            <Card className="p-5"><h3 className="mb-3 font-display text-lg font-extrabold">📈 {t("si.growth")}</h3>
              {d.growth.length < 2 ? <EmptyState /> : <div className="h-56"><ResponsiveContainer><LineChart data={d.growth}><XAxis dataKey="week" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} /><Tooltip /><Line dataKey="avg" name={t("ins.quizAvg")} stroke="#0EA5E9" strokeWidth={3} dot={{ r: 4 }} /></LineChart></ResponsiveContainer></div>}</Card>
            <Card className="p-5"><h3 className="mb-3 font-display text-lg font-extrabold">🔁 {t("si.reteach")}</h3>
              {!d.reteach.length ? <EmptyState /> : <ul className="space-y-2">{d.reteach.map((r) => (
                <li key={r.topic} className="flex items-center gap-2"><span className="w-36 truncate text-sm font-bold">{r.topic}</span><div className="h-4 flex-1 overflow-hidden rounded-full bg-line"><div className={cn("h-full rounded-full", r.mastery < 50 ? "bg-orange-400" : r.mastery < 70 ? "bg-amber-300" : "bg-emerald-400")} style={{ width: `${r.mastery}%` }} /></div><span className="w-12 text-right text-xs font-extrabold">{Math.round(r.mastery)}%</span></li>))}</ul>}</Card>
          </div>
        </div>
      )}
    </div>
  );
}
