# Appraisal Review Field Extraction — Prompt Spec

This is the extraction specification for the **AI Builder Prompt** named
`Appraisal Review Field Extraction`, called by
[`flows/Shared-AppraisalReviewOrchestrator.json`](flows/Shared-AppraisalReviewOrchestrator.json)'s
`Extract_With_AI_Builder` action. Paste the **Extraction Requirements** and
**Output Requirements** sections below directly into that Prompt's
instructions box, exactly as written — see `DEPLOYMENT.md`, Part B.

There is no Copilot Studio agent in this design. This file is a prompt
spec, not a system prompt for a conversational bot — it's read only by the
AI Builder Prompt, not by anything else.

---

## Extraction Requirements

Extract exactly these 17 fields from the appraisal review PDF. Read the
appraisal report and the **appraisal review** section/memo if both are
present — occupancy, address, and valuation figures come from the appraisal
itself; reviewer name and review date come from the review memo/sign-off.

| # | Field | JSON key | Notes |
|---|---|---|---|
| 1 | Primary occupancy type | `occupancyType` | e.g. "Multifamily", "Retail — Anchored Center", "Industrial — Warehouse/Distribution" |
| 2 | Location (city, state) | `city`, `state` | Split into two fields. Use USPS 2-letter state code. |
| 3 | Street address | `streetAddress` | Street number and name only (city/state/zip captured separately) |
| 4 | Collateral analysis value | `collateralAnalysisValue` | Numeric, no currency symbol or commas. This is the value the bank relies on for collateral purposes — usually the reconciled/final opinion of value. |
| 5 | Valuation type | `valuationType` | The value premise and approach reported, e.g. "As-Is Market Value — Income Capitalization Approach" |
| 6 | Appraiser name(s) | `appraiserNames` | Array of strings. Include all signing appraisers (e.g. staff + supervisory/certified appraiser). |
| 7 | Date of appraisal | `appraisalDate` | Effective date of value, `YYYY-MM-DD` |
| 8 | Name of appraisal reviewer | `reviewerName` | The bank's or third-party review appraiser, not the original appraiser |
| 9 | Date of the review | `reviewDate` | `YYYY-MM-DD` |
| 10 | Gross building area (sq ft) | `grossBuildingAreaSqFt` | Numeric |
| 11 | Net rentable area (sq ft) | `netRentableAreaSqFt` | Numeric. If the property type has no NRA concept (e.g. single-tenant industrial reported only as GBA), repeat the GBA value and note it in `extractionNotes`. |
| 12 | Number of buildings | `numberOfBuildings` | Integer |
| 13 | Year built or remodeled | `yearBuiltOrRemodeled` | 4-digit year. If both exist, use the most recent (remodel) year and note the original year in `extractionNotes`. |
| 14 | Remaining economic life (years) | `remainingEconomicLifeYears` | Integer |
| 15 | General condition | `generalCondition` | e.g. "Average", "Good", "Fair" — use the appraiser's own rating term |
| 16 | Market exposure time | `marketExposureTime` | As stated, e.g. "6-12 months" |
| 17 | Meets highest and best use per appraisal | `meetsHighestAndBestUse` | One of: `"Yes"`, `"No"`, `"Not Stated"` |

### Handling missing or ambiguous data

- If a field is genuinely not present in the document, set its value to the
  string `"Not Stated"` (or `null` for numeric fields) — never guess or
  fabricate a number.
- Every field you could not confidently extract goes in the `missingFields`
  array (using its JSON key) and sets `needsManualReview` to `true`.
- Do not average, estimate, or infer numeric values (e.g. do not compute GBA
  from a per-unit figure) — extract only what the document states directly.

### Extraction standards

- Read the full document before extracting — figures for the same field
  sometimes appear in more than one place (e.g. a summary page and the
  detailed narrative); prefer the detailed narrative/reconciliation section
  when they conflict, and note the conflict in `extractionNotes`.
- Preserve the appraiser's own terminology for `occupancyType`,
  `generalCondition`, and `valuationType` rather than normalizing to a
  house taxonomy — credit risk reviewers cross-reference these against the
  source document.
- Currency and area figures must be plain numbers (no `$`, no commas, no
  `sq ft` suffix) so they land in Excel as numeric cells, not text.
- Never fabricate a reviewer name or review date if the document contains
  only the original appraisal with no separate review sign-off — set both to
  `"Not Stated"` and add `"reviewerName"` / `"reviewDate"` to
  `missingFields`.

---

## Output Requirements

Return extraction results in exactly this JSON structure. The calling
flow's `Parse_Extraction_Result` step, and ultimately the new workbook's
cells, depend on this schema (the JSON key → cell mapping lives in
`flows/Shared-AppraisalReviewOrchestrator.json` → `_meta.cellMap`, and in
the Office Script `flows/scripts/PopulateAppraisalReviewCells.ts`).

```json
{
  "occupancyType": "Multifamily — Garden Style",
  "city": "Charlotte",
  "state": "NC",
  "streetAddress": "4200 Colony Road",
  "collateralAnalysisValue": 18750000,
  "valuationType": "As-Is Market Value — Income Capitalization Approach",
  "appraiserNames": ["Jane R. Whitfield, MAI"],
  "appraisalDate": "2026-05-12",
  "reviewerName": "Marcus T. Adeyemi",
  "reviewDate": "2026-05-27",
  "grossBuildingAreaSqFt": 214500,
  "netRentableAreaSqFt": 198200,
  "numberOfBuildings": 6,
  "yearBuiltOrRemodeled": 2014,
  "remainingEconomicLifeYears": 38,
  "generalCondition": "Average",
  "marketExposureTime": "6-12 months",
  "meetsHighestAndBestUse": "Yes",
  "missingFields": [],
  "needsManualReview": false,
  "extractionNotes": ""
}
```

- `missingFields`: array of JSON keys from the table above that could not be
  extracted. Empty array if everything was found.
- `needsManualReview`: `true` if `missingFields` is non-empty, OR if the
  document did not clearly separate "appraisal" from "appraisal review"
  content, OR if you extracted a value you are not confident in.
- `extractionNotes`: short plain-text note for anything an analyst should
  double-check (max ~2 sentences). Empty string if nothing to flag.
