# Drug Labeling MCP Server – GSA Flask & Databricks Quick start Guide

## Resources

- **GSA MCP Server Template:** [https://github.com/GSA-TTS/mcp-hackathon-template](https://github.com/GSA-TTS/mcp-hackathon-template)
- **Project Repository:** [https://github.com/gsa-mcp-hackathon/opioid_drug_explorer](https://github.com/gsa-mcp-hackathon/opioid_drug_explorer)

---

## 1. Initial Setup (Clone GSA Template)

Assuming `git` is installed, the following commands clone the GSA template, create a new empty Git repository, and push the template to the new repository:

```bash
git clone https://github.com/GSA-TTS/mcp-hackathon-template
cd mcp-hackathon-template
git remote rename origin upstream
git remote add origin https://github.com/<git-user-name>/<fda_mcp_hackathon>.git
git remote -v
git push -u origin main
```

---

## 2. Repository File Overview

### Original GSA Files

| Original File | Brief Description |
|---|---|
| `main.py` | Local entry point |
| `src/example_server/app.py` | Creates FastMCP and registers components |
| `tools/__init__.py` | Collects and registers MCP tools |
| `tools/example_tool.py` | Demonstrates how to implement a tool |
| `routes.py` | Provides `/health` and other HTTP routes |
| `config.py` | Manages environment configuration |
| `pyproject.toml` | Defines dependencies and project settings |
| `deploy/databricks/` | Contains deployment configuration and scripts |
| `tests/` | Contains automated tests |

### Added / Modified Files

| Added or Modified File | Function |
|---|---|
| `tools/drug_label.py` | Calls the OpenFDA API and extracts drug-label information |
| `tools/pdf_search.py` | Exposes open label updates PDF evidence retrieval as an MCP tool |
| `rag/fda_rag.py` | Extracts documents, creates text chunks, computes TF-IDF similarity, and retrieves evidence |
| `tools/__init__.py` | Registers the tools with FastMCP |
| `flask_ui/app.py` | Receives browser requests and invokes MCP tools |
| `flask_ui/templates/index.html` | Displays drug information and evidence combined |
| `combined_app.py` | Hosts Flask and FastMCP in one ASGI application |
| `app.yaml` | Defines the Databricks startup command |
| `test_fda_mcp.py` | Tests MCP connections and tool execution |

---

## 3. Local Testing

### Clone the Project

```bash
git clone https://github.com/nmkhan076/fda_mcp_hackathon
cd <downloaded git folder location>
```

Verify you are in the correct folder with:

```bash
dir
```

This should show `main.py`, `pyproject.toml`, `uv.lock`, `src/`, `flask_ui/`, `tests/`, etc.

---

### Install Project Dependencies

Check if `uv` is present:

```bash
uv --version
```

If not, install it:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

If `irm` is not working, try:

```bash
py -m pip install uv
# or
python -m pip install uv
```

Verify: `uv --version`

**Alternatively, use winget:**

```powershell
winget install --id astral-sh.uv -e
```

If you have already installed dependencies, this step simply verifies the environment:

```bash
uv sync --group dev
uv run python -c "import flask, fastmcp, uvicorn ; print('Dependencies OK')"
```

If `flask` or `uvicorn` are not already declared in the project, install them:

```bash
uv add flask uvicorn
```

**Troubleshooting:**

```bash
curl -I https://pypi.org/simple/flask
uv sync --group dev --native-tls -v
```

---

### Test the MCP Server Independently

**Terminal 1 – Start the MCP server:**

```cmd
# From cmd:
set MCP_TRANSPORT=streamable-http
# Or from PyCharm terminal:
$env:MCP_transport = "streamable-http"

uv run python main.py
```

Keep this terminal open. The MCP server should start on port **8000** (assuming default configuration has not been changed).

**Terminal 2 – Check server health:**

```powershell
Invoke-RestMethod -Uri http://localhost:8000/health
# or
curl.exe -i http://localhost:8000/health
```

A `healthy` status confirms the server has started successfully.

**Check the tools:**

```bash
uv run python test_fda_mcp.py
```

This shows available tools defined/registered and results from different tools with default values or queries defined in the file. If `success: false` is received, examine the error message.

---

### Test Combined Flask UI + MCP Application

Stop the server started in the earlier step, then run:

```powershell
$env:PYTHONPATH = "$((Get-Location).Path);$((Get-Location).Path)\src"
uv run python -m example_server.combined_app
```

Keep this terminal open and check the URLs.

---

### Local Endpoints

| Endpoint | Expected Result |
|---|---|
| `http://127.0.0.1:8000/` | Flask UI |
| `http://127.0.0.1:8000/health` | JSON healthy status |
| `http://127.0.0.1:8000/mcp` | MCP client endpoint (not a browser page) |

---

## 4. Deploy on Databricks

### Option A: Browser (No Terminal)

1. **Connect GitHub:** Sign into the Databricks workspace. Under **Workspace → user folder**, select **Create/New → Git folder**. Paste `https://github.com/nmkhan076/fda_mcp_hackathon.git`, choose **GitHub** and **main**. If prompted, configure Git credentials under user settings.

2. **Confirm Source:** Open the Git folder. Ensure root `app.yaml`, `pyproject.toml`, `uv.lock`, `flask_ui/`, `src/`, and `data/` are visible. Deploy the **repository root**, not `src/example_server` or `flask_ui` alone.

3. **Create and Deploy App:** Open **Databricks Apps → Create app → Custom app** (wording varies). Select your workspace folder as source and click **Deploy**. For an existing app, choose **Deploy** with the same root source path.

4. **Validate:** In **Apps → Overview/Deployments**, confirm **Running**; open the App URL (Flask UI), `/health`, and use an authenticated MCP client for `/mcp`. For failures, open **Logs** and read the first Python traceback.

5. **For Updates:** Push commits to GitHub; in the Databricks Git folder, use **Pull**; then redeploy the App.

---

### Option B: Databricks CLI

**Prerequisites:** Databricks CLI installed; authenticated account with Apps and workspace-folder permissions; use the same identity for source ownership and deployment.

> Commands below are PowerShell unless labeled Git Bash.

```bash
databricks version
databricks auth login --host https://YOUR-WORKSPACE.cloud.databricks.com
databricks auth profiles
databricks current-user me
```

**Deploy directly from PowerShell** (assuming the root `app.yaml` exists):

```powershell
$app = "opioid-drug-mcp-server"
$source = "/Workspace/Users/YOUR-EMAIL/fda_mcp_hackathon"

databricks apps create $app    # skip if app already exists
databricks sync . $source
databricks apps deploy $app --source-code-path $source
databricks apps get $app
```

---

## 5. Adding a New MCP Tool and Exposing It in Flask

**Example:** Add a small, read-only tool for a known FDA document identifier. Implement it in a new module; do not redefine the entire FastMCP server.

**Step 1 – Implement the tool:**

```python
# src/example_server/tools/document_info.py
from fastmcp import FastMCP

def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def document_info(document_id: str) -> dict:
        """Return metadata for a supplied document ID."""
        return {"success": True, "document_id": document_id}
```

**Step 2 – Register it in `src/example_server/tools/__init__.py`:**

```python
from example_server.tools import document_info

# Inside register_tools(mcp):
document_info.register(mcp)
```

**Step 3 – Connect Flask to the new tool:**

```python
# Inside an async function in flask_ui/app.py, with a connected session:
result = await session.call_tool("document_info", {"document_id": document_id})
# Parse result.structured_content (or JSON text fallback)
# and pass parsed data to render_template(...)
```

---

## 6. GitHub CI / Linting

GitHub CI may throw errors for commits if formatting issues appear in files. Resolve them by running:

```bash
uv run ruff check . --fix
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/ -v
```

If all tests pass, then run:

```bash
git add .
git commit -m "Update FDA MCP and Flask app"
git push
```
