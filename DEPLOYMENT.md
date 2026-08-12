# Deployment Guide — Appraisal Review Extractor

**Audience:** bank credit risk team. **Trigger:** an appraisal review PDF
dropped into a SharePoint intake library (which can be surfaced as a Teams
channel Files tab). **Output:** a brand-new Excel workbook for that review —
a copy of the bank's own appraisal review template with 17 cells populated —
posted as a link to a Teams channel.

> **Why the trigger looks like this.** The original version of this tool had
> the Copilot Studio agent call a Power Automate flow directly, using
> Copilot Studio's native "When Copilot Studio calls a flow" trigger. Some
> tenants' DLP (data loss prevention) policy blocks that trigger's connector
> (`shared_powervirtualagents`) outright — and because that connector is
> what *any* agent-calls-flow invocation depends on, no amount of redesigning
> the flow's own connectors fixes it. This version inverts the direction: a
> Power Automate flow is the entry point, and it calls *into* the agent's
> extraction topic using a different connector (the Copilot Studio "Run a
> topic" action). **Before deploying this version, confirm in your own
> tenant's DLP policy that this second connector is not grouped with the
> blocked one** — some tenants classify Copilot Studio's inbound and
> outbound connectors together, in which case this inversion does not
> actually route around the block, and you should fall back to a design that
> avoids Copilot Studio-to-flow connectors in both directions instead.

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [What this tool does](#what-this-tool-does)
3. [Why this design (cost rationale)](#why-this-design-cost-rationale)
4. [Prerequisites](#prerequisites)
5. [Part A — Designate template, destination, intake, and notification locations](#part-a--designate-template-destination-intake-and-notification-locations)
6. [Part B — Add the inline extraction Prompt action to the topic](#part-b--add-the-inline-extraction-prompt-action-to-the-topic)
7. [Part C — Configure the topic as a callable action](#part-c--configure-the-topic-as-a-callable-action)
8. [Part D — Add the Office Script to your template](#part-d--add-the-office-script-to-your-template)
9. [Part E — Build Shared-AppraisalReviewOrchestrator](#part-e--build-shared-appraisalrevieworchestrator)
10. [Part F — Publish the agent](#part-f--publish-the-agent)
11. [Part G — Connect the intake Files tab and Teams notifications](#part-g--connect-the-intake-files-tab-and-teams-notifications)
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
│   ├── Shared-AppraisalReviewOrchestrator.json   ← Owns the whole run: trigger, calls the agent, writes cells, notifies Teams
│   └── scripts/
│       └── PopulateAppraisalReviewCells.ts   ← Office Script run by the flow's "Run script" action
└── DEPLOYMENT.md
```

There is no `flows/packages/` directory and no template file shipped in
this repo. `Shared-AppraisalReviewOrchestrator` references your bank's own
template/destination/intake paths and Teams channel — values that only
exist after you designate them in your own environment, so a portable
`.zip` package can't pre-populate them (see Part A and Part E). The
workbook this tool writes into is **your** existing appraisal review
template, copied at runtime — not anything stored here.

---

## What this tool does

An analyst drops an appraisal review PDF into a designated SharePoint
intake library — directly, or via a Teams channel Files tab pointed at the
same library, so it still feels like "drop it in Teams." No bot
conversation is involved in starting a run.

`Shared-AppraisalReviewOrchestrator` triggers on that file's arrival,
checks it's a `.pdf` under 15 MB, and calls the **Appraisal Review
Extractor** agent's callable extraction topic — passing the file content —
via the Copilot Studio connector's "Run a topic" action. That topic
**extracts the 17 credit-risk data points itself, inline** — via a Prompt
action configured directly on the topic step, not a separately published
AI Builder catalog Prompt (full list and JSON contract in
[`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md))
— and returns the parsed, validated JSON as topic outputs, with no chat
activity sent anywhere.

The flow re-parses that response, and — if it's usable — **copies the
bank's own appraisal review template** to a new file, writes the values
into that copy's named cells on the `RE Collateral` sheet, and posts a
plain-language summary, any fields it could not find, and a link to the
new workbook **to a Teams channel**. A rejected upload or a failed
extraction each get their own distinct Teams post from the flow — the
agent never posts anything itself in this design, since it has no
conversation to post into.

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
| **Flow-calls-agent, not agent-calls-flow** — trigger is SharePoint "When a file is created," not Copilot Studio's native child-flow trigger | Routes around a DLP policy that blocks `shared_powervirtualagents`. **This is a risk mitigation, not a cost optimization** — verify the connector this design *does* use (Copilot Studio "Run a topic") isn't grouped with the blocked one in your tenant before deploying (see the callout at the top of this guide). |
| Extraction via an **inline Prompt action configured directly on the topic**, not a separately published AI Builder catalog Prompt, and not an AI Builder call inside the flow | One fewer resource to create, publish, version, and administer — there is no AI Builder catalog object for this tool at all. Neither flow action nor topic action can trigger an AI Builder charge, structurally. **This does not eliminate the LLM cost of reading the PDF** — that call still happens inside the topic, billed as Copilot Studio generative/message consumption. Do not read this row as "free extraction." |
| Cell population via **Office Scripts** ("Run script"), a standard Excel Online (Business) action | No Premium connector and no custom Azure Function to write 17 cells — Office Scripts are included in standard Microsoft 365 licensing. |
| **One new file per review**, copied from your existing template | Deliberate (matches how the bank already packages appraisal reviews), not the lowest-cost option — the trade-off is one Copy File action and one Create Sharing Link action per run, small next to the generative cost already spent on extraction. |
| Template, destination, intake, and notification locations are **flow parameters you designate**, not hardcoded | You point the flow at wherever your team actually keeps each of these — no repo-provided values to keep in sync with reality. |
| **File-type/size validation moved into the flow** (`Validate_Upload`), ahead of the call to the agent | The SharePoint trigger fires unconditionally on any upload, so *something* has to reject bad files before the generative call — that gate used to be a chat-side check before the file ever reached a flow; now the flow is first in line, so the flow does it. A malformed or oversized upload never reaches `Call_Extraction_Agent`. |
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
| Your bank's **existing appraisal review template**, with a sheet named exactly `RE Collateral` and the cell layout in the table above | This tool copies and populates it — it does not create one for you |
| **Office Scripts** enabled for your tenant/site (on by default for most Microsoft 365 commercial tenants; confirm with your M365 admin if "Automate" doesn't appear in Excel Online) | Runs the cell-population script — standard M365 feature, no added license cost |
| A **SharePoint site and document library** for the template, one for completed reviews, and one for intake uploads (can all be the same site, different libraries) | Source, destination, and trigger locations you'll designate as flow parameters |
| **Excel Online (Business)**, **SharePoint**, and **Microsoft Teams** connections (standard, no Premium required) | Used by the flow to copy files, run the script, and post notifications |
| A **Teams channel** for completion/failure/rejection notifications, and optionally a Files tab pointed at the intake library | Where analysts see results — no bot conversation happens in this design |
| An account with **Environment Maker** (or higher) in the target Power Platform environment | To create the flow and agent |
| An account with **git** access, to clone this repository | To pull the reference files you'll build the flow and topic from |

---

## Part A — Designate template, destination, intake, and notification locations

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
3. **Choose or create an intake library.** This is new in this version —
   the folder analysts drop PDFs into, which triggers the flow. Note:
   - **Intake site URL**
   - **Intake folder path** — e.g.
     `/sites/CreditRisk/Shared Documents/Appraisal Review Intake`
4. **Identify the Teams channel for notifications.** Get its channel ID
   (Teams → the channel's **···** menu → **Get link to channel**, or via
   the Teams connector's own picker when configuring the flow action in
   Part E) — this is where `Shared-AppraisalReviewOrchestrator` posts every
   success, failure, and rejection message.
5. Confirm the account that will own the Power Automate flow (Part E) has
   **edit** access to the template's library (read is enough there, since
   the flow only copies it), the destination folder (write), and the
   intake folder (read, to trigger and fetch content), plus post access to
   the notification channel.

You'll paste these values into the flow's parameters in Part E.

---

## Part B — Add the inline extraction Prompt action to the topic

This is the extraction engine, and it lives entirely inside the Copilot
Studio topic — there is no separate AI Builder catalog object to create,
publish, or version for this tool. You'll do this while building the topic
in Part F; this section explains what that one step needs so Part F can
stay a checklist.

1. In the topic's action list (see `agent/appraisal-agent-topic.yaml`,
   step `extractFieldsInline`), add an action via **Add an action → AI
   Builder → Prompt** (the picker offers both "Use an existing prompt" and
   "Create a new prompt inline" — choose **inline**, not a saved catalog
   prompt).
2. Under **Model**, choose a GPT-class model available in your tenant's
   Prompt picker (prefer a lower-cost/mini tier if your tenant offers one —
   extraction is a well-structured task and does not need the largest
   model).
3. Add an **input variable** bound to this topic's declared `document`
   input (see Part C):
   - Name: `document`
   - Type: **File**
   - Value: the topic input, not a chat-collected attachment — there is no
     attachment-collection step in this version of the topic.
4. In the instructions box, paste the **Extraction Requirements** and
   **Output Requirements** sections from
   [`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md)
   (from "## Extraction Requirements" through the end of "## Output
   Requirements"), then reference the file input at the top: `Extract data
   from this appraisal review document: {document}`.
5. Set **Response format** to **JSON** and paste the same JSON schema shown
   in the "Output Requirements" example so the model's output is
   constrained to that shape.
6. Bind the action's output to a topic variable — `topic.extractionRawJson`
   — matching what the next step (`parseExtraction`, a `ParseJSON()` Power
   Fx expression) expects.
7. Click **Test** in the topic's test pane, upload a sample appraisal
   review PDF, and confirm the response is valid JSON matching the
   17-field schema before moving on.
8. There is nothing to publish separately here — saving and publishing the
   agent (Part F) publishes this action along with everything else in the
   topic.

---

## Part C — Configure the topic as a callable action

This is what makes `agent/appraisal-agent-topic.yaml` invocable by a flow
instead of by a chat message — the part of this design with the least
certain designer mechanics, since it's a newer capability than the
conversational topic authoring most Copilot Studio documentation covers.
Verify each step against your tenant's actual designer; the YAML file is a
best-effort reference, not something guaranteed to round-trip through the
YAML editor unmodified.

1. Create the topic (**Topics** → **Add a topic** → **Create from blank**),
   name it `Extract Appraisal Fields` (this exact name is what
   `extractionTopicName` in the flow's parameters must match).
2. In the topic's **Settings** panel, look for an **Inputs**/**Outputs**
   section (sometimes surfaced as "Variables" with an "Input"/"Output"
   scope toggle, depending on your Copilot Studio version). Add:
   - Input `document`, type **File**
   - Output `extractionJson`, type **String**
   - Output `parseSucceeded`, type **Boolean**
3. Remove or skip any conversational entry scaffolding the blank-topic
   template pre-populates (trigger phrases, a default greeting) — this
   topic is never matched by user input, so none of that applies. If your
   designer requires *some* trigger configuration to save the topic, set it
   to the least permissive/most inert option available rather than adding
   real trigger phrases, since a stray trigger phrase would make this
   callable topic also reachable by an ordinary chat message.
4. Build the three actions from `agent/appraisal-agent-topic.yaml` in
   order: the inline Prompt action (Part B), the `ParseJSON()` Power Fx
   variable assignment, and a `Not(IsError(...))` assignment for
   `parseSucceeded`. End the topic by returning both outputs — look for an
   "End the topic and return a value" / "Respond with outputs" option on
   the topic's final step, rather than `SendActivity` (there is nothing to
   send activity into).
5. Confirm the topic does **not** appear in whatever "topics available in
   conversation" list your designer shows for the agent's default
   orchestration — it should only be reachable as a callable action.

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

This flow now owns the entire run — trigger, calling the agent, writing
cells, and all analyst-facing Teams communication.

1. Go to [make.powerautomate.com](https://make.powerautomate.com) → **+
   Create** → **Automated cloud flow**.
2. Name it `Shared-AppraisalReviewOrchestrator`.
3. In the trigger search box, choose **SharePoint → "When a file is
   created (properties only)"** (or "When a file is created," depending on
   your connector version). Site Address: your **Intake site URL**.
   Library/Folder: your **Intake folder path** (both from Part A).

**Add these actions in order:**

**Action 1 — Compose (`Init_RunTimestamp`)**
- Inputs (expression): `utcNow()`

**Action 2 — SharePoint: "Get file properties"**
- Resolves the uploaded file's name and size from the trigger's `Id`
  output — needed for the validation check next.

**Action 3 — Compose (`Validate_Upload`)**
- Inputs (expression):
  ```
  and(endsWith(toLower(body('Get_file_properties')?['Name']), '.pdf'), less(body('Get_file_properties')?['Size'], 15728640))
  ```
  (replace `Get_file_properties` with your actual step name)

**Action 4 — SharePoint: "Get file content"**
- File Identifier: the trigger's `Id` output.
- This reads the bytes to pass to the agent — only worth doing for files
  that will pass validation, but simplest to place before the branch since
  Power Automate's designer makes conditional-content-reads awkward; if
  your tenant's connector supports lazy/on-demand content reads, move this
  inside the "valid" branch instead to avoid reading rejected files.

**Action 5 — Condition (`Condition_Is_Valid`)**
- Condition: `Validate_Upload` output is equal to `true`.

**If yes — branch actions in order:**

**Action 6 — AI... no.** Skip AI Builder entirely. Instead:

**Action 6 — Copilot Studio: "Run a topic"** (or your tenant's equivalent
action name for this connector — search "Copilot Studio" in the connector
list)
- Environment: your Power Platform environment.
- Bot: `Appraisal Review Extractor` (from Part F).
- Topic: `Extract Appraisal Fields` (from Part C).
- `document` input: the output of **Get file content** (Action 4).
- **This is the action to double-check against your DLP policy before
  building the rest of the flow** — if it's blocked too, stop here and
  reconsider the approach (see the callout at the top of this guide).

**Action 7 — Parse JSON**
- Content: `Run a topic`'s `extractionJson` output.
- Schema: paste the `properties` block from
  `flows/Shared-AppraisalReviewOrchestrator.json` →
  `actions.Condition_Is_Valid.actions.Parse_Agent_Response.inputs.schema`.

**Action 8 — Condition (`Condition_Extraction_Ok`)**
- Condition: `Run a topic`'s `parseSucceeded` output is equal to `true`.

**If yes — the write path (mirrors the previous version's flow):**

**Actions 9–15** — Compose `Format_Appraiser_Names`, Compose
`Format_City_State`, Compose `Build_Destination_File_Name`, SharePoint
"Copy file", SharePoint "Get file properties" (of the new copy), Excel
Online "Run script" (script parameters straight off `Parse JSON`'s output
this time, not `triggerBody()` — see
`actions.Condition_Is_Valid.actions.Condition_Extraction_Ok.actions.Populate_Review_Cells`
in the reference file for every expression), SharePoint "Create sharing
link." Same configuration notes as the previous version of this guide
applied to the equivalent actions — the only change is every
`triggerBody()?['x']` reference becomes `body('Parse_Agent_Response')?['x']`.

**Action 16 — Teams: "Post message in a channel" (`Post_Success_To_Teams`)**
- Team / Channel: your **notification channel** (Part A).
- Message: see `actions.Condition_Is_Valid.actions.Condition_Extraction_Ok.actions.Post_Success_To_Teams.inputs.body.body`
  for the exact expression — states what was created, flags missing
  fields, includes the workbook link.

**If no (extraction parse failed) — `Post_Extraction_Failure_To_Teams`:**
same Teams action, different message; see the reference file. No workbook
is created in this branch.

**If Action 5 was no (upload failed validation) — `Post_Rejection_To_Teams`:**
same Teams action again, explaining the file was rejected. The agent is
never called in this branch — no generative cost is spent on an invalid
upload.

**One error branch outside the main condition tree:**

**Compose (`Handle_Write_Failure`)**
- Configure **Run after**: `Condition_Is_Valid` **has failed** or **timed
  out** — catches anything that breaks inside either branch that isn't
  already handled by the three Teams-post branches above (e.g. Copy File
  or Run Script erroring out after a successful extraction).

4. **Save** the flow. Unlike the previous version, there is no trigger
   Outputs panel to configure — this flow's trigger is a standard
   SharePoint event, not Copilot Studio's child-flow trigger, so there is
   no caller waiting on a structured response.

---

## Part F — Publish the agent

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com),
   same environment as Parts A–E.
2. **Create** → **New agent** → **Skip to configure**.
3. Name: `Appraisal Review Extractor`. Description: *"Callable extraction
   topic for appraisal review PDFs — invoked by
   Shared-AppraisalReviewOrchestrator, not a conversational agent."*
4. **Instructions**: paste the full contents of
   `agent/appraisal-agent-instructions.md`.
5. Build the `Extract Appraisal Fields` topic per **Part C** and **Part B**.
6. **Settings** (gear icon) → **Advanced** → note the agent's **Bot ID** —
   this is `appraisalAgentId` in the flow's parameters (Part E).
7. **Publish** the agent. You do **not** need to enable the Teams channel
   for this agent in this design — nothing chats with it directly. If you
   want a fallback path to manually test the topic via chat during
   development, enabling Teams for testing purposes is fine, but it is not
   part of the production invocation path.
8. Back in **Shared-AppraisalReviewOrchestrator** (Part E), open the "Run a
   topic" action and confirm it now resolves the published bot and topic
   correctly in the picker (some connector versions require the agent to
   be published before it appears as a selectable target).

---

## Part G — Connect the intake Files tab and Teams notifications

1. In the Teams channel your credit risk team already uses, add a **Files**
   tab (**+** → **Files**, or drag-and-drop directly into the channel's
   existing Files tab) pointed at the **intake library** from Part A —
   Teams channels already have a Files tab backed by a SharePoint library;
   if the channel's default library isn't your intake library, add the
   intake library as an additional tab instead of trying to redirect the
   default one.
2. Confirm analysts can drop a file into that tab and see it land in the
   SharePoint library at the path you configured — this is the entire
   "trigger" surface for this tool now; there is no bot to message.
3. Confirm `Shared-AppraisalReviewOrchestrator`'s Teams action (Part E,
   Action 16 and the two failure-branch equivalents) is configured to post
   into this same channel, so results show up next to where the file was
   dropped.

---

## Part H — Test end-to-end

1. Drop a sample appraisal review PDF into the intake Files tab (or
   directly into the SharePoint intake folder).
2. Confirm in the flow's run history that
   `Shared-AppraisalReviewOrchestrator` triggered, `Validate_Upload`
   evaluated `true`, and `Run a topic` (Call_Extraction_Agent) succeeded.
3. Confirm a message appears in the Teams notification channel within
   about a minute, reporting "Created \<file name\>..." with a workbook
   link.
4. Open the link — the `RE Collateral` sheet should show all 17 cells
   populated (or `Not Stated` for anything genuinely absent from the
   source PDF), and every other sheet/cell in the template should be
   untouched.
5. Test with a PDF missing a review sign-off page — confirm `F31`/`F32`
   come back `Not Stated`, and the Teams message flags missing fields.
6. Test the guardrails: drop a non-PDF file and a file over 15 MB. Both
   should produce a rejection message in Teams, and the flow's run history
   should show `Run a topic` never executed for either (check
   `Condition_Is_Valid` evaluated `false` and the flow went straight to
   `Post_Rejection_To_Teams`).
7. Drop two PDFs for the same property on the same day and confirm two
   distinct workbook files (the timestamp suffix in the file name should
   differ).
8. **Specifically confirm the DLP question this whole design exists to
   answer**: open the successful run's details for the `Run a topic`
   action and confirm it actually executed rather than being silently
   blocked at the connector level (a DLP block sometimes surfaces as a
   generic connection error rather than an explicit policy message,
   depending on your tenant).

---

## Troubleshooting

**The flow never triggers when a file is dropped**
- Confirm the SharePoint trigger's site/folder in Part E step 3 exactly
  matches the intake library from Part A — a typo here means the trigger
  is watching the wrong (or a nonexistent) folder.
- SharePoint's "When a file is created" trigger polls rather than firing
  instantly in some tenants; wait a few minutes before assuming it's
  broken, then check the trigger's run history for polling activity even
  when no run was produced.

**`Run a topic` (Call_Extraction_Agent) fails immediately, especially with a
generic connection/authorization error**
- This is the failure mode to treat as a DLP block first, not a
  configuration bug — re-confirm with your Power Platform admin that the
  Copilot Studio "Run a topic" connector is actually allowed, not just
  assumed to be different from the blocked one. If it's blocked too, this
  whole design needs to fall back to a non-connector hand-off (e.g., the
  agent — or a person — writes results to a SharePoint list that a
  separately-triggered flow polls, rather than any direct connector call
  in either direction).
- If it's not a DLP block: confirm the agent (Part F) is published, the
  `appraisalAgentId` and `extractionTopicName` parameters exactly match
  your published agent and topic, and the environment ID matches where the
  agent actually lives.

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
  trigger itself, or `Get file properties`), no Teams action ever executes,
  and this looks identical to a silent failure from the analyst's side.

**Costs climbing faster than expected**
- Confirm `Validate_Upload` is still correctly rejecting oversized/non-PDF
  files before `Call_Extraction_Agent` runs — if someone edited the
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
