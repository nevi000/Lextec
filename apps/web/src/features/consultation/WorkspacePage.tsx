import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, MessageSquarePlus, RefreshCw, TriangleAlert } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";
import { Badge } from "@/components/shared/badges";
import { SafetyEmergency, SafetyNotice } from "./SafetyPanel";
import { Rise } from "@/components/shared/motion";
import { ErrorState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "@/components/ui/dialog";
import { FieldError, Label, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoGuide } from "@/features/demo/DemoGuide";
import { DEMO_TITLE } from "@/features/demo/demoScenario";
import { api } from "@/lib/api";
import { caseStatus, currentPhase } from "@/lib/caseStatus";
import {
  errorMessage,
  useBriefings,
  useCase,
  useDecisions,
  useFacts,
  useInvalidateCase,
  useMessages,
} from "@/lib/queries";
import type { FactView } from "@/types";
import { CasePanel } from "./CasePanel";
import { CaseSummary } from "./CaseSummary";
import { BridgePanel } from "@/features/bridge/BridgePanel";
import { Composer } from "./Composer";
import { DeferDialog } from "./DeferDialog";
import { FactDialog } from "./FactDialog";
import { NextActionCard } from "./NextActionCard";
import { PhaseStepper } from "./PhaseStepper";
import { StatementsPanel } from "./StatementsPanel";
import { Timeline } from "./Timeline";

const completeSchema = z.object({ note: z.string().trim().min(3, "Bitte kurz festhalten, wie die Übergabe erfolgt ist.").max(1000) });

/**
 * Case workspace in three orientation phases (Situation erfassen → Fragen klären → Nächste Schritte).
 * The phase is derived from backend state and never blocks anything: an escalation shows up immediately.
 * All logic stays in the backend; this component only presents it.
 */
export function WorkspacePage() {
  const { caseId = "" } = useParams();
  const navigate = useNavigate();
  const caseQ = useCase(caseId);
  const messagesQ = useMessages(caseId);
  const factsQ = useFacts(caseId);
  const decisionsQ = useDecisions(caseId);
  const briefingsQ = useBriefings(caseId);
  const invalidate = useInvalidateCase(caseId);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const [infoOpen, setInfoOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [openFact, setOpenFact] = useState<FactView | null>(null);
  const [defer, setDefer] = useState<{ factId: string; label: string } | null>(null);
  const [closeOpen, setCloseOpen] = useState(false);
  const [handoverOpen, setHandoverOpen] = useState(false);
  const [completeOpen, setCompleteOpen] = useState(false);

  const post = useMutation({
    mutationFn: (b: Parameters<typeof api.postMessage>[1]) => api.postMessage(caseId, b),
    onSuccess: (r) => {
      void invalidate();
      if (r.analysis.status === "FAILED") {
        toast.error(r.analysis.error_message ?? "Analyse fehlgeschlagen.", {
          description: "Ihre Eingabe wurde gespeichert. Sie können die Analyse erneut starten.",
        });
      } else {
        toast.success("Erfasst und analysiert");
        r.analysis.warnings.forEach((w) => toast.message("Hinweis zur KI-Auswertung", { description: w }));
      }
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const unknown = useMutation({
    mutationFn: (factId: string) =>
      api.postMessage(caseId, { content: "Weiss nicht.", answers_fact_id: factId, unknown: true }),
    onSuccess: () => {
      void invalidate();
      toast.success("Als «gefragt, aber unbekannt» erfasst. Das System fragt nicht erneut.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  // Optional questions are skipped via the normal deferral (with an automatic, honest reason), never silently dropped.
  const skip = useMutation({
    mutationFn: (factId: string) => api.deferFact(caseId, factId, "Bei der Fallaufnahme übersprungen"),
    onSuccess: () => void invalidate(),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const reanalyze = useMutation({
    mutationFn: () => api.analyze(caseId),
    onSuccess: (d) => {
      void invalidate();
      if (d.analysis.status === "OK") toast.success("Analyse abgeschlossen");
      else toast.error(d.analysis.error_message ?? "Analyse weiterhin fehlgeschlagen.");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const setStatus = useMutation({
    mutationFn: (status: "OPEN" | "CLOSED") => api.patchCase(caseId, { status }),
    onSuccess: (d) => {
      void invalidate();
      setCloseOpen(false);
      toast.success(d.status === "CLOSED" ? "Fall abgeschlossen" : "Fall wieder geöffnet");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const request = useMutation({
    mutationFn: () => api.requestHandover(caseId),
    onSuccess: () => {
      void invalidate();
      setHandoverOpen(false);
      toast.success("Übergabe als angefragt markiert");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const complete = useMutation({
    mutationFn: (note: string) => api.completeHandover(caseId, note),
    onSuccess: () => {
      void invalidate();
      setCompleteOpen(false);
      toast.success("Übergabe bestätigt");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const briefing = useMutation({
    mutationFn: () => api.createBriefing(caseId),
    onSuccess: (b) => {
      void invalidate();
      navigate(`/cases/${caseId}/briefing/${b.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const completeForm = useForm<z.infer<typeof completeSchema>>({
    resolver: zodResolver(completeSchema),
    defaultValues: { note: "" },
  });

  if (caseQ.isError) {
    return <ErrorState error={caseQ.error} onRetry={() => void caseQ.refetch()} />;
  }
  if (caseQ.isLoading || !caseQ.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-48" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const detail = caseQ.data;
  const messages = messagesQ.data ?? [];
  const facts = factsQ.data ?? [];
  const decision = detail.current_decision;
  const closed = detail.status === "CLOSED";
  const analysisBad = detail.analysis.status !== "OK";
  const isDemo = detail.title.startsWith(DEMO_TITLE);
  const phase = currentPhase(detail, messages.length);
  const status = caseStatus({
    status: detail.status,
    current_action: decision?.action ?? null,
    handover_status: detail.handover?.status ?? null,
    safety_state: decision?.safety?.state,
  });
  const firstPhase = messages.length === 0;
  const safety = decision?.safety ?? null;
  const emergency = safety?.state === "IMMEDIATE";

  const nextAction =
    decision && !analysisBad ? (
              <Rise key={`${decision.action}:${decision.next_question?.fact_id ?? "-"}`}>
                <NextActionCard
                  detail={detail}
                  decision={decision}
                  busy={post.isPending || unknown.isPending || skip.isPending}
                  hasBriefing={(briefingsQ.data ?? []).length > 0}
                  briefingStale={detail.briefing_stale}
                  briefingError={briefing.isError ? errorMessage(briefing.error) : null}
                  onOpenMore={() => {
                    setMoreOpen(true);
                    setTimeout(() => composerRef.current?.focus(), 50);
                  }}
                  onAnswer={(factId, text) => post.mutate({ content: text, answers_fact_id: factId })}
                  onUnknown={(factId) => unknown.mutate(factId)}
                  onDefer={(factId, label) => setDefer({ factId, label })}
                  onSkip={(factId) => skip.mutate(factId)}
                  onRequestHandover={() => setHandoverOpen(true)}
                  onCompleteHandover={() => setCompleteOpen(true)}
                  onCreateBriefing={() => briefing.mutate()}
                  briefingBusy={briefing.isPending}
                />
              </Rise>
            ) : null;

  return (
    <div className="mx-auto max-w-[880px]">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/" className="mb-1.5 inline-flex items-center gap-1 text-[12.5px] text-ink-subtle hover:text-ink">
            <ArrowLeft className="size-3.5" aria-hidden /> Meine Fälle
          </Link>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[22px] font-semibold leading-tight">{detail.title}</h1>
            {(status.group !== "active" || emergency) && <Badge tone={status.tone}>{status.label}</Badge>}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {(briefingsQ.data ?? []).length > 0 && decision?.action === "ASK" && (
            <Button asChild variant="ghost" size="sm">
              <Link to={`/cases/${caseId}/briefing`}>Briefing ansehen</Link>
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => (closed ? setStatus.mutate("OPEN") : setCloseOpen(true))}>
            {closed ? "Fall wieder öffnen" : "Fall abschliessen"}
          </Button>
        </div>
      </div>
      <div className="mb-5">
        <PhaseStepper phase={phase} questionsOpen={(decision?.missing_facts ?? []).length > 0} />
      </div>

      <div className="flex flex-col gap-6">
        {safety && emergency && <SafetyEmergency caseId={caseId} safety={safety} />}
        {safety && !emergency && (safety.state === "HUMAN_CHECK" || safety.state === "UNCLEAR") && (
          <SafetyNotice caseId={caseId} safety={safety} />
        )}
        {analysisBad && (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-3 rounded-lg border border-error-line bg-error-bg p-4 text-error-fg"
          >
            <TriangleAlert className="size-4 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1 text-[13px]">
              <p className="font-medium">
                {detail.analysis.status === "FAILED" ? "Die KI-Analyse ist fehlgeschlagen." : "Analyse ausstehend."}
              </p>
              <p>
                {detail.analysis.error_message ?? "Neue Eingaben sind gespeichert, aber noch nicht ausgewertet."} Ihre
                Eingabe ist nicht verloren; es wurde keine Analyse erfunden.
              </p>
            </div>
            <Button variant="secondary" size="sm" loading={reanalyze.isPending} onClick={() => reanalyze.mutate()}>
              <RefreshCw /> Erneut analysieren
            </Button>
          </div>
        )}

        {isDemo && (
          <DemoGuide
            caseId={caseId}
            messages={messages}
            draft={draft}
            onInsert={(t) => {
              setDraft(t);
              setMoreOpen(true);
              composerRef.current?.focus();
              composerRef.current?.scrollIntoView?.({ behavior: "smooth", block: "center" });
            }}
          />
        )}

        {firstPhase ? (
          <Composer
            ref={composerRef}
            first
            busy={post.isPending}
            disabled={closed}
            value={draft}
            onChange={setDraft}
            onSubmit={(text) => {
              // keep the text visible until the server has stored it; a network error must not lose it
              post.mutate({ content: text, kind: "DESCRIPTION" }, { onSuccess: () => setDraft("") });
            }}
          />
        ) : (
          <>
            <CaseSummary detail={detail} facts={facts} onOpenAll={() => setInfoOpen(true)} />

            {emergency ? (
              <details data-testid="legal-secondary" className="group rounded-lg border border-line bg-surface">
                <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[13.5px] font-medium">
                  Juristische Fallbearbeitung (nachrangig, nach der Sicherheitsreaktion)
                  <ChevronDown className="ml-auto size-4 text-ink-subtle transition-transform group-open:rotate-180" aria-hidden />
                </summary>
                <div className="border-t border-line p-4">{nextAction}</div>
              </details>
            ) : (
              nextAction
            )}

            {!closed && !emergency && (
              <BridgePanel caseId={caseId} disabled={closed} onCaseChanged={() => void invalidate()} />
            )}

            {!closed && (
              <div>
                {!moreOpen ? (
                  phase === 3 ? null : (
                  <Button variant="ghost" size="sm" onClick={() => setMoreOpen(true)}>
                    <MessageSquarePlus /> Weitere Informationen aus dem Gespräch ergänzen
                  </Button>
                  )
                ) : (
                  <Composer
                    ref={composerRef}
                    first={false}
                    busy={post.isPending && !post.variables?.answers_fact_id}
                    disabled={closed}
                    value={draft}
                    onChange={setDraft}
                    onSubmit={(text) => {
                      post.mutate({ content: text, kind: "NOTE" }, { onSuccess: () => setDraft("") });
                    }}
                  />
                )}
              </div>
            )}

            {decision && !analysisBad && <StatementsPanel decision={decision} />}

            <Timeline
              messages={messages}
              decisions={[...(decisionsQ.data ?? [])].reverse()}
              facts={facts}
              onRetry={() => reanalyze.mutate()}
              retrying={reanalyze.isPending}
            />
          </>
        )}
      </div>

      <Dialog open={infoOpen} onOpenChange={setInfoOpen}>
        <DialogContent className="max-w-xl">
          <DialogTitle>Alle Fallinformationen</DialogTitle>
          <DialogDescription>
            Bekannte, offene und unklare Angaben. Klicken Sie eine Angabe an, um die Herkunft zu sehen, sie zu korrigieren
            oder den Änderungsverlauf zu öffnen.
          </DialogDescription>
          <div className="mt-3">
            <CasePanel detail={detail} facts={facts} onOpenFact={setOpenFact} />
          </div>
        </DialogContent>
      </Dialog>

      <FactDialog
        caseId={caseId}
        fact={openFact ? (facts.find((f) => f.fact_id === openFact.fact_id) ?? openFact) : null}
        open={!!openFact}
        onOpenChange={(o) => !o && setOpenFact(null)}
        closed={closed}
      />
      <DeferDialog
        caseId={caseId}
        factId={defer?.factId ?? null}
        label={defer?.label ?? ""}
        open={!!defer}
        onOpenChange={(o) => !o && setDefer(null)}
      />

      <Dialog open={closeOpen} onOpenChange={setCloseOpen}>
        <DialogContent>
          <DialogTitle>Fall abschliessen?</DialogTitle>
          <DialogDescription>
            Abgeschlossene Fälle nehmen keine neuen Eingaben an. Sie können den Fall jederzeit wieder öffnen.
          </DialogDescription>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCloseOpen(false)}>
              Abbrechen
            </Button>
            <Button loading={setStatus.isPending} onClick={() => setStatus.mutate("CLOSED")}>
              Fall abschliessen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={handoverOpen} onOpenChange={setHandoverOpen}>
        <DialogContent>
          <DialogTitle>Übergabe als angefragt markieren?</DialogTitle>
          <DialogDescription>
            LexTec Bridge kontaktiert niemanden selbst. Markieren Sie die Übergabe erst als angefragt, wenn Sie die
            Fachperson tatsächlich angefragt haben.
          </DialogDescription>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setHandoverOpen(false)}>
              Abbrechen
            </Button>
            <Button loading={request.isPending} onClick={() => request.mutate()}>
              Als angefragt markieren
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={completeOpen} onOpenChange={setCompleteOpen}>
        <DialogContent>
          <DialogTitle>Übergabe bestätigen</DialogTitle>
          <DialogDescription>
            Bestätigen Sie nur, wenn die Übergabe wirklich stattgefunden hat. Halten Sie kurz fest, wie und an wen.
          </DialogDescription>
          <form className="mt-4" onSubmit={completeForm.handleSubmit((v) => complete.mutate(v.note))}>
            <Label htmlFor="handover-note">Bestätigung</Label>
            <Textarea
              id="handover-note"
              rows={3}
              placeholder="z. B. Telefonisch an Mietrechtsberatung übergeben, Termin vereinbart"
              {...completeForm.register("note")}
            />
            <FieldError>{completeForm.formState.errors.note?.message}</FieldError>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCompleteOpen(false)}>
                Abbrechen
              </Button>
              <Button type="submit" loading={complete.isPending}>
                Übergabe bestätigen
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
