// Vite's license file (build.license) covers the bundled JavaScript. This adds what reaches
// the build another way: fonts and CSS through index.css, and the shadcn/ui component source
// copied into src/components/ui. Runs after `vite build`.
import { appendFileSync, readFileSync } from "node:fs"

const out = new URL("../../src/synthguard/ui_static/THIRD_PARTY_LICENSES.md", import.meta.url)
const extra = [
  ["@fontsource-variable/inter", "Inter font files (assets/inter-*.woff2)"],
  ["@fontsource-variable/geist-mono", "Geist Mono font files (assets/geist-mono-*.woff2)"],
  ["tailwindcss", "Base styles compiled into the CSS bundle"],
  ["tw-animate-css", "Animation utilities compiled into the CSS bundle"],
]

const SHADCN = `MIT License

Copyright (c) 2023 shadcn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`

let md = "\nThe build also contains the following, which reach it through CSS or copied source:\n"
for (const [pkg, what] of extra) {
  const meta = JSON.parse(readFileSync(new URL(`../node_modules/${pkg}/package.json`, import.meta.url), "utf8"))
  const text = readFileSync(new URL(`../node_modules/${pkg}/LICENSE`, import.meta.url), "utf8").trim()
  md += `\n## ${pkg} - ${meta.version} (${meta.license})\n\n${what}.\n\n${text}\n`
}
md += `\n## shadcn/ui (MIT)\n\nComponent source adapted from https://ui.shadcn.com into web/src/components/ui.\n\n${SHADCN}\n`
appendFileSync(out, md)
console.log(`notices: appended ${extra.length + 1} entries to THIRD_PARTY_LICENSES.md`)
