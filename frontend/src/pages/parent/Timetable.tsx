import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import WithChild from "@/components/common/ChildPicker";
import SectionTimetable from "@/components/common/SectionTimetable";

export default function ParentTimetable() {
  const { t } = useTranslation();
  return <><PageHeader title={t("nav.timetable")} /><WithChild>{(c) => <SectionTimetable key={c.section_id} sectionId={c.section_id} />}</WithChild></>;
}
