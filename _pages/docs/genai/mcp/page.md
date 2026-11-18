---
layout: post
title: "MCP: connect LLMs to tools and data"
nav_order: 7
---

Your assistant needs to run SQL queries against your analytics database and open GitHub issues. Next month, it also needs your ticketing system. The real question this page answers: how do you give an LLM application access to many tools and data sources without rewriting the application for each one?

We reduce it to a smaller one first: how do you connect **one** assistant to **one** system? Without a shared standard, you write a custom integration. That works once. Now count. Three assistants (a desktop app, an IDE plugin, an internal agent) and four systems need 3 × 4 = 12 custom integrations, and each new system adds three more.

The **Model Context Protocol (MCP)** fixes that count. It is an open standard that defines how LLM-powered applications connect to external tools, data sources, and services. Each assistant implements the protocol once, and each system is wrapped once in an MCP server. The same three assistants and four systems now need 3 + 4 = 7 pieces, and a new system adds one server that every assistant can use. Think of it as a universal power socket: you build the plug once, and it fits every wall.

What MCP does not decide: which tools a model should use, or whether a call is safe. The host application still owns approval and access control.

This page introduces the vocabulary first. The architecture, server primitives, transports, and best practices sections are still being written.

**MCP turns many-to-many custom integrations into one client per application and one server per system.**

---

## On this page

- [Key concepts](#key-concepts)
- [Resources](#resources)
- [Architecture](#architecture)
  - [Host application](#host-application)
  - [Client–server connection](#clientserver-connection)
  - [Capability negotiation](#capability-negotiation)
- [Server primitives](#server-primitives)
  - [Tools (model-controlled)](#tools-model-controlled)
  - [Resources (application-controlled)](#resources-application-controlled)
  - [Prompts (user-controlled)](#prompts-user-controlled)
- [Transports](#transports)
  - [stdio](#stdio)
  - [Streamable HTTP](#streamable-http)
- [Best practices](#best-practices)

---

## Key concepts

- **Model Context Protocol (MCP)**: An open protocol that standardizes how LLM applications communicate with external servers that provide tools, data, and prompts. It decouples the host application from the capabilities it can access.
- **Host**: The LLM-powered application the user interacts with (for example Claude Desktop, an IDE assistant, or a custom agent). A host creates and manages one or more clients.
- **Client**: A protocol-level connector inside the host that maintains a 1:1 session with a single MCP server. Handles capability negotiation, message routing, and transport lifecycle.
- **Server**: A lightweight process that exposes capabilities (tools, resources, prompts) over MCP. Servers are the integration point: each one wraps a specific system or data source.
- **Tools**: Functions a server exposes for the model to call (for example "run a SQL query," "create a GitHub issue"). The model decides when and how to invoke them, subject to user approval.
- **Resources**: Structured data a server exposes for the application to read (for example file contents, database schemas, API responses). The application controls access; the model can reference the data but does not invoke resources directly.
- **Prompts**: Templated message sequences a server provides (for example "summarize this PR," "explain this error"). The user selects and parameterizes them; they are neither model-invoked nor application-invoked.
- **Transports**: The communication channel between client and server. MCP defines two standard transports: **stdio** (local processes communicating over stdin/stdout) and **Streamable HTTP** (remote servers communicating over HTTP with optional SSE streaming).
- **Sampling** (deprecated): A mechanism that lets servers request LLM completions through the client. The 2026-07-28 specification deprecates it, along with Roots and Logging. New servers should call LLM provider APIs directly; for logging, write to stderr (stdio) or use OpenTelemetry.
- **Specification version**: This page follows the MCP specification **2026-07-28**. That revision made the protocol stateless: it removed the `initialize` handshake and Streamable HTTP sessions.

---

## Resources

<details class="boz-resource">
  <summary><code>mcp-server.example.py</code></summary>

{% highlight python %}
{% include_relative mcp-server.example.py %}
{% endhighlight %}
</details>

---

## Architecture

<!-- TODO: explain the host → client → server layering, the stateless request flow since spec 2026-07-28 (every request carries protocol version + client capabilities in _meta; no initialize/shutdown handshake), and why the 1:1 client-server relationship matters -->

### Host application

<!-- TODO: role of the host, what it controls (user consent, tool-call approval, client lifecycle), examples of hosts -->

### Client–server connection

<!-- TODO: 1:1 relationship, no protocol-level sessions since 2026-07-28 (cross-call state uses server-minted handles passed as tool arguments), how a host manages multiple clients for multiple servers simultaneously -->

### Capability negotiation

<!-- TODO: server/discover RPC (versions, capabilities, identity), per-request protocol version + clientCapabilities in _meta, UnsupportedProtocolVersionError; note that the initialize handshake was removed in 2026-07-28 -->

---

## Server primitives

<!-- TODO: opening paragraph — servers expose three categories of capabilities, each with a different control model -->

### Tools (model-controlled)

<!-- TODO: what tools are, JSON Schema input definitions, how the model selects and invokes them, human-in-the-loop approval, examples -->

### Resources (application-controlled)

<!-- TODO: what resources are, URI-based access, static vs dynamic resources, resource templates, change notifications via subscriptions/listen (resources/subscribe removed in 2026-07-28), how they differ from tools -->

### Prompts (user-controlled)

<!-- TODO: what prompts are, how they surface in the UI (slash commands, quick actions), parameterization via arguments, examples -->

---

## Transports

<!-- TODO: opening paragraph — transports are the wire protocol between client and server, MCP defines two standard options -->

### stdio

<!-- TODO: when to use (local servers, CLI tools, IDE integrations), how it works (stdin/stdout JSON-RPC), advantages (simple, no network), limitations -->

### Streamable HTTP

<!-- TODO: when to use (remote servers, multi-user deployments), how it works (HTTP POST + optional SSE response streaming, Mcp-Method/Mcp-Name headers, subscriptions/listen instead of the GET stream), stateless design (no Mcp-Session-Id, no SSE resumability since 2026-07-28), legacy HTTP+SSE transport is deprecated, advantages over stdio for remote scenarios -->

---

## Best practices

<!-- TODO: security (least privilege, input validation, user consent for tool calls, no secrets in server responses), scoping (one server per domain/system, keep tool surfaces small), testing (mock transports, integration tests against real servers), observability (logging, tracing MCP calls) -->
