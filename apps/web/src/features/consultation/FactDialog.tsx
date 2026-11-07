import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { BadgeCheck, Quote } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { FactStatusBadge, ProvenanceBadge } from "@/components/shared/badges";
import { SectionLabel } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { FieldError, Label, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { errorMessage, useInvalidateCase } from "@/lib/queries";
import { displayValue, formatDateTime } from "@/lib/utils";
import type { FactView } from "@/types";
import { ValueField, valueToField } from "./ValueField";

const EVENT_LABEL: Record<string, string> = {
  extracted: "Aus Schilderung extrahiert (KI)",
  answered: "Antwort erfasst",
  corrected: "Von Ihnen korrigiert",
  confirmed: "Bestätigt",
  confirmation_removed: "Bestätigung entfernt",
  contradiction: "Widerspruch erkannt",
  ambiguous: "Als unklar markiert",
  ambiguous_ignored: "Unklare Aussage ignoriert",
  ai_conflict_suppressed: "KI-Wert verworfen (Ihr Wert bleibt)",
  reconfirmed: "Erneut genannt",
  deferred: "Zurückgestellt",
  undeferred: "Zurückstellung aufgehoben",
  marked_not_applicable: "Als nicht zutreffend markiert",
  reset: "Zurückgesetzt",
  unknown: "Gefragt, der Klientin unbekannt",
  unknown_ignored: "«Unbekannt» ignoriert (Wert bereits vorhanden)",
  ambiguity_exhausted: "Zweimal unklar: gilt als unbekannt",
  documented: "Als dokumentarisch belegt markiert",
  documented_removed: "Beleg-Markierung entfernt",
};

const schema = z.object({ value: z.string().trim().min(1, "Bitte einen Wert angeben."), note: z.string().max(500).optional() });
type FormValues = z.infer<typeof schema>;

export function FactDialog({
  caseId,
  fact,
  open,
  onOpenChange,
  closed,
}: {
  caseId: string;
  fact: FactView | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  closed: boolean;
}) {
  const invalidate = useInvalidateCase(caseId);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: { value: valueToField(fact?.value), note: "" },
  });

  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof api.patchFact>[2]) => api.patchFact(caseId, fact?.fact_id ?? "", body),
    onSuccess: () => {
      void invalidate();
      toast.success("Angabe aktualisiert");
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!fact) return null;
  const disabled = closed || mutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogTitle>{fact.label_de}</DialogTitle>
        <DialogDescription>{fact.why_needed_de || "Angabe zum Fall."}</DialogDescription>

        <div className="mt-4 rounded-md border border-line bg-sunken p-3">
          <div className="flex flex-wrap items-center gap-2">
            <FactStatusBadge status={fact.status} />
            <span className="text-[14px] font-medium">
              {fact.enum_labels_de?.[String(fact.value)] ?? displayValue(fact.value)}
            </span>
            {fact.documented && <span className="rounded-full bg-proceed-bg px-2 py-0.5 text-[11.5px] text-proceed-fg">Dokumentarisch belegt</span>}
            <ProvenanceBadge origin={fact.origin} confirmed={fact.confirmed} />
          </div>
          {fact.evidence_quote && (
            <p className="mt-2.5 flex gap-2 text-[12.5px] text-ink-muted">
              <Quote className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span>
                Beleg: <q className="not-italic">{fact.evidence_quote}</q>
              </span>
            </p>
          )}
          {fact.conflicting_values.length > 0 && (
            <div className="mt-2.5 rounded-md bg-escalate-bg p-2.5 text-[12.5px] text-escalate-fg">
              <p className="font-medium">Widersprüchliche Angabe</p>
              {fact.conflicting_values.map((c, i) => (
                <p key={i}>
                  {displayValue(c.value)} – <q className="not-italic">{String(c.evidence_quote ?? "")}</q>
                </p>
              ))}
            </div>
          )}
          {fact.deferred_reason && (
            <p className="mt-2.5 text-[12.5px] text-ask-fg">Zurückgestellt: {fact.deferred_reason}</p>
          )}
        </div>

        <form
          className="mt-5 space-y-3"
          onSubmit={form.handleSubmit((v) => mutation.mutate({ value: v.value, note: v.note || undefined }))}
        >
          <div>
            <Label htmlFor="fact-value">Wert korrigieren oder ergänzen</Label>
            <Controller
              control={form.control}
              name="value"
              render={({ field }) => (
                <ValueField
                  id="fact-value"
                  dataType={fact.data_type}
                  enumValues={fact.enum_values}
                  enumLabels={fact.enum_labels_de ?? {}}
                  value={field.value}
                  onChange={field.onChange}
                  invalid={!!form.formState.errors.value}
                />
              )}
            />
            <FieldError>{form.formState.errors.value?.message}</FieldError>
          </div>
          <div>
            <Label htmlFor="fact-note">Notiz (optional)</Label>
            <Textarea id="fact-note" rows={2} className="min-h-[56px]" {...form.register("note")} />
          </div>
          <p className="text-[12px] text-ink-subtle">
            Ihre Eingabe gilt als bestätigt und wird von späteren KI-Auswertungen nicht überschrieben.
          </p>
          <DialogFooter className="!mt-4 justify-between">
            <div className="flex flex-wrap gap-2">
              {fact.status === "KNOWN" && !fact.confirmed && (
                <Button type="button" variant="secondary" size="sm" disabled={disabled} onClick={() => mutation.mutate({ confirmed: true })}>
                  <BadgeCheck /> Wert bestätigen
                </Button>
              )}
              {fact.status === "KNOWN" && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={disabled}
                  onClick={() => mutation.mutate({ documented: !fact.documented })}
                >
                  {fact.documented ? "Beleg-Markierung entfernen" : "Durch Dokument belegt"}
                </Button>
              )}
              {fact.status !== "UNKNOWN" && fact.status !== "KNOWN" && (
                <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => mutation.mutate({ status: "UNKNOWN" })}>
                  Gefragt, unbekannt
                </Button>
              )}
              {fact.status !== "NOT_APPLICABLE" && (
                <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => mutation.mutate({ status: "NOT_APPLICABLE" })}>
                  Nicht zutreffend
                </Button>
              )}
              {fact.status !== "MISSING" && (
                <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => mutation.mutate({ status: "MISSING" })}>
                  Zurücksetzen
                </Button>
              )}
            </div>
            <Button type="submit" loading={mutation.isPending} disabled={closed}>
              Speichern
            </Button>
          </DialogFooter>
        </form>

        {fact.history.length > 0 && (
          <div className="mt-5 border-t border-line pt-4">
            <SectionLabel>Verlauf</SectionLabel>
            <ol className="mt-2 space-y-1.5">
              {[...fact.history].reverse().map((h, i) => (
                <li key={i} className="flex flex-wrap items-baseline gap-x-2 text-[12.5px]">
                  <span className="text-ink-subtle">{formatDateTime(h.at)}</span>
                  <span className="font-medium">{EVENT_LABEL[h.event] ?? h.event}</span>
                  {h.value !== null && h.value !== undefined && <span className="text-ink-muted">→ {displayValue(h.value)}</span>}
                  {h.note && <span className="text-ink-subtle">({h.note})</span>}
                </li>
              ))}
            </ol>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
