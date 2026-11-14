import { CheckCircle2, XCircle } from "lucide-react";
import { create } from "zustand";
import { cn } from "@/lib/utils";

interface T { id: number; text: string; bad?: boolean }
interface S { items: T[]; push: (text: string, bad?: boolean) => void }
let n = 0;
export const useToast = create<S>((set) => ({
  items: [],
  push: (text, bad) => {
    const id = ++n;
    set((s) => ({ items: [...s.items, { id, text, bad }] }));
    setTimeout(() => set((s) => ({ items: s.items.filter((i) => i.id !== id) })), 3500);
  },
}));
export const toast = (text: string) => useToast.getState().push(text);
export const toastError = (e: unknown) => useToast.getState().push(e instanceof Error ? e.message : String(e), true);

export function Toaster() {
  const items = useToast((s) => s.items);
  return (
    <div className="pointer-events-none fixed bottom-20 right-4 z-[60] flex flex-col gap-2 lg:bottom-6" aria-live="polite">
      {items.map((i) => (
        <div key={i.id} className={cn("pointer-events-auto flex items-center gap-2 rounded-xl border bg-card px-4 py-3 text-sm font-medium shadow-card animate-fade", i.bad ? "border-bad/50 text-bad" : "border-ok/50")}>
          {i.bad ? <XCircle size={18} /> : <CheckCircle2 size={18} className="text-ok" />} {i.text}
        </div>
      ))}
    </div>
  );
}
