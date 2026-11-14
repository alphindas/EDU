import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import Chitti from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { get, post } from "@/lib/api";
import type { Contact, Dm } from "@/lib/v2";
import { cn } from "@/lib/utils";

const ROLE_TONE: Record<string, string> = { teacher: "bg-emerald-100 text-emerald-700", student: "bg-soft text-primary", parent: "bg-amber-100 text-amber-700" };

export default function Messages() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [sel, setSel] = useState<Contact | null>(null);
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const contacts = useQuery({ queryKey: ["contacts"], queryFn: () => get<Contact[]>("/messages/contacts"), refetchInterval: 30_000 });
  const thread = useQuery({ queryKey: ["dm", sel?.user_id], queryFn: () => get<Dm[]>(`/messages/thread/${sel!.user_id}`), enabled: !!sel, refetchInterval: 15_000 });
  const send = useMutation({ mutationFn: () => post("/messages", { to: sel!.user_id, body: text.trim() }), onSuccess: () => { setText(""); qc.invalidateQueries({ queryKey: ["dm", sel?.user_id] }); }, onError: toastError });
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); if (thread.data) qc.invalidateQueries({ queryKey: ["contacts"] }); }, [thread.data, qc]);
  return (
    <div>
      <PageHero title={t("msg.title")} subtitle={t("msg.sub")} emoji="💬" />
      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <Card className={cn("p-3", sel && "hidden lg:block")}>
          {contacts.isLoading ? <Loading /> : !contacts.data?.length ? <EmptyState text={t("msg.noContacts")} /> : (
            <ul className="space-y-1">
              {contacts.data.map((c) => (
                <li key={c.user_id}><button onClick={() => setSel(c)} className={cn("flex w-full items-center gap-3 rounded-2xl p-2 text-left", sel?.user_id === c.user_id ? "bg-soft" : "hover:bg-soft/60")}>
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl grad-bg font-extrabold text-white">{c.name[0]}</span>
                  <span className="min-w-0 flex-1"><span className="block truncate font-bold">{c.name}</span>
                    <span className={cn("chip", ROLE_TONE[c.role])}>{t(`roles.${c.role}`)}</span>{c.about && <span className="ml-1 text-xs text-mute">· {c.about}</span>}</span>
                  {c.unread > 0 && <span className="grid h-6 min-w-6 place-items-center rounded-full bg-bad px-1 text-xs font-bold text-white">{c.unread}</span>}
                </button></li>
              ))}
            </ul>
          )}
        </Card>
        <Card className={cn("flex min-h-[60vh] flex-col", !sel && "hidden lg:flex")}>
          {!sel ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-mute"><Chitti size={100} mood="happy" /><p>{t("msg.pick")}</p></div>
          ) : (
            <>
              <div className="flex items-center gap-2 border-b-2 border-line p-3">
                <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSel(null)} aria-label={t("common.back")}><ArrowLeft size={18} /></Button>
                <span className="font-display text-lg font-extrabold">{sel.name}</span><span className={cn("chip", ROLE_TONE[sel.role])}>{t(`roles.${sel.role}`)}</span>
              </div>
              <div className="flex-1 space-y-2 overflow-y-auto p-4">
                {(thread.data ?? []).map((m) => (
                  <div key={m.id} className={cn("flex", m.mine ? "justify-end" : "justify-start")}>
                    <div className={cn("max-w-[80%] rounded-3xl px-4 py-2 text-sm shadow-card", m.mine ? "rounded-br-md grad-bg text-white" : "rounded-bl-md border-2 border-line bg-card")}>
                      <div className="whitespace-pre-wrap">{m.body}</div>
                      <div className={cn("mt-0.5 text-[10px]", m.mine ? "text-white/70" : "text-mute")}>{new Date(m.at).toLocaleString(i18n.language, { dateStyle: "short", timeStyle: "short" })}{m.mine && (m.read ? " ✓✓" : " ✓")}</div>
                    </div>
                  </div>
                ))}
                {thread.data?.length === 0 && <p className="py-8 text-center text-sm text-mute">{t("msg.sayHi")}</p>}
                <div ref={endRef} />
              </div>
              <form className="flex gap-2 border-t-2 border-line p-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send.mutate(); }}>
                <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("msg.placeholder")} maxLength={2000} />
                <Button type="submit" disabled={!text.trim() || send.isPending} aria-label={t("common.send")}><Send size={18} /></Button>
              </form>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
