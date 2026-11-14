import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import SectionTimetable from "@/components/common/SectionTimetable";
import { useAuth } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { Loading } from "@/components/common/bits";
import type { Student } from "@/lib/types";

export default function StudentTimetable() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const me = useQuery({ queryKey: ["student", user.student_id], queryFn: () => get<Student>(`/students/${user.student_id}`) });
  return <><PageHeader title={t("nav.timetable")} />{me.data ? <SectionTimetable sectionId={me.data.section_id} /> : <Loading />}</>;
}
