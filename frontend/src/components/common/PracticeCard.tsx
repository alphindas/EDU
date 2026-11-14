import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toastError } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { post } from "@/lib/api";
import type { PracticeCheck, PracticeQuestion, QAnswer } from "@/lib/types";
import { cn } from "@/lib/utils";

const show = (q: PracticeQuestion, a: QAnswer, t: (k: string) => string) => {
  if (a === null || a === "") return "—";
  if (q.qtype === "mcq") return typeof a === "number" ? q.options[a] ?? String(a) : String(a);
  if (q.qtype === "true_false") return t(a ? "quiz.true" : "quiz.false");
  return Array.isArray(a) ? a.join(" / ") : String(a);
};

/** One ungraded practice question: answer it, press Check, see right/wrong + the key + explanation. Nothing is recorded. */
export default function PracticeCard({ q, onChecked }: { q: PracticeQuestion; onChecked?: (ok: boolean) => void }) {
  const { t } = useTranslation();
  const [ans, setAns] = useState<number | boolean | string | null>(null);
  const check = useMutation({
    mutationFn: () => post<PracticeCheck>(`/ai/practice/${q.question_id}/check`, { answer: ans }),
    onSuccess: (r) => onChecked?.(r.is_correct), onError: toastError,
  });
  const res = check.data;
  const opt = (selected: boolean) => cn("mb-2 flex cursor-pointer items-center gap-3 rounded-xl border p-3 text-sm", selected ? "border-primary bg-soft" : "border-line", res && "pointer-events-none");
  return (
    <div className="rounded-xl border border-line p-4" data-testid="practice-card">
      <p className="mb-3 font-semibold">{q.text}</p>
      {q.qtype === "mcq" && q.options.map((o, k) => (
        <label key={k} className={opt(ans === k)}><input type="radio" name={`pq-${q.question_id}`} checked={ans === k} onChange={() => setAns(k)} className="accent-[hsl(var(--ac))]" />{o}</label>
      ))}
      {q.qtype === "true_false" && [true, false].map((v) => (
        <label key={String(v)} className={opt(ans === v)}><input type="radio" name={`pq-${q.question_id}`} checked={ans === v} onChange={() => setAns(v)} className="accent-[hsl(var(--ac))]" />{t(v ? "quiz.true" : "quiz.false")}</label>
      ))}
      {q.qtype === "fill_blank" && <Input maxLength={200} disabled={!!res} value={typeof ans === "string" ? ans : ""} onChange={(e) => setAns(e.target.value)} aria-label={q.text} />}
      {!res ? (
        <Button size="sm" className="mt-3" disabled={ans === null || ans === "" || check.isPending} onClick={() => check.mutate()}>{t("ai.check")}</Button>
      ) : (
        <div className={cn("mt-3 rounded-xl border p-3 text-sm", res.is_correct ? "border-ok/50 bg-ok/10" : "border-bad/40 bg-bad/10")} role="status">
          <p className="flex items-center gap-2 font-semibold">
            {res.is_correct ? <CheckCircle2 size={16} className="text-ok" /> : <XCircle size={16} className="text-bad" />}
            {t(res.is_correct ? "ai.rightAnswer" : "ai.notQuite")}
          </p>
          {!res.is_correct && <p className="mt-1"><span className="text-mute">{t("quiz.correctAnswer")}:</span> <b>{show(q, res.correct_answer, t)}</b></p>}
          {res.explanation && <p className="mt-1">{res.explanation}</p>}
        </div>
      )}
    </div>
  );
}
