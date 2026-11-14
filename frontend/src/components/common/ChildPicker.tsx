import type { ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading } from "@/components/common/bits";
import { useMyChildren } from "@/lib/queries";
import type { Student } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Parent pages: pick one of the linked children, then render children(child). */
export default function WithChild({ children }: { children: (child: Student) => ReactNode }) {
  const { t } = useTranslation();
  const kids = useMyChildren();
  const [sel, setSel] = useState<number | null>(null);
  if (kids.isLoading) return <Loading />;
  if (kids.isError) return <ErrorState error={kids.error} onRetry={() => kids.refetch()} />;
  const list = kids.data ?? [];
  const child = list.find((c) => c.id === sel) ?? list[0];
  if (!child) return <EmptyState />;
  return (
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
      {children(child)}
    </>
  );
}
