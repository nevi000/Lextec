import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Languages, LoaderCircle, PauseCircle, PlayCircle, Smartphone, TriangleAlert } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/queries";
import type { WorkerState } from "./types";

const BASE_KEY = "lextec_bridge_base";

/** Addresses a phone could use to reach this app. Never `localhost`: another device cannot reach that. */
export function baseOptions(s: WorkerState): { bases: string[]; fixed: boolean } {
  if (s.public_base_url) return { bases: [s.public_base_url.replace(/\/$/, "")], fixed: true }; // BRIDGE_PUBLIC_BASE_URL
  const { hostname, port, protocol, origin } = window.location;
  const local = ["localhost", "127.0.0.1", "[::1]", "::1"].includes(hostname);
  const bases = local ? [] : [origin]; // opened via a network address: that address is known to work from here
  for (const ip of s.lan_candidates ?? []) bases.push(`${protocol}//${ip}${port ? `:${port}` : ""}`);
  return { bases: [...new Set(bases)], fixed: false };
}

type Probe = "checking" | "ok" | "fail";

/** Does something answer on this address? (From this computer: proves the server listens on the network adapter,
 *  not that the firewall lets the phone in; that is confirmed when the phone actually connects.) */
function useProbe(base: string | null): Probe {
  const [state, setState] = useState<Probe>("checking");
  useEffect(() => {
    if (!base) return;
    setState("checking");
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 4000);
    fetch(`${base}/api/health`, { mode: "no-cors", signal: ctl.signal, cache: "no-store" })
      .then(() => setState("ok"))
      .catch(() => setState("fail"))
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      ctl.abort();
    };
  }, [base]);
  return state;
}

function Qr({ url }: { url: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    QRCode.toDataURL(url, { margin: 1, width: 208, errorCorrectionLevel: "M" })
      .then((d) => live && setSrc(d))
      .catch(() => live && setSrc(null));
    return () => {
      live = false;
    };
  }, [url]);
  return src ? (
    <img src={src} width={208} height={208} alt="QR-Code zum Verbinden des Smartphones" className="rounded-md border border-line bg-white" />
  ) : (
    <div className="grid size-52 place-items-center rounded-md border border-line bg-sunken text-ink-subtle">
      <LoaderCircle className="size-5 motion-safe:animate-spin" aria-hidden />
    </div>
  );
}

/**
 * Sprachbrücke in phase 2: ONE QR per case, then the phone follows the engine's current question on its own.
 * The social worker stays in control: phone answers are proposals that she accepts, corrects, re-asks or skips.
 */
