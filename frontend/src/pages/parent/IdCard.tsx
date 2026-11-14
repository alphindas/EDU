import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import WithChild from "@/components/common/ChildPicker";
import IdCardView from "@/components/common/IdCardView";

export default function ParentIdCard() {
  const { t } = useTranslation();
  return <><PageHeader title={t("nav.idCard")} /><WithChild>{(c) => <IdCardView key={c.id} studentId={c.id} />}</WithChild></>;
}
