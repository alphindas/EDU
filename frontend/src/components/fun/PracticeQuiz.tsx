import { CheckCircle2, RotateCcw, XCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import Chitti from "./Chitti";
import { Button } from "@/components/ui/button";
import type { PracticeQ } from "@/lib/v2";
import { cn } from "@/lib/utils";

/** Ungraded practice set (topic explorer, photo doubt, mystery-style). Instant feedback + explanation per question. */
export default function PracticeQuiz({ questions, onDone }: { questions: PracticeQ[]; onDone?: (right: number) => void }) {
  const { t } = useTranslation();
  const [i, setI] = useState(0);
  const [pick, setPick] = useState<number | null>(null);
  const [right, setRight] = useState(0);
  const [done, setDone] = useState(false);
  if (!questions.length) return <p className="text-sm text-mute">{t("practice.none")}</p>;
  const q = questions[i];
  const next = () => {
    if (i + 1 >= questions.length) { setDone(true); onDone?.(right); return; }
    setI(i + 1); setPick(null);
  };
  if (done) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-3xl bg-soft/60 p-5 text-center animate-pop">
        <Chitti size={80} mood={right >= questions.length * 0.7 ? "cheer" : "happy"} />
        <div className="font-display text-2xl font-extrabold">{right} / {questions.length}</div>
        <p className="text-sm font-semibold text-mute">{right === questions.length ? t("practice.perfect") : right >= questions.length / 2 ? t("practice.good") : t("practice.tryAgain")}</p>
        <Button variant="outline" onClick={() => { setI(0); setPick(null); setRight(0); setDone(false); }}><RotateCcw size={16} /> {t("practice.restart")}</Button>
      </div>
    );
  }
  return (
    <div className="rounded-3xl border-2 border-line bg-card p-4">
      <div className="mb-2 flex items-center justify-between text-xs font-bold text-mute"><span>{t("practice.q", { n: i + 1, total: questions.length })}</span><span>✅ {right}</span></div>
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full grad-bg transition-all" style={{ width: `${(100 * i) / questions.length}%` }} /></div>
      <p className="mb-3 font-display text-lg font-bold leading-snug">{q.q}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {q.o.map((o, k) => {
          const isRight = pick !== null && k === q.a;
          const isWrong = pick === k && k !== q.a;
          return (
            <button key={k} disabled={pick !== null} onClick={() => { setPick(k); if (k === q.a) setRight((r) => r + 1); }}
              className={cn("flex items-center gap-2 rounded-2xl border-2 px-3 py-2.5 text-left text-sm font-bold transition",
                pick === null && "border-line hover:-translate-y-0.5 hover:border-primary hover:bg-soft",
                isRight && "border-ok bg-ok/10 text-ok", isWrong && "border-bad bg-bad/10 text-bad animate-wiggle", pick !== null && !isRight && !isWrong && "border-line opacity-60")}>
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-soft text-xs">{String.fromCharCode(65 + k)}</span>{o}
              {isRight && <CheckCircle2 className="ml-auto" size={18} />}{isWrong && <XCircle className="ml-auto" size={18} />}
            </button>
          );
        })}
      </div>
      {pick !== null && (
        <div className="mt-3 flex items-start gap-3 rounded-2xl bg-soft/70 p-3 animate-fade">
          <Chitti size={44} mood={pick === q.a ? "cheer" : "think"} float={false} />
          <div className="flex-1 text-sm"><b>{pick === q.a ? t("practice.correct") : t("practice.notQuite")}</b> {q.e}</div>
          <Button size="sm" onClick={next}>{i + 1 >= questions.length ? t("practice.finish") : t("practice.next")}</Button>
        </div>
      )}
    </div>
  );
}
