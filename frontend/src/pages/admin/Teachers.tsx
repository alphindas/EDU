import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { del, patch, post } from "@/lib/api";
import { useAllTeachers } from "@/lib/queries";
import type { Teacher } from "@/lib/types";

const blank = { employee_id: "", full_name: "", phone: "", email: "", qualification: "", joining_date: "" };

export default function Teachers() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const list = useAllTeachers();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [created, setCreated] = useState<Teacher | null>(null);
  const inv = () => qc.invalidateQueries({ queryKey: ["teachers"] });

  const create = useMutation({
    mutationFn: () => post<Teacher>("/teachers", { ...form, joining_date: form.joining_date || null }),
    onSuccess: (tch) => { inv(); setCreated(tch); setForm(blank); },
    onError: toastError,
  });
  const toggle = useMutation({ mutationFn: (x: Teacher) => patch(`/teachers/${x.id}`, { is_active: !x.is_active }), onSuccess: inv, onError: toastError });
  const remove = useMutation({ mutationFn: (id: number) => del(`/teachers/${id}`), onSuccess: () => { inv(); toast(t("common.saved")); }, onError: toastError });
  const set = (k: keyof typeof blank) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };

  return (
    <>
      <PageHeader
        title={t("teachers.title")}
        actions={
          <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setCreated(null); }}>
            <DialogTrigger asChild><Button><Plus size={16} />{t("teachers.add")}</Button></DialogTrigger>
            <DialogContent title={t("teachers.add")}>
              {created ? (
                <div className="space-y-4">
                  <p className="rounded-xl bg-ok/10 p-3 text-sm text-ok">{t("teachers.created")}: <b>{created.full_name}</b> ({created.employee_id})</p>
                  <Field label={t("common.tempPassword")}>
                    <div className="flex gap-2">
                      <Input readOnly value={created.temp_password ?? ""} className="font-mono" />
                      <Button type="button" variant="outline" onClick={() => { navigator.clipboard?.writeText(created.temp_password ?? ""); toast(t("common.copy")); }}><Copy size={16} /></Button>
                    </div>
                  </Field>
                  <Button className="w-full" onClick={() => setOpen(false)}>{t("common.close")}</Button>
                </div>
              ) : (
                <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
                  <Field label={t("teachers.employeeId")}><Input value={form.employee_id} onChange={set("employee_id")} required /></Field>
                  <Field label={t("teachers.fullName")}><Input value={form.full_name} onChange={set("full_name")} required /></Field>
                  <Field label={t("teachers.phone")}><Input value={form.phone} onChange={set("phone")} inputMode="tel" /></Field>
                  <Field label={t("teachers.email")}><Input type="email" value={form.email} onChange={set("email")} /></Field>
                  <Field label={t("teachers.qualification")}><Input value={form.qualification} onChange={set("qualification")} /></Field>
                  <Field label={t("teachers.joining")}><Input type="date" value={form.joining_date} onChange={set("joining_date")} /></Field>
                  <Button type="submit" className="sm:col-span-2" disabled={create.isPending}>{t("common.save")}</Button>
                </form>
              )}
            </DialogContent>
          </Dialog>
        }
      />
      <Card>
        {list.isLoading ? <Loading /> : list.isError ? <ErrorState error={list.error} onRetry={() => list.refetch()} /> : !list.data?.items.length ? <EmptyState /> : (
          <Table>
            <thead><tr><Th>{t("teachers.employeeId")}</Th><Th>{t("common.name")}</Th><Th>{t("teachers.qualification")}</Th><Th>{t("teachers.phone")}</Th><Th>{t("teachers.status")}</Th><Th /></tr></thead>
            <tbody>
              {list.data.items.map((x) => (
                <Tr key={x.id}>
                  <Td className="font-mono text-xs">{x.employee_id}</Td>
                  <Td className="font-semibold">{x.full_name}</Td>
                  <Td className="text-mute">{x.qualification || "—"}</Td>
                  <Td className="text-mute">{x.phone || "—"}</Td>
                  <Td><button onClick={() => toggle.mutate(x)}><Badge tone={x.is_active ? "ok" : "mute"}>{x.is_active ? t("teachers.active") : t("teachers.inactive")}</Badge></button></Td>
                  <Td className="text-right">
                    <Button variant="ghost" size="icon" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && remove.mutate(x.id)}><Trash2 size={16} className="text-bad" /></Button>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
