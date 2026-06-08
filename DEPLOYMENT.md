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
│   └── stapleton-agent-topic.yaml
├── flows/
│   ├── Shared-FormatResearchReport.json      ← HTML formatter flow definition
│   ├── Shared-ResearchAgentScheduler.json    ← Scheduled orchestrator definition
│   ├── Shared-StablecoinEmailFlow.json       ← Shared email sender definition
│   ├── Shared-FormatStablecoinReport.json
│   ├── Shared-FormatStapletonReport.json
│   ├── build_packages.py                     ← Script to generate .zip packages
│   └── packages/
│       ├── Shared-FormatResearchReport.zip   ← Ready to import
│       ├── Shared-ResearchAgentScheduler.zip ← Ready to import
│       ├── Shared-StablecoinEmailFlow.zip    ← Ready to import
│       ├── Shared-FormatStablecoinReport.zip
│       └── Shared-FormatStapletonReport.zip
├── templates/
│   ├── research-report.html                  ← Purple-branded HTML email template
│   ├── stablecoin-report.html
│   └── stapleton-report.html
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
> as a schema and rejects embedded expressions — you'll get
> `ActionSchemaInvalid`. The fix is to build the body in a Compose action
> (expressions are allowed there), then reference the Compose output as a
> single expression in the Response body.

- Click **+ New step** → search **Compose**
- In the **Inputs** field, click the expression tab (fx) and enter:
  ```
  createObject('status', 'sent', 'to', outputs('Compose'), 'cc', outputs('Compose_1'), 'subject', triggerBody()?['subject'], 'timestamp', utcNow())
  ```
  > Replace `outputs('Compose')` and `outputs('Compose_1')` with the actual
  > names Power Automate assigned to your To_String and Cc_String Compose steps.
  > Hover over each Compose step to confirm its name.

**Action 7 — Response (success)**
- Status Code: `200`
- Body field: click the expression tab (fx) and enter:
  ```
  outputs('Compose_2')
  ```
  > Replace `Compose_2` with whatever Power Automate named your
  > Build_Success_Body Compose step.

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

**Action 6 — Apply to each (Build_Categories)**
- Select output: (expression) `triggerBody()?['categories']`
- Inside the loop, add:

  **6a — Set variable** → Name: `currentArticlesHtml`, Value: *(empty string)*

  **6b — Apply to each (Build_Articles)**
  - Select output: (expression) `items('Apply_to_each')?['articles']`
  - Inside this inner loop, add:

    **6b-i — Compose (Build_Article_Html)**
    Expression:
    ```
    concat(
      '<div class="article-item"><a class="article-title" href="',
      items('Apply_to_each_2')?['url'],
      '">',
      items('Apply_to_each_2')?['title'],
      '</a><p class="article-meta">',
      items('Apply_to_each_2')?['source'],
      ' &nbsp;&middot;&nbsp; ',
      items('Apply_to_each_2')?['publishedAt'],
      '</p><p class="article-summary">',
      items('Apply_to_each_2')?['summary'],
      '</p></div>'
    )
    ```

    **6b-ii — Append to string variable**
    - Name: `currentArticlesHtml`
    - Value: `@{outputs('Compose_2')}` ← the article HTML compose

    **6b-iii — Increment variable**
    - Name: `articleCount`
    - Value: `1`

  **6c — Compose (Build_Category_Html)**
  Expression:
  ```
  concat(
    '<div class="category-section"><div class="category-heading">',
    items('Apply_to_each')?['name'],
    '</div>',
    if(empty(coalesce(items('Apply_to_each')?['description'],'')),
       '',
       concat('<p class="category-desc">',items('Apply_to_each')?['description'],'</p>')),
    variables('currentArticlesHtml'),
    '</div>'
  )
  ```

  **6d — Append to string variable**
  - Name: `categoryItemsHtml`
  - Value: `@{outputs('Compose_3')}` ← the category HTML compose

