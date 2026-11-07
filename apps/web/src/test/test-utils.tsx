import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { vi } from "vitest";
import { App } from "@/app/App";

type Handler = (url: URL, init?: RequestInit) => unknown | Promise<unknown>;
export type Routes = Record<string, Handler | unknown>;

export interface FetchCall {
  method: string;
  path: string;
  body: unknown;
}

/** Route-table fetch mock. Keys are "METHOD /path" (path without the /api prefix and query). */
export function mockApi(routes: Routes) {
  const calls: FetchCall[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const path = url.pathname.replace(/^\/api/, "");
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : init?.body ? "<binary>" : undefined;
    calls.push({ method, path, body });
    const handler = routes[`${method} ${path}`];
    if (handler === undefined) {
      return new Response(JSON.stringify({ error: { code: "not_found", message: `unmocked ${method} ${path}` } }), {
        status: 404,
      });
    }
    const data = typeof handler === "function" ? await (handler as Handler)(url, init) : handler;
    if (data instanceof Response) return data;
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return { calls, fn };
}

export const errorResponse = (status: number, code: string, message: string) =>
  new Response(JSON.stringify({ error: { code, message } }), { status });

export function renderApp(route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const statusRoute = {
  app_env: "test",
  ai_provider: "mock",
  ai_model: "mock-keyword-v1",
  ai_is_external: false,
  knowledge_base_version: "kb-test",
  knowledge_base_valid: true,
  auth_mode: "LOCAL_DEMO_NO_AUTH",
  notice: "Lokaler Entwicklungsmodus ohne Authentifizierung. Nur synthetische Daten verwenden.",
};

export const kbStatusRoute = {
  version: "kb-test",
  valid: true,
  errors: [],
  files: [],
  issue_count: 4,
  escalation_rule_count: 0,
  legal_rule_count: 0,
  global_rule_count: 0,
  source_count: 0,
  unverified_source_count: 0,
  scenario_count: 0,
  sources: [],
  professionals: [{ id: "employment_law_counsel", label_de: "Arbeitsrechtsberatung", description_de: "x" }],
};
