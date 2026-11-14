import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, StatCard } from "@/components/common/bits";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { get } from "@/lib/api";
import type { HistoryOut } from "@/lib/types";
import { CalendarCheck, CalendarX, Clock, Percent } from "lucide-react";

const tone = { present: "ok", absent: "bad", late: "warn" } as const;

export default function AttendanceHistory({ studentId }: { studentId: number }) {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["att-history", studentId], queryFn: () => get<HistoryOut>(`/attendance/students/${studentId}`) });
  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const h = q.data;
  return (
    <>
      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("att.rate")} value={h.percentage == null ? "—" : `${h.percentage}%`} icon={<Percent />} />
        <StatCard label={t("att.present")} value={h.present} icon={<CalendarCheck />} tone="ok" />
        <StatCard label={t("att.absent")} value={h.absent} icon={<CalendarX />} tone="warn" />
        <StatCard label={t("att.late")} value={h.late} icon={<Clock />} tone="accent2" />
      </div>
      <Card>
        {!h.items.length ? <EmptyState text={t("att.noRecords")} /> : (
          <Table>
            <thead><tr><Th>{t("att.date")}</Th><Th>{t("att.period")}</Th><Th>{t("att.status")}</Th><Th>{t("att.note")}</Th></tr></thead>
            <tbody>
              {h.items.map((i, k) => (
                <Tr key={k}>
                  <Td>{i.date}</Td><Td>{i.period === 0 ? t("att.wholeDay") : i.period}</Td>
                  <Td><Badge tone={tone[i.status]}>{t(`att.${i.status}`)}</Badge></Td><Td className="text-mute">{i.note}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