**Action 7 — Apply to each (Build_Recommendations)**
- Select output: (expression) `triggerBody()?['recommendations']`
- Inside loop:

  **7a — Compose**
  Expression: `concat('<li class="rec-item"><span class="rec-arrow">&#8594;</span>',items('Apply_to_each_3'),'</li>')`

  **7b — Append to string variable**
  - Name: `recItemsHtml`
  - Value: the rec HTML compose output

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

Same pattern as the email flow — build the body in Compose first.

- Add a **Compose** step
- Inputs (expression tab):
  ```
  createObject('htmlBody', outputs('R9'), 'articleCount', variables('articleCount'), 'categoryCount', length(triggerBody()?['categories']), 'recommendationCount', length(triggerBody()?['recommendations']))
  ```

**Action 18 — Response**
- Status Code: `200`
- Body field (expression tab):
  ```
  outputs('Compose_17')
  ```
  > Replace `Compose_17` with whatever Power Automate named your
  > Build_Response_Body Compose step.

4. Save and copy the HTTP trigger URL.

#### Step O2-3 — Manual creation: Shared-ResearchAgentScheduler

> **Reference file:** `flows/Shared-ResearchAgentScheduler.json`

1. **+ Create** → **Scheduled cloud flow**
2. Name it `Shared-ResearchAgentScheduler`
3. Set schedule: Starting **today**, Repeat every **1 Day**
4. Click **Create**

**Add these actions in order:**

**Action 1 — Initialize variable** → Name: `researchTopic`, Type: String,
Value: your topic (e.g. `Artificial Intelligence in Enterprise Software`)

**Action 2 — Initialize variable** → Name: `formatFlowUrl`, Type: String,
Value: *(the HTTP trigger URL from Step O2-4)*

**Action 3 — Initialize variable** → Name: `emailFlowUrl`, Type: String,
Value: *(the HTTP trigger URL from Step O2-3)*

**Action 4 — Run a copilot topic** (Microsoft Copilot Studio connector)
- Sign in with your work account when prompted
- Bot: select your published Research Agent
- Topic: select `Research & Return Report`
- Input variables → add `researchTopic` = `@{variables('researchTopic')}`

**Action 5 — Parse JSON**
- Content: `@{body('Run_a_copilot_topic')}`
- Schema: paste the schema from `flows/Shared-ResearchAgentScheduler.json`
  under `Parse_Agent_Response.inputs.schema`

**Action 6 — HTTP** (call format flow)
- Method: POST
- URI: `@{variables('formatFlowUrl')}`
- Headers: `Content-Type: application/json`
- Body:
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

**Action 7 — Parse JSON** (parse format response)
- Content: `@{body('HTTP')}`
- Schema: `{ "type":"object","properties":{ "htmlBody":{"type":"string"}, "articleCount":{"type":"integer"}, "categoryCount":{"type":"integer"}, "recommendationCount":{"type":"integer"} } }`

**Action 8 — HTTP** (call email flow)
- Method: POST
- URI: `@{variables('emailFlowUrl')}`
- Headers: `Content-Type: application/json`
- Body:
  ```json
  {
    "htmlBody":   "@{body('Parse_JSON_2')?['htmlBody']}",
    "subject":    "@{body('Parse_JSON')?['emailSubject']}",
    "to":         "@{body('Parse_JSON')?['emailTo']}",
    "cc":         "@{body('Parse_JSON')?['emailCc']}",
    "importance": "Normal"
  }
  ```

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

**5. Enable Generative Answers with Bing**

- Click **Knowledge** (left sidebar or top tab)
- Click **Add knowledge**
- Select **Public websites and Bing Search**
- Toggle **Bing Search** to **On**
- Click **Save**

**6. Create the topic**

- Click **Topics** (left sidebar)
- Click **Add a topic** → **Create from blank**
- Name the topic: `Research & Return Report`
- Click **More options** (··· menu on the topic) → **Open YAML editor**
- Select all the existing YAML and delete it
- Open `agent/research-agent-topic.yaml` from the repository, copy the entire file
- Paste it into the YAML editor
- Click **Save**

