import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "@/components/common/bits";
import { toast, toastError } from "@/components/common/toast";
import { PageHero } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/label";
import { Input, Select, Textarea } from "@/components/ui/input";
import { del, get, post, put } from "@/lib/api";
import { useStudentPage } from "@/lib/queries";
import type { Stop } from "@/lib/v2";

interface RouteT { id: number; name: string; start_time: string; stops: Stop[] }
interface Veh { id: number; number: string; route_id: number | null; driver_name: string; driver_phone: string; capacity: number; device_token: string }

export default function Transport() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const routes = useQuery({ queryKey: ["routes"], queryFn: () => get<RouteT[]>("/transport/routes") });
  const vehicles = useQuery({ queryKey: ["vehicles"], queryFn: () => get<Veh[]>("/transport/vehicles") });
  const asg = useQuery({ queryKey: ["bus-asg"], queryFn: () => get<{ student_id: number; name: string; route_id: number; stop_name: string }[]>("/transport/assignments") });
  const students = useStudentPage({ limit: 200 });
  const done = () => ["routes", "vehicles", "bus-asg"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const [r, setR] = useState({ name: "", start_time: "07:30", stops: "Gate, 17.41, 78.40, 0\nSchool, 17.44, 78.39, 30" });
  const [v, setV] = useState({ number: "", route_id: "", driver_name: "", driver_phone: "" });
  const [a, setA] = useState({ student_id: "", route_id: "", stop_name: "" });
  const addRoute = useMutation({
    mutationFn: () => post("/transport/routes", { name: r.name, start_time: r.start_time, stops: r.stops.split("\n").filter(Boolean).map((l) => {
      const [name, lat, lng, minute] = l.split(",").map((x) => x.trim()); return { name, lat: Number(lat), lng: Number(lng), minute: Number(minute) };
    }) }), onSuccess: () => { toast(t("common.saved")); done(); }, onError: toastError });
  const addVeh = useMutation({ mutationFn: () => post("/transport/vehicles", { ...v, route_id: v.route_id ? Number(v.route_id) : null }), onSuccess: () => { toast(t("common.saved")); done(); }, onError: toastError });
  const assign = useMutation({ mutationFn: () => put("/transport/assignments", { student_id: Number(a.student_id), route_id: Number(a.route_id), stop_name: a.stop_name }), onSuccess: () => { toast(t("common.saved")); done(); }, onError: toastError });
  const rmRoute = useMutation({ mutationFn: (id: number) => del(`/transport/routes/${id}`), onSuccess: done, onError: toastError });
  const rmVeh = useMutation({ mutationFn: (id: number) => del(`/transport/vehicles/${id}`), onSuccess: done, onError: toastError });
  const route = routes.data?.find((x) => String(x.id) === a.route_id);
  return (
    <div>
      <PageHero title={t("tr.title")} subtitle={t("tr.sub")} emoji="🚌" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="space-y-3 p-5">
          <h3 className="font-display text-lg font-extrabold">🛣️ {t("tr.routes")}</h3>
          {(routes.data ?? []).map((x) => <div key={x.id} className="flex items-center gap-2 rounded-2xl bg-soft/60 p-2.5 text-sm"><div className="flex-1"><b>{x.name}</b><div className="text-xs text-mute">⏰ {x.start_time} · {x.stops.map((s) => s.name).join(" → ")}</div></div>
            <button onClick={() => rmRoute.mutate(x.id)} className="text-mute hover:text-bad" aria-label={t("common.delete")}><Trash2 size={15} /></button></div>)}
          <Field label={t("tr.routeName")}><Input value={r.name} onChange={(e) => setR({ ...r, name: e.target.value })} /></Field>
          <Field label={t("tr.start")}><Input type="time" value={r.start_time} onChange={(e) => setR({ ...r, start_time: e.target.value })} /></Field>
          <Field label={t("tr.stops")} hint={t("tr.stopsHint")}><Textarea rows={4} value={r.stops} onChange={(e) => setR({ ...r, stops: e.target.value })} /></Field>
          <Button className="w-full" disabled={!r.name} onClick={() => addRoute.mutate()}><Plus size={16} /> {t("tr.addRoute")}</Button>
        </Card>
        <Card className="space-y-3 p-5">
          <h3 className="font-display text-lg font-extrabold">🚍 {t("tr.vehicles")}</h3>
          {(vehicles.data ?? []).map((x) => <div key={x.id} className="rounded-2xl bg-soft/60 p-2.5 text-sm"><div className="flex items-center"><b className="flex-1">{x.number}</b><button onClick={() => rmVeh.mutate(x.id)} className="text-mute hover:text-bad" aria-label={t("common.delete")}><Trash2 size={15} /></button></div>
            <div className="text-xs text-mute">{x.driver_name} · {routes.data?.find((y) => y.id === x.route_id)?.name ?? "—"}</div>
            <div className="mt-1 break-all font-mono text-[10px] text-mute">{t("tr.token")}: {x.device_token}</div></div>)}
          <Field label={t("tr.number")}><Input value={v.number} onChange={(e) => setV({ ...v, number: e.target.value })} /></Field>
          <Field label={t("tr.route")}><Select value={v.route_id} onChange={(e) => setV({ ...v, route_id: e.target.value })}><option value="">—</option>{routes.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select></Field>
          <div className="grid grid-cols-2 gap-2"><Field label={t("tr.driver")}><Input value={v.driver_name} onChange={(e) => setV({ ...v, driver_name: e.target.value })} /></Field>
            <Field label={t("tr.phone")}><Input value={v.driver_phone} onChange={(e) => setV({ ...v, driver_phone: e.target.value })} /></Field></div>
          <Button className="w-full" disabled={!v.number} onClick={() => addVeh.mutate()}><Plus size={16} /> {t("tr.addVehicle")}</Button>
          <p className="text-xs text-mute">{t("tr.gpsHint")}</p>
        </Card>
        <Card className="space-y-3 p-5">
          <h3 className="font-display text-lg font-extrabold">👧 {t("tr.assign")}</h3>
          <Field label={t("tr.student")}><Select value={a.student_id} onChange={(e) => setA({ ...a, student_id: e.target.value })}><option value="">—</option>{students.data?.items.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}</Select></Field>
          <Field label={t("tr.route")}><Select value={a.route_id} onChange={(e) => setA({ ...a, route_id: e.target.value, stop_name: "" })}><option value="">—</option>{routes.data?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select></Field>
          <Field label={t("tr.stop")}><Select value={a.stop_name} onChange={(e) => setA({ ...a, stop_name: e.target.value })}><option value="">—</option>{route?.stops.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}</Select></Field>
          <Button className="w-full" disabled={!a.student_id || !a.route_id} onClick={() => assign.mutate()}>{t("tr.save")}</Button>
          {!asg.data?.length ? <EmptyState /> : <ul className="space-y-1 text-sm">{asg.data.map((x) => <li key={x.student_id} className="rounded-xl bg-soft/60 px-2 py-1"><b>{x.name}</b> · {routes.data?.find((y) => y.id === x.route_id)?.name} · {x.stop_name}</li>)}</ul>}
        </Card>
      </div>
    </div>
  );
}
