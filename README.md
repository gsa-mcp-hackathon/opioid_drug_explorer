# Drug Labeling MCP Server

A drug-labeling research assistant built with **Model Context Protocol (MCP)**, **FastMCP**, **Flask**, and **Databricks**. The project provides structured access to public drug-labeling sources and FDA PDF reference materials, with an emphasis on opioid safety information, CYP-mediated interactions, and evidence-grounded responses.

> **Hackathon 2026 project:** A prototype for exploring FDA drug-labeling information. It is not a clinical decision-support system and should not be used as a substitute for official prescribing information or medical advice.

## Features

- **Drug label lookup:** Search for drug-label information by generic or brand name, using openFDA and a DailyMed fallback where supported.
- **CYP label details : Drug interaction, Enzyme Metabolism:** Examine labeling information related to CYP2D6 and CYP3A4 for selected opioids, with effective label dates, summaries, and detailed evidence.
- **FDA PDF search / RAG:** Retrieve relevant content from a curated set of FDA PDF documents and generate evidence-grounded answers using a Databricks-hosted language model.
- **Flask web interface:** Separate pages for drug labeling, CYP label history, and PDF search.
- **MCP integration:** Expose drug-information capabilities as tools callable by MCP-compatible clients and AI assistants.
- **Evaluation and observability:** Compare baseline LLM and baseline LLM given evidence with MCP-assisted responses, using an evaluation dataset, scoring metrics, and Phoenix traces.

## Architecture

```text
User / AI Assistant / Flask UI
              |
              v
       MCP Client / HTTP
              |
              v
        FastMCP Server
              |
       +------+--------------------+
       |      |                    |
       v      v                    v
    openFDA  DailyMed         FDA PDF Corpus
       |      |                    |
       +------+                    v
          |                Retrieval / RAG
          +-----------+------------+
                      |
                      v
             Databricks LLM
                      |
                      v
        Structured responses + evidence
```

**Main components:**

| Component | Purpose |
| --- | --- |
| FastMCP | Defines and exposes callable MCP tools |
| Flask | Provides a browser-based user interface |
| openFDA | Retrieves public FDA drug-labeling records |
| DailyMed | Supplies an additional source of drug-label information |
| FDA PDFs | Provide curated reference documents for retrieval |
| Databricks Model Serving | Hosts the language model used for summarization and answer generation |
| Phoenix | Supports tracing and evaluation of model/tool workflows |

## MCP Tools

### 1. `get_drug_label`

Accepts a drug name and retrieves available labeling information. Brand/generic normalization and DailyMed fallback are supported by the project's retrieval layer.

Example input:

```json
{"drug_name": "Oxycodone"}
```

The returned information depends on the source record and may include warnings, adverse reactions, interactions, and labeling metadata.

### 2. CYP label details : Drug interaction, Enzyme Metabolism 

Presents labeling information for four selected drugs:

- Oxycodone
- Hydrocodone
- Tramadol
- Buprenorphine

The interface displays the selected label's effective date, an LLM-generated summary where available, and a details view focused on **CYP2D6** and **CYP3A4** metabolism and drug-interaction evidence. This module is intended for examining label evidence, not predicting patient-specific interactions.

### 3. FDA PDF search / RAG

Searches an indexed collection of FDA PDF documents, retrieves relevant passages or tables, and uses the retrieved material to support an answer. Retrieval quality depends on document extraction, indexing, query wording, and evidence coverage.

> Tool names and argument schemas other than `get_drug_label` should be confirmed against the current server implementation before invoking them programmatically.

## Getting Started

### Prerequisites

