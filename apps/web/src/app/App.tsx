import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router/dom";
import { createQueryClient } from "./queryClient";
import { router } from "./router";
import { SessionExpiryListener } from "./session";
import { Toaster, TooltipProvider } from "@/shared/ui";

export function App() {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <SessionExpiryListener />
        <RouterProvider router={router} />
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
