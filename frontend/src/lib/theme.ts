import { create } from "zustand";
import { persist } from "zustand/middleware";

export const ACCENTS = ["ocean", "forest", "sunset", "violet", "rose"] as const;
export type Accent = (typeof ACCENTS)[number];

interface ThemeState { dark: boolean; accent: Accent; toggle: () => void; setAccent: (a: Accent) => void }

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      dark: true,
      accent: "ocean",
      toggle: () => set((s) => ({ dark: !s.dark })),
      setAccent: (accent) => set({ accent }),
    }),
    { name: "edunest-theme" },
  ),
);

export function applyTheme(dark: boolean, accent: Accent) {
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.dataset.accent = accent;
}
