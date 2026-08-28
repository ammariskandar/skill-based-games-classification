/**
 * Cross-boundary API contract parity tests (SBGC-93).
 *
 * Django is the single source of truth for the wire contract.  The backend
 * OpenAPI document is exported to a static fixture (see `fixtures/openapi.json`)
 * and this suite compares it against the hand-authored TypeScript DTOs in
 * `../../../types/api`.  Because the DTOs are runtime-erased, the expected
 * field lists are asserted as literal values — they mirror the DTO shapes
 * exactly, so any drift between the two sides fails here without requiring a
 * running Django process in frontend CI.
 */

import { describe, expect, it } from "vitest";
import openApi from "./fixtures/openapi.json";

/* ── Minimal structural typing for the OpenAPI subset this suite inspects ── */

interface SchemaObject {
  type?: string;
  title?: string;
  properties?: Record<string, unknown>;
  required?: string[];
}

interface PropertySchema {
  type?: string;
  anyOf?: Array<{ type?: string; enum?: string[] }>;
}

interface ParameterSchema {
  type?: string;
  enum?: string[];
  anyOf?: Array<{ type?: string; enum?: string[] }>;
}

interface Parameter {
  in: string;
  name: string;
  schema?: ParameterSchema;
}

interface Operation {
  parameters?: Parameter[];
  responses?: Record<string, unknown>;
}

interface OpenApiDocument {
  paths?: Record<string, Record<string, Operation>>;
  components?: { schemas?: Record<string, SchemaObject> };
}

const document = openApi as unknown as OpenApiDocument;
const schemas = document.components?.schemas ?? {};
const paths = document.paths ?? {};

/* ── helpers ── */

function schema(name: string): SchemaObject {
  const found = schemas[name];
  if (!found) throw new Error(`OpenAPI component schema "${name}" is missing`);
  return found;
}

function propertyNames(name: string): string[] {
  return Object.keys(schema(name).properties ?? {});
}

function expectPropertySet(name: string, expected: string[]): void {
  expect(propertyNames(name).sort()).toEqual([...expected].sort());
}

function isNullable(name: string, field: string): boolean {
  const property = schema(name).properties?.[field] as
    PropertySchema | undefined;
  return (
    Array.isArray(property?.anyOf) &&
    property.anyOf.some((option) => option?.type === "null")
  );
}

function expectNullable(name: string, fields: string[]): void {
  for (const field of fields) {
    expect(isNullable(name, field), `${name}.${field} should be nullable`).toBe(
      true,
    );
  }
}

function expectRequired(name: string, expected: string[]): void {
  expect((schema(name).required ?? []).sort()).toEqual([...expected].sort());
}

function successSchemaRef(path: string): string | undefined {
  const responses = paths[path]?.get?.responses ?? {};
  const ok = responses["200"] as
    | { content?: { "application/json"?: { schema?: { $ref?: string } } } }
    | undefined;
  return ok?.content?.["application/json"]?.schema?.$ref;
}

function queryParamSchema(
  path: string,
  name: string,
): ParameterSchema | undefined {
  return paths[path]?.get?.parameters?.find(
    (param) => param.in === "query" && param.name === name,
  )?.schema;
}

function enumValues(
  schemaRef: ParameterSchema | undefined,
): string[] | undefined {
  if (!schemaRef) return undefined;
  if (schemaRef.enum) return schemaRef.enum;
  return schemaRef.anyOf?.find((option) => option.enum)?.enum;
}

/* ── endpoint → response schema mapping ── */

describe("OpenAPI endpoint registration (SBGC-93)", () => {
  it("maps each public endpoint to its canonical response schema", () => {
    expect(successSchemaRef("/api/v1/games/{slug}")).toBe(
      "#/components/schemas/GameDetailResponse",
    );
    expect(successSchemaRef("/api/v1/games/")).toBe(
      "#/components/schemas/GameCatalogueResponse",
    );
    expect(successSchemaRef("/api/v1/rankings/")).toBe(
      "#/components/schemas/RankingResponse",
    );
    expect(successSchemaRef("/api/v1/games/search-index")).toBe(
      "#/components/schemas/SearchIndexResponse",
    );
  });

  it("documents the standard error envelope for the public endpoints", () => {
    for (const path of [
      "/api/v1/games/{slug}",
      "/api/v1/games/",
      "/api/v1/rankings/",
      "/api/v1/games/search-index",
    ]) {
      const responses = paths[path]?.get?.responses ?? {};
      const notFound = responses["404"] as
        | { content?: { "application/json"?: { schema?: { $ref?: string } } } }
        | undefined;
      expect(notFound?.content?.["application/json"]?.schema?.$ref).toBe(
        "#/components/schemas/ApiErrorResponse",
      );
    }
  });
});

/* ── game detail contract ── */

