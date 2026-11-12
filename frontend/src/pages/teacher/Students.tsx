import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import StudentsTable from "@/components/common/StudentsTable";

export default function TeacherStudents() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader title={t("nav.myStudents")} />
      <StudentsTable />
    </>
  );
}
