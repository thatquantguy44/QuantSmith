/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_HASH_ROUTER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
