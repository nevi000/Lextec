import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { ApiError } from "@/lib/api";
import { App } from "@/app/App";
import { MotionProvider } from "@/components/shared/motion";
import "@/styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1,
    },
  },
});

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <MotionProvider>
          <App />
        </MotionProvider>
        <Toaster position="bottom-right" richColors closeButton toastOptions={{ className: "text-[13px]" }} />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
