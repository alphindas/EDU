import { useTranslation } from "react-i18next";
import { Select } from "@/components/ui/input";
import { sectionLabel, useAssignments, useClasses, useSections } from "@/lib/queries";

export default function SectionPicker({ value, onChange, only }: { value: number | null; onChange: (id: number) => void; only?: Set<number> }) {
  const { t } = useTranslation();
  const classes = useClasses();
  const sections = useSections();
  const list = (sections.data ?? []).filter((s) => !only || only.has(s.id));
  return (
    <Select className="w-auto" value={value ?? ""} onChange={(e) => onChange(Number(e.target.value))} aria-label={t("students.section")}>
      <option value="" disabled>{t("students.section")}</option>
      {list.map((s) => <option key={s.id} value={s.id}>{sectionLabel(sections.data, classes.data, s.id)}</option>)}
    </Select>
  );
}

/** Sections a teacher may work in: class teacher of, or assigned a subject in. */
export function useMySectionIds(teacherId: number | null) {
  const sections = useSections();
  const assigns = useAssignments();
  const ids = new Set<number>([
    ...(assigns.data ?? []).filter((a) => a.teacher_id === teacherId).map((a) => a.section_id),
    ...(sections.data ?? []).filter((s) => s.class_teacher_id === teacherId).map((s) => s.id),
  ]);
  return { ids, loading: sections.isLoading || assigns.isLoading };
}
