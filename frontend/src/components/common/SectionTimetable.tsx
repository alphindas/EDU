import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { AuthImage } from "@/components/common/AuthFile";
import { EmptyState, ErrorState, Loading } from "@/components/common/bits";
import TimetableGrid from "@/components/common/TimetableGrid";
import { toast, toastError } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { del, get, put, upload } from "@/lib/api";
import { useAssignments, useAllTeachers, usePeriods, useSubjects } from "@/lib/queries";
import type { Period, Timetable, TtEntry } from "@/lib/types";

/** One section's timetable: grid (admin can edit cells) + teacher-uploaded image/text (teacher/admin can upload). */
export default function SectionTimetable({ sectionId, edit = false, canUpload = false, staff = false }: { sectionId: number; edit?: boolean; canUpload?: boolean; staff?: boolean }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const periods = usePeriods();
  const subjects = useSubjects();
  const teachers = useAllTeachers(staff);
  const assignments = useAssignments(staff);
  const q = useQuery({ queryKey: ["timetable", sectionId], queryFn: () => get<Timetable>(`/timetable/sections/${sectionId}`) });
  const [cell, setCell] = useState<{ day: number; period: Period; entry?: TtEntry } | null>(null);
  const [form, setForm] = useState({ subject_id: "", teacher_id: "", room: "" });
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const inv = () => qc.invalidateQueries({ queryKey: ["timetable"] });

  const save = useMutation({
    mutationFn: () => put("/timetable/entries", {
      section_id: sectionId, day: cell!.day, period_id: cell!.period.id, subject_id: Number(form.subject_id),
      teacher_id: form.teacher_id ? Number(form.teacher_id) : null, room: form.room,
    }),
    onSuccess: () => { inv(); setCell(null); toast(t("common.saved")); }, onError: toastError,
  });
  const clear = useMutation({ mutationFn: (id: number) => del(`/timetable/entries/${id}`), onSuccess: () => { inv(); setCell(null); }, onError: toastError });
  const up = useMutation({
    mutationFn: () => { const fd = new FormData(); fd.set("section_id", String(sectionId)); if (file) fd.set("file", file); else fd.set("text", text); return upload("POST", "/timetable/uploads", fd); },
    onSuccess: () => { inv(); setText(""); setFile(null); toast(t("tt.uploaded")); }, onError: toastError,
  });
  const rmUp = useMutation({ mutationFn: (id: number) => del(`/timetable/uploads/${id}`), onSuccess: inv, onError: toastError });

  if (q.isLoading || periods.isLoading) return <Loading />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const sname = (id: number) => subjects.data?.find((s) => s.id === id)?.name ?? "—";
  const tname = (id: number | null) => teachers.data?.items.find((x) => x.id === id)?.full_name;
  const eligible = (assignments.data ?? []).filter((a) => a.section_id === sectionId && String(a.subject_id) === form.subject_id);
  const latest = q.data.uploads[0];

  const openCell = (day: number, period: Period, entry?: TtEntry) => {
    setForm({ subject_id: entry ? String(entry.subject_id) : "", teacher_id: entry?.teacher_id ? String(entry.teacher_id) : "", room: entry?.room ?? "" });
    setCell({ day, period, entry });
  };
  const submitUp = (e: FormEvent) => { e.preventDefault(); up.mutate(); };

  return (
    <div className="space-y-6">
      {(q.data.entries.length > 0 || edit) && (
        <TimetableGrid periods={periods.data ?? []} entries={q.data.entries} onCell={edit ? openCell : undefined}
          cell={(e) => e && (<><div className="font-semibold">{sname(e.subject_id)}</div><div className="text-xs text-mute">{[tname(e.teacher_id), e.room].filter(Boolean).join(" · ")}</div></>)} />
      )}

      {latest ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("tt.uploadedTimetable")}</CardTitle>
            {canUpload && <Button variant="ghost" size="icon" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && rmUp.mutate(latest.id)}><Trash2 size={16} className="text-bad" /></Button>}
          </CardHeader>
          <CardContent>
            {latest.kind === "image"
              ? <AuthImage path={`/timetable/uploads/${latest.id}/file`} alt={t("tt.uploadedTimetable")} className="mx-auto max-h-[70vh] rounded-xl border border-line" />
              : <pre className="whitespace-pre-wrap font-sans text-sm">{latest.text}</pre>}
            <p className="mt-3 text-xs text-mute">{new Date(latest.created_at).toLocaleString()}</p>
          </CardContent>
        </Card>
      ) : !q.data.entries.length && !edit ? <EmptyState text={t("tt.none")} /> : null}

      {canUpload && (
        <Card>
          <CardHeader><CardTitle>{t("tt.upload")}</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={submitUp} className="grid gap-3 md:grid-cols-2">
              <Field label={t("tt.uploadImage")} hint="PNG / JPG / WebP"><Input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
              <Field label={t("tt.uploadText")}><Textarea rows={3} value={text} disabled={!!file} placeholder={t("tt.textPlaceholder")} onChange={(e) => setText(e.target.value)} /></Field>
              <div className="md:col-span-2"><Button type="submit" disabled={up.isPending || (!file && !text.trim())}><ImagePlus size={16} />{t("tt.upload")}</Button></div>
            </form>
          </CardContent>
        </Card>
      )}

      <Dialog open={!!cell} onOpenChange={(o) => !o && setCell(null)}>
        <DialogContent title={cell ? `${t(`tt.d${cell.day}`)} · ${cell.period.label || cell.period.number}` : ""}>
          <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-3">
            <Field label={t("structure.subject")}>
              <Select required value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value, teacher_id: "" })}>
                <option value="" disabled>—</option>
                {subjects.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label={t("structure.teacher")} hint={t("tt.teacherHint")}>
              <Select value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: e.target.value })}>
                <option value="">{t("structure.none")}</option>
                {eligible.map((a) => <option key={a.id} value={a.teacher_id}>{tname(a.teacher_id) ?? a.teacher_id}</option>)}
              </Select>
            </Field>
            <Field label={t("tt.room")}><Input maxLength={30} value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} /></Field>
            <div className="flex justify-between gap-2">
              {cell?.entry ? <Button type="button" variant="danger" onClick={() => clear.mutate(cell.entry!.id)}>{t("tt.clear")}</Button> : <span />}
              <Button type="submit" disabled={save.isPending || !form.subject_id}>{t("common.save")}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