- Python (use the version specified by the repository's `pyproject.toml`, if present)
- Git
- [`uv`](https://docs.astral.sh/uv/)
- Access to a Databricks workspace and a configured model-serving endpoint for LLM-backed features
- Network access to the public APIs used by the application

### 1. Clone the repository

```bash
git clone <REPOSITORY_URL>
cd <REPOSITORY_DIRECTORY>
```

### 2. Install dependencies

If the repository contains a `pyproject.toml` and `uv.lock`:

```bash
uv sync
```

If it instead uses `requirements.txt`:

```bash
uv venv
uv pip install -r requirements.txt
```

On Windows PowerShell, `uv` can be installed using the instructions on the [official uv installation page](https://docs.astral.sh/uv/getting-started/installation/).

### 3. Configure environment variables

Create a local `.env` file, if the application loads dotenv configuration, or set the variables in your shell or deployment environment:

```dotenv
DATABRICKS_HOST=https://<your-workspace-host>
DATABRICKS_TOKEN=<your-databricks-token>
DATABRICKS_MODEL_ENDPOINT=<your-serving-endpoint>
```

Use the model-serving endpoint configured for the deployment. Ensure the identity used by the application has permission to invoke it.

**Security:**  `.env`, access tokens, or other secrets are not shared in the files. Need to configure credentials through deployment platform's secret management and access controls.

### 4. Run the combined application locally

From the repository root, run the combined entry point used by this project:

```bash
uv run python -m src.example_server.combined_app
```

The application has previously been served on `127.0.0.1:8000`; verify the host and port in your current configuration. The MCP endpoint is typically:

```text
http://127.0.0.1:8000/mcp
```

**Note:** A `404 Not Found` response at `/` does not necessarily indicate a failed MCP server. Check the configured Flask routes and the `/mcp` endpoint. The exact module path and launch command should be verified against the current repository layout.

## Test the MCP Server

The test script named `test_fda_mcp.py` tests the mcp tool function calls. To test the other tools, use the names and argument schemas returned by `list_tools()`. It discovers tools and calls the drug-label lookup tools using the given inputs defined in the script.

To run the script `test_fda_mcp.py`, then run:

```bash
uv run python test_fda_mcp.py
```
## Deploy to Databricks Apps

The project is deployed as a Databricks App with the combined Flask/MCP application as its runtime.

1. Make the application source and dependency configuration available to Databricks Apps.
2. Configure the application start command to launch the combined server and listen on the host/port required by Databricks Apps.
4. Provide secrets through the supported Databricks configuration rather than hard-coding tokens.
5. Deploy the app, inspect startup logs, and test both the web UI and the `/mcp` endpoint.
6. Validate outbound connectivity to openFDA and DailyMed and access to any packaged PDF resources.

The exact `app.yaml` configuration and deployment commands depend on the current repository and workspace setup. Confirm these against the checked-in configuration before deploying.

## Evaluation

The evaluation workflow compares  **MCP-assisted responses** against **baseline LLM responses** and **baseline LLM responses based on provided evidences** on a curated set of drug-labeling questions. The project has used a evaluation dataset with questions from 4 categories, reference answers, scope adherence and associated evidences.

### Evaluation dimensions

| Metric | What it assesses |
| --- | --- |
| Correctness | Whether an answer matches the reference answer in substance |
| Evidence grounding | Whether the answer is supported by retrieved or supplied evidence |
| Scope adherence | Whether the response stays within the requested drug, formulation, and source scope |
| Uncertainty handling | Whether unsupported or missing information is handled appropriately |
| Approval-date boundary | Whether approval and label-effective dates are distinguished correctly |
| Latency | Response time |
| Tool usage and success | Whether expected MCP tools were invoked and completed successfully |
| Source match | Whether the response used the intended evidence source |

### Phoenix tracing

Phoenix traces help inspect model calls and, when instrumented, retrieval and tool activity. Traces can support investigation of latency, missing evidence, tool-selection failures, and unexpected answers. Tracing visibility depends on which components are instrumented.

### RAG retrieval audit

A separate retrieval audit can be used to inspect whether the PDF search layer retrieves relevant material for targeted queries. Its questions may differ from the main end-to-end evaluation dataset. **Retrieval audits and answer-quality evaluations measure different stages of the system and should be reported separately.**

No numerical performance claims are included here because results should be taken from the latest verified evaluation report.

## Known Limitations

- Public labeling sources can differ in coverage, formulation, naming conventions, and update timing.
- Brand and generic names do not always uniquely identify a formulation; immediate-release and extended-release labels must not be conflated.
- Effective labeling dates are not the same as original approval dates.
- PDF extraction can lose table structure or omit relevant passages, affecting RAG accuracy.
- An LLM-generated summary can be incomplete or inaccurate and must be checked against cited source evidence.
- A tool's availability does not guarantee that an agent will select it for every applicable question.
- The prototype does not establish clinical safety or completeness for patient-specific drug interactions.

## Suggested Future Improvements

- Strengthen formulation-aware label matching and latest-record selection.
- Improve PDF table extraction, indexing, and retrieval diagnostics.
- Display clearer source citations, document dates, and retrieval provenance.
- Expand regression tests for brand/generic matching and tool invocation.
- Automate evaluation runs and compare performance across revisions.
- Add deployment health checks and more comprehensive MCP/tool tracing.

## Data Sources and References

- [openFDA](https://open.fda.gov/apis/drug/label/)
- [DailyMed](https://dailymed.nlm.nih.gov/dailymed/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://gofastmcp.com/)
- [Databricks Apps documentation](https://docs.databricks.com/dev-tools/databricks-apps/)
- [Arize Phoenix](https://phoenix.arize.com/)

## Disclaimer

This repository is a research and hackathon prototype. Drug information should be verified against current official labeling. Outputs are not medical advice, and this project is not an official FDA service or endorsement.

## License

See the repository's `LICENSE` file, if provided. No license is implied by this README.
