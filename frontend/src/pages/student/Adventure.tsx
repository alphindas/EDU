import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gift, Lock, ShoppingBag, Swords, Trophy, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Ring, WORLD_COLORS, WorldArt } from "@/components/fun/Art";
import { BADGE_EMOJI, celebrate, type Reward } from "@/components/fun/Celebrate";
import Chitti from "@/components/fun/Chitti";
import PuzzleView from "@/components/fun/Puzzle";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { get, patch, post } from "@/lib/api";
import type { GameProfile, Puzzle } from "@/lib/v2";
import { cn } from "@/lib/utils";

const TEAM_EMOJI: Record<string, string> = { sky_hawks: "🦅", mint_turtles: "🐢", sun_foxes: "🦊", lavender_owls: "🦉" };
const MISSIONS = ["shapes", "teach", "measure", "plant", "story", "kindness", "recycle", "stars"];

export default function Adventure() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["game"], queryFn: () => get<GameProfile>("/game/profile") });
  const lb = useQuery({ queryKey: ["leaderboard"], queryFn: () => get<{ people: { student_id: number; name: string; xp: number; me: boolean }[]; teams: { team: string; xp: number }[]; hidden: number }>("/game/leaderboard") });
  const [boss, setBoss] = useState<string | null>(null);
  const [mystery, setMystery] = useState(false);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["game"] }); qc.invalidateQueries({ queryKey: ["leaderboard"] }); };
  const claim = useMutation({ mutationFn: (id: string) => post<Reward>(`/game/quests/${id}/claim`), onSuccess: (r) => { celebrate(r); refresh(); }, onError: toastError });
  const buy = useMutation({ mutationFn: (id: string) => post(`/game/shop/${id}/buy`), onSuccess: () => { toast(t("game.bought")); refresh(); }, onError: toastError });
  const prefs = useMutation({ mutationFn: (b: object) => patch("/game/prefs", b), onSuccess: refresh, onError: toastError });
  if (q.isLoading || !q.data) return <Loading />;
  const g = q.data;
  const lvlPct = g.level.xp_for_next ? (100 * g.level.xp_in_level) / g.level.xp_for_next : 100;
  const equip = (slot: "hat" | "color" | "pet", id: string) => prefs.mutate({ avatar: { ...g.avatar, [slot]: g.avatar[slot] === id ? "" : id } });

  return (
    <div className="space-y-5">
      {/* hero */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-amber-100 via-orange-50 to-sky-100 p-5 shadow-card sm:p-7 dark:from-soft dark:via-soft dark:to-soft">
        <div className="grid items-center gap-5 md:grid-cols-[auto_1fr_auto]">
          <Chitti size={130} mood="cheer" avatar={g.avatar} className="mx-auto" />
          <div>
            <p className="text-sm font-extrabold uppercase tracking-widest text-amber-700">{t("game.title")}</p>
            <h1 className="font-display text-3xl font-extrabold text-navy dark:text-ink">{t(`level.${g.level.key}`)}</h1>
            <div className="mt-2 flex items-center gap-3">
              <div className="h-4 flex-1 overflow-hidden rounded-full border-2 border-navy/10 bg-white"><div className="h-full rounded-full grad-sun transition-all duration-700" style={{ width: `${lvlPct}%` }} /></div>
              <span className="text-sm font-extrabold">{g.level.xp_for_next ? `${g.level.xp_in_level}/${g.level.xp_for_next}` : "MAX"}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="chip bg-white text-base text-primary">⭐ {g.xp} XP</span>
              <span className="chip bg-white text-base text-amber-600">🪙 {g.coins}</span>
              <span className="chip bg-white text-base text-orange-600">🔥 {g.streak.current} · {t("game.best", { n: g.streak.best })}</span>
              <span className="chip bg-white text-base text-primary" title={t("game.freezeHelp")}>🧊 {g.streak.freezes}</span>
              <span className="chip bg-white text-base">{TEAM_EMOJI[g.team]} {t(`team.${g.team}`)}</span>
            </div>
          </div>
          <Ring value={lvlPct} size={110} stroke={12} color="hsl(var(--sun))"><div><div className="text-[10px] font-bold uppercase text-mute">{t("game.level")}</div><div className="font-display text-3xl font-extrabold">{g.level.level}</div></div></Ring>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* quests */}
        <Card className="p-5 lg:col-span-2">
          <h2 className="mb-3 font-display text-xl font-extrabold">🎯 {t("game.todayQuests")}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {(g.quests ?? []).map((x) => (
              <div key={x.id} className={cn("rounded-3xl border-2 p-4 text-center transition", x.claimed ? "border-ok/40 bg-ok/5" : x.done ? "border-sun bg-amber-50 animate-pop dark:bg-soft" : "border-line")}>
                <div className="text-4xl">{x.emoji}</div>
                <div className="mt-1 min-h-[2.5rem] text-sm font-extrabold">{t(`quest.${x.id}`)}</div>
                <div className="my-2 h-2.5 overflow-hidden rounded-full bg-line"><div className="h-full grad-mint" style={{ width: `${(100 * x.progress) / x.target}%` }} /></div>
                <div className="mb-2 text-xs font-bold text-mute">{x.progress}/{x.target} · +{x.xp} XP · +{x.coins} 🪙</div>
                {x.claimed ? <span className="chip bg-ok/15 text-ok">✓ {t("game.claimed")}</span>
                  : <Button size="sm" variant={x.done ? "sun" : "outline"} disabled={!x.done || claim.isPending} onClick={() => claim.mutate(x.id)}>{x.done ? t("game.claim") : t("game.inProgress")}</Button>}
              </div>
            ))}
          </div>
        </Card>
        {/* mystery */}
        <Card className="relative overflow-hidden p-5 text-center">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-100 to-pink-100 opacity-70 dark:opacity-10" aria-hidden />
          <div className="relative">
            <h2 className="font-display text-xl font-extrabold">🎁 {t("game.mystery")}</h2>
            <p className="text-sm text-mute">{t("game.mysterySub")}</p>
            <button disabled={g.mystery_done} onClick={() => setMystery(true)} className={cn("mx-auto my-4 grid h-28 w-28 place-items-center rounded-3xl text-6xl shadow-pop transition", g.mystery_done ? "bg-line grayscale" : "grad-lav hover:rotate-3 hover:scale-105 animate-float")} aria-label={t("game.openMystery")}>
              <Gift size={56} className="text-white" />
            </button>
            <span className="text-sm font-bold">{g.mystery_done ? t("game.mysteryDone") : t("game.openMystery")}</span>
          </div>
        </Card>
      </div>

      {/* worlds */}
      <Card className="p-5">
        <h2 className="mb-1 font-display text-xl font-extrabold">🗺️ {t("game.worlds")}</h2>
        <p className="mb-4 text-sm text-mute">{t("game.worldsSub")}</p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {g.worlds.map((w) => (
            <div key={w.id} className={cn("lift overflow-hidden rounded-3xl border-2 border-line bg-gradient-to-b", WORLD_COLORS[w.id])}>
              <div className="h-28 p-2"><WorldArt id={w.id} /></div>
              <div className="bg-card/85 p-3">
                <div className="font-display text-lg font-extrabold leading-tight">{w.emoji} {t(`world.${w.id}`)}</div>
                <div className="my-2 flex gap-1" aria-label={t("game.stage", { n: w.stage, total: w.stages })}>
                  {Array.from({ length: w.stages }, (_, i) => <span key={i} className={cn("h-3 flex-1 rounded-full", i < w.stage ? "grad-sun" : "bg-line")} />)}
                </div>
                <div className="text-xs font-bold text-mute">{t("game.stage", { n: w.stage, total: w.stages })} · {w.xp} XP</div>
                <Button size="sm" className="mt-2 w-full" variant="default" onClick={() => setBoss(w.id)}><Swords size={15} /> {t("game.boss")}</Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* badges */}
        <Card className="p-5">
          <h2 className="mb-3 font-display text-xl font-extrabold">🏅 {t("game.badges")} <span className="text-sm text-mute">({g.badges.filter((b) => b.earned).length}/{g.badges.length})</span></h2>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            {g.badges.map((b) => (
              <div key={b.id} title={t(`badge.${b.id}.desc`)} className={cn("flex flex-col items-center rounded-2xl p-2 text-center", b.earned ? "bg-amber-50 ring-2 ring-sun/50 dark:bg-soft" : "bg-soft/40")}>
                <span className={cn("text-4xl", !b.earned && "opacity-30 grayscale")}>{BADGE_EMOJI[b.id] ?? b.emoji}</span>
                <span className="mt-1 text-[11px] font-extrabold leading-tight">{t(`badge.${b.id}.name`)}</span>
                {!b.earned && <span className="mt-0.5 flex items-center gap-0.5 text-[10px] text-mute"><Lock size={10} />{t(`badge.${b.id}.desc`)}</span>}
              </div>
            ))}
          </div>
        </Card>
        {/* teams + leaderboard */}
        <Card className="p-5">
          <h2 className="mb-3 flex items-center gap-2 font-display text-xl font-extrabold"><Users size={20} /> {t("game.teams")}</h2>
          <div className="space-y-2">
            {(lb.data?.teams ?? []).map((x, i) => {
              const max = Math.max(1, ...(lb.data?.teams ?? []).map((y) => y.xp));
              return (
                <div key={x.team} className="flex items-center gap-2">
                  <span className="w-6 text-center text-xl">{TEAM_EMOJI[x.team]}</span>
                  <span className={cn("w-32 truncate text-sm font-bold", x.team === g.team && "text-primary")}>{t(`team.${x.team}`)}</span>
                  <div className="h-5 flex-1 overflow-hidden rounded-full bg-line"><div className={cn("h-full rounded-full", ["grad-sun", "grad-bg", "grad-mint", "grad-lav"][i % 4])} style={{ width: `${(100 * x.xp) / max}%` }} /></div>
                  <span className="w-14 text-right text-xs font-extrabold">{x.xp}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-5 flex items-center justify-between gap-2 border-t-2 border-line pt-4">
            <h3 className="flex items-center gap-2 font-display text-lg font-extrabold"><Trophy size={18} /> {t("game.leaderboard")}</h3>
            <label className="flex cursor-pointer items-center gap-2 text-sm font-bold">
              <input type="checkbox" className="h-5 w-5 accent-[hsl(var(--ac))]" checked={g.leaderboard_opt_in} onChange={(e) => prefs.mutate({ leaderboard_opt_in: e.target.checked })} />{t("game.showMe")}
            </label>
          </div>
          <p className="text-xs text-mute">{t("game.lbPrivacy", { n: lb.data?.hidden ?? 0 })}</p>
          <ol className="mt-2 space-y-1">
            {(lb.data?.people ?? []).map((p, i) => (
              <li key={p.student_id} className={cn("flex items-center gap-2 rounded-xl px-2 py-1.5 text-sm", p.me && "bg-soft font-extrabold")}>
                <span className="w-6 text-center">{["🥇", "🥈", "🥉"][i] ?? i + 1}</span><span className="flex-1">{p.name}</span><span className="font-bold">{p.xp} XP</span>
              </li>
            ))}
          </ol>
        </Card>
      </div>

      {/* shop */}
      <Card className="p-5">
        <h2 className="mb-1 flex items-center gap-2 font-display text-xl font-extrabold"><ShoppingBag size={20} /> {t("game.shop")}</h2>
        <p className="mb-4 text-sm text-mute">{t("game.shopSub")}</p>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {(g.shop ?? []).map((it) => {
            const slot = it.id.split("_")[0] as "hat" | "color" | "pet";
            const on = g.avatar[slot] === it.id;
            return (
              <div key={it.id} className={cn("flex flex-col items-center gap-1 rounded-2xl border-2 p-3", on ? "border-primary bg-soft" : "border-line")}>
                <span className="text-4xl">{it.emoji}</span>
                <span className="text-center text-[11px] font-bold">{t(`shop.${it.id}`)}</span>
                {it.owned ? <Button size="sm" variant={on ? "default" : "outline"} onClick={() => equip(slot, it.id)}>{on ? t("game.wearing") : t("game.wear")}</Button>
                  : <Button size="sm" variant="sun" disabled={g.coins < it.cost || buy.isPending} onClick={() => buy.mutate(it.id)}>🪙 {it.cost}</Button>}
              </div>
            );
          })}
        </div>
      </Card>

      {/* real-world missions (offline activities kids do with family/friends) */}
      <Card className="p-5">
        <h2 className="mb-1 font-display text-xl font-extrabold">🌍 {t("game.realWorld")}</h2>
        <p className="mb-4 text-sm text-mute">{t("game.realWorldSub")}</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {MISSIONS.map((m, i) => (
            <div key={m} className={cn("rounded-3xl p-4", ["bg-soft", "bg-amber-50", "bg-emerald-50", "bg-violet-50"][i % 4], "dark:bg-soft")}>
              <div className="text-3xl">{t(`mission.${m}.emoji`)}</div>
              <div className="mt-1 font-extrabold">{t(`mission.${m}.title`)}</div>
              <p className="text-sm text-mute">{t(`mission.${m}.body`)}</p>
            </div>
          ))}
        </div>
      </Card>

      {boss && <BossDialog world={boss} onClose={() => { setBoss(null); refresh(); }} />}
      {mystery && <MysteryDialog onClose={() => { setMystery(false); refresh(); }} />}
    </div>
  );
}

function BossDialog({ world, onClose }: { world: string; onClose: () => void }) {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["boss", world], queryFn: () => get<{ puzzles: Puzzle[]; done_today: boolean; difficulty: number }>(`/game/boss/${world}`), staleTime: Infinity, gcTime: 0 });
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<{ token: string; choice: number; time_ms: number }[]>([]);
  const submit = useMutation({
    mutationFn: (a: typeof answers) => post<{ right: number; total: number; won: boolean; reward: Reward | null }>(`/game/boss/${world}`, { answers: a }),
    onSuccess: (r) => celebrate(r.reward), onError: toastError,
  });
  const ps = q.data?.puzzles ?? [];
  const pick = (c: number, ms: number) => {
    const next = [...answers, { token: ps[i].token, choice: c, time_ms: ms }];
    setAnswers(next);
    setTimeout(() => { if (i + 1 < ps.length) setI(i + 1); else submit.mutate(next); }, 350);
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={`⚔️ ${t("game.bossOf", { world: t(`world.${world}`) })}`} description={t("game.bossSub")} className="max-w-xl">
        {q.isLoading && <Loading />}
        {q.data?.done_today && !submit.data && <p className="mb-3 rounded-2xl bg-amber-50 p-3 text-sm font-bold dark:bg-soft">{t("game.bossDoneToday")}</p>}
        {submit.data ? (
          <div className="flex flex-col items-center gap-2 text-center">
            <Chitti size={110} mood={submit.data.won ? "cheer" : "happy"} />
            <div className="font-display text-3xl font-extrabold">{submit.data.right}/{submit.data.total}</div>
            <p className="font-bold">{submit.data.won ? t("game.bossWon") : t("game.bossTry")}</p>
            <Button onClick={onClose}>{t("common.close")}</Button>
          </div>
        ) : ps[i] && (
          <>
            <div className="mb-3 flex gap-1">{ps.map((_, k) => <span key={k} className={cn("h-2 flex-1 rounded-full", k < i ? "grad-sun" : k === i ? "bg-primary" : "bg-line")} />)}</div>
            <div className="mb-2 flex items-center gap-2"><span className="text-2xl">{ps[i].emoji}</span><span className="chip bg-soft text-primary">{t(`skill.${ps[i].skill}`)}</span></div>
            <PuzzleView key={ps[i].token} p={ps[i]} picked={answers[i]?.choice ?? null} onPick={pick} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MysteryDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["mystery"], queryFn: () => get<{ questions: { q: string; o: string[]; topic: string }[]; done: boolean }>("/game/mystery") });
  const [choices, setChoices] = useState<number[]>([]);
  const submit = useMutation({
    mutationFn: (c: number[]) => post<{ right: number; answers: number[]; explanations: string[]; reward: Reward }>("/game/mystery", { choices: c }),
    onSuccess: (r) => celebrate(r.reward), onError: toastError,
  });
  const qs = q.data?.questions ?? [];
  const i = choices.length;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={`🎁 ${t("game.mystery")}`} className="max-w-xl">
        {submit.data ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3"><Chitti size={70} mood="cheer" /><div className="font-display text-2xl font-extrabold">{submit.data.right}/3 · +{submit.data.reward.coins} 🪙</div></div>
            {qs.map((x, k) => (
              <div key={k} className={cn("rounded-2xl p-3 text-sm", choices[k] === submit.data!.answers[k] ? "bg-ok/10" : "bg-bad/10")}>
                <b>{x.q}</b><div>✔ {x.o[submit.data!.answers[k]]} — {submit.data!.explanations[k]}</div>
              </div>
            ))}
            <Button onClick={onClose} className="w-full">{t("common.close")}</Button>
          </div>
        ) : qs[i] ? (
          <div>
            <span className="chip bg-lav/30 text-violet-700">🏷️ {qs[i].topic}</span>
            <p className="my-3 font-display text-xl font-bold">{qs[i].q}</p>
            <div className="grid gap-2">{qs[i].o.map((o, k) => (
              <button key={k} onClick={() => { const c = [...choices, k]; setChoices(c); if (c.length === qs.length) submit.mutate(c); }}
                className="rounded-2xl border-2 border-line px-4 py-3 text-left font-bold hover:border-primary hover:bg-soft">{o}</button>
            ))}</div>
          </div>
        ) : <Loading />}
      </DialogContent>
    </Dialog>
  );
}
