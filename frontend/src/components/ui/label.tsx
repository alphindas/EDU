import * as LabelPrimitive from "@radix-ui/react-label";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...p }, ref) => (
  <LabelPrimitive.Root ref={ref} className={cn("mb-1.5 block text-xs font-semibold uppercase tracking-wide text-mute", className)} {...p} />
));
Label.displayName = "Label";

export const Field = ({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) => {
  const id = React.useId();
  const child = React.isValidElement<{ id?: string }>(children) ? React.cloneElement(children, { id: children.props.id ?? id }) : children;
  const forId = React.isValidElement<{ id?: string }>(children) ? (children.props.id ?? id) : undefined;
  return (
    <div>
      <Label htmlFor={forId}>{label}</Label>
      {child}
      {hint && <p className="mt-1 text-xs text-mute">{hint}</p>}
    </div>
  );
};
