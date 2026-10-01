# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
import urllib.request
from typing import Any
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types
from google.cloud import firestore, storage

from .a2ui_utils import a2ui_callback

# Hardcoded project ID and bucket name as required to prevent Agent Platform project number resolution issues
PROJECT_ID = "qwiklabs-gcp-01-136c2b1f011b"
COLLECTION_NAME = "workloads"
BUCKET_NAME = "novacorp-ai-governance-qwiklabs-gcp-01-136c2b1f011b"
MEMORY_BANK_ID = "2078190775950114816"

# Set default Agent Engine ID for Memory Bank service auto-configuration when deployed
os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ID", MEMORY_BANK_ID)

# Load Agent Engine resource name from deployment_metadata.json if available
DEPLOYMENT_METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")


def _get_agent_engine_resource_name() -> str | None:
    if os.path.exists(DEPLOYMENT_METADATA_PATH):
        try:
            with open(DEPLOYMENT_METADATA_PATH, "r") as f:
                meta = json.load(f)
                return meta.get("remote_agent_runtime_id")
        except Exception:
            pass
    return None


code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=_get_agent_engine_resource_name()
)

# Seeded fallback workload inventory if Firestore database is uninitialized
_LOCAL_WORKLOADS: dict[str, dict[str, Any]] = {
    "price-match-agent": {
        "workload_id": "price-match-agent",
        "display_name": "Price Match Agent",
        "environment": "managed_runtime",
        "is_registered": True,
        "service_account": "price-match-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "active",
        "last_audit": "2026-10-01",
    },
    "markdown-strategy-agent": {
        "workload_id": "markdown-strategy-agent",
        "display_name": "Markdown Strategy Agent",
        "environment": "managed_runtime",
        "is_registered": True,
        "service_account": "markdown-strategy-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "active",
        "last_audit": "2026-10-01",
    },
    "customer-personalization-agent": {
        "workload_id": "customer-personalization-agent",
        "display_name": "Customer Personalization Agent",
        "environment": "managed_runtime",
        "is_registered": True,
        "service_account": "novasmart-customer-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "active",
        "last_audit": "2026-10-01",
    },
    "promo-agent-shadow": {
        "workload_id": "promo-agent-shadow",
        "display_name": "Promo Agent Shadow",
        "environment": "cloud_run",
        "is_registered": False,
        "service_account": "novasmart-customer-sa@qwiklabs-gcp-01-136c2b1f011b.iam.gserviceaccount.com",
        "status": "flagged",
        "last_audit": "2026-10-01",
    },
}


def _get_firestore_client():
    return firestore.Client(project=PROJECT_ID)


def list_workloads(status_filter: str = "") -> str:
    """List AI workload records from the Firestore database collection.

    Args:
        status_filter: Optional filter by status (e.g., 'active', 'flagged').

    Returns:
        JSON string listing workload objects.
    """
    try:
        db = _get_firestore_client()
        docs = db.collection(COLLECTION_NAME).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            if not status_filter or data.get("status") == status_filter:
                results.append(data)
        if results:
            return json.dumps(results, indent=2)
    except Exception:
        pass

    filtered = [
        w for w in _LOCAL_WORKLOADS.values()
        if not status_filter or w.get("status") == status_filter
    ]
    return json.dumps(filtered, indent=2)


def get_workload_details(workload_id: str) -> str:
    """Retrieve detailed record for a specific AI workload document by ID.

    Args:
        workload_id: The unique ID of the workload (e.g., 'price-match-agent').

    Returns:
        JSON string containing the workload properties.
    """
    try:
        db = _get_firestore_client()
        doc = db.collection(COLLECTION_NAME).document(workload_id).get()
        if doc.exists:
            return json.dumps(doc.to_dict(), indent=2)
    except Exception:
        pass

    if workload_id in _LOCAL_WORKLOADS:
        return json.dumps(_LOCAL_WORKLOADS[workload_id], indent=2)
    return json.dumps({"error": f"Workload '{workload_id}' not found."})


def register_or_update_workload(
    workload_id: str,
    display_name: str,
    environment: str,
    is_registered: bool,
    service_account: str,
    status: str = "active",
) -> str:
    """Create or update an AI workload record in the Firestore database collection.

    Args:
        workload_id: Unique workload identifier.
        display_name: Human-readable name of the agent workload.
        environment: Execution environment ('managed_runtime' or 'cloud_run').
        is_registered: Whether the workload is registered in central Agent Registry.
        service_account: Service account email used by the workload.
        status: Operational status ('active', 'flagged', 'audited').

    Returns:
        JSON status message confirming the write operation.
    """
    record = {
        "workload_id": workload_id,
        "display_name": display_name,
        "environment": environment,
        "is_registered": is_registered,
        "service_account": service_account,
        "status": status,
        "last_audit": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    }

    _LOCAL_WORKLOADS[workload_id] = record

    try:
        db = _get_firestore_client()
        db.collection(COLLECTION_NAME).document(workload_id).set(record)
        return json.dumps({"message": f"Successfully updated Firestore workload '{workload_id}'.", "record": record})
    except Exception as e:
        return json.dumps({"message": f"Updated workload record for '{workload_id}'.", "record": record})


