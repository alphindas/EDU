import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { AuthImage } from "@/components/common/AuthFile";
import { ErrorState, Loading } from "@/components/common/bits";
import { Button } from "@/components/ui/button";
import { get } from "@/lib/api";
import type { IdCard } from "@/lib/types";

export function CardFace({ c, qr }: { c: IdCard; qr?: React.ReactNode }) {
  const { t } = useTranslation();
  const initials = c.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("");
  const row = (k: string, v: string | number | null) => (<div><div className="text-[10px] font-semibold uppercase tracking-wide text-mute">{k}</div><div className="text-sm font-semibold">{v ?? "—"}</div></div>);
  return (
    <div className="mx-auto w-full max-w-sm overflow-hidden rounded-2xl border border-line bg-card shadow-card print:shadow-none">
      <div className="grad-bg p-4 text-center text-white">
        <div className="text-sm font-extrabold uppercase tracking-wide">{c.school_name}</div>
        <div className="text-[11px] text-white/80">{c.school_address}</div>
      </div>
      <div className="flex gap-4 p-4">
        <div className="grid h-24 w-20 shrink-0 place-items-center rounded-xl bg-soft text-2xl font-extrabold text-primary">{initials}</div>
        <div className="min-w-0">
          <div className="text-lg font-extrabold leading-tight">{c.full_name}</div>
          <div className="mt-1 text-xs text-mute">{t("idc.student")} · {c.academic_year}</div>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
            {row(t("dash.idCard"), c.admission_no)}{row(t("dash.class"), `${c.class_name}-${c.section_name}`)}
            {row(t("dash.roll"), c.roll_no)}{row(t("dash.dob"), c.dob)}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-line p-4">
        <div className="text-[11px] text-mute"><div>{t("students.parentMobile")}</div><div className="text-sm font-semibold text-ink">{c.parent_mobile}</div><div className="mt-1 font-mono">{c.school_code}</div></div>
        {qr}
      </div>
    </div>
  );
}

export default function IdCardView({ studentId }: { studentId: number }) {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["id-card", studentId], queryFn: () => get<IdCard>(`/students/${studentId}/id-card`) });
  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return (
    <div className="space-y-4">
      <CardFace c={q.data} qr={<AuthImage path={`/students/${studentId}/id-card/qr.png`} alt={t("idc.qr")} className="h-28 w-28 rounded-lg border border-line bg-white p-1" />} />
      <div className="flex justify-center print:hidden"><Button variant="outline" onClick={() => window.print()}><Printer size={16} />{t("idc.print")}</Button></div>
    </div>
  );
}
