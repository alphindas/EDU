import { useQuery } from "@tanstack/react-query";
import { Phone } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState, Loading } from "@/components/common/bits";
import { PageHero } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/card";
import { API_BASE, get } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Live } from "@/lib/v2";
import { cn } from "@/lib/utils";

/** Live school bus: WebSocket updates every few seconds (falls back to polling). Route drawn as a friendly SVG road. */
export default function Bus() {
  const { t } = useTranslation();
  const my = useQuery({ queryKey: ["bus-my"], queryFn: () => get<{ student_id: number; name: string; stop_name: string; vehicle_id: number | null; live: Live | null }[]>("/transport/my"), refetchInterval: 20_000 });
  return (
    <div>
      <PageHero title={t("bus.title")} subtitle={t("bus.sub")} emoji="🚌" />
      {my.isLoading ? <Loading /> : !my.data?.length ? <EmptyState text={t("bus.none")} /> : (
        <div className="space-y-5">{my.data.map((x) => <BusCard key={x.student_id} name={x.name} stop={x.stop_name} vid={x.vehicle_id} initial={x.live} />)}</div>
      )}
    </div>
  );
}

function BusCard({ name, stop, vid, initial }: { name: string; stop: string; vid: number | null; initial: Live | null }) {
  const { t, i18n } = useTranslation();
  const access = useAuth((s) => s.access);
  const [live, setLive] = useState<Live | null>(initial);
  useEffect(() => {
    if (!vid || !access) return;
    const base = API_BASE || window.location.origin;
    const ws = new WebSocket(`${base.replace(/^http/, "ws")}/api/ws/bus/${vid}?token=${encodeURIComponent(access)}`);
    ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.type === "bus") setLive(m as Live); };
    return () => ws.close();
  }, [vid, access]);
  if (!live) return <Card className="p-5"><b>{name}</b> · {t("bus.noVehicle")}</Card>;
  const stops = live.stops;
  const last = stops[stops.length - 1].minute || 1;
  const nextIdx = stops.findIndex((s) => !s.passed);
  // bus x-position along the road: by simulated minute progress
  const prog = live.state === "arrived" ? 1 : live.state === "not_started" ? 0 : (() => {
    const i = Math.max(1, nextIdx); const a = stops[i - 1], b = stops[i];
    const f = b ? 1 - (b.eta_min ?? 0) / Math.max(1, b.minute - a.minute) : 1;
    return (a.minute + Math.min(1, Math.max(0, f)) * ((b?.minute ?? a.minute) - a.minute)) / last;
  })();
  const W = 700, X0 = 40, X1 = 660;
  const xOf = (m: number) => X0 + ((X1 - X0) * m) / last;
  const myStop = stops.find((s) => s.name === stop);
  return (
    <Card className="overflow-hidden p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto font-display text-xl font-extrabold">👦 {name} · {live.route.name}</h2>
        <span className={cn("chip", live.state === "on_route" ? "bg-ok/15 text-ok" : "bg-line")}>{t(`bus.state.${live.state}`)}</span>
        {live.simulated && <span className="chip bg-amber-100 text-amber-700">{t("bus.simulated")}</span>}
      </div>
      {myStop && !myStop.passed && <div className="mt-3 rounded-2xl grad-sun p-4 text-navy"><div className="text-sm font-bold">{t("bus.yourStop", { stop })}</div>
        <div className="font-display text-4xl font-extrabold">{myStop.eta_min} {t("bus.min")}</div></div>}
      {myStop?.passed && <div className="mt-3 rounded-2xl bg-ok/10 p-3 font-bold text-ok">✓ {t("bus.passed", { stop })}</div>}
      <div className="mt-4 overflow-x-auto">
        <svg viewBox={`0 0 ${W} 150`} className="min-w-[560px]" role="img" aria-label={t("bus.map")}>
          <rect x="20" y="70" width={W - 40} height="26" rx="13" fill="#94A3B8" />
          <line x1="30" y1="83" x2={W - 30} y2="83" stroke="#fff" strokeWidth="3" strokeDasharray="14 12" />
          {stops.map((s, i) => (
            <g key={i}>
              <circle cx={xOf(s.minute)} cy="83" r={s.name === stop ? 11 : 8} fill={s.passed ? "#34D399" : s.name === stop ? "#FACC15" : "#fff"} stroke="#1E3A8A" strokeWidth="3" />
              <text x={xOf(s.minute)} y={i % 2 ? 128 : 50} textAnchor="middle" fontSize="13" fontWeight="800" fill="#1E3A8A">{s.name}</text>
              <text x={xOf(s.minute)} y={i % 2 ? 144 : 34} textAnchor="middle" fontSize="11" fill="#64748B">{s.passed ? "✓" : `${s.eta_min} min`}</text>
            </g>
          ))}
          <g transform={`translate(${X0 + (X1 - X0) * prog - 22}, 52)`} style={{ transition: "transform 2.5s linear" }}>
            <rect width="44" height="26" rx="7" fill="#FACC15" stroke="#1E3A8A" strokeWidth="2.5" />
            <rect x="5" y="5" width="11" height="8" rx="2" fill="#BAE6FD" /><rect x="19" y="5" width="11" height="8" rx="2" fill="#BAE6FD" /><rect x="33" y="5" width="7" height="8" rx="2" fill="#BAE6FD" />
            <circle cx="11" cy="27" r="5" fill="#1E293B" /><circle cx="34" cy="27" r="5" fill="#1E293B" />
          </g>
        </svg>
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        <span className="chip bg-soft">🚌 {live.vehicle.number}</span>
        <span className="chip bg-soft">👨‍✈️ {live.vehicle.driver_name}</span>
        {live.vehicle.driver_phone && <a className="chip bg-soft text-primary" href={`tel:${live.vehicle.driver_phone}`}><Phone size={12} /> {live.vehicle.driver_phone}</a>}
        <span className="chip bg-soft">⏰ {t("bus.start", { time: live.route.start_time })}</span>
        <span className="chip bg-soft">🔄 {new Date(live.updated_at).toLocaleTimeString(i18n.language)}</span>
      </div>
    </Card>
  );
}
