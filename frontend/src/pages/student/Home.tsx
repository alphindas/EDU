import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Bot, BrainCircuit, CalendarCheck, Compass, Flame, Gamepad2, Megaphone, Mic, NotebookPen, Sparkles, Target } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { greetingKey } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { SchoolScene, Ring } from "@/components/fun/Art";
import { celebrate, type Reward } from "@/components/fun/Celebrate";
import Chitti, { Bubble } from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { todayISO } from "@/lib/queries";
import type { HistoryOut, Homework } from "@/lib/types";
import { type Announcement, type GameProfile, fmtDate } from "@/lib/v2";
import { cn } from "@/lib/utils";

const WELCOME = ["welcome.0", "welcome.1", "welcome.2", "welcome.3", "welcome.4", "welcome.5", "welcome.6"];

export default function StudentHome() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user)!;
  const game = useQuery({ queryKey: ["game"], queryFn: () => get<GameProfile>("/game/profile") });
  const att = useQuery({ queryKey: ["att-me"], queryFn: () => get<HistoryOut>(`/attendance/students/${user.student_id}`), enabled: !!user.student_id });
  const hw = useQuery({ queryKey: ["hw-home"], queryFn: () => get<Homework[]>("/homework") });
  const ann = useQuery({ queryKey: ["ann"], queryFn: () => get<Announcement[]>("/announcements?limit=3") });
  const exams = useQuery({ queryKey: ["exams-home"], queryFn: () => get<{ id: number; name: string; exam_date: string; subject_id: number }[]>("/exams") });
  const checkin = useMutation({
    mutationFn: () => post<Reward>("/game/checkin"),
    onSuccess: (r) => { celebrate(r); qc.invalidateQueries({ queryKey: ["game"] }); },
    onError: toastError,
  });
  const g = game.data;
  // welcome message rotates daily and nudges by progress
  const welcome = useMemo(() => {
    if (g && g.streak.current >= 3) return t("welcome.streak", { n: g.streak.current });
    const d = new Date().getDate();
    return t(WELCOME[d % WELCOME.length]);
  }, [g, t]);
  const due = (hw.data ?? []).filter((h) => !h.my_submission && h.due_date >= todayISO()).slice(0, 3);
  const upcoming = (exams.data ?? []).filter((e) => e.exam_date >= todayISO()).slice(0, 3);
  const lvlPct = g?.level.xp_for_next ? (100 * g.level.xp_in_level) / g.level.xp_for_next : 100;

  const tiles = [
    { to: "/student/chitti", icon: Bot, label: "nav.chitti", sub: "home.tileChitti", c: "from-violet-100 to-sky-100", ic: "bg-violet-500" },
    { to: "/student/adventure", icon: Gamepad2, label: "nav.adventure", sub: "home.tileAdventure", c: "from-amber-100 to-orange-100", ic: "bg-amber-500" },
    { to: "/student/brain", icon: BrainCircuit, label: "nav.brain", sub: "home.tileBrain", c: "from-rose-100 to-pink-100", ic: "bg-rose-500" },
    { to: "/student/learning", icon: Target, label: "nav.learning", sub: "home.tileLearning", c: "from-emerald-100 to-teal-100", ic: "bg-emerald-500" },
    { to: "/student/english", icon: Mic, label: "nav.english", sub: "home.tileEnglish", c: "from-sky-100 to-cyan-100", ic: "bg-soft0" },
    { to: "/student/attendance", icon: CalendarCheck, label: "nav.attendance", sub: "home.tileAttendance", c: "from-teal-100 to-emerald-50", ic: "bg-teal-500" },
    { to: "/student/library", icon: BookOpen, label: "nav.library", sub: "home.tileLibrary", c: "from-indigo-100 to-sky-50", ic: "bg-indigo-500" },
    { to: "/student/career", icon: Compass, label: "nav.career", sub: "home.tileCareer", c: "from-yellow-100 to-amber-50", ic: "bg-yellow-500" },
  ];

  return (
    <div className="space-y-5">
      {/* hero */}
      <div className="relative overflow-hidden rounded-3xl grad-sky p-5 shadow-card sm:p-7">
        <div className="relative z-10 grid items-center gap-4 md:grid-cols-[1fr_auto]">
          <div>
            <p className="font-bold text-navy/70">{t(greetingKey())} 👋</p>
            <h1 className="font-display text-3xl font-extrabold leading-tight text-navy sm:text-4xl">{user.full_name.split(" ")[0]}!</h1>
            <div className="mt-3 flex items-start gap-3">
              <Bubble className="max-w-md text-navy">{welcome}</Bubble>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {g && !g.checked_in ? (
                <Button variant="sun" size="lg" onClick={() => checkin.mutate()} disabled={checkin.isPending}><Sparkles size={18} /> {t("home.checkin")}</Button>
              ) : (
                <span className="chip bg-white/80 py-1.5 text-sm text-ok">✅ {t("home.checkedIn")}</span>
              )}
              <Button asChild variant="outline" size="lg" className="bg-white/80"><Link to="/student/chitti"><Bot size={18} /> {t("chitti.ask")}</Link></Button>
            </div>
          </div>
          <Chitti size={150} mood={g?.checked_in ? "cheer" : "wave"} avatar={g?.avatar} className="mx-auto hidden sm:block" />
        </div>
        <SchoolScene className="pointer-events-none absolute -bottom-2 right-0 hidden w-[480px] opacity-40 lg:block" />
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="flex items-center gap-3 p-4">
          <Ring value={lvlPct} size={64} stroke={8}><span className="font-display text-lg font-extrabold">{g?.level.level ?? "–"}</span></Ring>
          <div><div className="text-xs font-bold uppercase text-mute">{t("game.level")}</div><div className="font-display text-lg font-extrabold leading-tight">{g ? t(`level.${g.level.key}`) : "…"}</div>
            <div className="text-xs text-mute">{g?.xp ?? 0} XP</div></div>
        </Card>
        <Card className="flex items-center gap-3 p-4">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-orange-100 text-3xl">🔥</div>
          <div><div className="text-xs font-bold uppercase text-mute">{t("game.streak")}</div><div className="font-display text-2xl font-extrabold">{g?.streak.current ?? 0} <span className="text-sm text-mute">{t("game.days")}</span></div></div>
        </Card>
        <Card className="flex items-center gap-3 p-4">
          <div className="grid h-14 w-14 place-items-center rounded-2xl bg-amber-100 text-3xl">🪙</div>
          <div><div className="text-xs font-bold uppercase text-mute">{t("game.coins")}</div><div className="font-display text-2xl font-extrabold">{g?.coins ?? 0}</div></div>
        </Card>
        <Card className="flex items-center gap-3 p-4">
          <Ring value={att.data?.percentage ?? 0} size={64} stroke={8} color="hsl(var(--mint))"><span className="text-sm font-extrabold">{att.data?.percentage != null ? Math.round(att.data.percentage) : "–"}%</span></Ring>
          <div><div className="text-xs font-bold uppercase text-mute">{t("nav.attendance")}</div><div className="text-sm font-semibold text-mute">{t("home.attSub")}</div></div>
        </Card>
      </div>

      {/* quick tiles */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((x) => (
          <Link key={x.to} to={x.to} className={cn("group lift relative overflow-hidden rounded-3xl bg-gradient-to-br p-4 shadow-card", x.c)}>
            <span className={cn("grid h-11 w-11 place-items-center rounded-2xl text-white shadow-chunky transition group-hover:rotate-6 group-hover:scale-110", x.ic)}><x.icon size={22} /></span>
            <div className="mt-3 font-display text-lg font-extrabold leading-tight text-navy">{t(x.label)}</div>
            <div className="text-xs font-semibold text-navy/65">{t(x.sub)}</div>
            <ArrowRight className="absolute right-3 top-4 text-navy/30 transition group-hover:translate-x-1 group-hover:text-navy/70" size={18} />
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* quests */}
        <Card className="p-5 lg:col-span-1">
          <div className="mb-3 flex items-center justify-between"><h3 className="font-display text-lg font-extrabold">🎯 {t("game.todayQuests")}</h3>
            <Link to="/student/adventure" className="text-sm font-bold text-primary">{t("common.seeAll")}</Link></div>
          <div className="space-y-2">
            {(g?.quests ?? []).map((q) => (
              <div key={q.id} className="flex items-center gap-3 rounded-2xl bg-soft/60 p-2.5">
                <span className="text-2xl">{q.emoji}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-bold">{t(`quest.${q.id}`)}</div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full grad-mint transition-all" style={{ width: `${(100 * q.progress) / q.target}%` }} /></div>
                </div>
                <span className={cn("chip", q.claimed ? "bg-ok/15 text-ok" : "bg-amber-100 text-amber-700")}>{q.claimed ? "✓" : `+${q.xp}`}</span>
              </div>
            ))}
          </div>
        </Card>
        {/* homework + exams */}
        <Card className="p-5">
          <h3 className="mb-3 font-display text-lg font-extrabold">📚 {t("home.dueSoon")}</h3>
          {due.length === 0 && upcoming.length === 0 && <p className="py-6 text-center text-sm text-mute">🎉 {t("home.allClear")}</p>}
          <ul className="space-y-2">
            {due.map((h) => (
              <li key={h.id}><Link to="/student/homework" className="flex items-center gap-3 rounded-2xl border-2 border-line p-2.5 hover:border-primary/40">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-100 text-emerald-600"><NotebookPen size={17} /></span>
                <span className="min-w-0 flex-1 truncate text-sm font-bold">{h.title}</span><span className="chip bg-soft text-primary">{fmtDate(h.due_date, i18n.language)}</span></Link></li>
            ))}
            {upcoming.map((e) => (
              <li key={`e${e.id}`}><Link to="/student/exams" className="flex items-center gap-3 rounded-2xl border-2 border-line p-2.5 hover:border-primary/40">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-100 text-lg">📝</span>
                <span className="min-w-0 flex-1 truncate text-sm font-bold">{e.name}</span><span className="chip bg-indigo-100 text-indigo-700">{fmtDate(e.exam_date, i18n.language)}</span></Link></li>
            ))}
          </ul>
        </Card>
        {/* announcements */}
        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between"><h3 className="font-display text-lg font-extrabold"><Megaphone className="mr-1 inline" size={18} /> {t("nav.announcements")}</h3>
            <Link to="/student/announcements" className="text-sm font-bold text-primary">{t("common.seeAll")}</Link></div>
          <ul className="space-y-2">
            {(ann.data ?? []).map((a) => (
              <li key={a.id} className={cn("rounded-2xl p-3", a.pinned ? "bg-amber-50 ring-2 ring-sun/60 dark:bg-soft" : "bg-soft/60")}>
                <div className="text-sm font-extrabold">{a.emoji} {a.title}</div><p className="line-clamp-2 text-xs text-mute">{a.body}</p>
              </li>
            ))}
            {!ann.data?.length && <p className="py-6 text-center text-sm text-mute">{t("common.empty")}</p>}
          </ul>
        </Card>
      </div>

      {/* this week */}
      {g?.week && (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2"><Flame className="text-coral" size={20} /><h3 className="font-display text-lg font-extrabold">{t("home.week")}</h3></div>
          <div className="flex items-end gap-2" style={{ height: 120 }}>
            {g.week.map((d) => {
              const max = Math.max(30, ...g.week!.map((x) => x.xp));
              return (
                <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
                  <span className="text-[11px] font-bold text-mute">{d.xp || ""}</span>
                  <div className={cn("w-full max-w-[44px] rounded-t-xl transition-all", d.xp ? "grad-bg" : "bg-line")} style={{ height: `${Math.max(6, (90 * d.xp) / max)}px` }} />
                  <span className="text-[11px] font-bold">{new Date(d.day).toLocaleDateString(i18n.language, { weekday: "short" })}</span>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
