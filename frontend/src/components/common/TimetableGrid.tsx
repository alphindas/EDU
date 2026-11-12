import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/card";
import type { Period, TtEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

export const DAYS = [0, 1, 2, 3, 4, 5];
export const hhmm = (s: string) => s.slice(0, 5);

/** Periods down, Mon-Sat across. Break periods render as a thin band. */
export default function TimetableGrid({ periods, entries, cell, onCell }: {
  periods: Period[]; entries: TtEntry[];
  cell: (e: TtEntry | undefined) => ReactNode;
  onCell?: (day: number, p: Period, e: TtEntry | undefined) => void;
}) {
  const { t } = useTranslation();
  const find = (d: number, p: Period) => entries.find((e) => e.day === d && e.period_id === p.id);
  return (
    <Card className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr>
            <th className="w-28 border-b border-line p-3 text-left text-xs font-semibold uppercase tracking-wide text-mute">{t("att.period")}</th>
            {DAYS.map((d) => <th key={d} className="border-b border-line p-3 text-left text-xs font-semibold uppercase tracking-wide text-mute">{t(`tt.d${d}`)}</th>)}
          </tr>
        </thead>
        <tbody>
          {periods.map((p) => (
            <tr key={p.id} className={cn(p.is_break && "bg-soft/60")}>
              <th scope="row" className="border-b border-line/60 p-3 text-left align-top">
                <div className="font-semibold">{p.label || p.number}</div>
                <div className="text-xs font-normal text-mute">{hhmm(p.start_time)}–{hhmm(p.end_time)}</div>
              </th>
              {p.is_break
                ? <td colSpan={DAYS.length} className="border-b border-line/60 p-2 text-center text-xs font-semibold uppercase tracking-widest text-mute">{p.label || t("tt.break")}</td>
                : DAYS.map((d) => {
                    const e = find(d, p);
                    const inner = cell(e);
                    return (
                      <td key={d} className="border-b border-line/60 p-1.5 align-top">
                        {onCell
                          ? <button type="button" onClick={() => onCell(d, p, e)} className="min-h-12 w-full rounded-lg border border-dashed border-line p-2 text-left transition hover:border-primary hover:bg-soft">{inner ?? <span className="text-mute">+</span>}</button>
                          : <div className="min-h-12 rounded-lg p-2">{inner}</div>}
                      </td>
                    );
                  })}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
