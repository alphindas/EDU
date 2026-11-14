import { cn } from "@/lib/utils";
import fullImg from "@/assets/chitti.webp";
import headImg from "@/assets/chitti-head.webp";

/** CHITTI: EduNest's robot buddy, drawn from the robot picture in src/assets.
 *  - size >= 72 shows the full robot in a soft rounded card; smaller sizes show the face in a circle.
 *  - mood adds a gentle motion or a small badge (no loud effects).
 *  - speaking / listening add a calm glowing ring for the voice "talk" mode.
 *  - avatar items from the shop (hat, colour ring, pet) still show on top.
 *  To change the picture, replace src/assets/chitti.webp (full body) and chitti-head.webp (face, square). */
export type Mood = "happy" | "wave" | "think" | "cheer" | "sleepy" | "wow";
export interface Avatar { hat?: string; color?: string; pet?: string }

const RING: Record<string, string> = {
  color_mint: "ring-emerald-300",
  color_lavender: "ring-violet-300",
  color_sun: "ring-yellow-300",
  color_coral: "ring-orange-300",
};
const HAT: Record<string, string> = { hat_cap: "🧢", hat_crown: "👑", hat_grad: "🎓", hat_party: "🥳" };
const PET: Record<string, string> = { pet_star: "⭐", pet_rocket: "🚀", pet_owl: "🦉", pet_cat: "🐱" };
const BADGE: Partial<Record<Mood, string>> = { think: "💭", sleepy: "💤", wow: "✨", cheer: "🎉" };

export default function Chitti({
  size = 120, mood = "happy", avatar, className, float = true, title = "CHITTI", speaking = false, listening = false,
}: {
  size?: number; mood?: Mood; avatar?: Avatar; className?: string; float?: boolean; title?: string;
  speaking?: boolean; listening?: boolean;
}) {
  const small = size < 72;
  const w = size;
  const h = small ? size : Math.round(size * 1.26);
  const ring = RING[avatar?.color ?? ""];
  const motion = speaking ? "animate-talk" : mood === "cheer" ? "animate-hop" : mood === "wave" ? "animate-sway" : mood === "think" ? "animate-tilt" : "";
  const badge = BADGE[mood];
  return (
    <div
      className={cn("relative inline-block shrink-0 select-none", float && !speaking && "animate-float", className)}
      style={{ width: w, height: h }}
      role="img"
      aria-label={title}
    >
      {(speaking || listening) && (
        <span
          aria-hidden
          className={cn("absolute -inset-1.5 animate-ping-soft", small ? "rounded-full" : "rounded-[30%]", listening ? "bg-rose-300/50" : "bg-primary/35")}
        />
      )}
      <div
        className={cn(
          "relative h-full w-full overflow-hidden bg-[#bfe5fc] shadow-sm",
          small ? "rounded-full" : "rounded-[28%]",
          ring && `ring-4 ${ring}`,
          (speaking || listening) && "ring-4 ring-primary/50",
          mood === "sleepy" && "opacity-75 saturate-50",
          motion,
        )}
      >
        <img
          src={small ? headImg : fullImg}
          alt=""
          draggable={false}
          className="h-full w-full object-cover object-top"
          loading="lazy"
        />
      </div>
      {badge && !small && (
        <span aria-hidden className="absolute -right-1 -top-1 grid place-items-center rounded-full bg-card shadow-card animate-pop" style={{ width: size * 0.26, height: size * 0.26, fontSize: size * 0.14 }}>
          {badge}
        </span>
      )}
      {avatar?.hat && HAT[avatar.hat] && (
        <span className="pointer-events-none absolute left-1/2 -translate-x-1/2" style={{ top: -size * 0.16, fontSize: size * 0.28 }} aria-hidden>{HAT[avatar.hat]}</span>
      )}
      {avatar?.pet && PET[avatar.pet] && (
        <span className="pointer-events-none absolute animate-float" style={{ right: -size * 0.16, bottom: size * 0.02, fontSize: size * 0.22, animationDelay: "-1.5s" }} aria-hidden>{PET[avatar.pet]}</span>
      )}
    </div>
  );
}

/** Speech bubble next to CHITTI. */
export function Bubble({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("relative rounded-2xl border border-line bg-card px-4 py-3 text-sm font-medium shadow-card animate-pop", className)}>
      {children}
      <span className="absolute -left-[7px] top-6 h-3 w-3 rotate-45 border-b border-l border-line bg-card" aria-hidden />
    </div>
  );
}
