import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader, StatCard } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { del, get, post } from "@/lib/api";
import type { AiDocument, Flashcard, FlashcardGen, FlashcardStats } from "@/lib/types";
import { cn } from "@/lib/utils";

const RATINGS = [{ q: 1, key: "again", cls: "bg-bad text-white" }, { q: 3, key: "hard", cls: "bg-warn text-white" }, { q: 4, key: "good", cls: "bg-ok text-white" }, { q: 5, key: "easy", cls: "bg-primary text-white" }] as const;

function Review() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const due = useQuery({ queryKey: ["cards", "due"], queryFn: () => get<Flashcard[]>("/ai/flashcards?due=true") });
  const [shown, setShown] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const rate = useMutation({
    mutationFn: (v: { id: number; quality: number }) => post<Flashcard>(`/ai/flashcards/${v.id}/review`, { quality: v.quality }),
    onSuccess: () => { setShown(false); setReviewed((n) => n + 1); qc.invalidateQueries({ queryKey: ["cards"] }); qc.invalidateQueries({ queryKey: ["card-stats"] }); qc.invalidateQueries({ queryKey: ["plan"] }); }, onError: toastError,
  });
  if (due.isLoading) return <Loading />;
  if (due.isError) return <ErrorState error={due.error} onRetry={() => due.refetch()} />;
  const card = due.data![0];
  if (!card) return <EmptyState text={reviewed ? t("fc.allDone", { n: reviewed }) : t("fc.noneDue")} />;
  return (
    <div className="mx-auto max-w-xl space-y-4" data-testid="fc-review">
      <p className="text-center text-xs font-semibold text-mute">{t("fc.remaining", { n: due.data!.length })}</p>
      <button type="button" onClick={() => setShown(true)} className="block min-h-[12rem] w-full rounded-2xl border border-line bg-card p-6 text-center shadow-card">
        {card.topic && <Badge className="mb-3">{card.topic}</Badge>}
        <p className="whitespace-pre-line text-lg font-bold" data-testid="fc-front">{card.front}</p>
        {shown ? <p className="mt-4 whitespace-pre-line border-t border-line pt-4 text-base" data-testid="fc-back">{card.back}</p> : <p className="mt-6 text-sm text-mute">{t("fc.tapToShow")}</p>}
      </button>
      {!shown ? <Button className="w-full" onClick={() => setShown(true)}>{t("fc.show")}</Button> : (
        <div className="grid grid-cols-4 gap-2" role="group" aria-label={t("fc.howWell")}>
          {RATINGS.map((r) => <button key={r.key} disabled={rate.isPending} onClick={() => rate.mutate({ id: card.id, quality: r.q })} className={cn("rounded-xl py-2.5 text-sm font-semibold transition hover:brightness-110 disabled:opacity-50", r.cls)}>{t(`fc.${r.key}`)}</button>)}
        </div>
      )}
    </div>
  );
}

