import { useTranslation } from "react-i18next";
import AttendanceHistory from "@/components/common/AttendanceHistory";
import { PageHeader } from "@/components/common/bits";
import WithChild from "@/components/common/ChildPicker";

export default function ParentAttendance() {
  const { t } = useTranslation();
  return <><PageHeader title={t("nav.attendance")} subtitle={t("att.last30")} /><WithChild>{(c) => <AttendanceHistory studentId={c.id} />}</WithChild></>;
}
