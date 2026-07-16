import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "dist",
      "storybook-static",
      "coverage",
      "playwright-report",
      "test-results",
      "public",
      "src/shared/api/generated.ts",
      "scripts",
    ],
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": "off",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
      "no-restricted-globals": ["error", { name: "fetch", message: "业务代码不得直接调用 fetch，请使用 shared/api。" }],
    },
  },
  {
    files: [
      "src/shared/api/**/*.ts",
      "src/mocks/**/*.{ts,tsx}",
      "src/test/**/*.{ts,tsx}",
      "src/**/*.test.{ts,tsx}",
      "e2e/**/*.ts",
      "src/features/uploads/**/*.ts",
    ],
    rules: {
      "no-restricted-globals": "off",
    },
  },
);
