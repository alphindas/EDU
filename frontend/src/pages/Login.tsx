import { useMutation } from "@tanstack/react-query";
import { GraduationCap, KeyRound, ShieldCheck, Smartphone, Sparkles, User } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import { Brand, LangSwitcher, ThemeControls } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { post } from "@/lib/api";
import { firstLogin, homePath, useAuth } from "@/lib/auth";
import type { TokenOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const ROLES = [
  { id: "admin", icon: ShieldCheck },
  { id: "teacher", icon: GraduationCap },
  { id: "student", icon: User },
  { id: "parent", icon: Smartphone },
] as const;

const DEMO: Record<string, { id: string; pw: string }> = {
  admin: { id: "admin", pw: "admin123" },
  teacher: { id: "T-001", pw: "teacher123" },
  student: { id: "EN-26-001", pw: "15082010" },
  parent: { id: "9000000001", pw: "" },
};

export default function Login() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { user, setSession, schoolCode, setSchoolCode } = useAuth();
  const [role, setRole] = useState<(typeof ROLES)[number]["id"]>("admin");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);

  const done = (r: TokenOut) => {
    firstLogin.password = r.must_change_password ? password : "";
    setSession(r);
    nav(r.must_change_password ? "/change-password" : homePath(r.user.role), { replace: true });
  };
  const loginM = useMutation({
    mutationFn: () => post<TokenOut>("/auth/login", { school_code: schoolCode, role, login_id: loginId, password }),
    onSuccess: done,
  });
  const otpReq = useMutation({ mutationFn: () => post("/auth/otp/request", { school_code: schoolCode, mobile: loginId }), onSuccess: () => setOtpSent(true) });
  const otpVerify = useMutation({
    mutationFn: () => post<TokenOut>("/auth/otp/verify", { school_code: schoolCode, mobile: loginId, code: otp }),
    onSuccess: done,
  });

  if (user) return <Navigate to={user.must_change_password ? "/change-password" : homePath(user.role)} replace />;

  const isParent = role === "parent";
  const err = (loginM.error || otpReq.error || otpVerify.error) as Error | null;
  const fill = (r: string) => { setRole(r as typeof role); setLoginId(DEMO[r].id); setPassword(DEMO[r].pw); setOtpSent(false); setOtp(""); };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="grad-bg relative hidden overflow-hidden p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-black/20 blur-3xl" />
        <div className="relative flex items-center gap-2.5 text-xl font-extrabold"><GraduationCap /> EduNest</div>
        <div className="relative max-w-md">
          <Sparkles className="mb-4 opacity-80" />
          <h1 className="text-4xl font-extrabold leading-tight">{t("login.heroTitle")}</h1>
          <p className="mt-4 text-lg text-white/80">{t("login.heroBody")}</p>
          <p className="mt-8 text-sm font-semibold tracking-wide text-white/70">{t("app.tagline")}</p>
        </div>
      </section>

      <section className="relative flex items-center justify-center p-5">
        <div className="absolute right-4 top-4 flex items-center gap-1.5"><LangSwitcher /><ThemeControls /></div>
        <div className="w-full max-w-md">
          <Brand className="mb-8 lg:hidden" />
          <h2 className="text-3xl font-extrabold tracking-tight">{t("login.title")}</h2>
          <p className="mb-6 mt-1 text-mute">{t("login.subtitle")}</p>

          <Card className="p-6">
            <div className="mb-5 grid grid-cols-4 gap-1.5 rounded-xl bg-soft p-1" role="tablist" aria-label={t("login.role")}>
              {ROLES.map(({ id, icon: Icon }) => (
                <button
                  key={id} role="tab" aria-selected={role === id}
                  onClick={() => { setRole(id); setLoginId(""); setPassword(""); setOtpSent(false); loginM.reset(); }}
                  className={cn("flex flex-col items-center gap-1 rounded-lg py-2 text-[11px] font-semibold transition", role === id ? "bg-card text-primary shadow-card" : "text-mute hover:text-ink")}
                >
                  <Icon size={17} />{t(`roles.${id}`)}
                </button>
              ))}
            </div>

            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                if (!isParent) loginM.mutate();
                else if (otpSent) otpVerify.mutate();
                else otpReq.mutate();
              }}
            >
              <Field label={t("login.schoolCode")}>
                <Input value={schoolCode} onChange={(e) => setSchoolCode(e.target.value.toUpperCase())} autoCapitalize="characters" required />
              </Field>
              <Field label={t(`login.${role}`)} hint={role === "student" ? t("login.studentHint") : undefined}>
                <Input value={loginId} onChange={(e) => setLoginId(e.target.value)} inputMode={isParent ? "numeric" : undefined} autoComplete="username" required disabled={isParent && otpSent} />
              </Field>
              {isParent ? (
                otpSent && (
                  <Field label={t("login.otp")} hint={`${t("login.otpSent", { mobile: loginId })} · ${t("login.otpHint")}`}>
                    <Input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" maxLength={6} autoFocus required />
                  </Field>
                )
              ) : (
                <Field label={t("login.password")}>
                  <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
                </Field>
              )}
              {err && <p role="alert" className="rounded-lg bg-bad/10 px-3 py-2 text-sm text-bad">{err.message === "Invalid credentials" ? t("login.invalid") : err.message}</p>}
              <Button type="submit" size="lg" className="w-full" disabled={loginM.isPending || otpReq.isPending || otpVerify.isPending}>
                <KeyRound size={16} />
                {isParent ? (otpSent ? t("login.verify") : t("login.sendOtp")) : t("login.signIn")}
              </Button>
            </form>
          </Card>

          <div className="mt-5 text-center text-xs text-mute">
            <span className="mr-2 font-semibold uppercase tracking-wide">{t("login.demo")}:</span>
            {ROLES.map((r) => (
              <button key={r.id} onClick={() => fill(r.id)} className="mx-1 rounded-full bg-soft px-2.5 py-1 font-semibold text-primary hover:brightness-110">
                {t(`roles.${r.id}`)}
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
