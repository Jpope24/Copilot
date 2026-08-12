# Proof of Concept — Execute Agent + File Attachments

**Purpose:** answer two open questions before the production Appraisal
Review Extractor topic/flow are rebuilt around Power Automate's
**"Execute Agent" / "Execute Agent and wait"** action, which research
turned up as the real mechanism for a flow to call a Copilot Studio agent —
replacing the "Run a topic" action this repo's earlier design invented and
got wrong.

1. **Can a file get from a Power Automate flow into a Copilot Studio topic
   via Execute Agent's attachments, and how does the topic actually read
   it?**
2. **What does Execute Agent and wait's response really look like** — is
   there a `lastResponse` field, does it need `json()` to parse, what else
   is on it?

This is deliberately the smallest possible build to answer those two
questions — not a preview of the production design. **Delete everything
built for this PoC once you have answers**, including the throwaway agent.
Do not extend it into the real tool.

## Files

- [`agent/poc-attachment-echo-topic.yaml`](agent/poc-attachment-echo-topic.yaml) — a topic that does nothing but echo back whatever attachment it received, as JSON text.
- [`flows/Poc-ExecuteAgentAttachmentTest.json`](flows/Poc-ExecuteAgentAttachmentTest.json) — a flow that uploads a test file, calls the topic via Execute Agent, and posts both the raw response and a parse attempt to Teams. **This file's `Execute_Agent_And_Wait` action is explicitly a placeholder** — build that one action from the live connector picker, not by pasting JSON; nothing in this repo has verified its real operation schema yet.

## Build steps

### 1. Create a throwaway agent

