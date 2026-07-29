# Deployment Guide — Appraisal Review Extractor

**Audience:** bank credit risk team. **Trigger:** a Teams chat or channel
message with an appraisal review PDF attached. **Output:** a brand-new
Excel workbook for that review — a copy of the bank's own appraisal review
template with 17 cells populated — plus a link to it.

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [What this tool does](#what-this-tool-does)
3. [Why this design (cost rationale)](#why-this-design-cost-rationale)
4. [Prerequisites](#prerequisites)
5. [Part A — Designate the template and destination locations](#part-a--designate-the-template-and-destination-locations)
6. [Part B — Add the inline extraction Prompt action to the topic](#part-b--add-the-inline-extraction-prompt-action-to-the-topic)
7. [Part C — Add the Office Script to your template](#part-c--add-the-office-script-to-your-template)
8. [Part D — Build Shared-AppraisalCellWriter](#part-d--build-shared-appraisalcellwriter)
9. [Part E — Create the Appraisal Review Extractor agent in Copilot Studio](#part-e--create-the-appraisal-review-extractor-agent-in-copilot-studio)
10. [Part F — Add the agent to Teams](#part-f--add-the-agent-to-teams)
11. [Part G — Test end-to-end](#part-g--test-end-to-end)
12. [Troubleshooting](#troubleshooting)

---

## Repository Layout

```
Copilot/
├── agent/
│   ├── appraisal-agent-instructions.md   ← Appraisal Review Extractor system prompt
│   └── appraisal-agent-topic.yaml        ← Copilot Studio topic YAML (inline extraction + flow call)
├── flows/
│   ├── Shared-AppraisalCellWriter.json   ← Per-review workbook writer — no AI Builder connector
│   └── scripts/
│       └── PopulateAppraisalReviewCells.ts   ← Office Script run by the flow's "Run script" action
└── DEPLOYMENT.md
```

There is no `flows/packages/` directory and no template file shipped in
this repo. `Shared-AppraisalCellWriter` references your bank's own
template/destination paths — values that only exist after you designate
them in your own environment, so a portable `.zip` package can't
pre-populate them (see Part A and Part D). The workbook this tool writes
into is **your** existing appraisal review template, copied at runtime —
not anything stored here.

---

## What this tool does

An analyst attaches an appraisal review PDF to the **Appraisal Review
Extractor** bot in Teams. The bot **extracts the 17 credit-risk data points
itself, inline, in the conversation** — via a Prompt action configured
directly on the topic step, not a separately published AI Builder catalog
Prompt and not a call the flow makes (full list and JSON contract in
[`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md)).
Once the extraction is parsed and validated, the topic hands only the
finished values to a Power Automate flow that **copies the bank's own
appraisal review template** to a new file and writes the values into that
copy's named cells on the `RE Collateral` sheet. The agent then replies in
Teams with a plain-language summary, any fields it could not find, and a
link to the new workbook.

This split matters for cost, not just architecture: the flow
([`flows/Shared-AppraisalCellWriter.json`](flows/Shared-AppraisalCellWriter.json))
has no AI Builder connector at all — it cannot spend a generative credit
under any input, because it has no action capable of calling a model. The
one LLM call this tool makes happens earlier, inside the topic, and is
billed as Copilot Studio generative/message consumption instead of AI
Builder credits. See "Why this design (cost rationale)" below for what that
trade actually buys you.

Every review gets its own file — this is intentional (see below), not a
cost-saving shortcut. Nothing about the template's design, its other
sheets, or its formulas is touched; the tool only ever writes to the 17
cells listed in `_meta.cellMap` inside
[`flows/Shared-AppraisalCellWriter.json`](flows/Shared-AppraisalCellWriter.json):

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

| Choice | Why it keeps cost down |
|---|---|
| Extraction via an **inline Prompt action configured directly on the topic**, not a separately published AI Builder catalog Prompt, and not an AI Builder call inside the flow | One fewer resource to create, publish, version, and administer — there is no AI Builder catalog object for this tool at all. The flow's connector list is SharePoint + Excel Online only (see `_meta.connectors` in `flows/Shared-AppraisalCellWriter.json`), so it is structurally incapable of triggering an AI Builder charge. **This does not eliminate the LLM cost of reading the PDF** — that call still happens, now inside the topic, billed as Copilot Studio generative/message consumption instead of AI Builder credits. Do not read this row as "free extraction." |
| Flow triggered by Copilot Studio's **native child-flow trigger** ("When Copilot Studio calls a flow"), not an HTTP Request trigger | Avoids requiring a Power Automate **Premium** license just to receive the call. |
| Cell population via **Office Scripts** ("Run script"), a standard Excel Online (Business) action | No Premium connector and no custom Azure Function to write 17 cells — Office Scripts are included in standard Microsoft 365 licensing. |
| **One new file per review**, copied from your existing template | This is a deliberate design choice (matching how the bank already packages appraisal reviews), not the lowest-cost option — the trade-off is one Copy File action and one Create Sharing Link action per run, a small, predictable cost next to the generative cost already spent on extraction. |
| Template and destination location are **flow parameters you designate**, not hardcoded | You point the flow at wherever your team actually keeps the template and wherever completed reviews should be saved — no repo-provided template to keep in sync with the real one. |
| **15 MB / 40-page cap** enforced in the Copilot Studio topic before extraction is invoked | A malformed or oversized upload is rejected for free, before it can burn any generative consumption or create a stray file. |
| **No retries** on a failed extraction | A failure is surfaced to the analyst immediately instead of silently doubling the cost on a document likely to fail again. |
| Extraction failures never reach the flow | The topic parses and validates the model's JSON (`checkParsedOk` in `agent/appraisal-agent-topic.yaml`) before calling `Shared-AppraisalCellWriter` at all — a bad extraction never spends a Copy File / Run Script / Create Sharing Link action, and never leaves an orphaned partially-written workbook in the destination folder. |

The only new recurring costs are **Copilot Studio generative/message
consumption per PDF processed** (check your tenant's included message
allocation and overage pricing in the Power Platform admin center before
rollout — there is no separate AI Builder credit balance to track for this
tool, since it never calls AI Builder) and whatever ordinary **Copilot
Studio message** consumption your licensing already meters for the rest of
the conversation (the acknowledgment and final reply). SharePoint storage
for one workbook per review is typically negligible (each file is a few
hundred KB).

> **A genuinely AI-free alternative exists, but it isn't this design.** The
> only way to remove the generative cost entirely — not just move it off
> the AI Builder meter — is regex/pattern-based text extraction against
> known anchors in the PDF, with no model call anywhere. That trades away
> reliability across appraisal firms with different report formats for a
> hard zero on the LLM line item. This repo does not implement that
> variant; ask if you want it scoped separately.

---

## Prerequisites

| Requirement | Why it is needed |
|---|---|
| **Microsoft Copilot Studio** license, with generative/message capacity sufficient for inline Prompt actions | Runs both the conversation and the extraction — see cost note above. No separate AI Builder capacity is required; this design never calls AI Builder. |
| Your bank's **existing appraisal review template**, with a sheet named exactly `RE Collateral` and the cell layout in the table above | This tool copies and populates it — it does not create one for you |
| **Office Scripts** enabled for your tenant/site (on by default for most Microsoft 365 commercial tenants; confirm with your M365 admin if "Automate" doesn't appear in Excel Online) | Runs the cell-population script — standard M365 feature, no added license cost |
| A **SharePoint site and document library** for the template, and one for completed reviews (can be the same site/library) | Source and destination locations you'll designate as flow parameters |
| **Excel Online (Business)** and **SharePoint** connections (standard, no Premium required) | Used by the flow to copy files and run the script |
| **Teams** access to add/pin the agent to a channel or chat | Where analysts interact with the tool |
| An account with **Environment Maker** (or higher) in the target Power Platform environment | To create the flow, prompt, and agent |
| An account with **git** access, to clone this repository | To pull the reference files you'll build the flow and topic from |

---

## Part A — Designate the template and destination locations

Nothing is provisioned here — you're just choosing (and writing down) where
things already live, or should be saved:

1. **Locate your existing template.** Find the SharePoint site and file
   path of the appraisal review template your team already uses (the one
   with the `RE Collateral` sheet and the cells listed above). Note:
   - **Template site URL** — e.g. `https://yourbank.sharepoint.com/sites/CreditRisk`
   - **Template file path** — the server-relative path to the file, e.g.
     `/sites/CreditRisk/Shared Documents/Templates/Appraisal Review Template.xlsx`
2. **Choose where completed reviews should be saved.** Can be a folder in
   the same site/library or a different one. Note:
   - **Destination site URL**
   - **Destination folder path** — e.g.
     `/sites/CreditRisk/Shared Documents/Appraisal Reviews`
3. Confirm the account that will own the Power Automate flow (Part D) has
   **edit** access to both the template's library (read is enough there,
   since the flow only copies it) and the destination folder (needs write
   access).

You'll paste these four values into the flow's parameters in Part D.

---

## Part B — Add the inline extraction Prompt action to the topic

This is the extraction engine, and it lives entirely inside the Copilot
Studio topic — there is no separate AI Builder catalog object to create,
publish, or version for this tool. You'll do this while building the topic
in Part E; this section explains what that one step needs so Part E can
stay a checklist.

1. In the topic's action list (see `agent/appraisal-agent-topic.yaml`,
   step `extractFieldsInline`), after the file-size/type validation and
   before the call to `Shared-AppraisalCellWriter`, add an action via
   **Add an action → AI Builder → Prompt** (the picker offers both "Use an
   existing prompt" and "Create a new prompt inline" — choose **inline**,
   not a saved catalog prompt).
2. Under **Model**, choose a GPT-class model available in your tenant's
   Prompt picker (prefer a lower-cost/mini tier if your tenant offers one —
   extraction is a well-structured task and does not need the largest
   model).
3. Add an **input variable** bound to the attachment collected in the
   preceding step:
   - Name: `document`
   - Type: **File**
   - Value: `topic.AppraisalFile`
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
   **agent** (Part E, step 8) publishes this action along with everything
   else in the topic. If you later want to reuse this exact prompt in
   another topic or agent, you can promote it to a saved AI Builder Prompt
   at that point, but doing so reintroduces a standalone AI Builder
   resource and is a deliberate trade you'd be opting into, not something
   this design requires.

---

## Part C — Add the Office Script to your template

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

## Part D — Build Shared-AppraisalCellWriter

> **Reference file:** `flows/Shared-AppraisalCellWriter.json`

This flow is deliberately smaller than a typical extraction pipeline — it
never sees the PDF, never calls a model, and has no AI Builder connector.
It receives 17 already-extracted field values (plus the requestor's
name/email) from the topic and does one thing: write them into a new
workbook.

1. Go to [make.powerautomate.com](https://make.powerautomate.com) → **+
   Create** → **Automated cloud flow**.
2. Name it `Shared-AppraisalCellWriter`.
3. In the trigger search box, type **"Power Virtual Agents"** (shows as
   *"When Power Virtual Agents calls a flow"* — this is Copilot Studio's
   native child-flow trigger) and select it. Click **Create**.
4. On the trigger card, click **+ Add an input** for each of the 17 fields
   plus `requestedByName` and `requestedByEmail` — all as **Text** type
   (see `flows/Shared-AppraisalCellWriter.json` → `trigger.inputs.schema`
   for the exact list and names). There is no `fileContent` input on this
   flow — the topic never sends it the PDF.

**Add these actions in order:**

**Action 1 — Compose (`Init_WriteTimestamp`)**
- Inputs (expression): `utcNow()`

**Action 2 — Compose (`Format_City_State`)**
- Inputs (expression):
  ```
  concat(coalesce(triggerBody()?['city'], 'Not Stated'), ', ', coalesce(triggerBody()?['state'], 'Not Stated'))
  ```

**Action 3 — Compose (`Build_Destination_File_Name`)**
- Inputs (expression): see
  `flows/Shared-AppraisalCellWriter.json` → `actions.Build_Destination_File_Name.inputs`
  — builds a unique file name like `Appraisal Review - 4200 Colony Road -
  20260729-143022.xlsx` from the street address and a timestamp, with
  slashes/colons/question marks stripped so it's a valid file name.

**Action 4 — SharePoint: "Copy file"**
- Site Address: paste your **Template site URL** (Part A) directly, or use
  a flow-level parameter if your tenant's designer supports one
  (**···** menu → this flow's **Settings**, or the classic **peek code**
  view — not every tenant exposes named parameters in the visual designer;
  if yours doesn't, hardcode the four Part A values directly into this
  action and the ones that follow instead of referencing
  `parameters(...)`).
- File to Copy: your **Template file path**
- Destination Site Address: your **Destination site URL**
- Destination Folder: your **Destination folder path**
- Destination File Name (if your connector version exposes it): the output
  of `Build_Destination_File_Name`
- If another file already exists: **Rename** (safety net — the timestamp
  in the file name already makes a collision very unlikely)

**Action 5 — SharePoint: "Get file properties"**
- Site Address: your **Destination site URL**
- File Identifier: the path/URL returned by the Copy File action's output
  (exact dynamic-content field name depends on your connector version —
  look for something like *"Full Path"* or *"Item ID"*)
- This resolves the drive/item identifiers the next two actions need.

**Action 6 — Excel Online (Business): "Run script"**
- Location: **SharePoint Site** → your **Destination site URL**
- Document Library: the destination library
- File: pick **dynamic content** and select the file identifier from
  **Get file properties** (Action 5), not a fixed file — this must resolve
  to the *new* copy, not the template.
- Script: `PopulateAppraisalReviewCells` (from Part C — it will only appear
  in this picker if Part C was completed on this exact file or the
  template it was copied from)
- Script parameters: map each parameter directly to the matching **trigger
  input** — see `flows/Shared-AppraisalCellWriter.json` →
  `actions.Populate_Review_Cells.inputs.body.scriptParameters` for the
  exact expression for each of the 17 fields. There is no `Parse JSON` step
  to reference here; every value comes straight off `triggerBody()`,
  wrapped in `coalesce(..., 'Not Stated')` as a last-resort default in case
  a field arrives blank.

**Action 7 — SharePoint: "Create sharing link for a file or folder"**
- Site Address: your **Destination site URL**
- File Identifier: the identifier from Action 5
- Link Type: **View**
- Link Scope: **Organization** (adjust to your data classification policy)

**Action 8 — Compose (`Build_Review_Summary`)**
- Inputs (expression): see `flows/Shared-AppraisalCellWriter.json` →
  `actions.Build_Review_Summary.inputs` — builds the one-line summary sent
  back to Teams.

**Action 9 — Compose (`Build_Response_Body`)**
- Inputs: a JSON object with `status`, `errorMessage`, `reviewFileUrl`,
  `reviewFileName`, `reviewSummary` — see the reference file for the exact
  expression for each. Note `missingFields` / `needsManualReview` /
  `extractionNotes` are **not** built here — the topic already has them
  from its own parse of the extraction JSON, so this flow doesn't need to
  round-trip them.

**One error branch (there is no extraction step in this flow to fail):**

**Action 10 — Compose (`Handle_Write_Failure`)**
- Click the **"..."** menu on the **Copy File** action (Action 4) → **Add a
  parallel branch**, add this Compose action there, and configure **Run
  after**: Copy File, Get File Properties, Run Script, **or** Create
  Sharing Link **has failed** (check "has failed" on all four).
- Inputs: `status: "error"` with an error message pulled from whichever
  action actually failed — see the reference file.

5. Click the trigger card → **Outputs** panel → add an output for each of:
   `status`, `errorMessage`, `reviewFileUrl`, `reviewFileName`,
   `reviewSummary`. For each, bind it to the matching field from
   **Build_Response_Body** — since a failed run produces its value from
   **Handle_Write_Failure** instead, wrap each binding in `coalesce()`
   across both Compose outputs (or, if your tenant's designer doesn't
   support that in the Outputs panel directly, add one final Compose step
   that does the `coalesce()` and bind every trigger output to a field on
   that single step).
6. **Save** the flow.

---

## Part E — Create the Appraisal Review Extractor agent in Copilot Studio

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com),
   same environment as Parts A–D.
2. **Create** → **New agent** → **Skip to configure**.
3. Name: `Appraisal Review Extractor`. Description: *"Extracts credit-risk
   data points from appraisal review PDFs attached in Teams and creates a
   populated copy of the bank's appraisal review template."*
4. **Instructions**: paste the full contents of
   `agent/appraisal-agent-instructions.md`.
5. **Topics** → **Add a topic** → **Create from blank** → name it
   `Extract Appraisal Review` → **More options (···)** → **Open YAML
   editor** → select all, delete, paste the contents of
   `agent/appraisal-agent-topic.yaml` → **Save**.
6. The YAML references an inline extraction step (`extractFieldsInline`)
   that the YAML editor cannot fully create for you — generative Prompt
   actions are configured through the visual designer, not round-tripped
   through pasted YAML. Open that step in the visual designer and complete
   it per **Part B** above (model choice, `document` input binding,
   instructions, response schema, output variable). If the YAML paste
   leaves a placeholder or an unresolved action where `extractFieldsInline`
   should be, that is expected — add the action fresh at that point in the
   sequence rather than trying to make the pasted placeholder resolve.
7. Confirm the **InvokeFlowAction** step (`callWriterFlow`) is linked to
   the `Shared-AppraisalCellWriter` flow from Part D — if the YAML paste
   doesn't auto-bind it, open that step in the visual designer and select
   the flow from the picker. Confirm every input on that step maps to a
   `topic.extraction.*` field (per the YAML) and not to the raw file — this
   flow should never receive `topic.AppraisalFile`.
8. **Settings** (gear icon) → **Security** → confirm authentication is
   appropriate for your tenant (Teams users authenticate via Microsoft
   Entra ID automatically in the Teams channel).
9. **Publish** the agent.

---

## Part F — Add the agent to Teams

1. In Copilot Studio, go to **Channels** → **Microsoft Teams**.
2. Turn the Teams channel **on**. Copilot Studio generates a Teams app
   package for the agent.
3. Choose how the credit risk team will use it:
   - **Direct chat**: click **Open bot**, then have each analyst add it as
     a personal app in Teams (search for it by name, or your Teams admin
     can pre-install it tenant-wide).
   - **Shared channel** (recommended for a team workflow everyone can
     watch): download the app package, have your Teams admin upload it via
     **Teams admin center → Manage apps** (or **Org-wide app settings** if
     custom app upload is restricted), then add the app to the credit risk
     team's channel. Analysts trigger it by @mentioning the bot and
     attaching the PDF.
4. Confirm the trigger phrases from the topic YAML work in Teams (e.g.
   `@Appraisal Review Extractor Extract appraisal`) — Teams requires an
   @mention or DM to start a conversation with the bot; it does not read
   every message in a channel.

---

## Part G — Test end-to-end

1. In Teams, message the bot (or @mention it in the channel) with the
   phrase `Extract appraisal`.
2. When prompted, attach a sample appraisal review PDF.
3. Confirm:
   - The bot acknowledges receipt and reports "Created \<file name\>..."
     within about a minute.
   - A new file appears in the destination folder from Part A, named from
     the street address and a timestamp.
   - Open the link from the Teams reply — the `RE Collateral` sheet should
     show all 17 cells populated (or `Not Stated` for anything genuinely
     absent from the source PDF), and every other sheet/cell in the
     template should be untouched.
   - If you intentionally test with a PDF missing a review sign-off page,
     confirm `F31`/`F32` come back `Not Stated`, `missingFields` lists
     them, and the Teams reply flags "needs manual verification."
4. Test the guardrails: attach a non-PDF file (should be rejected before
   extraction is invoked) and, if you have one, a file over 15 MB (should
   also be rejected before extraction — check the topic's test/analytics
   pane to confirm the inline Prompt action never ran, and the flow's run
   history to confirm `Shared-AppraisalCellWriter` was never triggered).
5. Run it twice for the same property on the same day and confirm you get
   two distinct files (the timestamp suffix in the file name should differ).
6. Confirm the split: in the flow's run history for `Shared-
   AppraisalCellWriter`, open a successful run and check its trigger
   inputs — you should see the 17 already-extracted text values and the
   requestor's name/email, never a file. There should be no AI Builder
   action anywhere in this flow's run details, because there is no AI
   Builder action in the flow.

---

## Troubleshooting

**The inline Prompt action (`extractFieldsInline`) fails or times out**
- Confirm the action's model selection is still valid for your tenant —
  models available in the Prompt picker can change; a model that was
  selectable when you built this may need to be re-picked.
- Open the PDF manually — if it's a scanned image with no text layer, the
  model cannot read it. Route these to manual entry.
- Check your tenant's Copilot Studio generative/message consumption in the
  Power Platform admin center — a depleted allocation fails inline Prompt
  actions the same way a depleted AI Builder credit pool would have under
  the old design; there is no separate AI Builder balance to check here,
  since this design never calls AI Builder.

**`checkParsedOk` fails / topic reports "the model's response could not be
read as valid data"**
- Open the topic's test pane and inspect `topic.extractionRawJson` on the
  failed run — the model may have returned prose instead of JSON. Re-open
  the `extractFieldsInline` action, confirm **Response format** is set to
  **JSON**, confirm the pasted schema still exactly matches the "Output
  Requirements" example in `agent/appraisal-agent-instructions.md`, and
  re-test with Part B step 7's sample PDF.
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
  template it was copied from) — confirm Part C was done on the correct
  file, and that the script is named exactly `PopulateAppraisalReviewCells`.
- `"Worksheet 'RE Collateral' was not found"` — the template's sheet is
  named differently than expected. Either rename the sheet to
  `RE Collateral` or edit the sheet name in
  `flows/scripts/PopulateAppraisalReviewCells.ts` and re-save the script in
  Excel.
- A cell shows the literal text `Not Stated` instead of the extracted
  value — check `topic.extraction` on the run in the topic's test/analytics
  pane for that field; the model likely didn't find it in the source PDF.
  This flow only ever writes what the topic sent it — it has no visibility
  into the original extraction, so the fix (if any) is in the prompt
  instructions or the source document, not in this flow.

**Create Sharing Link step fails, or the Teams reply has no link**
- Confirm the flow's SharePoint connection has sharing permissions on the
  destination library (some tenants restrict link creation by policy).
- Check `Get_New_File_Properties`' output — if the drive/item identifiers
  are empty, Copy File likely returned a path format this step doesn't
  parse the way your tenant's connector version expects; adjust the
  dynamic-content binding to match the actual output fields shown in your
  designer.

**Teams reply never arrives / flow doesn't run**
- Confirm **Part D step 5** — the trigger's Outputs — is fully configured
  and every output resolves through the failure branch, not just the
  success path. A "When Power Virtual Agents calls a flow" trigger with no
  bound outputs returns nothing to the topic, which then shows a blank or
  generic error.
- Confirm the topic's `callWriterFlow` step is bound to the correct flow
  (Copilot Studio topics silently do nothing if the flow reference is
  unresolved after a YAML paste).
- If the reply never arrives but the flow never even shows a run in its run
  history, the break is upstream of the flow — check `extractFieldsInline`
  and `checkParsedOk` in the topic first; a parse failure ends the dialog
  before the flow is ever called (by design — see the cost rationale
  above).

**Costs climbing faster than expected**
- Check whether the 15 MB / 40-page guardrail in the topic YAML is still in
  place — if someone edited the topic and removed it, oversized documents
  can consume disproportionate generative consumption before extraction
  even reaches the parse step.
- Confirm `checkParsedOk` in the topic and `Handle_Write_Failure` in the
  flow are both still wired up correctly so failed runs return immediately
  rather than looping or leaving orphaned partially-copied files in the
  destination folder.
- Pull the Copilot Studio message/generative consumption report for this
  agent specifically (Power Platform admin center → Copilot Studio
  analytics) rather than assuming a spike is this tool — a shared
  environment message allocation is consumed by every agent in it, not
  just this one.
