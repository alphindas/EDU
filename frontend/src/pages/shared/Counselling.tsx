import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Phone, Send, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import Chitti from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/label";
import { Select, Textarea } from "@/components/ui/input";
import { ApiError, get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Thread } from "@/lib/v2";
import { cn } from "@/lib/utils";

/** Students: private (optionally anonymous) chat with the school counsellor. Staff: inbox, only for counsellors. */
export default function Counselling() {
  const role = useAuth((s) => s.user?.role);
  return role === "student" ? <StudentView /> : <Inbox />;
}

function ThreadView({ th, staff }: { th: Thread; staff: boolean }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const send = useMutation({ mutationFn: (close: boolean) => post(`/counselling/${th.id}/messages`, { body: text, close }), onSuccess: () => { setText(""); qc.invalidateQueries({ queryKey: ["counsel"] }); }, onError: toastError });
  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="chip bg-rose-100 text-rose-700">{t(`counsel.topic.${th.topic}`)}</span>
        {th.anonymous ? <span className="chip bg-line"><Lock size={11} /> {t("counsel.anon")}</span> : staff && <span className="chip bg-soft text-primary">{th.student}</span>}
        <span className={cn("chip", th.status === "open" ? "bg-ok/15 text-ok" : "bg-line text-mute")}>{t(`counsel.status.${th.status}`)}</span>
        <span className="ml-auto text-xs text-mute">{new Date(th.created_at).toLocaleDateString(i18n.language)}</span>
      </div>
      <div className="space-y-2">
        {th.messages.map((m) => (
          <div key={m.id} className={cn("flex", m.from_staff === staff ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] rounded-3xl px-4 py-2 text-sm", m.from_staff ? "bg-emerald-50 dark:bg-soft" : "bg-soft dark:bg-soft")}>
              <div className="text-[10px] font-extrabold uppercase text-mute">{m.from_staff ? t("counsel.counsellor") : staff ? t("counsel.student") : t("counsel.you")}</div>
              <div className="whitespace-pre-wrap">{m.body}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("counsel.reply")} />
        <div className="flex flex-col gap-1">
          <Button disabled={!text.trim()} onClick={() => send.mutate(false)} aria-label={t("common.send")}><Send size={16} /></Button>
          {staff && th.status === "open" && <Button size="sm" variant="outline" disabled={!text.trim()} onClick={() => send.mutate(true)}>{t("counsel.close")}</Button>}
        </div>
      </div>
    </Card>
  );
}

function StudentView() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const mine = useQuery({ queryKey: ["counsel", "mine"], queryFn: () => get<Thread[]>("/counselling") });
  const [f, setF] = useState({ topic: "talk", anonymous: true, body: "" });
  const open = useMutation({ mutationFn: () => post("/counselling", f), onSuccess: () => { setF({ ...f, body: "" }); qc.invalidateQueries({ queryKey: ["counsel"] }); }, onError: toastError });
  return (
    <div>
      <PageHero title={t("counsel.title")} subtitle={t("counsel.sub")} emoji="💗" />
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card className="h-fit space-y-3 p-5">
          <div className="flex items-center gap-3"><Chitti size={70} mood="happy" float={false} /><p className="text-sm font-semibold">{t("counsel.hug")}</p></div>
          <Field label={t("counsel.topicLabel")}><Select value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })}>
            {["talk", "study_stress", "friends", "complaint", "other"].map((k) => <option key={k} value={k}>{t(`counsel.topic.${k}`)}</option>)}</Select></Field>
          <Field label={t("counsel.message")}><Textarea rows={5} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" className="h-5 w-5 accent-rose-500" checked={f.anonymous} onChange={(e) => setF({ ...f, anonymous: e.target.checked })} /> <Lock size={14} /> {t("counsel.stayAnon")}</label>
          <Button className="w-full" disabled={!f.body.trim() || open.isPending} onClick={() => open.mutate()}>{t("counsel.send")}</Button>
          <div className="flex gap-2 rounded-2xl bg-soft/70 p-3 text-xs"><ShieldCheck size={16} className="shrink-0 text-ok" /> {t("counsel.privacy")}</div>
          <div className="flex gap-2 rounded-2xl bg-amber-50 p-3 text-xs dark:bg-soft"><Phone size={16} className="shrink-0 text-amber-600" /> {t("counsel.urgent")}</div>
        </Card>
        <div className="space-y-3">
          {mine.isLoading ? <Loading /> : !mine.data?.length ? <EmptyState text={t("counsel.none")} /> : mine.data.map((th) => <ThreadView key={th.id} th={th} staff={false} />)}
        </div>
      </div>
    </div>
  );
}

function Inbox() {
  const { t } = useTranslation();
  const inbox = useQuery({ queryKey: ["counsel", "inbox"], queryFn: () => get<Thread[]>("/counselling/inbox"), retry: false });
  const denied = inbox.error instanceof ApiError && inbox.error.status === 403;
  return (
    <div>
      <PageHero title={t("counsel.inbox")} subtitle={t("counsel.inboxSub")} emoji="💗" />
      {denied ? (
        <Card className="mx-auto max-w-lg p-8 text-center"><Lock className="mx-auto text-mute" size={40} /><p className="mt-3 font-bold">{t("counsel.notCounsellor")}</p></Card>
      ) : inbox.isLoading ? <Loading /> : !inbox.data?.length ? <EmptyState text={t("counsel.inboxEmpty")} /> : (
        <div className="grid gap-3 lg:grid-cols-2">{inbox.data.map((th) => <ThreadView key={th.id} th={th} staff />)}</div>
      )}
    </div>
  );
}
