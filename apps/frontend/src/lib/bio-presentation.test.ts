/**
 * Bio-presentation tests — SBGC-221.
 */

import { describe, expect, it } from "vitest";

import { segmentBio, splitBio } from "./bio-presentation";

describe("splitBio", () => {
  it("splits off the final word and highlights it when it ends with a full stop", () => {
    const segments = splitBio("Roguelites, tac shooters deep.");
    expect(segments.leading).toBe("Roguelites, tac shooters ");
    expect(segments.lastWord).toBe("deep.");
    expect(segments.highlightLastWord).toBe(true);
  });

  it("does not highlight a word when the bio is cut off without a full stop", () => {
    const segments = splitBio("Roguelites, tac shooters happe");
    expect(segments.highlightLastWord).toBe(false);
    expect(segments.lastWord).toBe("happe");
  });

  it("highlights a Japanese word ending with the ideographic full stop", () => {
    const segments = splitBio("sample です。");
    expect(segments.highlightLastWord).toBe(true);
    expect(segments.lastWord).toBe("です。");
  });

  it("handles a single-word bio", () => {
    const segments = splitBio("deep.");
    expect(segments.leading).toBe("");
    expect(segments.lastWord).toBe("deep.");
    expect(segments.highlightLastWord).toBe(true);
  });

  it("handles an empty bio", () => {
    const segments = splitBio("");
    expect(segments.leading).toBe("");
    expect(segments.lastWord).toBe("");
    expect(segments.highlightLastWord).toBe(false);
  });
});

describe("segmentBio", () => {
  it("italicizes roman runs and highlights the final word", () => {
    expect(segmentBio("Roguelites deep.")).toEqual([
      { text: "Roguelites ", italic: true, red: false },
      { text: "deep.", italic: true, red: true },
    ]);
  });

  it("does not italicize non-roman (CJK) text", () => {
    expect(segmentBio("你好世界。")).toEqual([
      { text: "你好世界。", italic: false, red: true },
    ]);
  });

  it("bounds the red highlight to the final sentence in space-less CJK", () => {
    const segments = splitBio("我喜欢游戏。我认真对待作品。");
    expect(segments.leading).toBe("我喜欢游戏。");
    expect(segments.lastWord).toBe("我认真对待作品。");
    expect(segments.highlightLastWord).toBe(true);

    expect(segmentBio("我喜欢游戏。我认真对待作品。")).toEqual([
      { text: "我喜欢游戏。", italic: false, red: false },
      { text: "我认真对待作品。", italic: false, red: true },
    ]);
  });

  it("never reddens a cut-off space-less CJK bio", () => {
    expect(segmentBio("我是一名玩家。作品写了一半")).toEqual([
      { text: "我是一名玩家。", italic: false, red: false },
      { text: "作品写了一半", italic: false, red: false },
    ]);
  });

  it("treats a single space-less sentence without earlier boundaries as one word", () => {
    expect(splitBio("谢谢大家。")).toEqual({
      leading: "",
      lastWord: "谢谢大家。",
      highlightLastWord: true,
    });
  });

  it("mixes roman and non-roman runs", () => {
    expect(segmentBio("Hello 世界 deep.")).toEqual([
      { text: "Hello ", italic: true, red: false },
      { text: "世界", italic: false, red: false },
      { text: " ", italic: true, red: false },
      { text: "deep.", italic: true, red: true },
    ]);
  });
});
