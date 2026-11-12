import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileUp, Pencil, Plus, Timer, Trash2, XCircle } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import WithChild from "@/components/common/ChildPicker";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { del, get, patch, post, put, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sectionLabel, subjectName, useAssignments, useClasses, useSections, useSubjects } from "@/lib/queries";
import type { AnswerResult, AttemptPlay, AttemptResult, AttemptRow, QType, Quiz, QuizDetail, QuestionStaff } from "@/lib/types";
import { cn } from "@/lib/utils";

const QTYPES: QType[] = ["mcq", "true_false", "fill_blank", "descriptive"];
const statusTone = { draft: "mute", published: "ok", closed: "warn" } as const;
const blank = (qtype: QType): QuestionStaff => ({
  qtype, text: "", options: qtype === "mcq" ? ["", "", "", ""] : [], answer: qtype === "true_false" ? true : qtype === "fill_blank" ? [] : qtype === "mcq" ? null : "",
  explanation: "", topic: "", difficulty: "medium", marks: 1,
});

const fmtAnswer = (a: AnswerResult, v: AnswerResult["your_answer"] | AnswerResult["correct_answer"], t: (k: string) => string) => {
  if (v === null || v === undefined || v === "") return t("quiz.yourAnswerBlank");
  if (a.qtype === "mcq") return a.options[v as number] ?? String(v);
  if (a.qtype === "true_false") return t(v ? "quiz.true" : "quiz.false");
  return Array.isArray(v) ? v.join(" | ") : String(v);
};

// ------------------------------------------------------------------ builder (teacher)
function QuestionEditor({ q, i, onChange, onRemove }: { q: QuestionStaff; i: number; onChange: (q: QuestionStaff) => void; onRemove: () => void }) {
  const { t } = useTranslation();
  const set = (p: Partial<QuestionStaff>) => onChange({ ...q, ...p });
  return (
    <div className="space-y-3 rounded-xl border border-line p-4">
      <div className="flex items-center justify-between gap-2">
        <b className="text-sm">{t("quiz.qno", { n: i + 1 })}</b>
        <Button type="button" size="icon" variant="ghost" aria-label={t("quiz.removeQuestion")} onClick={onRemove}><Trash2 size={16} className="text-bad" /></Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("quiz.type")}>
          <Select value={q.qtype} onChange={(e) => { const b = blank(e.target.value as QType); onChange({ ...b, text: q.text, marks: q.marks, topic: q.topic, difficulty: q.difficulty, explanation: q.explanation }); }}>
            {QTYPES.map((x) => <option key={x} value={x}>{t(`quiz.${x}`)}</option>)}
          </Select>
        </Field>
        <Field label={t("quiz.marks")}><Input type="number" min={0.5} max={100} step={0.5} required value={q.marks} onChange={(e) => set({ marks: Number(e.target.value) })} /></Field>
        <Field label={t("quiz.difficulty")}>
          <Select value={q.difficulty} onChange={(e) => set({ difficulty: e.target.value as QuestionStaff["difficulty"] })}>
            {["easy", "medium", "hard"].map((x) => <option key={x} value={x}>{t(`quiz.${x}`)}</option>)}
          </Select>
        </Field>
      </div>
      <Field label={t("quiz.questionText")}><Textarea required rows={2} maxLength={2000} value={q.text} onChange={(e) => set({ text: e.target.value })} /></Field>

      {q.qtype === "mcq" && (
        <div className="space-y-2" role="radiogroup" aria-label={t("quiz.correct")}>
          {q.options.map((o, k) => (
            <div key={k} className="flex items-center gap-2">
              <input type="radio" name={`correct-${i}`} checked={q.answer === k} onChange={() => set({ answer: k })} aria-label={`${t("quiz.correct")} ${k + 1}`} className="h-4 w-4 accent-[hsl(var(--ac))]" />
              <Input required placeholder={t("quiz.option", { n: k + 1 })} aria-label={t("quiz.option", { n: k + 1 })} value={o} onChange={(e) => set({ options: q.options.map((x, j) => (j === k ? e.target.value : x)) })} />
              {q.options.length > 2 && (
                <Button type="button" size="icon" variant="ghost" aria-label={t("common.delete")}
                  onClick={() => set({ options: q.options.filter((_, j) => j !== k), answer: q.answer === k ? null : typeof q.answer === "number" && q.answer > k ? q.answer - 1 : q.answer })}><XCircle size={16} /></Button>
              )}
            </div>
          ))}
          {q.options.length < 6 && <Button type="button" size="sm" variant="soft" onClick={() => set({ options: [...q.options, ""] })}><Plus size={14} />{t("quiz.addOption")}</Button>}
        </div>
      )}
      {q.qtype === "true_false" && (
        <Field label={t("quiz.correct")}>
          <Select value={String(q.answer)} onChange={(e) => set({ answer: e.target.value === "true" })}>
            <option value="true">{t("quiz.true")}</option><option value="false">{t("quiz.false")}</option>
          </Select>
        </Field>
      )}
      {q.qtype === "fill_blank" && (
        <Field label={t("quiz.acceptedAnswers")} hint={t("quiz.acceptedHint")}>
          <Input required value={Array.isArray(q.answer) ? q.answer.join(" | ") : ""} onChange={(e) => set({ answer: e.target.value.split("|").map((s) => s.trim()) })} />
        </Field>
      )}
      {q.qtype === "descriptive" && (
        <Field label={t("quiz.modelAnswer")} hint={t("quiz.descHint")}><Textarea rows={2} maxLength={2000} value={typeof q.answer === "string" ? q.answer : ""} onChange={(e) => set({ answer: e.target.value })} /></Field>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("quiz.topic")}><Input maxLength={100} value={q.topic} onChange={(e) => set({ topic: e.target.value })} /></Field>
        <Field label={t("quiz.explanation")}><Input maxLength={2000} value={q.explanation} onChange={(e) => set({ explanation: e.target.value })} /></Field>
      </div>
    </div>
  );
}

