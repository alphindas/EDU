import { BookOpen, GraduationCap, Layers, Rocket, Users, UsersRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loading, PageHeader, StatCard, greetingKey } from "@/components/common/bits";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { sectionLabel, useAllTeachers, useClasses, useParentPage, useSections, useStudentPage } from "@/lib/queries";

export default function AdminDashboard() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user);
  const students = useStudentPage({ limit: 200 });
  const teachers = useAllTeachers();
  const parents = useParentPage(1);
  const classes = useClasses();
  const sections = useSections();
  if (students.isLoading || teachers.isLoading) return <Loading />;

  const perSection = (sections.data ?? []).map((s) => ({
    name: sectionLabel(sections.data, classes.data, s.id),
    count: students.data?.items.filter((x) => x.section_id === s.id).length ?? 0,
  }));

  return (
    <>
      <PageHeader title={`${t(greetingKey())}, ${user?.full_name}`} subtitle={user?.school?.name} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label={t("dash.students")} value={students.data?.total ?? 0} icon={<GraduationCap />} />
        <StatCard label={t("dash.teachers")} value={teachers.data?.total ?? 0} icon={<Users />} tone="ok" />
        <StatCard label={t("dash.parents")} value={parents.data?.total ?? 0} icon={<UsersRound />} tone="accent2" />
        <StatCard label={t("dash.classes")} value={classes.data?.length ?? 0} icon={<BookOpen />} tone="warn" />
        <StatCard label={t("dash.sections")} value={sections.data?.length ?? 0} icon={<Layers />} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>{t("dash.perSection")}</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={perSection} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--line))" vertical={false} />
                <XAxis dataKey="name" stroke="hsl(var(--mute))" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} stroke="hsl(var(--mute))" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: "hsl(var(--soft))" }} contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--line))", borderRadius: 12 }} />
                <Bar dataKey="count" fill="hsl(var(--ac))" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card className="grad-bg border-0 text-white">
          <CardContent className="flex h-full flex-col justify-center gap-3">
            <Rocket size={28} />
            <h3 className="text-xl font-extrabold">{t("dash.nextUp")}</h3>
            <p className="text-white/85">{t("dash.nextUpBody")}</p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
