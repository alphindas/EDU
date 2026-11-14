import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loading, PageHeader } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { del, patch, post } from "@/lib/api";
import { sectionLabel, useAllTeachers, useAssignments, useClasses, useSections, useSubjects } from "@/lib/queries";

export default function Structure() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const classes = useClasses();
  const sections = useSections();
  const subjects = useSubjects();
  const teachers = useAllTeachers();
  const assignments = useAssignments();
  const refresh = (k: string) => qc.invalidateQueries({ queryKey: [k] });
  const useAction = <V,>(fn: (v: V) => Promise<unknown>, key: string) =>
    useMutation({ mutationFn: fn, onSuccess: () => { refresh(key); toast(t("common.saved")); }, onError: toastError });

  const addClass = useAction((name: string) => post("/classes", { name, sort_order: Number(name) || 0 }), "classes");
  const delClass = useAction((id: number) => del(`/classes/${id}`), "classes");
  const addSection = useAction((v: { class_id: number; name: string }) => post("/sections", v), "sections");
  const delSection = useAction((id: number) => del(`/sections/${id}`), "sections");
  const setTeacher = useAction((v: { id: number; class_teacher_id: number | null }) => patch(`/sections/${v.id}`, { class_teacher_id: v.class_teacher_id }), "sections");
  const addSubject = useAction((name: string) => post("/subjects", { name }), "subjects");
  const delSubject = useAction((id: number) => del(`/subjects/${id}`), "subjects");
  const addAssign = useAction((v: { teacher_id: number; section_id: number; subject_id: number }) => post("/assignments", v), "assignments");
  const delAssign = useAction((id: number) => del(`/assignments/${id}`), "assignments");

  const [cls, setCls] = useState("");
  const [sub, setSub] = useState("");
  const [secClass, setSecClass] = useState("");
  const [secName, setSecName] = useState("");
  const [a, setA] = useState({ teacher: "", section: "", subject: "" });

  if (classes.isLoading || sections.isLoading || subjects.isLoading) return <Loading />;
  const tname = (id: number) => teachers.data?.items.find((x) => x.id === id)?.full_name ?? "—";
  const sname = (id: number) => subjects.data?.find((x) => x.id === id)?.name ?? "—";
  const submit = (fn: () => void) => (e: FormEvent) => { e.preventDefault(); fn(); };
  const confirmDel = (fn: () => void) => () => confirm(t("common.confirmDelete")) && fn();

  return (
    <>
      <PageHeader title={t("nav.structure")} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>{t("structure.classes")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={submit(() => { addClass.mutate(cls); setCls(""); })} className="flex gap-2">
              <Input value={cls} onChange={(e) => setCls(e.target.value)} placeholder={t("structure.className")} required aria-label={t("structure.className")} />
              <Button type="submit"><Plus size={16} />{t("common.add")}</Button>
            </form>
            <div className="flex flex-wrap gap-2">
              {classes.data?.map((c) => (
                <Badge key={c.id} className="gap-1.5 py-1.5 pl-3 text-sm">
                  {c.name}
                  <button aria-label={t("common.delete")} onClick={confirmDel(() => delClass.mutate(c.id))}><Trash2 size={13} className="text-bad" /></button>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("structure.subjects")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={submit(() => { addSubject.mutate(sub); setSub(""); })} className="flex gap-2">
              <Input value={sub} onChange={(e) => setSub(e.target.value)} placeholder={t("structure.subjectName")} required aria-label={t("structure.subjectName")} />
              <Button type="submit"><Plus size={16} />{t("common.add")}</Button>
            </form>
            <div className="flex flex-wrap gap-2">
              {subjects.data?.map((s) => (
                <Badge key={s.id} tone="mute" className="gap-1.5 py-1.5 pl-3 text-sm">
                  {s.name}
                  <button aria-label={t("common.delete")} onClick={confirmDel(() => delSubject.mutate(s.id))}><Trash2 size={13} className="text-bad" /></button>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>{t("structure.sections")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={submit(() => { addSection.mutate({ class_id: Number(secClass), name: secName }); setSecName(""); })} className="flex flex-wrap gap-2">
              <Select className="w-32" value={secClass} onChange={(e) => setSecClass(e.target.value)} required aria-label={t("students.class")}>
                <option value="">{t("students.class")}</option>
                {classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
              <Input className="w-48" value={secName} onChange={(e) => setSecName(e.target.value)} placeholder={t("structure.sectionName")} required aria-label={t("structure.sectionName")} />
              <Button type="submit"><Plus size={16} />{t("structure.addSection")}</Button>
            </form>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {sections.data?.map((s) => (
                <div key={s.id} className="rounded-xl border border-line p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-lg font-extrabold">{sectionLabel(sections.data, classes.data, s.id)}</span>
                    <button aria-label={t("common.delete")} onClick={confirmDel(() => delSection.mutate(s.id))}><Trash2 size={15} className="text-bad" /></button>
                  </div>
                  <label className="mb-1 block text-xs font-semibold uppercase text-mute">{t("structure.classTeacher")}</label>
                  <Select value={s.class_teacher_id ?? ""} onChange={(e) => setTeacher.mutate({ id: s.id, class_teacher_id: e.target.value ? Number(e.target.value) : null })}>
                    <option value="">{t("structure.none")}</option>
                    {teachers.data?.items.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
                  </Select>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>{t("structure.assignments")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <form
              onSubmit={submit(() => addAssign.mutate({ teacher_id: Number(a.teacher), section_id: Number(a.section), subject_id: Number(a.subject) }))}
              className="flex flex-wrap gap-2"
            >
              <Select className="w-auto" value={a.teacher} onChange={(e) => setA({ ...a, teacher: e.target.value })} required aria-label={t("structure.teacher")}>
                <option value="">{t("structure.teacher")}</option>
                {teachers.data?.items.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.full_name}</option>)}
              </Select>
              <Select className="w-auto" value={a.section} onChange={(e) => setA({ ...a, section: e.target.value })} required aria-label={t("structure.section")}>
                <option value="">{t("structure.section")}</option>
                {sections.data?.map((s) => <option key={s.id} value={s.id}>{sectionLabel(sections.data, classes.data, s.id)}</option>)}
              </Select>
              <Select className="w-auto" value={a.subject} onChange={(e) => setA({ ...a, subject: e.target.value })} required aria-label={t("structure.subject")}>
                <option value="">{t("structure.subject")}</option>
                {subjects.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
              <Button type="submit"><Plus size={16} />{t("structure.assign")}</Button>
            </form>
            <div className="flex flex-wrap gap-2">
              {assignments.data?.map((x) => (
                <Badge key={x.id} className="gap-1.5 py-1.5 pl-3 text-sm">
                  {tname(x.teacher_id)} · {sname(x.subject_id)} · {sectionLabel(sections.data, classes.data, x.section_id)}
                  <button aria-label={t("common.delete")} onClick={confirmDel(() => delAssign.mutate(x.id))}><Trash2 size={13} className="text-bad" /></button>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