**7. Allow Power Automate to call this agent**

- Click **Settings** (gear icon, top-right)
- Go to **Security** → **Authentication**
- Confirm **Authentication** is set to **No authentication** or
  **Authenticate with Microsoft** (either works with the PA connector)
- Go to **Advanced settings** → enable **Allow the bot to be called
  from Power Automate flows**
- Click **Save**

**8. Publish the agent**

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

The first three actions in the flow are `Initialize Variable` steps.
Click each one and update the **Value** field:

| Action name | Field to change | What to enter |
|---|---|---|
| `Init_ResearchTopic` | Value | The topic you want researched, e.g. `"Cybersecurity Threats in Financial Services"` |
| `Init_FormatFlowUrl` | Value | The HTTP trigger URL copied from Part 3 Step 5 |
| `Init_EmailFlowUrl` | Value | The HTTP trigger URL copied from Part 2 Step 5 |

**6. Update the flow parameters**

Below the variable steps, click the **Call_Research_Agent** action. You
will see it references `parameters('environmentId')`,
`parameters('agentId')`, and `parameters('topicName')`.

To set these parameters:
- Click the **··· More** menu at the top of the flow editor → **Settings**
  (or look for a **Parameters** panel in the flow)
- Update the three parameter default values:

| Parameter | Value |
|---|---|
| `environmentId` | Your Power Platform environment GUID (from Part 4 Step 9) |
| `agentId` | Your Copilot Studio agent GUID (from Part 4 Step 9) |
| `topicName` | `Research & Return Report` (the topic name you created in Part 4 Step 6) |

> **Alternative:** If Power Automate's import UI does not expose parameters
> directly, click the **Call_Research_Agent** action and edit the **Path**
> field directly:
> ```
> /environments/YOUR-ENV-ID/bots/YOUR-AGENT-ID/topics/Research & Return Report/run
> ```

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
- Subject matching the pattern `{Topic} — Research Brief | {Date}`
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

The topic is a single variable in the scheduler flow — no agent or template
changes are needed.

1. Open **Shared-ResearchAgentScheduler** in Edit mode
2. Click the **Init_ResearchTopic** action (first step)
3. Change the **Value** to your new topic, e.g.:
   ```
   Global Supply Chain Disruptions
   ```
4. Click **Save**

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

Recipients are controlled by the **agent instructions**, not by the flows.
This means you update them once in Copilot Studio — no flow edits needed.

1. Open `agent/research-agent-instructions.md` in a text editor
2. Find the **Structured Output Schema** section
3. Update the `emailTo` and `emailCc` arrays:
   ```json
   "emailTo": [
     "alice@yourorg.com",
     "bob@yourorg.com"
   ],
   "emailCc": [
     "manager@yourorg.com"
   ]
   ```
4. Copy the entire updated file content
5. In **Copilot Studio** → your Research Agent → **Instructions**
6. Replace the existing instructions with the updated content
7. Click **Save** then **Publish**

---

## Running Multiple Topics

Each topic needs its own scheduler flow instance. The format and email flows
are shared — no additional deployments needed for those.

**1. Duplicate the scheduler flow**

- **My flows** → `Shared-ResearchAgentScheduler` → **··· More** → **Save as**
- Name it something descriptive, e.g. `ResearchScheduler-Cybersecurity`

**2. Update the topic variable**

Open the duplicate in Edit mode → change `Init_ResearchTopic` Value

**3. Stagger the schedules (optional)**

To avoid all reports arriving at the same time, offset each scheduler by
15–30 minutes:
- `ResearchScheduler-AI`: 07:00 UTC
- `ResearchScheduler-Cybersecurity`: 07:15 UTC
- `ResearchScheduler-Finance`: 07:30 UTC

**4. Update agent instructions for each topic's recipients (optional)**

If different topics need different distribution lists, create separate agent
instances in Copilot Studio with different `emailTo`/`emailCc` in their
instructions, and point each scheduler to the appropriate agent.

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
