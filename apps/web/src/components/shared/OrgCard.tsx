import { ExternalLink, Mail, Phone, ShieldAlert } from "lucide-react";
import type { ReferralCard } from "@/types";
import { Badge } from "./badges";

const HTTP = /^https?:\/\/[^\s"'<>]+$/;
const MAIL = /^[^@\s<>"']+@[^@\s<>"']+\.[A-Za-z]{2,}$/;
const TEL = /^\+?\d{3,15}$/;

const btn =
  "inline-flex min-h-9 items-center gap-1.5 rounded-md border border-line-strong bg-surface px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-sunken";
const btnEmergency =
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-md bg-escalate-solid px-5 py-2.5 text-[16px] font-semibold text-white hover:opacity-90";

/** Phone / website / e-mail actions. Only values that pass a strict scheme check become links. */
export function ContactActions({ org, emergency = false }: { org: ReferralCard; emergency?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {org.phones.map((p) =>
        p.tel && TEL.test(p.tel) ? (
          <a key={p.display} href={`tel:${p.tel}`} className={emergency ? btnEmergency : btn} aria-label={`${p.display.split(" (")[0]} anrufen, ${org.label}`}>
            <Phone className="size-4" aria-hidden /> {p.display.split(" (")[0]} anrufen
          </a>
        ) : (
          <span key={p.display} className="text-[13px] text-ink-muted">
            {p.label_de}: {p.display}
          </span>
        ),
      )}
      {!emergency && org.web && HTTP.test(org.web) && (
        <a href={org.web} target="_blank" rel="noreferrer noopener" className={btn}>
          <ExternalLink className="size-4" aria-hidden /> Website öffnen
        </a>
      )}
      {!emergency && org.email && MAIL.test(org.email) && (
        <a href={`mailto:${org.email}`} className={btn}>
          <Mail className="size-4" aria-hidden /> E-Mail schreiben
        </a>
      )}
    </div>
  );
}

const QUALITY_TONE = { OFFICIAL: "brand", NATIONAL: "brand", DIRECTORY: "ask", UNDOCUMENTED: "unverified" } as const;

/**
 * One organisation from the knowledge base. Shows what the social worker needs: who, how to reach, whether it fits
 * and how reliable the contact data is. Nothing here is hard-coded; protected addresses never arrive from the API.
 */
export function OrgCard({ org, compact = false }: { org: ReferralCard; compact?: boolean }) {
  const phone24 = org.phones.some((p) => p.label_de.includes("24 h"));
  return (
    <article className="rounded-md border border-line bg-surface p-4" aria-label={org.label} data-testid="org-card">
      <h3 className="text-[15px] font-semibold leading-snug">{org.label}</h3>
      {org.reason_de && !compact && <p className="mt-0.5 text-[12.5px] text-ink-subtle">{org.reason_de}</p>}
      {org.for_audience_de && <p className="mt-0.5 text-[12.5px] text-ink-muted">{org.for_audience_de}</p>}
      {org.not_emergency_number && (
        <p className="mt-1 inline-flex items-center gap-1 text-[12.5px] font-medium text-ask-fg">
          <ShieldAlert className="size-3.5" aria-hidden /> Beratung, keine Notrufnummer
        </p>
      )}
      {org.availability && <p className="mt-1 text-[12.5px] font-medium text-ask-fg">{org.availability}</p>}
      <div className="mt-3">
        <ContactActions org={org} />
      </div>
      <dl className="mt-3 grid gap-x-4 gap-y-1 text-[12.5px] text-ink-muted sm:grid-cols-[auto_1fr]">
        {org.address && (
          <>
            <dt className="text-ink-subtle">Adresse</dt>
            <dd>{org.address}</dd>
          </>
        )}
        {org.address_protected && (
          <>
            <dt className="text-ink-subtle">Adresse</dt>
            <dd>aus Schutzgründen nicht angegeben, bitte telefonisch kontaktieren</dd>
          </>
        )}
        {org.hours && !compact && (
          <>
            <dt className="text-ink-subtle">Öffnungszeiten</dt>
            <dd>{org.hours}</dd>
          </>
        )}
        {phone24 && !org.hours && (
          <>
            <dt className="text-ink-subtle">Erreichbarkeit</dt>
            <dd>Telefon rund um die Uhr (laut Wissensbasis)</dd>
          </>
        )}
        {org.costs && !compact && (
          <>
            <dt className="text-ink-subtle">Kosten</dt>
            <dd>{org.costs}</dd>
          </>
        )}
        {org.access && !compact && (
          <>
            <dt className="text-ink-subtle">Zugang</dt>
            <dd>{org.access}</dd>
          </>
        )}
      </dl>
      <p className="mt-3 flex flex-wrap items-center gap-1.5 text-[11.5px] text-ink-subtle">
        <Badge tone={QUALITY_TONE[org.quality]}>{org.quality === "UNDOCUMENTED" ? "Kontaktdaten nicht belegt" : org.quality === "DIRECTORY" ? "Fachverzeichnis" : "Offizielle Quelle"}</Badge>
        {!org.verified && <Badge tone="unverified">Zuständigkeit noch nicht geprüft</Badge>}
        <span>{org.quality_label_de}</span>
      </p>
    </article>
  );
}
