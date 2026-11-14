import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Info, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { Ring } from "@/components/fun/Art";
import { celebrate } from "@/components/fun/Celebrate";
import Chitti, { Bubble } from "@/components/fun/Chitti";
import PuzzleView from "@/components/fun/Puzzle";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AnswerOut, Puzzle, Scores } from "@/lib/v2";
import { cn } from "@/lib/utils";

const SKILLS = ["logical", "numerical", "pattern", "memory", "problem", "spatial", "verbal", "critical"];
const COLORS = ["#8B5CF6", "#0EA5E9", "#F59E0B", "#EC4899", "#10B981", "#6366F1", "#F97316", "#14B8A6"];

/** Knowledge Growth: adaptive brain games with a "Learning Growth Score" per skill (explicitly NOT an IQ score). */
export default function Brain({ studentId }: { studentId?: number }) {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user?.role);
  const qc = useQueryClient();
  const sc = useQuery({ queryKey: ["growth-scores", studentId], queryFn: () => get<Scores>(`/growth/scores${studentId ? `?student_id=${studentId}` : ""}`) });
  const [skill, setSkill] = useState<string | null>(null);
  const [p, setP] = useState<Puzzle | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [res, setRes] = useState<AnswerOut | null>(null);
  const [session, setSession] = useState({ right: 0, total: 0 });
  const load = useMutation({ mutationFn: (s: string) => get<Puzzle>(`/growth/puzzle?skill=${s}`), onSuccess: (x) => { setP(x); setPicked(null); setRes(null); }, onError: toastError });
  const answer = useMutation({
    mutationFn: ({ c, ms }: { c: number; ms: number }) => post<AnswerOut>("/growth/answer", { token: p!.token, choice: c, time_ms: ms }),
    onSuccess: (r) => { setRes(r); celebrate(r.reward); setSession((s) => ({ right: s.right + (r.correct ? 1 : 0), total: s.total + 1 })); qc.invalidateQueries({ queryKey: ["growth-scores"] }); },
    onError: toastError,
  });
  useEffect(() => { if (skill) load.mutate(skill); }, [skill]); // eslint-disable-line react-hooks/exhaustive-deps
  if (sc.isLoading || !sc.data) return <Loading />;
  const s = sc.data;
  const canPlay = role === "student";

  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-rose-100 via-violet-50 to-sky-100 p-5 shadow-card sm:p-7 dark:from-soft dark:to-soft">
        <div className="grid items-center gap-5 md:grid-cols-[auto_1fr]">
          <Ring value={s.overall} size={130} stroke={14} color="#EC4899"><div><div className="font-display text-4xl font-extrabold">{s.overall}</div><div className="text-[10px] font-bold uppercase text-mute">/ 100</div></div></Ring>
          <div>
            <p className="text-sm font-extrabold uppercase tracking-widest text-rose-600">{t("brain.kicker")}</p>
            <h1 className="font-display text-3xl font-extrabold text-navy dark:text-ink">{t("brain.title")}</h1>
            <p className="mt-1 max-w-xl text-sm font-semibold text-navy/70 dark:text-mute">{t("brain.sub")}</p>
            <p className="mt-2 flex items-start gap-1.5 text-xs text-mute"><Info size={14} className="mt-0.5 shrink-0" /> {t("brain.notIq")}</p>
            {canPlay && (
              <Button className="mt-3" variant="sun" onClick={() => setSkill(s.recommend)}>{t("brain.tryRecommended", { skill: t(`skill.${s.recommend}`) })} <ArrowRight size={16} /></Button>
            )}
          </div>
        </div>
      </div>

      {canPlay && skill && (
        <Card className="p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-3xl">{p?.emoji}</span>
            <h2 className="mr-auto font-display text-xl font-extrabold">{t(`skill.${skill}`)}</h2>
            {p && <span className="chip bg-soft text-primary">{t("brain.level", { n: p.difficulty })} {"⭐".repeat(p.difficulty)}</span>}
            <span className="chip bg-ok/15 text-ok">✅ {session.right}/{session.total}</span>
            <Button variant="ghost" size="sm" onClick={() => { setSkill(null); setP(null); }}>{t("common.close")}</Button>
          </div>
          {load.isPending && <Loading />}
          {p && !load.isPending && (
            <>
              <PuzzleView p={p} picked={picked} result={res} onPick={(c, ms) => { setPicked(c); answer.mutate({ c, ms }); }} />
              {res && (
                <div className="mt-4 flex flex-wrap items-center gap-3 animate-fade">
                  <Chitti size={60} mood={res.correct ? "cheer" : "think"} float={false} />
                  <Bubble className="flex-1">{res.correct ? t("brain.right") : t("brain.wrong")} {res.explanation}</Bubble>
                  <Button onClick={() => load.mutate(skill)}>{t("brain.next")} <ArrowRight size={16} /></Button>
                </div>
              )}
            </>
          )}
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {SKILLS.map((k, i) => {
          const v = s.skills[k];
          return (
            <button key={k} disabled={!canPlay} onClick={() => setSkill(k)}
              className={cn("lift flex flex-col items-center gap-2 rounded-3xl border-2 bg-card p-4 text-center shadow-card", skill === k ? "border-primary" : "border-line", k === s.recommend && "ring-4 ring-sun/50")}>
              <Ring value={v.score} size={78} stroke={9} color={COLORS[i]}><span className="text-2xl">{s.emoji[k]}</span></Ring>
              <div className="font-display text-base font-extrabold leading-tight">{t(`skill.${k}`)}</div>
              <div className="text-xs font-bold text-mute">{v.attempts ? `${v.score}/100 · ${v.accuracy}%` : t("brain.notTried")}</div>
              {v.trend !== 0 && <span className={cn("chip", v.trend > 0 ? "bg-ok/15 text-ok" : "bg-amber-100 text-amber-700")}>{v.trend > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}{v.trend > 0 ? "+" : ""}{v.trend}%</span>}
              {k === s.recommend && <span className="chip bg-amber-100 text-amber-700">✨ {t("brain.recommended")}</span>}
            </button>
          );
        })}
      </div>

      {s.history.length > 1 && (
        <Card className="p-5">
          <h3 className="mb-3 font-display text-lg font-extrabold">📈 {t("brain.history")}</h3>
          <div className="h-48">
            <ResponsiveContainer><BarChart data={s.history}><XAxis dataKey="week" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="accuracy" fill="#EC4899" radius={[8, 8, 0, 0]} /></BarChart></ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  );
}
