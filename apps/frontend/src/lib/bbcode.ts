/**
 * BBCode parser & structural validator — SBGC-222.
 *
 * Pure TypeScript — no DOM, no fetch.  Owns the display contract for
 * ``BBCODE``-mode bios: a whitelisted tag set, dual visible/raw character
 * limits, a combined embed budget, strict https:// enforcement, and SVG
 * rejection.  The returned HTML is built solely from whitelisted tags over
 * already HTML-free input (the BFF rejects any ``<``/``>`` before parsing).
 */

export const BBCODE_MAX_RAW_CHARS = 500;
export const BBCODE_MAX_VISIBLE_CHARS = 250;
export const BBCODE_MAX_EMBEDS = 3;

const FORMATTING_TAG_RE = /\[\/?(?:b|i|u|s|color|url|img)(?:=[^\]]+)?\]/gi;

export interface BbCodeLimits {
  maxVisibleChars: number;
  maxRawChars: number;
  maxEmbeds: number;
}

export const BBCODE_LIMITS: BbCodeLimits = {
  maxVisibleChars: BBCODE_MAX_VISIBLE_CHARS,
  maxRawChars: BBCODE_MAX_RAW_CHARS,
  maxEmbeds: BBCODE_MAX_EMBEDS,
};

export interface ParseResult {
  isValid: boolean;
  error?: string;
  html?: string;
  visibleCharCount: number;
  rawCharCount: number;
  embedCount?: number;
}

/** Remove whitelisted BBCode tags, leaving only visible text. */
export function stripBbCode(text: string): string {
  return text.replace(FORMATTING_TAG_RE, "");
}

function countEmbeds(rawText: string): number {
  const imgMatches = rawText.match(/\[img\]/gi) ?? [];
  const urlMatches = rawText.match(/\[url(?:=[^\]]+)?\]/gi) ?? [];
  return imgMatches.length + urlMatches.length;
}

export function parseAndValidateBbCode(rawText: string): ParseResult {
  const rawCharCount = rawText.length;
  if (rawCharCount > BBCODE_MAX_RAW_CHARS) {
    return {
      isValid: false,
      error: `Raw bio markup exceeds the maximum of ${BBCODE_MAX_RAW_CHARS} characters (${rawCharCount}/${BBCODE_MAX_RAW_CHARS}).`,
      visibleCharCount: 0,
      rawCharCount,
    };
  }

  const visibleCharCount = stripBbCode(rawText).length;
  if (visibleCharCount > BBCODE_MAX_VISIBLE_CHARS) {
    return {
      isValid: false,
      error: `Visible bio text exceeds the maximum of ${BBCODE_MAX_VISIBLE_CHARS} characters (${visibleCharCount}/${BBCODE_MAX_VISIBLE_CHARS}).`,
      visibleCharCount,
      rawCharCount,
    };
  }

  const embedCount = countEmbeds(rawText);
  if (embedCount > BBCODE_MAX_EMBEDS) {
    return {
      isValid: false,
      error: `Bio may contain a maximum of ${BBCODE_MAX_EMBEDS} links or images combined (found ${embedCount}).`,
      visibleCharCount,
      rawCharCount,
      embedCount,
    };
  }

  // [url=...]text[/url] — match any target, then enforce the protocol.
  const urlRegex = /\[url=([^\]]+)\](.*?)\[\/url\]/gi;
  let urlMatch: RegExpExecArray | null;
  while ((urlMatch = urlRegex.exec(rawText)) !== null) {
    if (!urlMatch[1].startsWith("https://")) {
      return {
        isValid: false,
        error: "All links must strictly use the secure https:// protocol.",
        visibleCharCount,
        rawCharCount,
        embedCount,
      };
    }
  }

  // [img]...[/img] — match any URL, then enforce protocol and format.
  const imgRegex = /\[img\]([^\]]+?)\[\/img\]/gi;
  let imgMatch: RegExpExecArray | null;
  while ((imgMatch = imgRegex.exec(rawText)) !== null) {
    const imgUrl = imgMatch[1];
    if (!imgUrl.startsWith("https://")) {
      return {
        isValid: false,
        error:
          "All embedded images must strictly use the secure https:// protocol.",
        visibleCharCount,
        rawCharCount,
        embedCount,
      };
    }
    if (imgUrl.toLowerCase().split("?")[0].endsWith(".svg")) {
      return {
        isValid: false,
        error: "SVG image embedding is not permitted for security reasons.",
        visibleCharCount,
        rawCharCount,
        embedCount,
      };
    }
  }

  return {
    isValid: true,
    html: renderBbCodeToHtml(rawText),
    visibleCharCount,
    rawCharCount,
    embedCount,
  };
}

/** Convert whitelisted BBCode to a constrained, safe HTML fragment. */
export function renderBbCodeToHtml(input: string): string {
  let html = input;

  html = html.replace(/\[b\](.*?)\[\/b\]/gi, "<strong>$1</strong>");
  html = html.replace(/\[i\](.*?)\[\/i\]/gi, "<em>$1</em>");
  html = html.replace(/\[u\](.*?)\[\/u\]/gi, "<u>$1</u>");
  html = html.replace(/\[s\](.*?)\[\/s\]/gi, "<s>$1</s>");

  html = html.replace(
    /\[color=(#[0-9A-Fa-f]{6})\](.*?)\[\/color\]/gi,
    '<span style="color: $1;">$2</span>',
  );

  html = html.replace(
    /\[url=(https:\/\/[^\]]+)\](.*?)\[\/url\]/gi,
    '<a href="$1" target="_blank" rel="noopener noreferrer" class="text-blue underline hover:text-blue">$2</a>',
  );

  // A single image renders at full/original size; multiple images are
  // constrained to micro-badge sizing (SBGC-222).
  const imgCount = (input.match(/\[img\]/gi) ?? []).length;
  const imgClass =
    imgCount === 1
      ? "inline-block h-auto max-w-full rounded mx-0.5"
      : "inline-block max-h-12 max-w-24 object-cover align-middle rounded mx-0.5";
  html = html.replace(
    /\[img\](https:\/\/[^\]]+?)\[\/img\]/gi,
    `<img src="$1" alt="User embedded badge" class="${imgClass}" loading="lazy" />`,
  );

  return html;
}