function BuilderDialog({ initial, onClose }: { initial: QuizDetail | null; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user)!;
  const assignments = useAssignments();
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const mine = (assignments.data ?? []).filter((a) => a.teacher_id === user.teacher_id);
  const [f, setF] = useState({ section_id: String(initial?.section_id ?? ""), subject_id: String(initial?.subject_id ?? ""), title: initial?.title ?? "", description: initial?.description ?? "", time: initial?.time_limit_minutes ? String(initial.time_limit_minutes) : "" });
  const [qs, setQs] = useState<QuestionStaff[]>(initial?.questions ?? [blank("mcq")]);
  const secIds = [...new Set(mine.map((a) => a.section_id))];
  const subjOpts = mine.filter((a) => String(a.section_id) === f.section_id);
  const save = useMutation({
    mutationFn: () => {
      const body = {
        section_id: Number(f.section_id), subject_id: Number(f.subject_id), title: f.title, description: f.description, time_limit_minutes: f.time ? Number(f.time) : null,
        questions: qs.map((q) => ({ qtype: q.qtype, text: q.text, options: q.options, answer: q.answer, explanation: q.explanation, topic: q.topic, difficulty: q.difficulty, marks: q.marks })),
      };
      return initial ? put<QuizDetail>(`/quizzes/${initial.id}`, body) : post<QuizDetail>("/quizzes", body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["quizzes"] }); toast(t("common.saved")); onClose(); }, onError: toastError,
  });
  const total = qs.reduce((s, q) => s + (q.marks || 0), 0);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={initial ? t("quiz.edit") : t("quiz.new")} description={initial?.source === "pdf" ? t("quiz.reviewDraft") : undefined} className="max-w-3xl">
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("students.section")}>
              <Select required value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value, subject_id: "" })}>
                <option value="" disabled>—</option>{secIds.map((id) => <option key={id} value={id}>{sectionLabel(sections.data, classes.data, id)}</option>)}
              </Select>
            </Field>
            <Field label={t("structure.subject")}>
              <Select required value={f.subject_id} onChange={(e) => setF({ ...f, subject_id: e.target.value })}>
                <option value="" disabled>—</option>{subjOpts.map((a) => <option key={a.id} value={a.subject_id}>{subjectName(subjects.data, a.subject_id)}</option>)}
              </Select>
            </Field>
            <div className="sm:col-span-2"><Field label={t("quiz.titleField")}><Input required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
            <Field label={t("quiz.description")}><Input maxLength={5000} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
            <Field label={t("quiz.timeLimit")} hint={t("quiz.timeLimitHint")}><Input type="number" min={1} max={300} value={f.time} onChange={(e) => setF({ ...f, time: e.target.value })} /></Field>
          </div>
          {qs.map((q, i) => (
            <QuestionEditor key={i} q={q} i={i} onChange={(nq) => setQs(qs.map((x, j) => (j === i ? nq : x)))} onRemove={() => setQs(qs.filter((_, j) => j !== i))} />
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="soft" onClick={() => setQs([...qs, blank("mcq")])}><Plus size={16} />{t("quiz.addQuestion")}</Button>
            <span className="ml-auto text-sm text-mute">{t("quiz.totalMarks")}: <b className="text-ink">{total}</b></span>
          </div>
          <Button type="submit" className="w-full" disabled={save.isPending || !qs.length}>{t("common.save")}</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PdfDialog({ onClose, onDrafted }: { onClose: () => void; onDrafted: (q: QuizDetail) => void }) {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const assignments = useAssignments();
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const mine = (assignments.data ?? []).filter((a) => a.teacher_id === user.teacher_id);
  const [f, setF] = useState({ section_id: "", subject_id: "", title: "", time_limit_minutes: "" });
  const [file, setFile] = useState<File | null>(null);
  const secIds = [...new Set(mine.map((a) => a.section_id))];
  const go = useMutation({
    mutationFn: () => { const fd = new FormData(); Object.entries(f).forEach(([k, v]) => v && fd.set(k, v)); fd.set("file", file!); return upload<QuizDetail>("POST", "/quizzes/from-pdf", fd); },
    onSuccess: (q) => { onDrafted(q); }, onError: toastError,
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("quiz.fromPdf")} description={t("quiz.pdfHint")}>
        <form onSubmit={(e) => { e.preventDefault(); go.mutate(); }} className="grid gap-3 sm:grid-cols-2">
          <Field label={t("students.section")}>
            <Select required value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value, subject_id: "" })}>
              <option value="" disabled>—</option>{secIds.map((id) => <option key={id} value={id}>{sectionLabel(sections.data, classes.data, id)}</option>)}
            </Select>
          </Field>
          <Field label={t("structure.subject")}>
            <Select required value={f.subject_id} onChange={(e) => setF({ ...f, subject_id: e.target.value })}>
              <option value="" disabled>—</option>{mine.filter((a) => String(a.section_id) === f.section_id).map((a) => <option key={a.id} value={a.subject_id}>{subjectName(subjects.data, a.subject_id)}</option>)}
            </Select>
          </Field>
          <div className="sm:col-span-2"><Field label={t("quiz.titleField")} hint={t("common.optional")}><Input maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
          <Field label={t("quiz.timeLimit")} hint={t("quiz.timeLimitHint")}><Input type="number" min={1} max={300} value={f.time_limit_minutes} onChange={(e) => setF({ ...f, time_limit_minutes: e.target.value })} /></Field>
          <Field label={t("quiz.pdfFile")}><Input required type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <div className="sm:col-span-2"><Button type="submit" className="w-full" disabled={go.isPending || !file}><FileUp size={16} />{t("quiz.fromPdf")}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ result view (+ teacher grading)
function Grader({ a, onDone }: { a: AnswerResult; onDone: () => void }) {
  const { t } = useTranslation();
  const [marks, setMarks] = useState(String(a.marks_awarded ?? ""));
  const [fb, setFb] = useState(a.feedback);
  const grade = useMutation({
    mutationFn: () => patch(`/attempts/answers/${a.answer_id}/grade`, { marks: Number(marks), feedback: fb }),
    onSuccess: () => { toast(t("common.saved")); onDone(); }, onError: toastError,
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); grade.mutate(); }} className="mt-2 grid gap-2 sm:grid-cols-[8rem_1fr_auto]">
      <Input required type="number" min={0} max={a.marks} step={0.5} value={marks} onChange={(e) => setMarks(e.target.value)} aria-label={t("quiz.gradeMarks", { max: a.marks })} placeholder={t("quiz.gradeMarks", { max: a.marks })} />
      <Input maxLength={2000} value={fb} onChange={(e) => setFb(e.target.value)} aria-label={t("quiz.feedback")} placeholder={t("quiz.feedback")} />
      <Button type="submit" size="sm" disabled={grade.isPending}>{t("common.save")}</Button>
    </form>
  );
}

