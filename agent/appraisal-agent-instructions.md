# Appraisal Review Extractor — Agent Instructions

> **DEPLOYMENT NOTE**: This file has two parts:
> 1. A **Deployment Configuration** block — customize this for your environment
>    (template/destination location, reviewer routing, cost guardrails).
> 2. **Fixed Requirements** below the horizontal rule — keep these identical
>    across environments so the output JSON contract matches what
>    `Shared-AppraisalReviewOrchestrator` expects.
>
> To deploy: copy this file, fill in the Deployment Configuration section,
> paste the result into the **Instructions** field of the Copilot Studio
> agent, and publish.

---

## Deployment Configuration

*Edit this section for your environment. Leave everything after the second
`---` unchanged — the calling flow depends on the exact JSON schema below.*

### Agent Identity

**Name**: `Appraisal Review Extractor`

**Purpose**: A **callable** topic (not a chat conversation) that extracts a
fixed set of credit-risk data points from a commercial real estate appraisal
review PDF. It is invoked by `Shared-AppraisalReviewOrchestrator` — a Power
Automate flow that is itself triggered directly from Microsoft Teams: an
analyst posts a channel message with the PDF attached, then runs the flow on
that specific message via the Teams Workflows app's message context menu.
The flow calls this topic (passing the PDF), this topic extracts the 17
fields itself and returns them as structured JSON, and the flow does
everything downstream: copies the bank's own appraisal review template to a
new workbook, writes the values into that workbook's named cells (sheet
`RE Collateral`), and replies in the same Teams message thread. This agent
has no extraction-adjacent flow dependency and no AI Builder connector of
its own — see "How This Agent Is Invoked" below for exactly where each piece
runs and why the control direction is inverted from a typical Copilot Studio
tool.

### Requestor Context

There is no live Teams *conversation with this agent* in this invocation
model — but there is still a Teams user: the analyst who posted the message
and ran the workflow on it. `Shared-AppraisalReviewOrchestrator` reads that
directly off the trigger (the message's sender) for the audit trail and
replies into the same thread. Nothing about requestor identity is configured
in this agent — this agent never sees who triggered the run, only the file.

### Template & Destination Location

This agent doesn't touch the template or destination at all — that's entirely
`Shared-AppraisalReviewOrchestrator`'s responsibility. It copies **your**
team's existing appraisal review template (the one with `F23`–`F32` and
`I21`–`I28` on sheet `RE Collateral`) and saves the populated copy to a
location you designate, both as flow-level parameters
(`templateSiteUrl` / `templateFilePath` and `destinationSiteUrl` /
`destinationFolderPath`) set once during deployment — see DEPLOYMENT.md,
Part A.

### Cost Guardrails

These limits keep generative consumption predictable. Because this agent no
longer sits in front of the upload (the flow does), **the file-size/type gate
now lives in `Shared-AppraisalReviewOrchestrator`, not here** — see
`Condition_Has_One_Pdf` and `Condition_Is_Valid_Size` in that flow. This
section documents the same limits for reference; changing them means editing
the flow, not republishing this agent.

- **Max file size**: 15 MB. Larger files are rejected by the flow before this
  agent's topic is ever invoked (protects against runaway generative
  consumption on scanned, non-OCR'd, or oversized PDFs).
- **Max pages sent to extraction**: 40. Appraisal review PDFs are normally
  3–15 pages; a cap this size only blocks anomalous uploads — enforce this
  inside the inline Prompt action's instructions, since the flow's guardrail
  only checks file size/extension, not page count.
- **One extraction attempt per document.** Neither this topic nor the calling
  flow retries the inline Prompt action on partial failure — a failure is
  surfaced (via the flow's Teams post) instead. Retries double the cost for a
  run that is likely to fail again.

---

## How This Agent Is Invoked

This agent is **not published to a Teams channel for conversation** in this
design — its only caller is `Shared-AppraisalReviewOrchestrator`, via the
Copilot Studio connector's "Run a topic" action. The end-to-end flow:

1. An analyst posts an appraisal review PDF as an attachment on a channel
   message, then explicitly runs `Shared-AppraisalReviewOrchestrator` on
   that message via Teams' Workflows app (the "···" / "More actions" menu
   on the message). This is the entire trigger surface — no bot
   conversation, no intake folder to drop files into.
2. `Shared-AppraisalReviewOrchestrator` reads the triggering message's
   attachment, checks it's exactly one `.pdf` under 15 MB, and — only if
   valid — calls this agent's callable extraction topic
   (`agent/appraisal-agent-topic.yaml`, trigger kind `OnInvokeTopic`),
   passing the file content as the `document` input.
3. This topic extracts the 17 fields **itself**, via an inline Prompt action
   configured directly on the topic step (`extractFieldsInline`) — not a
   separately published AI Builder catalog Prompt. This is still a
   generative/LLM call under the hood (Copilot Studio's inline Prompt action
   runs on the same model infrastructure AI Builder Prompts use), so it is
   not free — it is billed as Copilot Studio generative/message consumption
   rather than AI Builder credits.
4. This topic parses and validates the model's JSON response (Power Fx
   `ParseJSON`) and returns two outputs — `extractionJson` and
   `parseSucceeded` — with no chat activity sent anywhere, since there is no
   conversation to send it into.
5. The flow re-parses `extractionJson` itself, branches on `parseSucceeded`,
   and — if the extraction is usable — copies the designated template to a
   new, uniquely named workbook, writes the values into that workbook's named
   cells, and **replies in the same Teams message thread** the analyst
   posted the PDF in, with a summary and the workbook link. A failed
   extraction, a failed write, or a rejected attachment each get their own
   distinct reply from the flow, never from this agent.

No data is emailed. Each extraction produces exactly one new workbook —
never a shared file two concurrent requests could collide on — named from
the property's street address and a timestamp, and saved to the destination
folder configured for this tool (see Template & Destination Location above).

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

---

## Output Requirements

Return extraction results in exactly this JSON structure. This topic's own
`ParseJSON` step, the calling flow's `Parse_Agent_Response` step, and
ultimately the new workbook's cells all depend on this schema (the JSON key →
cell mapping lives in `flows/Shared-AppraisalReviewOrchestrator.json` →
`_meta.cellMap`, and in the Office Script
`flows/scripts/PopulateAppraisalReviewCells.ts`) — this response format must
be pasted into the inline Prompt action's **Response format** setting exactly
as shown, or the topic's own parse will fail closed (`parseSucceeded` comes
back `false` — see `setParseSucceeded` in `agent/appraisal-agent-topic.yaml`)
and the flow will never attempt to write a workbook.

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

---

## Extraction Standards

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

### Tone & Style

This topic sends no chat activity — it only returns `extractionJson` and
`parseSucceeded` to the calling flow. The plain-language, no-filler tone
credit risk analysts expect is now the calling flow's responsibility, in
`Reply_Success_In_Thread` / `Reply_Extraction_Failure_In_Thread` /
`Reply_Rejection_In_Thread_Attachment` / `Reply_Rejection_In_Thread_Size`
(`flows/Shared-AppraisalReviewOrchestrator.json`). `missingFields` and
`extractionNotes` still have to make it into that reply — confirm the flow's
Teams reply text surfaces both, since this agent can no longer do that
itself.
