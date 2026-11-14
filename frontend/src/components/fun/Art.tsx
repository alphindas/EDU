import { cn } from "@/lib/utils";

/** Original, hand-built SVG illustrations (no third-party art): the five Knowledge Adventure worlds, a school
 * hero scene, and small decorative bits. Kept lightweight: flat shapes + CSS animations. */

export const WORLD_COLORS: Record<string, string> = {
  science: "from-violet-200 via-sky-100 to-cyan-100",
  math: "from-amber-100 via-yellow-50 to-orange-100",
  language: "from-rose-100 via-pink-50 to-orange-50",
  innovation: "from-emerald-100 via-teal-50 to-sky-100",
  brain: "from-indigo-100 via-violet-50 to-fuchsia-100",
};

export function WorldArt({ id, className }: { id: string; className?: string }) {
  return (
    <svg viewBox="0 0 200 120" className={cn("h-full w-full", className)} aria-hidden>
      {id === "science" && (
        <g>
          <circle cx="150" cy="38" r="22" fill="#A78BFA" />
          <ellipse cx="150" cy="38" rx="36" ry="8" fill="none" stroke="#7C3AED" strokeWidth="4" transform="rotate(-18 150 38)" />
          <circle cx="40" cy="22" r="2" fill="#FACC15" className="animate-glow" /><circle cx="95" cy="14" r="2.5" fill="#FACC15" className="animate-glow" style={{ animationDelay: ".6s" }} />
          <circle cx="182" cy="80" r="2" fill="#FACC15" className="animate-glow" style={{ animationDelay: "1.1s" }} />
          <path d="M62 50 h18 v22 l18 34 a6 6 0 0 1 -5 9 h-44 a6 6 0 0 1 -5 -9 l18 -34z" fill="#E0F2FE" stroke="#1E3A8A" strokeWidth="3" />
          <path d="M50 96 l12 -20 h18 l12 20 a5 5 0 0 1 -4 8 h-34 a5 5 0 0 1 -4 -8z" fill="#34D399" />
          <circle cx="66" cy="90" r="3" fill="#fff" className="animate-float" /><circle cx="76" cy="84" r="2" fill="#fff" className="animate-float" style={{ animationDelay: "-1s" }} />
          <rect x="58" y="44" width="26" height="8" rx="3" fill="#1E3A8A" />
        </g>
      )}
      {id === "math" && (
        <g>
          <rect x="60" y="48" width="80" height="62" fill="#FDE68A" stroke="#1E3A8A" strokeWidth="3" />
          <rect x="48" y="34" width="24" height="76" fill="#FCD34D" stroke="#1E3A8A" strokeWidth="3" />
          <rect x="128" y="34" width="24" height="76" fill="#FCD34D" stroke="#1E3A8A" strokeWidth="3" />
          {[48, 56, 64, 128, 136, 144].map((x) => <rect key={x} x={x} y="26" width="6" height="9" fill="#FCD34D" stroke="#1E3A8A" strokeWidth="2" />)}
          <path d="M88 110 v-22 a12 12 0 0 1 24 0 v22z" fill="#1E3A8A" />
          <line x1="100" y1="48" x2="100" y2="16" stroke="#1E3A8A" strokeWidth="3" />
          <path d="M100 16 l22 7 -22 7z" fill="#F97316" className="animate-wiggle" />
          <text x="18" y="40" fontSize="22" fontWeight="900" fill="#F59E0B">+</text>
          <text x="166" y="62" fontSize="22" fontWeight="900" fill="#0EA5E9">×</text>
          <text x="20" y="96" fontSize="20" fontWeight="900" fill="#8B5CF6">π</text>
          <text x="168" y="104" fontSize="18" fontWeight="900" fill="#10B981">=</text>
        </g>
      )}
      {id === "language" && (
        <g>
          <path d="M100 58 C80 48 50 48 30 54 v52 c20 -6 50 -6 70 4z" fill="#fff" stroke="#1E3A8A" strokeWidth="3" />
          <path d="M100 58 C120 48 150 48 170 54 v52 c-20 -6 -50 -6 -70 4z" fill="#FFE4E6" stroke="#1E3A8A" strokeWidth="3" />
          {[66, 74, 82, 90].map((y) => <line key={y} x1="42" y1={y} x2="88" y2={y + 2} stroke="#CBD5E1" strokeWidth="3" strokeLinecap="round" />)}
          <g className="animate-float"><circle cx="128" cy="26" r="13" fill="#FB7185" /><text x="121" y="32" fontSize="16" fontWeight="800" fill="#fff">A</text></g>
          <g className="animate-float" style={{ animationDelay: "-1.3s" }}><circle cx="160" cy="34" r="12" fill="#0EA5E9" /><text x="153" y="40" fontSize="15" fontWeight="800" fill="#fff">అ</text></g>
          <g className="animate-float" style={{ animationDelay: "-2.4s" }}><circle cx="44" cy="24" r="12" fill="#F59E0B" /><text x="37" y="30" fontSize="15" fontWeight="800" fill="#fff">अ</text></g>
          <g className="animate-float" style={{ animationDelay: "-.8s" }}><circle cx="78" cy="18" r="11" fill="#8B5CF6" /><text x="71" y="24" fontSize="14" fontWeight="800" fill="#fff">അ</text></g>
        </g>
      )}
      {id === "innovation" && (
        <g>
          <path d="M0 98 q25 -8 50 0 t50 0 t50 0 t50 0 v22 h-200z" fill="#7DD3FC" />
          <ellipse cx="100" cy="98" rx="52" ry="12" fill="#FDE68A" stroke="#1E3A8A" strokeWidth="2.5" />
          <path d="M98 96 q-4 -26 6 -50" stroke="#92400E" strokeWidth="5" fill="none" strokeLinecap="round" />
          <circle cx="106" cy="32" r="16" fill="#FEF08A" stroke="#1E3A8A" strokeWidth="3" className="animate-glow" />
          <rect x="100" y="46" width="12" height="7" rx="2" fill="#94A3B8" stroke="#1E3A8A" strokeWidth="2" />
          <path d="M88 44 q-18 -4 -26 6 M120 42 q18 -6 28 2" stroke="#10B981" strokeWidth="6" fill="none" strokeLinecap="round" />
          <path d="M150 70 l10 -16 l10 16z" fill="#fff" stroke="#1E3A8A" strokeWidth="2" /><line x1="160" y1="70" x2="160" y2="84" stroke="#1E3A8A" strokeWidth="2" />
          <path d="M40 30 q4 -6 8 0 q4 -6 8 0" stroke="#1E3A8A" strokeWidth="2" fill="none" />
        </g>
      )}
      {id === "brain" && (
        <g>
          <ellipse cx="100" cy="104" rx="80" ry="12" fill="#C7D2FE" />
          <path d="M100 30 c-22 -14 -50 0 -46 22 c-14 6 -12 30 4 34 c4 14 26 18 34 8 h16 c8 10 30 6 34 -8 c16 -4 18 -28 4 -34 c4 -22 -24 -36 -46 -22z" fill="#F9A8D4" stroke="#1E3A8A" strokeWidth="3" />
          <path d="M100 32 v62 M76 50 q10 6 0 14 M124 50 q-10 6 0 14 M70 74 q14 0 16 10 M130 74 q-14 0 -16 10" stroke="#1E3A8A" strokeWidth="2.5" fill="none" strokeLinecap="round" />
          <path d="M30 22 l10 14 h-8 l8 16" stroke="#FACC15" strokeWidth="4" fill="none" strokeLinejoin="round" className="animate-glow" />
          <path d="M168 18 l-10 14 h8 l-8 16" stroke="#FACC15" strokeWidth="4" fill="none" strokeLinejoin="round" className="animate-glow" style={{ animationDelay: ".7s" }} />
        </g>
      )}
    </svg>
  );
}

