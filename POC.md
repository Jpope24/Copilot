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

In [copilotstudio.microsoft.com](https://copilotstudio.microsoft.com), same
environment you'll use for the real tool: **Create → New agent → Skip to
configure**. Name it something obviously disposable, e.g. `PoC Execute
Agent Test`. You do not need to configure Instructions or anything else.

### 2. Build the PoC topic

**Topics → Add a topic → Create from blank.** Name it `PoC Echo
Attachment`. Give it exactly one trigger phrase: `poc echo attachment`
(Classic phrase trigger — don't rely on generative orchestration for this
test, it adds a variable you don't want yet).

Add two steps, matching `agent/poc-attachment-echo-topic.yaml`:

1. **Question** node — **Identify**: **File** (this is the entity type
   Microsoft's own docs call "Attachment" under the hood). Variable name:
   `TestFile`. Prompt text (only relevant if the node actually has to ask):
   `NO_ATTACHMENT_AUTO_RESOLVED`.
2. **Send a message** node — message text (use the **{x}** / formula
   button to build this as an expression, not literal text):
   ```
   {"attachmentReceived": !IsBlank(Topic.TestFile), "fileName": If(IsBlank(Topic.TestFile), "none", Topic.TestFile.Name), "fileSizeBytes": If(IsBlank(Topic.TestFile), 0, Topic.TestFile.Size)}
   ```
   (Exact Power Fx property names — `.Name` / `.Size` vs. lowercase, etc. —
   may differ slightly in your designer; use whatever the formula bar's
   autocomplete offers for the `TestFile` variable.)

**Publish** this throwaway agent.

### 3. Build the PoC flow

**Power Automate → + Create → Instant cloud flow**, trigger **"Manually
trigger a flow."** Add a **File** input named `testFile` (should auto-pair
a filename field).

Add actions in order:

1. **Compose** — `concat('data:application/pdf;base64,', triggerBody()?['testFile'])`
2. **Copilot Studio → "Execute Agent and wait"** (search "Copilot Studio"
   in the connector list if it doesn't show up under a category). This is
   the action to actually inspect carefully — its real field layout is
   exactly what this PoC exists to discover:
   - Point it at the **PoC Execute Agent Test** agent from step 1.
   - Message/body field: literal text `poc echo attachment`.
   - Look for an **Advanced parameters** / **Show advanced options**
     toggle — under it, look for an **attachments** field. Add one
     attachment: name = the trigger's filename output, content type =
     `application/pdf`, content/URL = the Compose output from step 1.
     **If there's no attachments field at all**, that's itself an
     important finding — note it and stop here; it means this action
     doesn't support attachments the way secondhand research suggested,
     and the whole "flow calls agent with a file" approach needs
     rethinking before going further.
3. **Compose** (`Compose_Raw_Response`) — `body('Execute Agent and wait')`
   (select the whole output via dynamic content, not a specific field).
4. **Compose** (`Attempt_Parse_LastResponse`) —
   `json(body('Execute Agent and wait')?['lastResponse'])`
5. **Teams → "Post message in a channel"** (`Post_Raw_Result_To_Teams`) —
   any test channel, message: `concat('PoC raw Execute Agent response: ', string(outputs('Compose_Raw_Response')))`. Run after step 3 succeeded.
6. **Teams → "Post message in a channel"** (`Post_Parsed_Result_To_Teams`)
   — same channel, message:
   `concat('PoC parsed lastResponse: ', string(outputs('Attempt_Parse_LastResponse')))`.
   Configure **Run after** step 4 **has succeeded** only (leave "has
   failed" unchecked) — if step 4 fails, you should see the raw-response
   message from step 5 but not this one, and that absence is itself the
   answer to question 2.

**Save** the flow. Share it with yourself if needed so it appears in your
Teams flow picker (same as production Part G).

### 4. Run it

From Teams, launch the flow (Workflows/Power Automate picker in the
compose box) and upload any small PDF.

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
