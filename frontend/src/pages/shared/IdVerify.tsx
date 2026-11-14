import { useMutation } from "@tanstack/react-query";
import { BadgeCheck, ShieldX } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/common/bits";
import { CardFace } from "@/components/common/IdCardView";
import { toastError } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { post } from "@/lib/api";
import type { IdVerify } from "@/lib/types";

/** Gate/desk check. A USB/Bluetooth QR scanner types the payload into the box and presses Enter. */
export default function IdVerifyPage() {
  const { t } = useTranslation();
  const [payload, setPayload] = useState("");
  const verify = useMutation({ mutationFn: () => post<IdVerify>("/id/verify", { payload }), onError: toastError });
  const res = verify.data;
  return (
    <>
      <PageHeader title={t("nav.idVerify")} subtitle={t("idc.verifyHint")} />
      <Card className="mb-6 p-5">
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); verify.mutate(); }} className="flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1"><Field label={t("idc.payload")}><Input autoFocus className="font-mono" value={payload} onChange={(e) => setPayload(e.target.value)} placeholder="EDN1.EDN01.EN-26-001.…" /></Field></div>
          <Button type="submit" disabled={verify.isPending || !payload.trim()}>{t("idc.verify")}</Button>
        </form>
      </Card>
      {res && (res.valid && res.student
        ? <div className="space-y-3"><p className="flex items-center justify-center gap-2 font-bold text-ok" role="status"><BadgeCheck />{t("idc.valid")}</p><CardFace c={res.student} /></div>
        : <p className="flex items-center justify-center gap-2 rounded-xl bg-bad/10 p-4 font-bold text-bad" role="alert"><ShieldX />{t("idc.invalid")}: {t(`idc.reason.${res.reason}`)}</p>)}
    </>
  );
}
