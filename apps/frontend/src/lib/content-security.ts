/**
 * Bio content-security sweeps — SBGC-222.
 *
 * Pure TypeScript, server-side only.  Runs ahead of the Django write boundary
 * in the Astro BFF so malicious payloads are rejected before touching the
 * database.  This is defense-in-depth; Django remains the authoritative gate.
 */

import allProfanity from "allprofanity";
import { stripBbCode } from "./bbcode";

export type BioMode = "PLAIN" | "BBCODE";

export interface ValidationResult {
  isValid: boolean;
  error?: string;
  sanitizedBio?: string;
}

// XSS / script protocols.
const XSS_PATTERN =
  /\b(?:javascript:|data:|vbscript:|onerror=|onload=|onclick=|onmouseover=)/i;

// Python execution vectors.
const PYTHON_EXEC_PATTERN =
  /\b(?:__import__|eval\s*\(|exec\s*\(|globals\s*\(|locals\s*\(|compile\s*\()/i;

// SQL keywords accompanied by quotes, semicolons, comments, or logical bypasses.
const ACTIVE_SQL_PATTERN =
  /('|"|;|--|\/\*)\s*(?:OR|AND|DROP|SELECT|INSERT|DELETE|UPDATE|UNION|ALTER|EXEC)\b/i;
const SQL_BYPASS_PATTERN = /'\s*OR\s*['"]?1['"]?\s*=\s*['"]?1/i;

export function validateContentSecurity(
  bio: string,
  bioMode: BioMode,
): ValidationResult {
  // 1. Zero-HTML policy: reject any explicit angle bracket.
  if (bio.includes("<") || bio.includes(">")) {
    return {
      isValid: false,
      error:
        "HTML tags are not permitted. Use BBCode for rich text formatting.",
    };
  }

  // 2. Cross-site scripting / script protocol detection.
  if (XSS_PATTERN.test(bio)) {
    return {
      isValid: false,
      error: "Potentially malicious script protocol detected.",
    };
  }

  // 3. Python execution vectors.
  if (PYTHON_EXEC_PATTERN.test(bio)) {
    return {
      isValid: false,
      error: "Executable code patterns are prohibited.",
    };
  }

  // 4. Structural SQL-injection verification.
  if (ACTIVE_SQL_PATTERN.test(bio) || SQL_BYPASS_PATTERN.test(bio)) {
    return {
      isValid: false,
      error: "Suspicious database instruction syntax detected.",
    };
  }

  // 5. Profanity sweep on the visible text.
  const visibleText = bioMode === "BBCODE" ? stripBbCode(bio) : bio;
  if (allProfanity.check(visibleText)) {
    return {
      isValid: false,
      error: "Bio contains inappropriate or restricted language.",
    };
  }

  return { isValid: true, sanitizedBio: bio };
}
