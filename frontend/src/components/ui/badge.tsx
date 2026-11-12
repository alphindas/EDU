import { type VariantProps, cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badge = cva("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", {
  variants: {
    tone: {
      default: "bg-soft text-primary",
      ok: "bg-ok/15 text-ok",
      warn: "bg-warn/15 text-warn",
      bad: "bg-bad/15 text-bad",
      mute: "bg-line text-mute",
    },
  },
  defaultVariants: { tone: "default" },
});

export const Badge = ({ className, tone, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) => (
  <span className={cn(badge({ tone }), className)} {...p} />
);
