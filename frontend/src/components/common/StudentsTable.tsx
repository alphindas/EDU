import { useQueryClient, useMutation } from "@tanstack/react-query";
import { IdCard as IdIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import IdCardView from "@/components/common/IdCardView";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { del } from "@/lib/api";
import { sectionLabel, useClasses, useSections, useStudentPage } from "@/lib/queries";

const LIMIT = 15;

export default function StudentsTable({ canDelete = false }: { canDelete?: boolean }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [classId, setClassId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [idFor, setIdFor] = useState<number | null>(null);
  const classes = useClasses();
  const sections = useSections();
  const page = useStudentPage({ class_id: classId, section_id: sectionId, q, limit: LIMIT, offset });
  const remove = useMutation({
    mutationFn: (id: number) => del(`/students/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast(t("common.saved")); },
    onError: toastError,
  });
  const secOpts = (sections.data ?? []).filter((s) => !classId || s.class_id === Number(classId));
  const reset = () => setOffset(0);

  return (
    <Card>
      <div className="flex flex-wrap gap-2 p-4">
        <Input className="max-w-xs" placeholder={t("common.search")} value={q} onChange={(e) => { setQ(e.target.value); reset(); }} aria-label={t("common.search")} />
        <Select className="w-auto" value={classId} onChange={(e) => { setClassId(e.target.value); setSectionId(""); reset(); }} aria-label={t("students.class")}>
          <option value="">{t("students.filterClass")}</option>
          {classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select className="w-auto" value={sectionId} onChange={(e) => { setSectionId(e.target.value); reset(); }} aria-label={t("students.section")}>
          <option value="">{t("students.filterSection")}</option>
          {secOpts.map((s) => <option key={s.id} value={s.id}>{sectionLabel(sections.data, classes.data, s.id)}</option>)}
        </Select>
      </div>
      {page.isLoading ? <Loading /> : page.isError ? <ErrorState error={page.error} onRetry={() => page.refetch()} /> : !page.data?.items.length ? <EmptyState /> : (
        <>
          <Table>
            <thead><tr><Th>{t("students.admissionNo")}</Th><Th>{t("students.fullName")}</Th><Th>{t("students.class")}</Th><Th>{t("students.roll")}</Th><Th>{t("students.parentMobile")}</Th><Th />{canDelete && <Th />}</tr></thead>
            <tbody>
              {page.data.items.map((s) => (
                <Tr key={s.id}>
                  <Td className="font-mono text-xs">{s.admission_no}</Td>
                  <Td className="font-semibold">{s.full_name}</Td>
                  <Td><Badge>{sectionLabel(sections.data, classes.data, s.section_id)}</Badge></Td>
                  <Td>{s.roll_no ?? "—"}</Td>
                  <Td className="text-mute">{s.parent_mobile}</Td>
                  <Td><Button variant="ghost" size="icon" aria-label={t("nav.idCard")} title={t("nav.idCard")} onClick={() => setIdFor(s.id)}><IdIcon size={16} /></Button></Td>
                  {canDelete && (
                    <Td className="text-right">
                      <Button variant="ghost" size="icon" aria-label={t("common.delete")} onClick={() => confirm(t("common.confirmDelete")) && remove.mutate(s.id)}>
                        <Trash2 size={16} className="text-bad" />
                      </Button>
                    </Td>
                  )}
                </Tr>
              ))}
            </tbody>
          </Table>
          <div className="flex items-center justify-between p-4 text-sm text-mute">
            <span>{t("common.total")}: {page.data.total}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>{t("common.prev")}</Button>
              <Button variant="outline" size="sm" disabled={offset + LIMIT >= page.data.total} onClick={() => setOffset(offset + LIMIT)}>{t("common.next")}</Button>
            </div>
          </div>
        </>
      )}
      <Dialog open={idFor !== null} onOpenChange={(o) => !o && setIdFor(null)}>
        <DialogContent title={t("nav.idCard")}>{idFor !== null && <IdCardView studentId={idFor} />}</DialogContent>
      </Dialog>
    </Card>
  );
}
