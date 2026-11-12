import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loading, PageHeader } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { get, patch } from "@/lib/api";

interface School { name: string; code: string; address: string; district: string; mandal: string; default_language: string; headmaster_name: string; headmaster_phone: string }
interface Year { id: number; label: string; start_date: string; end_date: string; is_current: boolean }

export default function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const school = useQuery({ queryKey: ["school"], queryFn: () => get<School>("/school") });
  const years = useQuery({ queryKey: ["years"], queryFn: () => get<Year[]>("/academic-years") });
  const [f, setF] = useState<School | null>(null);
  useEffect(() => { if (school.data) setF(school.data); }, [school.data]);
  const save = useMutation({
    mutationFn: () => patch<School>("/school", f),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["school"] }); toast(t("common.saved")); },
    onError: toastError,
  });
  if (!f) return <Loading />;
  const set = (k: keyof School) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };

  return (
    <>
      <PageHeader title={t("settings.title")} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent>
            <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
              <Field label={t("settings.name")}><Input value={f.name} onChange={set("name")} required /></Field>
              <Field label={t("settings.code")}><Input value={f.code} disabled /></Field>
              <Field label={t("settings.address")}><Input value={f.address} onChange={set("address")} /></Field>
              <Field label={t("settings.defaultLanguage")}>
                <Select value={f.default_language} onChange={set("default_language")}>
                  <option value="en">English</option><option value="te">తెలుగు</option><option value="hi">हिन्दी</option>
                </Select>
              </Field>
              <Field label={t("settings.district")}><Input value={f.district} onChange={set("district")} /></Field>
              <Field label={t("settings.mandal")}><Input value={f.mandal} onChange={set("mandal")} /></Field>
              <Field label={t("settings.headmaster")}><Input value={f.headmaster_name} onChange={set("headmaster_name")} /></Field>
              <Field label={t("settings.headmasterPhone")}><Input value={f.headmaster_phone} onChange={set("headmaster_phone")} /></Field>
              <Button type="submit" className="sm:col-span-2" disabled={save.isPending}>{t("common.save")}</Button>
            </form>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("settings.year")}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {years.data?.map((y) => (
              <div key={y.id} className="flex items-center justify-between rounded-xl border border-line p-3 text-sm">
                <div><div className="font-bold">{y.label}</div><div className="text-xs text-mute">{y.start_date} → {y.end_date}</div></div>
                {y.is_current && <Badge tone="ok">●</Badge>}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
