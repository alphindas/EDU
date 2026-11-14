import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Role, TokenOut, User } from "./types";

interface AuthState {
  access: string | null;
  refresh: string | null;
  user: User | null;
  schoolCode: string;
  setSession: (t: TokenOut) => void;
  setTokens: (access: string, refresh: string) => void;
  setUser: (u: User) => void;
  setSchoolCode: (c: string) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      access: null, refresh: null, user: null, schoolCode: "EDN01",
      setSession: (t) => set({ access: t.access_token, refresh: t.refresh_token, user: t.user }),
      setTokens: (access, refresh) => set({ access, refresh }),
      setUser: (user) => set({ user }),
      setSchoolCode: (schoolCode) => set({ schoolCode }),
      logout: () => set({ access: null, refresh: null, user: null }),
    }),
    { name: "edunest-auth" },
  ),
);

export const homePath = (role: Role) => `/${role === "superadmin" ? "admin" : role}`;

/** Password just used to sign in, held in memory only (never persisted) so the forced-change screen can prefill "current password". */
export const firstLogin = { password: "" };
