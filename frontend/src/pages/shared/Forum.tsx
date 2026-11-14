import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, EyeOff, Heart, MessageSquare, Plus, Search } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/label";
import { Input, Select, Textarea } from "@/components/ui/input";
import { get, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ForumPostT } from "@/lib/v2";
import { cn } from "@/lib/utils";

const KIND = { doubt: "❓", idea: "💡", showcase: "🌟" } as Record<string, string>;

export default function Forum() {
  const { t, i18n } = useTranslation();
  const role = useAuth((s) => s.user?.role);
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [add, setAdd] = useState(false);
  const list = useQuery({ queryKey: ["forum", kind, q], queryFn: () => get<ForumPostT[]>(`/forum?${new URLSearchParams({ ...(kind && { kind }), ...(q && { q }) })}`) });
  if (open) return <PostView id={open} onBack={() => setOpen(null)} />;
  return (
    <div>
      <PageHero title={t("forum.title")} subtitle={t("forum.sub")} emoji="🗨️">
        {(role === "student" || role === "teacher") && <Button onClick={() => setAdd(true)}><Plus size={16} /> {t("forum.ask")}</Button>}
      </PageHero>
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-[14rem] flex-1"><Search className="absolute left-3 top-3.5 text-mute" size={18} /><Input className="pl-10" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("forum.search")} /></div>
        {["", "doubt", "idea", "showcase"].map((k) => <button key={k} onClick={() => setKind(k)} className={cn("chip py-1.5 text-sm", kind === k ? "grad-bg text-white" : "bg-card shadow-card")}>{k ? `${KIND[k]} ${t(`forum.kind.${k}`)}` : t("lib.all")}</button>)}
      </div>
      {list.isLoading ? <Loading /> : !list.data?.length ? <EmptyState text={t("forum.empty")} /> : (
        <div className="space-y-3">
          {list.data.map((p) => (
            <button key={p.id} onClick={() => setOpen(p.id)} className={cn("lift w-full rounded-3xl border-2 border-line bg-card p-4 text-left shadow-card", p.hidden && "opacity-60")}>
              <div className="flex items-start gap-3">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-soft text-xl">{KIND[p.kind]}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-display text-lg font-extrabold leading-tight">{p.title}</span>
                    {p.solved && <span className="chip bg-ok/15 text-ok"><CheckCircle2 size={12} /> {t("forum.solved")}</span>}{p.hidden && <span className="chip bg-bad/10 text-bad"><EyeOff size={12} /> {t("forum.hidden")}</span>}
                    {p.section_id === null && <span className="chip bg-lav/30 text-violet-700">🏫 {t("forum.schoolWide")}</span>}</div>
                  <p className="line-clamp-2 text-sm text-mute">{p.body}</p>
                  <div className="mt-1 flex gap-3 text-xs font-bold text-mute"><span>{p.author}</span><span><Heart size={12} className="inline" /> {p.likes}</span><span><MessageSquare size={12} className="inline" /> {p.replies_count}</span>
                    <span>{new Date(p.created_at).toLocaleDateString(i18n.language)}</span></div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
      {add && <NewPost onClose={() => setAdd(false)} />}
    </div>
  );
}

function PostView({ id, onBack }: { id: number; onBack: () => void }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [reply, setReply] = useState("");
  const p = useQuery({ queryKey: ["post", id], queryFn: () => get<ForumPostT>(`/forum/${id}`) });
  const done = () => { qc.invalidateQueries({ queryKey: ["post", id] }); qc.invalidateQueries({ queryKey: ["forum"] }); };
  const send = useMutation({ mutationFn: () => post(`/forum/${id}/replies`, { body: reply }), onSuccess: () => { setReply(""); done(); }, onError: toastError });
  const like = useMutation({ mutationFn: () => post(`/forum/${id}/like`), onSuccess: done });
  const mod = useMutation({ mutationFn: (b: object) => patch(`/forum/${id}`, b), onSuccess: done, onError: toastError });
  if (!p.data) return <Loading />;
  const d = p.data;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft size={16} /> {t("common.back")}</Button>
      <Card className="p-5">
        <div className="flex flex-wrap items-center gap-2"><span className="text-2xl">{KIND[d.kind]}</span><h1 className="font-display text-2xl font-extrabold">{d.title}</h1>{d.solved && <span className="chip bg-ok/15 text-ok">✓ {t("forum.solved")}</span>}</div>
        <div className="text-xs font-semibold text-mute">{d.author} · {t(`roles.${d.author_role}`)} · {new Date(d.created_at).toLocaleString(i18n.language)}</div>
        <p className="mt-3 whitespace-pre-wrap">{d.body}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant={d.liked ? "default" : "outline"} onClick={() => like.mutate()}><Heart size={15} /> {d.likes}</Button>
          {(d.mine || d.can_moderate) && <Button size="sm" variant="outline" onClick={() => mod.mutate({ solved: !d.solved })}><CheckCircle2 size={15} /> {d.solved ? t("forum.unsolve") : t("forum.markSolved")}</Button>}
          {d.can_moderate && <Button size="sm" variant="ghost" className="text-bad" onClick={() => mod.mutate({ hidden: !d.hidden })}><EyeOff size={15} /> {d.hidden ? t("forum.unhide") : t("forum.hide")}</Button>}
        </div>
      </Card>
      {(d.replies ?? []).map((r) => (
        <Card key={r.id} className={cn("p-4", r.accepted && "ring-4 ring-ok/30", r.hidden && "opacity-50")}>
          <div className="flex items-center gap-2 text-xs font-bold text-mute"><span className="text-ink">{r.author}</span><span>{t(`roles.${r.author_role}`)}</span>{r.accepted && <span className="chip bg-ok/15 text-ok">⭐ {t("forum.best")}</span>}</div>
          <p className="mt-1 whitespace-pre-wrap text-sm">{r.body}</p>
          <div className="mt-2 flex gap-2">
            {(d.mine || d.can_moderate) && !r.accepted && <Button size="sm" variant="soft" onClick={() => mod.mutate({ reply_id: r.id, reply_accepted: true })}>⭐ {t("forum.accept")}</Button>}
            {d.can_moderate && <Button size="sm" variant="ghost" className="text-bad" onClick={() => mod.mutate({ reply_id: r.id, reply_hidden: !r.hidden })}><EyeOff size={14} /></Button>}
          </div>
        </Card>
      ))}
      <Card className="p-4">
        <Textarea rows={3} value={reply} onChange={(e) => setReply(e.target.value)} placeholder={t("forum.replyHint")} />
        <p className="mt-1 text-[11px] text-mute">{t("forum.kindRule")}</p>
        <Button className="mt-2" disabled={!reply.trim() || send.isPending} onClick={() => send.mutate()}>{t("forum.reply")}</Button>
      </Card>
    </div>
  );
}

function NewPost({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [f, setF] = useState({ title: "", body: "", kind: "doubt", school_wide: false });
  const save = useMutation({ mutationFn: () => post("/forum", f), onSuccess: () => { qc.invalidateQueries({ queryKey: ["forum"] }); onClose(); }, onError: toastError });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("forum.ask")}>
        <div className="space-y-3">
          <Field label={t("forum.kindLabel")}><Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{["doubt", "idea", "showcase"].map((k) => <option key={k} value={k}>{KIND[k]} {t(`forum.kind.${k}`)}</option>)}</Select></Field>
          <Field label={t("forum.titleLabel")}><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t("forum.bodyLabel")}><Textarea rows={4} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" className="h-5 w-5 accent-violet-500" checked={f.school_wide} onChange={(e) => setF({ ...f, school_wide: e.target.checked })} /> 🏫 {t("forum.schoolWide")}</label>
          <Button className="w-full" disabled={f.title.length < 3 || !f.body || save.isPending} onClick={() => save.mutate()}>{t("forum.post")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
