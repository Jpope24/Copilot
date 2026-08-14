# Deployment Guide — Appraisal Review Extractor

**Audience:** bank credit risk team. **Trigger:** a menu item in the Teams
channel message compose box — an analyst picks this workflow, uploads the
appraisal review PDF directly into its form, and runs it. **Output:** a
brand-new Excel workbook for that review — a copy of the bank's own
appraisal review template with 17 cells populated — posted as a link to a
Teams channel.

> **Why there's no Copilot Studio agent in this design.** Two earlier
> versions of this tool tried to involve a Copilot Studio agent — first
> with the agent calling this flow (blocked by a tenant DLP policy on the
> `shared_powervirtualagents` connector), then with this flow calling the
> agent instead (`Execute Agent and wait`, which worked as a connector call
> but had no working way to get a file attachment *into* the agent's topic
> logic — a Question node's File entity only slot-fills from a message
> *after* the one that triggers the topic, and Execute Agent delivers the
> file in the same single turn as the trigger, so it never resolved). This
> version drops the agent entirely: the extraction call happens via an
> **AI Builder Prompt action inside this flow**, directly on the file this
> flow's own trigger already received. No second system ever needs the
> file handed to it, which sidesteps both problems at once — and removes
> every DLP question this tool has needed to worry about, since none of
> the remaining connectors (Teams, SharePoint, Excel Online, AI Builder)
> are the one that was blocked.

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [What this tool does](#what-this-tool-does)
3. [Why this design (cost rationale)](#why-this-design-cost-rationale)
4. [Prerequisites](#prerequisites)
5. [Part A — Designate template, destination, and notification locations](#part-a--designate-template-destination-and-notification-locations)
6. [Part B — Create the AI Builder Prompt](#part-b--create-the-ai-builder-prompt)
7. [Part C — Add the Office Script to your template](#part-c--add-the-office-script-to-your-template)
8. [Part D — Build Shared-AppraisalReviewOrchestrator](#part-d--build-shared-appraisalrevieworchestrator)
9. [Part E — Make the workflow available in Teams](#part-e--make-the-workflow-available-in-teams)
10. [Part F — Test end-to-end](#part-f--test-end-to-end)
11. [Troubleshooting](#troubleshooting)

---

## Repository Layout

```
Copilot/
├── EXTRACTION-SPEC.md                    ← Field list + JSON schema, pasted into the AI Builder Prompt
├── flows/
│   ├── Shared-AppraisalReviewOrchestrator.json   ← The whole tool: trigger, extraction, cell writes, Teams notification
│   └── scripts/
│       └── PopulateAppraisalReviewCells.ts   ← Office Script run by the flow's "Run script" action
└── DEPLOYMENT.md
```

There is no `agent/` directory, no `flows/packages/` directory, and no
template file shipped in this repo. `Shared-AppraisalReviewOrchestrator`
references your bank's own template/destination paths and a Teams
notification channel — values that only exist after you designate them in
your own environment. The workbook this tool writes into is **your**
existing appraisal review template, copied at runtime — not anything
stored here.

---

## What this tool does

An analyst opens the compose box in the credit risk Teams channel, selects
**Shared-AppraisalReviewOrchestrator** from the built-in
Workflows/Power Automate flow picker, uploads the appraisal review PDF
directly into the form that appears, and runs it. That's the entire
trigger surface — no bot, no conversation, no intake folder to monitor.

The flow checks the upload is a `.pdf` under roughly 15 MB, and — only if
valid — calls a custom **AI Builder Prompt** (`Extract_With_AI_Builder`)
directly on the file content, extracting the 17 credit-risk data points in
one call (full list and JSON contract in
[`EXTRACTION-SPEC.md`](EXTRACTION-SPEC.md)). It then **copies the bank's
own appraisal review template** to a new file, writes the values into that
copy's named cells on the `RE Collateral` sheet, and **posts to a
designated Teams channel** with a plain-language summary, any fields it
could not find, and a link to the new workbook. A rejected upload or a
failed extraction each get their own post to that same channel.

This is a single flow, start to finish — no agent, no second system the
file has to be handed to. That's a direct consequence of two earlier
designs not panning out; see the callout at the top of this guide.

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
| **No Copilot Studio agent anywhere** | Removes every DLP question this tool has had to worry about — none of the remaining connectors (Teams, SharePoint, Excel Online, AI Builder) are the one a previous version got blocked on. One fewer resource to create, publish, and maintain, and one fewer connector-compatibility question to verify per tenant. |
| Extraction via an **AI Builder Prompt**, not a new Azure OpenAI or Azure AI Document Intelligence resource | Reuses AI Builder capacity your Power Platform/Copilot Studio licensing already includes, rather than paying for a separate Azure resource with its own meter and ops overhead. |
| **Trigger is an Instant cloud flow with a File input,** surfaced as a Teams menu item — not an automatic file-drop or channel-message trigger | The flow only runs when an analyst deliberately opens it and uploads a file. Nothing runs (and nothing is spent) until someone asks for it. |
| Cell population via **Office Scripts** ("Run script"), a standard Excel Online (Business) action | No Premium connector and no custom Azure Function to write 17 cells — Office Scripts are included in standard Microsoft 365 licensing. |
| **One new file per review**, copied from your existing template | Deliberate (matches how the bank already packages appraisal reviews), not the lowest-cost option — the trade-off is one Copy File action and one Create Sharing Link action per run, small next to the AI Builder cost already spent on extraction. |
| Template and destination locations are **flow parameters you designate**, not hardcoded | You point the flow at wherever your team actually keeps each of these — no repo-provided values to keep in sync with reality. |
| **Upload validated before AI Builder is ever called** (`Validate_Upload`: filename and approximate size) | A non-PDF or oversized upload never reaches `Extract_With_AI_Builder` — rejected for the cost of a Compose action, not an AI Builder credit. |
| **No retries** on a failed extraction | A failure is posted to Teams immediately instead of silently doubling AI Builder credit spend on a document likely to fail again. |

### What it actually costs per document

Real, tenant-measured numbers beat estimates here — **AI Builder's own Test
screen shows credits consumed per run before you build anything**, and
testing doesn't bill. Build the Prompt (Part B), click **Test**, upload a
real appraisal PDF, and read the credit count directly.

As a rough planning figure: AI Builder's pay-as-you-go rate is
**1 Copilot Credit = $0.01**, and a typical GPT-4o-mini prompt runs
roughly 3–5 credits. An appraisal PDF (5–15 pages, plus the ~800–1,000
token extraction instruction) is larger than a "typical" prompt, so budget
more — call it **$0.15–$0.50 per document** until you've measured your own
actual documents, not this estimate. At realistic credit-risk volumes (tens
to low hundreds of appraisals a month) this is a small line item.

**One licensing change to plan around:** Microsoft is removing seeded AI
Builder credits (the allocation bundled into Premium Power Platform
licenses) in November 2026, and new customers can no longer buy the AI
Builder capacity add-on — only Copilot Credits. If your tenant currently
relies on seeded credits, confirm with your licensing admin what your
position looks like after that change before rollout.

---

## Prerequisites

| Requirement | Why it is needed |
|---|---|
| **AI Builder** capacity (included/trial credits, or purchased Copilot Credits) | Runs the extraction prompt — see cost note above |
| The **Teams Workflows/Power Automate app** available in your tenant (on by default for most Microsoft 365 commercial tenants) | This is how analysts see and run this flow from the message compose box — confirm with your Teams admin if it doesn't appear |
| Your bank's **existing appraisal review template**, with a sheet named exactly `RE Collateral` and the cell layout in the table above | This tool copies and populates it — it does not create one for you |
| **Office Scripts** enabled for your tenant/site (on by default for most Microsoft 365 commercial tenants; confirm with your M365 admin if "Automate" doesn't appear in Excel Online) | Runs the cell-population script — standard M365 feature, no added license cost |
| A **SharePoint site and document library** for the template, and one for completed reviews (can be the same site/library) | Source and destination locations you'll designate as flow parameters |
| **Excel Online (Business)**, **SharePoint**, **AI Builder**, and **Microsoft Teams** connections (standard, no Premium required) | Used by the flow's actions |
| A **Teams channel** for result notifications | Where analysts see outcomes — this trigger type has no specific message to reply into, so results go to a fixed channel |
| An account with **Environment Maker** (or higher) in the target Power Platform environment | To create the flow and the Prompt |
| An account with **git** access, to clone this repository | To pull the reference files you'll build the flow from |

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
   Part D) — this is where `Shared-AppraisalReviewOrchestrator` posts every
   success, failure, and rejection message. Typically the same channel
   analysts will launch the workflow from.
4. Confirm the account that will own the Power Automate flow (Part D) has
   **edit** access to the template's library (read is enough there, since
   the flow only copies it), the destination folder (write), and post
   access to the notification channel.

You'll paste these values into the flow's parameters in Part D.

---

## Part B — Create the AI Builder Prompt

This is the extraction engine.

1. Go to [make.powerautomate.com](https://make.powerautomate.com) (or
   [make.powerapps.com](https://make.powerapps.com)) → **AI Builder** →
   **Prompts** → **+ Create a new prompt** → **Start from scratch**.
2. Name it `Appraisal Review Field Extraction`.
3. Under **Model**, choose a GPT-class model available in your tenant's AI
   Builder Prompt list (prefer a lower-cost/mini tier if your tenant offers
   one — extraction is a well-structured task and does not need the
   largest model).
4. Add an **input variable**:
   - Name: `document`
   - Type: **File**
5. In the prompt instructions box, paste the **Extraction Requirements**
   section from [`EXTRACTION-SPEC.md`](EXTRACTION-SPEC.md) (from
   "## Extraction Requirements" through "### Extraction standards"), then
   reference the file input at the top: `Extract data from this appraisal
   review document: {document}`.
6. Set the **Response format** to **JSON** and paste the JSON schema shown
   in `EXTRACTION-SPEC.md`'s "Output Requirements" section so the model's
   output is constrained to that shape.
7. Click **Test**, upload a sample appraisal review PDF, and confirm:
   - The response is valid JSON matching the 17-field schema.
   - **Note the credits consumed** — this is your real, tenant-specific
     per-document cost (see "What it actually costs per document" above).
8. **Save** and **Publish** the prompt.
9. Copy the prompt's GUID from the browser URL
   (`.../prompts/<PROMPT_GUID>/edit`) — this is `aiBuilderPromptId` in
   Part D.

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

## Part D — Build Shared-AppraisalReviewOrchestrator

> **Reference file:** `flows/Shared-AppraisalReviewOrchestrator.json`

1. Go to [make.powerautomate.com](https://make.powerautomate.com) → **+
   Create** → **Instant cloud flow**.
2. Name it `Shared-AppraisalReviewOrchestrator`.
3. Choose trigger **"Manually trigger a flow."** Click **Create**.
4. On the trigger card, click **+ Add an input → File**, name it
   `document`. **Confirmed against a real tenant:** this resolves at
   runtime to an *object* — `{"contentBytes": "<base64>", "name":
   "<filename>"}` — not a plain base64 string and not two separate flat
   inputs. Every expression below drills into `?['document']?['contentBytes']`
   or `?['document']?['name']` accordingly; don't reference
   `triggerBody()?['document']` directly expecting a plain string.

**Add these actions in order:**

**Action 1 — Compose (`Init_RunTimestamp`)**
- Inputs (expression): `utcNow()`

**Action 2 — Compose (`Validate_Upload`)**
- Inputs (expression):
  ```
  and(endsWith(toLower(coalesce(triggerBody()?['document']?['name'], '')), '.pdf'), less(mul(length(triggerBody()?['document']?['contentBytes']), 0.75), 15728640))
  ```
  The `0.75` factor approximates base64-to-byte size — confirm empirically
  against a real upload in your tenant before trusting the 15 MB boundary
  precisely.

**Action 3 — Condition (`Condition_Is_Valid`)**
- Condition: `Validate_Upload` output equals `true`.

**If yes — branch actions in order:**

**Action 4 — AI Builder: "Predict"** (search "AI Builder" in the connector
list, action **Predict**, or your tenant's equivalent "Run a prompt" action)
- Prompt: select `Appraisal Review Field Extraction` (from Part B)
- `document` input: the expression
  `triggerBody()?['document']?['contentBytes']`

**Action 5 — Parse JSON**
- Content: the output of the AI Builder Predict action
- Schema: paste the `properties` block from
  `flows/Shared-AppraisalReviewOrchestrator.json` →
  `actions.Condition_Is_Valid.actions.Parse_Extraction_Result.inputs.schema`

**Action 6 — Compose (`Format_Appraiser_Names`)**
- **+ New step** → search **"Compose"** → select the **Compose** action
  (Data Operation connector).
- Rename it (**"..."** on the action card → **Rename**) to
  `Format_Appraiser_Names`.
- Click into the **Inputs** field, switch to the **Expression** tab (next
  to Dynamic content), and enter exactly:
  ```
  join(coalesce(body('Parse_JSON')?['appraiserNames'], createArray('Not Stated')), '; ')
  ```
  Replace `Parse_JSON` with the **actual name** your Parse JSON action from
  Action 5 shows in the designer — if you renamed it to
  `Parse_Extraction_Result` (matching the reference file), use that
  instead. Click **OK**/**Add**.
- This joins the `appraiserNames` array (e.g. `["Jane R. Whitfield, MAI"]`)
  into a single semicolon-separated string for the Excel cell, since the
  cell holds text, not an array.

**Action 7 — Compose (`Format_City_State`)**
- **+ New step** → **Compose**. Rename to `Format_City_State`.
- Inputs, **Expression** tab:
  ```
  concat(coalesce(body('Parse_Extraction_Result')?['city'], 'Not Stated'), ', ', coalesce(body('Parse_Extraction_Result')?['state'], 'Not Stated'))
  ```
  (again, substitute your Parse JSON action's real name if different)
- Produces the combined "City, State" text for cell `F24`.

**Action 8 — Compose (`Build_Destination_File_Name`)**
- **+ New step** → **Compose**. Rename to `Build_Destination_File_Name`.
- Inputs, **Expression** tab:
  ```
  concat('Appraisal Review - ', replace(replace(replace(replace(coalesce(body('Parse_Extraction_Result')?['streetAddress'], 'Address Not Stated'), '/', '-'), '\', '-'), ':', '-'), '?', ''), ' - ', formatDateTime(utcNow(), 'yyyyMMdd-HHmmss'), '.xlsx')
  ```
  This builds a filename like `Appraisal Review - 4200 Colony Road -
  20260814-091530.xlsx` — the nested `replace()` calls strip characters
  that aren't valid in a SharePoint file name (`/`, `\`, `:`, `?`) out of
  the street address before using it, and the timestamp suffix guarantees
  two runs on the same day never collide.

**Action 9 — SharePoint: "Copy file" (`Copy_Template_To_New_File`)**
- **+ New step** → search **"SharePoint"** → select **Copy file**.
- You'll likely be prompted to create/select a connection the first time —
  sign in with an account that has the access described in Part A step 4.
- Fill in the action's fields — for each, switch to the field's
  **Expression** tab where noted, otherwise these are plain values:
  - **Site Address**: type or paste your **Template site URL** directly
    (from Part A) — e.g. `https://yourbank.sharepoint.com/sites/CreditRisk`.
  - **File to Copy**: your **Template file path** (from Part A) — e.g.
    `/Shared Documents/Templates/Appraisal Review Template.xlsx` (the
    picker may want this relative to the site, without repeating the site
    URL — use whichever format the designer's own file picker resolves
    without an error).
  - **Destination Site Address**: your **Destination site URL** (Part A).
  - **Destination Folder**: your **Destination folder path** (Part A).
  - **Destination File Name** (if your connector version exposes this
    field — not all do): **Expression** tab,
    `outputs('Build_Destination_File_Name')`.
  - **If another file already exists**: set to **Rename** — a safety net;
    the timestamp in the filename already makes a real collision very
    unlikely.
- Rename the action to `Copy_Template_To_New_File`.

**Action 10 — SharePoint: "Get file properties" (`Get_New_File_Properties`)**
- **+ New step** → **SharePoint** → **Get file properties**.
- **Site Address**: your **Destination site URL** (same as above).
- **File Identifier**: switch to **Expression**, enter:
  ```
  body('Copy_Template_To_New_File')?['destinationFilePath']
  ```
  (substitute your actual Copy File action's name if you didn't rename it
  to match). This resolves the drive/item identifiers the next two actions
  need — Copy File's own output only gives you a path, not the IDs
  required to run a script or create a link against the new file.
- Rename to `Get_New_File_Properties`.

**Action 11 — Excel Online (Business): "Run script" (`Populate_Review_Cells`)**
- **+ New step** → search **"Excel Online (Business)"** → select
  **Run script**.
- **Location**: **SharePoint Site**.
- **Document Library**: pick the library containing your **Destination
  site URL**'s folder.
- **File**: click the **Dynamic content** picker and select the file
  identifier output from **Get_New_File_Properties** (Action 10) — do
  **not** pick a fixed/browsed file here, since it must resolve to
  whichever new copy this specific run just created, not the template.
- **Script**: select `PopulateAppraisalReviewCells` from the dropdown —
  it only appears here if Part C (adding the Office Script to the
  template) was completed on this exact file or the template it was
  copied from.
- **Script parameters**: this is the long part — the script has 17
  parameters, one per extracted field, and each needs an expression. For
  each parameter field shown in the designer, switch to **Expression** and
  enter the matching line below (substitute your actual Parse JSON action
  name for `Parse_Extraction_Result` throughout if different):
  ```
  occupancyType:              coalesce(body('Parse_Extraction_Result')?['occupancyType'], 'Not Stated')
  cityState:                  outputs('Format_City_State')
  streetAddress:               coalesce(body('Parse_Extraction_Result')?['streetAddress'], 'Not Stated')
  collateralAnalysisValue:    string(coalesce(body('Parse_Extraction_Result')?['collateralAnalysisValue'], 'Not Stated'))
  valuationType:               coalesce(body('Parse_Extraction_Result')?['valuationType'], 'Not Stated')
  appraiserNames:              outputs('Format_Appraiser_Names')
  appraisalDate:               coalesce(body('Parse_Extraction_Result')?['appraisalDate'], 'Not Stated')
  reviewerName:                coalesce(body('Parse_Extraction_Result')?['reviewerName'], 'Not Stated')
  reviewDate:                  coalesce(body('Parse_Extraction_Result')?['reviewDate'], 'Not Stated')
  grossBuildingAreaSqFt:       string(coalesce(body('Parse_Extraction_Result')?['grossBuildingAreaSqFt'], 'Not Stated'))
  netRentableAreaSqFt:         string(coalesce(body('Parse_Extraction_Result')?['netRentableAreaSqFt'], 'Not Stated'))
  numberOfBuildings:           string(coalesce(body('Parse_Extraction_Result')?['numberOfBuildings'], 'Not Stated'))
  yearBuiltOrRemodeled:        string(coalesce(body('Parse_Extraction_Result')?['yearBuiltOrRemodeled'], 'Not Stated'))
  remainingEconomicLifeYears:  string(coalesce(body('Parse_Extraction_Result')?['remainingEconomicLifeYears'], 'Not Stated'))
  generalCondition:            coalesce(body('Parse_Extraction_Result')?['generalCondition'], 'Not Stated')
  marketExposureTime:          coalesce(body('Parse_Extraction_Result')?['marketExposureTime'], 'Not Stated')
  meetsHighestAndBestUse:      coalesce(body('Parse_Extraction_Result')?['meetsHighestAndBestUse'], 'Not Stated')
  ```
  Every value is wrapped in `coalesce(..., 'Not Stated')` so a field the
  model couldn't find never breaks the action — it lands in the cell as
  the literal text `Not Stated` instead. The five numeric-looking fields
  (`collateralAnalysisValue`, `grossBuildingAreaSqFt`,
  `netRentableAreaSqFt`, `numberOfBuildings`,
  `remainingEconomicLifeYears`) are additionally wrapped in `string(...)`
  — every one of the script's 17 parameters is typed as Text on the Office
  Script side (see `flows/scripts/PopulateAppraisalReviewCells.ts`), so a
  raw number here would be a type mismatch; the script itself decides
  whether to write the cell as a number, date, or text once it receives
  the string.
- Rename the action to `Populate_Review_Cells`.

**Action 12 — SharePoint: "Create sharing link for a file or folder"
(`Create_Sharing_Link`)**
- **+ New step** → **SharePoint** → **Create sharing link for a file or
  folder**.
- **Site Address**: your **Destination site URL**.
- **File Identifier**: **Dynamic content**, the same identifier output
  from **Get_New_File_Properties** (Action 10) you used in Action 11.
- **Link Type**: **View**.
- **Link Scope**: **Organization** (adjust to your bank's data
  classification policy if a different scope is required).
- Rename to `Create_Sharing_Link`.

**Action 13 — Teams: "Post message in a channel" (`Post_Success_To_Teams`)**
- **+ New step** → search **"Teams"** → **Post message in a channel**.
- **Team** / **Channel**: your **notification channel** (Part A) — pick it
  from the dropdowns, or if your connector version wants a raw channel ID
  instead of a picker, use the ID you captured in Part A step 3.
- **Message**: switch to **Expression**, enter:
  ```
  concat('Created ', outputs('Build_Destination_File_Name'), ' from ', triggerBody()?['document']?['name'], '. ', if(equals(body('Parse_Extraction_Result')?['needsManualReview'], true), concat('Needs manual verification: ', join(coalesce(body('Parse_Extraction_Result')?['missingFields'], createArray()), ', '), '. ', coalesce(body('Parse_Extraction_Result')?['extractionNotes'], '')), 'All 17 fields were extracted with no flags.'), ' Open the workbook: ', body('Create_Sharing_Link')?['link'])
  ```
  This states what was created, flags any missing fields plus the model's
  own extraction notes when `needsManualReview` is `true`, and always
  includes the workbook link at the end.
- Rename to `Post_Success_To_Teams`.

**If Action 3 was no (upload failed validation) — `Post_Rejection_To_Teams`:**
same Teams action, explaining the upload was rejected. AI Builder is never
called in this branch.

**Two parallel error branches, outside the main condition tree:**

**`Handle_Extraction_Failure`**
- Add a parallel branch off the AI Builder Predict action (Action 4):
  **"..."** menu → **Add a parallel branch**. Configure **Run after**: the
  AI Builder step **has failed** or **timed out**, and the Parse JSON step
  **has failed**.
- A Teams "Post message in a channel" action — see the reference file for
  the exact message expression. No file is created in this branch.

**`Handle_Write_Failure`**
- Add another parallel branch off **Copy File**, configured to run after
  Copy File, Get File Properties, Run Script, **or** Create Sharing Link
  **has failed**.
- Another Teams post — see the reference file.

5. **Save** the flow. Consider setting a clear **description** on the flow
   (Details pane) — the flow's own name and description are directly
   user-facing, since they're what analysts see in Teams' flow picker.

---

## Part E — Make the workflow available in Teams

1. In Power Automate, open `Shared-AppraisalReviewOrchestrator` → **···** →
   **Share** (or **Details** → **Share**, depending on your designer
   version) and add the credit risk team's members/security group as
   **Run only** or **Co-owner** users. An Instant cloud flow with a File
   input that isn't shared won't appear in a teammate's Teams flow picker
   at all.
2. In Teams, open the credit risk channel's message compose box and look
   for the **Workflows** (or **Power Automate**, depending on your Teams
   client version) icon — typically under the "+" or the "···" in the
   compose toolbar. Confirm `Shared-AppraisalReviewOrchestrator` appears in
   the list of flows you (and, once shared, your teammates) can run.
3. If it doesn't appear automatically, some tenants require browsing "All
   flows" / "See your flows" from the same picker, which surfaces any
   Instant cloud flow with Teams-compatible inputs you have access to,
   even if it isn't pinned to the compose toolbar by default.

---

## Part F — Test end-to-end

1. In the credit risk Teams channel, open the compose box, select
   `Shared-AppraisalReviewOrchestrator` from the Workflows/Power Automate
   picker, and upload a sample appraisal review PDF into the form that
   appears. Run it.
2. Confirm in the flow's run history that it triggered, `Validate_Upload`
   evaluated `true`, and `Extract_With_AI_Builder` succeeded.
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
   `Extract_With_AI_Builder` never executed for either.
7. Run the workflow twice for the same property on the same day and
   confirm two distinct workbook files (the timestamp suffix in the file
   name should differ).
8. Confirm the flow appears correctly for a **teammate**, not just its
   owner — sign in as (or ask) another analyst to confirm the workflow is
   visible and runnable from their own Teams client, validating the
   sharing step in Part E actually took effect.

---

## Troubleshooting

**The flow doesn't appear in Teams' Workflows/Power Automate picker**
- Confirm it's an **Instant cloud flow** with a **File-type input** on the
  "Manually trigger a flow" trigger — other trigger types don't surface
  here.
- Confirm the sharing step in Part E was completed for the user trying to
  find it — an unshared flow is invisible to everyone but its owner.

**AI Builder Predict step fails or times out**
- Confirm the prompt is **Published** (not just saved as a draft) in AI
  Builder.
- Open the PDF manually — if it's a scanned image with no text layer, the
  prompt cannot read it. Route these to manual entry.
- Check your tenant's AI Builder credit balance in the Power Platform admin
  center — a depleted credit pool fails every Predict call.
- Confirm `triggerBody()?['document']?['contentBytes']` is what's being
  passed, not `triggerBody()?['document']` directly — the latter passes
  the whole object, not just the file bytes, and AI Builder will reject it.

**Parse JSON step fails with a schema mismatch**
- Open the AI Builder Predict action's raw output in run history — the
  model may have returned prose instead of JSON. Re-open the prompt in AI
  Builder, confirm **Response format** is set to **JSON**, and re-test with
  Part B step 7's sample PDF.

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
  value — check `Parse_Extraction_Result`'s raw output for that field; the
  model likely didn't find it in the source PDF.

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
- Confirm the flow's run history shows it reached one of the `Post_*` or
  `Handle_*` Teams actions at all — if the run failed somewhere entirely
  unhandled, no Teams action ever executes.

**Costs climbing faster than expected**
- Confirm `Validate_Upload` is still correctly rejecting oversized/non-PDF
  uploads before `Extract_With_AI_Builder` runs.
- Confirm both `Handle_Extraction_Failure` and `Handle_Write_Failure` are
  still wired up so failed runs return immediately rather than leaving
  orphaned partially-copied files in the destination folder.
- Check your tenant's AI Builder credit balance/consumption report in the
  Power Platform admin center — a shared environment credit pool is
  consumed by every Prompt in it, not just this one.