/** Rolling-hills school scene used on dashboards and the login page. */
export function SchoolScene({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 400 180" className={cn("w-full", className)} aria-hidden>
      <circle cx="340" cy="40" r="22" fill="#FDE047" className="animate-glow" />
      <g className="animate-drift" style={{ animationDuration: "55s" }}><ellipse cx="60" cy="34" rx="26" ry="10" fill="#fff" /><ellipse cx="78" cy="28" rx="16" ry="10" fill="#fff" /></g>
      <g className="animate-drift" style={{ animationDuration: "70s", animationDelay: "-30s" }}><ellipse cx="200" cy="22" rx="22" ry="8" fill="#fff" /><ellipse cx="214" cy="17" rx="12" ry="8" fill="#fff" /></g>
      <path d="M0 150 q100 -40 200 -10 t200 -6 v46 h-400z" fill="#86EFAC" />
      <path d="M0 162 q120 -24 240 0 t160 -8 v26 h-400z" fill="#4ADE80" />
      <rect x="150" y="84" width="110" height="64" rx="6" fill="#FEF3C7" stroke="#1E3A8A" strokeWidth="3" />
      <path d="M140 88 l65 -34 l65 34z" fill="#F87171" stroke="#1E3A8A" strokeWidth="3" strokeLinejoin="round" />
      <circle cx="205" cy="74" r="8" fill="#fff" stroke="#1E3A8A" strokeWidth="2.5" /><path d="M205 74 v-4 M205 74 h3" stroke="#1E3A8A" strokeWidth="2" />
      <rect x="194" y="116" width="22" height="32" rx="3" fill="#0EA5E9" stroke="#1E3A8A" strokeWidth="2.5" />
      {[162, 236].map((x) => <rect key={x} x={x} y="100" width="16" height="14" rx="2" fill="#BAE6FD" stroke="#1E3A8A" strokeWidth="2" />)}
      <line x1="205" y1="54" x2="205" y2="34" stroke="#1E3A8A" strokeWidth="2.5" /><path d="M205 34 l16 5 -16 5z" fill="#FACC15" />
      {[[70, 128], [110, 136], [310, 130], [350, 138]].map(([x, y], i) => (
        <g key={i}><rect x={x - 2} y={y} width="4" height="14" fill="#92400E" /><circle cx={x} cy={y - 4} r="12" fill="#22C55E" stroke="#166534" strokeWidth="2" /></g>
      ))}
    </svg>
  );
}

export function Sparkle({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cn("h-5 w-5", className)} aria-hidden>
      <path d="M12 2 l2.2 7.8 L22 12 l-7.8 2.2 L12 22 l-2.2 -7.8 L2 12 l7.8 -2.2z" fill="currentColor" />
    </svg>
  );
}

/** Circular progress ring (XP level, scores). */
export function Ring({ value, size = 88, stroke = 10, color = "hsl(var(--ac))", children }: {
  value: number; size?: number; stroke?: number; color?: string; children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="hsl(var(--line))" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} style={{ transition: "stroke-dashoffset .8s ease" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}
