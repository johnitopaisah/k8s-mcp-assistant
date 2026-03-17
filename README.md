# k8s-mcp-assistant

A read-only Kubernetes MCP server in Python for pod inspection and log retrieval.

## Step 1 scope

This first version supports:

- health check
- list pods in a namespace
- get pod logs

It is intentionally:
- read-only
- namespace-restricted
- easy to extend

---

## Project structure

```text
k8s-mcp-assistant/
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml
└── src/
    └── k8s_mcp_assistant/
        ├── __init__.py
        ├── config.py
        ├── server.py
        └── kubernetes/
            ├── __init__.py
            ├── client.py
            └── pods.py