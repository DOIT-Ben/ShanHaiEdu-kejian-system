import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "storybook-static", "src/generated", "public/mockServiceWorker.js"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strictTypeChecked],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": "off",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-confusing-void-expression": "off",
    },
  },
  {
    files: [
      "src/app/RuntimeApp.tsx",
      "src/layouts/Runtime*.tsx",
      "src/pages/runtime/**/*.{ts,tsx}",
      "src/pages/projects/Runtime*.{ts,tsx}",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/MockApp", "@/shared/api/mocks/*", "@/shared/data/mockData"],
              message: "Runtime 页面只能消费真实 API 和无状态产品组件，不能导入 MockRuntime。",
            },
          ],
        },
      ],
    },
  },
);
