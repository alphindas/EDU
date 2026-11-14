import { useMutation } from "@tanstack/react-query";
import { Bot, Lightbulb, RefreshCw, SearchX, Sparkles } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import PracticeCard from "@/components/common/PracticeCard";
import { Spinner } from "@/components/common/bits";
import { toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { post } from "@/lib/api";
import type { RoboOut } from "@/lib/types";

/** Robo assistant shown under a WRONG quiz answer. Three buttons: Explain answer / Why was mine wrong / Next suggestion. */
export default function RoboHelp({ answerId }: { answerId: number }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [out, setOut] = useState<RoboOut | null>(null);
  const [seen, setSeen] = useState<number[]>([]);
  const [round, setRound] = useState(0); // remounts the practice card for each new question
  const ask = useMutation({
    mutationFn: (mode: RoboOut["mode"]) => post<RoboOut>("/ai/robo", { answer_id: answerId, mode, lang: i18n.language, exclude: mode === "next" ? seen : [] }),
    onSuccess: (r) => {
      setOut(r);
      setRound((n) => n + 1);
      if (r.practice) setSeen((s) => [...s, r.practice!.question_id]);
    },
    onError: toastError,
  });
  if (!open) {
    return (
      <Button type="button" size="sm" variant="soft" className="mt-2" onClick={() => setOpen(true)} aria-label={t("ai.robo")}>
        <Bot size={16} />{t("ai.robo")}
      </Button>
    );
  }
  const btns: { mode: RoboOut["mode"]; icon: typeof Bot; label: string }[] = [
    { mode: "explain", icon: Lightbulb, label: t("ai.explain") },
    { mode: "why_wrong", icon: SearchX, label: t("ai.whyWrong") },
    { mode: "next", icon: Sparkles, label: t("ai.next") },
  ];
  return (
    <div className="mt-3 rounded-xl border border-primary/30 bg-soft/60 p-3" data-testid="robo-panel">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Bot size={18} className="text-primary" />{t("ai.robo")}</div>
      <div className="flex flex-wrap gap-2">
        {btns.map((b) => (
          <Button key={b.mode} type="button" size="sm" variant={out?.mode === b.mode ? "default" : "outline"} disabled={ask.isPending} onClick={() => ask.mutate(b.mode)}>
            <b.icon size={14} />{b.label}
          </Button>
        ))}
        {ask.isPending && <Spinner className="h-5 w-5" />}
      </div>
      {out && (
        <div className="mt-3 space-y-3">
          <p className="whitespace-pre-line text-sm" data-testid="robo-text">{out.text}</p>
          {out.provider === "stub" && <Badge tone="mute">{t("ai.stubBadge")}</Badge>}
          {out.mode === "next" && out.practice && (
            <>
              <PracticeCard key={round} q={out.practice} />
              <Button type="button" size="sm" variant="ghost" disabled={ask.isPending} onClick={() => ask.mutate("next")}><RefreshCw size={14} />{t("ai.anotherOne")}</Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
