import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bookmark, BookOpen, CheckCircle2, Circle, Download, ExternalLink, Network, Plus, Search, Trash2, Upload, Volume2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { celebrate, type Reward } from "@/components/fun/Celebrate";
import Chitti from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/label";
import { Input, Select, Textarea } from "@/components/ui/input";
import { del, fetchBlob, get, patch, post, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClasses, useSubjects, subjectName } from "@/lib/queries";
import type { Resource } from "@/lib/v2";
import { canSpeak, speak } from "@/lib/voice";
import { cn } from "@/lib/utils";

const KINDS = ["syllabus", "notes", "textbook", "paper", "ebook", "video", "audio"];
const KIND_EMOJI: Record<string, string> = { syllabus: "🗺️", notes: "📝", textbook: "📗", paper: "📄", ebook: "📚", video: "🎬", audio: "🎧" };

export default function Library() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user?.role);
  const subs = useSubjects();
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [add, setAdd] = useState(false);
  const list = useQuery({ queryKey: ["library", kind, q], queryFn: () => get<Resource[]>(`/library?${new URLSearchParams({ ...(kind && { kind }), ...(q && { q }) })}`) });
  const staff = role === "teacher" || role === "admin";
  if (open) return <Reader id={open} onBack={() => setOpen(null)} />;
  return (
    <div>
      <PageHero title={t("lib.title")} subtitle={t("lib.sub")} emoji="📚">
        {staff && <Button onClick={() => setAdd(true)}><Upload size={16} /> {t("lib.upload")}</Button>}
      </PageHero>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[14rem] flex-1"><Search className="absolute left-3 top-3.5 text-mute" size={18} /><Input className="pl-10" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("lib.search")} /></div>
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
          <button onClick={() => setKind("")} className={cn("chip shrink-0 py-1.5 text-sm", !kind ? "grad-bg text-white" : "bg-card shadow-card")}>{t("lib.all")}</button>
          {KINDS.map((k) => <button key={k} onClick={() => setKind(k)} className={cn("chip shrink-0 py-1.5 text-sm", kind === k ? "grad-bg text-white" : "bg-card shadow-card")}>{KIND_EMOJI[k]} {t(`lib.kind.${k}`)}</button>)}
        </div>
      </div>
      {list.isLoading ? <Loading /> : !list.data?.length ? <EmptyState text={t("lib.empty")} /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.data.map((r) => {
            const pct = r.chapter_count ? Math.round((100 * r.completed.length) / r.chapter_count) : 0;
            return (
              <Card key={r.id} className="lift flex flex-col p-4">
                <div className="flex items-start gap-3">
                  <span className="grid h-14 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-b from-sky-200 to-indigo-200 text-2xl shadow-chunky">{KIND_EMOJI[r.kind]}</span>
                  <div className="min-w-0 flex-1">
                    <div className="line-clamp-2 font-display text-lg font-extrabold leading-tight">{r.title}</div>
                    <div className="mt-1 flex flex-wrap gap-1"><span className="chip bg-soft text-primary">{t(`lib.kind.${r.kind}`)}</span>
                      {r.subject_id && <span className="chip bg-amber-100 text-amber-700">{subjectName(subs.data, r.subject_id)}</span>}
                      {r.year && <span className="chip bg-line">{r.year}</span>}</div>
                  </div>
                </div>
                {r.description && <p className="mt-2 line-clamp-2 text-sm text-mute">{r.description}</p>}
                {r.chapter_count > 0 && (
                  <div className="mt-3"><div className="mb-1 flex justify-between text-xs font-bold text-mute"><span>{t("lib.chapters", { n: r.chapter_count })}</span><span>{pct}%</span></div>
                    <div className="h-2 overflow-hidden rounded-full bg-line"><div className="h-full grad-mint" style={{ width: `${pct}%` }} /></div></div>
                )}
                <div className="mt-auto flex gap-2 pt-3">
                  {r.chapter_count > 0 && <Button size="sm" onClick={() => setOpen(r.id)}><BookOpen size={15} /> {t("lib.read")}</Button>}
                  {r.url && <Button size="sm" variant="outline" asChild><a href={r.url} target="_blank" rel="noreferrer noopener"><ExternalLink size={15} /> {t("lib.open")}</a></Button>}
                  {r.has_file && <DownloadBtn r={r} />}
                </div>
              </Card>
            );
          })}
        </div>
      )}
      {add && <AddResource onClose={() => setAdd(false)} />}
    </div>
  );
}

