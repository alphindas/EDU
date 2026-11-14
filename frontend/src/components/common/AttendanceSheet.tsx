import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCheck, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorState, Loading } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { get, post, api } from "@/lib/api";
import type { AttStatus, FaceStatus, FaceStop, Sheet } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUSES: AttStatus[] = ["present", "absent", "late"];
const tone = { present: "ok", absent: "bad", late: "warn" } as const;
interface Cell { status: AttStatus | null; note: string; confidence: number | null }

/** Marking sheet for one <section, date, period>. Teachers mark; admin reuses it to correct. Face mode (teachers only) proposes a register. */
export default function AttendanceSheet({ sectionId, date, period, allowFace }: { sectionId: number; date: string; period: number; allowFace: boolean }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const key = ["sheet", sectionId, date, period];
  const sheet = useQuery({ queryKey: key, queryFn: () => get<Sheet>(`/attendance/sheet?section_id=${sectionId}&date=${date}&period=${period}`) });
  const [cells, setCells] = useState<Record<number, Cell>>({});
  const [source, setSource] = useState<"manual" | "face">("manual");
  const [faceOn, setFaceOn] = useState(false);

  useEffect(() => {
    if (!sheet.data) return;
    setCells(Object.fromEntries(sheet.data.rows.map((r) => [r.student_id, { status: r.status, note: r.note, confidence: null }])));
    setSource("manual");
  }, [sheet.data]);

  const face = useQuery({
    queryKey: ["face", sectionId], queryFn: () => get<FaceStatus>(`/attendance/face/status?section_id=${sectionId}`),
    enabled: faceOn, refetchInterval: 2000, retry: false,
  });
  const start = useMutation({
    mutationFn: () => post<FaceStatus>("/attendance/face/start", { section_id: sectionId, period: period || 1 }),
    onSuccess: () => { setFaceOn(true); qc.invalidateQueries({ queryKey: ["face", sectionId] }); }, onError: toastError,
  });
  const stop = useMutation({
    mutationFn: () => post<FaceStop>(`/attendance/face/stop?section_id=${sectionId}`),
    onSuccess: (r) => {
      setFaceOn(false);
      setCells((c) => ({ ...c, ...Object.fromEntries(r.proposal.map((p) => [p.student_id, { status: p.status, note: "", confidence: p.confidence ?? null }])) }));
      setSource("face");
      toast(t("att.faceReview"));
    }, onError: toastError,
  });
  const save = useMutation({
    mutationFn: () => api("/attendance/sessions", {
      method: "PUT",
      json: {
        section_id: sectionId, date, period, source,
        records: Object.entries(cells).filter(([, c]) => c.status).map(([id, c]) => ({ student_id: Number(id), status: c.status, note: c.note, confidence: c.confidence })),
      },
    }),
    onSuccess: () => { toast(t("att.saved")); qc.invalidateQueries({ queryKey: ["sheet"] }); qc.invalidateQueries({ queryKey: ["att-summary"] }); }, onError: toastError,
  });

  if (sheet.isLoading) return <Loading />;
  if (sheet.isError || !sheet.data) return <ErrorState error={sheet.error} onRetry={() => sheet.refetch()} />;
  const rows = sheet.data.rows;
  const setS = (id: number, status: AttStatus) => setCells((c) => ({ ...c, [id]: { ...c[id], status, confidence: null } }));
  const counts = STATUSES.map((s) => [s, rows.filter((r) => cells[r.student_id]?.status === s).length] as const);
  const unmarked = rows.filter((r) => !cells[r.student_id]?.status).length;

  return (
    <div className="space-y-4">
      {allowFace && (
        <Card className="flex flex-wrap items-center gap-3 p-4">
          <Camera size={20} className="text-primary" />
          <div className="min-w-0 flex-1 text-sm">
            <div className="font-semibold">{t("att.faceMode")}</div>
            <div className="text-mute">
              {faceOn ? t("att.faceRunning", { n: face.data?.detected.length ?? 0, total: face.data?.total ?? rows.length }) : t("att.faceHelp")}
              {face.data?.demo && faceOn && <Badge tone="warn" className="ml-2">demo</Badge>}
            </div>
          </div>
          {faceOn
            ? <Button variant="danger" onClick={() => stop.mutate()} disabled={stop.isPending}><Square size={16} />{t("att.stopFace")}</Button>
            : <Button variant="outline" onClick={() => start.mutate()} disabled={start.isPending}><Camera size={16} />{t("att.startFace")}</Button>}
        </Card>
      )}
      {source === "face" && <p className="rounded-xl bg-warn/10 p-3 text-sm text-warn" role="status">{t("att.faceReview")}</p>}

      <Card>
        <div className="flex flex-wrap items-center gap-3 p-4">
          {counts.map(([s, n]) => <Badge key={s} tone={tone[s]}>{t(`att.${s}`)}: {n}</Badge>)}
          <Badge tone="mute">{t("att.notMarked")}: {unmarked}</Badge>
          <div className="ml-auto flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setCells((c) => Object.fromEntries(rows.map((r) => [r.student_id, { ...(c[r.student_id] ?? { note: "" }), status: "present", confidence: null } as Cell])))}>
              <CheckCheck size={16} />{t("att.markAll")}
            </Button>
            <Button onClick={() => save.mutate()} disabled={save.isPending || unmarked === rows.length}>{t("common.save")}</Button>
          </div>
        </div>
        <Table>
          <thead><tr><Th>{t("students.roll")}</Th><Th>{t("students.fullName")}</Th><Th>{t("att.status")}</Th><Th>{t("att.note")}</Th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const c = cells[r.student_id];
              return (
                <Tr key={r.student_id}>
                  <Td>{r.roll_no ?? "—"}</Td>
                  <Td><div className="font-semibold">{r.full_name}</div><div className="font-mono text-xs text-mute">{r.admission_no}</div></Td>
                  <Td>
                    <div className="inline-flex overflow-hidden rounded-xl border border-line" role="group" aria-label={r.full_name}>
                      {STATUSES.map((s) => (
                        <button key={s} type="button" aria-pressed={c?.status === s} onClick={() => setS(r.student_id, s)}
                          className={cn("px-3 py-1.5 text-xs font-semibold transition", c?.status === s ? { present: "bg-ok text-white", absent: "bg-bad text-white", late: "bg-warn text-white" }[s] : "bg-card text-mute hover:bg-soft")}>
                          {t(`att.${s}`)}
                        </button>
                      ))}
                    </div>
                    {c?.confidence != null && <span className="ml-2 text-xs text-mute">{Math.round(c.confidence * 100)}%</span>}
                  </Td>
                  <Td><Input className="h-8 min-w-32" maxLength={200} value={c?.note ?? ""} aria-label={t("att.note")} onChange={(e) => setCells((x) => ({ ...x, [r.student_id]: { ...x[r.student_id], note: e.target.value } }))} /></Td>
                </Tr>
              );
            })}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
