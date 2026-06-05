# Deployment Guide

## Repository Layout

```
Copilot/
├── agent/
│   ├── stablecoin-agent-instructions.md      # Stablecoin agent system prompt
│   ├── stablecoin-agent-topic.yaml           # Stablecoin Copilot Studio topic
│   ├── stapleton-agent-instructions.md       # Stapleton agent system prompt
│   ├── stapleton-agent-topic.yaml            # Stapleton Copilot Studio topic
│   ├── research-agent-instructions.md        # Generic Research Agent system prompt
│   └── research-agent-topic.yaml            # Research Agent Copilot Studio topic
├── flows/
│   ├── Shared-FormatStablecoinReport.json    # HTML formatter for stablecoin reports
│   ├── Shared-FormatStapletonReport.json     # HTML formatter for Stapleton reports
│   ├── Shared-FormatResearchReport.json      # HTML formatter for generic research reports
│   ├── Shared-StablecoinEmailFlow.json       # Shared Outlook email sender (reusable)
│   ├── Shared-ResearchAgentScheduler.json    # Scheduled orchestrator for Research Agent
│   ├── build_packages.py                     # Builds importable .zip packages
│   └── packages/                             # Generated Power Automate import packages
├── templates/
│   ├── stablecoin-report.html                # Stablecoin HTML email template
│   ├── stapleton-report.html                 # Stapleton HTML email template
│   └── research-report.html                  # Generic research HTML email template
└── DEPLOYMENT.md                             # This file
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Microsoft Copilot Studio license | Per-tenant or per-user |
| Power Automate Premium | Required for HTTP trigger on flows |
| Office 365 Outlook connector | Shared connection named `shared_o365_outlook` |
| Bing Search / Generative Answers | Enabled on the Copilot Studio environment |
| SharePoint or Azure Blob | Recommended for hosting the HTML template file |

---

## Step 1 — Deploy Shared-FormatStablecoinReport

1. In **Power Automate**, create a new **Instant cloud flow**.
2. Import the definition from `flows/Shared-FormatStablecoinReport.json`.
3. Upload `templates/stablecoin-report.html` to a SharePoint document library
   (e.g. `https://yourorg.sharepoint.com/sites/CopilotAssets/Shared%20Documents/templates/`).
4. In the **Load_HTML_Template** action, replace the placeholder `Compose` with a
   **SharePoint – Get file content** action pointing to the uploaded template.
5. Save and note the **HTTP trigger URL**.
6. Under **Manage** → **Connections**, confirm the flow runs under a service account
   that has access to SharePoint.
7. Share the flow: **More** → **Share** → add the Copilot Studio environment service principal.

---

## Step 2 — Deploy Shared-StablecoinEmailFlow

1. In **Power Automate**, create a new **Instant cloud flow**.
2. Import the definition from `flows/Shared-StablecoinEmailFlow.json`.
3. In the **Send_Email_via_Outlook** action, configure the
   `shared_o365_outlook` connection using a licensed shared mailbox
   (e.g. `stablecoin-reports@yourorg.com`).
4. Save and note the **HTTP trigger URL**.
5. Share the flow the same way as Step 1.

> **Reuse tip:** Any other Copilot Studio agent can call
> `Shared-StablecoinEmailFlow` by passing a different `htmlBody`, `subject`,
> `to`, and `cc`. The flow is intentionally generic.

---

## Step 3 — Create the Copilot Studio Agent

1. In **Copilot Studio**, click **Create** → **New agent**.
2. Name it **Stablecoin Research Agent**.
3. Paste the contents of `agent/stablecoin-agent-instructions.md` into the
   **Instructions** field.
4. Under **Topics**, create a new topic named **Research & Send Report**.
5. Switch to **YAML editor** and paste the contents of
   `agent/stablecoin-agent-topic.yaml`.
6. In the two `InvokeFlowAction` steps, map the `flowId` values to the
   actual flow GUIDs from Steps 1 and 2.
7. Enable **Generative Answers** and connect the Bing Search data source.

