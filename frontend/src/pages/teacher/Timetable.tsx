import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loading, PageHeader } from "@/components/common/bits";
import SectionPicker, { useMySectionIds } from "@/components/common/SectionPicker";
import SectionTimetable from "@/components/common/SectionTimetable";
import TimetableGrid from "@/components/common/TimetableGrid";
import { cn } from "@/lib/utils";
import { get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { sectionLabel, subjectName, useClasses, usePeriods, useSections, useSubjects } from "@/lib/queries";
import type { TtEntry } from "@/lib/types";

export default function TeacherTimetable() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const [tab, setTab] = useState<"mine" | "section">("mine");
  const [section, setSection] = useState<number | null>(null);
  const mine = useMySectionIds(user.teacher_id);
  const periods = usePeriods();
  const subjects = useSubjects();
  const sections = useSections();
  const classes = useClasses();
  const entries = useQuery({ queryKey: ["timetable", "me"], queryFn: () => get<TtEntry[]>("/timetable/me") });
  useEffect(() => { if (section === null && mine.ids.size) setSection([...mine.ids][0]); }, [mine.ids, section]);
  if (periods.isLoading || mine.loading) return <Loading />;

  return (
    <>
      <PageHeader title={t("nav.timetable")} actions={tab === "section" ? <SectionPicker value={section} onChange={setSection} /> : undefined} />
      <div className="mb-4 flex gap-2" role="tablist">
        {(["mine", "section"] as const).map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cn("rounded-full border px-4 py-1.5 text-sm font-semibold transition", tab === k ? "grad-bg border-transparent text-white shadow-card" : "border-line bg-card text-mute hover:text-ink")}>
            {t(k === "mine" ? "tt.myTimetable" : "tt.sectionTimetable")}
          </button>
        ))}
      </div>
      {tab === "mine"
        ? <TimetableGrid periods={periods.data ?? []} entries={entries.data ?? []}
            cell={(e) => e && (<><div className="font-semibold">{subjectName(subjects.data, e.subject_id)}</div><div className="text-xs text-mute">{[sectionLabel(sections.data, classes.data, e.section_id), e.room].filter(Boolean).join(" · ")}</div></>)} />
        : section !== null && <SectionTimetable key={section} sectionId={section} staff canUpload={mine.ids.has(section)} />}
    </>
  );
}
