#!/usr/bin/env python3
"""
Build Power Automate import packages (.zip) for the Stablecoin Research Agent flows.

Output:
  flows/packages/Shared-FormatStablecoinReport.zip
  flows/packages/Shared-StablecoinEmailFlow.zip

Each zip follows the Power Automate export package structure:
  manifest.json
  Microsoft.Flow/flows/<guid>/definition.json
"""

import json
import zipfile
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
PACKAGES   = os.path.join(SCRIPT_DIR, "packages")
TEMPLATE   = os.path.join(REPO_ROOT, "templates", "stablecoin-report.html")

os.makedirs(PACKAGES, exist_ok=True)

with open(TEMPLATE, "r", encoding="utf-8") as fh:
    HTML_TEMPLATE = fh.read()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def manifest(display_name, description, flow_guid, resource_key,
             workflow_def, connection_refs=None, telemetry_guid=""):
    connection_refs = connection_refs or {}
    return {
        "schema": "1.0",
        "details": {
            "displayName":        display_name,
            "description":        description,
            "createdTime":        "2026-05-16T07:00:00Z",
            "packageTelemetryId": telemetry_guid,
            "creator":            "Stablecoin Research Agent",
            "sourceEnvironment":  ""
        },
        "resources": {
            resource_key: {
                "type":            "Microsoft.Flow/flows",
                "designerVersion": "2",
                "id":              resource_key,
                "name":            flow_guid,
                "properties": {
                    "displayName":  display_name,
                    "description":  description,
                    "environment":  {"id": "", "name": ""},
                    "definition":   workflow_def,
                    "apiDefinitions": {}
                },
                "creationType":      "New",
                "configurationData": {
                    "gateways":    {},
                    "connections": connection_refs
                },
                "comment":    "",
                "isManaged":  False
            }
        }
    }


def definition_envelope(flow_guid, display_name, description,
                        workflow_def, connection_references=None):
    connection_references = connection_references or {}
    return {
        "name": flow_guid,
        "id":   f"/providers/Microsoft.ProcessSimple/environments//flows/{flow_guid}",
        "type": "Microsoft.ProcessSimple/environments/flows",
        "properties": {
            "apiId":                "/providers/Microsoft.PowerApps/apis/shared_logicflows",
            "displayName":          display_name,
            "description":          description,
            "definition":           workflow_def,
            "connectionReferences": connection_references,
            "state":                "Started"
        }
    }


def write_zip(path, flow_guid, manifest_obj, definition_obj):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json",
                    json.dumps(manifest_obj, indent=2, ensure_ascii=False))
        zf.writestr(
            f"Microsoft.Flow/flows/{flow_guid}/definition.json",
            json.dumps(definition_obj, indent=2, ensure_ascii=False)
        )
    print(f"  Created: {os.path.relpath(path, REPO_ROOT)}")


# ═════════════════════════════════════════════════════════════════════════════
# FLOW 1 — Shared-FormatStablecoinReport
# ═════════════════════════════════════════════════════════════════════════════
FLOW1_GUID    = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
FLOW1_DISPLAY = "Shared-FormatStablecoinReport"
FLOW1_DESC    = (
    "Accepts structured stablecoin research JSON and returns a rendered HTML "
    "email body. Reusable by any Copilot Studio agent or Power Automate flow."
)

