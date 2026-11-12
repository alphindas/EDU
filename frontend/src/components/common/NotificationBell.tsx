import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "@/components/common/bits";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { get, post } from "@/lib/api";
import type { Notice } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function NotificationBell() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const count = useQuery({ queryKey: ["notif-count"], queryFn: () => get<{ count: number }>("/notifications/unread-count"), refetchInterval: 60_000 });
  const list = useQuery({ queryKey: ["notifs"], queryFn: () => get<Notice[]>("/notifications"), enabled: open });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["notif-count"] }); qc.invalidateQueries({ queryKey: ["notifs"] }); };
  const readOne = useMutation({ mutationFn: (id: number) => post(`/notifications/${id}/read`), onSuccess: refresh });
  const readAll = useMutation({ mutationFn: () => post("/notifications/read-all"), onSuccess: refresh });
  const n = count.data?.count ?? 0;
  return (
    <>
      <button onClick={() => setOpen(true)} aria-label={t("notif.title")} className="relative grid h-9 w-9 place-items-center rounded-xl text-mute hover:bg-soft hover:text-ink">
        <Bell size={18} />
        {n > 0 && <span className="absolute -right-0.5 -top-0.5 grid min-w-4 place-items-center rounded-full bg-bad px-1 text-[10px] font-bold text-white">{n > 9 ? "9+" : n}</span>}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title={t("notif.title")}>
          {!list.data?.length ? <EmptyState text={t("notif.empty")} /> : (
            <>
              <div className="mb-3 flex justify-end"><Button variant="ghost" size="sm" onClick={() => readAll.mutate()}>{t("notif.markAll")}</Button></div>
              <ul className="space-y-2">
                {list.data.map((x) => (
                  <li key={x.id}>
                    <button onClick={() => !x.read && readOne.mutate(x.id)} className={cn("w-full rounded-xl border p-3 text-left text-sm transition", x.read ? "border-line text-mute" : "border-primary/40 bg-soft font-medium")}>
                      <div>{t(x.key, x.params)}</div>
                      <div className="mt-1 text-xs text-mute">{new Date(x.created_at).toLocaleString(i18n.language)}</div>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