---

## Step 4 — Configure the Scheduled Trigger

1. In **Power Automate**, create a new **Scheduled cloud flow** (daily, 07:00 UTC).
2. Add a single action: **HTTP** → POST to the Copilot Studio agent's
   **Direct Line** endpoint with the trigger phrase
   `"Run the stablecoin 24-hour report"`.
3. Store the Direct Line secret in **Key Vault**; reference it via the
   Key Vault connector.

---

## Updating Email Recipients

Edit `agent/stablecoin-agent-instructions.md` → **Email Configuration** section,
then redeploy the agent instructions. No flow changes are needed unless you want
to change the hard-coded fallback lists in `Shared-StablecoinEmailFlow.json`.

---

## Using the Flows with Other Agents

Both flows accept standard HTTP POST requests. To reuse them in a different agent:

```yaml
# Any agent topic can call the email flow with its own content:
- kind: InvokeFlowAction
  flowId: Shared-StablecoinEmailFlow   # same shared flow
  inputs:
    htmlBody: =topic.myCustomHtmlBody
    subject:  ="My Report – " & topic.reportDate
    to:       =["customrecipient@yourorg.com"]
    cc:       =[]
```

To use a different HTML template, call `Shared-FormatStablecoinReport` with
a custom template loaded in the **Load_HTML_Template** step, or create a
sibling flow (e.g. `Shared-FormatEquityReport`) that follows the same
input/output contract.

---

---

# Generic Research Agent — Deployment Guide

The **Research Agent** is a configurable, topic-agnostic solution. A single
Power Automate scheduled flow (**Shared-ResearchAgentScheduler**) kicks off
a Copilot Studio agent, receives the research payload (including the email
subject and distribution list from the agent), formats it into HTML, and
sends the email — with no hardcoded recipients in the flow itself.

## Architecture

```
Power Automate Recurrence Trigger (daily 07:00 UTC)
  │
  ├─► Shared-ResearchAgentScheduler
  │     │
  │     ├─► [1] Call Research Agent (Copilot Studio connector)
  │     │         Agent researches topic via Bing generative answers
  │     │         Returns: executiveSummary, categories[], recommendations[],
  │     │                  emailSubject, emailTo[], emailCc[]
  │     │
  │     ├─► [2] Call Shared-FormatResearchReport (HTTP)
  │     │         Builds HTML from categories + articles + recommendations
  │     │         Returns: htmlBody, articleCount, categoryCount
  │     │
  │     └─► [3] Call Shared-StablecoinEmailFlow (HTTP)
  │               Sends email via Office 365 Outlook
  │               Subject + To + CC all come from the agent's output
```

**Key design principle:** The agent owns the email configuration. Change
recipients or subject formatting by editing the agent instructions — the
flows require no modification.

---

## Step A — Deploy Shared-FormatResearchReport

1. In **Power Automate**, create a new **Instant cloud flow**.
2. Import the flow definition from `flows/Shared-FormatResearchReport.json`.
3. In the `R1` Compose action, replace the `'{{TEMPLATE_PLACEHOLDER}}'`
   literal with the full content of `templates/research-report.html`
   (paste it as a string, or load it via a SharePoint Get file content action).
4. Save and copy the **HTTP trigger URL** — you will need it in Step C.
5. Share the flow with the Power Automate service principal.

> **Or use the build script:** Run `python flows/build_packages.py` to generate
> `flows/packages/Shared-FormatResearchReport.zip`, then import that zip in
> Power Automate (**My flows** → **Import** → **Import Package (Legacy)**).
> The script embeds the template automatically.

### Input payload accepted by this flow

