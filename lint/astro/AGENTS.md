## Astro site (this repo)

### Environment
- Run `npm ci` after you clone or pull, so the hooks and `./check` use the versions in `package-lock.json`.
- Add a dependency with `npm install <pkg>`, or `npm install --save-dev <pkg>` for a tool. Commit
  `package.json` and `package-lock.json` together.
- Run tools with `npx --no-install <tool>`, so the project's locked version runs, not a global one.

### Checks to run
- `./check` runs every check (hooks, eslint, prettier, astro check, build) and prints one line per
  step, with the failing lines and a log path when something fails. Paste its summary into the PR's
  Evidence section.
- `./check --quick` skips the slow steps (the build) while you iterate; run the full `./check` before
  you say you're done. `./check --list` shows exactly what runs.

### Conventions
- TypeScript is strict (`astro/tsconfigs/strict`). Don't use `any`: give the type, or use `unknown`
  and narrow it.
- Every image has `alt` text; use `alt=""` only for a decorative image. A control is a `<button>` or
  an `<a href>`, not a `<div>` with a click handler. ESLint's accessibility rules check both.
- Images in `src/` go through `astro:assets` (`<Image>`). Files that must keep their URL go in
  `public/`.
- Content lives in content collections with a schema, so a missing or wrong field fails the build.
- Only `PUBLIC_` environment variables reach the browser. Never put a secret in a `PUBLIC_` variable
  or in client-side code.
- Don't edit `eslint.config.mjs`, `.prettierrc.json` or `tsconfig.json` to pass a check.
