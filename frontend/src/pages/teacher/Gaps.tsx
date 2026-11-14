import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SectionPicker, { useMySectionIds } from "@/components/common/SectionPicker";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { GapTopic } from "@/lib/types";

/** Teacher learning-gap report: which topics a section struggles with, and which students are below the weak threshold. */
export default function GapsPage() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const mine = useMySectionIds(user.teacher_id);
  const [sec, setSec] = useState<number | null>(null);
  const q = useQuery({ queryKey: ["gaps", sec], enabled: sec !== null, queryFn: () => get<{ topics: GapTopic[] }>(`/ai/gap-report?section_id=${sec}`) });
  return (
    <>
      <PageHeader title={t("nav.gaps")} subtitle={t("ai.gapsSubtitle")} actions={<SectionPicker value={sec} onChange={setSec} only={mine.ids} />} />
      {sec === null ? <EmptyState text={t("ai.pickSection")} /> : q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.data!.topics.length === 0 ? <EmptyState text={t("ai.noGaps")} /> : (
        <Card className="overflow-x-auto">
          <Table>
            <thead><tr><Th>{t("quiz.topic")}</Th><Th>{t("rc.subject")}</Th><Th>{t("ai.gapAvg")}</Th><Th>{t("ai.gapWeak")}</Th><Th>{t("ai.gapWho")}</Th></tr></thead>
            <tbody>
              {q.data!.topics.map((g) => (
                <Tr key={`${g.subject_id}-${g.topic}`}>
                  <Td><b>{g.topic}</b></Td><Td>{g.subject}</Td>
                  <Td><Badge tone={g.avg_mastery < 50 ? "bad" : g.avg_mastery < 80 ? "warn" : "ok"}>{g.avg_mastery}%</Badge></Td>
                  <Td>{g.weak_students} / {g.students_attempted}</Td>
                  <Td className="text-sm">{g.weak_list.map((s) => `${s.name} (${s.mastery}%)`).join(", ") || "—"}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </>
  );
}
