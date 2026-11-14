import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import WithChild from "@/components/common/ChildPicker";
import { BADGE_EMOJI } from "@/components/fun/Celebrate";
import { Card } from "@/components/ui/card";
import { get } from "@/lib/api";
import type { GameProfile } from "@/lib/v2";
import Brain from "@/pages/student/Brain";
import Projects from "@/pages/shared/Projects";
import { cn } from "@/lib/utils";

/** Parent view of a child's growth: adventure summary, Learning Growth Score, English fluency, portfolio, career ideas. */
export default function ParentProgress() {
  return <WithChild>{(c) => <ChildProgress id={c.id} />}</WithChild>;
}

function ChildProgress({ id }: { id: number }) {
  const { t } = useTranslation();
  const g = useQuery({ queryKey: ["game", id], queryFn: () => get<GameProfile>(`/game/profile?student_id=${id}`) });
  const eng = useQuery({ queryKey: ["eng", id], queryFn: () => get<{ average: number; sessions: { score: number }[] }>(`/english/progress?student_id=${id}`) });
  const car = useQuery({ queryKey: ["car", id], queryFn: () => get<{ suggestions: { area: string; careers: { name: string; emoji: string }[] }[] } | null>(`/career/latest?student_id=${id}`) });
  return (
    <div className="space-y-5">
      {g.data && (
        <Card className="p-5">
          <h2 className="mb-3 font-display text-xl font-extrabold">🎮 {t("pp.adventure")}</h2>
          <div className="flex flex-wrap gap-2"><span className="chip bg-amber-100 py-1 text-sm text-amber-700">⭐ {t(`level.${g.data.level.key}`)} · {g.data.xp} XP</span>
            <span className="chip bg-orange-100 py-1 text-sm text-orange-700">🔥 {t("pp.streak", { n: g.data.streak.current, b: g.data.streak.best })}</span></div>
          <div className="mt-3 flex flex-wrap gap-2">{g.data.badges.filter((b) => b.earned).map((b) => <span key={b.id} className="chip bg-soft py-1 text-sm">{BADGE_EMOJI[b.id]} {t(`badge.${b.id}.name`)}</span>)}</div>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">{g.data.worlds.map((w) => (
            <div key={w.id} className="rounded-2xl bg-soft/60 p-2 text-center"><div className="text-2xl">{w.emoji}</div><div className="text-xs font-bold">{t(`world.${w.id}`)}</div>
              <div className="mt-1 flex gap-0.5">{Array.from({ length: w.stages }, (_, i) => <span key={i} className={cn("h-1.5 flex-1 rounded-full", i < w.stage ? "grad-sun" : "bg-line")} />)}</div></div>))}</div>
        </Card>
      )}
      <Brain studentId={id} />
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-5"><h3 className="font-display text-lg font-extrabold">🗣️ {t("pp.english")}</h3>
          <p className="mt-2 text-sm">{eng.data?.sessions.length ? t("pp.englishBody", { n: eng.data.sessions.length, avg: eng.data.average }) : t("pp.englishNone")}</p>
          <p className="mt-1 text-xs text-mute">{t("pp.englishPrivate")}</p></Card>
        <Card className="p-5"><h3 className="font-display text-lg font-extrabold">🧭 {t("pp.career")}</h3>
          {car.data ? <div className="mt-2 flex flex-wrap gap-2">{car.data.suggestions.flatMap((s) => s.careers.slice(0, 2)).map((c) => <span key={c.name} className="chip bg-soft py-1 text-sm">{c.emoji} {c.name}</span>)}</div>
            : <p className="mt-2 text-sm text-mute">{t("pp.careerNone")}</p>}
          <p className="mt-2 text-xs text-mute">{t("career.note")}</p></Card>
      </div>
      <Projects studentId={id} />
    </div>
  );
}