flow1_workflow = {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/"
               "schemas/2016-06-01/workflowdefinition.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "$connections":    {"defaultValue": {}, "type": "Object"},
        "$authentication": {"defaultValue": {}, "type": "SecureObject"}
    },
    "triggers": {
        "manual": {
            "type": "Request",
            "kind": "Http",
            "inputs": {
                "schema": {
                    "type": "object",
                    "required": [
                        "reportDate", "windowStart", "windowEnd",
                        "coins", "newsItems", "executiveSummary", "macroContext"
                    ],
                    "properties": {
                        "reportDate":       {"type": "string"},
                        "windowStart":      {"type": "string"},
                        "windowEnd":        {"type": "string"},
                        "generatedAt":      {"type": "string"},
                        "executiveSummary": {"type": "string"},
                        "macroContext":     {"type": "string"},
                        "coins": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name":           {"type": "string"},
                                    "ticker":         {"type": "string"},
                                    "priceUsd":       {"type": "number"},
                                    "pegDeltaPct":    {"type": "number"},
                                    "marketCapUsd":   {"type": "number"},
                                    "capDelta24hPct": {"type": "number"},
                                    "volume24hUsd":   {"type": "number"}
                                }
                            }
                        },
                        "newsItems": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title":       {"type": "string"},
                                    "source":      {"type": "string"},
                                    "publishedAt": {"type": "string"},
                                    "body":        {"type": "string"},
                                    "category":    {
                                        "type": "string",
                                        "enum": ["regulatory", "protocol", "market"]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "actions": {
        # ── Variables ──────────────────────────────────────────────────────
        "Init_CoinRows": {
            "type": "InitializeVariable",
            "inputs": {
                "variables": [{"name": "coinRowsHtml", "type": "string", "value": ""}]
            },
            "runAfter": {}
        },
        "Init_NewsHtml": {
            "type": "InitializeVariable",
            "inputs": {
                "variables": [{"name": "newsItemsHtml", "type": "string", "value": ""}]
            },
            "runAfter": {"Init_CoinRows": ["Succeeded"]}
        },

        # ── Embed the HTML template as a literal string ────────────────────
        "HTML_Template": {
            "type": "Compose",
            "inputs": HTML_TEMPLATE,
            "runAfter": {"Init_NewsHtml": ["Succeeded"]}
        },

        # ── Build coin table rows ──────────────────────────────────────────
        "Build_Coin_Rows": {
            "type": "Foreach",
            "foreach": "@triggerBody()?['coins']",
            "runAfter": {"HTML_Template": ["Succeeded"]},
            "actions": {
                "Peg_Class": {
                    "type": "Compose",
                    "runAfter": {},
                    "inputs": "@if(less(abs(items('Build_Coin_Rows')?['pegDeltaPct']), 0.1), 'peg-ok', if(less(abs(items('Build_Coin_Rows')?['pegDeltaPct']), 0.5), 'peg-warn', 'peg-alert'))"
                },
                "Peg_Label": {
                    "type": "Compose",
                    "runAfter": {"Peg_Class": ["Succeeded"]},
                    "inputs": "@if(less(abs(items('Build_Coin_Rows')?['pegDeltaPct']), 0.1), 'Stable', if(less(abs(items('Build_Coin_Rows')?['pegDeltaPct']), 0.5), 'Watch', 'Alert'))"
                },
                "Cap_Class": {
                    "type": "Compose",
                    "runAfter": {"Peg_Label": ["Succeeded"]},
                    "inputs": "@if(greaterOrEquals(items('Build_Coin_Rows')?['capDelta24hPct'], 0), 'cap-up', 'cap-down')"
                },
                "Peg_Delta_Str": {
                    "type": "Compose",
                    "runAfter": {"Cap_Class": ["Succeeded"]},
                    "inputs": "@concat(if(greaterOrEquals(items('Build_Coin_Rows')?['pegDeltaPct'], 0), '+', ''), string(items('Build_Coin_Rows')?['pegDeltaPct']), '%')"
                },
                "Cap_Delta_Str": {
                    "type": "Compose",
                    "runAfter": {"Peg_Delta_Str": ["Succeeded"]},
                    "inputs": "@concat(if(greaterOrEquals(items('Build_Coin_Rows')?['capDelta24hPct'], 0), '+', ''), string(items('Build_Coin_Rows')?['capDelta24hPct']), '%')"
                },
                "Market_Cap_Str": {
                    "type": "Compose",
                    "runAfter": {"Cap_Delta_Str": ["Succeeded"]},
                    "inputs": "@concat('$', string(div(items('Build_Coin_Rows')?['marketCapUsd'], 1000000000)), ' B')"
                },
                "Volume_Str": {
                    "type": "Compose",
                    "runAfter": {"Market_Cap_Str": ["Succeeded"]},
                    "inputs": "@concat('$', string(div(items('Build_Coin_Rows')?['volume24hUsd'], 1000000000)), ' B')"
                },
                "Row_Html": {
                    "type": "Compose",
                    "runAfter": {"Volume_Str": ["Succeeded"]},
                    "inputs": "@concat('<tr><td><span class=\"coin-name\">', items('Build_Coin_Rows')?['name'], '</span><span class=\"coin-ticker\">', items('Build_Coin_Rows')?['ticker'], '</span></td><td>$', string(items('Build_Coin_Rows')?['priceUsd']), '</td><td class=\"', outputs('Peg_Class'), '\">', outputs('Peg_Delta_Str'), '</td><td>', outputs('Market_Cap_Str'), '</td><td class=\"', outputs('Cap_Class'), '\">', outputs('Cap_Delta_Str'), '</td><td>', outputs('Volume_Str'), '</td><td class=\"', outputs('Peg_Class'), '\">', outputs('Peg_Label'), '</td></tr>')"
                },
                "Append_Row": {
                    "type": "AppendToStringVariable",
                    "runAfter": {"Row_Html": ["Succeeded"]},
                    "inputs": {
                        "name":  "coinRowsHtml",
                        "value": "@outputs('Row_Html')"
                    }
                }
            }
        },

        # ── Build news item blocks ─────────────────────────────────────────
        "Build_News_Items": {
            "type": "Foreach",
            "foreach": "@triggerBody()?['newsItems']",
            "runAfter": {"Build_Coin_Rows": ["Succeeded"]},
            "actions": {
                "News_Badge": {
                    "type": "Compose",
                    "runAfter": {},
                    "inputs": "@if(equals(items('Build_News_Items')?['category'], 'regulatory'), '<span class=\"badge-regulatory\">&#9888; Regulatory</span>', if(equals(items('Build_News_Items')?['category'], 'protocol'), '<span class=\"badge-protocol\">Protocol</span>', '<span class=\"badge-market\">Market</span>'))"
                },
                "News_Html": {
                    "type": "Compose",
                    "runAfter": {"News_Badge": ["Succeeded"]},
                    "inputs": "@concat('<div class=\"news-item\"><p class=\"news-title\">', outputs('News_Badge'), items('Build_News_Items')?['title'], '</p><p class=\"news-meta\">Source: ', items('Build_News_Items')?['source'], ' &nbsp;&middot;&nbsp; ', items('Build_News_Items')?['publishedAt'], '</p><p class=\"news-body\">', items('Build_News_Items')?['body'], '</p></div>')"
                },
                "Append_News": {
                    "type": "AppendToStringVariable",
                    "runAfter": {"News_Html": ["Succeeded"]},
                    "inputs": {
                        "name":  "newsItemsHtml",
                        "value": "@outputs('News_Html')"
                    }
                }
            }
        },

        # ── Inject values into template (chained replace calls) ────────────
        "Replace_ReportDate": {
            "type": "Compose",
            "runAfter": {"Build_News_Items": ["Succeeded"]},
            "inputs": "@replace(string(outputs('HTML_Template')), '{{REPORT_DATE}}', triggerBody()?['reportDate'])"
        },
        "Replace_WindowStart": {
            "type": "Compose",
            "runAfter": {"Replace_ReportDate": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_ReportDate'), '{{WINDOW_START}}', triggerBody()?['windowStart'])"
        },
        "Replace_WindowEnd": {
            "type": "Compose",
            "runAfter": {"Replace_WindowStart": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_WindowStart'), '{{WINDOW_END}}', triggerBody()?['windowEnd'])"
        },
        "Replace_GeneratedAt": {
            "type": "Compose",
            "runAfter": {"Replace_WindowEnd": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_WindowEnd'), '{{GENERATED_AT}}', coalesce(triggerBody()?['generatedAt'], utcNow()))"
        },
        "Replace_CoinCount": {
            "type": "Compose",
            "runAfter": {"Replace_GeneratedAt": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_GeneratedAt'), '{{COIN_COUNT}}', string(length(triggerBody()?['coins'])))"
        },
        "Replace_ExecSummary": {
            "type": "Compose",
            "runAfter": {"Replace_CoinCount": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_CoinCount'), '{{EXECUTIVE_SUMMARY}}', triggerBody()?['executiveSummary'])"
        },
        "Replace_CoinRows": {
            "type": "Compose",
            "runAfter": {"Replace_ExecSummary": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_ExecSummary'), '{{COIN_ROWS}}', variables('coinRowsHtml'))"
        },
        "Replace_NewsItems": {
            "type": "Compose",
            "runAfter": {"Replace_CoinRows": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_CoinRows'), '{{NEWS_ITEMS}}', variables('newsItemsHtml'))"
        },
        "Replace_MacroContext": {
            "type": "Compose",
            "runAfter": {"Replace_NewsItems": ["Succeeded"]},
            "inputs": "@replace(outputs('Replace_NewsItems'), '{{MACRO_CONTEXT}}', triggerBody()?['macroContext'])"
        },

        # ── Return rendered HTML ───────────────────────────────────────────
        "Respond": {
            "type": "Response",
            "runAfter": {"Replace_MacroContext": ["Succeeded"]},
            "inputs": {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "htmlBody":  "@outputs('Replace_MacroContext')",
                    "coinCount": "@length(triggerBody()?['coins'])",
                    "newsCount": "@length(triggerBody()?['newsItems'])"
                }
            }
        }
    },
    "outputs": {}
}

flow1_def_envelope = definition_envelope(
    FLOW1_GUID, FLOW1_DISPLAY, FLOW1_DESC, flow1_workflow
)
flow1_manifest = manifest(
    FLOW1_DISPLAY, FLOW1_DESC, FLOW1_GUID,
    resource_key="formatstablecoinreport",
    workflow_def=flow1_workflow,
    connection_refs={},
    telemetry_guid="c3d4e5f6-a7b8-9012-cdef-012345678901"
)

write_zip(
    os.path.join(PACKAGES, "Shared-FormatStablecoinReport.zip"),
    FLOW1_GUID, flow1_manifest, flow1_def_envelope
)


# ═════════════════════════════════════════════════════════════════════════════
# FLOW 2 — Shared-StablecoinEmailFlow
# ═════════════════════════════════════════════════════════════════════════════
FLOW2_GUID    = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
FLOW2_DISPLAY = "Shared-StablecoinEmailFlow"
FLOW2_DESC    = (
    "Generic reusable flow. Accepts an HTML body, subject, and optional "
    "recipient lists, then sends the email via Office 365 Outlook. Callable "
    "by any Copilot Studio agent or Power Automate flow."
)

flow2_workflow = {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/"
               "schemas/2016-06-01/workflowdefinition.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "$connections":    {"defaultValue": {}, "type": "Object"},
        "$authentication": {"defaultValue": {}, "type": "SecureObject"}
    },
    "triggers": {
        "manual": {
            "type": "Request",
            "kind": "Http",
            "inputs": {
                "schema": {
                    "type": "object",
                    "required": ["htmlBody", "subject"],
                    "properties": {
                        "htmlBody": {
                            "type": "string",
                            "description": "Fully rendered HTML email body"
                        },
                        "subject": {"type": "string"},
                        "to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Primary recipients. Falls back to default list if omitted."
                        },
                        "cc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "CC recipients. Falls back to default list if omitted."
                        },
                        "importance": {
                            "type": "string",
                            "enum": ["Low", "Normal", "High"],
                            "default": "Normal"
                        }
                    }
                }
            }
        }
    },
    "actions": {
        # ── Resolve recipients (use defaults when caller omits them) ───────
        "Init_To": {
            "type": "InitializeVariable",
            "runAfter": {},
            "inputs": {
                "variables": [{
                    "name":  "resolvedTo",
                    "type":  "array",
                    "value": "@if(empty(triggerBody()?['to']), createArray('analyst1@yourorg.com', 'analyst2@yourorg.com', 'portfoliomanager@yourorg.com'), triggerBody()?['to'])"
                }]
            }
        },
        "Init_Cc": {
            "type": "InitializeVariable",
            "runAfter": {"Init_To": ["Succeeded"]},
            "inputs": {
                "variables": [{
                    "name":  "resolvedCc",
                    "type":  "array",
                    "value": "@if(empty(triggerBody()?['cc']), createArray('compliance@yourorg.com', 'research-team@yourorg.com'), triggerBody()?['cc'])"
                }]
            }
        },
        "To_String": {
            "type": "Compose",
            "runAfter": {"Init_Cc": ["Succeeded"]},
            "inputs": "@join(variables('resolvedTo'), ';')"
        },
        "Cc_String": {
            "type": "Compose",
            "runAfter": {"To_String": ["Succeeded"]},
            "inputs": "@join(variables('resolvedCc'), ';')"
        },

        # ── Send via Office 365 Outlook ────────────────────────────────────
        "Send_Email": {
            "type": "ApiConnection",
            "runAfter": {"Cc_String": ["Succeeded"]},
            "inputs": {
                "host": {
                    "connection": {
                        "name": "@parameters('$connections')['shared_office365']['connectionId']"
                    }
                },
                "method": "post",
                "path":   "/v2/Mail",
                "body": {
                    "To":         "@outputs('To_String')",
                    "Cc":         "@outputs('Cc_String')",
                    "Subject":    "@triggerBody()?['subject']",
                    "Body":       "@triggerBody()?['htmlBody']",
                    "IsHtml":     True,
                    "Importance": "@coalesce(triggerBody()?['importance'], 'Normal')"
                }
            }
        },

        # ── Respond with send status ───────────────────────────────────────
        "Respond_Success": {
            "type": "Response",
            "runAfter": {"Send_Email": ["Succeeded"]},
            "inputs": {
                "statusCode": 200,
                "body": {
                    "status":    "sent",
                    "to":        "@outputs('To_String')",
                    "cc":        "@outputs('Cc_String')",
                    "subject":   "@triggerBody()?['subject']",
                    "timestamp": "@utcNow()"
                }
            }
        },
        "Respond_Failure": {
            "type": "Response",
            "runAfter": {"Send_Email": ["Failed", "TimedOut"]},
            "inputs": {
                "statusCode": 500,
                "body": {
                    "status":    "failed",
                    "error":     "@actions('Send_Email')?['error']",
                    "timestamp": "@utcNow()"
                }
            }
        }
    },
    "outputs": {}
}

flow2_connection_refs = {
    "shared_office365": {
        "runtimeSource": "embedded",
        "connection": {},
        "api": {"name": "shared_office365"}
    }
}

flow2_def_envelope = definition_envelope(
    FLOW2_GUID, FLOW2_DISPLAY, FLOW2_DESC,
    flow2_workflow, flow2_connection_refs
)
flow2_manifest = manifest(
    FLOW2_DISPLAY, FLOW2_DESC, FLOW2_GUID,
    resource_key="stablecoinemailflow",
    workflow_def=flow2_workflow,
    connection_refs={
        "shared_office365": {
            "source":       "Embedded",
            "id":           "/providers/Microsoft.PowerApps/apis/shared_office365",
            "creationType": "Existing"
        }
    },
    telemetry_guid="d4e5f6a7-b8c9-0123-defa-123456789012"
)

write_zip(
    os.path.join(PACKAGES, "Shared-StablecoinEmailFlow.zip"),
    FLOW2_GUID, flow2_manifest, flow2_def_envelope
)

print("Done — both packages ready in flows/packages/")
