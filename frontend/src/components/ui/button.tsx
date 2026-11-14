import { Slot } from "@radix-ui/react-slot";
import { type VariantProps, cva } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition disabled:pointer-events-none disabled:opacity-50 active:scale-[.97]",
  {
    variants: {
      variant: {
        default: "bg-primary text-white shadow-sm hover:brightness-105",
        sun: "bg-sun text-navy shadow-sm hover:brightness-105",
        mint: "bg-mint text-white shadow-sm hover:brightness-105",
        outline: "border border-line bg-card text-ink hover:bg-soft",
        ghost: "text-mute hover:bg-soft hover:text-ink",
        danger: "bg-bad text-white hover:brightness-110",
        soft: "bg-soft text-primary hover:brightness-95",
      },
      size: { default: "h-10 px-4", sm: "h-8 px-3 text-xs", icon: "h-9 w-9", lg: "h-11 px-6 text-base" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, ...p }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...p} />;
});
Button.displayName = "Button";