def upload_audit_report_to_gcs(
    workload_id: str,
    audit_findings: str,
    severity: str = "medium",
) -> str:
    """Generates a security audit report for an AI workload and uploads it to public Cloud Storage.

    Args:
        workload_id: Unique identifier of the workload being audited (e.g., 'promo-agent-shadow').
        audit_findings: Detailed audit notes, policy compliance observations, or risk assessment.
        severity: Severity rating ('low', 'medium', 'high', 'critical').

    Returns:
        JSON object containing confirmation message and public HTTPS URL to the report artifact.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    filename = f"audits/{workload_id}_audit.json"

    report_data = {
        "workload_id": workload_id,
        "timestamp": timestamp,
        "severity": severity,
        "audit_findings": audit_findings,
        "inspector": "NovaSmart AI Platform & Security Agent",
    }

    try:
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(
            data=json.dumps(report_data, indent=2),
            content_type="application/json",
        )
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return json.dumps({
            "message": f"Security audit report for '{workload_id}' successfully uploaded to Cloud Storage.",
            "public_url": public_url,
            "report": report_data,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to upload report to Cloud Storage: {str(e)}"}, indent=2)


def check_package_vulnerabilities(package_name: str, ecosystem: str = "PyPI") -> str:
    """Queries the Open Source Vulnerability (OSV.dev) public API to check security advisories for an agent dependency package.

    Args:
        package_name: Name of the package dependency to check (e.g., 'aiohttp', 'google-adk', 'fastapi').
        ecosystem: Package ecosystem (e.g., 'PyPI', 'npm'). Defaults to 'PyPI'.

    Returns:
        JSON string listing vulnerability advisories from the OSV database.
    """
    api_key = os.environ.get("OSV_API_KEY", "")
    url = "https://api.osv.dev/v1/query"

    payload = json.dumps({"package": {"name": package_name, "ecosystem": ecosystem}}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            vulns = data.get("vulns", [])
            summary = [
                {
                    "id": v.get("id"),
                    "summary": v.get("summary", "No summary available"),
                }
                for v in vulns[:5]
            ]
            return json.dumps({
                "package": package_name,
                "ecosystem": ecosystem,
                "total_vulnerabilities": len(vulns),
                "advisories": summary,
            }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch vulnerability advisories: {str(e)}"}, indent=2)


async def generate_governance_image(
    prompt_description: str,
    tool_context: ToolContext,
) -> str:
    """Generates a visual diagram or graphic for an AI governance item using gemini-3.1-flash-lite-image in the global region.

    Saves the image into the Playground Artifacts panel via tool_context.save_artifact, and uploads it to public Cloud Storage, returning the public HTTPS URL.

    Args:
        prompt_description: Description of the governance graphic to generate (e.g. 'security topology map', 'workload risk badge').
        tool_context: Context provided automatically by ADK framework.

    Returns:
        JSON string containing the public HTTPS URL of the uploaded image.
    """
    cleaned_name = "".join(c if c.isalnum() else "_" for c in prompt_description[:30].strip().lower()).strip("_")
    if not cleaned_name:
        cleaned_name = "governance_graphic"

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifact_name = f"{cleaned_name}_{timestamp_str}"

    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"High quality professional security governance graphic: {prompt_description}",
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        image_bytes = None
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    break

        if not image_bytes:
            return json.dumps({"error": "Failed to extract image bytes from model response."})

        # 1. Save as Playground session artifact using await tool_context.save_artifact
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        await tool_context.save_artifact(filename=f"{artifact_name}.png", artifact=artifact_part)

        # 2. Upload directly to public Cloud Storage bucket
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"images/{artifact_name}.png"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type="image/png")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"

        return json.dumps({
            "message": "Successfully generated governance image and uploaded to Cloud Storage.",
            "public_url": public_url,
            "artifact_filename": f"{artifact_name}.png",
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to generate image: {str(e)}"}, indent=2)


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The query or name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each turn, extract durable facts to Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="You are NovaSmart's AI Platform & Governance assistant. Help users discover, inspect, audit, check vulnerabilities, execute Python code safely in a sandbox, and generate security visual graphics for AI workload records. You remember user preferences and facts across sessions.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        list_workloads,
        get_workload_details,
        register_or_update_workload,
        upload_audit_report_to_gcs,
        check_package_vulnerabilities,
        generate_governance_image,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
