#!/usr/bin/env python3
"""
Build Power Automate import packages (.zip) for the Stablecoin and Stapleton Research Agent flows.

Output:
  flows/packages/Shared-FormatStablecoinReport.zip
  flows/packages/Shared-StablecoinEmailFlow.zip
  flows/packages/Shared-FormatStapletonReport.zip

Each zip follows the Power Automate export package structure:
  manifest.json
  Microsoft.Flow/flows/<guid>/definition.json
"""

import json
import zipfile
import os

SCRIPT_DIR         = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT          = os.path.dirname(SCRIPT_DIR)
PACKAGES           = os.path.join(SCRIPT_DIR, "packages")
TEMPLATE           = os.path.join(REPO_ROOT, "templates", "stablecoin-report.html")
STAPLETON_TEMPLATE = os.path.join(REPO_ROOT, "templates", "stapleton-report.html")

os.makedirs(PACKAGES, exist_ok=True)

with open(TEMPLATE, "r", encoding="utf-8") as fh:
    HTML_TEMPLATE = fh.read()

with open(STAPLETON_TEMPLATE, "r", encoding="utf-8") as fh:
    STAPLETON_HTML = fh.read()


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

print("Done — Flow 1 & 2 packages ready in flows/packages/")


# ═════════════════════════════════════════════════════════════════════════════
# FLOW 3 — Shared-FormatStapletonReport
# ═════════════════════════════════════════════════════════════════════════════
FLOW3_GUID    = "c3d4e5f6-a7b8-9012-cdef-012345678902"
FLOW3_DISPLAY = "Shared-FormatStapletonReport"
FLOW3_DESC    = (
    "Accepts structured Stapleton community research JSON and returns a rendered "
    "HTML email body. Reusable by any Copilot Studio agent or Power Automate flow."
)

