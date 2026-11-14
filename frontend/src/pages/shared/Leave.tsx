import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileButton } from "@/components/common/AuthFile";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { get, post, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { todayISO } from "@/lib/queries";
import type { Leave, LeaveStatus } from "@/lib/types";

const TYPES = ["sick", "casual", "family", "other"];
const tone: Record<LeaveStatus, "ok" | "bad" | "warn" | "mute"> = {
  approved: "ok", rejected: "bad", cancelled: "mute", pending_parent: "warn", pending_teacher: "warn", pending_admin: "warn",
};

function ApplyDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [f, setF] = useState({ leave_type: "sick", from_date: todayISO(), to_date: todayISO(), reason: "" });
  const [file, setFile] = useState<File | null>(null);
  const send = useMutation({
    mutationFn: () => { const fd = new FormData(); Object.entries(f).forEach(([k, v]) => fd.set(k, v)); if (file) fd.set("file", file); return upload("POST", "/leave", fd); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leave"] }); toast(t("leave.sent")); onClose(); }, onError: toastError,
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("leave.apply")}>
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); send.mutate(); }} className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><Field label={t("leave.type")}>
            <Select value={f.leave_type} onChange={(e) => setF({ ...f, leave_type: e.target.value })}>{TYPES.map((x) => <option key={x} value={x}>{t(`leave.types.${x}`)}</option>)}</Select>
          </Field></div>
          <Field label={t("leave.from")}><Input type="date" required min={todayISO()} value={f.from_date} onChange={(e) => setF({ ...f, from_date: e.target.value, to_date: e.target.value > f.to_date ? e.target.value : f.to_date })} /></Field>
          <Field label={t("leave.to")}><Input type="date" required min={f.from_date} value={f.to_date} onChange={(e) => setF({ ...f, to_date: e.target.value })} /></Field>
          <div className="sm:col-span-2"><Field label={t("leave.reason")}><Textarea rows={3} maxLength={2000} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field></div>
          <div className="sm:col-span-2"><Field label={t("leave.attachment")} hint={t("common.optional")}><Input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field></div>
          <div className="sm:col-span-2"><Button type="submit" className="w-full" disabled={send.isPending}>{t("leave.apply")}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function LeaveCard({ l }: { l: Leave }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [comment, setComment] = useState("");
  const inv = () => qc.invalidateQueries({ queryKey: ["leave"] });
  const decide = useMutation({ mutationFn: (decision: "approve" | "reject") => post(`/leave/${l.id}/decision`, { decision, comment }), onSuccess: () => { inv(); toast(t("common.saved")); }, onError: toastError });
  const cancel = useMutation({ mutationFn: () => post(`/leave/${l.id}/cancel`), onSuccess: inv, onError: toastError });
  const me = useAuth((s) => s.user!);
  const showName = me.role !== "student" && !(me.role === "teacher" && l.applicant_role === "teacher" && l.teacher_id === me.teacher_id);
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-bold">{showName && <>{l.applicant_name} · </>}{t(`leave.types.${l.leave_type}`)}</h3>
          <p className="text-xs text-mute">{l.from_date} → {l.to_date} · {t("leave.daysN", { count: l.days })}</p>
        </div>
        <Badge tone={tone[l.status]}>{t(`leave.status.${l.status}`)}</Badge>
      </div>
      {l.reason && <p className="mt-3 text-sm">{l.reason}</p>}
      {l.attachment_name && <div className="mt-2"><FileButton path={`/leave/${l.id}/attachment`} name={l.attachment_name} /></div>}
      {l.approvals.length > 0 && (
        <ol className="mt-3 space-y-1 border-l-2 border-line pl-3 text-xs">
          {l.approvals.map((a, i) => (
            <li key={i}><b>{t(`leave.step.${a.step}`)}</b> · {a.approver_name} · <span className={a.decision === "approved" ? "text-ok" : "text-bad"}>{t(`leave.decision.${a.decision}`)}</span>{a.comment && <> — “{a.comment}”</>}</li>
          ))}
        </ol>
      )}
      {l.can_act && (
        <div className="mt-4 space-y-2 rounded-xl bg-soft p-3">
          <Input placeholder={t("leave.comment")} maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} aria-label={t("leave.comment")} />
          <div className="flex gap-2">
            <Button size="sm" disabled={decide.isPending} onClick={() => decide.mutate("approve")}><Check size={14} />{t("leave.approve")}</Button>
            <Button size="sm" variant="danger" disabled={decide.isPending} onClick={() => decide.mutate("reject")}><X size={14} />{t("leave.reject")}</Button>
          </div>
        </div>
      )}
      {l.can_cancel && <Button className="mt-3" size="sm" variant="ghost" disabled={cancel.isPending} onClick={() => confirm(t("leave.confirmCancel")) && cancel.mutate()}>{t("leave.cancel")}</Button>}
    </Card>
  );
}

/** One page for all four roles: students/teachers apply, parents + class teachers + admin decide, admin views student leave. */
export default function LeavePage() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  const [applying, setApplying] = useState(false);
  const q = useQuery({ queryKey: ["leave"], queryFn: () => get<Leave[]>("/leave") });
  const canApply = role === "student" || role === "teacher";
  const todo = (q.data ?? []).filter((l) => l.can_act);
  const rest = (q.data ?? []).filter((l) => !l.can_act);
  return (
    <>
      <PageHeader title={t("nav.leave")} subtitle={t(`leave.hint_${role}`)} actions={canApply ? <Button onClick={() => setApplying(true)}><Plus size={16} />{t("leave.apply")}</Button> : undefined} />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? <EmptyState text={t("leave.none")} /> : (
        <div className="space-y-6">
          {todo.length > 0 && (<section><h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-warn">{t("leave.needsYou")} ({todo.length})</h2><div className="grid gap-4 lg:grid-cols-2">{todo.map((l) => <LeaveCard key={l.id} l={l} />)}</div></section>)}
          {rest.length > 0 && (<section>{todo.length > 0 && <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-mute">{t("leave.history")}</h2>}<div className="grid gap-4 lg:grid-cols-2">{rest.map((l) => <LeaveCard key={l.id} l={l} />)}</div></section>)}
        </div>
      )}
      {applying && <ApplyDialog onClose={() => setApplying(false)} />}
    </>
  );
}
