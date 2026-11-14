import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import WithChild from "@/components/common/ChildPicker";
import SectionPicker, { useMySectionIds } from "@/components/common/SectionPicker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useStudentPage } from "@/lib/queries";
import type { ProgressPoint, ReportCardData } from "@/lib/types";

const SERIES = [
  { key: "main", color: "hsl(var(--ac))", dash: undefined },
  { key: "mock", color: "hsl(var(--warn))", dash: "6 4" },
  { key: "quiz", color: "hsl(var(--ok))", dash: "2 3" },
] as const;

const pctTone = (p: number | null) => (p === null ? "mute" : p >= 60 ? "ok" : p >= 35 ? "warn" : "bad") as "mute" | "ok" | "warn" | "bad";
const Pct = ({ v }: { v: number | null }) => (v === null ? <span className="text-mute">—</span> : <Badge tone={pctTone(v)}>{v}%</Badge>);

/** One row per data point, one column per series, so the three kinds draw as separate lines on a shared % axis. */
function ProgressChart({ points }: { points: ProgressPoint[] }) {
  const { t } = useTranslation();
  const data = points.map((p, i) => ({ i, date: p.date, label: p.label, subject: p.subject, [p.kind]: p.percentage }));
  return (
    <div role="img" aria-label={t("rc.progress")} className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: -16, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "hsl(var(--mute))" }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "hsl(var(--mute))" }} unit="%" />
          <Tooltip
            contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--line))", borderRadius: 12 }}
            formatter={(v, name) => [`${v}%`, t(`rc.${String(name)}`)]}
            labelFormatter={(_, pl) => { const d = pl?.[0]?.payload as { label?: string; subject?: string; date?: string } | undefined; return d ? `${d.label} · ${d.subject} · ${d.date}` : ""; }}
          />
          <Legend formatter={(v) => t(`rc.${String(v)}`)} />
          {SERIES.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.key} stroke={s.color} strokeWidth={2.5} strokeDasharray={s.dash} dot={{ r: 4 }} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Card_({ studentId }: { studentId: number }) {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["report-card", studentId], queryFn: () => get<ReportCardData>(`/report-card?student_id=${studentId}`) });
  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const r = q.data;
  const empty = !r.subjects.length && !r.progress.length;
  return (
    <div className="space-y-4">
      <Card className="grad-bg flex flex-wrap items-center justify-between gap-4 border-0 p-6 text-white">
        <div>
          <h2 className="text-xl font-extrabold">{r.student_name}</h2>
          <p className="text-sm text-white/85">{r.class_name}-{r.section_name} · {t("rc.admission")} {r.admission_no}{r.roll_no ? ` · ${t("students.roll")} ${r.roll_no}` : ""}{r.academic_year ? ` · ${r.academic_year}` : ""}</p>
        </div>
        <div className="flex items-center gap-5">
          <div className="text-right"><div className="text-3xl font-extrabold leading-none">{r.overall_percentage === null ? "—" : `${r.overall_percentage}%`}</div><div className="text-xs uppercase tracking-wide text-white/80">{t("rc.overall")}</div></div>
          <div className="text-right"><div className="text-3xl font-extrabold leading-none">{r.overall_grade ?? "—"}</div><div className="text-xs uppercase tracking-wide text-white/80">{t("rc.grade")}</div></div>
          <Button variant="outline" size="icon" aria-label={t("rc.print")} className="print:hidden border-white/40 bg-white/15 text-white hover:bg-white/25" onClick={() => window.print()}><Printer size={16} /></Button>
        </div>
      </Card>

      {empty ? <Card><EmptyState text={t("rc.empty")} /></Card> : (
        <>
          <Card>
            <CardHeader><CardTitle>{t("rc.subject")}</CardTitle></CardHeader>
            <CardContent>
              <Table className="min-w-[480px]">
                <thead><tr><Th>{t("rc.subject")}</Th><Th>{t("rc.main")}</Th><Th>{t("rc.mock")}</Th><Th>{t("rc.quiz")}</Th><Th>{t("rc.grade")}</Th></tr></thead>
                <tbody>
                  {r.subjects.map((s) => (
                    <Tr key={s.subject_id}>
                      <Td className="font-semibold">{s.subject}</Td><Td><Pct v={s.main_percentage} /></Td><Td><Pct v={s.mock_percentage} /></Td><Td><Pct v={s.quiz_percentage} /></Td>
                      <Td className="font-extrabold">{s.grade ?? "—"}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
              <p className="mt-3 text-xs text-mute">{t("rc.gradeNote")}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>{t("rc.progress")}</CardTitle></CardHeader>
            <CardContent>
              <p className="mb-3 text-xs text-mute">{t("rc.progressHint")}</p>
              {r.progress.length ? <ProgressChart points={r.progress} /> : <EmptyState text={t("rc.empty")} />}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>{t("rc.exams")}</CardTitle></CardHeader>
            <CardContent>
              <Table className="min-w-[480px]">
                <tbody>
                  {r.subjects.flatMap((s) => s.exams.map((e, i) => (
                    <Tr key={`${s.subject_id}-${i}`}>
                      <Td className="font-semibold">{s.subject}</Td><Td>{e.name}</Td><Td className="text-mute">{e.date}</Td>
                      <Td><Badge tone={e.kind === "main" ? "default" : "mute"}>{t(e.kind === "main" ? "exam.mainBadge" : "exam.mockBadge")}</Badge></Td>
                      <Td>{e.absent ? <Badge tone="warn">{t("rc.absent")}</Badge> : `${e.marks} / ${e.max_marks}`}</Td><Td><Pct v={e.percentage} /></Td>
                    </Tr>
                  )))}
                </tbody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>{t("rc.topics")}</CardTitle></CardHeader>
          <CardContent>
            <p className="mb-3 text-xs text-mute">{t("rc.topicsHint")}</p>
            {!r.topics.length ? <p className="text-sm text-mute">—</p> : (
              <ul className="space-y-3">
                {r.topics.map((x) => (
                  <li key={x.topic}>
                    <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                      <span className="font-semibold">{x.topic}</span>
                      <span className="flex items-center gap-2 text-mute">{x.correct}/{x.total} {x.weak && <Badge tone="bad">{t("rc.weak")}</Badge>}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={x.percentage} aria-valuemin={0} aria-valuemax={100} aria-label={x.topic}>
                      <div className="h-full rounded-full" style={{ width: `${x.percentage}%`, background: x.weak ? "hsl(var(--bad))" : "hsl(var(--ok))" }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("rc.homework")}</CardTitle></CardHeader>
          <CardContent><p className="text-sm">{t("rc.hwSummary", { submitted: r.homework.submitted, total: r.homework.total, reviewed: r.homework.reviewed, late: r.homework.late })}</p></CardContent>
        </Card>
      </div>
    </div>
  );
}

/** Teacher/admin: choose a section, then a student. */
function StaffPicker() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const mine = useMySectionIds(user.role === "teacher" ? user.teacher_id : null);
  const [sec, setSec] = useState<number | null>(null);
  const [stu, setStu] = useState<number | null>(null);
  const students = useStudentPage(sec ? { section_id: sec, limit: 200 } : { limit: 1 });
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SectionPicker value={sec} onChange={(id) => { setSec(id); setStu(null); }} only={user.role === "teacher" ? mine.ids : undefined} />
        <Select className="w-auto min-w-48" disabled={!sec} value={stu ?? ""} onChange={(e) => setStu(Number(e.target.value))} aria-label={t("rc.pickStudent")}>
          <option value="" disabled>{t("rc.pickStudent")}</option>
          {sec && students.data?.items.map((s) => <option key={s.id} value={s.id}>{s.roll_no ? `${s.roll_no}. ` : ""}{s.full_name}</option>)}
        </Select>
      </div>
      {stu ? <Card_ key={stu} studentId={stu} /> : <Card><EmptyState text={t("rc.pickStudent")} /></Card>}
    </>
  );
}

export default function ReportCardPage() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  return (
    <>
      <PageHeader title={t(user.role === "teacher" || user.role === "admin" ? "nav.reportCards" : "nav.reportCard")} />
      {user.role === "student" && user.student_id ? <Card_ studentId={user.student_id} />
        : user.role === "parent" ? <WithChild>{(c) => <Card_ key={c.id} studentId={c.id} />}</WithChild>
        : <StaffPicker />}
    </>
  );
}
