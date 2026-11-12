import * as React from "react";
import { cn } from "@/lib/utils";

export const Table = ({ className, ...p }: React.HTMLAttributes<HTMLTableElement>) => (
  <div className="w-full overflow-x-auto">
    <table className={cn("w-full min-w-[560px] text-left text-sm", className)} {...p} />
  </div>
);
export const Th = ({ className, ...p }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
  <th className={cn("whitespace-nowrap border-b border-line px-4 py-3 text-xs font-semibold uppercase tracking-wide text-mute", className)} {...p} />
);
export const Td = ({ className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
  <td className={cn("border-b border-line/60 px-4 py-3 align-middle", className)} {...p} />
);
export const Tr = ({ className, ...p }: React.HTMLAttributes<HTMLTableRowElement>) => (
  <tr className={cn("transition hover:bg-soft/60", className)} {...p} />
);
