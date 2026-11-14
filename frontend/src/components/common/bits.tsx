import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const PageHeader = ({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-mute">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
);

export const Spinner = ({ className }: { className?: string }) => <Loader2 className={cn("animate-spin text-primary", className)} />;

export const Loading = () => {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-mute" role="status">
      <Spinner /> {t("common.loading")}
    </div>
  );
};

export const EmptyState = ({ text, children }: { text?: string; children?: ReactNode }) => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 py-14 text-center text-mute">
      <Inbox size={36} className="opacity-60" />
      <p>{text ?? t("common.empty")}</p>
      {children}
    </div>
  );
};

export const ErrorState = ({ error, onRetry }: { error: unknown; onRetry?: () => void }) => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 py-14 text-center" role="alert">
      <AlertTriangle size={36} className="text-bad" />
      <p className="text-sm text-mute">{error instanceof Error ? error.message : t("common.error")}</p>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>{t("common.retry")}</Button>}
    </div>
  );
};

export const StatCard = ({ label, value, icon, tone = "primary" }: { label: string; value: ReactNode; icon: ReactNode; tone?: "primary" | "ok" | "warn" | "accent2" }) => (
  <Card className="flex items-center gap-4 p-5">
    <div className={cn("grid h-12 w-12 place-items-center rounded-xl text-white",
      tone === "primary" && "bg-primary", tone === "ok" && "bg-ok", tone === "warn" && "bg-warn", tone === "accent2" && "bg-accent2")}>
      {icon}
    </div>
    <div>
      <div className="text-2xl font-extrabold leading-none">{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-wide text-mute">{label}</div>
    </div>
  </Card>
);

export const greetingKey = () => {
  const h = new Date().getHours();
  return h < 12 ? "dash.greeting_morning" : h < 17 ? "dash.greeting_afternoon" : "dash.greeting_evening";
};
