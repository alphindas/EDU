import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, PageHeader } from "@/components/common/bits";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { sectionLabel, useClasses, useParentPage, useSections } from "@/lib/queries";

export default function Parents() {
  const { t } = useTranslation();
  const q = useParentPage();
  const classes = useClasses();
  const sections = useSections();
  return (
    <>
      <PageHeader title={t("parents.title")} subtitle={`${t("common.total")}: ${q.data?.total ?? 0}`} />
      <Card>
        {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.items.length ? <EmptyState /> : (
          <Table>
            <thead><tr><Th>{t("common.name")}</Th><Th>{t("parents.mobile")}</Th><Th>{t("parents.relation")}</Th><Th>{t("parents.children")}</Th></tr></thead>
            <tbody>
              {q.data.items.map((p) => (
                <Tr key={p.id}>
                  <Td className="font-semibold">{p.full_name}</Td>
                  <Td className="font-mono text-xs">{p.mobile}</Td>
                  <Td className="text-mute">{p.relation || "—"}</Td>
                  <Td className="flex flex-wrap gap-1.5">
                    {p.children.map((c) => <Badge key={c.id}>{c.full_name} · {sectionLabel(sections.data, classes.data, c.section_id)}</Badge>)}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
