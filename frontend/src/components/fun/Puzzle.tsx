import { Eye } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Puzzle } from "@/lib/v2";
import { cn } from "@/lib/utils";

/** One skill puzzle. Memory puzzles first flash their sequence, then hide it before showing the question. */
export default function PuzzleView({ p, picked, result, onPick }: {
  p: Puzzle; picked: number | null; result?: { correct: boolean; answer: number } | null; onPick: (i: number, ms: number) => void;
}) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<"show" | "ask">(p.show ? "show" : "ask");
  const [left, setLeft] = useState(p.seconds ?? 0);
  const t0 = useRef(Date.now());
  useEffect(() => {
    setPhase(p.show ? "show" : "ask");
    setLeft(p.seconds ?? 0);
    t0.current = Date.now();
  }, [p.token, p.show, p.seconds]);
  useEffect(() => {
    if (phase !== "show") return;
    if (left <= 0) { setPhase("ask"); t0.current = Date.now(); return; }
    const id = setTimeout(() => setLeft((x) => x - 1), 1000);
    return () => clearTimeout(id);
  }, [phase, left]);

  if (phase === "show") {
    return (
      <div className="flex flex-col items-center gap-3 py-4 text-center">
        <div className="flex items-center gap-2 text-sm font-bold text-mute"><Eye size={16} /> {t("brain.memorise", { n: left })}</div>
        <div className="flex flex-wrap justify-center gap-2">
          {p.show!.map((x, i) => (
            <span key={i} className="grid h-14 w-14 place-items-center rounded-2xl border-2 border-line bg-card text-2xl font-extrabold shadow-card animate-pop" style={{ animationDelay: `${i * 0.08}s` }}>
              {x}<span className="sr-only"> {t("brain.position", { n: i + 1 })}</span>
            </span>
          ))}
        </div>
        <div className="h-2 w-48 overflow-hidden rounded-full bg-line"><div className="h-full grad-sun transition-all duration-1000" style={{ width: `${(100 * left) / (p.seconds || 1)}%` }} /></div>
      </div>
    );
  }
  return (
    <div>
      <p className="mb-3 font-display text-xl font-bold leading-snug">{p.question}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {p.options.map((o, i) => {
          const isAns = result && i === result.answer;
          const isWrong = result && picked === i && !result.correct;
          return (
            <button key={i} disabled={picked !== null} onClick={() => onPick(i, Date.now() - t0.current)}
              className={cn("rounded-2xl border-2 px-4 py-3 text-left text-base font-extrabold transition",
                picked === null && "border-line bg-card hover:-translate-y-0.5 hover:border-primary hover:bg-soft",
                picked === i && !result && "border-primary bg-soft", isAns && "border-ok bg-ok/10 text-ok", isWrong && "border-bad bg-bad/10 text-bad animate-wiggle",
                picked !== null && !isAns && !isWrong && picked !== i && "opacity-60")}>
              <span className="mr-2 inline-grid h-7 w-7 place-items-center rounded-lg bg-soft text-xs">{String.fromCharCode(65 + i)}</span>{o}
            </button>
          );
        })}
      </div>
    </div>
  );
}
