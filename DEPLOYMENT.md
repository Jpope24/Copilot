# Deployment Guide — Stablecoin Research Agent

## Repository Layout

```
Copilot/
├── agent/
│   ├── stablecoin-agent-instructions.md   # Agent system prompt / instructions
│   └── stablecoin-agent-topic.yaml        # Main Copilot Studio topic (AdaptiveDialog)
├── flows/
│   ├── Shared-FormatStablecoinReport.json # Flow 1: HTML formatter (reusable)
│   └── Shared-StablecoinEmailFlow.json    # Flow 2: Outlook email sender (reusable)
├── templates/
│   └── stablecoin-report.html             # HTML email template with {{PLACEHOLDERS}}
└── DEPLOYMENT.md                          # This file
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