function AttemptView({ attemptId, canGrade, onChanged }: { attemptId: number; canGrade: boolean; onChanged?: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["attempt", attemptId], queryFn: () => get<AttemptResult>(`/attempts/${attemptId}`) });
  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const r = q.data;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl bg-soft p-4">
        <span className="text-2xl font-extrabold">{r.score} / {r.max_score}</span>
        {r.percentage !== null ? <Badge tone={r.percentage >= 50 ? "ok" : "bad"}>{r.percentage}%</Badge> : <Badge tone="warn">{t("quiz.awaiting")}</Badge>}
        {r.timed_out && <Badge tone="bad">{t("quiz.timedOut")}</Badge>}
        <span className="ml-auto text-sm text-mute">{r.student_name}</span>
      </div>
      {r.answers.map((a, i) => (
        <div key={a.question_id} className={cn("rounded-xl border p-4", a.is_correct === true ? "border-ok/50" : a.is_correct === false ? "border-bad/40" : "border-warn/50")}>
          <div className="flex items-start justify-between gap-2">
            <p className="font-semibold"><span className="mr-1 text-mute">{i + 1}.</span>{a.text}</p>
            {a.is_correct === true ? <CheckCircle2 className="shrink-0 text-ok" size={18} aria-label={t("quiz.right")} />
              : a.is_correct === false ? <XCircle className="shrink-0 text-bad" size={18} aria-label={t("quiz.wrong")} /> : <Badge tone="warn">{t("quiz.awaiting")}</Badge>}
          </div>
          <p className="mt-1 text-sm"><span className="text-mute">{t("quiz.yourAnswer")}:</span> {fmtAnswer(a, a.your_answer, t)}</p>
          {a.qtype !== "descriptive" || a.correct_answer ? (
            <p className="text-sm"><span className="text-mute">{t("quiz.correctAnswer")}:</span> <b>{fmtAnswer(a, a.correct_answer, t)}</b></p>
          ) : null}
          <p className="mt-1 text-xs text-mute">{a.marks_awarded ?? "—"} / {a.marks} {t("quiz.marks").toLowerCase()}{a.topic && ` · ${a.topic}`}</p>
          {a.explanation && <p className="mt-2 rounded-lg bg-soft p-2 text-sm">{a.explanation}</p>}
          {a.feedback && !canGrade && <p className="mt-2 text-sm"><b>{t("quiz.feedback")}:</b> {a.feedback}</p>}
          {canGrade && a.qtype === "descriptive" && a.answer_id > 0 && a.your_answer !== null && a.your_answer !== "" && (
            <Grader a={a} onDone={() => { qc.invalidateQueries({ queryKey: ["attempt", attemptId] }); qc.invalidateQueries({ queryKey: ["quiz-attempts"] }); qc.invalidateQueries({ queryKey: ["quizzes"] }); onChanged?.(); }} />
          )}
        </div>
      ))}
    </div>
  );
}

