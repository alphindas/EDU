import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileImage, Plus, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { FileButton } from "@/components/common/AuthFile";
import { EmptyState, Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/label";
import { Input, Select, Textarea } from "@/components/ui/input";
import { del, get, patch, post, upload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PortfolioT, ProjectT } from "@/lib/v2";
import { cn } from "@/lib/utils";

const CATS = ["science", "coding", "art", "social", "robotics", "other"];
const CAT_TONE: Record<string, string> = { science: "from-violet-100 to-sky-100", coding: "from-sky-100 to-cyan-100", art: "from-rose-100 to-amber-100",
  social: "from-emerald-100 to-teal-100", robotics: "from-indigo-100 to-violet-100", other: "from-amber-100 to-yellow-50" };
const PORT_EMOJI: Record<string, string> = { certificate: "📜", sports: "🏅", art: "🎨", project: "🚀", award: "🏆", other: "⭐" };

export default function Projects({ studentId }: { studentId?: number }) {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user?.role);
  const [tab, setTab] = useState<"projects" | "portfolio">(role === "parent" ? "portfolio" : "projects");
  return (
    <div>
      <PageHero title={t("proj.title")} subtitle={t("proj.sub")} emoji="🚀" />
      {role === "student" && (
        <div className="mb-4 flex gap-2">
          {(["projects", "portfolio"] as const).map((k) => <button key={k} onClick={() => setTab(k)} className={cn("rounded-2xl px-4 py-2 text-sm font-extrabold", tab === k ? "grad-bg text-white shadow-chunky" : "bg-card text-mute shadow-card")}>{t(`proj.tab.${k}`)}</button>)}
        </div>
      )}
      {tab === "projects" ? <ProjectSpace /> : <Portfolio studentId={studentId} />}
    </div>
  );
}

