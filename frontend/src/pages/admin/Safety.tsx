import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { get, put } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Admin: audit log, counsellor assignment (who may read the counselling inbox), CHITTI oversight. */
export default function Safety() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(0);
  const logs = useQuery({ queryKey: ["audit", action, page], queryFn: () => get<{ total: number; items: { id: number; user: string; role: string; action: string; path: string; status: number; detail: string; at: string }[] }>(`/audit-logs?limit=50&offset=${page * 50}${action ? `&action=${action}` : ""}`) });
  const flags = useQuery({ queryKey: ["flags"], queryFn: () => get<{ user_id: number; name: string; role: string; counsellor: boolean }[]>("/staff-flags") });
  const setFlag = useMutation({ mutationFn: (b: { id: number; on: boolean }) => put(`/staff-flags/${b.id}`, { counsellor: b.on }), onSuccess: () => qc.invalidateQueries({ queryKey: ["flags"] }), onError: toastError });
  const ov = useQuery({ queryKey: ["oversight"], queryFn: () => get<{ id: number; student: string; path: string; question: string; at: string }[]>("/chitti/oversight?limit=30") });
  return (
    <div>
      <PageHero title={t("safe.title")} subtitle={t("safe.sub")} emoji="🛡️" />
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <Card className="overflow-x-auto p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2"><h3 className="mr-auto font-display text-lg font-extrabold">📜 {t("safe.audit")}</h3>
            <Select className="w-40" value={action} onChange={(e) => { setAction(e.target.value); setPage(0); }}><option value="">{t("lib.all")}</option>{["POST", "PUT", "PATCH", "DELETE", "AI"].map((a) => <option key={a}>{a}</option>)}</Select></div>
          {logs.isLoading ? <Loading /> : !logs.data?.items.length ? <EmptyState /> : (
            <table className="w-full min-w-[640px] text-sm">
              <thead><tr className="text-left text-xs uppercase text-mute"><th className="pb-2">{t("safe.when")}</th><th>{t("safe.who")}</th><th>{t("safe.action")}</th><th>{t("safe.path")}</th><th>{t("safe.result")}</th></tr></thead>
              <tbody>{logs.data.items.map((l) => (
                <tr key={l.id} className="border-t border-line align-top">
                  <td className="whitespace-nowrap py-1.5 text-xs">{new Date(l.at).toLocaleString(i18n.language, { dateStyle: "short", timeStyle: "short" })}</td>
                  <td className="text-xs"><b>{l.user || "—"}</b> <span className="text-mute">{l.role}</span></td>
                  <td><span className={cn("chip", l.action === "AI" ? "bg-violet-100 text-violet-700" : l.action === "DELETE" ? "bg-rose-100 text-rose-700" : "bg-soft text-primary")}>{l.action}</span></td>
                  <td className="max-w-[18rem] truncate font-mono text-xs" title={l.detail}>{l.path}{l.detail && <div className="truncate text-mute">{l.detail}</div>}</td>
                  <td className={cn("text-xs font-bold", l.status >= 400 ? "text-bad" : "text-ok")}>{l.status || "—"}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
          <div className="mt-3 flex items-center gap-2"><Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>←</Button>
            <span className="text-xs text-mute">{page * 50 + 1}–{Math.min((page + 1) * 50, logs.data?.total ?? 0)} / {logs.data?.total ?? 0}</span>
            <Button size="sm" variant="outline" disabled={(page + 1) * 50 >= (logs.data?.total ?? 0)} onClick={() => setPage(page + 1)}>→</Button></div>
        </Card>
        <div className="space-y-4">
          <Card className="p-5">
            <h3 className="font-display text-lg font-extrabold">💗 {t("safe.counsellors")}</h3>
            <p className="mb-3 text-xs text-mute">{t("safe.counsellorsSub")}</p>
            <ul className="space-y-1.5">{(flags.data ?? []).map((f) => (
              <li key={f.user_id}><label className="flex cursor-pointer items-center gap-2 rounded-xl p-1.5 text-sm hover:bg-soft/60">
                <input type="checkbox" className="h-5 w-5 accent-rose-500" checked={f.counsellor} onChange={(e) => setFlag.mutate({ id: f.user_id, on: e.target.checked })} />
                <span className="flex-1 font-bold">{f.name}</span><span className="text-xs text-mute">{t(`roles.${f.role}`)}</span></label></li>))}</ul>
          </Card>
          <Card className="p-5">
            <h3 className="font-display text-lg font-extrabold">🤖 {t("safe.ai")}</h3>
            <p className="mb-3 text-xs text-mute">{t("ins.aiSub")}</p>
            {!ov.data?.length ? <EmptyState /> : <ul className="max-h-96 space-y-2 overflow-y-auto">{ov.data.map((r) => <li key={r.id} className="rounded-xl bg-soft/60 p-2 text-xs"><b>{r.student}</b> · {r.path.replace("/chitti/", "")}<p className="text-mute">{r.question}</p></li>)}</ul>}
          </Card>
        </div>
      </div>
    </div>
  );
}
