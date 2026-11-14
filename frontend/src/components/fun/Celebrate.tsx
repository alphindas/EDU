import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { create } from "zustand";
import Chitti from "./Chitti";
import { Button } from "@/components/ui/button";

/** Reward celebration: any API response with a `reward` (xp, coins, new_badges, level_up) can be passed to
 * `celebrate()`. Small rewards show a floating "+XP" pill; badges / level-ups get confetti + a cheering CHITTI. */
export interface Reward { xp: number; coins: number; new_badges: string[]; level_up: number | null; streak?: number }
interface S { pill: Reward | null; big: Reward | null; set: (p: Partial<S>) => void }
export const useCelebrate = create<S>((set) => ({ pill: null, big: null, set: (p) => set(p) }));
let timer: ReturnType<typeof setTimeout> | undefined;

export function celebrate(r?: Reward | null) {
  if (!r) return;
  const s = useCelebrate.getState();
  if (r.new_badges?.length || r.level_up) s.set({ big: r });
  s.set({ pill: r });
  clearTimeout(timer);
  timer = setTimeout(() => useCelebrate.getState().set({ pill: null }), 2600);
}

const COLORS = ["#FACC15", "#0EA5E9", "#34D399", "#A78BFA", "#FB7185", "#F97316"];
export const BADGE_EMOJI: Record<string, string> = {
  first_explorer: "🧭", knowledge_seeker: "🔎", math_master: "👑", word_wizard: "🪄", puzzle_champion: "🧩", consistency_star: "🌟",
  innovation_hero: "💡", improvement_champion: "📈", boss_slayer: "🐉", kindness_heart: "💖", curious_mind: "❓", early_bird: "🐦",
};

export function Confetti({ count = 70 }: { count?: number }) {
  const bits = useMemo(() => Array.from({ length: count }, (_, i) => ({
    left: Math.random() * 100, delay: Math.random() * 0.8, dur: 2 + Math.random() * 1.6, color: COLORS[i % COLORS.length],
    w: 6 + Math.random() * 6, round: Math.random() > 0.6,
  })), [count]);
  return (
    <div className="pointer-events-none fixed inset-0 z-[80] overflow-hidden" aria-hidden>
      {bits.map((b, i) => (
        <span key={i} className="absolute top-0 animate-confetti" style={{ left: `${b.left}%`, width: b.w, height: b.round ? b.w : b.w * 1.6, background: b.color,
          borderRadius: b.round ? 999 : 2, animationDelay: `${b.delay}s`, animationDuration: `${b.dur}s` }} />
      ))}
    </div>
  );
}

export function CelebrationLayer() {
  const { t } = useTranslation();
  const { pill, big, set } = useCelebrate();
  useEffect(() => {
    if (!big) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && set({ big: null });
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [big, set]);
  return (
    <>
      {pill && pill.xp > 0 && (
        <div className="pointer-events-none fixed left-1/2 top-20 z-[70] -translate-x-1/2 animate-pop" role="status">
          <div className="flex items-center gap-2 rounded-full border-2 border-sun bg-card px-4 py-2 font-display text-lg font-extrabold shadow-pop">
            <span className="text-primary">+{pill.xp} XP</span>{pill.coins > 0 && <span className="text-warn">+{pill.coins} 🪙</span>}
            {pill.streak ? <span className="text-coral">🔥 {pill.streak}</span> : null}
          </div>
        </div>
      )}
      {big && (
        <>
          <Confetti />
          <div className="fixed inset-0 z-[75] grid place-items-center bg-navy/30 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={t("fun.celebrate")}>
            <div className="w-full max-w-sm rounded-3xl border-4 border-sun bg-card p-6 text-center shadow-pop animate-pop">
              <Chitti size={110} mood="cheer" />
              <h2 className="mt-2 font-display text-2xl font-extrabold">{big.level_up ? t("fun.levelUp", { n: big.level_up }) : t("fun.newBadge")}</h2>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                {big.new_badges.map((b) => (
                  <div key={b} className="rounded-2xl bg-soft px-3 py-2 animate-pop">
                    <div className="text-3xl">{BADGE_EMOJI[b] ?? "🏅"}</div>
                    <div className="text-xs font-bold">{t(`badge.${b}.name`)}</div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-sm text-mute">{t("fun.keepGoing")}</p>
              <Button className="mt-4 w-full" variant="sun" onClick={() => set({ big: null })} autoFocus>{t("fun.yay")}</Button>
            </div>
          </div>
        </>
      )}
    </>
  );
}
