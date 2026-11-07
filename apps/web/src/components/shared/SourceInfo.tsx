import { ExternalLink } from "lucide-react";
import { useSources } from "@/lib/queries";
import type { SourceRef } from "@/types";
import { Badge } from "./badges";

type Fedlex = NonNullable<SourceRef["fedlex"]>;
type Tone = "neutral" | "brand" | "unverified" | "ask" | "error";

const isRetrieved = (f: Fedlex) => f.retrieval_status === "RETRIEVED" || f.retrieval_status === "RETRIEVED_STALE";

function retrievalTone(f: Fedlex): Tone {
  if (f.origin === "FIXTURE") return "ask";
  switch (f.retrieval_status) {
    case "RETRIEVED":
      return "brand";
    case "RETRIEVED_STALE":
      return "ask";
    case "NOT_APPLICABLE":
    case "NOT_RETRIEVED":
      return "unverified";
    default:
      return "error";
  }
}

/** Retrieval, wording and interpretation are three SEPARATE statuses; none of them is a legal conclusion. */
export function FedlexBadges({ info }: { info: Fedlex }) {
  if (info.retrieval_status === "NOT_APPLICABLE") return null;
  return (
    <>
      <Badge tone={retrievalTone(info)} title="Abruf bei Fedlex (amtliche Rechtssammlung)">
        {info.retrieval_label_de}
      </Badge>
      {isRetrieved(info) && (
        <Badge
          tone={info.wording_status === "MISMATCH" ? "error" : info.wording_status === "MATCHED" ? "brand" : "unverified"}
          title="Vergleich des Zitats in der Wissensbasis mit dem amtlichen Text"
        >
          {info.wording_label_de}
        </Badge>
      )}
      <Badge tone="unverified" title="Ob die rechtliche Auslegung geprüft ist, sagt der Textabruf nicht aus">
        {info.interpretation_label_de}
      </Badge>
    </>
  );
}

const linkCls = "inline-flex items-center gap-1 text-brand-700 underline";

/** Version, validity, retrieval time, official links and the retrieved wording. */
export function FedlexDetails({ info }: { info: Fedlex }) {
  if (!isRetrieved(info)) {
    return info.message ? <p className="mt-1.5 text-[12px] text-ink-subtle">{info.message}</p> : null;
  }
  return (
    <div className="mt-2 rounded-md bg-sunken p-2.5 text-[12px] text-ink-muted" data-testid="fedlex-details">
      {info.origin === "FIXTURE" && (
        <p className="mb-1 font-medium text-ask-fg">Testdaten (Fixture): kein Abruf bei Fedlex, nur für Tests.</p>
      )}
      <p>
        <strong>{info.article_label}</strong>
        {info.heading ? ` – ${info.heading}` : ""} · {info.law_abbreviation ?? "Erlass"}
      </p>
      <p className="mt-0.5">
        Fassung {info.version_identifier}, gültig ab {info.valid_from}
        {info.valid_to ? ` bis ${info.valid_to}` : ""}
        {info.version_covers_reference === false && " · deckt den Stichtag nicht ab"}
        {info.retrieved_at && ` · abgerufen ${info.retrieved_at.replace("T", " ").slice(0, 16)}`}
        {info.cache_age_days != null && info.cache_age_days > 0 && ` (vor ${info.cache_age_days} Tagen geprüft)`}
      </p>
      {info.official_text && <p className="mt-1.5 text-ink">{info.official_text}</p>}
      <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
        {info.official_article_url && (
          <a className={linkCls} href={info.official_article_url} target="_blank" rel="noreferrer">
            Artikel in Fedlex <ExternalLink className="size-3" aria-hidden />
          </a>
        )}
        {info.official_document_url && (
          <a className={linkCls} href={info.official_document_url} target="_blank" rel="noreferrer">
            Amtliches XML <ExternalLink className="size-3" aria-hidden />
          </a>
        )}
        {info.official_eli_uri && (
          <a className={linkCls} href={info.official_eli_uri} target="_blank" rel="noreferrer">
            ELI <ExternalLink className="size-3" aria-hidden />
          </a>
        )}
      </p>
      {info.article_url_note && <p className="mt-1 text-[11px] text-ink-subtle">{info.article_url_note}</p>}
    </div>
  );
}

/** Compact source chip for the case workspace and the briefing review points. */
export function SourceChip({ id }: { id: string }) {
  const { ref } = useSources();
  const s = ref(id);
  const f = s?.fedlex;
  const label = s?.citation ?? s?.title_de ?? id;
  const retrieved = !!f && isRetrieved(f);
  const tip =
    retrieved && f
      ? `${f.retrieval_label_de} · Fassung ${f.version_identifier} · ${f.wording_label_de} · ${f.interpretation_label_de}`
      : "Quelle laut Law-Dossier; Text noch nicht von Fedlex abgerufen";
  const badge = (
    <Badge tone={f ? retrievalTone(f) : "unverified"} title={tip}>
      {label}
      {retrieved && f ? (f.origin === "FEDLEX" ? " · Fedlex" : " · Test") : ""}
    </Badge>
  );
  return retrieved && f?.official_article_url ? (
    <a href={f.official_article_url} target="_blank" rel="noreferrer" aria-label={`${label} bei Fedlex öffnen`}>
      {badge}
    </a>
  ) : (
    badge
  );
}
