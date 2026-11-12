import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { sectionLabel, useClasses, useSections } from "@/lib/queries";
import type { Student } from "@/lib/types";

export default function StudentCard({ s }: { s: Student }) {
  const { t } = useTranslation();
  const classes = useClasses();
  const sections = useSections();
  const initials = s.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("");
  const row = (k: string, v: string | number | null) => (
    <div><div className="text-xs font-semibold uppercase tracking-wide text-mute">{k}</div><div className="font-semibold">{v ?? "—"}</div></div>
  );
  return (
    <Card className="overflow-hidden">
      <div className="grad-bg h-20" />
      <div className="-mt-10 px-6 pb-6">
        <div className="grid h-20 w-20 place-items-center rounded-2xl border-4 border-card bg-soft text-2xl font-extrabold text-primary shadow-card">{initials}</div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-extrabold">{s.full_name}</h2>
          <Badge>{t("dash.class")} {sectionLabel(sections.data, classes.data, s.section_id)}</Badge>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {row(t("dash.idCard"), s.admission_no)}
          {row(t("dash.roll"), s.roll_no)}
          {row(t("dash.dob"), s.dob)}
          {row(t("students.parentMobile"), s.parent_mobile)}
        </div>
      </div>
    </Card>
  );
}
