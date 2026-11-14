import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pin, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/label";
import { Input, Select, Textarea } from "@/components/ui/input";
import { del, get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sectionLabel, useClasses, useSections } from "@/lib/queries";
import type { Announcement } from "@/lib/v2";
import { cn } from "@/lib/utils";

const EMOJIS = ["📢", "🎉", "📅", "🔬", "🏆", "⚽", "🎨", "🤝", "⚠️", "🌧️"];

export default function Announcements() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.role);
  const [open, setOpen] = useState(false);
  const list = useQuery({ queryKey: ["ann-all"], queryFn: () => get<Announcement[]>("/announcements?limit=100") });
  const secs = useSections(); const classes = useClasses();
  const remove = useMutation({ mutationFn: (id: number) => del(`/announcements/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["ann-all"] }), onError: toastError });
  const staff = role === "admin" || role === "teacher";
  return (
    <div>
      <PageHero title={t("ann.title")} subtitle={t("ann.sub")} emoji="📢">
        {staff && <Button onClick={() => setOpen(true)}><Plus size={16} /> {t("ann.new")}</Button>}
      </PageHero>
      {list.isLoading ? <Loading /> : !list.data?.length ? <EmptyState text={t("ann.empty")} /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {list.data.map((a) => (
            <Card key={a.id} className={cn("relative p-5", a.pinned && "ring-4 ring-sun/50")}>
              {a.pinned && <span className="absolute right-4 top-4 chip bg-amber-100 text-amber-700"><Pin size={12} /> {t("ann.pinned")}</span>}
              <div className="flex items-start gap-3">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-soft text-2xl">{a.emoji}</span>
                <div className="min-w-0 flex-1 pr-16">
                  <h3 className="font-display text-xl font-extrabold leading-tight">{a.title}</h3>
                  <div className="mt-0.5 text-xs font-semibold text-mute">{a.author} · {new Date(a.created_at).toLocaleDateString(i18n.language)} · {t(`ann.aud.${a.audience}`)}{a.section_id ? ` · ${sectionLabel(secs.data, classes.data, a.section_id)}` : ""}</div>
                </div>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{a.body}</p>
              {staff && <Button variant="ghost" size="sm" className="mt-2 text-mute" onClick={() => remove.mutate(a.id)}><Trash2 size={14} /> {t("common.delete")}</Button>}
            </Card>
          ))}
        </div>
      )}
      {open && <NewAnnouncement onClose={() => setOpen(false)} />}
    </div>
  );
}

function NewAnnouncement({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user?.role);
  const secs = useSections(); const classes = useClasses();
  const tid = useAuth((s) => s.user?.teacher_id);
  const mySecs = useQuery({ queryKey: ["my-asg", tid], queryFn: () => get<{ section_id: number }[]>(`/assignments?teacher_id=${tid}`), enabled: role === "teacher" && !!tid });
  const [f, setF] = useState({ title: "", body: "", audience: role === "teacher" ? "students" : "all", section_id: "", pinned: false, emoji: "📢" });
  const save = useMutation({ mutationFn: () => post("/announcements", { ...f, section_id: f.section_id ? Number(f.section_id) : null }),
    onSuccess: () => { toast(t("ann.posted")); qc.invalidateQueries({ queryKey: ["ann-all"] }); onClose(); }, onError: toastError });
  const allowed = role === "teacher" ? new Set((mySecs.data ?? []).map((a) => a.section_id)) : null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("ann.new")}>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">{EMOJIS.map((e) => <button key={e} onClick={() => setF({ ...f, emoji: e })} className={cn("grid h-10 w-10 place-items-center rounded-xl text-xl", f.emoji === e ? "bg-soft ring-2 ring-primary" : "hover:bg-soft")}>{e}</button>)}</div>
          <Field label={t("ann.titleLabel")}><Input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label={t("ann.body")}><Textarea rows={4} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("ann.audience")}><Select value={f.audience} onChange={(e) => setF({ ...f, audience: e.target.value })}>
              {(role === "teacher" ? ["all", "students", "parents"] : ["all", "students", "teachers", "parents", "staff"]).map((a) => <option key={a} value={a}>{t(`ann.aud.${a}`)}</option>)}</Select></Field>
            <Field label={t("ann.section")}><Select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })}>
              {role !== "teacher" && <option value="">{t("ann.wholeSchool")}</option>}
              {(secs.data ?? []).filter((s) => !allowed || allowed.has(s.id)).map((s) => <option key={s.id} value={s.id}>{sectionLabel(secs.data, classes.data, s.id)}</option>)}</Select></Field>
          </div>
          {role === "admin" && <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" className="h-5 w-5 accent-amber-500" checked={f.pinned} onChange={(e) => setF({ ...f, pinned: e.target.checked })} /> 📌 {t("ann.pin")}</label>}
          <Button className="w-full" disabled={!f.title || !f.body || (role === "teacher" && !f.section_id) || save.isPending} onClick={() => save.mutate()}>{t("ann.post")}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
