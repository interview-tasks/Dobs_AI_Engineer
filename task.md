# Build MCP Server

# **Goal**

Wrap the **DOBS Financial Document Analyzer API** behind a minimal [**Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro) (MCP)** server. Expose a few useful tools so AI clients (Claude Desktop, OpenAI Agents, Claude Code SDK etc.) can call the API through MCP. 

[Dobs.AI](http://Dobs.AI) API: https://api.dobs.ai/swagger

---

## **What you build (in 3 hours)**

- **MCP server** (Python or Node; stdio transport) with **4 tools total**:
    - **3 GET** endpoints of your choice.
    - **3 POST** (or PUT) endpoint of your choice.
- **Auth**: read key from env (e.g., DOBS_API_KEY) and send it per the API’s security scheme; make base URL configurable (DOBS_BASE_URL).

---

## **Demo expectations**

- **Claude Desktop** config snippet to launch your server (or equivalent client). Show list tools and one success call per tool.

---

---

## **Deliverables**

1. **Repo** with one-command run
2. **README (short)**
3. **DEMO (video)**