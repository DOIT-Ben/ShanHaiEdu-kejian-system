import { setupWorker } from "msw/browser";
import { handlers } from "@/shared/api/mocks/handlers";

export const worker = setupWorker(...handlers);