function DownloadBtn({ r }: { r: Resource }) {
  const { t } = useTranslation();
  const go = async () => {
    try {
      const b = await fetchBlob(`/library/${r.id}/file`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b); a.download = r.title; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (e) { toastError(e); }
  };
  return <Button size="sm" variant="outline" onClick={go} title={t("lib.offline")}><Download size={15} /> {t("lib.download")}</Button>;
}

function Reader({ id, onBack }: { id: number; onBack: () => void }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.role);
  const r = useQuery({ queryKey: ["resource", id], queryFn: () => get<Resource>(`/library/${id}`) });
  const [ch, setCh] = useState(0);
  const [find, setFind] = useState("");
  const hits = useQuery({ queryKey: ["res-search", id, find], queryFn: () => get<{ chapter: number; title: string; snippet: string }[]>(`/library/${id}/search?q=${encodeURIComponent(find)}`), enabled: find.length > 1 });
  const prog = useMutation({ mutationFn: (b: object) => patch<{ reward: Reward | null }>(`/library/${id}/progress`, b), onSuccess: (x) => { celebrate(x.reward); qc.invalidateQueries({ queryKey: ["resource", id] }); qc.invalidateQueries({ queryKey: ["library"] }); }, onError: toastError });
  const sum = useMutation({ mutationFn: () => post<{ title: string; bullets: string[]; mind: { center: string; branches: { label: string; items: string[] }[] } }>("/chitti/summary", { resource_id: id, chapter: ch, lang: i18n.language }), onError: toastError });
  const remove = useMutation({ mutationFn: () => del(`/library/${id}`), onSuccess: () => { toast(t("common.deleted")); qc.invalidateQueries({ queryKey: ["library"] }); onBack(); }, onError: toastError });
  if (!r.data) return <Loading />;
  const d = r.data;
  const chapters = d.chapters ?? [];
  const cur = chapters[ch];
  const done = d.completed.includes(ch);
  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <Card className="h-fit p-4">
        <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft size={16} /> {t("common.back")}</Button>
        <h2 className="mt-2 font-display text-lg font-extrabold leading-tight">{d.title}</h2>
        <div className="relative mt-3"><Search className="absolute left-3 top-3.5 text-mute" size={16} /><Input className="pl-9" value={find} onChange={(e) => setFind(e.target.value)} placeholder={t("lib.findIn")} /></div>
        {find.length > 1 && <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">{(hits.data ?? []).map((h, i) => <li key={i}><button onClick={() => setCh(h.chapter)} className="w-full rounded-xl bg-soft/60 p-2 text-left text-xs"><b>{h.title}</b><div className="text-mute">…{h.snippet}…</div></button></li>)}</ul>}
        <ol className="mt-3 space-y-1">
          {chapters.map((c, i) => (
            <li key={i}><button onClick={() => { setCh(i); sum.reset(); }} className={cn("flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left text-sm font-bold", i === ch ? "bg-soft text-primary" : "hover:bg-soft/60")}>
              {d.completed.includes(i) ? <CheckCircle2 size={16} className="shrink-0 text-ok" /> : <Circle size={16} className="shrink-0 text-mute" />}<span className="truncate">{c.title}</span></button></li>
          ))}
        </ol>
        {!!d.bookmarks.length && (<><div className="mt-3 text-[11px] font-extrabold uppercase text-mute">{t("lib.bookmarks")}</div>
          <ul className="mt-1 space-y-1">{d.bookmarks.map((b, i) => <li key={i} className="flex items-center gap-1 text-xs"><button className="flex-1 truncate text-left font-bold text-primary" onClick={() => setCh(b.chapter)}>🔖 {chapters[b.chapter]?.title} {b.note && `· ${b.note}`}</button>
            <button onClick={() => prog.mutate({ remove_bookmark: i })} className="text-mute hover:text-bad"><Trash2 size={12} /></button></li>)}</ul></>)}
        {(role === "admin" || role === "teacher") && <Button variant="ghost" size="sm" className="mt-3 text-bad" onClick={() => remove.mutate()}><Trash2 size={14} /> {t("common.delete")}</Button>}
      </Card>
      <div className="space-y-4">
        <Card className="p-5 sm:p-7">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h1 className="mr-auto font-display text-2xl font-extrabold">{cur?.title}</h1>
            {canSpeak() && <Button size="sm" variant="soft" onClick={() => speak(cur?.text ?? "", i18n.language)}><Volume2 size={15} /> {t("chitti.readAloud")}</Button>}
            <Button size="sm" variant="outline" onClick={() => prog.mutate({ bookmark: { chapter: ch, note: "" } })}><Bookmark size={15} /></Button>
            <Button size="sm" variant={done ? "outline" : "mint"} onClick={() => prog.mutate(done ? { uncomplete_chapter: ch } : { complete_chapter: ch })}>{done ? `✓ ${t("lib.completed")}` : t("lib.markDone")}</Button>
          </div>
          <article className="whitespace-pre-wrap text-[1.05rem] leading-8">{cur?.text}</article>
        </Card>
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-3"><Chitti size={56} float={false} mood={sum.isPending ? "think" : "happy"} />
            <div className="mr-auto"><div className="font-display text-lg font-extrabold">{t("lib.aiTitle")}</div><div className="text-sm text-mute">{t("lib.aiSub")}</div></div>
            <Button onClick={() => sum.mutate()} disabled={sum.isPending}><Network size={16} /> {t("lib.summarise")}</Button></div>
          {sum.data && (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <ul className="space-y-2">{sum.data.bullets.map((b, i) => <li key={i} className="flex gap-2 rounded-2xl bg-soft/60 p-2.5 text-sm"><span className="font-extrabold text-primary">{i + 1}</span>{b}</li>)}</ul>
              <MindMap center={sum.data.mind.center} branches={sum.data.mind.branches} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function MindMap({ center, branches }: { center: string; branches: { label: string; items: string[] }[] }) {
  const colors = ["bg-soft text-primary", "bg-amber-100 text-amber-800", "bg-emerald-100 text-emerald-800", "bg-violet-100 text-violet-800", "bg-rose-100 text-rose-800", "bg-teal-100 text-teal-800"];
  return (
    <div className="rounded-3xl border-2 border-dashed border-line p-4">
      <div className="mx-auto mb-3 w-fit rounded-2xl grad-bg px-4 py-2 text-center font-display font-extrabold text-white shadow-chunky">{center}</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {branches.map((b, i) => (
          <div key={i} className={cn("rounded-2xl p-2.5", colors[i % colors.length])}>
            <div className="font-extrabold">● {b.label}</div>
            <ul className="mt-1 space-y-0.5 text-xs">{b.items.map((x, k) => <li key={k}>– {x}</li>)}</ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function AddResource({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const classes = useClasses();
  const subs = useSubjects();
  const [f, setF] = useState({ kind: "notes", title: "", description: "", class_id: "", subject_id: "", year: "", url: "", text: "" });
  const [file, setFile] = useState<File | null>(null);
  const save = useMutation({
    mutationFn: () => { const fd = new FormData(); Object.entries(f).forEach(([k, v]) => v && fd.append(k, v)); if (file) fd.append("file", file); return upload("POST", "/library", fd); },
    onSuccess: () => { toast(t("lib.uploaded")); qc.invalidateQueries({ queryKey: ["library"] }); onClose(); }, onError: toastError,
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("lib.upload")} description={t("lib.uploadHint")} className="max-w-2xl">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("lib.kindLabel")}><Select value={f.kind} onChange={set("kind")}>{KINDS.map((k) => <option key={k} value={k}>{KIND_EMOJI[k]} {t(`lib.kind.${k}`)}</option>)}</Select></Field>
          <Field label={t("lib.titleLabel")}><Input value={f.title} onChange={set("title")} /></Field>
          <Field label={t("lib.class")}><Select value={f.class_id} onChange={set("class_id")}><option value="">{t("lib.allClasses")}</option>{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label={t("lib.subject")}><Select value={f.subject_id} onChange={set("subject_id")}><option value="">—</option>{subs.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          {f.kind === "paper" && <Field label={t("lib.year")}><Input type="number" value={f.year} onChange={set("year")} /></Field>}
          <Field label={t("lib.link")}><Input value={f.url} onChange={set("url")} placeholder="https://" /></Field>
        </div>
        <div className="mt-3 space-y-3">
          <Field label={t("lib.desc")}><Input value={f.description} onChange={set("description")} /></Field>
          <Field label={t("lib.text")} hint={t("lib.textHint")}><Textarea rows={5} value={f.text} onChange={set("text")} /></Field>
          <Field label={t("lib.file")} hint={t("lib.fileHint")}><Input type="file" accept="application/pdf,text/plain,image/*,audio/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Button className="w-full" onClick={() => save.mutate()} disabled={!f.title || save.isPending}><Plus size={16} /> {t("common.save")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
