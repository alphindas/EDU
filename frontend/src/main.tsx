import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { Toaster } from "./components/common/toast";
import "./i18n";
import "./index.css";
import { ApiError } from "./lib/api";
import { applyTheme, useTheme } from "./lib/theme";

const qc = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: (n, e) => !(e instanceof ApiError && e.status < 500) && n < 2 },
  },
});

function Theme({ children }: { children: React.ReactNode }) {
  const { dark, accent } = useTheme();
  useEffect(() => applyTheme(dark, accent), [dark, accent]);
  return children;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <Theme>
        <BrowserRouter>
          <App />
          <Toaster />
        </BrowserRouter>
      </Theme>
    </QueryClientProvider>
  </StrictMode>,
);
