import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import AttendanceSheet from "@/components/common/AttendanceSheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { get } from "@/lib/api";
import { sectionLabel, todayISO, useClasses, useSections } from "@/lib/queries";
import type { SummaryRow } from "@/lib/types";
import { PERIODS } from "@/pages/teacher/Attendance";

/** Admin: school-wide present/absent counts for a date; open a section to correct its register. */
export default function AdminAttendance() {
  const { t } = useTranslation();
  const [date, setDate] = useState(todayISO());
  const [open, setOpen] = useState<number | null>(null);
  const [period, setPeriod] = useState(0);
  const classes = useClasses();
  const sections = useSections();
  const q = useQuery({ queryKey: ["att-summary", date], queryFn: () => get<SummaryRow[]>(`/attendance/summary?date=${date}`) });
  const tot = (q.data ?? []).reduce((a, r) => ({ total: a.total + r.total, present: a.present + r.present, absent: a.absent + r.absent, late: a.late + r.late }), { total: 0, present: 0, absent: 0, late: 0 });

  return (
    <>
      <PageHeader title={t("nav.attendance")} subtitle={t("att.adminHint")} actions={<Input type="date" className="w-auto" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} aria-label={t("att.date")} />} />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.length ? <EmptyState /> : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="ok">{t("att.present")}: {tot.present}</Badge><Badge tone="bad">{t("att.absent")}: {tot.absent}</Badge>
            <Badge tone="warn">{t("att.late")}: {tot.late}</Badge><Badge tone="mute">{t("common.total")}: {tot.total}</Badge>
          </div>
          <Card>
            <Table>
              <thead><tr><Th>{t("students.section")}</Th><Th>{t("common.total")}</Th><Th>{t("att.present")}</Th><Th>{t("att.absent")}</Th><Th>{t("att.late")}</Th><Th>{t("att.status")}</Th><Th /></tr></thead>
              <tbody>
                {q.data.map((r) => (
                  <Tr key={r.section_id}>
                    <Td className="font-semibold">{sectionLabel(sections.data, classes.data, r.section_id)}</Td>
                    <Td>{r.total}</Td><Td>{r.present}</Td><Td>{r.absent}</Td><Td>{r.late}</Td>
                    <Td><Badge tone={r.marked ? "ok" : "mute"}>{r.marked ? t("att.marked") : t("att.notMarked")}</Badge></Td>
                    <Td className="text-right"><Button variant="soft" size="sm" onClick={() => { setPeriod(0); setOpen(r.section_id); }}>{t("att.correct")}</Button></Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </>
      )}
      <Dialog open={open !== null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent title={`${t("att.correct")} · ${open ? sectionLabel(sections.data, classes.data, open) : ""} · ${date}`} className="max-w-3xl">
          <Select className="mb-4 w-auto" value={period} onChange={(e) => setPeriod(Number(e.target.value))} aria-label={t("att.period")}>
            {PERIODS.map((p) => <option key={p} value={p}>{p === 0 ? t("att.wholeDay") : `${t("att.period")} ${p}`}</option>)}
          </Select>
          {open !== null && <AttendanceSheet key={`${open}-${period}`} sectionId={open} date={date} period={period} allowFace={false} />}
        </DialogContent>
      </Dialog>
    </>
  );
}