function ProjectSpace() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user?.role);
  const [open, setOpen] = useState<number | null>(null);
  const [add, setAdd] = useState(false);
  const list = useQuery({ queryKey: ["projects"], queryFn: () => get<ProjectT[]>("/projects") });
  if (open) return <ProjectView id={open} onBack={() => setOpen(null)} />;
  return (
    <>
      {role === "student" && <Button className="mb-4" onClick={() => setAdd(true)}><Plus size={16} /> {t("proj.new")}</Button>}
      {list.isLoading ? <Loading /> : !list.data?.length ? <EmptyState text={t("proj.empty")} /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.data.map((p) => (
            <button key={p.id} onClick={() => setOpen(p.id)} className={cn("lift overflow-hidden rounded-3xl border-2 border-line bg-gradient-to-br text-left shadow-card", CAT_TONE[p.category])}>
              <div className="p-4"><div className="text-5xl">{p.emoji}</div>
                <div className="mt-2 font-display text-xl font-extrabold leading-tight text-navy">{p.title}</div>
                <p className="mt-1 line-clamp-2 text-sm text-navy/70">{p.summary}</p></div>
              <div className="flex items-center justify-between bg-card/80 px-4 py-2 text-xs font-bold">
                <span className="chip bg-soft text-primary">{t(`proj.cat.${p.category}`)}</span>
                <span className="flex items-center gap-1"><Users size={13} /> {p.members.length}/{p.max_members}</span>
                <span className={cn("chip", p.status === "open" ? "bg-ok/15 text-ok" : p.status === "done" ? "bg-violet-100 text-violet-700" : "bg-amber-100 text-amber-700")}>{t(`proj.status.${p.status}`)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
      {add && <NewProject onClose={() => setAdd(false)} />}
    </>
  );
}

function ProjectView({ id, onBack }: { id: number; onBack: () => void }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.role);
  const [c, setC] = useState("");
  const p = useQuery({ queryKey: ["project", id], queryFn: () => get<ProjectT>(`/projects/${id}`) });
  const done = () => { qc.invalidateQueries({ queryKey: ["project", id] }); qc.invalidateQueries({ queryKey: ["projects"] }); };
  const join = useMutation({ mutationFn: () => post(`/projects/${id}/join`), onSuccess: done, onError: toastError });
  const comment = useMutation({ mutationFn: () => post(`/projects/${id}/comments`, { body: c }), onSuccess: () => { setC(""); done(); }, onError: toastError });
  const status = useMutation({ mutationFn: (s: string) => patch(`/projects/${id}`, { status: s }), onSuccess: done, onError: toastError });
  if (!p.data) return <Loading />;
  const d = p.data;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Button variant="ghost" size="sm" onClick={onBack}><ArrowLeft size={16} /> {t("common.back")}</Button>
      <Card className={cn("bg-gradient-to-br p-6", CAT_TONE[d.category])}>
        <div className="text-6xl">{d.emoji}</div>
        <h1 className="mt-2 font-display text-3xl font-extrabold text-navy">{d.title}</h1>
        <p className="mt-2 text-navy/80">{d.summary}</p>
        <div className="mt-3 flex flex-wrap gap-2">{d.members.map((m) => <span key={m.user_id} className="chip bg-white/80">👤 {m.name}</span>)}</div>
        <div className="mt-4 flex flex-wrap gap-2">
          {role === "student" && !d.mine && <Button onClick={() => join.mutate()} variant={d.joined ? "outline" : "sun"}>{d.joined ? t("proj.leave") : t("proj.join")}</Button>}
          {(d.mine || role !== "student") && ["open", "building", "done"].map((s) => <Button key={s} size="sm" variant={d.status === s ? "default" : "outline"} onClick={() => status.mutate(s)}>{t(`proj.status.${s}`)}</Button>)}
        </div>
      </Card>
      <Card className="p-5">
        <h3 className="mb-3 font-display text-lg font-extrabold">💬 {t("proj.feedback")}</h3>
        <ul className="space-y-2">{(d.comments ?? []).map((x) => <li key={x.id} className="rounded-2xl bg-soft/60 p-3 text-sm"><b>{x.author}</b> <span className="text-xs text-mute">· {t(`roles.${x.role}`)} · {new Date(x.at).toLocaleDateString(i18n.language)}</span><p className="mt-0.5">{x.body}</p></li>)}</ul>
        <div className="mt-3 flex gap-2"><Input value={c} onChange={(e) => setC(e.target.value)} placeholder={t("proj.commentHint")} /><Button disabled={!c.trim()} onClick={() => comment.mutate()}>{t("common.send")}</Button></div>
      </Card>
    </div>
  );
}

function NewProject({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [f, setF] = useState({ title: "", summary: "", category: "science", max_members: 4, emoji: "🚀" });
  const save = useMutation({ mutationFn: () => post("/projects", f), onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); onClose(); }, onError: toastError });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("proj.new")}>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">{["🚀", "🔬", "🤖", "🎨", "🌱", "💡", "🎮", "🌍", "☀️", "🧪"].map((e) => <button key={e} onClick={() => setF({ ...f, emoji: e })} className={cn("grid h-10 w-10 place-items-center rounded-xl text-xl", f.emoji === e ? "bg-soft ring-2 ring-primary" : "hover:bg-soft")}>{e}</button>)}</div>
          <Field label={t("proj.name")}><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t("proj.about")}><Textarea rows={3} value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("proj.category")}><Select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{CATS.map((c) => <option key={c} value={c}>{t(`proj.cat.${c}`)}</option>)}</Select></Field>
            <Field label={t("proj.team")}><Input type="number" min={1} max={10} value={f.max_members} onChange={(e) => setF({ ...f, max_members: Number(e.target.value) })} /></Field>
          </div>
          <Button className="w-full" disabled={f.title.length < 3 || save.isPending} onClick={() => save.mutate()}>{t("proj.create")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Portfolio({ studentId }: { studentId?: number }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.role);
  const [add, setAdd] = useState(false);
  const list = useQuery({ queryKey: ["portfolio", studentId], queryFn: () => get<PortfolioT[]>(`/portfolio${studentId ? `?student_id=${studentId}` : ""}`) });
  const remove = useMutation({ mutationFn: (id: number) => del(`/portfolio/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }) });
  return (
    <>
      {role === "student" && <Button className="mb-4" onClick={() => setAdd(true)}><Plus size={16} /> {t("port.add")}</Button>}
      {list.isLoading ? <Loading /> : !list.data?.length ? <EmptyState text={t("port.empty")} /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.data.map((x) => (
            <Card key={x.id} className="p-4">
              <div className="flex items-start gap-3"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-amber-100 text-2xl">{PORT_EMOJI[x.kind]}</span>
                <div className="flex-1"><div className="font-display text-lg font-extrabold leading-tight">{x.title}</div>
                  <div className="text-xs font-bold text-mute">{t(`port.kind.${x.kind}`)}{x.achieved_on && ` · ${new Date(x.achieved_on).toLocaleDateString(i18n.language)}`}</div></div>
                {role === "student" && <button onClick={() => remove.mutate(x.id)} className="text-mute hover:text-bad" aria-label={t("common.delete")}><Trash2 size={15} /></button>}</div>
              {x.details && <p className="mt-2 text-sm text-mute">{x.details}</p>}
              {x.has_file && <div className="mt-2"><FileButton path={`/portfolio/${x.id}/file`} name={x.title} /></div>}
            </Card>
          ))}
        </div>
      )}
      {add && <AddPortfolio onClose={() => setAdd(false)} />}
    </>
  );
}

function AddPortfolio({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [f, setF] = useState({ kind: "certificate", title: "", details: "", achieved_on: "" });
  const [file, setFile] = useState<File | null>(null);
  const save = useMutation({ mutationFn: () => { const fd = new FormData(); Object.entries(f).forEach(([k, v]) => v && fd.append(k, v)); if (file) fd.append("file", file); return upload("POST", "/portfolio", fd); },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["portfolio"] }); onClose(); }, onError: toastError });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("port.add")}>
        <div className="space-y-3">
          <Field label={t("port.kindLabel")}><Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.keys(PORT_EMOJI).map((k) => <option key={k} value={k}>{PORT_EMOJI[k]} {t(`port.kind.${k}`)}</option>)}</Select></Field>
          <Field label={t("port.titleLabel")}><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t("port.details")}><Textarea rows={3} value={f.details} onChange={(e) => setF({ ...f, details: e.target.value })} /></Field>
          <Field label={t("port.date")}><Input type="date" value={f.achieved_on} onChange={(e) => setF({ ...f, achieved_on: e.target.value })} /></Field>
          <Field label={t("port.file")}><Input type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          <Button className="w-full" disabled={!f.title || save.isPending} onClick={() => save.mutate()}><FileImage size={16} /> {t("common.save")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
