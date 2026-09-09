/**
 * Presentation-only helpers for the profile bio (SBGC-221).
 *
 * Pure TypeScript — no fetch, no DOM, no Django domain policy.  Owns the
 * display contract: bios are quoted, only Roman/Latin characters are
 * italicized (CJK is left upright), and the final word is highlighted red
 * only when the sentence actually terminates with a full stop.
 */

const FULLSTOP_CHARS = new Set([".", "。"]);

/** Sentence-ending punctuation used to bound a terminal unit in space-less scripts. */
const SENTENCE_ENDERS = new Set(["。", "！", "？", "!", "?"]);

export interface BioSplit {
  /** Bio text before the final whitespace-delimited word (may be empty). */
  leading: string;
  /** The final whitespace-delimited word (including any trailing punctuation). */
  lastWord: string;
  /** True when the bio ends with a full stop — highlight the last word. */
  highlightLastWord: boolean;
}

/**
 * Split a bio so callers can style the final word independently.
 *
 * Roman/spaced scripts delimit words with whitespace. Space-less scripts such
 * as Chinese have no word boundaries, so when the entire bio is a single
 * whitespace run the "final word" is bounded by the last sentence-ending
 * punctuation instead (e.g. the text after the previous 。). That keeps the red
 * highlight a terminal unit rather than flooding the whole bio.
 */
export function splitBio(bio: string): BioSplit {
  const trimmed = bio.trim();
  if (!trimmed) {
    return { leading: "", lastWord: "", highlightLastWord: false };
  }

  const lastChar = trimmed[trimmed.length - 1];
  const highlightLastWord = FULLSTOP_CHARS.has(lastChar);

  // Whitespace-delimited word (Latin and other spaced scripts).
  const match = /^(.*?)(\S+)$/s.exec(trimmed);
  const leading = match?.[1] ?? "";
  if (leading) {
    return { leading, lastWord: match?.[2] ?? "", highlightLastWord };
  }

  // Space-less script (CJK): bound the terminal unit by the previous sentence
  // ender when one exists; otherwise the whole text is the only candidate.
  let boundaryIndex = -1;
  for (let i = trimmed.length - 2; i >= 0; i -= 1) {
    if (SENTENCE_ENDERS.has(trimmed[i])) {
      boundaryIndex = i;
      break;
    }
  }
  if (boundaryIndex === -1) {
    return { leading: "", lastWord: trimmed, highlightLastWord };
  }
  return {
    leading: trimmed.slice(0, boundaryIndex + 1),
    lastWord: trimmed.slice(boundaryIndex + 1),
    highlightLastWord,
  };
}

/** A character counts as "roman/latin" when it is within the Basic Latin block. */
function isRomanChar(ch: string): boolean {
  return (ch.codePointAt(0) ?? 0) <= 0x007f;
}

interface ItalicRun {
  text: string;
  italic: boolean;
}

/** Split a string into runs of roman vs non-roman characters. */
function splitItalicRuns(text: string): ItalicRun[] {
  const runs: ItalicRun[] = [];
  let buffer = "";
  let bufferItalic: boolean | null = null;
  for (const ch of text) {
    const italic = isRomanChar(ch);
    if (bufferItalic === null || italic === bufferItalic) {
      buffer += ch;
      bufferItalic = italic;
    } else {
      runs.push({ text: buffer, italic: bufferItalic });
      buffer = ch;
      bufferItalic = italic;
    }
  }
  if (buffer) runs.push({ text: buffer, italic: bufferItalic ?? false });
  return runs;
}

export interface BioSegment {
  text: string;
  /** True for roman/latin runs (rendered italic). */
  italic: boolean;
  /** True when this run is the highlighted final word. */
  red: boolean;
}

/** Segment a bio into styled runs (italic + optional final-word highlight). */
export function segmentBio(bio: string): BioSegment[] {
  const { leading, lastWord, highlightLastWord } = splitBio(bio);
  const segments: BioSegment[] = [];
  for (const run of splitItalicRuns(leading)) {
    segments.push({ text: run.text, italic: run.italic, red: false });
  }
  for (const run of splitItalicRuns(lastWord)) {
    segments.push({
      text: run.text,
      italic: run.italic,
      red: highlightLastWord,
    });
  }
  return segments;
}
