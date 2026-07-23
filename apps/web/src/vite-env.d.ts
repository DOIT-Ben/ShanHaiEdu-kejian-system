/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: "mock" | "real";
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_RELEASE_VERSION?: string;
  readonly VITE_RUNTIME_CONTRACT_TEST?: "1";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
