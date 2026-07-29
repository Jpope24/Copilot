# Deployment Guide

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Prerequisites](#prerequisites)
3. [IMPORTANT — If zip import is blocked by your admin](#important--if-zip-import-is-blocked-by-your-admin)
4. [Part 1 — Build the Import Packages](#part-1--build-the-import-packages)
5. [Part 2 — Deploy the Email Flow (Shared-StablecoinEmailFlow)](#part-2--deploy-the-email-flow)
6. [Part 3 — Deploy the Format Flow (Shared-FormatResearchReport)](#part-3--deploy-the-format-flow)
7. [Part 4 — Create the Research Agent in Copilot Studio](#part-4--create-the-research-agent-in-copilot-studio)
8. [Part 5 — Deploy the Scheduler Flow (Shared-ResearchAgentScheduler)](#part-5--deploy-the-scheduler-flow)
9. [Part 6 — Configure & Test End-to-End](#part-6--configure--test-end-to-end)
10. [Changing the Research Topic](#changing-the-research-topic)
11. [Changing Email Recipients](#changing-email-recipients)
12. [Running Multiple Topics](#running-multiple-topics)
13. [Troubleshooting](#troubleshooting)
14. [Stablecoin & Stapleton Agent Deployment](#stablecoin--stapleton-agent-deployment)
15. [Appraisal PDF-to-Excel Extractor Deployment](#appraisal-pdf-to-excel-extractor-deployment)

---

## Repository Layout

```
Copilot/
├── agent/
│   ├── research-agent-instructions.md        ← Agent system prompt
│   ├── research-agent-topic.yaml             ← Copilot Studio topic YAML
│   ├── stablecoin-agent-instructions.md
│   ├── stablecoin-agent-topic.yaml
│   ├── stapleton-agent-instructions.md
│   ├── stapleton-agent-topic.yaml
│   ├── appraisal-agent-instructions.md       ← Appraisal Review Extractor system prompt
│   └── appraisal-agent-topic.yaml            ← Copilot Studio topic YAML
├── flows/
│   ├── Shared-FormatResearchReport.json      ← HTML formatter flow definition
│   ├── Shared-ResearchAgentScheduler.json    ← Scheduled orchestrator definition
│   ├── Shared-StablecoinEmailFlow.json       ← Shared email sender definition
│   ├── Shared-FormatStablecoinReport.json
│   ├── Shared-FormatStapletonReport.json
│   ├── Shared-AppraisalCellWriter.json       ← Per-review workbook writer (no AI Builder — see deployment section)
│   ├── scripts/
│   │   └── PopulateAppraisalReviewCells.ts   ← Office Script run by the flow's "Run script" action
│   ├── build_packages.py                     ← Script to generate .zip packages
│   └── packages/
│       ├── Shared-FormatResearchReport.zip   ← Ready to import
│       ├── Shared-ResearchAgentScheduler.zip ← Ready to import
│       ├── Shared-StablecoinEmailFlow.zip    ← Ready to import
│       ├── Shared-FormatStablecoinReport.zip
│       └── Shared-FormatStapletonReport.zip
│       (Shared-AppraisalCellWriter has no .zip — see note in its deployment section)
├── templates/
│   ├── research-report.html                  ← Purple-branded HTML email template
│   ├── stablecoin-report.html
│   └── stapleton-report.html
│       (no appraisal template here — the flow copies your bank's own
│        template workbook; see its deployment section, Part A)
└── DEPLOYMENT.md
```

---

## Prerequisites

### Licenses & Access

| Requirement | Why it is needed |
|---|---|
| **Microsoft Copilot Studio** license (per-tenant or per-user) | To create and publish the Research Agent |
| **Power Automate Premium** license | The HTTP trigger connector requires Premium; needed on the account that owns the flows |
| **Office 365 / Exchange Online** mailbox | The email sender mailbox; can be a shared mailbox |
| **Bing Search / Generative Answers** enabled in Copilot Studio environment | The agent uses Bing grounding to research topics |

### Accounts to have ready

- An account with **Environment Maker** or higher role in your Power Platform environment
- A mailbox address to send reports from (e.g. `reports@yourorg.com`)
- A list of recipient email addresses for the To and CC lines

### Tools (for building packages locally — optional)

```
Python 3.8+   (only needed if you rebuild packages from source)
git           (to clone the repository)
```

---

## IMPORTANT — If zip import is blocked by your admin

If you see the error:

> *"Importing packages with flows is disabled because the 'Include flows in
> Dataverse solutions' option was enabled by your admin. Use solution import
> instead."*

This means your Power Platform admin has turned on a tenant-wide setting that
requires all flows to live inside Dataverse solutions. The legacy zip import
(`.zip` via **Import Package (Legacy)**) is disabled. You have three options:

---

### Option 1 — Ask your admin to disable the setting (quickest, 5 minutes)

This is the fastest fix if your admin is available.

1. Admin goes to [admin.powerplatform.microsoft.com](https://admin.powerplatform.microsoft.com)
2. Click **Environments** → select your environment
3. Click **Settings** (top toolbar)
4. Expand **Product** → click **Features**
5. Find **"Include flows in Dataverse solutions"** (may also appear as
   "Power Automate — Turn on solution-aware flows")
6. Toggle it **Off**
7. Click **Save**

After saving, return to Power Automate and retry the zip import as described
in Parts 2–5. Once all flows are deployed, the admin can re-enable the setting
if needed.

---

### Option 2 — Create flows directly in Power Automate (no zip, no Solutions needed)

> **If you don't see "Solutions" in make.powerapps.com, skip it entirely.**
> The Solutions sidebar requires a Dataverse-provisioned environment. You don't
> need it. The admin setting only blocks *importing* zip packages — **creating
> flows from scratch still works**. Flows you create this way are automatically
> placed in the Default Solution behind the scenes, which satisfies the admin
> requirement without you having to interact with Solutions at all.

Go to **[make.powerautomate.com](https://make.powerautomate.com)** and create
each flow by hand using the steps below. No zip file, no Solutions page needed.

#### How to start each flow

| Flow | Start with |
|---|---|
| `Shared-StablecoinEmailFlow` | **+ Create** → **Instant cloud flow** → name it → choose **"When a HTTP request is received"** trigger |
| `Shared-FormatResearchReport` | **+ Create** → **Instant cloud flow** → name it → choose **"When a HTTP request is received"** trigger |
| `Shared-ResearchAgentScheduler` | **+ Create** → **Scheduled cloud flow** → name it → set interval to 1 Day |

Then build each flow action-by-action using the steps below.

#### Step O2-1 — Manual creation: Shared-StablecoinEmailFlow

> **Reference file:** `flows/Shared-StablecoinEmailFlow.json`

This flow receives an HTML body + subject + recipient lists and sends an email.

1. **+ Create** → **Instant cloud flow**
2. Name it `Shared-StablecoinEmailFlow`
3. Choose trigger: **When a HTTP request is received** → click **Create**

**Add these actions in order:**

**Action 1 — Initialize variable (resolvedTo)**
- Click **+ New step** → search "Initialize variable"
- Name: `resolvedTo`
- Type: `Array`
- Value (expression):
  ```
  if(empty(triggerBody()?['to']), createArray('analyst1@yourorg.com','analyst2@yourorg.com'), triggerBody()?['to'])
  ```

**Action 2 — Initialize variable (resolvedCc)**
- Name: `resolvedCc`
- Type: `Array`
- Value (expression):
  ```
  if(empty(triggerBody()?['cc']), createArray('compliance@yourorg.com','research-team@yourorg.com'), triggerBody()?['cc'])
  ```

**Action 3 — Compose (To_String)**
- Search "Compose"
- Inputs (expression): `join(variables('resolvedTo'), ';')`

**Action 4 — Compose (Cc_String)**
- Inputs (expression): `join(variables('resolvedCc'), ';')`

**Action 5 — Send an email (V2)** (Office 365 Outlook connector)
- To: (expression) `outputs('Compose')`  ← the To_String compose output
- Cc: (expression) `outputs('Compose_1')` ← the Cc_String compose output
- Subject: (expression) `triggerBody()?['subject']`
- Body: (expression) `triggerBody()?['htmlBody']`
- Toggle **Is HTML** to **Yes**
- Importance: Normal

**Action 6 — Compose (Build_Success_Body)**

> **Why a Compose first?** Power Automate's Response action validates its body
> as a schema and rejects embedded expressions (`ActionSchemaInvalid`). The fix
> is to assemble the body in a Compose action — expressions are fine there —
> then pass the Compose output as a single reference in the Response body field.

- Click **+ New step** → search **Compose**
- In the **Inputs** field, switch to the **expression tab (fx)** and type a JSON
  object where each value starts with `@` to signal it is an expression:
  ```
  {
    "status": "sent",
    "to": "@outputs('Compose')",
    "cc": "@outputs('Compose_1')",
    "subject": "@triggerBody()?['subject']",
    "timestamp": "@utcNow()"
  }
  ```
  > Replace `outputs('Compose')` and `outputs('Compose_1')` with the actual
  > names Power Automate auto-assigned to your To_String and Cc_String Compose
  > steps. Hover over each step title to confirm the internal name.

  Alternatively, type the JSON directly in the plain Inputs field (no expression
  mode) and use **Add dynamic content** to insert each value from the picker —
  Power Automate will wrap the picked value in the correct `@{}` syntax for you.

**Action 7 — Response (success)**
- Status Code: `200`
- Body field — click the **expression tab (fx)** and enter:
  ```
  outputs('Compose_5')
  ```
  > Replace `Compose_5` with the internal name Power Automate assigned to your
  > Build_Success_Body Compose step (check the step title bar).

4. Click **Save**
5. Click the **When a HTTP request is received** trigger step and copy the
   **HTTP POST URL** that appears after saving

**Configure the request body JSON schema** on the trigger step:

Click the trigger step → **Add JSON schema** → paste:
```json
{
  "type": "object",
  "properties": {
    "htmlBody": { "type": "string" },
    "subject": { "type": "string" },
    "to": { "type": "array", "items": { "type": "string" } },
    "cc": { "type": "array", "items": { "type": "string" } },
    "importance": { "type": "string" }
  },
  "required": ["htmlBody", "subject"]
}
```

#### Step O2-2 — Manual creation: Shared-FormatResearchReport

> **Reference file:** `flows/Shared-FormatResearchReport.json`
> **Template file:** `templates/research-report.html`

This flow builds the HTML email from the agent's research payload.

1. **+ Create** → **Instant cloud flow**
2. Name it `Shared-FormatResearchReport`
3. Trigger: **When a HTTP request is received**

**Paste the request body JSON schema** on the trigger:
```json
{
  "type": "object",
  "required": ["reportDate","windowStart","windowEnd","topic","executiveSummary","categories","recommendations"],
  "properties": {
    "reportDate":       { "type": "string" },
    "windowStart":      { "type": "string" },
    "windowEnd":        { "type": "string" },
    "generatedAt":      { "type": "string" },
    "topic":            { "type": "string" },
    "executiveSummary": { "type": "string" },
    "categories": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name":        { "type": "string" },
          "description": { "type": "string" },
          "articles": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "title":       { "type": "string" },
                "summary":     { "type": "string" },
                "url":         { "type": "string" },
                "source":      { "type": "string" },
                "publishedAt": { "type": "string" }
              }
            }
          }
        }
      }
    },
    "recommendations": { "type": "array", "items": { "type": "string" } }
  }
}
```

**Add these actions in order:**

**Action 1 — Initialize variable** → Name: `categoryItemsHtml`, Type: String, Value: *(empty)*

**Action 2 — Initialize variable** → Name: `currentArticlesHtml`, Type: String, Value: *(empty)*

**Action 3 — Initialize variable** → Name: `recItemsHtml`, Type: String, Value: *(empty)*

**Action 4 — Initialize variable** → Name: `articleCount`, Type: Integer, Value: `0`

**Action 5 — Compose (HTML_Template)**
- Open `templates/research-report.html`, copy the entire file content
- Paste it as the **Inputs** value of this Compose action

**Action 6 — Apply to each**
- Select output: (expression) `triggerBody()?['categories']`
- **IMPORTANT**: After adding this action, click **"…" (three dots) → Rename** and set the name to exactly: `Build_Categories`
  (The `items()` expression in child steps must match this name exactly.)
- Inside the loop, add:

  **6a — Set variable** → Name: `currentArticlesHtml`, Value: *(empty string)*

  **6b — Apply to each** *(nested inside Action 6)*
  - Select output: (expression) `items('Build_Categories')?['articles']`
  - **IMPORTANT**: After adding this action, click **"…" → Rename** and set the name to exactly: `Build_Articles`
  - Inside this inner loop, add:

    **6b-i — Compose** *(nested inside 6b)*
    - **Rename** this Compose step to: `Build_Article_Html`
    - Expression (enter in the **fx / Expression** tab — not Dynamic content):
    ```
    concat(
      '<div class="article-item"><a class="article-title" href="',
      items('Build_Articles')?['url'],
      '">',
      items('Build_Articles')?['title'],
      '</a><p class="article-meta">',
      items('Build_Articles')?['source'],
      ' &nbsp;&middot;&nbsp; ',
      items('Build_Articles')?['publishedAt'],
      '</p><p class="article-summary">',
      items('Build_Articles')?['summary'],
      '</p></div>'
    )
    ```

    **6b-ii — Append to string variable**
    - Name: `currentArticlesHtml`
    - Value (expression): `outputs('Build_Article_Html')`

    **6b-iii — Increment variable**
    - Name: `articleCount`
    - Value: `1`

  **6c — Compose** *(back in the outer Build_Categories loop, after 6b)*
  - **Rename** this Compose step to: `Build_Category_Html`
  - Expression:
  ```
  concat(
    '<div class="category-section"><div class="category-heading">',
    items('Build_Categories')?['name'],
    '</div>',
    if(empty(coalesce(items('Build_Categories')?['description'],'')),
       '',
       concat('<p class="category-desc">',items('Build_Categories')?['description'],'</p>')),
    variables('currentArticlesHtml'),
    '</div>'
  )
  ```

  **6d — Append to string variable**
  - Name: `categoryItemsHtml`
  - Value (expression): `outputs('Build_Category_Html')`

**Action 7 — Apply to each**
- Select output: (expression) `triggerBody()?['recommendations']`
- **IMPORTANT**: After adding this action, click **"…" → Rename** and set the name to: `Build_Recommendations`
- Inside loop:

  **7a — Compose**
  - **Rename** this Compose step to: `Build_Rec_Html`
  - Expression: `concat('<li class="rec-item"><span class="rec-arrow">&#8594;</span>',items('Build_Recommendations'),'</li>')`

  **7b — Append to string variable**
  - Name: `recItemsHtml`
  - Value (expression): `outputs('Build_Rec_Html')`

**Actions 8–16 — Compose chain (template injection)**

Add 9 consecutive Compose actions chained together. Each replaces one
placeholder in the HTML. Name them R1 through R9:

| Step | Expression |
|---|---|
| R1 | `replace(string(outputs('HTML_Template')), '{{REPORT_DATE}}', triggerBody()?['reportDate'])` |
| R2 | `replace(outputs('R1'), '{{WINDOW_START}}', triggerBody()?['windowStart'])` |
| R3 | `replace(outputs('R2'), '{{WINDOW_END}}', triggerBody()?['windowEnd'])` |
| R4 | `replace(outputs('R3'), '{{GENERATED_AT}}', coalesce(triggerBody()?['generatedAt'],utcNow()))` |
| R5 | `replace(outputs('R4'), '{{TOPIC_NAME}}', triggerBody()?['topic'])` |
| R6 | `replace(outputs('R5'), '{{ARTICLE_COUNT}}', string(variables('articleCount')))` |
| R7 | `replace(outputs('R6'), '{{EXECUTIVE_SUMMARY}}', triggerBody()?['executiveSummary'])` |
| R8 | `replace(outputs('R7'), '{{CATEGORY_ITEMS}}', variables('categoryItemsHtml'))` |
| R9 | `replace(outputs('R8'), '{{RECOMMENDATION_ITEMS}}', variables('recItemsHtml'))` |

**Action 17 — Compose (Build_Response_Body)**
- **Rename** this Compose step to: `Build_Response_Body`
- Click the **Inputs** field. In the text area (default mode, **not** the fx/Expression tab),
  type or paste:
  ```
  {
    "htmlBody": "@{outputs('R9')}",
    "articleCount": "@{variables('articleCount')}",
    "categoryCount": "@{length(triggerBody()?['categories'])}",
    "recommendationCount": "@{length(triggerBody()?['recommendations'])}"
  }
  ```
  > Each `@{...}` is an inline expression. `R9` is the name of your last
  > template-replacement Compose step.

**Action 18 — Response**
- Status Code: `200`
- Headers: `Content-Type` = `application/json`
- Body: click the Body field, switch to the **Expression (fx)** tab, and enter **exactly**:
  ```
  outputs('Build_Response_Body')
  ```
  > This single-expression reference is required. Putting `@{...}` expressions directly
  > inside a JSON body on a Response action causes `ActionSchemaInvalid`.

4. Save and copy the HTTP trigger URL.

#### Step O2-3 — Manual creation: Shared-ResearchAgentScheduler

> **Reference file:** `flows/Shared-ResearchAgentScheduler.json`

This flow calls **every agent in its `agentConfigs` list** in sequence. Each
agent owns its own topic and distribution list — the flow just orchestrates,
formats, and delivers. To run multiple agents, you add entries to `agentConfigs`;
no other flow changes are needed.

1. **+ Create** → **Scheduled cloud flow**
2. Name it `Shared-ResearchAgentScheduler`
3. Set schedule: Starting **today**, Repeat every **1 Day**
4. Click **Create**

**Add these actions in order:**

**Action 1 — Initialize variable** → Name: `agentConfigs`, Type: **Array**
Value (paste as raw JSON text):
```json
[
  {
    "agentId":   "REPLACE_WITH_AGENT_1_ID",
    "topicName": "Research Agent"
  }
]
```
> To add a second agent later, append another `{ "agentId": "...", "topicName": "Research Agent" }` object to this array. No other changes needed.

**Action 2 — Initialize variable** → Name: `formatFlowUrl`, Type: String,
Value: *(the HTTP trigger URL from the Shared-FormatResearchReport flow)*

**Action 3 — Initialize variable** → Name: `emailFlowUrl`, Type: String,
Value: *(the HTTP trigger URL from the Shared-StablecoinEmailFlow flow)*

**Action 4 — Apply to each**
- **Rename** this step to: `Run_Each_Agent`
- Select output (Expression tab): `variables('agentConfigs')`
- Inside the loop, add all actions below. Each action is **nested inside** this Apply to each.

**4a — Run a copilot topic** (Microsoft Copilot Studio connector)
- Sign in with your work account when prompted
- Bot: *(dynamic — leave blank for now; set via the agentId expression)*
- After adding the action, switch to **Advanced mode** (peek code / `</>`) and
  set the path to:
  ```
  /environments/@{parameters('environmentId')}/bots/@{items('Run_Each_Agent')?['agentId']}/topics/@{items('Run_Each_Agent')?['topicName']}/run
  ```
- Body: *(leave empty — the agent owns its topic)*

**4b — Parse JSON** (parse agent response)
- Content (expression): `body('Run_a_copilot_topic')`
- Schema: paste the JSON schema from `flows/Shared-ResearchAgentScheduler.json`
  → `Run_Each_Agent.actions.Parse_Agent_Response.inputs.schema`

**4c — HTTP** (call format flow)
- **Rename** to: `Call_Format_Flow`
- Method: POST
- URI (expression): `variables('formatFlowUrl')`
- Headers: `Content-Type: application/json`
- Body (raw text mode):
  ```json
  {
    "reportDate":       "@{body('Parse_JSON')?['reportDate']}",
    "windowStart":      "@{body('Parse_JSON')?['windowStart']}",
    "windowEnd":        "@{body('Parse_JSON')?['windowEnd']}",
    "generatedAt":      "@{body('Parse_JSON')?['generatedAt']}",
    "topic":            "@{body('Parse_JSON')?['topic']}",
    "executiveSummary": "@{body('Parse_JSON')?['executiveSummary']}",
    "categories":       "@{body('Parse_JSON')?['categories']}",
    "recommendations":  "@{body('Parse_JSON')?['recommendations']}"
  }
  ```
  > Replace `Parse_JSON` with whatever Power Automate named your Parse JSON step in 4b.

**4d — Parse JSON** (parse format response)
- Content (expression): `body('Call_Format_Flow')`
- Schema: `{"type":"object","properties":{"htmlBody":{"type":"string"},"articleCount":{"type":"integer"},"categoryCount":{"type":"integer"},"recommendationCount":{"type":"integer"}}}`

**4e — HTTP** (call email flow)
- **Rename** to: `Call_Email_Flow`
- Method: POST
- URI (expression): `variables('emailFlowUrl')`
- Headers: `Content-Type: application/json`
- Body (raw text mode):
  ```json
  {
    "htmlBody":   "@{body('Parse_JSON_2')?['htmlBody']}",
    "subject":    "@{body('Parse_JSON')?['emailSubject']}",
    "to":         "@{body('Parse_JSON')?['emailTo']}",
    "cc":         "@{body('Parse_JSON')?['emailCc']}",
    "importance": "Normal"
  }
  ```
  > Replace `Parse_JSON_2` with the name Power Automate assigned to step 4d.
  > Subject, To, and CC all come from the agent output — nothing is hardcoded here.

5. **Edit the recurrence trigger** to run at 07:00 UTC:
   - Click the Recurrence trigger step
   - Set **At these hours**: `7`
   - Set **At these minutes**: `0`
   - Time zone: `UTC`

6. Save and turn the flow **On**.

After completing Steps O2-1 through O2-3, skip Parts 2–5 below and
continue directly with [Part 6 — Configure & Test End-to-End](#part-6--configure--test-end-to-end).

---

### Option 3 — Request the admin setting be re-examined

If neither Option 1 nor Option 2 is practical, share this context with
your admin:

> The "Include flows in Dataverse solutions" setting prevents all legacy flow
> package imports. This is appropriate for production governance but blocks
> developer and initial deployment workflows. A common compromise is to leave
> it **Off** in development/sandbox environments and **On** only in production,
> where flows are promoted via ALM pipelines rather than manual import.
> See: [https://go.microsoft.com/fwlink/?linkid=2211592](https://go.microsoft.com/fwlink/?linkid=2211592)

---

## Part 1 — Build the Import Packages

You can either **download the pre-built zips** from the repository or **rebuild
them locally** from source. The pre-built packages in `flows/packages/` are
ready to use and do not require Python.

### Option A — Use the pre-built packages (recommended)

1. Navigate to the repository on GitHub: `github.com/Jpope24/Copilot`
2. Click the branch dropdown and select `claude/power-automate-copilot-email-sqqcH`
3. Browse to `flows/packages/`
4. Click each `.zip` file, then click **Download raw file**

Download these three files for the Research Agent solution:

```
Shared-FormatResearchReport.zip
Shared-ResearchAgentScheduler.zip
Shared-StablecoinEmailFlow.zip
```

### Option B — Rebuild from source

Use this option if you have modified the HTML template or flow definitions
and need to re-embed them into fresh packages.

**1. Clone the repository**

```bash
git clone https://github.com/Jpope24/Copilot.git
cd Copilot
git checkout claude/power-automate-copilot-email-sqqcH
```

**2. Run the build script**

```bash
cd flows
python build_packages.py
```

Expected output:

```
  Created: flows/packages/Shared-FormatStablecoinReport.zip
  Created: flows/packages/Shared-StablecoinEmailFlow.zip
Done — Flow 1 & 2 packages ready in flows/packages/
  Created: flows/packages/Shared-FormatStapletonReport.zip
Done — all 3 packages ready in flows/packages/
  Created: flows/packages/Shared-FormatResearchReport.zip
  Created: flows/packages/Shared-ResearchAgentScheduler.zip
Done — all 5 packages ready in flows/packages/
```

**3. Verify the packages**

```bash
ls -lh flows/packages/
```

You should see five `.zip` files, all under 15 KB each. The two new packages:

```
Shared-FormatResearchReport.zip    ~12 KB  (HTML template embedded inside)
Shared-ResearchAgentScheduler.zip  ~ 5 KB
```

> **What the script does:** It reads `templates/research-report.html`,
> embeds it as a literal string inside the `HTML_Template` Compose action
> of the format flow, then wraps everything in the Power Automate package
> structure (`manifest.json` + `definition.json`) inside a `.zip`.

---

## Part 2 — Deploy the Email Flow

`Shared-StablecoinEmailFlow` is the shared email sender used by all agents.
Deploy it once; every other flow calls it via HTTP.

**1. Open Power Automate**

Go to [make.powerautomate.com](https://make.powerautomate.com) and confirm
you are in the correct environment (top-right environment selector).

**2. Import the package**

- Left sidebar → **My flows**
- Click **Import** (top menu) → **Import Package (Legacy)**
- Click **Upload** and select `Shared-StablecoinEmailFlow.zip`
- Wait for the upload to process (a few seconds)

**3. Configure the import options**

The import screen shows a list of resources. For each row:

| Resource | Action | Setting |
|---|---|---|
| `Shared-StablecoinEmailFlow` (flow) | **Create as new** | Leave the name as-is |
| `shared_office365` (connection) | **Select during import** | Choose your Office 365 Outlook connection, or click **Create new** to set one up |

To create a new Office 365 connection:
- Click the wrench icon next to the connection row
- Click **Create new**
- Sign in with the mailbox account you want to send from
- Return to the import screen and select the newly created connection

**4. Click Import** and wait for the confirmation banner.

**5. Open the flow and copy its trigger URL**

- Go to **My flows** → click `Shared-StablecoinEmailFlow`
- Click **Edit**
- Click the **When a HTTP request is received** trigger (the first step)
- The **HTTP POST URL** field will be populated after you save. Click **Save** first.
- Copy the full URL — it looks like:
  ```
  https://prod-XX.eastus.logic.azure.com:443/workflows/abc123.../triggers/manual/paths/invoke?...
  ```
- Save this URL — it is needed in Part 5.

**6. Share the flow**

- Go back to the flow detail page
- Click the **·· · More** menu → **Share**
- Add the service account or service principal that Power Automate uses
  in your environment so other flows can call it

---

## Part 3 — Deploy the Format Flow

`Shared-FormatResearchReport` converts the agent's research JSON into a
fully rendered HTML email body.

**1. Import the package**

- **My flows** → **Import** → **Import Package (Legacy)**
- Upload `Shared-FormatResearchReport.zip`

**2. Configure the import options**

| Resource | Action |
|---|---|
| `Shared-FormatResearchReport` (flow) | **Create as new** |

No connections are required — this flow has no external connectors.

**3. Click Import**

**4. Verify the HTML template is embedded**

- Open the flow in Edit mode
- Scroll to the action named **HTML_Template** (a Compose action near the top)
- Its **Inputs** field should contain the full HTML from `templates/research-report.html`
  (you will see `<!DOCTYPE html>…` as the value)
- If the input says `{{TEMPLATE_PLACEHOLDER}}`, the template was not embedded.
  In that case:
  - Open `templates/research-report.html` in a text editor
  - Copy the entire file content
  - Click the **HTML_Template** Compose action
  - Replace `{{TEMPLATE_PLACEHOLDER}}` with the copied HTML
  - Click **Save**

**5. Save and copy the trigger URL**

Same process as Part 2 Step 5. Copy the **HTTP POST URL** from the
`When a HTTP request is received` trigger and save it for Part 5.

**6. Test the flow manually (optional but recommended)**

- Click **Test** (top-right in Edit mode) → **Manually** → **Test**
- In the **Run flow** panel, paste this sample body:

```json
{
  "reportDate": "June 5, 2026",
  "windowStart": "2026-06-04T07:00:00Z",
  "windowEnd": "2026-06-05T07:00:00Z",
  "topic": "Artificial Intelligence in Enterprise Software",
  "executiveSummary": "AI adoption in enterprise software accelerated this week with three major product announcements. Cloud vendors are competing aggressively on model integration and pricing. Regulatory scrutiny is increasing in the EU.",
  "categories": [
    {
      "name": "Product Launches",
      "description": "New AI-powered software products announced this week.",
      "articles": [
        {
          "title": "Microsoft Copilot Gets New Reasoning Features",
          "summary": "Microsoft announced enhanced reasoning capabilities for Copilot across its 365 suite. The update enables multi-step task planning directly in Word and Excel. General availability is set for Q3 2026.",
          "url": "https://blogs.microsoft.com/blog/sample",
          "source": "Microsoft Blog",
          "publishedAt": "June 5, 2026 08:00 UTC"
        }
      ]
    }
  ],
  "recommendations": [
    "Evaluate Microsoft Copilot's new reasoning features against your current AI tooling.",
    "Monitor EU AI Act implementation timelines — enterprise software vendors will need compliance updates."
  ]
}
```

- Click **Run flow**
- In the run history, open the completed run and expand **Respond_With_HTML**
- The **Outputs** → **body** → **htmlBody** field should contain full rendered HTML
- Copy and paste the HTML into a browser file to preview the email

---

## Part 4 — Create the Research Agent in Copilot Studio

**1. Open Copilot Studio**

Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com) and
confirm you are in the same Power Platform environment you used in Parts 2–3.

**2. Create a new agent**

- Click **Create** (left sidebar)
- Click **New agent**
- Choose **Skip to configure** (you will add instructions manually)

**3. Name and describe the agent**

| Field | Value |
|---|---|
| Name | `Research Agent` |
| Description | `Researches a configured topic daily and returns a structured report with categorized articles, summaries, links, recommendations, and email routing to the calling Power Automate flow.` |
| Instructions | *(see next step)* |

**4. Paste the agent instructions**

- Open `agent/research-agent-instructions.md` from the repository
- Copy the entire file content
- Paste it into the **Instructions** field in Copilot Studio
- Before saving, find this section near the bottom of the instructions:

```json
"emailTo": [
  "recipient1@yourorg.com",
  "recipient2@yourorg.com"
],
"emailCc": [
  "manager@yourorg.com"
]
```

- Replace the placeholder addresses with your actual recipient email addresses

**5. Create the `Global.ResearchTopic` variable**

The agent reads the research topic from a global variable — no topic is passed in
from Power Automate. You set the default value here, in the agent.

- Click **Variables** in the top toolbar
- Click **+ Add a variable** → set:
  - **Name**: `ResearchTopic`
  - **Scope**: `Global`
  - **Type**: `String`
  - **Default value**: your topic, e.g. `Artificial Intelligence in Enterprise Software`
- Click **Save**

> To change the topic later, update this variable's **Default value** and republish.

**7. Enable Generative Answers with Bing**

- Click **Knowledge** (left sidebar or top tab)
- Click **Add knowledge**
- Select **Public websites and Bing Search**
- Toggle **Bing Search** to **On**
- Click **Save**

**8. Create the topic**

- Click **Topics** (left sidebar)
- Click **Add a topic** → **Create from blank**
- Name the topic: `Research Agent`
- Click **More options** (··· menu on the topic) → **Open YAML editor**
- Select all the existing YAML and delete it
- Open `agent/research-agent-topic.yaml` from the repository, copy the entire file
- Paste it into the YAML editor
- Click **Save**

**9. Allow Power Automate to call this agent**

- Click **Settings** (gear icon, top-right)
- Go to **Security** → **Authentication**
- Confirm **Authentication** is set to **No authentication** or
  **Authenticate with Microsoft** (either works with the PA connector)
- Go to **Advanced settings** → enable **Allow the bot to be called
  from Power Automate flows**
- Click **Save**

**10. Publish the agent**

- Click **Publish** (top-right)
- Wait for the publish confirmation banner

**9. Record the Agent ID and Environment ID**

You need both values for the scheduler flow in Part 5.

**Agent ID:**
- While on the agent page, look at the browser URL bar:
  ```
  https://copilotstudio.microsoft.com/environments/ENV_ID/bots/AGENT_ID/...
  ```
- Copy the `AGENT_ID` portion (a GUID like `cr123_myResearchAgent`)

**Environment ID:**
- Go to [admin.powerplatform.microsoft.com](https://admin.powerplatform.microsoft.com)
- Click **Environments** → click your environment name
- Copy the **Environment ID** (a GUID like `a1b2c3d4-e5f6-...`)

---

## Part 5 — Deploy the Scheduler Flow

`Shared-ResearchAgentScheduler` is the daily orchestrator. It runs on a
schedule, calls the agent, formats the results, and sends the email.

**1. Import the package**

- **My flows** → **Import** → **Import Package (Legacy)**
- Upload `Shared-ResearchAgentScheduler.zip`

**2. Configure the import options**

| Resource | Action | Notes |
|---|---|---|
| `Shared-ResearchAgentScheduler` (flow) | **Create as new** | |
| `shared_CopilotStudio` (connection) | **Select during import** | Choose or create a Microsoft Copilot Studio connection |

To create a new Copilot Studio connection:
- Click the wrench icon next to the connection row
- Click **Create new** → sign in with your work account
- Return and select the new connection

**3. Click Import**

**4. Open the flow in Edit mode**

Go to **My flows** → `Shared-ResearchAgentScheduler` → **Edit**

**5. Update the three configuration variables**

The flow has three `Initialize Variable` steps. Click each one and update the **Value** field:

| Action name | Field to change | What to enter |
|---|---|---|
| `Init_AgentConfigs` | Value | JSON array of agents (see below) |
| `Init_FormatFlowUrl` | Value | The HTTP trigger URL copied from Part 3 Step 5 |
| `Init_EmailFlowUrl` | Value | The HTTP trigger URL copied from Part 2 Step 5 |

**Updating `Init_AgentConfigs`:**
Click the step and replace the default Value with a JSON array listing every agent to run.
Start with one agent:
```json
[
  {
    "agentId":   "YOUR-AGENT-GUID-HERE",
    "topicName": "Research Agent"
  }
]
```
- `agentId`: the Copilot Studio agent GUID from Part 4 Step 9
- `topicName`: the topic name you created in Copilot Studio (Step 8 of Part 4)

To add more agents, append additional objects. Each sends its own email to
its own distribution list (configured in that agent's instructions).

**6. Update the `environmentId` parameter**

Click the **··· More** menu → **Settings** (or find the **Parameters** panel).
Set `environmentId` to your Power Platform environment GUID (from Part 4 Step 9).

> The flow no longer has `agentId` or `topicName` parameters — those are now
> in the `agentConfigs` variable, which makes adding agents much easier.

**7. Verify the recurrence schedule**

- Click the **Recurrence** trigger (the very first step in the flow)
- Confirm it is set to:
  - **Frequency:** Day
  - **Interval:** 1
  - **At these hours:** 7
  - **At these minutes:** 0
  - **Time zone:** UTC
- Adjust if you want a different run time

**8. Save the flow**

Click **Save** (top-right). Fix any validation errors before proceeding.

**9. Turn the flow on**

- Return to **My flows**
- Find `Shared-ResearchAgentScheduler`
- If it shows as **Off**, click the toggle to turn it **On**

---

## Part 6 — Configure & Test End-to-End

Before waiting for the 07:00 UTC scheduled run, trigger the flow manually
to confirm everything is wired up correctly.

**1. Run the scheduler flow manually**

- Go to **My flows** → `Shared-ResearchAgentScheduler`
- Click **Run** (the play button on the flow detail page)
- Confirm the run by clicking **Run flow** in the panel

**2. Monitor the run**

- Click **My flows** → `Shared-ResearchAgentScheduler`
- Scroll down to **28-day run history**
- The run will appear with a spinner while in progress (the agent research
  step typically takes 30–90 seconds)
- Click the run to open the detailed view

**3. Check each step**

The run detail shows every action with a green checkmark (success) or red X
(failure). Work through them in order:

| Step | What to check if it fails |
|---|---|
| `Call_Research_Agent` | Verify Agent ID, Environment ID, and topic name are correct. Check that the agent is published and PA connection is authenticated. |
| `Parse_Agent_Response` | Open the raw output of `Call_Research_Agent` — confirm it returns JSON, not an error message. |
| `Call_Format_Flow` | Verify the format flow URL is correct and the format flow is turned on. Click the step to see the HTTP response code (should be 200). |
| `Parse_Format_Response` | Confirm the format flow returned `htmlBody` in its response. |
| `Call_Email_Flow` | Verify the email flow URL is correct. Check the HTTP response — code 200 means the email was sent. |
| `Log_Run_Summary` | If this step is green, the full run succeeded. |

**4. Check your inbox**

Within a few minutes of a successful run, the configured recipients should
receive an email with:
- Subject matching the pattern `{Topic} - Research Brief | {Date}`
- A purple-branded HTML body containing the executive summary,
  categorized article cards with clickable links, and a recommendations list

**5. Verify the email renders correctly**

Open the email in Outlook (desktop or web). The email should display:
- A dark purple gradient header with the topic name
- A meta bar showing the date range and article count
- An executive summary block
- Category sections with article cards (title link, source, date, summary)
- A recommendations list with arrow bullets
- A footer with the agent attribution

If the email shows raw HTML tags instead of rendered content, the recipient's
email client may be blocking HTML. Forward it to a Gmail or Outlook web address
to confirm the HTML renders correctly.

---

## Changing the Research Topic

The topic is configured as a global variable **inside the Copilot Studio agent** —
no changes to the Power Automate flow or template are needed.

1. Open **Copilot Studio** → open your Research Agent
2. Click **Variables** in the top toolbar
3. Find `Global.ResearchTopic` in the variable list
4. Click it and update the **Default value** to your new topic, e.g.:
   ```
   Global Supply Chain Disruptions
   ```
5. Click **Save**, then **Publish** the agent

The next scheduled run (or your next manual test run) will research the new topic.

**Topic examples that work well:**

- `Cybersecurity Threats in Financial Services`
- `Electric Vehicle Market Trends`
- `Federal Reserve Policy and Inflation`
- `Mergers and Acquisitions in Healthcare`
- `Open Source AI Model Releases`
- `Commercial Real Estate Market`

---

## Changing Email Recipients

Recipients are defined in the **agent's instructions** — not in any flow.
Each agent has its own Distribution List section. Changing it requires only
updating the agent's Instructions field and republishing.

1. Open `agent/research-agent-instructions.md` in a text editor (or open your
   customized copy)
2. Find the **Distribution List** section under Deployment Configuration
3. Update the `emailTo` and `emailCc` arrays with the new addresses
4. Copy the entire updated file content
5. In **Copilot Studio** → open your Research Agent → click **Instructions**
6. Select all and paste the updated content
7. Click **Save** then **Publish**

No flow edits are required. The flow reads the distribution list from the
agent's output on every run.

---

## Running Multiple Agents (Multiple Topics)

One `Shared-ResearchAgentScheduler` instance can run **any number of agents**
in sequence. Each agent sends its own formatted email to its own distribution
list. The format flow and email flow are shared — no additional flow deployments
are needed.

### Creating a new agent for a different topic

1. **Copy the instructions template**
   - Start from `agent/research-agent-instructions.md`
   - Update the three Deployment Configuration sections:
     - **Topic** — new topic name (must match `Global.ResearchTopic`)
     - **Research Focus** — specific categories, source priorities, and
       research guidance for this topic
     - **Distribution List** — the `emailTo` / `emailCc` addresses for this topic's audience

2. **Create the agent in Copilot Studio**
   - Follow Part 4 of this guide using your customized instructions
   - Set `Global.ResearchTopic` to the new topic name
   - Use the same `agent/research-agent-topic.yaml` (it is generic)
   - Record the new agent's **Agent ID**

3. **Add the agent to the scheduler flow**
   - Open `Shared-ResearchAgentScheduler` in Edit mode
   - Click the **Init_AgentConfigs** step
   - Add an entry to the array:
     ```json
     [
       {
         "agentId":   "EXISTING-AGENT-1-ID",
         "topicName": "Research Agent"
       },
       {
         "agentId":   "NEW-AGENT-2-ID",
         "topicName": "Research Agent"
       }
     ]
     ```
   - Click **Save**

The next scheduled run calls both agents in sequence and sends two separate
emails — one per agent, each formatted identically, each going to its own
distribution list. Recipients see only their agent's report; there is no
combined email.

### Example multi-agent configuration

```json
[
  { "agentId": "cr123_aiResearch",        "topicName": "Research Agent" },
  { "agentId": "cr456_cyberResearch",     "topicName": "Research Agent" },
  { "agentId": "cr789_financeResearch",   "topicName": "Research Agent" }
]
```

Each agent in this list must be published in Copilot Studio and have its
own customized Instructions (topic, research focus, distribution list).

---

## Troubleshooting

### "Call_Research_Agent" step fails with 404

- Verify the `environmentId` and `agentId` parameters match your actual
  environment and agent exactly (GUIDs are case-sensitive)
- Confirm the agent is **Published** in Copilot Studio (draft agents cannot
  be called externally)
- Check that **Allow the bot to be called from Power Automate flows** is
  enabled in the agent's Security settings

### "Call_Research_Agent" step fails with 401 / Unauthorized

- The Copilot Studio connection used by the flow may be expired or
  using the wrong account
- Go to [make.powerautomate.com](https://make.powerautomate.com) →
  **Data** → **Connections** → find the Copilot Studio connection →
  click **··· More** → **Fix connection** → re-authenticate

### "Parse_Agent_Response" fails with a schema mismatch

- The agent returned data in an unexpected format
- Open the **Call_Research_Agent** output in the run history and copy the
  raw JSON
- Compare it against the schema in `flows/Shared-ResearchAgentScheduler.json`
  under `Parse_Agent_Response.inputs.schema`
- Common cause: the agent returned a conversational text response instead of
  JSON. Check the agent's topic YAML and confirm the `EndTask` outputs are
  mapped correctly.

### "Call_Format_Flow" returns 400 Bad Request

- The JSON payload sent to the format flow is missing a required field
- Open the step's input/output in the run history — look for which property
  is null or missing
- Required fields: `reportDate`, `windowStart`, `windowEnd`, `topic`,
  `executiveSummary`, `categories`, `recommendations`

### "Call_Format_Flow" returns 500 / template not injected

- The `HTML_Template` Compose action in `Shared-FormatResearchReport` still
  contains `{{TEMPLATE_PLACEHOLDER}}` instead of actual HTML
- Follow Part 3 Step 4 to manually paste the template content

### "Call_Email_Flow" returns 500

- The Office 365 connection may have expired — re-authenticate it in the
  Data → Connections section
- The `to` field returned by the agent may be empty — check that the agent
  instructions contain valid email addresses in the `emailTo` array

### Email arrives with broken layout / missing styles

- Most email clients strip `<style>` blocks. The template uses inline-compatible
  CSS but some clients (notably older Outlook desktop versions) have limited
  support for flexbox and CSS grid
- To maximize compatibility, open `templates/research-report.html`,
  inline all CSS using a tool like [Mailchimp's CSS Inliner](https://templates.mailchimp.com/resources/inline-css/),
  then rebuild the packages with `python flows/build_packages.py`

### Flow runs but no email is received

- Check the `Call_Email_Flow` step output — confirm `status` is `"sent"`
- Check the sender mailbox's **Sent Items** folder to confirm it dispatched
- Check recipient spam/junk folders — HTML emails from automated senders
  are sometimes filtered
- Verify the email addresses in the agent instructions are correct

---

## Stablecoin & Stapleton Agent Deployment

These agents use the older pattern where the agent calls flows directly
(rather than returning data to a scheduler flow). They share the same
`Shared-StablecoinEmailFlow` email sender.

### Deploy Shared-FormatStablecoinReport

1. **My flows** → **Import** → upload `Shared-FormatStablecoinReport.zip`
2. No connections needed — click **Import**
3. Open the flow, verify `HTML_Template` Compose contains the stablecoin HTML
4. Save and copy the HTTP trigger URL

### Deploy Shared-FormatStapletonReport

1. Same process — upload `Shared-FormatStapletonReport.zip`
2. Verify `HTML_Template` Compose contains the Stapleton HTML
3. Save and copy the HTTP trigger URL

### Create Stablecoin Agent in Copilot Studio

1. Create a new agent named **Stablecoin Research Agent**
2. Paste contents of `agent/stablecoin-agent-instructions.md` as Instructions
3. Create topic **Research & Send Report** from `agent/stablecoin-agent-topic.yaml`
4. In the two `InvokeFlowAction` steps, replace `flowId` values with the
   actual GUIDs of your deployed `Shared-FormatStablecoinReport` and
   `Shared-StablecoinEmailFlow` flows
5. Enable Bing Search under Knowledge
6. Publish the agent

### Create Stapleton Agent in Copilot Studio

1. Create a new agent named **Stapleton Research Agent**
2. Paste contents of `agent/stapleton-agent-instructions.md` as Instructions
3. Create topic from `agent/stapleton-agent-topic.yaml`
4. Map flow IDs: `Shared-FormatStapletonReport` + `Shared-StablecoinEmailFlow`
5. Enable Bing Search, publish

### Schedule both agents

For each agent, create a Power Automate Scheduled flow (daily 07:00 UTC)
with a single HTTP action that POSTs to the agent's Direct Line endpoint
with the trigger phrase from its instructions. Store the Direct Line secret
in Azure Key Vault and reference it via the Key Vault connector.

---

## Appraisal PDF-to-Excel Extractor Deployment

**Audience:** bank credit risk team. **Trigger:** a Teams chat or channel
message with an appraisal review PDF attached. **Output:** a brand-new
Excel workbook for that review — a copy of the bank's own appraisal review
template with 17 cells populated — plus a link to it.

### What this tool does

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

### Why this design (cost rationale)

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

### Prerequisites

| Requirement | Why it is needed |
|---|---|
| **Microsoft Copilot Studio** license, with generative/message capacity sufficient for inline Prompt actions | Runs both the conversation and the extraction — see cost note above. No separate AI Builder capacity is required; this design never calls AI Builder. |
| Your bank's **existing appraisal review template**, with a sheet named exactly `RE Collateral` and the cell layout in the table above | This tool copies and populates it — it does not create one for you |
| **Office Scripts** enabled for your tenant/site (on by default for most Microsoft 365 commercial tenants; confirm with your M365 admin if "Automate" doesn't appear in Excel Online) | Runs the cell-population script — standard M365 feature, no added license cost |
| A **SharePoint site and document library** for the template, and one for completed reviews (can be the same site/library) | Source and destination locations you'll designate as flow parameters |
| **Excel Online (Business)** and **SharePoint** connections (standard, no Premium required) | Used by the flow to copy files and run the script |
| **Teams** access to add/pin the agent to a channel or chat | Where analysts interact with the tool |
| An account with **Environment Maker** (or higher) in the target Power Platform environment | To create the flow, prompt, and agent |

> **A note on this flow's package.** Unlike the other flows in this repo,
> `Shared-AppraisalCellWriter` is **not** shipped as a pre-built `.zip` in
> `flows/packages/`. It references your bank's own template/destination
> paths — values that only exist after you designate them in your own
> environment, so a portable zip can't pre-populate them. Build this one
> flow by hand following Parts A–D below; `flows/Shared-AppraisalCellWriter.json`
> is the reference definition to build from (same idea as the "Option 2:
> manual creation" flows earlier in this guide).

---

### Part A — Designate the template and destination locations

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
3. Confirm the account that will own the Power Automate flow (Part C) has
   **edit** access to both the template's library (read is enough there,
   since the flow only copies it) and the destination folder (needs write
   access).

You'll paste these four values into the flow's parameters in Part C.

---

### Part B — Add the inline extraction Prompt action to the topic

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

### Part C — Add the Office Script to your template

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

### Part D — Build Shared-AppraisalCellWriter

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

**One error branch (down from two — there is no extraction step in this
flow to fail):**

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

### Part E — Create the Appraisal Review Extractor agent in Copilot Studio

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

### Part F — Add the agent to Teams

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

### Part G — Test end-to-end

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

### Troubleshooting (Appraisal Extractor)

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