describe("Game detail contract parity", () => {
  it("matches PublicGameDetail fields and forbids publisher", () => {
    expectPropertySet("PublicGameDetail", [
      "id",
      "slug",
      "name",
      "source",
      "external_id",
      "content_type",
      "description",
      "release_date",
      "developer",
      "image_url",
      "library_hero_url",
      "library_capsule_url",
      "metadata_updated_at",
    ]);
    expect(schema("PublicGameDetail").properties).not.toHaveProperty(
      "publisher",
    );
    expectRequired("PublicGameDetail", [
      "id",
      "slug",
      "name",
      "source",
      "external_id",
      "content_type",
      "description",
      "release_date",
      "developer",
      "image_url",
      "metadata_updated_at",
    ]);
    expectNullable("PublicGameDetail", [
      "external_id",
      "release_date",
      "library_hero_url",
      "library_capsule_url",
    ]);
  });

  it("matches the classification profile and final classification", () => {
    expectPropertySet("PublicClassificationProfile", [
      "micro",
      "macro",
      "mystiko",
    ]);
    expectRequired("PublicClassificationProfile", [
      "micro",
      "macro",
      "mystiko",
    ]);

    expectPropertySet("PublicFinalClassification", [
      "status",
      "regime",
      "challenge",
      "reward",
      "confidence_level",
      "confidence_label",
      "submission_count",
      "calculation_version",
      "calculated_at",
      "is_stale",
    ]);
    expectRequired("PublicFinalClassification", ["status"]);
    expectNullable("PublicFinalClassification", [
      "regime",
      "challenge",
      "reward",
      "confidence_level",
      "confidence_label",
      "submission_count",
      "calculation_version",
      "calculated_at",
    ]);
  });

  it("matches the GameDetailResponse envelope and nullability", () => {
    expectPropertySet("GameDetailResponse", ["game", "classification"]);
    expectRequired("GameDetailResponse", ["game"]);
    expectNullable("GameDetailResponse", ["classification"]);
  });
});

/* ── catalogue contract ── */

describe("Catalogue contract parity", () => {
  it("matches GameCatalogueItem fields and forbids id", () => {
    expectPropertySet("GameCatalogueItem", [
      "slug",
      "name",
      "source",
      "image_url",
      "library_capsule_url",
      "classification",
    ]);
    expect(schema("GameCatalogueItem").properties).not.toHaveProperty("id");
    expectRequired("GameCatalogueItem", [
      "slug",
      "name",
      "source",
      "image_url",
    ]);
    expectNullable("GameCatalogueItem", [
      "library_capsule_url",
      "classification",
    ]);
  });

  it("matches the paginated catalogue envelope", () => {
    expectPropertySet("GameCatalogueResponse", [
      "count",
      "page",
      "page_size",
      "total_pages",
      "results",
    ]);
    expectRequired("GameCatalogueResponse", [
      "count",
      "page",
      "page_size",
      "total_pages",
      "results",
    ]);
  });

  it("matches the catalogue query parameter enums", () => {
    expect(enumValues(queryParamSchema("/api/v1/games/", "source"))).toEqual([
      "steam",
      "manual",
    ]);
    expect(enumValues(queryParamSchema("/api/v1/games/", "sort"))).toEqual([
      "name_asc",
      "name_desc",
      "recent",
      "micro",
      "mystiko",
      "macro",
    ]);
    expect(enumValues(queryParamSchema("/api/v1/games/", "profile"))).toEqual([
      "challenge",
      "reward",
    ]);
    expect(enumValues(queryParamSchema("/api/v1/games/", "dominant"))).toEqual([
      "micro",
      "mystiko",
      "macro",
    ]);
  });
});

/* ── rankings contract ── */

describe("Rankings contract parity", () => {
  it("matches RankingItem fields", () => {
    expectPropertySet("RankingItem", ["slug", "name", "hero_url", "score"]);
    expectRequired("RankingItem", ["slug", "name", "hero_url", "score"]);
  });

  it("matches the paginated ranking envelope", () => {
    expectPropertySet("RankingResponse", [
      "count",
      "page",
      "page_size",
      "total_pages",
      "results",
    ]);
    expectRequired("RankingResponse", [
      "count",
      "page",
      "page_size",
      "total_pages",
      "results",
    ]);
  });

  it("matches the ranking query parameter enums", () => {
    expect(
      enumValues(queryParamSchema("/api/v1/rankings/", "profile")),
    ).toEqual(["unified", "challenge", "reward"]);
    expect(
      enumValues(queryParamSchema("/api/v1/rankings/", "dimension")),
    ).toEqual(["micro", "mystiko", "macro"]);
    expect(
      enumValues(queryParamSchema("/api/v1/rankings/", "direction")),
    ).toEqual(["desc", "asc"]);
    expect(
      enumValues(queryParamSchema("/api/v1/rankings/", "dominant")),
    ).toEqual(["micro", "mystiko", "macro"]);
  });
});

/* ── search index contract ── */

describe("Search index contract parity", () => {
  it("matches SearchIndexItem fields and nullability", () => {
    expectPropertySet("SearchIndexItem", [
      "slug",
      "name",
      "capsule_url",
      "image_url",
    ]);
    expectRequired("SearchIndexItem", ["slug", "name"]);
    expectNullable("SearchIndexItem", ["capsule_url", "image_url"]);
  });

  it("matches the SearchIndexResponse envelope", () => {
    expectPropertySet("SearchIndexResponse", ["games"]);
    expectRequired("SearchIndexResponse", ["games"]);
  });
});

/* ── error envelope contract ── */

describe("Error envelope contract parity", () => {
  it("matches ApiError, ApiErrorDetail, and ApiErrorResponse", () => {
    expectPropertySet("ApiError", ["code", "message", "details"]);
    expectRequired("ApiError", ["code", "message"]);

    expectPropertySet("ApiErrorDetail", ["location", "message", "type"]);
    expectRequired("ApiErrorDetail", ["location", "message", "type"]);

    expectPropertySet("ApiErrorResponse", ["error"]);
    expectRequired("ApiErrorResponse", ["error"]);
  });
});
