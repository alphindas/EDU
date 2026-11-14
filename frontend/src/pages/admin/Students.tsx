import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import StudentsTable from "@/components/common/StudentsTable";
import { toast, toastError } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { post } from "@/lib/api";
import { sectionLabel, useClasses, useSections } from "@/lib/queries";
import type { Student } from "@/lib/types";

const blank = { admission_no: "", full_name: "", class_id: "", section_id: "", roll_no: "", dob: "", gender: "", parent_mobile: "", parent_name: "", address: "" };

export default function Students() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const classes = useClasses();
  const sections = useSections();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [created, setCreated] = useState<Student | null>(null);
  const set = (k: keyof typeof blank) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  const create = useMutation({
    mutationFn: () => post<Student>("/students", { ...form, class_id: Number(form.class_id), section_id: Number(form.section_id), roll_no: form.roll_no ? Number(form.roll_no) : null }),
    onSuccess: (s) => { qc.invalidateQueries({ queryKey: ["students"] }); qc.invalidateQueries({ queryKey: ["parents"] }); setCreated(s); setForm(blank); },
    onError: toastError,
  });
  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };

  return (
    <>
      <PageHeader
        title={t("students.title")}
        actions={
          <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setCreated(null); }}>
            <DialogTrigger asChild><Button><Plus size={16} />{t("students.add")}</Button></DialogTrigger>
            <DialogContent title={t("students.add")} className="max-w-2xl">
              {created ? (
                <div className="space-y-4">
                  <p className="rounded-xl bg-ok/10 p-3 text-sm text-ok">{t("students.created")}</p>
                  <Field label={`${created.full_name} · ${created.admission_no}`} hint={t("students.firstLoginNote")}>
                    <div className="flex gap-2">
                      <Input readOnly value={created.temp_password ?? ""} className="font-mono" />
                      <Button type="button" variant="outline" onClick={() => { navigator.clipboard?.writeText(created.temp_password ?? ""); toast(t("common.copy")); }}><Copy size={16} /></Button>
                    </div>
                  </Field>
                  <Button className="w-full" onClick={() => setOpen(false)}>{t("common.close")}</Button>
                </div>
              ) : (
                <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
                  <Field label={t("students.admissionNo")}><Input value={form.admission_no} onChange={set("admission_no")} required /></Field>
                  <Field label={t("students.fullName")}><Input value={form.full_name} onChange={set("full_name")} required /></Field>
                  <Field label={t("students.class")}>
                    <Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value, section_id: "" })} required>
                      <option value="" />{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </Select>
                  </Field>
                  <Field label={t("students.section")}>
                    <Select value={form.section_id} onChange={set("section_id")} required>
                      <option value="" />
                      {sections.data?.filter((s) => String(s.class_id) === form.class_id).map((s) => <option key={s.id} value={s.id}>{sectionLabel(sections.data, classes.data, s.id)}</option>)}
                    </Select>
                  </Field>
                  <Field label={t("students.dob")}><Input type="date" value={form.dob} onChange={set("dob")} required /></Field>
                  <Field label={t("students.roll")}><Input type="number" min={1} value={form.roll_no} onChange={set("roll_no")} /></Field>
                  <Field label={t("students.gender")}>
                    <Select value={form.gender} onChange={set("gender")}>
                      <option value="" /><option value="M">{t("students.male")}</option><option value="F">{t("students.female")}</option><option value="O">{t("students.other")}</option>
                    </Select>
                  </Field>
                  <Field label={t("students.parentMobile")}><Input value={form.parent_mobile} onChange={set("parent_mobile")} inputMode="tel" minLength={6} required /></Field>
                  <Field label={t("students.parentName")}><Input value={form.parent_name} onChange={set("parent_name")} /></Field>
                  <Field label={t("students.address")}><Input value={form.address} onChange={set("address")} /></Field>
                  <Button type="submit" className="sm:col-span-2" disabled={create.isPending}>{t("common.save")}</Button>
                </form>
              )}
            </DialogContent>
          </Dialog>
        }
      />
      <StudentsTable canDelete />
    </>
  );
}
