import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ErrorBoundary } from "./ErrorBoundary";
import { Toaster } from "./Toaster";
import { UserProvider } from "./UserProvider";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UserProvider>
          <Toaster>{children}</Toaster>
        </UserProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}