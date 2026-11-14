import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HeartHandshake, Lock } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Loading } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { celebrate, type Reward } from "@/components/fun/Celebrate";
import Chitti, { Bubble } from "@/components/fun/Chitti";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { get, post } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Today {
  prompt: { id: string; emoji: string; done: boolean };
  missions: { id: string; emoji: string; area: string; done: boolean }[];
  scenario: { id: string; emoji: string; options: string[]; done: boolean };
  note: string;
}
const MOODS = ["😄", "🙂", "😐", "😕", "😢", "😠", "😴", "🤩"];

/** Beyond academics: voluntary reflections, kindness/confidence missions and decision scenarios. Private, no labels. */
export default function Growth() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const today = useQuery({ queryKey: ["growth-today"], queryFn: () => get<Today>("/growth/today") });
  const past = useQuery({ queryKey: ["reflections"], queryFn: () => get<{ id: number; day: string; kind: string; prompt: string; mood: string; text: string }[]>("/growth/reflections") });
  const [mood, setMood] = useState("");
  const [text, setText] = useState("");
  const [pick, setPick] = useState<string | null>(null);
  const done = () => { qc.invalidateQueries({ queryKey: ["growth-today"] }); qc.invalidateQueries({ queryKey: ["reflections"] }); };
  const save = useMutation({
    mutationFn: (b: { kind: string; prompt: string; mood?: string; text?: string }) => post<{ reward: Reward; feedback: { kind: boolean } | null }>("/growth/reflections", b),
    onSuccess: (r) => { celebrate(r.reward); setText(""); done(); }, onError: toastError,
  });
  if (!today.data) return <Loading />;
  const d = today.data;
  return (
    <div className="space-y-5">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-100 via-lime-50 to-pink-50 p-5 shadow-card sm:p-7 dark:from-soft dark:to-soft">
        <div className="flex flex-wrap items-center gap-4"><Chitti size={100} mood="happy" />
          <div className="flex-1"><h1 className="font-display text-3xl font-extrabold text-navy dark:text-ink">🌱 {t("grow.title")}</h1>
            <p className="text-sm font-semibold text-navy/70 dark:text-mute">{t("grow.sub")}</p>
            <p className="mt-1 flex items-center gap-1 text-xs text-mute"><Lock size={12} /> {t("grow.private")}</p></div></div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-display text-xl font-extrabold">{d.prompt.emoji} {t("grow.reflectTitle")}</h2>
          <Bubble className="mt-3">{t(`grow.prompt.${d.prompt.id}`)}</Bubble>
          {d.prompt.done ? <p className="mt-4 chip bg-ok/15 py-1.5 text-sm text-ok">✓ {t("grow.doneToday")}</p> : (
            <>
              <div className="mt-4 text-xs font-bold uppercase text-mute">{t("grow.mood")}</div>
              <div className="mt-1 flex flex-wrap gap-1.5">{MOODS.map((m) => <button key={m} onClick={() => setMood(m)} className={cn("grid h-11 w-11 place-items-center rounded-2xl text-2xl transition", mood === m ? "scale-110 bg-soft ring-2 ring-primary" : "hover:bg-soft")}>{m}</button>)}</div>
              <Textarea className="mt-3" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("grow.writeHint")} />
              <Button className="mt-3 w-full" disabled={!text.trim() || save.isPending} onClick={() => save.mutate({ kind: "reflection", prompt: d.prompt.id, mood, text })}>{t("grow.save")}</Button>
            </>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-display text-xl font-extrabold">🦸 {t("grow.missions")}</h2>
          <p className="text-sm text-mute">{t("grow.missionsSub")}</p>
          <div className="mt-3 space-y-2">
            {d.missions.map((m) => (
              <div key={m.id} className={cn("flex items-center gap-3 rounded-2xl border-2 p-3", m.done ? "border-ok/40 bg-ok/5" : "border-line")}>
                <span className="text-3xl">{m.emoji}</span>
                <div className="flex-1"><div className="font-bold">{t(`grow.mission.${m.id}`)}</div><span className="chip bg-soft text-primary">{t(`grow.area.${m.area}`)}</span></div>
                {m.done ? <span className="text-2xl">✅</span> : <Button size="sm" variant="mint" onClick={() => save.mutate({ kind: "mission", prompt: m.id, text: "done" })}>{t("grow.didIt")}</Button>}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <h2 className="font-display text-xl font-extrabold">{d.scenario.emoji} {t("grow.scenario")}</h2>
        <Bubble className="mt-3 text-base">{t(`grow.scen.${d.scenario.id}.q`)}</Bubble>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {d.scenario.options.map((o) => (
            <button key={o} disabled={d.scenario.done || !!save.data?.feedback} onClick={() => { setPick(o); save.mutate({ kind: "scenario", prompt: d.scenario.id, text: o }); }}
              className={cn("rounded-2xl border-2 px-4 py-3 text-left font-bold transition", pick === o ? "border-primary bg-soft" : "border-line hover:border-primary/50")}>{t(`grow.scen.${d.scenario.id}.${o}`)}</button>
          ))}
        </div>
        {save.data?.feedback && <div className="mt-3 flex items-center gap-3 animate-fade"><Chitti size={56} mood={save.data.feedback.kind ? "cheer" : "think"} float={false} />
          <Bubble>{save.data.feedback.kind ? t("grow.scenGood") : t("grow.scenThink")} {t(`grow.scen.${d.scenario.id}.why`)}</Bubble></div>}
        {d.scenario.done && !save.data && <p className="mt-3 chip bg-ok/15 py-1.5 text-sm text-ok">✓ {t("grow.doneToday")}</p>}
      </Card>

      <div className="flex flex-wrap items-center gap-3 rounded-3xl bg-rose-50 p-4 text-sm dark:bg-soft">
        <HeartHandshake className="text-rose-500" /><span className="flex-1 font-semibold">{t("grow.talk")}</span>
        <Button asChild variant="outline" size="sm"><Link to="/student/counselling">{t("nav.counselling")}</Link></Button>
      </div>

      {!!past.data?.length && (
        <Card className="p-5">
          <h3 className="mb-3 font-display text-lg font-extrabold">📔 {t("grow.journal")}</h3>
          <ul className="space-y-2">{past.data.filter((r) => r.kind === "reflection").map((r) => (
            <li key={r.id} className="rounded-2xl bg-soft/60 p-3 text-sm"><span className="mr-2 text-xl">{r.mood}</span><b>{new Date(r.day).toLocaleDateString(i18n.language)}</b> · {t(`grow.prompt.${r.prompt}`)}<p className="mt-1">{r.text}</p></li>
          ))}</ul>
        </Card>
      )}
    </div>
  );
}
