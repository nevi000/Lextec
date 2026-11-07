import { useMutation } from "@tanstack/react-query";
import { ChevronDown, ShieldAlert, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ContactActions, OrgCard } from "@/components/shared/OrgCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { errorMessage, useInvalidateCase } from "@/lib/queries";
import type { SafetyAssessment } from "@/types";

/** Who must look at it, in plain words. The wording comes from the knowledge base; this is only the frame. */
function Acknowledge({ caseId, safety }: { caseId: string; safety: SafetyAssessment }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const invalidate = useInvalidateCase(caseId);
  const open_events = safety.signals.filter((s) => !s.acknowledged && s.certainty === "ACUTE");
  const done = safety.signals.filter((s) => s.acknowledged);
  const mutation = useMutation({
    mutationFn: async () => {
      for (const s of open_events) if (s.id) await api.acknowledgeSafety(caseId, s.id, note.trim());
    },
    onSuccess: () => {
      void invalidate();
      setOpen(false);
      setNote("");
      toast.success("Dokumentiert. Der Sicherheitshinweis bleibt sichtbar.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="mt-5 border-t border-line pt-3 text-[13px]">
      {done.length > 0 && (
        <p className="mb-2 text-ink-muted">
          Von Ihnen als bearbeitet dokumentiert: «{done[done.length - 1]?.acknowledged_note}». Das ist keine Entwarnung; die Situation wird weiter angezeigt.
        </p>
      )}
      {open_events.length > 0 &&
        (open ? (
          <div className="space-y-2">
            <label htmlFor="safety-note" className="block font-medium">
              Was wurde veranlasst? (Dokumentation, keine Entwarnung)
            </label>
            <Textarea id="safety-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="z. B. Rettungsdienst 144 gerufen, Klientin nicht allein gelassen" />
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" loading={mutation.isPending} disabled={note.trim().length < 3} onClick={() => mutation.mutate()}>
                Als bearbeitet dokumentieren
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
                Abbrechen
              </Button>
            </div>
          </div>
        ) : (
          <button type="button" className="font-medium text-brand-700 hover:underline" onClick={() => setOpen(true)}>
            Als bearbeitet dokumentieren
          </button>
        ))}
    </div>
  );
}

/**
 * Emergency mode for IMMEDIATE_SAFETY_RESPONSE: the first thing on the page, never collapsed, never a small badge.
 * Phone buttons only open the device's phone app; nothing is dialled, logged or reported as a completed call.
 */
export function SafetyEmergency({ caseId, safety }: { caseId: string; safety: SafetyAssessment }) {
  return (
    <section
      role="alert"
      aria-labelledby="safety-headline"
      data-testid="safety-emergency"
      className="rounded-lg border-2 border-escalate-solid bg-surface p-5 shadow-card sm:p-6"
    >
      <div className="flex items-start gap-3">
        <TriangleAlert className="mt-1 size-6 shrink-0 text-escalate-solid" aria-hidden />
        <div className="min-w-0">
          <h2 id="safety-headline" className="text-[22px] font-bold leading-snug text-escalate-fg">
            {safety.headline_de}
          </h2>
          {safety.explanation_de && <p className="mt-2 text-[14.5px] leading-relaxed">{safety.explanation_de}</p>}
          <p className="mt-2 text-[12.5px] text-ink-muted">
            Erkannt: {[...new Set(safety.signals.filter((s) => s.certainty === "ACUTE" && safety.immediate_categories.includes(s.category)).map((s) => s.label_de))].join(", ")}
          </p>
        </div>
      </div>

      <div className="mt-5" data-testid="emergency-contacts">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Sofort Hilfe holen</p>
        <ul className="mt-2 grid gap-3 sm:grid-cols-2">
          {safety.contacts_immediate.map((c) => (
            <li key={c.id} className="rounded-md border border-escalate-line bg-escalate-bg/40 p-3">
              <p className="text-[14px] font-semibold">{c.label}</p>
              <p className="text-[12.5px] text-ink-muted">Notruf, rund um die Uhr</p>
              <div className="mt-2">
                <ContactActions org={c} emergency />
              </div>
            </li>
          ))}
        </ul>
      </div>

      {safety.steps_de.length > 0 && (
        <div className="mt-5">
          <p className="text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Was Sie jetzt tun können</p>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-[14px]">
            {safety.steps_de.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
          <p className="mt-2 text-[12px] text-ink-subtle">Kurzhinweise, keine Diagnose und keine Garantie. Die Texte sind vor produktivem Einsatz fachlich zu prüfen.</p>
        </div>
      )}

      {safety.contacts_counselling.length > 0 && (
        <div className="mt-5">
          <p className="text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Ergänzende Beratung (keine Notrufnummern)</p>
          <ul className="mt-2 grid gap-3 sm:grid-cols-2">
            {safety.contacts_counselling.map((c) => (
              <li key={c.id}>
                <OrgCard org={c} compact />
              </li>
            ))}
          </ul>
        </div>
      )}

      {safety.contacts_further.length > 0 && (
        <details className="group mt-4 border-t border-line pt-3">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-[12.5px] font-medium text-brand-700 hover:underline">
            <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
            Weiterführende Stellen nach der akuten Situation
          </summary>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {safety.contacts_further.map((c) => (
              <li key={c.id}>
                <OrgCard org={c} compact />
              </li>
            ))}
          </ul>
        </details>
      )}

      <Acknowledge caseId={caseId} safety={safety} />
    </section>
  );
}

/** Non-immediate safety hints (human check needed / unclear): visible, calm, contacts one click away. */
export function SafetyNotice({ caseId, safety }: { caseId: string; safety: SafetyAssessment }) {
  const contacts = [...safety.contacts_immediate, ...safety.contacts_counselling, ...safety.contacts_further];
  return (
    <section role="status" aria-label="Sicherheitshinweis" data-testid="safety-notice" className="rounded-lg border border-ask-line border-l-4 border-l-ask-solid bg-surface p-4 sm:p-5">
      <h2 className="flex items-center gap-2 text-[16px] font-semibold">
        <ShieldAlert className="size-5 text-ask-solid" aria-hidden /> {safety.headline_de}
      </h2>
      {safety.explanation_de && <p className="mt-1.5 text-[13.5px] text-ink-muted">{safety.explanation_de}</p>}
      {safety.state === "HUMAN_CHECK" && contacts.length > 0 && (
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {contacts.slice(0, 4).map((c) => (
            <li key={c.id}>
              <OrgCard org={c} compact />
            </li>
          ))}
        </ul>
      )}
      <Acknowledge caseId={caseId} safety={safety} />
    </section>
  );
}
