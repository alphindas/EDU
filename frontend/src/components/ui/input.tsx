import * as React from "react";
import { cn } from "@/lib/utils";

const field =
  "flex h-10 w-full rounded-xl border border-line bg-card px-3 text-sm text-ink placeholder:text-mute/70 transition focus-visible:border-primary disabled:opacity-50";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn(field, className)} {...p} />
));
Input.displayName = "Input";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...p }, ref) => (
  <select ref={ref} className={cn(field, "pr-8", className)} {...p} />
));
Select.displayName = "Select";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(field, "h-auto py-2", className)} {...p} />
));
Textarea.displayName = "Textarea";
