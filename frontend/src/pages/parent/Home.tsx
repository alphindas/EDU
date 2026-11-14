import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Bus, CalendarCheck, MessageCircle, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { greetingKey, Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Ring, SchoolScene } from "@/components/fun/Art";
import Chitti, { Bubble } from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/label";
import { Input, Select, Textarea } from "@/components/ui/input";
import { get, post, put } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sectionLabel, useClasses, useMyChildren, useSections } from "@/lib/queries";
import type { HistoryOut } from "@/lib/types";
import type { Announcement, GameProfile } from "@/lib/v2";

interface Draft { student_id: number | null; from_date: string; to_date: string; reason: string; leave_type: string; confidence: number; children: { id: number; name: string }[]; needs_review: boolean }

export default function ParentHome() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const kids = useMyChildren();
  const secs = useSections(); const classes = useClasses();
  const ids = (kids.data ?? []).map((k) => k.id);
  const games = useQueries({ queries: ids.map((id) => ({ queryKey: ["game", id], queryFn: () => get<GameProfile>(`/game/profile?student_id=${id}`) })) });
  const atts = useQueries({ queries: ids.map((id) => ({ queryKey: ["att", id], queryFn: () => get<HistoryOut>(`/attendance/students/${id}`) })) });
  const ann = useQuery({ queryKey: ["ann"], queryFn: () => get<Announcement[]>("/announcements?limit=4") });
  if (kids.isLoading) return <Loading />;
  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-3xl grad-sky p-5 shadow-card sm:p-7">
        <div className="relative z-10 flex flex-wrap items-center gap-4">
          <Chitti size={110} mood="wave" />
          <div className="flex-1"><p className="font-bold text-navy/70">{t(greetingKey())} 👋</p><h1 className="font-display text-3xl font-extrabold text-navy">{user.full_name}</h1>
            <Bubble className="mt-2 max-w-lg text-navy">{t("ph.hello")}</Bubble></div>
        </div>
        <SchoolScene className="pointer-events-none absolute -bottom-2 right-0 hidden w-[440px] opacity-40 lg:block" />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {(kids.data ?? []).map((k, i) => {
          const g = games[i]?.data; const a = atts[i]?.data;
          return (
            <Card key={k.id} className="p-5">
              <div className="flex items-center gap-3">
                <Chitti size={64} float={false} avatar={g?.avatar} mood="happy" />
                <div className="flex-1"><div className="font-display text-xl font-extrabold">{k.full_name}</div><div className="text-sm font-bold text-mute">{t("ph.class", { c: sectionLabel(secs.data, classes.data, k.section_id) })} · #{k.roll_no ?? "—"}</div></div>
                <Ring value={a?.percentage ?? 0} size={64} stroke={8} color="hsl(var(--mint))"><span className="text-xs font-extrabold">{a?.percentage != null ? Math.round(a.percentage) : "–"}%</span></Ring>
              </div>
              {g && <div className="mt-3 flex flex-wrap gap-2 text-sm"><span className="chip bg-amber-100 text-amber-700">⭐ {t(`level.${g.level.key}`)}</span><span className="chip bg-orange-100 text-orange-700">🔥 {g.streak.current}</span>
                <span className="chip bg-soft text-primary">🏅 {g.badges.filter((b) => b.earned).length}</span><span className="chip bg-line">{g.xp} XP</span></div>}
              <div className="mt-4 grid grid-cols-4 gap-2">
                {[["/parent/attendance", CalendarCheck, "nav.attendance"], ["/parent/progress", Sparkles, "nav.progress"], ["/parent/bus", Bus, "nav.bus"], ["/parent/messages", MessageCircle, "nav.messages"]].map(([to, Ic, l]) => {
                  const I = Ic as typeof Bus;
                  return <Link key={to as string} to={to as string} className="flex flex-col items-center gap-1 rounded-2xl bg-soft/60 p-2 text-center text-[11px] font-bold hover:bg-soft"><I size={18} className="text-primary" />{t(l as string)}</Link>;
                })}
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <LeaveAssistant />
        <div className="space-y-4">
          <Consent />
          <Card className="p-5">
            <div className="mb-2 flex items-center justify-between"><h3 className="font-display text-lg font-extrabold">📢 {t("nav.announcements")}</h3><Link className="text-sm font-bold text-primary" to="/parent/announcements">{t("common.seeAll")}</Link></div>
            <ul className="space-y-2">{(ann.data ?? []).map((x) => <li key={x.id} className="rounded-2xl bg-soft/60 p-3"><b className="text-sm">{x.emoji} {x.title}</b><p className="line-clamp-2 text-xs text-mute">{x.body}</p></li>)}</ul>
          </Card>
          <Card className="flex items-center gap-3 p-5"><Bot className="text-violet-500" size={32} /><div className="flex-1"><b>{t("ph.chittiTitle")}</b><p className="text-sm text-mute">{t("ph.chittiSub")}</p></div>
            <Button asChild><Link to="/parent/chitti">{t("chitti.ask")}</Link></Button></Card>
        </div>
      </div>
    </div>
  );
}

function LeaveAssistant() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [msg, setMsg] = useState("");
  const [d, setD] = useState<Draft | null>(null);
  const parse = useMutation({ mutationFn: () => post<Draft>("/leave-assist/parse", { message: msg }), onSuccess: setD, onError: toastError });
  const submit = useMutation({ mutationFn: () => post("/leave-assist/submit", { student_id: d!.student_id, from_date: d!.from_date, to_date: d!.to_date, leave_type: d!.leave_type, reason: d!.reason }),
    onSuccess: () => { toast(t("ph.leaveSent")); setD(null); setMsg(""); qc.invalidateQueries({ queryKey: ["leave"] }); }, onError: toastError });
  return (
    <Card className="p-5">
      <h3 className="font-display text-lg font-extrabold">✉️ {t("ph.leaveTitle")}</h3>
      <p className="text-sm text-mute">{t("ph.leaveSub")}</p>
      <Textarea className="mt-3" rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={t("ph.leaveExample")} />
      <Button className="mt-2" onClick={() => parse.mutate()} disabled={msg.trim().length < 3 || parse.isPending}><Sparkles size={16} /> {t("ph.understand")}</Button>
      {d && (
        <div className="mt-4 space-y-3 rounded-3xl border-2 border-dashed border-primary/40 bg-soft/40 p-4 animate-fade">
          <div className="flex items-center gap-2 text-sm font-bold">{d.needs_review ? `⚠️ ${t("ph.checkDetails")}` : `✅ ${t("ph.looksRight")}`}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("ph.child")}><Select value={d.student_id ?? ""} onChange={(e) => setD({ ...d, student_id: Number(e.target.value) })}><option value="">—</option>{d.children.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
            <Field label={t("ph.type")}><Select value={d.leave_type} onChange={(e) => setD({ ...d, leave_type: e.target.value })}>{["sick", "casual", "family", "other"].map((x) => <option key={x} value={x}>{t(`leave.types.${x}`, x)}</option>)}</Select></Field>
            <Field label={t("ph.from")}><Input type="date" value={d.from_date} onChange={(e) => setD({ ...d, from_date: e.target.value })} /></Field>
            <Field label={t("ph.to")}><Input type="date" value={d.to_date} onChange={(e) => setD({ ...d, to_date: e.target.value })} /></Field>
          </div>
          <Field label={t("ph.reason")}><Input value={d.reason} onChange={(e) => setD({ ...d, reason: e.target.value })} /></Field>
          <p className="text-xs text-mute">ⓘ {t("ph.neverAuto")}</p>
          <Button className="w-full" disabled={!d.student_id || submit.isPending} onClick={() => submit.mutate()}><Send size={16} /> {t("ph.sendTeacher")}</Button>
        </div>
      )}
    </Card>
  );
}

function Consent() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const c = useQuery({ queryKey: ["consent"], queryFn: () => get<{ student_id: number; name: string; allow: boolean }[]>("/chitti/consent") });
  const set = useMutation({ mutationFn: (b: { student_id: number; allow: boolean }) => put("/chitti/consent", b), onSuccess: () => qc.invalidateQueries({ queryKey: ["consent"] }), onError: toastError });
  return (
    <Card className="p-5">
      <h3 className="flex items-center gap-2 font-display text-lg font-extrabold"><ShieldCheck className="text-ok" size={20} /> {t("ph.consentTitle")}</h3>
      <p className="mb-3 text-sm text-mute">{t("ph.consentSub")}</p>
      {(c.data ?? []).map((k) => (
        <label key={k.student_id} className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl bg-soft/60 p-3">
          <span className="font-bold">{k.name}</span>
          <span className="flex items-center gap-2 text-sm font-bold"><span className={k.allow ? "text-ok" : "text-mute"}>{k.allow ? t("ph.on") : t("ph.off")}</span>
            <input type="checkbox" role="switch" className="h-6 w-11 cursor-pointer appearance-none rounded-full bg-line transition before:block before:h-5 before:w-5 before:translate-x-0.5 before:rounded-full before:bg-white before:shadow before:transition checked:bg-ok checked:before:translate-x-[22px]"
              checked={k.allow} onChange={(e) => set.mutate({ student_id: k.student_id, allow: e.target.checked })} aria-label={t("ph.consentTitle")} /></span>
        </label>
      ))}
    </Card>
  );
}
