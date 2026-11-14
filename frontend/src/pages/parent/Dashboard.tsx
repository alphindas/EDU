import { Rocket } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader, greetingKey } from "@/components/common/bits";
import StudentCard from "@/components/common/StudentCard";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useMyChildren } from "@/lib/queries";
import { cn } from "@/lib/utils";

export default function ParentDashboard() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const kids = useMyChildren();
  const [sel, setSel] = useState<number | null>(null);
  if (kids.isLoading) return <Loading />;
  if (kids.isError) return <ErrorState error={kids.error} onRetry={() => kids.refetch()} />;
  const list = kids.data ?? [];
  const child = list.find((c) => c.id === sel) ?? list[0];

  return (
    <>
      <PageHeader title={`${t(greetingKey())}, ${user.full_name}`} subtitle={user.school?.name} />
      {!child ? <EmptyState /> : (
        <>
          {list.length > 1 && (
            <div className="mb-4 flex flex-wrap items-center gap-2" role="tablist" aria-label={t("dash.selectChild")}>
              <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-mute">{t("dash.selectChild")}</span>
              {list.map((c) => (
                <button key={c.id} role="tab" aria-selected={c.id === child.id} onClick={() => setSel(c.id)}
                  className={cn("rounded-full border px-4 py-1.5 text-sm font-semibold transition", c.id === child.id ? "grad-bg border-transparent text-white shadow-card" : "border-line bg-card text-mute hover:text-ink")}>
                  {c.full_name}
                </button>
              ))}
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2"><StudentCard s={child} /></div>
            <Card className="grad-bg border-0 text-white">
              <CardContent className="flex h-full flex-col justify-center gap-3">
                <Rocket size={28} /><h3 className="text-xl font-extrabold">{t("dash.nextUp")}</h3><p className="text-white/85">{t("dash.nextUpBody")}</p>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </>
  );
}
