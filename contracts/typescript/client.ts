import createClient from "openapi-fetch";

import type { paths } from "../generated/typescript/schema";

export function createApiClient(baseUrl = "/api/v2") {
  return createClient<paths>({ baseUrl });
}
