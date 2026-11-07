import { FileText, Send, TriangleAlert } from "lucide-react";
import { forwardRef, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/queries";
import { AnalysisCard } from "./AnalysisCard";

/**
 * Controlled composer: the parent owns the draft so the guided demo can insert prepared texts.
 * The PDF import is only another way to fill this very field; analysis is identical for typed and imported text.
 */
export const Composer = forwardRef<
  HTMLTextAreaElement,
  {
    first: boolean;
    busy: boolean;
    disabled: boolean;
    value: string;
    onChange: (v: string) => void;
    onSubmit: (text: string) => void;
  }
>(function Composer({ first, busy, disabled, value, onChange, onSubmit }, ref) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [imported, setImported] = useState<string | null>(null); // file name of the last successful import
  const [pending, setPending] = useState<{ text: string; name: string } | null>(null);

  function send() {
    const t = value.trim();
    if (!t || busy || importing) return;
    onSubmit(t);
  }

  function take(text: string, name: string, mode: "replace" | "append") {
    onChange(mode === "append" && value.trim() ? `${value.replace(/\s+$/, "")}\n\n${text}` : text);
    setImported(name);
    setPending(null);
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    setImportError(null);
    setImported(null);
    setPending(null);
    setImporting(true);
    try {
      const r = await api.importPdfText(file);
      if (r.truncated) {
        toast.message("Der Text wurde gekürzt", { description: "Das PDF enthält mehr Text, als eingegeben werden kann." });
      }
      if (value.trim()) setPending({ text: r.text, name: file.name });
      else take(r.text, file.name, "replace");
    } catch (e) {
      setImportError(errorMessage(e)); // existing text stays untouched
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <form
      className="rounded-xl border border-line bg-surface p-5 shadow-raised sm:p-7"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      <Label htmlFor="composer" className={first ? "font-display text-[24px] font-semibold leading-tight tracking-tight text-ink" : undefined}>
        {first ? "Was ist passiert?" : "Weitere Informationen aus dem Gespräch"}
      </Label>
      {first && (
        <p className="mb-4 mt-1.5 max-w-[60ch] text-[15px] text-ink-muted">
          Beschreiben Sie die Situation der ratsuchenden Person in eigenen Worten oder importieren Sie eine bereits
          verfasste Fallbeschreibung als PDF.
        </p>
      )}
      <Textarea
        id="composer"
        ref={ref}
        rows={first ? 10 : 4}
        value={value}
        disabled={disabled}
        readOnly={busy}
        aria-busy={busy}
        className={busy ? "bg-sunken text-ink-muted" : first ? "rounded-xl px-4 py-3.5 text-[15.5px] leading-relaxed" : undefined}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            send();
          }
        }}
        placeholder={
          first
            ? "z. B. Meine Klientin hat von ihrem Vermieter eine Kündigung erhalten und weiss nicht, wie sie reagieren soll …"
            : "Neue Informationen festhalten, z. B. ein Brief, den die Klientin inzwischen erhalten hat …"
        }
      />

      {first && !disabled && (
        <div className="mt-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              tabIndex={-1}
              aria-label="PDF-Datei auswählen"
              data-testid="pdf-input"
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={importing}
              disabled={busy || importing}
              onClick={() => fileRef.current?.click()}
            >
              <FileText /> {importing ? "PDF wird ausgelesen …" : "Fallbeschreibung als PDF importieren"}
            </Button>
            <p className="text-[12px] text-ink-subtle">
              Nur eine bereits verfasste Fallbeschreibung. Vertragsunterlagen, Kündigungsschreiben und Belege werden hier
              nicht benötigt.
            </p>
          </div>

          {pending && (
            <div role="group" aria-label="PDF-Text übernehmen" className="mt-3 rounded-md border border-line bg-sunken/60 p-3">
              <p className="text-[13px]">
                Das Eingabefeld enthält bereits Text. Was soll mit dem Text aus «{pending.name}» geschehen?
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="primary" onClick={() => take(pending.text, pending.name, "append")}>
                  Text aus PDF anhängen
                </Button>
                <Button type="button" size="sm" variant="secondary" onClick={() => take(pending.text, pending.name, "replace")}>
                  Bestehenden Text ersetzen
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setPending(null)}>
                  Abbrechen
                </Button>
              </div>
            </div>
          )}
          {imported && !pending && (
            <p role="status" className="mt-2 text-[12.5px] text-brand-700" data-testid="pdf-imported">
              Fallbeschreibung aus PDF übernommen ({imported}). Bitte überprüfen Sie den Text vor der Analyse.
            </p>
          )}
          {importError && (
            <p role="alert" className="mt-2 flex items-start gap-1.5 text-[12.5px] text-error-fg" data-testid="pdf-error">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {importError}
            </p>
          )}
        </div>
      )}

      {busy && first && <AnalysisCard />}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-ink-subtle">
          {disabled ? "Der Fall ist abgeschlossen." : "Strg + Enter zum Absenden · nur synthetische Daten verwenden"}
        </p>
        <Button
          type="submit"
          variant="primary"
          size={first ? "lg" : "md"}
          loading={busy}
          disabled={disabled || busy || importing || !value.trim()}
        >
          {busy ? (
            "Analysiere …"
          ) : (
            <>
              <Send /> {first ? "Fall analysieren" : "Erfassen"}
            </>
          )}
        </Button>
      </div>
    </form>
  );
});
