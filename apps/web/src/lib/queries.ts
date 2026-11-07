import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError, api, type CaseFilters } from "@/lib/api";

export const keys = {
  status: ["system-status"] as const,
  dashboard: ["dashboard"] as const,
  cases: (f: CaseFilters) => ["cases", f] as const,
  case: (id: string) => ["case", id] as const,
  messages: (id: string) => ["messages", id] as const,
  facts: (id: string) => ["facts", id] as const,
  decisions: (id: string) => ["decisions", id] as const,
  briefings: (id: string) => ["briefings", id] as const,
  briefing: (id: string, bid: string) => ["briefing", id, bid] as const,
  briefingOverview: ["briefing-overview"] as const,
  kbStatus: ["kb-status"] as const,
  kbIssues: ["kb-issues"] as const,
};

export const errorMessage = (e: unknown) =>
  e instanceof ApiError ? e.message : "Unerwarteter Fehler. Bitte erneut versuchen.";

export const useSystemStatus = () => useQuery({ queryKey: keys.status, queryFn: api.systemStatus, staleTime: 30_000 });
export const useDashboard = () => useQuery({ queryKey: keys.dashboard, queryFn: api.dashboard });
export const useCases = (f: CaseFilters) =>
  useQuery({ queryKey: keys.cases(f), queryFn: () => api.listCases(f), placeholderData: (p) => p });
export const useCase = (id: string) => useQuery({ queryKey: keys.case(id), queryFn: () => api.getCase(id) });
export const useMessages = (id: string) =>
  useQuery({ queryKey: keys.messages(id), queryFn: () => api.listMessages(id) });
export const useFacts = (id: string) => useQuery({ queryKey: keys.facts(id), queryFn: () => api.listFacts(id) });
export const useDecisions = (id: string) =>
  useQuery({ queryKey: keys.decisions(id), queryFn: () => api.decisions(id) });
export const useBriefings = (id: string) =>
  useQuery({ queryKey: keys.briefings(id), queryFn: () => api.listBriefings(id) });
export const useBriefing = (id: string, bid: string | undefined) =>
  useQuery({
    queryKey: keys.briefing(id, bid ?? ""),
    queryFn: () => api.getBriefing(id, bid as string),
    enabled: !!bid,
  });

/** Invalidate everything derived from one case after any mutation. */
export function useInvalidateCase(id: string) {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: keys.case(id) }),
      qc.invalidateQueries({ queryKey: keys.messages(id) }),
      qc.invalidateQueries({ queryKey: keys.facts(id) }),
      qc.invalidateQueries({ queryKey: keys.decisions(id) }),
      qc.invalidateQueries({ queryKey: keys.briefings(id) }),
      qc.invalidateQueries({ queryKey: ["cases"] }),
      qc.invalidateQueries({ queryKey: keys.dashboard }),
      qc.invalidateQueries({ queryKey: keys.briefingOverview }),
    ]);
}

export function useCreateCase(onCreated: (id: string) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.createCase(""),
    onSuccess: (c) => {
      void qc.invalidateQueries({ queryKey: ["cases"] });
      void qc.invalidateQueries({ queryKey: keys.dashboard });
      toast.success(`${c.display_id} angelegt`);
      onCreated(c.id);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

export function useSources() {
  const q = useQuery({ queryKey: keys.kbStatus, queryFn: api.kbStatus, staleTime: 60_000 });
  const title = (id: string) => q.data?.sources.find((s) => s.id === id)?.title_de ?? id;
  const ref = (id: string) => q.data?.sources.find((s) => s.id === id);
  return { title, ref, ...q };
}

export const useAIUsage = () => useQuery({ queryKey: ["ai-usage"], queryFn: api.aiUsage, staleTime: 5_000 });

export function useProfessionals() {
  const q = useQuery({ queryKey: keys.kbStatus, queryFn: api.kbStatus, staleTime: 60_000 });
  const label = (id: string) => q.data?.professionals.find((p) => p.id === id)?.label_de ?? id;
  return { label, ...q };
}
