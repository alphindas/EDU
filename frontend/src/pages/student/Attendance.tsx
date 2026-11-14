import { useTranslation } from "react-i18next";
import AttendanceHistory from "@/components/common/AttendanceHistory";
import { PageHeader } from "@/components/common/bits";
import { useAuth } from "@/lib/auth";

export default function StudentAttendance() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  return <><PageHeader title={t("nav.attendance")} subtitle={t("att.last30")} /><AttendanceHistory studentId={user.student_id!} /></>;
}
