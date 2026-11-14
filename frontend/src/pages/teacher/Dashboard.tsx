import { GraduationCap, Layers, Star } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Loading, PageHeader, StatCard, greetingKey } from "@/components/common/bits";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { sectionLabel, useAssignments, useClasses, useSections, useStudentPage, useSubjects } from "@/lib/queries";

export default function TeacherDashboard() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const sections = useSections();
  const classes = useClasses();
  const subjects = useSubjects();
  const assignments = useAssignments();
  const students = useStudentPage({ limit: 1 });
  if (sections.isLoading || assignments.isLoading) return <Loading />;

  const mine = (assignments.data ?? []).filter((a) => a.teacher_id === user.teacher_id);
  const classTeacherOf = (sections.data ?? []).filter((s) => s.class_teacher_id === user.teacher_id);
  const sname = (id: number) => subjects.data?.find((s) => s.id === id)?.name ?? "—";

  return (
    <>
      <PageHeader title={`${t(greetingKey())}, ${user.full_name}`} subtitle={user.school?.name} />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label={t("dash.students")} value={students.data?.total ?? 0} icon={<GraduationCap />} />
        <StatCard label={t("dash.mySections")} value={new Set(mine.map((a) => a.section_id)).size} icon={<Layers />} tone="ok" />
        <StatCard label={t("dash.classTeacher")} value={classTeacherOf.map((s) => sectionLabel(sections.data, classes.data, s.id)).join(", ") || "—"} icon={<Star />} tone="warn" />
      </div>
      <Card className="mt-6">
        <CardHeader><CardTitle>{t("dash.teaches")}</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {mine.map((a) => (
            <Badge key={a.id} className="py-2 text-sm">{sname(a.subject_id)} · {sectionLabel(sections.data, classes.data, a.section_id)}</Badge>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