function AttemptsDialog({ quiz, onClose }: { quiz: Quiz; onClose: () => void }) {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  const q = useQuery({ queryKey: ["quiz-attempts", quiz.id], queryFn: () => get<AttemptRow[]>(`/quizzes/${quiz.id}/attempts`) });
  const [sel, setSel] = useState<number | null>(null);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={quiz.title} description={t("quiz.studentResults")} className="max-w-3xl">
        {sel ? (
          <>
            <Button variant="ghost" size="sm" className="mb-3" onClick={() => setSel(null)}>← {t("common.back")}</Button>
            <AttemptView attemptId={sel} canGrade={role === "teacher"} />
          </>
        ) : q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} /> : (
          <Table className="min-w-[480px]">
            <thead><tr><Th>{t("students.roll")}</Th><Th>{t("students.fullName")}</Th><Th>{t("att.status")}</Th><Th>{t("quiz.score")}</Th><Th /></tr></thead>
            <tbody>
              {q.data?.map((r) => (
                <Tr key={r.student_id}>
                  <Td>{r.roll_no ?? "—"}</Td><Td className="font-semibold">{r.full_name}</Td>
                  <Td>{r.attempt ? <Badge tone={r.attempt.status === "graded" ? "ok" : r.attempt.status === "submitted" ? "warn" : "mute"}>{t(`quiz.${r.attempt.status === "in_progress" ? "resume" : r.attempt.status}`)}</Badge> : <Badge tone="mute">{t("quiz.notTaken")}</Badge>}</Td>
                  <Td>{r.attempt && r.attempt.status !== "in_progress" ? `${r.attempt.score} / ${r.attempt.max_score}` : "—"}</Td>
                  <Td className="text-right">{r.attempt_id && r.attempt?.status !== "in_progress" && <Button size="sm" variant="soft" onClick={() => setSel(r.attempt_id)}>{t("common.view")}</Button>}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ player (student)
function Countdown({ deadline, onExpire }: { deadline: string; onExpire: () => void }) {
  const { t } = useTranslation();
  const end = new Date(deadline).getTime();
  const [left, setLeft] = useState(Math.max(0, end - Date.now()));
  useEffect(() => {
    const id = setInterval(() => setLeft(Math.max(0, end - Date.now())), 1000);
    return () => clearInterval(id);
  }, [end]);
  const fired = useRef(false);
  useEffect(() => { if (left <= 0 && !fired.current) { fired.current = true; onExpire(); } }, [left, onExpire]);
  const s = Math.ceil(left / 1000);
  return <Badge tone={s < 60 ? "bad" : "default"} className="gap-1 text-sm" role="timer" aria-label={t("quiz.timeLeft")}><Timer size={14} />{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</Badge>;
}

function PlayerDialog({ quiz, onClose }: { quiz: Quiz; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const play = useQuery({ queryKey: ["play", quiz.id], queryFn: () => post<AttemptPlay>(`/quizzes/${quiz.id}/attempts`), staleTime: Infinity, gcTime: 0, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false });
  const [ans, setAns] = useState<Record<number, number | boolean | string>>({});
  const [done, setDone] = useState<number | null>(null);
  const submit = useMutation({
    mutationFn: () => post<AttemptResult>(`/attempts/${play.data!.attempt_id}/submit`, { answers: Object.entries(ans).map(([k, v]) => ({ question_id: Number(k), answer: v })) }),
    onSuccess: (r) => { setDone(r.id); qc.invalidateQueries({ queryKey: ["quizzes"] }); if (r.timed_out) toastError(new Error(t("quiz.timedOut"))); }, onError: toastError,
  });
  const expire = () => { if (!submit.isPending && !submit.isSuccess) submit.mutate(); };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={quiz.title} description={quiz.description} className="max-w-2xl">
        {done ? <AttemptView attemptId={done} canGrade={false} /> : play.isLoading ? <Loading /> : play.isError || !play.data ? <ErrorState error={play.error} /> : (
          <form onSubmit={(e) => { e.preventDefault(); if (confirm(t("quiz.submitConfirm"))) submit.mutate(); }} className="space-y-4">
            {play.data.deadline && <div className="sticky top-0 z-10 flex justify-end bg-card py-1"><Countdown deadline={play.data.deadline} onExpire={expire} /></div>}
            {play.data.questions.map((q, i) => (
              <fieldset key={q.id} className="rounded-xl border border-line p-4">
                <legend className="px-1 text-xs font-semibold text-mute">{t("quiz.qno", { n: i + 1 })} · {q.marks} {t("quiz.marks").toLowerCase()}</legend>
                <p className="mb-3 font-semibold">{q.text}</p>
                {q.qtype === "mcq" && q.options.map((o, k) => (
                  <label key={k} className={cn("mb-2 flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-sm", ans[q.id] === k ? "border-primary bg-soft" : "border-line")}>
                    <input type="radio" name={`q-${q.id}`} checked={ans[q.id] === k} onChange={() => setAns({ ...ans, [q.id]: k })} className="accent-[hsl(var(--ac))]" />{o}
                  </label>
                ))}
                {q.qtype === "true_false" && [true, false].map((v) => (
                  <label key={String(v)} className={cn("mb-2 flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-sm", ans[q.id] === v ? "border-primary bg-soft" : "border-line")}>
                    <input type="radio" name={`q-${q.id}`} checked={ans[q.id] === v} onChange={() => setAns({ ...ans, [q.id]: v })} className="accent-[hsl(var(--ac))]" />{t(v ? "quiz.true" : "quiz.false")}
                  </label>
                ))}
                {q.qtype === "fill_blank" && <Input maxLength={200} value={String(ans[q.id] ?? "")} onChange={(e) => setAns({ ...ans, [q.id]: e.target.value })} aria-label={q.text} />}
                {q.qtype === "descriptive" && <Textarea rows={4} maxLength={5000} value={String(ans[q.id] ?? "")} onChange={(e) => setAns({ ...ans, [q.id]: e.target.value })} aria-label={q.text} />}
              </fieldset>
            ))}
            <Button type="submit" className="w-full" disabled={submit.isPending}>{t("quiz.submit")}</Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ list
function QuizList({ childId }: { childId?: number }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user!.role);
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const q = useQuery({ queryKey: ["quizzes", role, childId], queryFn: () => get<Quiz[]>(`/quizzes${childId ? `?child_id=${childId}` : ""}`) });
  const [builder, setBuilder] = useState<{ q: QuizDetail | null } | null>(null);
  const [pdf, setPdf] = useState(false);
  const [results, setResults] = useState<Quiz | null>(null);
  const [playing, setPlaying] = useState<Quiz | null>(null);
  const [viewAttempt, setViewAttempt] = useState<number | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["quizzes"] });
  const act = useMutation({ mutationFn: (p: { id: number; verb: "publish" | "close" }) => post(`/quizzes/${p.id}/${p.verb}`), onSuccess: () => { refresh(); toast(t("quiz.publishedOk")); }, onError: toastError });
  const rm = useMutation({ mutationFn: (id: number) => del(`/quizzes/${id}`), onSuccess: refresh, onError: toastError });
  const edit = useMutation({ mutationFn: (id: number) => get<QuizDetail>(`/quizzes/${id}`), onSuccess: (d) => setBuilder({ q: d }), onError: toastError });
  const staff = role === "teacher" || role === "admin";

  return (
    <>
      {role === "teacher" && (
        <div className="mb-4 flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={() => setPdf(true)}><FileUp size={16} />{t("quiz.fromPdf")}</Button>
          <Button onClick={() => setBuilder({ q: null })}><Plus size={16} />{t("quiz.new")}</Button>
        </div>
      )}
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? <EmptyState text={t("quiz.none")} /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {q.data.map((x) => {
            const my = x.my_attempt;
            return (
              <Card key={x.id} className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-bold">{x.title}</h3>
                    <p className="mt-0.5 text-xs text-mute">{subjectName(subjects.data, x.subject_id)} · {sectionLabel(sections.data, classes.data, x.section_id)}{x.time_limit_minutes ? ` · ${x.time_limit_minutes} min` : ""}</p>
                  </div>
                  <span className="flex flex-wrap justify-end gap-1.5">
                    {x.source === "pdf" && <Badge>{t("quiz.aiDraft")}</Badge>}
                    <Badge tone={statusTone[x.status]}>{t(`quiz.${x.status}`)}</Badge>
                  </span>
                </div>
                {x.description && <p className="mt-3 text-sm">{x.description}</p>}
                <p className="mt-3 text-sm text-mute">{t("quiz.questionsCount", { n: x.question_count, m: x.total_marks })}</p>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {staff && x.attempt_count !== null && <Badge tone="mute">{t("quiz.attemptsCount", { n: x.attempt_count })}</Badge>}
                  {staff && !!x.pending_grading && <Badge tone="warn">{t("quiz.toGrade", { n: x.pending_grading })}</Badge>}
                  {staff && <Button size="sm" variant="outline" onClick={() => setResults(x)}>{t("quiz.results")}</Button>}
                  {role === "teacher" && !x.attempt_count && <Button size="sm" variant="soft" onClick={() => edit.mutate(x.id)}><Pencil size={14} />{t("quiz.edit")}</Button>}
                  {role === "teacher" && x.status === "draft" && <Button size="sm" onClick={() => act.mutate({ id: x.id, verb: "publish" })}>{t("quiz.publish")}</Button>}
                  {role === "teacher" && x.status === "published" && <Button size="sm" variant="outline" onClick={() => act.mutate({ id: x.id, verb: "close" })}>{t("quiz.close")}</Button>}
                  {role === "student" && (!my || my.status === "in_progress") && x.status === "published" && <Button size="sm" onClick={() => setPlaying(x)}>{my ? t("quiz.resume") : t("quiz.start")}</Button>}
                  {!staff && my && my.status !== "in_progress" && (
                    <>
                      <Badge tone={my.status === "graded" ? "ok" : "warn"}>{my.status === "graded" ? `${my.score} / ${my.max_score}` : t("quiz.awaiting")}</Badge>
                      <Button size="sm" variant="soft" onClick={() => setViewAttempt(my.id)}>{t("quiz.viewResult")}</Button>
                    </>
                  )}
                  {!staff && !my && role === "parent" && <Badge tone="mute">{t("quiz.notTaken")}</Badge>}
                  {staff && <Button size="icon" variant="ghost" className="ml-auto" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && rm.mutate(x.id)}><Trash2 size={16} className="text-bad" /></Button>}
                </div>
              </Card>
            );
          })}
        </div>
      )}
      {builder && <BuilderDialog initial={builder.q} onClose={() => setBuilder(null)} />}
      {pdf && <PdfDialog onClose={() => setPdf(false)} onDrafted={(d) => { setPdf(false); refresh(); toast(t("quiz.reviewDraft")); setBuilder({ q: d }); }} />}
      {results && <AttemptsDialog quiz={results} onClose={() => setResults(null)} />}
      {playing && <PlayerDialog quiz={playing} onClose={() => setPlaying(null)} />}
      {viewAttempt && (
        <Dialog open onOpenChange={(o) => !o && setViewAttempt(null)}>
          <DialogContent title={t("quiz.viewResult")} className="max-w-2xl"><AttemptView attemptId={viewAttempt} canGrade={false} /></DialogContent>
        </Dialog>
      )}
    </>
  );
}

export default function QuizzesPage() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  return (
    <>
      <PageHeader title={t("nav.quizzes")} subtitle={role === "admin" ? t("quiz.adminHint") : undefined} />
      {role === "parent" ? <WithChild>{(c) => <QuizList key={c.id} childId={c.id} />}</WithChild> : <QuizList />}
    </>
  );
}
