import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading, PageHeader } from "@/components/common/bits";
import AttendanceSheet from "@/components/common/AttendanceSheet";
import SectionPicker, { useMySectionIds } from "@/components/common/SectionPicker";
import { Input, Select } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { todayISO } from "@/lib/queries";

export const PERIODS = Array.from({ length: 9 }, (_, i) => i); // 0 = whole day, 1..8

export default function TeacherAttendance() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const mine = useMySectionIds(user.teacher_id);
  const [section, setSection] = useState<number | null>(null);
  const [date, setDate] = useState(todayISO());
  const [period, setPeriod] = useState(0);
  useEffect(() => { if (section === null && mine.ids.size) setSection([...mine.ids][0]); }, [mine.ids, section]);
  if (mine.loading) return <Loading />;
  return (
    <>
      <PageHeader title={t("nav.attendance")} actions={
        <>
          <SectionPicker value={section} onChange={setSection} only={mine.ids} />
          <Input type="date" className="w-auto" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)} aria-label={t("att.date")} />
          <Select className="w-auto" value={period} onChange={(e) => setPeriod(Number(e.target.value))} aria-label={t("att.period")}>
            {PERIODS.map((p) => <option key={p} value={p}>{p === 0 ? t("att.wholeDay") : `${t("att.period")} ${p}`}</option>)}
          </Select>
        </>
      } />
      {section === null ? <EmptyState /> : <AttendanceSheet key={`${section}-${date}-${period}`} sectionId={section} date={date} period={period} allowFace />}
    </>
  );
}