```json
{
  "reportDate":       "June 5, 2026",
  "windowStart":      "2026-06-04T07:00:00Z",
  "windowEnd":        "2026-06-05T07:00:00Z",
  "generatedAt":      "2026-06-05T07:05:00Z",
  "topic":            "Artificial Intelligence in Enterprise Software",
  "executiveSummary": "2–4 sentence overall summary.",
  "categories": [
    {
      "name":        "Market Adoption",
      "description": "Optional one-sentence overview.",
      "articles": [
        {
          "title":       "Article Headline",
          "summary":     "2–3 sentence factual summary.",
          "url":         "https://source.com/article",
          "source":      "Source Name",
          "publishedAt": "June 5, 2026 04:30 UTC"
        }
      ]
    }
  ],
  "recommendations": [
    "First actionable item.",
    "Second actionable item."
  ]
}
```

### Response returned by this flow

```json
{
  "htmlBody":            "<html>…</html>",
  "articleCount":        12,
  "categoryCount":       4,
  "recommendationCount": 5
}
```

---

## Step B — Deploy Shared-StablecoinEmailFlow (if not already deployed)

This flow is shared across all agents. See **Step 2** in the Stablecoin
section above. No changes are needed — it accepts `to` and `cc` arrays from
the caller, so the Research Agent's dynamic distribution list works without
any flow modifications.

---

## Step C — Create the Research Agent in Copilot Studio

1. In **Copilot Studio**, click **Create** → **New agent**.
2. Name it **Research Agent** (or any name matching your topic).
3. Paste the contents of `agent/research-agent-instructions.md` into the
   **Instructions** field.
4. Under **Topics**, create a new topic named **Research & Return Report**.
5. Switch to the **YAML editor** and paste the contents of
   `agent/research-agent-topic.yaml`.
6. Enable **Generative Answers** with a Bing Search data source.
7. Under **Settings** → **Security**, confirm the agent can be called by
   Power Automate (toggle **Allow the bot to be called from Power Automate**).
8. Note the **Agent ID** from the URL bar — you need it in Step D.

---

## Step D — Deploy Shared-ResearchAgentScheduler

1. In **Power Automate**, create a new **Scheduled cloud flow**.
2. Import the definition from `flows/Shared-ResearchAgentScheduler.json`.
3. Configure the four required values in the flow:

| Variable / Parameter | Where to find it | Description |
|---|---|---|
| `researchTopic` (variable) | Edit directly in flow | The topic the agent will research daily |
| `formatFlowUrl` (variable) | Step A trigger URL | HTTP URL of Shared-FormatResearchReport |
| `emailFlowUrl` (variable) | Step B trigger URL | HTTP URL of Shared-StablecoinEmailFlow |
| `environmentId` (parameter) | Power Platform admin center | Your Power Platform environment GUID |
| `agentId` (parameter) | Copilot Studio URL | The agent's GUID from Step C |
| `topicName` (parameter) | Copilot Studio | The topic name you created in Step C |

4. Add the **Microsoft Copilot Studio** connection when prompted.
5. Set the schedule to **Daily at 07:00 UTC** (configured in the trigger).
6. Save and **turn the flow on**.

---

## Configuring Email Recipients

Recipients are set by the **agent's instructions**, not in the flow. To change
who receives the report:

1. Open `agent/research-agent-instructions.md`.
2. Update the `emailTo` and `emailCc` arrays in the **Structured Output Schema**
   section (the example JSON).
3. Update the agent instructions in Copilot Studio.

No flow changes are required.

---

## Running Multiple Research Topics

To run reports on several topics simultaneously:

1. Duplicate `Shared-ResearchAgentScheduler` in Power Automate.
2. Change the `researchTopic` variable to a different topic.
3. Optionally adjust the scheduled time to stagger delivery.

All duplicates share the same **Shared-FormatResearchReport** and
**Shared-StablecoinEmailFlow** — no additional flow deployments needed.

---

## Rebuilding Import Packages

```bash
# From the repo root:
cd flows
python build_packages.py

# Outputs:
#   packages/Shared-FormatStablecoinReport.zip
#   packages/Shared-StablecoinEmailFlow.zip
#   packages/Shared-FormatStapletonReport.zip
#   packages/Shared-FormatResearchReport.zip
#   packages/Shared-ResearchAgentScheduler.zip
```
