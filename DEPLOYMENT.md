# Deployment Guide — Appraisal Review Extractor

**Audience:** bank credit risk team. **Trigger:** a menu item in the Teams
channel message compose box — an analyst picks this workflow, uploads the
appraisal review PDF directly into its form, and runs it. **Output:** a
brand-new Excel workbook for that review — a copy of the bank's own
appraisal review template with 17 cells populated — posted as a link to a
Teams channel.

> **Why the trigger looks like this.** The original version of this tool had
> the Copilot Studio agent call a Power Automate flow directly, using
> Copilot Studio's native "When Copilot Studio calls a flow" trigger. Some
> tenants' DLP (data loss prevention) policy blocks that trigger's connector
> (`shared_powervirtualagents`) outright — and because that connector is
> what *any* agent-calls-flow invocation depends on, no amount of redesigning
> the flow's own connectors fixes it. This version inverts the direction: a
> Power Automate flow is the entry point, and it calls *into* the agent's
> extraction topic using a different connector (the Copilot Studio "Run a
> topic" action). The flow itself is an **Instant cloud flow with a
> File-type input**, which Teams' built-in Power Automate/Workflows flow
> launcher surfaces directly as a menu item in the message compose box, file
> upload control included — no bot conversation, no message to attach a
> file to first, no SharePoint drop-folder to monitor. **Before deploying,
> confirm in your own tenant's DLP policy that the Copilot Studio "Run a
> topic" connector is not grouped with the blocked one** — some tenants
> classify Copilot Studio's inbound and outbound connectors together, in
> which case this design does not actually route around the block.

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [What this tool does](#what-this-tool-does)
3. [Why this design (cost rationale)](#why-this-design-cost-rationale)
4. [Prerequisites](#prerequisites)
5. [Part A — Designate template, destination, and notification locations](#part-a--designate-template-destination-and-notification-locations)
6. [Part B — Add the inline extraction Prompt action to the topic](#part-b--add-the-inline-extraction-prompt-action-to-the-topic)
7. [Part C — Configure the topic as a callable action](#part-c--configure-the-topic-as-a-callable-action)
8. [Part D — Add the Office Script to your template](#part-d--add-the-office-script-to-your-template)
9. [Part E — Build Shared-AppraisalReviewOrchestrator](#part-e--build-shared-appraisalrevieworchestrator)
10. [Part F — Publish the agent](#part-f--publish-the-agent)
11. [Part G — Make the workflow available in Teams](#part-g--make-the-workflow-available-in-teams)
12. [Part H — Test end-to-end](#part-h--test-end-to-end)
13. [Troubleshooting](#troubleshooting)

---

## Repository Layout

```
Copilot/
├── agent/
│   ├── appraisal-agent-instructions.md   ← Appraisal Review Extractor system prompt
│   └── appraisal-agent-topic.yaml        ← Callable extraction topic (OnInvokeTopic, no chat)
├── flows/
│   ├── Shared-AppraisalReviewOrchestrator.json   ← Instant cloud flow, File-input trigger, calls the agent, writes cells, posts to Teams
│   └── scripts/
│       └── PopulateAppraisalReviewCells.ts   ← Office Script run by the flow's "Run script" action
└── DEPLOYMENT.md
```

There is no `flows/packages/` directory and no template file shipped in
this repo. `Shared-AppraisalReviewOrchestrator` references your bank's own
template/destination paths and a Teams notification channel — values that
only exist after you designate them in your own environment, so a portable
`.zip` package can't pre-populate them (see Part A and Part E). The
workbook this tool writes into is **your** existing appraisal review
template, copied at runtime — not anything stored here.

---

## What this tool does

An analyst opens the compose box in the credit risk Teams channel, selects
**Shared-AppraisalReviewOrchestrator** from the built-in
Workflows/Power Automate flow picker (the same integration Teams uses for
any flow with a "Manually trigger a flow" trigger), uploads the appraisal
review PDF directly into the form that appears, and runs it. That's the
entire trigger surface — no bot conversation, no message to attach a file
to first, no SharePoint drop-folder to monitor.

`Shared-AppraisalReviewOrchestrator` checks the upload is a `.pdf` under
roughly 15 MB, and — only if valid — calls the **Appraisal Review
Extractor** agent's callable extraction topic, passing the file content, via
the Copilot Studio connector's "Run a topic" action. That topic **extracts
the 17 credit-risk data points itself, inline** — via a Prompt action
configured directly on the topic step, not a separately published AI
Builder catalog Prompt (full list and JSON contract in
[`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md))
— and returns the parsed, validated JSON as topic outputs, with no chat
activity sent anywhere.

The flow re-parses that response, and — if it's usable — **copies the
bank's own appraisal review template** to a new file, writes the values
into that copy's named cells on the `RE Collateral` sheet, and **posts to a
designated Teams channel** with a plain-language summary, any fields it
could not find, and a link to the new workbook. A rejected upload or a
failed extraction each get their own post to that same channel — the agent
never posts anything itself in this design, since it has no conversation to
post into.

This split matters for cost, not just architecture: neither the flow nor
the agent's topic has an AI Builder connector. The one LLM call this tool
makes happens inside the topic's inline Prompt action, billed as Copilot
Studio generative/message consumption. See "Why this design (cost
rationale)" below for what the trigger inversion actually buys you, and
what it doesn't.

Every review gets its own file — this is intentional, not a cost-saving
shortcut. Nothing about the template's design, its other sheets, or its
formulas is touched; the tool only ever writes to the 17 cells listed in
`_meta.cellMap` inside
[`flows/Shared-AppraisalReviewOrchestrator.json`](flows/Shared-AppraisalReviewOrchestrator.json):

| Cell | Field | Cell | Field |
|---|---|---|---|
| `F23` | Primary Occupancy Type | `I21` | Gross Building Area (SF) |
| `F24` | City, State | `I22` | Net Rentable Area (SF) |
| `F25` | Street Address | `I23` | Number of Buildings |
| `F26` | Collateral Analysis Value | `I24` | Year Built/Remodeled |
| `F27` | Valuation Type | `I25` | Remaining Economic Life (Yrs) |
| `F29` | Appraiser Name(s) | `I26` | General Condition |
| `F30` | Date of Appraisal | `I27` | Market Exposure Time |
| `F31` | Appraisal Reviewer | `I28` | Meets Highest & Best Use |
| `F32` | Date of Review | | |

All 17 cells are on a sheet named exactly **`RE Collateral`** — confirm
your template's sheet is named exactly that (case-sensitive) before
deploying, or update the sheet name in
`flows/scripts/PopulateAppraisalReviewCells.ts`.

---

## Why this design (cost rationale)

| Choice | Why it keeps cost (and risk) down |
|---|---|
| **Trigger is an Instant cloud flow with a File input,** surfaced as a Teams menu item — not Copilot Studio's native child-flow trigger, not an automatic file-drop or channel-message trigger | Routes around a DLP policy that blocks `shared_powervirtualagents`, while keeping the trigger genuinely Teams-native and explicit — the flow only runs when an analyst deliberately opens it and uploads a file, never automatically. Nothing runs (and nothing is spent) until someone asks for it. |
| **Flow-calls-agent, not agent-calls-flow**, for the extraction step | Same DLP-avoidance rationale as the trigger choice, applied to the second connector boundary in this design. **Verify the Copilot Studio "Run a topic" connector isn't grouped with the blocked one in your tenant** before deploying (see the callout at the top of this guide) — this is risk mitigation, not a cost optimization on its own. |
| Extraction via an **inline Prompt action configured directly on the topic**, not a separately published AI Builder catalog Prompt, and not an AI Builder call inside the flow | One fewer resource to create, publish, version, and administer — there is no AI Builder catalog object for this tool at all. Neither flow action nor topic action can trigger an AI Builder charge, structurally. **This does not eliminate the LLM cost of reading the PDF** — that call still happens inside the topic, billed as Copilot Studio generative/message consumption. Do not read this row as "free extraction." |
| Cell population via **Office Scripts** ("Run script"), a standard Excel Online (Business) action | No Premium connector and no custom Azure Function to write 17 cells — Office Scripts are included in standard Microsoft 365 licensing. |
| **One new file per review**, copied from your existing template | Deliberate (matches how the bank already packages appraisal reviews), not the lowest-cost option — the trade-off is one Copy File action and one Create Sharing Link action per run, small next to the generative cost already spent on extraction. |
| Template and destination locations are **flow parameters you designate**, not hardcoded | You point the flow at wherever your team actually keeps each of these — no repo-provided values to keep in sync with reality. |
| **Upload validated before the agent is ever called** (`Validate_Upload`: filename and approximate size) | A non-PDF or oversized upload never reaches `Call_Extraction_Agent` — rejected for the cost of a Compose action, not a generative call. |
| **No retries** on a failed extraction | A failure is posted to Teams immediately instead of silently doubling the cost on a document likely to fail again. |
| Extraction failures never reach the write steps | `Condition_Extraction_Ok` branches on the topic's `parseSucceeded` output before `Copy_Template_To_New_File` runs at all — a bad extraction never spends a Copy File / Run Script / Create Sharing Link action, and never leaves an orphaned partially-written workbook in the destination folder. |

The only new recurring costs are **Copilot Studio generative/message
consumption per PDF processed** (check your tenant's included message
allocation and overage pricing in the Power Platform admin center before
rollout — there is no AI Builder credit balance to track for this tool,
since it never calls AI Builder) and ordinary SharePoint/Teams connector
usage, which is typically unmetered under standard licensing. SharePoint
storage for one workbook per review is typically negligible (each file is
a few hundred KB).

> **A genuinely AI-free alternative exists, but it isn't this design.** The
> only way to remove the generative cost entirely — not just move it
> between connectors — is regex/pattern-based text extraction against known
> anchors in the PDF, with no model call anywhere. That trades away
> reliability across appraisal firms with different report formats for a
> hard zero on the LLM line item. This repo does not implement that
> variant; ask if you want it scoped separately.

---

## Prerequisites

| Requirement | Why it is needed |
|---|---|
| **Microsoft Copilot Studio** license, with generative/message capacity sufficient for inline Prompt actions | Runs the extraction — see cost note above. No AI Builder capacity is required; this design never calls AI Builder. |
| Confirmation from your Power Platform admin that the **Copilot Studio "Run a topic" connector is allowed** under your DLP policy | This whole design exists to route around a blocked `shared_powervirtualagents` connector — if the connector this design uses instead is *also* blocked (some tenants group them), this approach does not work and you'll need a different hand-off mechanism (e.g., a SharePoint list as a message queue instead of a direct connector call). |
| The **Teams Workflows/Power Automate app** available in your tenant (on by default for most Microsoft 365 commercial tenants) | This is how analysts see and run this flow from the message compose box — confirm with your Teams admin if it doesn't appear. |
| Your bank's **existing appraisal review template**, with a sheet named exactly `RE Collateral` and the cell layout in the table above | This tool copies and populates it — it does not create one for you |
| **Office Scripts** enabled for your tenant/site (on by default for most Microsoft 365 commercial tenants; confirm with your M365 admin if "Automate" doesn't appear in Excel Online) | Runs the cell-population script — standard M365 feature, no added license cost |
| A **SharePoint site and document library** for the template, and one for completed reviews (can be the same site/library) | Source and destination locations you'll designate as flow parameters |
| **Excel Online (Business)**, **SharePoint**, and **Microsoft Teams** connections (standard, no Premium required) | Used by the flow to copy files, run the script, and post results |
| A **Teams channel** for result notifications | Where analysts see outcomes — this trigger type has no specific message to reply into, so results go to a fixed channel |
| An account with **Environment Maker** (or higher) in the target Power Platform environment | To create the flow and agent |
| An account with **git** access, to clone this repository | To pull the reference files you'll build the flow and topic from |

---

## Part A — Designate template, destination, and notification locations

Nothing is provisioned here — you're just choosing (and writing down) where
things already live, or should be saved:

1. **Locate your existing template.** Find the SharePoint site and file
   path of the appraisal review template your team already uses (the one
   with the `RE Collateral` sheet and the cells listed above). Note:
   - **Template site URL** — e.g. `https://yourbank.sharepoint.com/sites/CreditRisk`
   - **Template file path** — e.g.
     `/sites/CreditRisk/Shared Documents/Templates/Appraisal Review Template.xlsx`
2. **Choose where completed reviews should be saved.** Note:
   - **Destination site URL**
   - **Destination folder path** — e.g.
     `/sites/CreditRisk/Shared Documents/Appraisal Reviews`
3. **Identify the Teams channel for result notifications.** Get its channel
   ID (Teams → the channel's **···** menu → **Get link to channel**, or via
   the Teams connector's own picker when configuring the flow action in
   Part E) — this is where `Shared-AppraisalReviewOrchestrator` posts every
   success, failure, and rejection message. Typically the same channel
   analysts will launch the workflow from.
4. Confirm the account that will own the Power Automate flow (Part E) has
   **edit** access to the template's library (read is enough there, since
   the flow only copies it), the destination folder (write), and post
   access to the notification channel.

You'll paste these values into the flow's parameters in Part E.

---

## Part B — Add the inline extraction Prompt action to the topic

This is the extraction engine, and it lives entirely inside the Copilot
Studio topic — there is no separate AI Builder catalog object to create,
publish, or version for this tool. Do this from inside the topic canvas
you'll create in Part C step 1 — build Part C steps 1–3 first (create the
topic, declare its inputs/outputs, clear the default trigger scaffolding),
then come back here for the topic's first real action, then continue with
Part C step 4 onward.

1. In the topic canvas, click the **+** below the topic's start node →
   **Add an action** → search **"AI Builder"** → select the **Prompt**
   action (some tenants label it **"Predict"** or **"Run a prompt"** — any
   of these names refer to the same AI Builder Prompt action).
2. The configuration pane that opens offers a choice between an existing
   saved prompt and creating one on the spot — choose **Create a prompt**
   (sometimes phrased "Create a new prompt" or shown as a blank prompt
   editor by default). This keeps the prompt inline on this action instead
   of creating a separate AI Builder catalog object.
3. **Model**: pick a GPT-class model from the dropdown — prefer a
   lower-cost/mini tier if your tenant's list offers one (e.g. a "mini" or
   "small" variant); extraction from a well-structured document doesn't
   need your largest available model.
4. **Add the file input.** Look for an **"Add data"**, **"Insert data"**,
   or **{ }** button near the instructions box — this is how you declare a
   named input the prompt can reference inline. Add:
   - Name: `document`
   - Type: **File**

   This input will later be bound to the topic's own `document` input
   (declared in Part C step 2) when you wire up this action's dynamic
   value — for now just declare it so it exists as a `{document}` token you
   can drop into the instructions text.

5. **Instructions box** — clear any placeholder text and paste the block
   below exactly (do not paraphrase; the flow's `Parse_Agent_Response`
   step and this topic's own `ParseJSON` call both depend on these literal
   JSON key names):

   ```
   Extract data from this appraisal review document: {document}

   Extract exactly these 17 fields from the appraisal review PDF. Read the
   appraisal report and the appraisal review section/memo if both are
   present — occupancy, address, and valuation figures come from the
   appraisal itself; reviewer name and review date come from the review
   memo/sign-off.

   1. Primary occupancy type -> occupancyType (string) — e.g. "Multifamily",
      "Retail — Anchored Center", "Industrial — Warehouse/Distribution"
   2. Location (city, state) -> city, state (two separate strings). Use
      USPS 2-letter state code.
   3. Street address -> streetAddress (string) — street number and name
      only; city/state/zip are captured separately.
   4. Collateral analysis value -> collateralAnalysisValue (number, no
      currency symbol or commas) — the value the bank relies on for
      collateral purposes, usually the reconciled/final opinion of value.
   5. Valuation type -> valuationType (string) — the value premise and
      approach reported, e.g. "As-Is Market Value — Income Capitalization
      Approach"
   6. Appraiser name(s) -> appraiserNames (array of strings) — include all
      signing appraisers (e.g. staff + supervisory/certified appraiser).
   7. Date of appraisal -> appraisalDate (string, YYYY-MM-DD) — effective
      date of value.
   8. Name of appraisal reviewer -> reviewerName (string) — the bank's or
      third-party review appraiser, not the original appraiser.
   9. Date of the review -> reviewDate (string, YYYY-MM-DD)
   10. Gross building area (sq ft) -> grossBuildingAreaSqFt (number)
   11. Net rentable area (sq ft) -> netRentableAreaSqFt (number). If the
       property type has no NRA concept (e.g. single-tenant industrial
       reported only as GBA), repeat the GBA value and note it in
       extractionNotes.
   12. Number of buildings -> numberOfBuildings (integer)
   13. Year built or remodeled -> yearBuiltOrRemodeled (4-digit year). If
       both exist, use the most recent (remodel) year and note the
       original year in extractionNotes.
   14. Remaining economic life (years) -> remainingEconomicLifeYears
       (integer)
   15. General condition -> generalCondition (string) — e.g. "Average",
       "Good", "Fair"; use the appraiser's own rating term.
   16. Market exposure time -> marketExposureTime (string, as stated, e.g.
       "6-12 months")
   17. Meets highest and best use per appraisal -> meetsHighestAndBestUse —
       one of "Yes", "No", "Not Stated"

   Handling missing or ambiguous data:
   - If a field is genuinely not present in the document, set its value to
     the string "Not Stated" (or null for numeric fields) — never guess or
     fabricate a number.
   - Every field you could not confidently extract goes in the
     missingFields array (using its JSON key) and sets needsManualReview to
     true.
   - Do not average, estimate, or infer numeric values (e.g. do not compute
     GBA from a per-unit figure) — extract only what the document states
     directly.

   Extraction standards:
   - Read the full document before extracting — figures for the same field
     sometimes appear in more than one place (e.g. a summary page and the
     detailed narrative); prefer the detailed narrative/reconciliation
     section when they conflict, and note the conflict in extractionNotes.
   - Preserve the appraiser's own terminology for occupancyType,
     generalCondition, and valuationType rather than normalizing to a house
     taxonomy.
   - Currency and area figures must be plain numbers (no $, no commas, no
     "sq ft" suffix).
   - Never fabricate a reviewer name or review date if the document
     contains only the original appraisal with no separate review
     sign-off — set both to "Not Stated" and add "reviewerName" /
     "reviewDate" to missingFields.

   Return your answer as a single JSON object with exactly these keys:
   occupancyType, city, state, streetAddress, collateralAnalysisValue,
   valuationType, appraiserNames, appraisalDate, reviewerName, reviewDate,
   grossBuildingAreaSqFt, netRentableAreaSqFt, numberOfBuildings,
   yearBuiltOrRemodeled, remainingEconomicLifeYears, generalCondition,
   marketExposureTime, meetsHighestAndBestUse, missingFields,
   needsManualReview, extractionNotes.
   - missingFields: array of JSON keys from the list above that could not
     be extracted. Empty array if everything was found.
   - needsManualReview: true if missingFields is non-empty, OR if the
     document did not clearly separate "appraisal" from "appraisal review"
     content, OR if you extracted a value you are not confident in.
   - extractionNotes: short plain-text note for anything an analyst should
     double-check (max ~2 sentences). Empty string if nothing to flag.
   ```

6. **Response format**: find the toggle/dropdown below the instructions box
   (often labeled **Response format** or **Output type**) and switch it
   from **Free text** to **JSON**. A schema editor should appear — paste
   this schema exactly:

   ```json
   {
     "type": "object",
     "properties": {
       "occupancyType":              { "type": "string" },
       "city":                       { "type": "string" },
       "state":                      { "type": "string" },
       "streetAddress":              { "type": "string" },
       "collateralAnalysisValue":    { "type": ["number", "null"] },
       "valuationType":              { "type": "string" },
       "appraiserNames":             { "type": "array", "items": { "type": "string" } },
       "appraisalDate":              { "type": "string" },
       "reviewerName":               { "type": "string" },
       "reviewDate":                 { "type": "string" },
       "grossBuildingAreaSqFt":      { "type": ["number", "null"] },
       "netRentableAreaSqFt":        { "type": ["number", "null"] },
       "numberOfBuildings":          { "type": ["integer", "null"] },
       "yearBuiltOrRemodeled":       { "type": ["integer", "string", "null"] },
       "remainingEconomicLifeYears": { "type": ["integer", "null"] },
       "generalCondition":           { "type": "string" },
       "marketExposureTime":         { "type": "string" },
       "meetsHighestAndBestUse":     { "type": "string" },
       "missingFields":              { "type": "array", "items": { "type": "string" } },
       "needsManualReview":          { "type": "boolean" },
       "extractionNotes":            { "type": "string" }
     }
   }
   ```

   If your tenant's schema editor only accepts a flat example payload
   rather than a JSON Schema document, paste the example JSON from
   `agent/appraisal-agent-instructions.md` → "Output Requirements" instead —
   most versions accept either and infer the shape.

7. **Name the action's output variable.** Find the output binding at the
   bottom of the configuration pane (often auto-named something like
   `TextResponse` or `Predict_Prompt_output`) and rename it, or note its
   exact generated name — you'll reference it in Part C step 4 as
   whatever variable holds the Prompt's raw JSON string. The reference
   design (`agent/appraisal-agent-topic.yaml`) calls this
   `topic.extractionRawJson`.
8. Click **Save** on the action.
9. Test this specific action before wiring up the rest of the topic:
   right-click the topic in the **Topics** list → **Test** (chat-style
   testing depends on trigger phrases this topic doesn't have, so use
   whatever direct-test option your designer offers instead of the normal
   chat pane), supply a sample PDF for the `document` input, and confirm
   the response is valid JSON matching the schema above before continuing
   to Part C step 4.
10. There is nothing to publish separately for this action — saving and
    publishing the agent (Part F) publishes it along with everything else
    in the topic.

---

## Part C — Configure the topic as a callable action

This is what makes `agent/appraisal-agent-topic.yaml` invocable by a flow
instead of by a chat message — the part of this design with the least
certain designer mechanics, since it's a newer capability than the
conversational topic authoring most Copilot Studio documentation covers.
Verify each step against your tenant's actual designer; the YAML file is a
best-effort reference, not something guaranteed to round-trip through the
YAML editor unmodified.

1. From the agent's **Topics** page, click **+ Add a topic** → **Create
   from blank**. Name it exactly `Extract Appraisal Fields` (this exact
   string is what `extractionTopicName` in the flow's parameters, Part E,
   must match).
2. Open the topic's **Settings** — the gear icon in the canvas toolbar, or
   **···** on the topic's entry in the Topics list → **Settings**. Look
   for a section governing whether this topic can be **called by other
   topics, agents, or Power Automate** (phrasing varies by version — look
   for "Inputs and outputs," "Callable," or a toggle near "Availability").
   Turn it on, then add:
   - **Input**: name `document`, type **File**
   - **Output**: name `extractionJson`, type **Text** (or **String**)
   - **Output**: name `parseSucceeded`, type **Yes/No** (or **Boolean**)

   If you can't find this section at all, search your tenant's Copilot
   Studio documentation for "topic inputs and outputs" or "reusable
   topics" — this capability's exact menu location has moved between
   Copilot Studio releases.
3. Back in the canvas, the blank-topic template usually pre-populates a
   **Trigger** node expecting phrases, and sometimes a greeting
   **Send a message** node. Delete the greeting node. For the Trigger
   node: leave its phrase list empty if the designer allows saving that
   way; if it insists on at least one phrase, enter something no live user
   would plausibly type (e.g. a GUID-like string) purely to satisfy
   validation, and treat that as a workaround, not a real entry point —
   the actual invocation always comes from Power Automate, never from a
   phrase match. Re-check step 2's "callable" toggle — turning it on is
   often what suppresses the phrase requirement entirely, so try that
   first before resorting to a placeholder phrase.
4. Add the Prompt action from **Part B** as the topic's first real step.
   When binding its `document` input (Part B step 4), use the dynamic
   values / **{ }** picker and look for the topic's own declared input —
   typically shown as `Topic.document` or listed under a "Topic inputs"
   category in the picker. If it doesn't appear automatically, save the
   topic's Settings (step 2) first, then reopen the Prompt action — the
   input sometimes only appears in pickers after the topic-level input is
   saved.
5. Add a **Set a variable value** action (Power Fx) directly after the
   Prompt action:
   - Variable: create new, name `extraction`.
   - Value (formula bar): `ParseJSON(Topic.extractionRawJson)` — replace
     `extractionRawJson` with whatever you actually named the Prompt
     action's output variable in Part B step 7.
6. Add a second **Set a variable value** action, targeting the
   `parseSucceeded` **output** variable you declared in step 2 (it should
   appear as an existing, settable variable — outputs behave like normal
   topic variables once declared):
   - Value (formula bar): `Not(IsError(Topic.extraction))`
7. Add a third **Set a variable value** action, targeting the
   `extractionJson` **output** variable:
   - Value (formula bar): `Topic.extractionRawJson`

   (Steps 6–7 can sometimes be combined into whatever "return a value" node
   your designer offers at the very end of the topic instead of separate
   Set Variable actions — if your canvas has an explicit **"End the
   topic"** node with fields for each declared output, set both outputs
   there directly instead of adding steps 6–7 as their own actions.)
8. End the topic. Look for **"End the topic"**, **"End and return a
   value,"** or similar as the final node — this is what actually sends
   `extractionJson` and `parseSucceeded` back to the calling flow. Do
   **not** use a `SendActivity` / "Send a message" node anywhere in this
   topic — there is no conversation for it to send into, and doing so is
   harmless but meaningless in this invocation model.
9. Save the topic. Confirm it does **not** appear in whatever "topics
   available in conversation" or "suggested topics" list your designer
   shows elsewhere for this agent's default orchestration — it should only
   be reachable as a callable action, not something a real chat user could
   stumble into.

---

## Part D — Add the Office Script to your template

Power Automate's Excel "Run script" action can only run a script that has
already been added to the target file (or another file it has access to)
via Excel's own **Automate** tab. Do this once, on your template file (the
one from Part A) — every copy of it keeps the script.

1. Open your template workbook (from Part A) in **Excel Online**.
2. Go to the **Automate** tab → **New Script**.
3. Delete the placeholder code, then paste the full contents of
   [`flows/scripts/PopulateAppraisalReviewCells.ts`](flows/scripts/PopulateAppraisalReviewCells.ts).
4. Rename the script (top-left, above the code editor) to exactly
   `PopulateAppraisalReviewCells`.
5. Click **Save script** (Ctrl+S / the save icon). You do **not** need to
   run it manually — Power Automate will call it.
6. Confirm the sheet name the script targets (`RE Collateral`) matches your
   template exactly. If your sheet is named differently, edit the
   `workbook.getWorksheet("RE Collateral")` line in the script before
   saving.

---

## Part E — Build Shared-AppraisalReviewOrchestrator

> **Reference file:** `flows/Shared-AppraisalReviewOrchestrator.json`

This flow owns the entire run — trigger, calling the agent, writing cells,
and posting every outcome to Teams.

1. Go to [make.powerautomate.com](https://make.powerautomate.com) → **+
   Create** → **Instant cloud flow**.
2. Name it `Shared-AppraisalReviewOrchestrator`.
3. Choose trigger **"Manually trigger a flow."** Click **Create**.
4. On the trigger card, click **+ Add an input → File**, name it
   `document`. Your designer should automatically create a paired text
   field for the file's name (`documentFileName` in the reference file) —
   confirm this happened; if your connector version names it differently,
   use its actual name consistently in place of `documentFileName`
   everywhere below.

**Add these actions in order:**

**Action 1 — Compose (`Init_RunTimestamp`)**
- Inputs (expression): `utcNow()`

**Action 2 — Compose (`Validate_Upload`)**
- Inputs (expression):
  ```
  and(endsWith(toLower(coalesce(triggerBody()?['documentFileName'], '')), '.pdf'), less(mul(length(triggerBody()?['document']), 0.75), 15728640))
  ```
  The `0.75` factor approximates base64-to-byte size (base64 inflates
  content by roughly 4/3) — **confirm this empirically** against a real
  upload in your tenant before trusting the 15 MB boundary precisely; if
  your connector exposes an actual byte-size property instead of just the
  base64 string, use that directly and drop the approximation.

**Action 3 — Condition (`Condition_Is_Valid`)**
- Condition: `Validate_Upload` output equals `true`.

**If yes — branch actions in order:**

**Action 4 — Copilot Studio: "Run a topic"** (or your tenant's equivalent
action name for this connector — search "Copilot Studio" in the connector
list)
- Environment: your Power Platform environment.
- Bot: `Appraisal Review Extractor` (from Part F).
- Topic: `Extract Appraisal Fields` (from Part C).
- `document` input: `base64ToBinary(triggerBody()?['document'])` — the
  trigger's File input arrives base64-encoded; convert it before passing
  it on.
- **This is the action to double-check against your DLP policy before
  building the rest of the flow** — if it's blocked too, stop here and
  reconsider the approach (see the callout at the top of this guide).

**Action 5 — Parse JSON**
- Content: `Run a topic`'s `extractionJson` output.
- Schema: paste the `properties` block from
  `flows/Shared-AppraisalReviewOrchestrator.json` →
  `actions.Condition_Is_Valid.actions.Parse_Agent_Response.inputs.schema`.

**Action 6 — Condition (`Condition_Extraction_Ok`)**
- Condition: `Run a topic`'s `parseSucceeded` output equals `true`.

**If yes — the write path:**

**Actions 7–12** — Compose `Format_Appraiser_Names`, Compose
`Format_City_State`, Compose `Build_Destination_File_Name`, SharePoint
"Copy file", SharePoint "Get file properties" (of the new copy), Excel
Online "Run script" (script parameters straight off `Parse JSON`'s output —
see `actions...Populate_Review_Cells` in the reference file for every
expression), SharePoint "Create sharing link." Same configuration notes as
earlier versions of this guide applied to the equivalent actions.

**Action 13 — Teams: "Post message in a channel" (`Post_Success_To_Teams`)**
- Team / Channel: your **notification channel** (Part A).
- Message: see
  `actions.Condition_Is_Valid.actions.Condition_Extraction_Ok.actions.Post_Success_To_Teams.inputs.body.body`
  for the exact expression — states what was created, flags missing
  fields, includes the workbook link.

**If no (extraction parse failed) — `Post_Extraction_Failure_To_Teams`:**
same Teams action, different message; see the reference file. No workbook
is created in this branch.

**If Action 3 was no (upload failed validation) — `Post_Rejection_To_Teams`:**
same Teams action again, explaining the upload was rejected. The agent is
never called in this branch — no generative cost is spent on an invalid
upload.

**One error branch outside the main condition tree:**

**Compose (`Handle_Write_Failure`)**
- Configure **Run after**: `Condition_Is_Valid` **has failed** or **timed
  out** — catches anything that breaks inside either branch that isn't
  already handled by the three Teams-post branches above (e.g. Copy File
  or Run Script erroring out after a successful extraction).

5. **Save** the flow. Consider setting a clear **description** on the flow
   (Details pane) — unlike earlier versions of this design, the flow's own
   name and description are now directly user-facing, since they're what
   analysts see in Teams' flow picker.

---

## Part F — Publish the agent

This is the checklist that ties Parts B and C together and gets the agent
into a state Power Automate can actually call. Do the sub-steps in order.

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com).
   Confirm the environment picker (top of the page, or under your profile
   icon) is set to the **same Power Platform environment** you used for
   Parts A, D, and E — a Copilot Studio agent created in the wrong
   environment won't be selectable from the flow's "Run a topic" action
   later.
2. Click **Agents** in the left nav (or **Create** on some tenants) → **New
   agent**. You'll be offered a conversational setup ("describe what you
   want your agent to do") — click **Skip to configure** to go straight to
   a blank agent instead, since you're pasting fixed instructions rather
   than having Copilot Studio draft them.
3. On the configuration page:
   - **Name**: `Appraisal Review Extractor`
   - **Description**: `Callable extraction topic for appraisal review PDFs — invoked by Shared-AppraisalReviewOrchestrator, not a conversational agent.`
4. Find the **Instructions** field — usually on the same configuration
   page under a heading like "Instructions" or "Additional instructions,"
   sometimes under **Settings → Generative AI** instead depending on your
   tenant's Copilot Studio version. Paste the **full contents** of
   [`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md)
   — the whole file, not just an excerpt; the extraction spec later gets
   pasted a second time into the Prompt action itself (Part B step 5), but
   the agent-level Instructions field is still worth having the complete
   file for context and maintainability.
5. Click **Create** (or **Save**) to actually create the agent shell before
   moving to topics — some designers won't let you add topics until the
   agent has been saved once.
6. Go to the **Topics** tab and build `Extract Appraisal Fields` following
   **Part C** (topic creation, inputs/outputs, trigger cleanup) and
   **Part B** (the inline Prompt action) in the order those two sections
   describe — Part C step 4 is where you drop into Part B.
7. **Find the agent's identifier for the flow.** Look under **Settings**
   (gear icon) → **Advanced** — depending on version this is labeled
   **Metadata** or shows fields like **Schema name** and/or **Bot ID**
   directly. Note whichever identifier is shown; you'll want it as a
   fallback for `appraisalAgentId` in Part E. In practice, you may not need
   to copy this by hand at all: when you configure the flow's "Run a
   topic" action in Part E, its **Bot** field is usually a searchable
   dropdown listing agents by display name (`Appraisal Review Extractor`)
   rather than requiring you to paste a raw ID — try the picker first, and
   only fall back to manually entering an ID if the picker doesn't resolve
   your agent.
8. **Publish** the agent (top-right **Publish** button, then confirm). You
   do **not** need to enable the Teams channel for this agent in this
   design — nothing chats with it directly, so skipping **Channels →
   Microsoft Teams** entirely is fine. If you want a fallback path to
   manually test the topic via chat during development, enabling Teams for
   testing purposes doesn't hurt, but it is not part of the production
   invocation path and analysts should never be told to message this
   agent directly.
9. Back in **Shared-AppraisalReviewOrchestrator** (Part E), open the "Run a
   topic" action and confirm it now resolves the published bot and topic
   correctly in the picker — some connector versions cache the agent/topic
   list and require the agent to be published (not just saved) before it
   appears as a selectable target, so revisit this action after step 8
   even if you configured it earlier.

---

## Part G — Make the workflow available in Teams

1. In Power Automate, open `Shared-AppraisalReviewOrchestrator` → **···** →
   **Share** (or **Details** → **Share**, depending on your designer
   version) and add the credit risk team's members/security group as
   **Run only** or **Co-owner** users, per your team's normal flow-sharing
   convention. This sharing step is what makes the flow selectable by
   anyone besides its owner — an Instant cloud flow with a File input that
   isn't shared won't appear in a teammate's Teams flow picker at all.
2. In Teams, open the credit risk channel's message compose box and look
   for the **Workflows** (or **Power Automate**, depending on your Teams
   client version) icon — typically under the "+" or the "···" in the
   compose toolbar. Confirm `Shared-AppraisalReviewOrchestrator` appears in
   the list of flows you (and, once shared, your teammates) can run.
3. If it doesn't appear automatically, some tenants require explicitly
   pinning it: from the same picker, look for an option to browse "All
   flows" or "Create" → "See your flows," which surfaces any Instant cloud
   flow with Teams-compatible inputs you have access to, even if it isn't
   pinned to the compose toolbar by default.

---

## Part H — Test end-to-end

1. In the credit risk Teams channel, open the compose box, select
   `Shared-AppraisalReviewOrchestrator` from the Workflows/Power Automate
   picker, and upload a sample appraisal review PDF into the form that
   appears. Run it.
2. Confirm in the flow's run history that it triggered, `Validate_Upload`
   evaluated `true`, and `Run a topic` (`Call_Extraction_Agent`) succeeded.
3. Confirm a message appears in the notification channel within about a
   minute, reporting "Created \<file name\>..." with a workbook link.
4. Open the link — the `RE Collateral` sheet should show all 17 cells
   populated (or `Not Stated` for anything genuinely absent from the
   source PDF), and every other sheet/cell in the template should be
   untouched.
5. Test with a PDF missing a review sign-off page — confirm `F31`/`F32`
   come back `Not Stated`, and the notification flags missing fields.
6. Test the guardrails: run the workflow uploading a non-PDF file, and (if
   you have one) a file over 15 MB. Both should produce a rejection message
   in the notification channel, and the flow's run history should show
   `Run a topic` never executed for either.
7. Run the workflow twice for the same property on the same day and
   confirm two distinct workbook files (the timestamp suffix in the file
   name should differ).
8. **Specifically confirm the DLP question this whole design exists to
   answer**: open the successful run's details for the `Run a topic`
   action and confirm it actually executed rather than being silently
   blocked at the connector level (a DLP block sometimes surfaces as a
   generic connection error rather than an explicit policy message,
   depending on your tenant).
9. Confirm the flow appears correctly for a **teammate**, not just its
   owner — sign in as (or ask) another analyst to confirm the workflow is
   visible and runnable from their own Teams client, validating the
   sharing step in Part G actually took effect.

---

## Troubleshooting

**The flow doesn't appear in Teams' Workflows/Power Automate picker**
- Confirm it's actually an **Instant cloud flow** with a **File-type
  input** on the "Manually trigger a flow" trigger — other trigger types
  don't surface here.
- Confirm the sharing step in Part G was completed for the user trying to
  find it — an unshared flow is invisible to everyone but its owner.
- Some Teams clients cache the flow list; try the "All flows" / "See your
  flows" browse option mentioned in Part G instead of only the pinned
  shortcut.

**The upload form doesn't show a proper file-upload control**
- Confirm the trigger input was added as type **File**, not **Text** or
  **String** — a text-typed input renders as a plain text box, not an
  upload control.

**`Run a topic` (Call_Extraction_Agent) fails immediately, especially with a
generic connection/authorization error**
- Treat this as a DLP block first, not a configuration bug — re-confirm
  with your Power Platform admin that the Copilot Studio "Run a topic"
  connector is actually allowed, not just assumed to be different from the
  blocked one. If it's blocked too, this whole design needs to fall back
  to a non-connector hand-off (e.g., a SharePoint list as a message queue
  that a separately-triggered flow polls, rather than any direct connector
  call in either direction).
- If it's not a DLP block: confirm the agent (Part F) is published, the
  `appraisalAgentId` and `extractionTopicName` parameters exactly match
  your published agent and topic, and the environment ID matches where the
  agent actually lives.
- Confirm `base64ToBinary(triggerBody()?['document'])` is actually
  producing valid file content — some connector versions surface the File
  input pre-decoded, in which case wrapping it in `base64ToBinary` again
  will corrupt it. Check the action's raw input in run history if the
  agent reports it can't read the document.

**The topic runs but `parseSucceeded` comes back `false`**
- Open the topic's own test pane (not the flow's run history) and inspect
  `topic.extractionRawJson` on a manual test run — the model likely
  returned prose instead of JSON. Re-open the `extractFieldsInline` action,
  confirm **Response format** is set to **JSON**, and confirm the pasted
  schema still exactly matches the "Output Requirements" example in
  `agent/appraisal-agent-instructions.md`.
- If this only happens on certain documents, check whether the instructions
  text was pasted in full — a truncated paste (common when copying from a
  rendered Markdown view instead of the raw file) silently drops
  field-handling rules and produces malformed output on edge cases.

**Copy File step fails**
- Most common cause: `templateFilePath` or `destinationFolderPath` is
  wrong (typo, or the file/folder was moved after Part A). Re-check both
  paths directly in SharePoint.
- Confirm the flow's SharePoint connection has read access to the template
  library and write access to the destination folder.

**Run Script step fails, or the script doesn't appear in the picker**
- The script must be saved on the file the action points at (or the
  template it was copied from) — confirm Part D was done on the correct
  file, and that the script is named exactly `PopulateAppraisalReviewCells`.
- `"Worksheet 'RE Collateral' was not found"` — the template's sheet is
  named differently than expected. Either rename the sheet to
  `RE Collateral` or edit the sheet name in
  `flows/scripts/PopulateAppraisalReviewCells.ts` and re-save the script in
  Excel.
- A cell shows the literal text `Not Stated` instead of the extracted
  value — check `Parse_Agent_Response`'s raw output for that field in the
  flow's run history; the model likely didn't find it in the source PDF.

**Create Sharing Link step fails, or the Teams message has no link**
- Confirm the flow's SharePoint connection has sharing permissions on the
  destination library (some tenants restrict link creation by policy).
- Check `Get_New_File_Properties`' output — if the drive/item identifiers
  are empty, Copy File likely returned a path format this step doesn't
  parse the way your tenant's connector version expects; adjust the
  dynamic-content binding to match the actual output fields shown in your
  designer.

**No Teams message ever arrives, even for a rejected upload**
- Confirm `notificationChannelId` in the flow's parameters resolves to a
  channel the flow's Teams connection actually has post access to.
- Confirm the flow's run history shows it reached one of the three
  `Post_*_To_Teams` actions at all — if the run failed earlier (e.g., the
  trigger itself, or `Validate_Upload`), no Teams action ever executes,
  and this looks identical to a silent failure from the analyst's side.

**Costs climbing faster than expected**
- Confirm `Validate_Upload` is still correctly rejecting oversized/non-PDF
  uploads before `Call_Extraction_Agent` runs — if someone edited the
  condition, invalid uploads could reach the agent and consume generative
  capacity before being rejected.
- Confirm `Condition_Extraction_Ok` is still wired up so a failed parse
  never reaches the write actions, leaving no orphaned partially-copied
  files in the destination folder.
- Pull the Copilot Studio message/generative consumption report for this
  agent specifically (Power Platform admin center → Copilot Studio
  analytics) rather than assuming a spike is this tool — a shared
  environment message allocation is consumed by every agent in it, not
  just this one.
