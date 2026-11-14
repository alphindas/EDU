import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import { Brand } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { post } from "@/lib/api";
import { firstLogin, homePath, useAuth } from "@/lib/auth";
import type { TokenOut } from "@/lib/types";

export default function ChangePassword() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const { user, setSession, logout } = useAuth();
  const [oldPw, setOld] = useState(firstLogin.password);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const m = useMutation({
    mutationFn: () => post<TokenOut>("/auth/change-password", { old_password: oldPw, new_password: pw }),
    onSuccess: (r) => { firstLogin.password = ""; setSession(r); nav(homePath(r.user.role), { replace: true }); },
  });
  if (!user) return <Navigate to="/login" replace />;
  const mismatch = confirm.length > 0 && pw !== confirm;
  const tooShort = pw.length > 0 && pw.length < 8;

  return (
    <div className="flex min-h-screen items-center justify-center p-5">
      <div className="w-full max-w-md">
        <Brand className="mb-8 justify-center" />
        <Card className="p-6">
          <h1 className="text-2xl font-extrabold">{t("changePw.title")}</h1>
          <p className="mb-5 mt-1 text-sm text-mute">{t("changePw.subtitle")}</p>
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (!mismatch && !tooShort) m.mutate(); }}>
            <Field label={t("changePw.old")} hint={t("changePw.oldHint")}><Input type="password" value={oldPw} onChange={(e) => setOld(e.target.value)} autoComplete="off" required /></Field>
            <Field label={t("changePw.new")} hint={tooShort ? t("changePw.min") : undefined}><Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" minLength={8} required /></Field>
            <Field label={t("changePw.confirm")} hint={mismatch ? t("changePw.mismatch") : undefined}><Input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required /></Field>
            {m.error && <p role="alert" className="rounded-lg bg-bad/10 px-3 py-2 text-sm text-bad">{(m.error as Error).message}</p>}
            <Button type="submit" className="w-full" size="lg" disabled={m.isPending || mismatch || tooShort}>{t("changePw.submit")}</Button>
            <Button type="button" variant="ghost" className="w-full" onClick={() => { logout(); nav("/login"); }}>{t("common.logout")}</Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
