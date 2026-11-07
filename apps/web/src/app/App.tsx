import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/skeleton";

// Route-level code splitting keeps the initial bundle small.
const MobileBridgePage = lazy(() =>
  import("@/features/bridge/MobileBridgePage").then((m) => ({ default: m.MobileBridgePage })),
);
const DevPage = lazy(() => import("@/features/dev/DevPage").then((m) => ({ default: m.DevPage })));
const CasesPage = lazy(() => import("@/features/cases/CasesPage").then((m) => ({ default: m.CasesPage })));
const WorkspacePage = lazy(() =>
  import("@/features/consultation/WorkspacePage").then((m) => ({ default: m.WorkspacePage })),
);
const DecisionPage = lazy(() => import("@/features/decisions/DecisionPage").then((m) => ({ default: m.DecisionPage })));
const BriefingPage = lazy(() => import("@/features/briefings/BriefingPage").then((m) => ({ default: m.BriefingPage })));
const BriefingOverviewPage = lazy(() =>
  import("@/features/briefings/BriefingOverviewPage").then((m) => ({ default: m.BriefingOverviewPage })),
);
const EvaluationPage = lazy(() =>
  import("@/features/evaluation/EvaluationPage").then((m) => ({ default: m.EvaluationPage })),
);
const DemoPage = lazy(() => import("@/features/demo/DemoPage").then((m) => ({ default: m.DemoPage })));
const KnowledgeBasePage = lazy(() =>
  import("@/features/knowledge/KnowledgeBasePage").then((m) => ({ default: m.KnowledgeBasePage })),
);
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import("@/features/settings/SettingsPage").then((m) => ({ default: m.NotFoundPage })));

export function App() {
  return (
    <Suspense fallback={<Skeleton className="m-8 h-64" />}>
      <Routes>
        {/* the phone side lives outside the app shell: no navigation, no case data */}
        <Route path="bridge" element={<MobileBridgePage />} />
        <Route element={<AppShell />}>
          <Route index element={<CasesPage />} />
          <Route path="cases" element={<Navigate to="/" replace />} />
          <Route path="dev" element={<DevPage />} />
          <Route path="cases/:caseId" element={<WorkspacePage />} />
          <Route path="cases/:caseId/decision" element={<DecisionPage />} />
          <Route path="cases/:caseId/briefing" element={<BriefingPage />} />
          <Route path="cases/:caseId/briefing/:briefingId" element={<BriefingPage />} />
          <Route path="briefings" element={<BriefingOverviewPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
          <Route path="knowledge-base" element={<KnowledgeBasePage />} />
          <Route path="demo" element={<DemoPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