function Library() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const cards = useQuery({ queryKey: ["cards", "all"], queryFn: () => get<Flashcard[]>("/ai/flashcards") });
  const docs = useQuery({ queryKey: ["ai-docs"], queryFn: () => get<AiDocument[]>("/ai/documents") });
  const [f, setF] = useState({ front: "", back: "", topic: "" });
  const [docId, setDocId] = useState("");
  const refresh = () => { qc.invalidateQueries({ queryKey: ["cards"] }); qc.invalidateQueries({ queryKey: ["card-stats"] }); };
  const add = useMutation({ mutationFn: () => post("/ai/flashcards", f), onSuccess: () => { refresh(); setF({ front: "", back: "", topic: "" }); toast(t("common.saved")); }, onError: toastError });
  const rm = useMutation({ mutationFn: (id: number) => del(`/ai/flashcards/${id}`), onSuccess: refresh, onError: toastError });
  const gen = useMutation({
    mutationFn: (body: object) => post<FlashcardGen>("/ai/flashcards/generate", body),
    onSuccess: (r) => { refresh(); toast(r.created ? t("ai.cardsMade", { n: r.created }) : t("ai.noNewCards")); }, onError: toastError,
  });
  const readable = (docs.data ?? []).filter((d) => d.readable);
  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="space-y-4">
        <Card className="space-y-3 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={16} className="text-primary" />{t("fc.generate")}</h3>
          <Button className="w-full" variant="soft" disabled={gen.isPending} onClick={() => gen.mutate({ source: "mistakes" })}>{t("fc.fromMistakes")}</Button>
          <div className="space-y-2">
            <Select value={docId} onChange={(e) => setDocId(e.target.value)} aria-label={t("fc.pickNotes")}>
              <option value="">{t("fc.pickNotes")}</option>
              {readable.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
            <Button className="w-full" variant="soft" disabled={!docId || gen.isPending} onClick={() => gen.mutate({ source: "notes", document_id: Number(docId) })}>{t("fc.fromNotes")}</Button>
            <p className="text-xs text-mute">{t("fc.notesHint")}</p>
          </div>
        </Card>
        <Card className="p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Plus size={16} className="text-primary" />{t("fc.addOwn")}</h3>
          <form className="space-y-3" onSubmit={(e: FormEvent) => { e.preventDefault(); add.mutate(); }}>
            <Field label={t("fc.front")}><Input required maxLength={1000} value={f.front} onChange={(e) => setF({ ...f, front: e.target.value })} /></Field>
            <Field label={t("fc.back")}><Textarea required rows={2} maxLength={2000} value={f.back} onChange={(e) => setF({ ...f, back: e.target.value })} /></Field>
            <Field label={t("quiz.topic")}><Input maxLength={100} value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })} /></Field>
            <Button type="submit" className="w-full" disabled={add.isPending}>{t("fc.add")}</Button>
          </form>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>{t("fc.library")}</CardTitle></CardHeader>
        <div className="p-5">
          {cards.isLoading ? <Loading /> : cards.isError ? <ErrorState error={cards.error} /> : cards.data!.length === 0 ? <EmptyState text={t("fc.empty")} /> : (
            <ul className="divide-y divide-line" data-testid="fc-library">
              {cards.data!.map((c) => (
                <li key={c.id} className="flex items-start gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="whitespace-pre-line text-sm font-semibold">{c.front}</p>
                    <p className="mt-0.5 whitespace-pre-line text-sm text-mute">{c.back}</p>
                    <p className="mt-1 flex flex-wrap gap-1.5 text-xs text-mute">
                      <Badge tone="mute">{t(`fc.src.${c.source}`)}</Badge>{c.topic && <Badge>{c.topic}</Badge>}
                      <span>{t("fc.dueOn", { date: c.due_date })} · {t("fc.interval", { n: c.interval_days })}</span>
                    </p>
                  </div>
                  <Button size="icon" variant="ghost" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && rm.mutate(c.id)}><Trash2 size={16} className="text-bad" /></Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}

export default function FlashcardsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"review" | "library">("review");
  const stats = useQuery({ queryKey: ["card-stats"], queryFn: () => get<FlashcardStats>("/ai/flashcards/stats") });
  return (
    <>
      <PageHeader title={t("nav.flashcards")} subtitle={t("fc.subtitle")} />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label={t("fc.due")} value={stats.data?.due ?? "–"} icon={<RotateCcw size={20} />} tone="warn" />
        <StatCard label={t("fc.new")} value={stats.data?.new ?? "–"} icon={<Sparkles size={20} />} />
        <StatCard label={t("fc.learned")} value={stats.data?.learned ?? "–"} icon={<Layers size={20} />} tone="ok" />
        <StatCard label={t("fc.total")} value={stats.data?.total ?? "–"} icon={<Layers size={20} />} tone="accent2" />
      </div>
      <div className="mb-4 flex gap-2" role="tablist">
        {(["review", "library"] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cn("rounded-full border px-4 py-1.5 text-sm font-semibold", tab === k ? "grad-bg border-transparent text-white shadow-card" : "border-line bg-card text-mute hover:text-ink")}>{t(`fc.tab.${k}`)}</button>
        ))}
      </div>
      {tab === "review" ? <Review /> : <Library />}
    </>
  );
}
