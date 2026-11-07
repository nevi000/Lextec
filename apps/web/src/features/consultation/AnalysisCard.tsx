import { Check, LoaderCircle } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";

const STEPS = [
  "Fallbeschreibung vorbereiten",
  "Rechtsprobleme und Informationen erkennen",
  "Nächste Schritte vorbereiten",
] as const;

const SLOW_AFTER_MS = 20_000;

/**
 * Shown under the (still visible, read-only) description while the analysis request runs.
 *
 * Honest by design: the only events we really know are «request handed to the server» (step 1 done) and
 * «answer received» (the card disappears). While the server works there is no intermediate state, so step 2 is
 * shown as running with an indeterminate bar. No percentages, no timer that marks steps as finished.
 */
export function AnalysisCard() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <section
      role="status"
      aria-live="polite"
      aria-label="Fall wird analysiert"
      data-testid="analysis-card"
      className="mt-4 overflow-hidden rounded-lg border border-line bg-sunken/60 p-4"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-brand-600/10 text-brand-700">
          <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden />
        </span>
        <div className="min-w-0">
          <h3 className="text-[14.5px] font-semibold">Fall wird analysiert</h3>
          <p className="text-[13px] text-ink-muted">Wir ordnen die Angaben ein und bereiten die nächsten Schritte vor.</p>
        </div>
      </div>

      <div className="mt-3 h-1 overflow-hidden rounded-full bg-line" aria-hidden>
        <motion.div
          className="h-full w-1/3 rounded-full bg-brand-600"
          animate={{ x: ["-100%", "300%"] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <ol className="mt-3 space-y-1.5 text-[13px]">
        {STEPS.map((label, i) => {
          const state = i === 0 ? "done" : i === 1 ? "active" : "waiting";
          return (
            <li
              key={label}
              data-state={state}
              className={state === "waiting" ? "flex items-center gap-2 text-ink-subtle" : "flex items-center gap-2 text-ink"}
            >
              {state === "done" ? (
                <Check className="size-4 text-brand-700" aria-hidden />
              ) : state === "active" ? (
                <span className="relative grid size-4 place-items-center" aria-hidden>
                  <span className="absolute size-2.5 rounded-full bg-brand-600/30 motion-safe:animate-ping" />
                  <span className="size-2 rounded-full bg-brand-600" />
                </span>
              ) : (
                <span className="grid size-4 place-items-center" aria-hidden>
                  <span className="size-1.5 rounded-full bg-line-strong" />
                </span>
              )}
              <span>{label}</span>
              <span className="sr-only">
                {state === "done" ? " (erledigt)" : state === "active" ? " (läuft)" : " (folgt)"}
              </span>
            </li>
          );
        })}
      </ol>

      {slow && (
        <p className="mt-3 text-[12.5px] text-ink-muted" data-testid="analysis-slow">
          Die Analyse dauert etwas länger als gewöhnlich. Ihre Eingaben bleiben erhalten.
        </p>
      )}
    </section>
  );
}