flow3_workflow = {
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
                        "executiveSummary", "developments", "realEstateSnapshot"
                    ],
                    "properties": {
                        "reportDate":       {"type": "string"},
                        "windowStart":      {"type": "string"},
                        "windowEnd":        {"type": "string"},
                        "generatedAt":      {"type": "string"},
                        "executiveSummary": {"type": "string"},
                        "developments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "category":    {"type": "string"},
                                    "title":       {"type": "string"},
                                    "description": {"type": "string"},
                                    "source":      {"type": "string"},
                                    "publishedAt": {"type": "string"},
                                    "impact":      {"type": "string"}
                                }
                            }
                        },
                        "realEstateSnapshot": {
                            "type": "object",
                            "properties": {
                                "medianListPrice":   {"type": "number"},
                                "priceChangePct":    {"type": "number"},
                                "activeListings":    {"type": "number"},
                                "listingsChangePct": {"type": "number"},
                                "avgDaysOnMarket":   {"type": "number"},
                                "newListings24h":    {"type": "number"}
                            }
                        },
                        "events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title":       {"type": "string"},
                                    "date":        {"type": "string"},
                                    "location":    {"type": "string"},
                                    "description": {"type": "string"}
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
        "Init_DevItems": {
            "type": "InitializeVariable",
            "inputs": {
                "variables": [{"name": "devItemsHtml", "type": "string", "value": ""}]
            },
            "runAfter": {}
        },
        "Init_EventItems": {
            "type": "InitializeVariable",
            "inputs": {
                "variables": [{"name": "eventItemsHtml", "type": "string", "value": ""}]
            },
            "runAfter": {"Init_DevItems": ["Succeeded"]}
        },

        # ── Embed Stapleton HTML template ──────────────────────────────────
        "HTML_Template": {
            "type": "Compose",
            "inputs": STAPLETON_HTML,
            "runAfter": {"Init_EventItems": ["Succeeded"]}
        },

        # ── Build development item cards ───────────────────────────────────
        "Build_Dev_Items": {
            "type": "Foreach",
            "foreach": "@triggerBody()?['developments']",
            "runAfter": {"HTML_Template": ["Succeeded"]},
            "actions": {
                "Category_Badge": {
                    "type": "Compose",
                    "runAfter": {},
                    "inputs": (
                        "@if(equals(items('Build_Dev_Items')?['category'], 'real-estate'),"
                        " '<span class=\"badge badge-real-estate\">Real Estate</span>',"
                        " if(equals(items('Build_Dev_Items')?['category'], 'infrastructure'),"
                        " '<span class=\"badge badge-infrastructure\">Infrastructure</span>',"
                        " if(equals(items('Build_Dev_Items')?['category'], 'community'),"
                        " '<span class=\"badge badge-community\">Community</span>',"
                        " if(equals(items('Build_Dev_Items')?['category'], 'business'),"
                        " '<span class=\"badge badge-business\">Business</span>',"
                        " if(equals(items('Build_Dev_Items')?['category'], 'safety'),"
                        " '<span class=\"badge badge-safety\">&#9888; Safety</span>',"
                        " '<span class=\"badge badge-government\">Government</span>')))))"
                    )
                },
                "Impact_Label": {
                    "type": "Compose",
                    "runAfter": {"Category_Badge": ["Succeeded"]},
                    "inputs": (
                        "@if(equals(items('Build_Dev_Items')?['impact'], 'high'),"
                        " '<span class=\"impact-high\">&#9650; High Impact</span>',"
                        " if(equals(items('Build_Dev_Items')?['impact'], 'medium'),"
                        " '<span class=\"impact-medium\">&#9654; Medium Impact</span>',"
                        " '<span class=\"impact-low\">&#9658; Low Impact</span>'))"
                    )
                },
                "Dev_Html": {
                    "type": "Compose",
                    "runAfter": {"Impact_Label": ["Succeeded"]},
                    "inputs": (
                        "@concat('<div class=\"dev-item\"><div class=\"dev-header\">',"
                        " outputs('Category_Badge'), ' ', outputs('Impact_Label'),"
                        " '</div><p class=\"dev-title\">',"
                        " items('Build_Dev_Items')?['title'],"
                        " '</p><p class=\"dev-meta\">Source: ',"
                        " items('Build_Dev_Items')?['source'],"
                        " ' &nbsp;&middot;&nbsp; ',"
                        " items('Build_Dev_Items')?['publishedAt'],"
                        " '</p><p class=\"dev-body\">',"
                        " items('Build_Dev_Items')?['description'],"
                        " '</p></div>')"
                    )
                },
                "Append_Dev": {
                    "type": "AppendToStringVariable",
                    "runAfter": {"Dev_Html": ["Succeeded"]},
                    "inputs": {"name": "devItemsHtml", "value": "@outputs('Dev_Html')"}
                }
            }
        },

        # ── Build event list items ─────────────────────────────────────────
        "Build_Event_Items": {
            "type": "Foreach",
            "foreach": "@triggerBody()?['events']",
            "runAfter": {"Build_Dev_Items": ["Succeeded"]},
            "actions": {
                "Event_Html": {
                    "type": "Compose",
                    "runAfter": {},
                    "inputs": (
                        "@concat('<div class=\"event-item\"><div class=\"event-date-box\">',"
                        " '<span class=\"ev-month\">', substring(items('Build_Event_Items')?['date'], 0, 3), '</span>',"
                        " '<span class=\"ev-day\">', substring(items('Build_Event_Items')?['date'], 4, 2), '</span>',"
                        " '</div><div class=\"event-details\">',"
                        " '<p class=\"ev-title\">', items('Build_Event_Items')?['title'], '</p>',"
                        " '<p class=\"ev-location\">', items('Build_Event_Items')?['location'], '</p>',"
                        " '<p class=\"ev-desc\">', coalesce(items('Build_Event_Items')?['description'], ''), '</p>',"
                        " '</div></div>')"
                    )
                },
                "Append_Event": {
                    "type": "AppendToStringVariable",
                    "runAfter": {"Event_Html": ["Succeeded"]},
                    "inputs": {"name": "eventItemsHtml", "value": "@outputs('Event_Html')"}
                }
            }
        },

        # ── Fallback for empty events ──────────────────────────────────────
        "Events_Or_Placeholder": {
            "type": "Compose",
            "runAfter": {"Build_Event_Items": ["Succeeded"]},
            "inputs": "@if(empty(variables('eventItemsHtml')), '<p class=\"no-events\">No community events scheduled in the next 14 days.</p>', variables('eventItemsHtml'))"
        },

        # ── Compute real estate delta strings and CSS classes ──────────────
        "RE_PriceClass": {
            "type": "Compose",
            "runAfter": {"Events_Or_Placeholder": ["Succeeded"]},
            "inputs": "@if(greaterOrEquals(triggerBody()?['realEstateSnapshot']?['priceChangePct'], 0), 're-up', 're-down')"
        },
        "RE_PriceChange": {
            "type": "Compose",
            "runAfter": {"RE_PriceClass": ["Succeeded"]},
            "inputs": "@concat(if(greaterOrEquals(triggerBody()?['realEstateSnapshot']?['priceChangePct'], 0), '+', ''), string(triggerBody()?['realEstateSnapshot']?['priceChangePct']), '% vs yesterday')"
        },
        "RE_ListingsClass": {
            "type": "Compose",
            "runAfter": {"RE_PriceChange": ["Succeeded"]},
            "inputs": "@if(greaterOrEquals(triggerBody()?['realEstateSnapshot']?['listingsChangePct'], 0), 're-up', 're-down')"
        },
        "RE_ListingsChange": {
            "type": "Compose",
            "runAfter": {"RE_ListingsClass": ["Succeeded"]},
            "inputs": "@concat(if(greaterOrEquals(triggerBody()?['realEstateSnapshot']?['listingsChangePct'], 0), '+', ''), string(triggerBody()?['realEstateSnapshot']?['listingsChangePct']), '% vs yesterday')"
        },

        # ── Inject all values into template ───────────────────────────────
        "R1":  {"type": "Compose", "runAfter": {"RE_ListingsChange": ["Succeeded"]},
                "inputs": "@replace(string(outputs('HTML_Template')), '{{REPORT_DATE}}', triggerBody()?['reportDate'])"},
        "R2":  {"type": "Compose", "runAfter": {"R1": ["Succeeded"]},
                "inputs": "@replace(outputs('R1'), '{{WINDOW_START}}', triggerBody()?['windowStart'])"},
        "R3":  {"type": "Compose", "runAfter": {"R2": ["Succeeded"]},
                "inputs": "@replace(outputs('R2'), '{{WINDOW_END}}', triggerBody()?['windowEnd'])"},
        "R4":  {"type": "Compose", "runAfter": {"R3": ["Succeeded"]},
                "inputs": "@replace(outputs('R3'), '{{GENERATED_AT}}', coalesce(triggerBody()?['generatedAt'], utcNow()))"},
        "R5":  {"type": "Compose", "runAfter": {"R4": ["Succeeded"]},
                "inputs": "@replace(outputs('R4'), '{{DEV_COUNT}}', string(length(triggerBody()?['developments'])))"},
        "R6":  {"type": "Compose", "runAfter": {"R5": ["Succeeded"]},
                "inputs": "@replace(outputs('R5'), '{{EXECUTIVE_SUMMARY}}', triggerBody()?['executiveSummary'])"},
        "R7":  {"type": "Compose", "runAfter": {"R6": ["Succeeded"]},
                "inputs": "@replace(outputs('R6'), '{{DEVELOPMENT_ITEMS}}', variables('devItemsHtml'))"},
        "R8":  {"type": "Compose", "runAfter": {"R7": ["Succeeded"]},
                "inputs": "@replace(outputs('R7'), '{{RE_MEDIAN_PRICE}}', concat('$', string(triggerBody()?['realEstateSnapshot']?['medianListPrice'])))"},
        "R9":  {"type": "Compose", "runAfter": {"R8": ["Succeeded"]},
                "inputs": "@replace(outputs('R8'), '{{RE_PRICE_CLASS}}', outputs('RE_PriceClass'))"},
        "R10": {"type": "Compose", "runAfter": {"R9": ["Succeeded"]},
                "inputs": "@replace(outputs('R9'), '{{RE_PRICE_CHANGE}}', outputs('RE_PriceChange'))"},
        "R11": {"type": "Compose", "runAfter": {"R10": ["Succeeded"]},
                "inputs": "@replace(outputs('R10'), '{{RE_ACTIVE_LISTINGS}}', string(triggerBody()?['realEstateSnapshot']?['activeListings']))"},
        "R12": {"type": "Compose", "runAfter": {"R11": ["Succeeded"]},
                "inputs": "@replace(outputs('R11'), '{{RE_LISTINGS_CLASS}}', outputs('RE_ListingsClass'))"},
        "R13": {"type": "Compose", "runAfter": {"R12": ["Succeeded"]},
                "inputs": "@replace(outputs('R12'), '{{RE_LISTINGS_CHANGE}}', outputs('RE_ListingsChange'))"},
        "R14": {"type": "Compose", "runAfter": {"R13": ["Succeeded"]},
                "inputs": "@replace(outputs('R13'), '{{RE_AVG_DAYS}}', string(triggerBody()?['realEstateSnapshot']?['avgDaysOnMarket']))"},
        "R15": {"type": "Compose", "runAfter": {"R14": ["Succeeded"]},
                "inputs": "@replace(outputs('R14'), '{{RE_NEW_CLASS}}', 're-up')"},
        "R16": {"type": "Compose", "runAfter": {"R15": ["Succeeded"]},
                "inputs": "@replace(outputs('R15'), '{{RE_NEW_LISTINGS}}', string(triggerBody()?['realEstateSnapshot']?['newListings24h']))"},
        "R17": {"type": "Compose", "runAfter": {"R16": ["Succeeded"]},
                "inputs": "@replace(outputs('R16'), '{{EVENT_ITEMS}}', outputs('Events_Or_Placeholder'))"},

        # ── Return rendered HTML ───────────────────────────────────────────
        "Respond": {
            "type": "Response",
            "runAfter": {"R17": ["Succeeded"]},
            "inputs": {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "htmlBody":   "@outputs('R17')",
                    "devCount":   "@length(triggerBody()?['developments'])",
                    "eventCount": "@length(triggerBody()?['events'])"
                }
            }
        }
    },
    "outputs": {}
}

flow3_def_envelope = definition_envelope(
    FLOW3_GUID, FLOW3_DISPLAY, FLOW3_DESC, flow3_workflow
)
flow3_manifest = manifest(
    FLOW3_DISPLAY, FLOW3_DESC, FLOW3_GUID,
    resource_key="formatstapletonreport",
    workflow_def=flow3_workflow,
    connection_refs={},
    telemetry_guid="e5f6a7b8-c9d0-1234-efab-234567890123"
)

write_zip(
    os.path.join(PACKAGES, "Shared-FormatStapletonReport.zip"),
    FLOW3_GUID, flow3_manifest, flow3_def_envelope
)

print("Done — all 3 packages ready in flows/packages/")