export function BridgePanel({ caseId, disabled, onCaseChanged }: { caseId: string; disabled: boolean; onCaseChanged: () => void }) {
  const qc = useQueryClient();
  const key = ["bridge", caseId];
  const q = useQuery({
    queryKey: key,
    queryFn: () => api.bridge.get(caseId),
    refetchInterval: (query) => (query.state.data?.active ? 2000 : false),
    enabled: !disabled,
  });
  const s = q.data;
  const wasActive = useRef(false);
  const [endedNote, setEndedNote] = useState(false);
  useEffect(() => {
    if (s?.active) {
      wasActive.current = true;
      setEndedNote(false);
    } else if (s && wasActive.current) {
      wasActive.current = false;
      setEndedNote(true); // ended (by you, by case closing or by expiry): say so instead of silently resetting
    }
  }, [s]);
  const set = (d: WorkerState) => qc.setQueryData(key, d);
  const useAct = (fn: () => Promise<WorkerState>, after?: () => void) =>
    useMutationFor(fn, (d) => {
      set(d);
      after?.();
    });
  const start = useAct(() => api.bridge.start(caseId));
  const pause = useAct(() => api.bridge.pause(caseId));
  const resume = useAct(() => api.bridge.resume(caseId));
  const end = useAct(() => api.bridge.end(caseId));
  const reask = useAct(() => api.bridge.reask(caseId));
  const skip = useAct(() => api.bridge.skip(caseId), onCaseChanged);
  const retry = useAct(() => api.bridge.retryTranslation(caseId));

  const acceptM = useMutation({
    mutationFn: (body: { corrected_value?: string; corrected_text_de?: string }) => api.bridge.accept(caseId, body),
    onSuccess: (d) => {
      set(d);
      onCaseChanged();
      toast.success("Antwort übernommen");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (disabled || q.isLoading) return null;
  if (q.isError || !s) {
    return (
      <section aria-label="Sprachbrücke" className="rounded-lg border border-line bg-surface p-4 text-[13px] text-ink-muted">
        Die Sprachbrücke ist gerade nicht erreichbar ({errorMessage(q.error)}). Läuft der API-Server mit dem neuesten Stand?
      </section>
    );
  }

  if (!s.active) {
    return (
      <section aria-label="Sprachbrücke" className="rounded-xl border border-dashed border-line-strong bg-surface/60 p-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-brand-100 text-brand-700" aria-hidden>
              <Smartphone className="size-4" />
            </span>
            <div className="min-w-0">
            <h2 className="text-[15px] font-semibold">Sprachbrücke</h2>
            <p className="mt-0.5 text-[13px] text-ink-muted">
              Die ratsuchende Person kann die Fragen auf dem eigenen Smartphone in ihrer Sprache beantworten.
            </p>
            {endedNote && (
              <p className="mt-1 text-[12.5px] text-ink-muted" role="status" data-testid="bridge-ended">
                Sitzung beendet. Das Smartphone kann keine Antworten mehr senden; ein neuer QR-Code startet eine neue Sitzung.
              </p>
            )}
            </div>
          </div>
          <Button variant="secondary" size="sm" loading={start.isPending} onClick={() => start.mutate()}>
            Sprachbrücke aktivieren
          </Button>
        </div>
        <p className="mt-3 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-subtle">
          Es wird nur die jeweils aktuelle Frage übertragen, nie die Fallakte. Fragen und Antworten werden maschinell übersetzt; bei
          rechtlich wichtigen Punkten ersetzt das keine qualifizierte Sprachmittlung.
        </p>
      </section>
    );
  }

  const connected = s.status !== "WAITING_FOR_CONNECTION";
  const link = linkState(s);
  const busy = start.isPending || pause.isPending || resume.isPending || end.isPending;

  return (
    <section aria-label="Sprachbrücke" className="rounded-xl border border-brand-600/25 bg-surface p-4 shadow-card sm:p-5" data-testid="bridge-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold">
            <span className="grid size-7 place-items-center rounded-full bg-brand-100 text-brand-700" aria-hidden>
              <Smartphone className="size-3.5" />
            </span>
            {connected ? "Sprachbrücke verbunden" : "Sprachbrücke wartet auf das Smartphone"}
          </h2>
          {connected && (
            <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-ink-muted" data-testid="bridge-status">
              <Languages className="size-3.5" aria-hidden /> {s.language_name} ·{" "}
              <span data-testid="bridge-link-state" data-state={link.state} className={link.tone}>
                {link.label}
              </span>
              {s.status === "PAUSED" && " · pausiert"}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1">
          {connected &&
            (s.status === "PAUSED" ? (
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => resume.mutate()}>
                <PlayCircle /> Fortsetzen
              </Button>
            ) : (
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => pause.mutate()}>
                <PauseCircle /> Pausieren
              </Button>
            ))}
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => end.mutate()}>
            Sitzung beenden
          </Button>
        </div>
      </div>

      {!connected && s.join_token && <Connect s={s} />}

      {connected && s.question && (
        <div className="mt-3 rounded-md bg-sunken/60 p-3 text-[13px]">
          <p className="text-ink-subtle">Aktuelle Frage auf dem Smartphone</p>
          <p className="mt-0.5 font-medium">{s.question.text_de}</p>
          {s.question.text_translated && (
            <p className="mt-1 text-ink-muted" lang={s.language ?? undefined} dir="auto">
              {s.question.text_translated} <span className="text-[11.5px] text-ink-subtle">(maschinell übersetzt)</span>
            </p>
          )}
          {s.question.translation_status === "PENDING" && (
            <p className="mt-2 flex items-center gap-2 text-ink-muted" role="status" data-testid="bridge-translating">
              <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden /> Die Frage wird übersetzt …
            </p>
          )}
          {s.question.translation_status === "FAILED" && (
            <div role="alert" className="mt-2 space-y-2 text-error-fg" data-testid="bridge-translation-failed" data-code={s.question.translation_error_code ?? ""}>
              <p className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  <strong>Übersetzung fehlgeschlagen.</strong> {s.question.translation_error} Die Frage wird dem Smartphone nicht angezeigt; die
                  Verbindung zum Smartphone ist davon nicht betroffen. Erklären Sie die Frage selbst oder ziehen Sie eine Dolmetschperson bei.
                </span>
              </p>
              <Button variant="secondary" size="sm" loading={retry.isPending} onClick={() => retry.mutate()}>
                Übersetzung erneut versuchen
              </Button>
            </div>
          )}
        </div>
      )}
      {connected && !s.question && s.status !== "PAUSED" && (
        <p className="mt-3 text-[13px] text-ink-muted">Im Moment gibt es keine Frage für das Smartphone.</p>
      )}

      {s.answer && s.question && (
        <AnswerCard
          s={s}
          busy={acceptM.isPending || reask.isPending || skip.isPending}
          onAccept={(b) => acceptM.mutate(b)}
          onReask={() => reask.mutate()}
          onSkip={() => skip.mutate()}
        />
      )}
    </section>
  );
}

function AnswerCard({
  s,
  busy,
  onAccept,
  onReask,
  onSkip,
}: {
  s: WorkerState;
  busy: boolean;
  onAccept: (b: { corrected_value?: string; corrected_text_de?: string }) => void;
  onReask: () => void;
  onSkip: () => void;
}) {
  const a = s.answer!;
  const q = s.question!;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(a.german);
  const [value, setValue] = useState("");
  const isText = a.kind === "text";
  const failed = a.translation_status === "FAILED";
  const structured = q.data_type !== "string";

  function saveCorrection() {
    if (isText || !structured) onAccept({ corrected_text_de: text.trim() });
    else onAccept({ corrected_value: value });
  }

  return (
    <div className="mt-4 rounded-xl border border-brand-600/40 bg-brand-50/70 p-4" data-testid="bridge-answer" role="group" aria-label="Antwort eingegangen">
      <p className="flex items-center gap-1.5 text-[13.5px] font-semibold">
        <Check className="size-4 text-brand-700" aria-hidden /> Antwort eingegangen
        <span className="ml-auto text-[11.5px] font-normal text-ink-subtle">Herkunft: Sprachbrücke · wartet auf Bestätigung</span>
      </p>
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-[13px] sm:grid-cols-[auto_1fr]">
        <dt className="text-ink-subtle">Frage</dt>
        <dd>{q.text_de}</dd>
        <dt className="text-ink-subtle">Antwort im Original</dt>
        <dd lang={a.language} dir="auto" data-testid="bridge-answer-original">
          {a.kind === "unknown" ? "—" : a.original}
        </dd>
        <dt className="text-ink-subtle">Auf Deutsch</dt>
        <dd data-testid="bridge-answer-german">
          {a.kind === "unknown" ? "Weiss nicht" : failed ? <em className="text-error-fg">Übersetzung fehlgeschlagen. Bitte selbst übertragen.</em> : a.german}
          {a.machine_translated && <span className="ml-2 rounded bg-sunken px-1.5 py-0.5 text-[11px] text-ink-muted">maschinell übersetzt, bitte prüfen</span>}
        </dd>
      </dl>

      {editing && (
        <div className="mt-2 space-y-2">
          {isText || !structured ? (
            <Textarea aria-label="Deutsche Fassung korrigieren" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
          ) : q.data_type === "boolean" ? (
            <Select aria-label="Antwort korrigieren" value={value} onChange={(e) => setValue(e.target.value)}>
              <option value="">Bitte wählen</option>
              <option value="true">Ja</option>
              <option value="false">Nein</option>
            </Select>
          ) : q.data_type === "enum" ? (
            <Select aria-label="Antwort korrigieren" value={value} onChange={(e) => setValue(e.target.value)}>
              <option value="">Bitte wählen</option>
              {q.options_de.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          ) : (
            <input
              aria-label="Antwort korrigieren"
              type={q.data_type === "date" ? "date" : "text"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="h-9 w-full rounded-md border border-line-strong bg-surface px-3 text-[13px]"
            />
          )}
          <div className="flex gap-2">
            <Button size="sm" loading={busy} disabled={isText || !structured ? !text.trim() : !value} onClick={saveCorrection}>
              Korrigiert übernehmen
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}

      {!editing && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="primary" loading={busy} disabled={failed && isText} onClick={() => onAccept({})}>
            Antwort übernehmen
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => setEditing(true)}>
            Korrigieren
          </Button>
          <Button size="sm" variant="secondary" disabled={busy} onClick={onReask}>
            Erneut fragen
          </Button>
          <Button size="sm" variant="ghost" disabled={busy} onClick={onSkip}>
            Frage überspringen
          </Button>
        </div>
      )}
    </div>
  );
}

function useMutationFor(fn: () => Promise<WorkerState>, onSuccess: (d: WorkerState) => void) {
  return useMutation({ mutationFn: fn, onSuccess, onError: (e) => toast.error(errorMessage(e)) });
}

function Connect({ s }: { s: WorkerState }) {
  const { bases, fixed } = baseOptions(s);
  const [custom, setCustom] = useState<string>(() => {
    try {
      return localStorage.getItem(BASE_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [picked, setPicked] = useState<string>(bases[0] ?? "");
  const [typing, setTyping] = useState(false);
  const customOk = /^https?:\/\/(\d{1,3}(\.\d{1,3}){3}|[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)(:\d{2,5})?\/?$/.test(custom.trim());
  const base = typing && customOk ? custom.trim().replace(/\/$/, "") : (bases.includes(picked) ? picked : (bases[0] ?? null));
  const probe = useProbe(base);
  const url = base ? `${base}/bridge#t=${s.join_token}` : null;
  const [waited, setWaited] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setWaited(true), 25_000);
    return () => clearTimeout(t);
  }, []);

  function saveCustom(v: string) {
    setCustom(v);
    try {
      localStorage.setItem(BASE_KEY, v);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="mt-3 space-y-3" data-testid="bridge-connect">
      {url ? (
        <div className="flex flex-wrap items-start gap-4">
          <Qr url={url} />
          <div className="min-w-0 flex-1 space-y-2 text-[13px] text-ink-muted">
            <p>Die ratsuchende Person scannt den Code einmal und wählt ihre Sprache. Danach erscheinen alle Fragen automatisch.</p>
            <a href={url} target="_blank" rel="noreferrer" data-testid="bridge-link" className="block break-all text-[12px] text-brand-700 underline">
              {url}
            </a>
            <p className="text-[12px]" role="status" data-testid="bridge-probe">
              {probe === "checking" && "Adresse wird geprüft …"}
              {probe === "ok" && <span className="text-brand-700">Der Server antwortet unter dieser Adresse.</span>}
              {probe === "fail" && <span className="text-error-fg">Unter dieser Adresse antwortet kein Server.</span>}
            </p>
          </div>
        </div>
      ) : (
        <div role="alert" className="rounded-md border border-ask-line bg-ask-bg p-3 text-[13px] text-ask-fg" data-testid="bridge-noaddr">
          Es wurde keine Netzwerkadresse dieses Computers gefunden. Verbinden Sie den Computer mit dem WLAN, starten Sie LexTec mit{" "}
          <code>.\scripts\dev.ps1 -Lan</code> oder tragen Sie die Adresse selbst ein.
        </div>
      )}

      {!fixed && (
        <div className="space-y-1.5 text-[12.5px] text-ink-muted">
          {bases.length > 1 && !typing && (
            <label className="block">
              Netzwerkadresse dieses Computers
              <Select aria-label="Netzwerkadresse dieses Computers" className="mt-1" value={base ?? ""} onChange={(e) => setPicked(e.target.value)}>
                {bases.map((b) => (
                  <option key={b} value={b}>
                    {b.replace(/^https?:\/\//, "")}
                  </option>
                ))}
              </Select>
            </label>
          )}
          {typing || bases.length === 0 ? (
            <input
              aria-label="Eigene Basisadresse"
              placeholder="http://192.168.1.20:5173"
              value={custom}
              onChange={(e) => {
                saveCustom(e.target.value);
                setTyping(true);
              }}
              className="h-8 w-full rounded-md border border-line-strong bg-surface px-2 text-[12px] text-ink"
            />
          ) : (
            <button type="button" className="text-brand-700 underline" onClick={() => setTyping(true)}>
              Andere Adresse eintragen
            </button>
          )}
        </div>
      )}

      {(probe === "fail" || waited) && (
        <details open={probe === "fail"} className="rounded-md bg-sunken/60 p-3 text-[12.5px] text-ink-muted" data-testid="bridge-help">
          <summary className="cursor-pointer font-medium text-ink">Das Smartphone kann die Seite nicht öffnen?</summary>
          <ol className="mt-2 list-decimal space-y-1 ps-5">
            <li>
              LexTec muss für das Netzwerk gestartet sein: <code>.\scripts\dev.ps1 -Lan</code> (ohne diese Option lauscht der Webserver nur auf
              diesem Computer und das Handy erhält «Verbindung abgelehnt»).
            </li>
            <li>Computer und Smartphone müssen im selben WLAN beziehungsweise Hotspot sein.</li>
            <li>
              Die Windows-Firewall muss eingehende Verbindungen auf diesem Port für das aktive Netzwerkprofil erlauben (das Skript zeigt eine
              eng begrenzte Regel an).
            </li>
          </ol>
        </details>
      )}
    </div>
  );
}

type LinkState = { state: "connected" | "interrupted" | "away"; label: string; tone: string };

/** How the phone's heartbeat (its poll) looks from here. Independent of the translation state. */
export function linkState(s: WorkerState): LinkState {
  const age = s.last_seen_seconds;
  if (age !== null && age <= 12) return { state: "connected", label: "Smartphone verbunden", tone: "text-brand-700" };
  if (age !== null && age <= 120) {
    return {
      state: "interrupted",
      label: "Verbindung unterbrochen, Wiederherstellung läuft. Das Smartphone verbindet sich automatisch neu.",
      tone: "text-ask-fg",
    };
  }
  const min = age === null ? null : Math.round(age / 60);
  return {
    state: "away",
    label: `Smartphone seit ${min ?? "?"} Min. nicht erreichbar (Sitzung bleibt gültig, bis sie beendet wird oder abläuft)`,
    tone: "text-error-fg",
  };
}
