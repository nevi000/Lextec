import { Send } from "lucide-react";
import { forwardRef } from "react";
import { Button } from "@/components/ui/button";
import { Label, Textarea } from "@/components/ui/input";

/** Controlled composer: the parent owns the draft so the guided demo can insert prepared texts. */
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
  function send() {
    const t = value.trim();
    if (!t || busy) return;
    onSubmit(t);
  }

  return (
    <form
      className="rounded-lg border border-line-strong bg-surface p-4 shadow-card"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      <Label htmlFor="composer" className={first ? "text-[18px] font-semibold" : undefined}>
        {first ? "Was ist passiert?" : "Weitere Informationen aus dem Gespräch"}
      </Label>
      {first && (
        <p className="mb-2 mt-1 text-[13.5px] text-ink-muted">
          Beschreiben Sie die Situation der ratsuchenden Person in eigenen Worten. Sie müssen keine juristischen Begriffe verwenden.
        </p>
      )}
      <Textarea
        id="composer"
        ref={ref}
        rows={first ? 8 : 4}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            send();
          }
        }}
        placeholder={
          first
            ? "z. B. «Meine Klientin hat von ihrem Vermieter die Kündigung erhalten …»"
            : "Neue Informationen festhalten, z. B. ein Brief, den die Klientin inzwischen erhalten hat …"
        }
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-ink-subtle">
          {disabled ? "Der Fall ist abgeschlossen." : "Strg + Enter zum Absenden · nur synthetische Daten verwenden"}
        </p>
        <Button type="submit" variant="primary" size={first ? "lg" : "md"} loading={busy} disabled={disabled || !value.trim()}>
          {busy ? (
            "Analysiere …"
          ) : (
            <>
              <Send /> {first ? "Situation analysieren" : "Erfassen"}
            </>
          )}
        </Button>
      </div>
    </form>
  );
});
