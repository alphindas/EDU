import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import IdCardView from "@/components/common/IdCardView";
import { useAuth } from "@/lib/auth";

export default function StudentIdCard() {
  const { t } = useTranslation();
  const user = useAuth((s) => s.user)!;
  return <><PageHeader title={t("nav.idCard")} /><IdCardView studentId={user.student_id!} /></>;
}
