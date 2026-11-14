import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { FileButton } from "@/components/common/AuthFile";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import WithChild from "@/components/common/ChildPicker";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { del, get, post, put, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sectionLabel, subjectName, todayISO, useAssignments, useClasses, useSections, useSubjects } from "@/lib/queries";
import type { Exam, MarksSheet } from "@/lib/types";

// ------------------------------------------------------------------ create (teacher)
function NewExamDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user)!;
  const assignments = useAssignments();
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const mine = (assignments.data ?? []).filter((a) => a.teacher_id === user.teacher_id);
  const [f, setF] = useState({ name: "", kind: "main", section_id: "", subject_id: "", exam_date: todayISO(), max_marks: "100", pass_marks: "35" });
  const secIds = [...new Set(mine.map((a) => a.section_id))];
  const create = useMutation({
    mutationFn: () => post("/exams", { ...f, section_id: Number(f.section_id), subject_id: Number(f.subject_id), max_marks: Number(f.max_marks), pass_marks: Number(f.pass_marks) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exams"] }); toast(t("common.saved")); onClose(); }, onError: toastError,
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("exam.new")} description={f.kind === "mock" ? t("exam.mockNote") : undefined}>
        <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><Field label={t("exam.name")}><Input required maxLength={200} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field></div>
          <Field label={t("exam.kind")}>
            <Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="main">{t("exam.main")}</option><option value="mock">{t("exam.mock")}</option></Select>
          </Field>
          <Field label={t("exam.date")}><Input type="date" required value={f.exam_date} onChange={(e) => setF({ ...f, exam_date: e.target.value })} /></Field>
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
          <Field label={t("exam.maxMarks")}><Input type="number" required min={1} max={1000} step={0.5} value={f.max_marks} onChange={(e) => setF({ ...f, max_marks: e.target.value })} /></Field>
          <Field label={t("exam.passMarks")}><Input type="number" required min={0} max={Number(f.max_marks) || 1000} step={0.5} value={f.pass_marks} onChange={(e) => setF({ ...f, pass_marks: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Button type="submit" className="w-full" disabled={create.isPending}>{t("common.save")}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ marks sheet
function MarksDialog({ exam, canEdit, onClose }: { exam: Exam; canEdit: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["exam-marks", exam.id], queryFn: () => get<MarksSheet>(`/exams/${exam.id}/marks`) });
  const [edits, setEdits] = useState<Record<number, { marks: string; absent: boolean; remarks: string }>>({});
  const editable = canEdit && exam.status !== "published";
  const save = useMutation({
    mutationFn: () => put<MarksSheet>(`/exams/${exam.id}/marks`, { rows: Object.entries(edits).map(([id, v]) => ({ student_id: Number(id), marks: v.marks === "" ? null : Number(v.marks), absent: v.absent, remarks: v.remarks })) }),
    onSuccess: (d) => { qc.setQueryData(["exam-marks", exam.id], d); qc.invalidateQueries({ queryKey: ["exams"] }); setEdits({}); toast(t("exam.marksSaved")); }, onError: toastError,
  });
  const s = q.data?.stats;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={exam.name} description={t("exam.marksOf", { max: exam.max_marks })} className="max-w-3xl">
        {q.isLoading ? <Loading /> : q.isError || !q.data ? <ErrorState error={q.error} /> : (
          <>
            {s && (
              <div className="mb-3 flex flex-wrap gap-2 text-xs">
                <Badge tone="mute">{t("exam.entered", { done: s.entered, total: q.data.rows.length })}</Badge>
                {s.average !== null && <Badge>{t("exam.average")}: {s.average}</Badge>}
                {s.highest !== null && <Badge tone="ok">{t("exam.highest")}: {s.highest}</Badge>}
                {s.lowest !== null && <Badge tone="warn">{t("exam.lowest")}: {s.lowest}</Badge>}
                <Badge tone="ok">{t("exam.passed")}: {s.passed}</Badge><Badge tone="bad">{t("exam.failed")}: {s.failed}</Badge>
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); if (Object.keys(edits).length) save.mutate(); }}>
              <Table className="min-w-[520px]">
                <thead><tr><Th>{t("students.roll")}</Th><Th>{t("students.fullName")}</Th><Th>{t("exam.enterMarks")}</Th><Th>{t("exam.absent")}</Th><Th>{t("exam.remarks")}</Th></tr></thead>
                <tbody>
                  {q.data.rows.map((r) => {
                    const v = edits[r.student_id] ?? { marks: r.marks === null ? "" : String(r.marks), absent: r.absent, remarks: r.remarks };
                    const set = (p: Partial<typeof v>) => setEdits({ ...edits, [r.student_id]: { ...v, ...p } });
                    return (
                      <Tr key={r.student_id}>
                        <Td>{r.roll_no ?? "—"}</Td><Td className="font-semibold">{r.full_name}</Td>
                        <Td><Input className="h-9 w-24" type="number" min={0} max={exam.max_marks} step={0.5} disabled={!editable || v.absent} value={v.absent ? "" : v.marks} aria-label={`${r.full_name} ${t("exam.enterMarks")}`} onChange={(e) => set({ marks: e.target.value })} /></Td>
                        <Td><input type="checkbox" disabled={!editable} checked={v.absent} aria-label={`${r.full_name} ${t("exam.absent")}`} onChange={(e) => set({ absent: e.target.checked, marks: e.target.checked ? "" : v.marks })} className="h-4 w-4 accent-[hsl(var(--ac))]" /></Td>
                        <Td><Input className="h-9" maxLength={200} disabled={!editable} value={v.remarks} aria-label={`${r.full_name} ${t("exam.remarks")}`} onChange={(e) => set({ remarks: e.target.value })} /></Td>
                      </Tr>
                    );
                  })}
                </tbody>
              </Table>
              {editable && <Button type="submit" className="mt-4 w-full" disabled={save.isPending || !Object.keys(edits).length}>{t("exam.saveMarks")}</Button>}
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ paper + key upload (teacher)
function FilesDialog({ exam, onClose }: { exam: Exam; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const send = useMutation({
    mutationFn: ({ kind, file }: { kind: "paper" | "key"; file: File }) => { const fd = new FormData(); fd.set("kind", kind); fd.set("file", file); return upload("POST", `/exams/${exam.id}/papers`, fd); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exams"] }); toast(t("common.saved")); }, onError: toastError,
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={exam.name} description={t("exam.paperHint")}>
        <div className="space-y-4">
          {(["paper", "key"] as const).map((kind) => (
            <Field key={kind} label={t(`exam.${kind}`)} hint={(kind === "paper" ? exam.has_paper : exam.has_key) ? t("exam.replace") : undefined}>
              <Input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" disabled={send.isPending} onChange={(e) => { const f = e.target.files?.[0]; if (f) send.mutate({ kind, file: f }); e.target.value = ""; }} />
            </Field>
          ))}
          <div className="flex flex-wrap gap-2">
            {exam.has_paper && <FileButton path={`/exams/${exam.id}/papers/paper`} name={t("exam.paper")} />}
            {exam.has_key && <FileButton path={`/exams/${exam.id}/papers/key`} name={t("exam.key")} />}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ list
function ExamList({ childId }: { childId?: number }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user!.role);
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const q = useQuery({ queryKey: ["exams", role, childId], queryFn: () => get<Exam[]>(`/exams${childId ? `?child_id=${childId}` : ""}`) });
  const [creating, setCreating] = useState(false);
  const [marks, setMarks] = useState<Exam | null>(null);
  const [filesFor, setFilesFor] = useState<Exam | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["exams"] });
  const toggle = useMutation({ mutationFn: (p: { id: number; verb: "publish" | "unpublish" }) => post(`/exams/${p.id}/${p.verb}`), onSuccess: refresh, onError: toastError });
  const rm = useMutation({ mutationFn: (id: number) => del(`/exams/${id}`), onSuccess: refresh, onError: toastError });
  const staff = role === "teacher" || role === "admin";

  return (
    <>
      {role === "teacher" && <div className="mb-4 flex justify-end"><Button onClick={() => setCreating(true)}><Plus size={16} />{t("exam.new")}</Button></div>}
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? <EmptyState text={t("exam.none")} /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {q.data.map((e) => (
            <Card key={e.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold">{e.name}</h3>
                  <p className="mt-0.5 text-xs text-mute">{subjectName(subjects.data, e.subject_id)} · {sectionLabel(sections.data, classes.data, e.section_id)} · {e.exam_date} · {t("exam.maxMarks")} {e.max_marks}</p>
                </div>
                <span className="flex flex-wrap justify-end gap-1.5">
                  <Badge tone={e.kind === "main" ? "default" : "mute"}>{t(e.kind === "main" ? "exam.mainBadge" : "exam.mockBadge")}</Badge>
                  <Badge tone={e.status === "published" ? "ok" : "warn"}>{t(`exam.${e.status}`)}</Badge>
                </span>
              </div>
              {!staff && (
                <div className="mt-3 rounded-xl bg-soft p-3 text-sm">
                  {e.my_result ? (
                    e.my_result.absent ? <Badge tone="warn">{t("exam.absent")}</Badge> : (
                      <span className="flex flex-wrap items-center gap-2">
                        <b className="text-lg">{e.my_result.marks} / {e.max_marks}</b> <Badge tone="mute">{e.my_result.percentage}%</Badge>
                        <Badge tone={e.my_result.passed ? "ok" : "bad"}>{t(e.my_result.passed ? "exam.pass" : "exam.fail")}</Badge>
                        {e.my_result.remarks && <span className="text-mute">{e.my_result.remarks}</span>}
                      </span>
                    )
                  ) : <span className="text-mute">{t("exam.pending")}</span>}
                </div>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {staff && e.total_students !== null && <Badge tone={e.entered_count === e.total_students ? "ok" : "mute"}>{t("exam.entered", { done: e.entered_count ?? 0, total: e.total_students })}</Badge>}
                {staff && <Button size="sm" variant="outline" onClick={() => setMarks(e)}>{t("exam.enterMarks")}</Button>}
                {role === "teacher" && <Button size="sm" variant="soft" onClick={() => setFilesFor(e)}>{t("exam.files")}</Button>}
                {staff && e.status === "draft" && <Button size="sm" onClick={() => confirm(t("exam.publishConfirm")) && toggle.mutate({ id: e.id, verb: "publish" })}>{t("exam.publish")}</Button>}
                {staff && e.status === "published" && <Button size="sm" variant="outline" onClick={() => toggle.mutate({ id: e.id, verb: "unpublish" })}>{t("exam.unpublish")}</Button>}
                {!staff && e.has_paper && <FileButton path={`/exams/${e.id}/papers/paper`} name={t("exam.paper")} />}
                {staff && <Button size="icon" variant="ghost" className="ml-auto" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && rm.mutate(e.id)}><Trash2 size={16} className="text-bad" /></Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      {creating && <NewExamDialog onClose={() => setCreating(false)} />}
      {marks && <MarksDialog exam={marks} canEdit={role === "teacher"} onClose={() => setMarks(null)} />}
      {filesFor && <FilesDialog exam={filesFor} onClose={() => setFilesFor(null)} />}
    </>
  );
}

export default function ExamsPage() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  return (
    <>
      <PageHeader title={t("nav.exams")} subtitle={role === "admin" ? t("exam.adminHint") : undefined} />
      {role === "parent" ? <WithChild>{(c) => <ExamList key={c.id} childId={c.id} />}</WithChild> : <ExamList />}
    </>
  );
}
