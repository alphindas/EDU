import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toastError } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { fetchBlob } from "@/lib/api";

/** <img> for files that live behind auth. */
export function AuthImage({ path, alt, className }: { path: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    let live = true;
    setSrc(null); setFailed(false);
    fetchBlob(path).then((b) => { if (live) { url = URL.createObjectURL(b); setSrc(url); } }).catch(() => live && setFailed(true));
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (failed) return <div className={className} role="img" aria-label={alt} />;
  return src ? <img src={src} alt={alt} className={className} /> : <div className={className} aria-busy="true" />;
}

/** Opens an authenticated file (PDF, photo, voice note) in a new tab. */
export function FileButton({ path, name }: { path: string; name: string }) {
  const { t } = useTranslation();
  const open = async () => {
    try {
      const url = URL.createObjectURL(await fetchBlob(path));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) { toastError(e); }
  };
  return (
    <Button type="button" variant="soft" size="sm" onClick={open} title={t("common.open")}>
      <Download size={14} />{name || t("common.open")}
    </Button>
  );
}
