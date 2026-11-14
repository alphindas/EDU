import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Layers, RefreshCw, Target } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import WithChild from "@/components/common/ChildPicker";
import PracticeCard from "@/components/common/PracticeCard";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { get, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FlashcardGen, LearningPlan, MasteryReport, MasteryTopic, PlanItem, PracticeQuestion } from "@/lib/types";
import { cn } from "@/lib/utils";

const tone = { weak: "bad", ok: "warn", strong: "ok" } as const;
const bar = { weak: "bg-bad", ok: "bg-warn", strong: "bg-ok" } as const;

function PracticeDialog({ topic, onClose }: { topic: MasteryTopic; onClose: () => void }) {
  const { t } = useTranslation();
  const [i, setI] = useState(0);
  const [done, setDone] = useState(false);
  const qs = useQuery({
    queryKey: ["practice", topic.subject_id, topic.topic], staleTime: Infinity, gcTime: 0,
    queryFn: () => get<PracticeQuestion[]>(`/ai/practice?topic=${encodeURIComponent(topic.topic)}&subject_id=${topic.subject_id}&limit=5`),
  });
  const list = qs.data ?? [];
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("ai.practiceTopic", { topic: topic.topic })} description={t("ai.practiceHint")} className="max-w-xl">
        {qs.isLoading ? <Loading /> : qs.isError ? <ErrorState error={qs.error} /> : list.length === 0 ? <EmptyState text={t("ai.noPractice")} /> : (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-mute">{t("ai.questionOf", { n: i + 1, total: list.length })}</p>
            <PracticeCard key={list[i].question_id} q={list[i]} onChecked={() => setDone(true)} />
            {done && (i + 1 < list.length
              ? <Button onClick={() => { setI(i + 1); setDone(false); }}>{t("ai.nextQuestion")}</Button>
              : <Button variant="soft" onClick={onClose}>{t("ai.finished")}</Button>)}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PlanGrid({ plan, canEdit, onTick }: { plan: LearningPlan; canEdit: boolean; onTick: (it: PlanItem, done: boolean) => void }) {
  const { t, i18n } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  const dayLabel = (d: number) => {
    const dt = new Date(`${plan.week_start}T12:00:00`);
    dt.setDate(dt.getDate() + d);
    return dt.toLocaleDateString(i18n.language, { weekday: "short", day: "numeric", month: "short" });
  };
  const label = (it: PlanItem) => {
    const base = t(`ai.plan.${it.kind}`, { topic: it.topic, subject: it.subject });
    return it.difficulty === "easy" && (it.kind === "revise" || it.kind === "practice") ? `${base} ${t("ai.plan.easyStart")}` : base;
  };
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="plan-grid">
      {Array.from({ length: 7 }, (_, d) => d).map((d) => {
        const items = plan.items.filter((x) => x.day === d);
        return (
          <div key={d} className="rounded-xl border border-line p-3">
            <div className="mb-2 text-xs font-bold uppercase tracking-wide text-mute">{dayLabel(d)}</div>
            {items.length === 0 ? <p className="text-xs text-mute">—</p> : items.map((it) => (
              <label key={it.id} className={cn("mb-2 flex items-start gap-2 rounded-lg bg-soft/60 p-2 text-sm", it.kind === "rest" && "opacity-70")}>
                {it.kind !== "rest" && <input type="checkbox" checked={it.done} disabled={!canEdit} onChange={(e) => onTick(it, e.target.checked)} className="mt-1 accent-[hsl(var(--ac))]" aria-label={label(it)} />}
                <span className={cn("min-w-0 flex-1", it.done && "text-mute line-through")}>
                  {label(it)}
                  {it.minutes > 0 && <span className="ml-1 text-xs text-mute">· {t("ai.minutes", { n: it.minutes })}</span>}
                  {it.kind === "flashcards" && role === "student" && <Link to="/student/flashcards" className="ml-2 text-xs font-semibold text-primary underline">{t("nav.flashcards")}</Link>}
                </span>
              </label>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function LearningView({ childId }: { childId?: number }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const role = useAuth((s) => s.user!.role);
  const isStudent = role === "student";
  const qs = childId ? `?student_id=${childId}` : "";
  const mastery = useQuery({ queryKey: ["mastery", childId], queryFn: () => get<MasteryReport>(`/ai/mastery${qs}`) });
  const plan = useQuery({ queryKey: ["plan", childId], queryFn: () => get<LearningPlan>(`/ai/plan${qs}`) });
  const [practice, setPractice] = useState<MasteryTopic | null>(null);
  const setPlan = (p: LearningPlan) => qc.setQueryData(["plan", childId], p);
  const regen = useMutation({ mutationFn: () => post<LearningPlan>("/ai/plan/regenerate"), onSuccess: (p) => { setPlan(p); toast(t("ai.planUpdated")); }, onError: toastError });
  const tick = useMutation({
    mutationFn: (v: { it: PlanItem; done: boolean }) => patch<LearningPlan>(`/ai/plan/${plan.data!.id}/items/${v.it.id}`, { done: v.done }),
    onMutate: (v) => qc.setQueryData<LearningPlan>(["plan", childId], (p) => p && { ...p, items: p.items.map((i) => (i.id === v.it.id ? { ...i, done: v.done } : i)) }), // optimistic
    onSuccess: setPlan,
    onError: (e) => { toastError(e); qc.invalidateQueries({ queryKey: ["plan", childId] }); },
  });
  const cards = useMutation({
    mutationFn: (topic: string) => post<FlashcardGen>("/ai/flashcards/generate", { source: "mistakes", topic }),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["cards"] }); qc.invalidateQueries({ queryKey: ["plan"] }); toast(r.created ? t("ai.cardsMade", { n: r.created }) : t("ai.noNewCards")); }, onError: toastError,
  });

  const weak = (mastery.data?.topics ?? []).filter((x) => x.level === "weak");
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Target size={18} className="text-primary" />{t("ai.topics")}</CardTitle>{mastery.data && <Badge tone={weak.length ? "bad" : "ok"}>{t("ai.weakCount", { n: weak.length })}</Badge>}</CardHeader>
        <div className="p-5">
          <p className="mb-3 text-xs text-mute">{t("ai.topicsHint")}</p>
          {mastery.isLoading ? <Loading /> : mastery.isError ? <ErrorState error={mastery.error} onRetry={() => mastery.refetch()} /> : mastery.data!.topics.length === 0 ? <EmptyState text={t("ai.noTopics")} /> : (
            <ul className="space-y-3" data-testid="mastery-list">
              {mastery.data!.topics.map((m) => (
                <li key={`${m.subject_id}-${m.topic}`} className="flex flex-wrap items-center gap-3">
                  <div className="min-w-[10rem] flex-1">
                    <div className="flex items-center justify-between text-sm"><b>{m.topic}</b><span className="text-xs text-mute">{m.subject}</span></div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={m.mastery} aria-valuemin={0} aria-valuemax={100} aria-label={m.topic}>
                      <div className={cn("h-full rounded-full", bar[m.level])} style={{ width: `${Math.max(m.mastery, 2)}%` }} />
                    </div>
                  </div>
                  <Badge tone={tone[m.level]}>{m.mastery}% · {m.correct}/{m.total}</Badge>
                  <Badge tone={tone[m.level]}>{t(`ai.level.${m.level}`)}</Badge>
                  {isStudent && m.level !== "strong" && (
                    <>
                      <Button size="sm" variant="soft" onClick={() => setPractice(m)}>{t("ai.practice")}</Button>
                      <Button size="sm" variant="outline" disabled={cards.isPending} onClick={() => cards.mutate(m.topic)}><Layers size={14} />{t("ai.makeCards")}</Button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><CalendarClock size={18} className="text-primary" />{t("ai.weeklyPlan")}</CardTitle>
          {isStudent && <Button size="sm" variant={plan.data?.stale ? "default" : "outline"} disabled={regen.isPending} onClick={() => regen.mutate()}><RefreshCw size={14} />{t("ai.refreshPlan")}</Button>}
        </CardHeader>
        <div className="p-5">
          {plan.data?.stale && <p className="mb-3 rounded-lg bg-warn/15 p-2 text-sm text-warn" role="status">{t("ai.planStale")}</p>}
          <p className="mb-3 text-xs text-mute">{t("ai.planHint")}</p>
          {plan.isLoading ? <Loading /> : plan.isError ? <ErrorState error={plan.error} onRetry={() => plan.refetch()} /> : <PlanGrid plan={plan.data!} canEdit={isStudent} onTick={(it, done) => tick.mutate({ it, done })} />}
        </div>
      </Card>
      {practice && <PracticeDialog topic={practice} onClose={() => setPractice(null)} />}
    </div>
  );
}

export default function LearningPage() {
  const { t } = useTranslation();
  const role = useAuth((s) => s.user!.role);
  return (
    <>
      <PageHeader title={t("nav.learning")} subtitle={t("ai.learningSubtitle")} />
      {role === "parent" ? <WithChild>{(c) => <LearningView key={c.id} childId={c.id} />}</WithChild> : <LearningView />}
    </>
  );
}
