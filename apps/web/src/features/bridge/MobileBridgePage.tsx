import { Check, Languages, LoaderCircle, WifiOff } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { isLang, LANGUAGES, T, type Lang } from "./i18n";
import type { MobileQuestion, MobileState } from "./types";

const POLL_MS = 2000;
const REQUEST_TIMEOUT_MS = 8000; // a hanging request must not freeze the poll loop
const RECONNECT_NOTICE_AFTER = 2; // one failed request is not yet «connection lost»
const BACKOFF_MS = [1000, 2000, 4000, 8000]; // bounded exponential backoff while the server is unreachable
const TOKEN_KEY = "lextec_bridge_token";

export class HttpError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

/** Errors that mean «try again» (network, timeout, server hiccup, rate limit) - never «the session is over». */
export const isTransient = (e: unknown) =>
  !(e instanceof HttpError) || e.status === 0 || e.status === 429 || e.status >= 500 || e.status === 408;

async function call<T>(token: string, path: string, body?: unknown): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), REQUEST_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`/api/bridge${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "X-Bridge-Token": token, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctl.signal,
      cache: "no-store",
    });
  } catch {
    throw new HttpError(0, "network");
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let code = "http";
    try {
      code = (await res.json())?.error?.code ?? code;
    } catch {
      /* not json */
    }
    throw new HttpError(res.status, code);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new HttpError(0, "bad_body"); // a truncated response is a transport problem
  }
}

function readToken(): string | null {
  try {
    const m = /(?:^|[#&])t=([A-Za-z0-9_-]+)/.exec(window.location.hash);
    if (m) {
      sessionStorage.setItem(TOKEN_KEY, m[1]!);
      window.history.replaceState(null, "", window.location.pathname); // the key does not stay in the address bar
      return m[1]!;
    }
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

const newRequestId = () => (globalThis.crypto?.randomUUID?.() ?? `r${Date.now()}${Math.random().toString(36).slice(2)}`).replace(/-/g, "");

function browserLang(): Lang {
  const l = (navigator.language ?? "de").slice(0, 2);
  return isLang(l) ? l : "de";
}

const jitter = (ms: number) => ms + Math.floor(Math.random() * 250);

/** Phone side of the Sprachbrücke: a controlled input surface. It only ever sees the current question. */
export function MobileBridgePage() {
  const [token] = useState(readToken);
  const [state, setState] = useState<MobileState | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const [ended, setEnded] = useState<"gone" | "done" | null>(null);
  const [invalidLink, setInvalidLink] = useState(!token);
  const [uiLang, setUiLang] = useState<Lang>(browserLang);
  const wake = useRef<() => void>(() => undefined);

  const apply = useCallback((s: MobileState) => {
    setState(s);
    setReconnecting(false);
    if (isLang(s.language)) setUiLang(s.language);
    if (s.status === "COMPLETED" || s.status === "EXPIRED") setEnded(s.status === "COMPLETED" ? "done" : "gone");
  }, []);

  /** Returns true when the error was a final answer of the server (session over / link invalid). */
  const fatal = useCallback((e: unknown): boolean => {
    if (e instanceof HttpError && e.status === 410) {
      setEnded("gone");
      return true;
    }
    if (e instanceof HttpError && e.status === 401) {
      setInvalidLink(true);
      return true;
    }
    return false;
  }, []);

  // Polling the backend state: both devices only read the same server-side state. One request at a time, a backoff while
  // the server is unreachable, and an immediate refresh when the phone wakes up (screen unlocked, tab visible, network back).
  useEffect(() => {
    if (!token || ended || invalidLink) return;
    let stop = false;
    let running = false;
    let fails = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = (ms: number) => {
      if (timer) clearTimeout(timer);
      if (!stop) timer = setTimeout(() => void tick(), ms);
    };
    const tick = async () => {
      if (running || stop) return;
      running = true;
      try {
        apply(await call<MobileState>(token, "/state"));
        fails = 0;
        schedule(POLL_MS);
      } catch (e) {
        if (fatal(e)) return;
        fails += 1;
        if (fails >= RECONNECT_NOTICE_AFTER) setReconnecting(true);
        schedule(jitter(BACKOFF_MS[Math.min(fails - 1, BACKOFF_MS.length - 1)]!));
      } finally {
        running = false;
      }
    };
    wake.current = () => {
      fails = 0;
      schedule(0);
    };
    const onWake = () => {
      if (document.visibilityState === "visible") wake.current();
    };
    document.addEventListener("visibilitychange", onWake);
    window.addEventListener("online", onWake);
    window.addEventListener("pageshow", onWake);
    window.addEventListener("focus", onWake);
    void tick();
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onWake);
      window.removeEventListener("online", onWake);
      window.removeEventListener("pageshow", onWake);
      window.removeEventListener("focus", onWake);
    };
  }, [token, ended, invalidLink, apply, fatal]);

  const t = T[uiLang];
  const rtl = state?.rtl ?? uiLang === "ar";

  return (
    <div dir={rtl ? "rtl" : "ltr"} lang={uiLang} className="min-h-dvh bg-canvas text-ink" data-testid="bridge-mobile">
      <header className="bg-brand-900 px-5 py-4 text-white">
        <img src="/brand/lextec-logo-white.png" alt="LexTec" width={1888} height={446} className="h-7 w-auto" />
      </header>
      <main className="mx-auto flex max-w-md flex-col gap-5 px-5 pb-10 pt-6">
        {reconnecting && !ended && (
          <p role="status" className="flex items-center gap-2 rounded-lg border border-ask-line bg-ask-bg px-3 py-2 text-[14px] text-ask-fg" data-testid="bridge-offline">
            <WifiOff className="size-4 shrink-0" aria-hidden /> {t.connectionLost}
          </p>
        )}
        {invalidLink ? (
          <Message text={t.noLink} />
        ) : ended ? (
          <Message text={ended === "done" ? t.completed : t.ended} done />
        ) : !state ? (
          <Message text={t.retrying} spin />
        ) : state.language === null ? (
          <Welcome
            uiLang={uiLang}
            onPick={async (code) => {
              setUiLang(code);
              try {
                apply(await call<MobileState>(token!, "/language", { language: code }));
              } catch (e) {
                if (!fatal(e)) setReconnecting(true);
              }
            }}
          />
        ) : (
          <Session
            token={token!}
            state={state}
            onState={apply}
            onFatal={fatal}
            onTransient={() => {
              setReconnecting(true);
              wake.current();
            }}
            t={t}
          />
        )}
      </main>
    </div>
  );
}

function Message({ text, spin, done }: { text: string; spin?: boolean; done?: boolean }) {
  return (
    <div role="status" className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface p-8 text-center shadow-card">
      {spin ? <LoaderCircle className="size-6 motion-safe:animate-spin text-brand-600" aria-hidden /> : null}
      {done ? <Check className="size-7 text-brand-600" aria-hidden /> : null}
      <p className="text-[17px] leading-snug">{text}</p>
    </div>
  );
}

function Welcome({ uiLang, onPick }: { uiLang: Lang; onPick: (l: Lang) => void }) {
  const t = T[uiLang];
  return (
    <section aria-labelledby="welcome-h" className="space-y-5">
      <div>
        <h1 id="welcome-h" className="text-[22px] font-semibold leading-tight">
          {t.chooseLanguage}
        </h1>
        <p className="mt-2 text-[15px] text-ink-muted">{t.intro}</p>
        <p className="mt-1 text-[14px] text-ink-muted">{t.workerGuides}</p>
      </div>
      <ul className="space-y-2.5">
        {LANGUAGES.map((l) => (
          <li key={l.code}>
            <button
              type="button"
              onClick={() => onPick(l.code)}
              className="flex min-h-16 w-full items-center gap-3 rounded-2xl border border-line-strong bg-surface px-5 text-start text-[19px] font-medium shadow-card transition-colors active:bg-brand-50"
              lang={l.code}
            >
              <Languages className="size-5 text-brand-600" aria-hidden /> {l.name}
            </button>
          </li>
        ))}
      </ul>
      <p className="text-[13px] leading-relaxed text-ink-subtle">{t.privacy}</p>
    </section>
  );
}

function Session({
  token,
  state,
  onState,
  onFatal,
  onTransient,
  t,
}: {
  token: string;
  state: MobileState;
  onState: (s: MobileState) => void;
  onFatal: (e: unknown) => boolean;
  onTransient: () => void;
  t: (typeof T)[Lang];
}) {
  const q = state.question;
  return (
    <div className="space-y-5">
      <p className="flex items-center gap-2 text-[14px] font-medium text-brand-700">
        <span className="size-2 rounded-full bg-brand-600" aria-hidden /> {t.connected}
      </p>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={q?.instance_id ?? state.status}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          {state.status === "PAUSED" ? (
            <Message text={t.paused} />
          ) : state.status === "AWAITING_WORKER_REVIEW" ? (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface p-8 text-center shadow-card" role="status">
              <Check className="size-7 text-brand-600" aria-hidden />
              <p className="text-[19px] font-semibold">{t.sent}</p>
              <p className="text-[15px] text-ink-muted">{t.reviewing}</p>
            </div>
          ) : state.notice === "translation_pending" ? (
            <Message text={t.preparing} spin />
          ) : state.notice === "translation_failed" ? (
            <div role="alert" className="rounded-xl border border-ask-line bg-ask-bg p-5 text-[16px] text-ask-fg">
              {t.translationFailed}
            </div>
          ) : q ? (
            <QuestionView key={q.instance_id} q={q} token={token} onState={onState} onFatal={onFatal} onTransient={onTransient} t={t} />
          ) : (
            <Message text={t.waitingQuestion} spin />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function QuestionView({
  q,
  token,
  onState,
  onFatal,
  onTransient,
  t,
}: {
  q: MobileQuestion;
  token: string;
  onState: (s: MobileState) => void;
  onFatal: (e: unknown) => boolean;
  onTransient: () => void;
  t: (typeof T)[Lang];
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const rid = useRef<string>(newRequestId()); // one id per attempt: a retry after a lost connection is not processed twice
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  /** Sends the answer; after a transport error it keeps retrying with the same request id (server-side idempotent) until
   *  the server answers or the question is gone. The poll shows «Antwort gesendet» as soon as the server has it. */
  async function submit(kind: "value" | "unknown", value?: string) {
    if (busy) return;
    setBusy(true);
    setProblem(null);
    for (let attempt = 0; attempt < 6 && alive.current; attempt++) {
      try {
        onState(await call<MobileState>(token, "/answer", { instance_id: q.instance_id, request_id: rid.current, kind, value }));
        if (alive.current) setBusy(false);
        return;
      } catch (e) {
        if (onFatal(e)) return;
        if (e instanceof HttpError && e.status === 409) {
          setProblem(t.stale);
          break;
        }
        if (e instanceof HttpError && e.status === 400) {
          setProblem(t.invalid);
          break;
        }
        if (!isTransient(e)) break;
        onTransient();
        await new Promise((r) => setTimeout(r, jitter(BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]!)));
      }
    }
    if (alive.current) setBusy(false);
  }

  const big = "flex min-h-14 w-full items-center justify-center rounded-xl border px-4 text-[18px] font-semibold transition-colors disabled:opacity-50";
  const primary = cn(big, "border-brand-600 bg-brand-600 text-white active:bg-brand-700");
  const secondary = cn(big, "border-line-strong bg-surface active:bg-brand-50");

  return (
    <section aria-labelledby="q-h" className="space-y-6 rounded-2xl border border-line bg-surface p-6 shadow-raised">
      <h1 id="q-h" className="font-display text-[24px] font-semibold leading-snug tracking-tight" data-testid="bridge-question">
        {q.text}
      </h1>
      {q.why && (
        <details className="text-[14px] text-ink-muted">
          <summary className="cursor-pointer font-medium text-brand-700">{t.why}</summary>
          <p className="mt-2 leading-relaxed">{q.why}</p>
        </details>
      )}

      {q.data_type === "boolean" && (
        <div className="grid grid-cols-2 gap-3">
          <button type="button" className={primary} disabled={busy} onClick={() => void submit("value", "true")}>
            {t.yes}
          </button>
          <button type="button" className={secondary} disabled={busy} onClick={() => void submit("value", "false")}>
            {t.no}
          </button>
        </div>
      )}
      {q.data_type === "enum" && (
        <div className="space-y-2.5">
          {q.options.map((o) => (
            <button key={o.value} type="button" className={cn(secondary, "justify-start text-start")} disabled={busy} onClick={() => void submit("value", o.value)}>
              {o.label}
            </button>
          ))}
        </div>
      )}
      {(q.data_type === "date" || q.data_type === "integer" || q.data_type === "string") && (
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) void submit("value", text.trim());
          }}
        >
          <label className="sr-only" htmlFor="bridge-answer">
            {t.yourAnswer}
          </label>
          {q.data_type === "string" ? (
            <textarea
              id="bridge-answer"
              rows={4}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full rounded-xl border border-line-strong bg-surface p-3 text-[18px] leading-relaxed"
              placeholder={t.yourAnswer}
            />
          ) : (
            <input
              id="bridge-answer"
              type={q.data_type === "date" ? "date" : "text"}
              inputMode={q.data_type === "integer" ? "numeric" : undefined}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="h-14 w-full rounded-xl border border-line-strong bg-surface px-3 text-[18px]"
              placeholder={t.yourAnswer}
            />
          )}
          <button type="submit" className={primary} disabled={busy || !text.trim()}>
            {busy ? t.sending : t.send}
          </button>
        </form>
      )}
      <button type="button" className="min-h-12 w-full rounded-xl text-[16px] font-medium text-ink-muted underline-offset-4 hover:underline" disabled={busy} onClick={() => void submit("unknown")}>
        {t.unknown}
      </button>
      {problem && (
        <p role="alert" className="text-[14px] text-escalate-fg">
          {problem}
        </p>
      )}
    </section>
  );
}
