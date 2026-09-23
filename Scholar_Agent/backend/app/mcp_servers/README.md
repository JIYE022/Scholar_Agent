# Paper Search MCP Server

`paper_search_server.py` exposes the existing OpenAlex and arXiv providers as
standard MCP tools. It does not contain an LLM and does not write to the RAG
knowledge base.

## Tools

- `search_papers`: searches selected providers, normalizes records, removes
  duplicates, ranks the remaining papers, and returns structured metadata.
- `list_paper_search_providers`: returns the supported provider identifiers.

Both tools are read-only. Search results contain public metadata and abstracts,
not verified full-text evidence.

## Run with Docker and stdio

Build and start the API container first:

```powershell
docker compose up -d --build scholar_agent_api
```

Then an MCP host can start the server through the already-running container:

```powershell
docker compose exec -T scholar_agent_api python -m mcp_servers.paper_search_server
```

Do not run this command through `/app/start.sh`: startup messages written to
stdout would corrupt the MCP stdio protocol.

## Cline

Open Cline's MCP Servers settings, choose the configuration editor, and merge
the `mcpServers.scholar-paper-search` entry from
`backend/mcp-config.cline.example.json` into Cline's settings. The example uses
an absolute Windows Compose path for this workspace. Update that path if the
project is moved.

Keep `autoApprove` empty until the tool behavior has been reviewed. The server
marks both tools as read-only, but approval remains a client-side policy.

## Direct Python execution

When using a local Python environment instead of Docker, install the backend
requirements, change to the application directory, then run:

```powershell
Set-Location D:\path\to\backend\app
python -m mcp_servers.paper_search_server
```

The default transport is stdio. For local MCP clients there is no port to
configure.
