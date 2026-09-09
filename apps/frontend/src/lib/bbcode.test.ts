/**
 * BBCode parser & structural validation tests — SBGC-222.
 */

import { describe, expect, it } from "vitest";

import {
  BBCODE_MAX_EMBEDS,
  BBCODE_MAX_RAW_CHARS,
  BBCODE_MAX_VISIBLE_CHARS,
  parseAndValidateBbCode,
  renderBbCodeToHtml,
  stripBbCode,
} from "./bbcode";

describe("parseAndValidateBbCode", () => {
  it("renders whitelisted formatting to constrained HTML", () => {
    const result = parseAndValidateBbCode("[b]Hello[/b] [i]world[/i]");
    expect(result.isValid).toBe(true);
    expect(result.html).toBe(
      '<strong class="font-bold">Hello</strong> <em>world</em>',
    );
    expect(result.visibleCharCount).toBe(11);
  });

  it("rejects more than the combined embed limit", () => {
    const raw =
      "[img]https://a.com/1.png[/img]" +
      "[url=https://b.com]b[/url]" +
      "[url=https://c.com]c[/url]" +
      "[img]https://d.com/4.png[/img]";
    const result = parseAndValidateBbCode(raw);
    expect(result.isValid).toBe(false);
    expect(result.error).toContain(`maximum of ${BBCODE_MAX_EMBEDS}`);
    expect(result.embedCount).toBe(4);
  });

  it("rejects non-https URLs in [url] and [img]", () => {
    expect(
      parseAndValidateBbCode("[url=http://insecure.com]x[/url]").isValid,
    ).toBe(false);
    expect(
      parseAndValidateBbCode("[img]http://insecure.com/a.png[/img]").isValid,
    ).toBe(false);
  });

  it("rejects SVG image URLs", () => {
    const result = parseAndValidateBbCode(
      "[img]https://example.com/badge.svg[/img]",
    );
    expect(result.isValid).toBe(false);
    expect(result.error).toContain("SVG");
  });

  it("still rejects SVG when hidden behind a query string", () => {
    // The query-string suffix is stripped before the .svg extension check.
    const result = parseAndValidateBbCode(
      "[img]https://example.com/badge.svg?x=1[/img]",
    );
    expect(result.isValid).toBe(false);
    expect(result.error).toContain("SVG");
  });

  it("accepts under-250 visible text even when raw approaches 500", () => {
    const tagPadding = "[b][/b]".repeat(70); // 490 raw, 0 visible
    const raw = `${tagPadding}hello`;
    const result = parseAndValidateBbCode(raw);
    expect(result.rawCharCount).toBe(495);
    expect(result.rawCharCount).toBeLessThanOrEqual(BBCODE_MAX_RAW_CHARS);
    expect(result.visibleCharCount).toBe(5);
    expect(result.visibleCharCount).toBeLessThanOrEqual(
      BBCODE_MAX_VISIBLE_CHARS,
    );
    expect(result.isValid).toBe(true);
  });

  it("rejects raw markup over the raw limit", () => {
    const result = parseAndValidateBbCode("a".repeat(BBCODE_MAX_RAW_CHARS + 1));
    expect(result.isValid).toBe(false);
    expect(result.error).toContain("Raw");
  });

  it("rejects visible text over the visible limit", () => {
    const result = parseAndValidateBbCode(
      "a".repeat(BBCODE_MAX_VISIBLE_CHARS + 1),
    );
    expect(result.isValid).toBe(false);
    expect(result.error).toContain("Visible");
  });
});

describe("stripBbCode", () => {
  it("removes whitelisted tags, leaving visible text", () => {
    expect(stripBbCode("[b]Hello[/b] [url=https://x.com]link[/url]")).toBe(
      "Hello link",
    );
  });
});

describe("renderBbCodeToHtml", () => {
  it("renders a single image at full size", () => {
    const html = renderBbCodeToHtml("[img]https://example.com/badge.png[/img]");
    expect(html).not.toContain("max-h-12");
    expect(html).not.toContain("max-w-24");
    expect(html).toContain("max-w-full");
  });

  it("reduces two images to half width each", () => {
    const html = renderBbCodeToHtml(
      "[img]https://example.com/a.png[/img] [img]https://example.com/b.png[/img]",
    );
    expect(html).not.toContain("max-h-12");
    expect(html).not.toContain("max-w-24");
    // Both images carry the 50% cap.
    expect(html.match(/max-width: 50%/g) ?? []).toHaveLength(2);
  });

  it("constrains three images to micro-badge sizing", () => {
    const html = renderBbCodeToHtml(
      "[img]https://example.com/a.png[/img] [img]https://example.com/b.png[/img] [img]https://example.com/c.png[/img]",
    );
    expect(html).toContain("max-h-12");
    expect(html).toContain("max-w-24");
    expect(html).toContain('loading="lazy"');
  });
});