1. Go to [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com).
2. Check the environment picker (top of the page — click the environment
   name if you're not sure) and confirm it's the same Power Platform
   environment you intend to build the real tool in later. This matters:
   an agent created in the wrong environment won't be selectable from
   Power Automate's Execute Agent action.
3. Click **Agents** in the left-hand navigation (some tenants show
   **Create** instead — either gets you to the same place), then **+ New
   agent**.
4. Copilot Studio will offer to let you describe the agent in natural
   language first ("What would you like your agent to do?"). Click **Skip
   to configure** in the corner of that screen instead — this PoC needs a
   blank agent, not a generatively-authored one.
5. On the configuration screen: set **Name** to `PoC Execute Agent Test`
   (or anything obviously disposable — the point is you can't mistake it
   for the production agent later). Leave **Description** and
   **Instructions** blank; neither matters for this test.
6. Click **Create** (or **Save**) to actually create the agent shell —
   some versions of the designer won't let you add a topic until the agent
   itself has been saved once.

### 2. Build the PoC topic

1. With the new agent open, click the **Topics** tab in the left nav of
   the agent's authoring workspace.
2. Click **+ Add a topic** (sometimes a dropdown with several options) →
   **Create from blank** (as opposed to "Create with Copilot," which would
   try to generatively author it).
3. Name the topic `PoC Echo Attachment` when prompted, or rename it via
   the topic's title field once the canvas opens.
4. **Trigger phrase.** Blank topics start with a **Trigger** node at the
   top of the canvas showing an empty (or example) phrase list. Click into
   it and type exactly: `poc echo attachment` as the only phrase. Leave
   the trigger type as the default **Phrases** setting — do not switch it
   to rely on generative/AI orchestration for this test; a fixed phrase
   match removes one variable from what you're diagnosing.
5. **Delete the default greeting**, if one was auto-added (a "Send a
   message" node with placeholder text right after the trigger) — you
   don't want any extra chat activity before the actual test steps.
6. **Add the Question node.** Click the **+** below the trigger node →
   **Ask a question**. In the node's configuration panel that opens on the
   right:
   - **Question to ask users** (the prompt text): type
     `NO_ATTACHMENT_AUTO_RESOLVED` — this is deliberately not a friendly
     prompt; if you ever see this exact string as the test's result, that
     is itself the diagnostic signal that the attachment didn't arrive the
     way expected (see the "Reading the results" table below).
   - **Identify** (sometimes labeled "User response" or shown as a
     dropdown under the question): change it from the default (usually
     "Multiple choice options" or "User's entire response") to **File**.
     Some designer versions list this as **Attachment** instead of
     **File** — either is the same underlying entity type.
   - **Save the response as**: click into the variable field, choose
     **Create new**, name it `TestFile`. Confirm its scope shows as
     **Topic** (not Global) — this is the default for a newly created
     topic variable, so you usually don't need to change anything, but
     it's worth glancing at.
7. **Add the reply node.** Click the **+** below the Question node → **Send
   a message**. In the message text box, you need an *expression*, not
   literal text — click the **{x}** icon (sometimes shown as *"Insert
   variable"* or a small formula/function icon) at the right edge of the
   text box to switch into formula-editing mode, then enter:
   ```
   {"attachmentReceived": !IsBlank(Topic.TestFile), "fileName": If(IsBlank(Topic.TestFile), "none", Topic.TestFile.Name), "fileSizeBytes": If(IsBlank(Topic.TestFile), 0, Topic.TestFile.Size)}
   ```
   As you type `Topic.TestFile`, the formula bar's autocomplete should
   offer property suggestions after the dot (`.Name`, `.Size`, etc.) — use
   whatever it actually offers if it differs from `.Name`/`.Size` in your
   version; the point of the PoC is partly to discover real property names
   too. If the formula bar rejects the whole expression as invalid syntax,
   simplify it first to just `Topic.TestFile.Name` alone to confirm the
   variable and property access work, then rebuild the JSON-shaped string
   around it once you know the right property names.
8. Click **Save** (top-right of the canvas, or it may autosave — look for
   a "Saved" indicator).
9. Click **Publish** (top-right of the agent workspace) to publish this
   throwaway agent. Confirm the publish when prompted. This step is easy
   to forget and causes confusing "topic not found" errors later if
   skipped — Power Automate's Execute Agent action generally only sees
   **published** agents/topics, not unpublished drafts.

### 3. Build the PoC flow

1. Go to [make.powerautomate.com](https://make.powerautomate.com).
   Confirm (top-right environment picker) you're in the **same
   environment** as the PoC agent.
2. Click **+ Create** → **Instant cloud flow**.
3. In the dialog that appears, name it `Poc-ExecuteAgentAttachmentTest`,
   choose **Manually trigger a flow** from the trigger list, then click
   **Create**.
4. On the trigger card (the first card in the canvas), click **+ Add an
   input** → **File**. Name it `testFile`. Your designer should
   automatically add a second, paired text input holding the file's name
   (commonly named something like `testFile_1` or with a suffix — check
   what it actually generated and use that exact name in later steps
   instead of assuming it's called `testFileFileName`).
5. Click **+ New step** below the trigger to add each action in order:

   **Action 1 — Compose**
   - Search "Compose" in the action picker, select the **Compose** action
     (Data Operation connector).
   - Rename it (click the "..." menu on the action card → **Rename**) to
     `Build_Data_Uri` for clarity.
   - In the **Inputs** field, click into it, switch to **Expression** (a
     tab near the dynamic-content picker), and enter:
     ```
     concat('data:application/pdf;base64,', triggerBody()?['testFile'])
     ```
     Click **OK**/**Add**.

   **Action 2 — Execute Agent and wait**
   - Click **+ New step**, search **"Copilot Studio"** in the connector
     search box (not "Power Virtual Agents" — search both terms if one
     doesn't surface it, naming varies by tenant).
   - Select the **Execute Agent and wait** action from the list of
     actions under that connector. If you only see **Execute Agent**
     (without "and wait"), that's the fire-and-forget variant — use the
     "and wait" version so the flow pauses for a response; if your tenant
     truly doesn't offer a "wait" variant, note that as a finding too.
   - You'll likely be prompted to create/select a connection the first
     time — sign in with an account that has access to the PoC agent.
   - Fill in the action's fields:
     - **Agent** (or **Bot**, naming varies): a dropdown/picker — select
       `PoC Execute Agent Test`. If it doesn't appear, the agent likely
       isn't published yet (see step 2.9 above) or you're in the wrong
       environment.
     - **Message** (or **Text**, **Utterance** — the field that sends
       what the "user" says): enter the literal text `poc echo
       attachment` — this must match the topic's trigger phrase exactly.
     - Look for **"Show advanced options"** or an **Advanced parameters**
       expander at the bottom of this action's configuration panel. Click
       it open.
     - Inside advanced options, look for an **Attachments** field. This
       is the field the whole PoC exists to characterize — document
       whatever you actually find:
       - If it's a simple list/array builder: add one entry. Look for
         sub-fields resembling **Name**, **Content type**, and
         **Content**/**Content URL**. Set Name to the dynamic content
         from the trigger's paired filename field (step 4 above), Content
         type to `application/pdf`, and Content/Content URL to the output
         of `Build_Data_Uri` (Action 1).
       - If there's no such field at all anywhere in advanced options,
         **stop here and note that as the PoC's primary finding** — it
         means this action doesn't support attachments the way secondhand
         blog research suggested, and the file-passing approach needs to
         be rethought entirely before any further building.

   **Action 3 — Compose (raw response)**
   - **+ New step** → **Compose**. Rename to `Compose_Raw_Response`.
   - Inputs: click into the field, go to the **Dynamic content** tab (not
     Expression this time), and select the *entire* output object of the
     Execute Agent and wait action (usually offered as something like
     "Execute Agent and wait output" or just clicking the action's name in
     the dynamic content list) — not one specific field. This captures
     everything so you can see real field names.

   **Action 4 — Compose (parse attempt)**
   - **+ New step** → **Compose**. Rename to `Attempt_Parse_LastResponse`.
   - Inputs: switch to **Expression**, enter:
     ```
     json(body('Execute Agent and wait')?['lastResponse'])
     ```
     Use the exact action name shown in your flow for `Execute Agent and
     wait` inside the `body(...)` reference — if you renamed the action
     card, use that name instead (with underscores replacing spaces, as
     Power Automate does internally).

   **Action 5 — Teams: raw result**
   - **+ New step** → search **"Teams"** → **Post message in a channel**
     (Microsoft Teams connector).
   - Configure: pick any Team/Channel you can post test messages to — it
     does not need to be the real credit risk channel.
   - **Message**: switch to Expression or just build via dynamic
     content + text concatenation:
     ```
     concat('PoC raw Execute Agent response: ', string(outputs('Compose_Raw_Response')))
     ```
   - Rename this action to `Post_Raw_Result_To_Teams`.

   **Action 6 — Teams: parsed result**
   - **+ New step** → **Post message in a channel** again, same
     Team/Channel.
   - Message:
     ```
     concat('PoC parsed lastResponse: ', string(outputs('Attempt_Parse_LastResponse')))
     ```
   - Rename to `Post_Parsed_Result_To_Teams`.
   - **This action needs a specific "run after" configuration.** By
     default, Power Automate only runs an action if everything before it
     succeeded — that default is actually exactly what you want here, so
     you can usually leave it alone. Just confirm it: click the **"..."**
     menu on this action's card → **Configure run after**. You should see
     `Attempt_Parse_LastResponse` listed with only **"is successful"**
     checked, and **"has failed," "is skipped,"** and **"has timed out"**
     all unchecked. If `Attempt_Parse_LastResponse` fails (Action 4), this
     action simply won't run at all — and that absence is itself the
     answer to question 2 (see the results table below), so don't check
     the "has failed" box to try to force a message out of it.
6. Click **Save** (top-right).
7. **Share the flow with yourself** so it appears in Teams: **"..."** on
   the flow → **Share** (or open the flow's **Details** page → **Share**),
   add your own account (or the security group you'll use for testing) as
   a **Run only** user.

### 4. Run it

1. In Teams, open any channel you have access to and click into the
   message compose box.
2. Look for the **Workflows** icon (a small flow/gear-like icon — exact
   position varies: under the **+** below the text box, or in the row of
   icons under the compose box, depending on your Teams client version).
   If you don't see it, click **More apps** (the "···" at the far end of
   that icon row) and search for **Workflows**.
3. In the panel that opens, search for `Poc-ExecuteAgentAttachmentTest`.
   Select it.
4. A form should appear showing the **File** input you configured (step
   3.4) with an actual upload control. Click it, choose any small PDF from
   your device, and click **Run flow** (button label may vary — "Run,"
   "Create," or similar).
5. Wait roughly 10–30 seconds, then check the Teams channel you configured
   in Actions 5–6 for the result message(s).
6. If nothing arrives within a minute or two, go to
   [make.powerautomate.com](https://make.powerautomate.com) → **My
   flows** → `Poc-ExecuteAgentAttachmentTest` → **Run history**, open the
   most recent run, and inspect it action-by-action — the failure point
   itself is diagnostic information, not just a bug to fix.

## Reading the results

| What you see | What it means | Next step |
|---|---|---|
| Teams message with `"attachmentReceived": true` and a real file name/size | The attachment made it from Execute Agent into the topic, and a Question node with File entity auto-resolved it without prompting. | Question 1 is answered — production topic can use the same pattern. Move to question 2's result below. |
| Teams message containing the literal string `NO_ATTACHMENT_AUTO_RESOLVED` | The Question node had to ask — the attachment did **not** auto-satisfy it from the triggering activity. | Question 1 has a different answer than hoped. The production topic will need to read the file from somewhere other than a Question node — worth checking Copilot Studio docs/support for how a topic accesses `System.Activity.Attachments` (or equivalent) directly, since a mid-dialog prompt won't work with a single synchronous Execute-Agent-and-wait call anyway. |
| No Teams message at all, flow run history shows `Execute_Agent_And_Wait` failed | Either the agent/topic reference is wrong, or (if you got a specific policy/connection error) this could be the same DLP concern from the trigger-inversion work — check the error message before assuming it's a build mistake. | Fix the referenced agent/topic name, or escalate to your Power Platform admin if it looks like a policy block. |
| `Post_Raw_Result_To_Teams` arrives but `Post_Parsed_Result_To_Teams` never does | `Execute Agent and wait`'s response does **not** have a usable `lastResponse` field (or its content isn't valid JSON) — the raw-response message tells you the actual field name to use instead. | Re-read the raw response message, identify the real field holding the topic's reply text, and use that field name (not `lastResponse`) in the production flow's parse step. |
| Both Teams messages arrive, with matching content | Both questions are answered favorably — Execute Agent successfully round-trips a file and a text reply, and `lastResponse` really is the field. | Tell me what you saw and I'll rebuild the production flow/topic around the confirmed real mechanics, instead of the two incorrect designs before this one. |

## When you're done

Delete the `PoC Execute Agent Test` agent, delete
`Poc-ExecuteAgentAttachmentTest` from Power Automate, and remove
`agent/poc-attachment-echo-topic.yaml`, `flows/Poc-ExecuteAgentAttachmentTest.json`,
and this file from the repo — none of it should linger once it's served its
purpose.
