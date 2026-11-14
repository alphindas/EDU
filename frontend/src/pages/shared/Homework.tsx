import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileButton } from "@/components/common/AuthFile";
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
import { api, del, get, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sectionLabel, subjectName, todayISO, useAssignments, useClasses, useSections, useSubjects } from "@/lib/queries";
import type { Homework, Submission, SubmissionRow } from "@/lib/types";

const subTone = { submitted: "default", reviewed: "ok", returned: "warn" } as const;

function SubmissionBadge({ s, due }: { s: Submission | null; due: string }) {
  const { t } = useTranslation();
  if (!s) return <Badge tone={due < todayISO() ? "bad" : "mute"}>{t("hw.pending")}</Badge>;
  return <span className="inline-flex gap-1.5"><Badge tone={subTone[s.status]}>{t(`hw.${s.status}`)}</Badge>{s.is_late && <Badge tone="warn">{t("hw.late")}</Badge>}</span>;
}

// ------------------------------------------------------------------ teacher/admin: submissions + review
function SubmissionsDialog({ hw, canReview, onClose }: { hw: Homework; canReview: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["hw-subs", hw.id], queryFn: () => get<SubmissionRow[]>(`/homework/${hw.id}/submissions`) });
  const [sel, setSel] = useState<Submission | null>(null);
  const [f, setF] = useState({ status: "reviewed", feedback: "", grade: "" });
  const review = useMutation({
    mutationFn: () => api(`/homework/submissions/${sel!.id}/review`, { method: "PATCH", json: f }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hw-subs", hw.id] }); qc.invalidateQueries({ queryKey: ["homework"] }); setSel(null); toast(t("common.saved")); }, onError: toastError,
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={hw.title} description={`${t("hw.due")}: ${hw.due_date}`} className="max-w-3xl">
        {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} /> : (
          <>
            <Table className="min-w-[520px]">
              <thead><tr><Th>{t("students.roll")}</Th><Th>{t("students.fullName")}</Th><Th>{t("att.status")}</Th><Th>{t("hw.answer")}</Th><Th /></tr></thead>
              <tbody>
                {q.data?.map((r) => (
                  <Tr key={r.student_id}>
                    <Td>{r.roll_no ?? "—"}</Td><Td className="font-semibold">{r.full_name}</Td>
                    <Td><SubmissionBadge s={r.submission} due={hw.due_date} /></Td>
                    <Td className="max-w-48">
                      {r.submission && (<>
                        {r.submission.text && <p className="line-clamp-2 text-xs text-mute">{r.submission.text}</p>}
                        {r.submission.original_name && <FileButton path={`/homework/submissions/${r.submission.id}/file`} name={r.submission.original_name} />}
                      </>)}
                    </Td>
                    <Td className="text-right">
                      {canReview && r.submission && <Button size="sm" variant="soft" onClick={() => { setSel(r.submission); setF({ status: "reviewed", feedback: r.submission!.feedback, grade: r.submission!.grade }); }}>{t("hw.review")}</Button>}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
            {sel && (
              <form onSubmit={(e) => { e.preventDefault(); review.mutate(); }} className="mt-4 grid gap-3 rounded-xl border border-line p-4 sm:grid-cols-2">
                <Field label={t("att.status")}>
                  <Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
                    <option value="reviewed">{t("hw.reviewed")}</option><option value="returned">{t("hw.returned")}</option>
                  </Select>
                </Field>
                <Field label={t("hw.grade")}><Input maxLength={20} value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })} /></Field>
                <div className="sm:col-span-2"><Field label={t("hw.feedback")}><Textarea rows={3} maxLength={2000} value={f.feedback} onChange={(e) => setF({ ...f, feedback: e.target.value })} /></Field></div>
                <div className="flex gap-2 sm:col-span-2"><Button type="submit" disabled={review.isPending}>{t("common.save")}</Button><Button type="button" variant="outline" onClick={() => setSel(null)}>{t("common.cancel")}</Button></div>
              </form>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ teacher: post
function PostDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user)!;
  const assignments = useAssignments();
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const mine = (assignments.data ?? []).filter((a) => a.teacher_id === user.teacher_id);
  const [f, setF] = useState({ section_id: "", subject_id: "", title: "", description: "", due_date: todayISO() });
  const [file, setFile] = useState<File | null>(null);
  const subjOpts = mine.filter((a) => String(a.section_id) === f.section_id);
  const post = useMutation({
    mutationFn: () => { const fd = new FormData(); Object.entries(f).forEach(([k, v]) => fd.set(k, v)); if (file) fd.set("file", file); return upload("POST", "/homework", fd); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast(t("common.saved")); onClose(); }, onError: toastError,
  });
  const secIds = [...new Set(mine.map((a) => a.section_id))];
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("hw.post")}>
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); post.mutate(); }} className="grid gap-3 sm:grid-cols-2">
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
          <div className="sm:col-span-2"><Field label={t("hw.titleField")}><Input required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("hw.description")}><Textarea rows={3} maxLength={5000} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field></div>
          <Field label={t("hw.due")}><Input type="date" required min={todayISO()} value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></Field>
          <Field label={t("hw.attachment")} hint={t("common.optional")}><Input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <div className="sm:col-span-2"><Button type="submit" className="w-full" disabled={post.isPending}>{t("hw.post")}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ student: submit
