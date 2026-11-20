// ESLint for an Astro site (dev-tooling astro profile): JavaScript, TypeScript, Astro and
// accessibility recommended rules, plus a few bans. Formatting is Prettier's job, not ESLint's.
import js from "@eslint/js";
import astro from "eslint-plugin-astro";
import tseslint from "typescript-eslint";

export default [
  { ignores: ["dist/", ".astro/", "node_modules/", "public/"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...astro.configs.recommended,
  ...astro.configs["jsx-a11y-recommended"],
  {
    rules: {
      "no-console": ["error", { allow: ["warn", "error"] }],
      eqeqeq: ["error", "always"],
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
];
