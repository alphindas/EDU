import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loading, PageHeader } from "@/components/common/bits";
import SectionPicker from "@/components/common/SectionPicker";
import SectionTimetable from "@/components/common/SectionTimetable";
import { hhmm } from "@/components/common/TimetableGrid";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { del, patch, post } from "@/lib/api";
import { usePeriods, useSections } from "@/lib/queries";
import type { Period } from "@/lib/types";

const blank = { number: "", label: "", start_time: "09:00", end_time: "09:45", is_break: false };

export default function AdminTimetable() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const periods = usePeriods();
  const sections = useSections();
  const [section, setSection] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Period | null>(null);
  const [form, setForm] = useState(blank);
  useEffect(() => { if (section === null && sections.data?.length) setSection(sections.data[0].id); }, [sections.data, section]);
  const inv = () => { qc.invalidateQueries({ queryKey: ["periods"] }); qc.invalidateQueries({ queryKey: ["timetable"] }); };
  const body = () => ({ number: Number(form.number), label: form.label, start_time: form.start_time, end_time: form.end_time, is_break: form.is_break });
  const saveP = useMutation({
    mutationFn: () => (editing ? patch(`/periods/${editing.id}`, body()) : post("/periods", body())),
    onSuccess: () => { inv(); setOpen(false); toast(t("common.saved")); }, onError: toastError,
  });
  const rmP = useMutation({ mutationFn: (id: number) => del(`/periods/${id}`), onSuccess: inv, onError: toastError });
  const edit = (p: Period | null) => {
    setEditing(p);
    setForm(p ? { number: String(p.number), label: p.label, start_time: hhmm(p.start_time), end_time: hhmm(p.end_time), is_break: p.is_break } : { ...blank, number: String((periods.data?.length ?? 0) + 1) });
    setOpen(true);
  };
  const submit = (e: FormEvent) => { e.preventDefault(); saveP.mutate(); };
  if (periods.isLoading) return <Loading />;

  return (
    <>
      <PageHeader title={t("nav.timetable")} subtitle={t("tt.adminHint")} actions={<SectionPicker value={section} onChange={setSection} />} />
      {section !== null && <SectionTimetable key={section} sectionId={section} edit canUpload staff />}

      <Card className="mt-8">
        <div className="flex items-center justify-between p-4">
          <h2 className="font-bold">{t("tt.periods")}</h2>
          <Button size="sm" onClick={() => edit(null)}><Plus size={16} />{t("tt.addPeriod")}</Button>
        </div>
        <Table>
          <thead><tr><Th>#</Th><Th>{t("tt.label")}</Th><Th>{t("tt.time")}</Th><Th /><Th /></tr></thead>
          <tbody>
            {periods.data?.map((p) => (
              <Tr key={p.id}>
                <Td>{p.number}</Td><Td className="font-semibold">{p.label || "—"}</Td><Td>{hhmm(p.start_time)}–{hhmm(p.end_time)}</Td>
                <Td>{p.is_break && <Badge tone="mute">{t("tt.break")}</Badge>}</Td>
                <Td className="text-right">
                  <Button variant="ghost" size="icon" aria-label={t("common.edit")} onClick={() => edit(p)}><Pencil size={16} /></Button>
                  <Button variant="ghost" size="icon" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && rmP.mutate(p.id)}><Trash2 size={16} className="text-bad" /></Button>
                </Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title={editing ? t("common.edit") : t("tt.addPeriod")}>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <Field label="#"><Input type="number" min={1} max={15} required value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} /></Field>
            <Field label={t("tt.label")}><Input maxLength={40} value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} /></Field>
            <Field label={t("tt.start")}><Input type="time" required value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} /></Field>
            <Field label={t("tt.end")}><Input type="time" required value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} /></Field>
            <label className="flex items-center gap-2 text-sm font-medium sm:col-span-2"><input type="checkbox" checked={form.is_break} onChange={(e) => setForm({ ...form, is_break: e.target.checked })} />{t("tt.isBreak")}</label>
            <div className="sm:col-span-2"><Button type="submit" className="w-full" disabled={saveP.isPending}>{t("common.save")}</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
