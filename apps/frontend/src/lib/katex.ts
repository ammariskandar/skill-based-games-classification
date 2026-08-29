import katex from "katex";

/**
 * Build-time math typesetting helpers.
 *
 * The methodology page is pre-rendered (`prerender = true`), so KaTeX runs
 * only during the build: the browser receives finished `.katex` markup plus
 * the KaTeX stylesheet — no math library, no runtime JavaScript.  Use the
 * tagged-template form so LaTeX backslashes do not need escaping:
 *
 *   <span set:html={math`s_{id} = 2^{-\bar h_{id}/c(\psi)}`} />
 */

const OPTIONS = {
  throwOnError: false,
  strict: false,
} as const;

export function math(
  strings: TemplateStringsArray,
  ...values: unknown[]
): string {
  return katex.renderToString(String.raw(strings, ...values), {
    ...OPTIONS,
    displayMode: false,
  });
}

export function mathDisplay(
  strings: TemplateStringsArray,
  ...values: unknown[]
): string {
  return katex.renderToString(String.raw(strings, ...values), {
    ...OPTIONS,
    displayMode: true,
  });
}