function SubmitDialog({ hw, onClose }: { hw: Homework; onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [text, setText] = useState(hw.my_submission?.text ?? "");
  const [file, setFile] = useState<File | null>(null);
  const send = useMutation({
    mutationFn: () => { const fd = new FormData(); fd.set("text", text); if (file) fd.set("file", file); return upload("POST", `/homework/${hw.id}/submissions`, fd); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast(t("hw.submittedOk")); onClose(); }, onError: toastError,
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={hw.title} description={hw.description}>
        <form onSubmit={(e) => { e.preventDefault(); send.mutate(); }} className="space-y-3">
          <Field label={t("hw.answer")}><Textarea rows={4} maxLength={10000} value={text} onChange={(e) => setText(e.target.value)} /></Field>
          <Field label={t("hw.file")} hint={t("hw.fileHint")}><Input type="file" accept="image/*,application/pdf,audio/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Button type="submit" className="w-full" disabled={send.isPending || (!text.trim() && !file)}><FileUp size={16} />{hw.my_submission ? t("hw.resubmit") : t("hw.submit")}</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ list
function HomeworkList({ childId }: { childId?: number }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user!.role);
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const q = useQuery({ queryKey: ["homework", role, childId], queryFn: () => get<Homework[]>(`/homework${childId ? `?child_id=${childId}` : ""}`) });
  const [posting, setPosting] = useState(false);
  const [viewing, setViewing] = useState<Homework | null>(null);
  const [submitting, setSubmitting] = useState<Homework | null>(null);
  const rm = useMutation({ mutationFn: (id: number) => del(`/homework/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["homework"] }), onError: toastError });
  const staff = role === "teacher" || role === "admin";

  return (
    <>
      {role === "teacher" && <div className="mb-4 flex justify-end"><Button onClick={() => setPosting(true)}><Plus size={16} />{t("hw.post")}</Button></div>}
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? <EmptyState text={t("hw.none")} /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {q.data.map((h) => (
            <Card key={h.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold">{h.title}</h3>
                  <p className="mt-0.5 text-xs text-mute">{subjectName(subjects.data, h.subject_id)} · {sectionLabel(sections.data, classes.data, h.section_id)} · {t("hw.due")} {h.due_date}</p>
                </div>
                {staff
                  ? <Badge tone={h.submitted_count === h.total_students ? "ok" : "default"}>{t("hw.completion", { done: h.submitted_count ?? 0, total: h.total_students ?? 0 })}</Badge>
                  : <SubmissionBadge s={h.my_submission} due={h.due_date} />}
              </div>
              {h.description && <p className="mt-3 whitespace-pre-wrap text-sm">{h.description}</p>}
              {h.my_submission && (h.my_submission.feedback || h.my_submission.grade) && (
                <p className="mt-3 rounded-xl bg-soft p-3 text-sm"><b>{t("hw.feedback")}:</b> {h.my_submission.feedback} {h.my_submission.grade && <Badge className="ml-1">{h.my_submission.grade}</Badge>}</p>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {h.attachment_name && <FileButton path={`/homework/${h.id}/attachment`} name={h.attachment_name} />}
                {staff && <Button size="sm" variant="outline" onClick={() => setViewing(h)}>{t("hw.submissions")}</Button>}
                {role === "student" && h.my_submission?.status !== "reviewed" && <Button size="sm" onClick={() => setSubmitting(h)}>{h.my_submission ? t("hw.resubmit") : t("hw.submit")}</Button>}
                {staff && <Button size="icon" variant="ghost" className="ml-auto" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && rm.mutate(h.id)}><Trash2 size={16} className="text-bad" /></Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      {posting && <PostDialog onClose={() => setPosting(false)} />}
      {viewing && <SubmissionsDialog hw={viewing} canReview={role === "teacher"} onClose={() => setViewing(null)} />}
      {submitting && <SubmitDialog hw={submitting} onClose={() => setSubmitting(null)} />}
    </>
  );
}

export default function HomeworkPage() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  return (
    <>
      <PageHeader title={t("nav.homework")} subtitle={role === "admin" ? t("hw.adminHint") : undefined} />
      {role === "parent" ? <WithChild>{(c) => <HomeworkList key={c.id} childId={c.id} />}</WithChild> : <HomeworkList />}
    </>
  );
}
