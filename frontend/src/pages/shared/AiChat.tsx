import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, FileText, MessageSquarePlus, Paperclip, Send, Trash2, User, X } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader, Spinner } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { del, get, post, upload } from "@/lib/api";
import type { AiConversation, AiConversationDetail, AiDocument, AiMessage, ChatTurn } from "@/lib/types";
import { cn } from "@/lib/utils";

function Bubble({ m, doc }: { m: AiMessage; doc?: AiDocument }) {
  const { t } = useTranslation();
  const mine = m.role === "user";
  return (
    <div className={cn("flex gap-2", mine && "flex-row-reverse")} data-testid={`msg-${m.role}`}>
      <div className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-full text-white", mine ? "bg-accent2" : "bg-primary")}>{mine ? <User size={16} /> : <Bot size={16} />}</div>
      <div className={cn("max-w-[85%] rounded-2xl px-4 py-2.5 text-sm", mine ? "bg-soft" : "border border-line bg-card")}>
        {m.attachment_id && <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-mute"><Paperclip size={12} />{doc?.name ?? t("aichat.attachment")}</p>}
        <p className="whitespace-pre-line">{m.content}</p>
        {m.sources.length > 0 && (
          <div className="mt-2 border-t border-line pt-2 text-xs text-mute">
            <b>{t("aichat.sources")}:</b> {[...new Set(m.sources.map((s) => s.name))].join(", ")}
          </div>
        )}
        {m.provider === "stub" && <Badge tone="mute" className="mt-2">{t("ai.stubBadge")}</Badge>}
      </div>
    </div>
  );
}

export default function AiChatPage() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [cid, setCid] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState<string | null>(null); // the user's message while the reply is on its way
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const convs = useQuery({ queryKey: ["ai-convs"], queryFn: () => get<AiConversation[]>("/ai/conversations") });
  const docs = useQuery({ queryKey: ["ai-docs"], queryFn: () => get<AiDocument[]>("/ai/documents") });
  const conv = useQuery({ queryKey: ["ai-conv", cid], queryFn: () => get<AiConversationDetail>(`/ai/conversations/${cid}`), enabled: cid !== null });
  const docById = new Map((docs.data ?? []).map((d) => [d.id, d]));

  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [conv.data?.messages.length, pending]);

  const newConv = useMutation({
    mutationFn: () => post<AiConversation>("/ai/conversations", {}),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["ai-convs"] }); setCid(c.id); }, onError: toastError,
  });
  const rmConv = useMutation({
    mutationFn: (id: number) => del(`/ai/conversations/${id}`),
    onSuccess: (_, id) => { if (cid === id) setCid(null); qc.invalidateQueries({ queryKey: ["ai-convs"] }); }, onError: toastError,
  });
  const rmDoc = useMutation({
    mutationFn: (id: number) => del(`/ai/documents/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ai-docs"] }); qc.invalidateQueries({ queryKey: ["ai-conv"] }); }, onError: toastError,
  });
  const upNotes = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.set("file", f); return upload<AiDocument>("POST", "/ai/documents", fd); },
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["ai-docs"] }); toast(d.readable ? t("aichat.notesAdded") : t("aichat.unreadable")); }, onError: toastError,
  });

  const send = useMutation({
    mutationFn: async (v: { id: number; text: string; file: File | null }) => {
      const fd = new FormData();
      fd.set("text", v.text); fd.set("lang", i18n.language);
      if (v.file) fd.set("file", v.file);
      return upload<ChatTurn>("POST", `/ai/conversations/${v.id}/messages`, fd);
    },
    onSuccess: (r) => {
      setText(""); setFile(null); if (fileRef.current) fileRef.current.value = "";
      if (r.document && !r.document.readable) toast(t("aichat.unreadable"));
      qc.invalidateQueries({ queryKey: ["ai-conv"] }); qc.invalidateQueries({ queryKey: ["ai-convs"] }); qc.invalidateQueries({ queryKey: ["ai-docs"] });
    },
    onError: toastError,
    onSettled: () => setPending(null),
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const v = text.trim();
    if (!v || send.isPending) return;
    let id = cid;
    if (id === null) {
      try { id = (await newConv.mutateAsync()).id; } catch { return; }
    }
    setPending(v);
    send.mutate({ id, text: v, file });
  };

  return (
    <>
      <PageHeader title={t("nav.aiChat")} subtitle={t("aichat.subtitle")} />
      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <aside className="space-y-4">
          <Card className="p-3">
            <Button className="mb-2 w-full" size="sm" onClick={() => { setCid(null); }} disabled={newConv.isPending}><MessageSquarePlus size={14} />{t("aichat.new")}</Button>
            {convs.isLoading ? <Loading /> : convs.isError ? <ErrorState error={convs.error} /> : (convs.data ?? []).length === 0 ? <p className="p-2 text-xs text-mute">{t("aichat.noChats")}</p> : (
              <ul className="max-h-64 space-y-1 overflow-y-auto">
                {convs.data!.map((c) => (
                  <li key={c.id} className="flex items-center gap-1">
                    <button onClick={() => setCid(c.id)} className={cn("min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-left text-sm", c.id === cid ? "bg-soft font-semibold text-primary" : "hover:bg-soft")}>{c.title || t("aichat.untitled")}</button>
                    <button aria-label={t("common.delete")} className="text-mute hover:text-bad" onClick={() => confirm(t("common.confirmDelete")) && rmConv.mutate(c.id)}><Trash2 size={14} /></button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="p-3">
            <h3 className="mb-1 text-sm font-semibold">{t("aichat.myNotes")}</h3>
            <p className="mb-2 text-xs text-mute">{t("aichat.notesHint")}</p>
            <label className="mb-2 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line p-2 text-xs font-semibold text-primary hover:bg-soft">
              {upNotes.isPending ? <Spinner className="h-4 w-4" /> : <Paperclip size={14} />}{t("aichat.addNotes")}
              <input type="file" className="sr-only" accept=".pdf,.txt,image/png,image/jpeg,image/webp" onChange={(e) => { const f = e.target.files?.[0]; if (f) upNotes.mutate(f); e.target.value = ""; }} />
            </label>
            {(docs.data ?? []).length === 0 ? <p className="text-xs text-mute">{t("aichat.noNotes")}</p> : (
              <ul className="space-y-1">
                {docs.data!.map((d) => (
                  <li key={d.id} className="flex items-center gap-2 text-xs">
                    <FileText size={14} className={d.readable ? "text-primary" : "text-warn"} />
                    <span className="min-w-0 flex-1 truncate" title={d.name}>{d.name}</span>
                    {!d.readable && <Badge tone="warn">{t("aichat.noText")}</Badge>}
                    <button aria-label={t("common.delete")} className="text-mute hover:text-bad" onClick={() => confirm(t("common.confirmDelete")) && rmDoc.mutate(d.id)}><Trash2 size={13} /></button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </aside>

        <Card className="flex min-h-[28rem] flex-col p-0">
          <div className="flex-1 space-y-4 overflow-y-auto p-4" style={{ maxHeight: "60vh" }} aria-live="polite">
            {cid === null && !pending ? <EmptyState text={t("aichat.empty")}><Bot size={28} className="text-primary" /></EmptyState>
              : conv.isLoading ? <Loading /> : conv.isError ? <ErrorState error={conv.error} onRetry={() => conv.refetch()} /> : (
                <>
                  {conv.data?.messages.map((m) => <Bubble key={m.id} m={m} doc={m.attachment_id ? docById.get(m.attachment_id) : undefined} />)}
                  {pending && (
                    <>
                      <div className="flex flex-row-reverse gap-2"><div className="grid h-8 w-8 place-items-center rounded-full bg-accent2 text-white"><User size={16} /></div><div className="rounded-2xl bg-soft px-4 py-2.5 text-sm">{pending}</div></div>
                      <div className="flex items-center gap-2 text-sm text-mute" role="status"><Spinner className="h-4 w-4" />{t("aichat.thinking")}</div>
                    </>
                  )}
                </>
              )}
            <div ref={endRef} />
          </div>
          <form onSubmit={submit} className="border-t border-line p-3">
            {file && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-soft px-3 py-1.5 text-xs">
                <Paperclip size={14} /><span className="min-w-0 flex-1 truncate">{file.name}</span>
                <button type="button" aria-label={t("common.cancel")} onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ""; }}><X size={14} /></button>
              </div>
            )}
            <div className="flex items-end gap-2">
              <label className="grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-xl border border-line text-mute hover:bg-soft hover:text-primary" title={t("aichat.attach")}>
                <Paperclip size={18} /><span className="sr-only">{t("aichat.attach")}</span>
                <input ref={fileRef} type="file" className="sr-only" accept=".pdf,.txt,image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </label>
              <Textarea rows={1} maxLength={2000} value={text} placeholder={t("aichat.placeholder")} aria-label={t("aichat.placeholder")} className="min-h-10 flex-1 resize-none"
                onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void submit(e as unknown as FormEvent); } }} />
              <Button type="submit" size="icon" aria-label={t("aichat.send")} disabled={!text.trim() || send.isPending || newConv.isPending}><Send size={16} /></Button>
            </div>
          </form>
        </Card>
      </div>
    </>
  );
}
