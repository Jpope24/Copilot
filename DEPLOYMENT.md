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
│   ├── Shared-AppraisalPdfToExcel.json       ← PDF extraction → Excel tracker flow definition
│   ├── build_packages.py                     ← Script to generate .zip packages
│   └── packages/
│       ├── Shared-FormatResearchReport.zip   ← Ready to import
│       ├── Shared-ResearchAgentScheduler.zip ← Ready to import
│       ├── Shared-StablecoinEmailFlow.zip    ← Ready to import
│       ├── Shared-FormatStablecoinReport.zip
│       └── Shared-FormatStapletonReport.zip
│       (Shared-AppraisalPdfToExcel has no .zip — see note in its deployment section)
├── templates/
│   ├── research-report.html                  ← Purple-branded HTML email template
│   ├── stablecoin-report.html
│   ├── stapleton-report.html
│   └── Appraisal-Review-Tracker-Template.xlsx ← Master Excel tracker (copy once, then reuse)
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
message with an appraisal review PDF attached. **Output:** one new row in a
shared Excel tracker (`AppraisalReviewData`), with a link back to the file.

### What this tool does

An analyst attaches an appraisal review PDF to the **Appraisal Review
Extractor** bot in Teams. The bot extracts 17 credit-risk data points
(occupancy type, address, collateral analysis value, valuation type,
appraiser/reviewer names and dates, building metrics, condition, market
exposure time, and the highest-and-best-use conclusion — full list in
[`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md)),
appends them as a new row to a single shared workbook, and replies in Teams
with a plain-language summary, any fields it could not find, and a link to
open the updated spreadsheet.

### Why this design (cost rationale)

| Choice | Why it keeps cost down |
|---|---|
| Extraction via an **AI Builder Prompt**, not a new Azure OpenAI or Azure AI Document Intelligence resource | Reuses AI Builder capacity your Power Platform/Copilot Studio licensing already includes, rather than standing up and paying for a separate Azure resource with its own meter and ops overhead. |
| Flow triggered by Copilot Studio's **native child-flow trigger** ("When Copilot Studio calls a flow"), not an HTTP Request trigger | Avoids requiring a Power Automate **Premium** license just to receive the call — every connector this flow uses (Excel Online (Business), SharePoint) is a standard connector. |
| **One shared tracker workbook**, appended to via "Add a row into a table", instead of copying the template per request | No per-run file-copy action, no document sprawl in SharePoint, and credit risk gets one auditable system of record instead of hundreds of one-off spreadsheets. |
| Tracker **sharing link computed once** at setup and passed to the flow as a parameter | Saves an API call on every single extraction — the link never changes. |
| **15 MB / 40-page cap** enforced in the Copilot Studio topic before the flow (and any AI Builder credits) are invoked | A malformed or oversized upload is rejected for free, before it can burn AI Builder credits or time out. |
| **No retries** on a failed extraction | A failure is surfaced to the analyst immediately instead of silently doubling the credit cost on a document likely to fail again. |

The only new recurring cost is **AI Builder credits per PDF processed**
(typically a few pages of extracted text per document — check your tenant's
AI Builder credit balance and per-prompt cost in the Power Platform admin
center before rollout) plus whatever **Copilot Studio message** consumption
your licensing already meters for agent conversations.

### Prerequisites

| Requirement | Why it is needed |
|---|---|
| **Microsoft Copilot Studio** license | To create, publish, and add the agent to Teams |
| **AI Builder** capacity (included/trial credits or a purchased add-on) | Runs the extraction prompt — see cost note above |
| A **SharePoint site and document library** the credit risk team already uses (or a new one) | Hosts the single shared tracker workbook |
| **Excel Online (Business)** and **SharePoint** connections (standard, no Premium required) | Used by the flow to append rows |
| **Teams** access to add/pin the agent to a channel or chat | Where analysts interact with the tool |
| An account with **Environment Maker** (or higher) in the target Power Platform environment | To create the flow, prompt, and agent |

> **A note on the AI Builder Prompt and this flow's package.** Unlike the
> other flows in this repo, `Shared-AppraisalPdfToExcel` is **not** shipped
> as a pre-built `.zip` in `flows/packages/`. The flow's AI Builder step
> references a Prompt GUID and a SharePoint drive/file ID that only exist
> *after* you create them in your own environment — a portable zip can't
> pre-populate those, and importing one with placeholder GUIDs would just
> fail. Build this one flow by hand following Parts A–C below; `flows/Shared-AppraisalPdfToExcel.json`
> is the reference definition to build from (same idea as the "Option 2:
> manual creation" flows earlier in this guide).

---

### Part A — Provision the shared tracker workbook (one-time)

1. Go to the SharePoint site / document library your credit risk team uses
   for shared files.
2. Upload `templates/Appraisal-Review-Tracker-Template.xlsx` to that
   library. Rename it if you like (e.g. `Appraisal Review Tracker.xlsx`) —
   this becomes the **one, permanent** file every extraction appends to.
3. Open the file in Excel Online and confirm the table `AppraisalReviewData`
   is present (click any cell in the header row — the **Table Design** tab
   should appear and show the table name).
4. Click **Share** → **Copy link**. Set permissions to "People in your
   organization" (or narrower, per your data classification policy) with
   **Can edit** access for the credit risk team and **Can view** for anyone
   else who needs it. Save this URL — it is `trackerFileUrl` in Part C.
5. Note the library's **Drive ID** and the file's **Item ID** — you'll need
   both for the Excel Online (Business) action in Part C. The easiest way:
   in Power Automate, add a temporary "Get file properties" (SharePoint)
   action pointed at this file, run it once, and read `{Identifier}` from
   the output (drive ID) and `{ItemId}` (file ID). Delete the temporary
   flow afterward.

---

### Part B — Create the AI Builder Prompt

This is the extraction engine. It replaces what would otherwise be a
separately-provisioned OCR/document-intelligence service.

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
   and **Output Requirements** sections from
   [`agent/appraisal-agent-instructions.md`](agent/appraisal-agent-instructions.md)
   (from "## Extraction Requirements" through the end of "## Output
   Requirements"), then reference the file input at the top: `Extract data
   from this appraisal review document: {document}`.
6. Set the **Response format** to **JSON** and paste the same JSON schema
   shown in the "Output Requirements" example so the model's output is
   constrained to that shape.
7. Click **Test**, upload a sample appraisal review PDF, and confirm the
   response is valid JSON matching the 17-field schema before saving.
8. **Save** and **Publish** the prompt.
9. Copy the prompt's GUID from the browser URL
   (`.../prompts/<PROMPT_GUID>/edit`) — this is `aiBuilderPromptId` in
   Part C.

---

### Part C — Build Shared-AppraisalPdfToExcel

> **Reference file:** `flows/Shared-AppraisalPdfToExcel.json`

1. Go to [make.powerautomate.com](https://make.powerautomate.com) → **+
   Create** → **Automated cloud flow**.
2. Name it `Shared-AppraisalPdfToExcel`.
3. In the trigger search box, type **"Power Virtual Agents"** (shows as
   *"When Power Virtual Agents calls a flow"* — this is Copilot Studio's
   native child-flow trigger) and select it. Click **Create**.
4. On the trigger card, click **+ Add an input** four times and configure:
   | Name | Type |
   |---|---|
   | `fileContent` | File |
   | `fileName` | Text |
   | `requestedByName` | Text |
   | `requestedByEmail` | Text |

**Add these actions in order:**

**Action 1 — Compose (`Init_ExtractionTimestamp`)**
- Inputs (expression): `utcNow()`

**Action 2 — AI Builder: "Predict"** (search "AI Builder" in the connector
list, action **Predict**, or your tenant's equivalent "Run a prompt" action)
- Prompt: select `Appraisal Review Field Extraction` (from Part B)
- `document` input: pick **fileContent** from Dynamic content (the trigger's
  file input)

**Action 3 — Parse JSON**
- Content: the output of the AI Builder Predict action
- Schema: paste the `properties` block from
  `flows/Shared-AppraisalPdfToExcel.json` → `actions.Parse_Extraction_Result.inputs.schema`

**Action 4 — Compose (`Format_Appraiser_Names`)**
- Inputs (expression):
  ```
  join(coalesce(body('Parse_JSON')?['appraiserNames'], createArray('Not Stated')), '; ')
  ```
  (replace `Parse_JSON` with your actual Parse JSON step name)

**Action 5 — Compose (`Format_Missing_Fields`)**
- Inputs (expression):
  ```
  if(empty(body('Parse_JSON')?['missingFields']), 'None', join(body('Parse_JSON')?['missingFields'], ', '))
  ```

**Action 6 — Excel Online (Business): "Add a row into a table"**
- Location: **SharePoint Site**
- Document Library: the library from Part A
- File: the tracker workbook from Part A
- Table: `AppraisalReviewData`
- Map each column to a value — use the exact mapping in
  `flows/Shared-AppraisalPdfToExcel.json` → `actions.Add_Row_To_Tracker.inputs.body`
  (25 columns: 4 metadata fields from the trigger, 18 extracted fields from
  Parse JSON, 3 quality fields from Parse JSON). For numeric fields
  (`Collateral Analysis Value`, `Gross Building Area (SF)`, etc.) pick the
  Parse JSON output directly — leave blank cells as blank rather than typing
  `0` when the model returned null.

**Action 7 — Compose (`Build_Row_Summary`)**
- Inputs (expression): see `flows/Shared-AppraisalPdfToExcel.json` →
  `actions.Build_Row_Summary.inputs` — builds the one-line summary sent back
  to Teams.

**Action 8 — Compose (`Build_Response_Body`)**
- Inputs: a JSON object with `status`, `errorMessage`, `trackerFileUrl`,
  `rowSummary`, `missingFields`, `needsManualReview`, `extractionNotes` —
  see the reference file for the exact expression for each.

**Action 9 (parallel error branch) — Compose (`Handle_Extraction_Failure`)**
- Click the **"..."** menu on the AI Builder Predict action → **Add a
  parallel branch**, add this Compose action there, and configure **Run
  after**: the AI Builder step **has failed** and the Parse JSON step **has
  failed** (Configure run after → check "has failed" on both).
- Inputs: `status: "error"`, `errorMessage`, and the remaining fields set to
  safe defaults — see the reference file.

5. Click the trigger card → **Outputs** panel → add an output for each of:
   `status`, `errorMessage`, `trackerFileUrl`, `rowSummary`, `missingFields`,
   `needsManualReview`, `extractionNotes`. For each, pick the matching field
   from **Build_Response_Body** (or **Handle_Extraction_Failure** — Power
   Automate lets a single output bind to whichever branch actually ran via
   `coalesce()`; if your tenant's designer doesn't offer that, wrap both
   Compose outputs in one final `coalesce()` Compose step and bind the
   trigger outputs to that instead).
6. In **Flow settings** (or as literal values if your tenant doesn't expose
   flow-level parameters in the designer), set:
   - `trackerFileUrl` = the sharing link from Part A step 4
   - `trackerDriveId` / `trackerFileId` = the IDs from Part A step 5
   - `aiBuilderPromptId` = the GUID from Part B step 9

   (If your environment doesn't support named flow parameters in the
   Power Automate designer, hardcode these four values directly into the
   corresponding actions instead of using `parameters(...)`.)
7. **Save** the flow.

---

### Part D — Create the Appraisal Review Extractor agent in Copilot Studio

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com),
   same environment as Parts A–C.
2. **Create** → **New agent** → **Skip to configure**.
3. Name: `Appraisal Review Extractor`. Description: *"Extracts credit-risk
   data points from appraisal review PDFs attached in Teams and appends them
   to the shared Appraisal Review Tracker."*
4. **Instructions**: paste the full contents of
   `agent/appraisal-agent-instructions.md`.
5. **Topics** → **Add a topic** → **Create from blank** → name it
   `Extract Appraisal Review` → **More options (···)** → **Open YAML
   editor** → select all, delete, paste the contents of
   `agent/appraisal-agent-topic.yaml` → **Save**.
6. In the topic, confirm the **InvokeFlowAction** step (`callExtractionFlow`)
   is linked to the `Shared-AppraisalPdfToExcel` flow from Part C — if the
   YAML paste doesn't auto-bind it, open that step in the visual designer
   and select the flow from the picker.
7. **Settings** (gear icon) → **Security** → confirm authentication is
   appropriate for your tenant (Teams users authenticate via Microsoft
   Entra ID automatically in the Teams channel).
8. **Publish** the agent.

---

### Part E — Add the agent to Teams

1. In Copilot Studio, go to **Channels** → **Microsoft Teams**.
2. Turn the Teams channel **on**. Copilot Studio generates a Teams app
   package for the agent.
3. Choose how the credit risk team will use it:
   - **Direct chat**: click **Open bot**, then have each analyst add it as
     a personal app in Teams (search for it by name, or your Teams admin
     can pre-install it tenant-wide).
   - **Shared channel** (recommended for a team workflow with an audit
     trail everyone can see): download the app package, have your Teams
     admin upload it via **Teams admin center → Manage apps** (or
     **Org-wide app settings** if custom app upload is restricted), then
     add the app to the credit risk team's channel. Analysts trigger it by
     @mentioning the bot and attaching the PDF.
4. Confirm the trigger phrases from the topic YAML work in Teams (e.g.
   `@Appraisal Review Extractor Extract appraisal`) — Teams requires an
   @mention or DM to start a conversation with the bot; it does not read
   every message in a channel.

---

### Part F — Test end-to-end

1. In Teams, message the bot (or @mention it in the channel) with the
   phrase `Extract appraisal`.
2. When prompted, attach a sample appraisal review PDF.
3. Confirm:
   - The bot acknowledges receipt and reports "Row added..." within about a
     minute.
   - Open the tracker link — the new row should have all 25 columns
     populated (or `Not Stated` / blank for anything genuinely absent from
     the source PDF).
   - If you intentionally test with a PDF missing a review sign-off page,
     confirm `reviewerName` / `reviewDate` come back `Not Stated`,
     `missingFields` lists them, and the Teams reply flags "needs manual
     verification."
4. Test the guardrails: attach a non-PDF file (should be rejected before
   the flow runs) and, if you have one, a file over 15 MB (should also be
   rejected before the flow runs — check the flow's run history to confirm
   it was never triggered).

---

### Troubleshooting (Appraisal Extractor)

**AI Builder Predict step fails or times out**
- Confirm the prompt is **Published** (not just saved as a draft) in AI
  Builder.
- Open the PDF manually — if it's a scanned image with no text layer, the
  prompt cannot read it. Route these to manual entry; consider a follow-up
  OCR step only if your team hits this often enough to justify the added
  cost.
- Check your tenant's AI Builder credit balance in the Power Platform admin
  center — a depleted credit pool fails every Predict call.

**Parse JSON step fails with a schema mismatch**
- Open the AI Builder Predict action's raw output in run history — the
  model may have returned prose instead of JSON. Re-open the prompt in AI
  Builder, confirm **Response format** is set to **JSON**, and re-test with
  Part B step 7's sample PDF.

**"Add a row into a table" fails**
- Most common cause: `trackerDriveId` / `trackerFileId` are wrong, or the
  tracker file was moved/renamed after Part A. Re-run "Get file properties"
  to refresh the IDs.
- Confirm the Excel Online (Business) connection used by the flow has edit
  access to the document library.

**Teams reply never arrives / flow doesn't run**
- Confirm **Part C step 5** — the trigger's Outputs — is fully configured.
  A "When Power Virtual Agents calls a flow" trigger with no bound outputs
  returns nothing to the topic, which then shows a blank or generic error.
- Confirm the topic's `callExtractionFlow` step is bound to the correct
  flow (Copilot Studio topics silently do nothing if the flow reference is
  unresolved after a YAML paste).

**Costs climbing faster than expected**
- Check whether the 15 MB / 40-page guardrail in the topic YAML is still in
  place — if someone edited the topic and removed it, oversized documents
  can consume disproportionate AI Builder credits.
- Confirm `Handle_Extraction_Failure` is wired up correctly so failed runs
  return immediately rather than looping or retrying.
