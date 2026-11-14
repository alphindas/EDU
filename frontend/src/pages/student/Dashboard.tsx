import { useQuery } from "@tanstack/react-query";
import { Rocket } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ErrorState, Loading, PageHeader, greetingKey } from "@/components/common/bits";
import StudentCard from "@/components/common/StudentCard";
import { Card, CardContent } from "@/components/ui/card";
import { get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Student } from "@/lib/types";

export default function StudentDashboard() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  const q = useQuery({ queryKey: ["student", user.student_id], queryFn: () => get<Student>(`/students/${user.student_id}`), enabled: !!user.student_id });
  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return (
    <>
      <PageHeader title={`${t(greetingKey())}, ${user.full_name.split(" ")[0]}`} subtitle={user.school?.name} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2"><StudentCard s={q.data} /></div>
        <Card className="grad-bg border-0 text-white">
          <CardContent className="flex h-full flex-col justify-center gap-3">
            <Rocket size={28} /><h3 className="text-xl font-extrabold">{t("dash.nextUp")}</h3><p className="text-white/85">{t("dash.nextUpBody")}</p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
