# Frappe AI

A central command for managing all AI operations inside the Frappe Framework. Frappe AI provides a unified, production-ready layer for AI Client management, OCR processes, and Retrieval-Augmented Generation (RAG), all wired into Frappe's background job infrastructure, configurable through doctypes and RQ scheduler.

![image](/assets/frappe_ai.png)

## The Problem

Every Frappe product that needs AI integration ends up re-implementing the same patterns: initializing provider SDKs, managing API keys across modules, queueing embedding jobs, polling long-running OCR operations, and wiring up vector search. Frappe AI solves this once, cleanly, and makes the full stack available to any app in the bench.

## Features

Here's a video to demonstration for a quick feature walkthrough: [Frappe AI](https://youtube.com/watch?v=-KoZMoWTHp4)

### AI Client

A configurable doctype that stores provider credentials and model parameters for famous providers including but not limited to Anthropic, OpenAI, and Google. Once created, any module in any installed Frappe app can import and use the initialized client without re-reading configuration or re-initializing SDKs, thus saving bandwidth and initialization time.

```python
from frappe_ai.api.chat import ask

answer = ask("<name-of-client-created>", "Summarize this contract.")
```

The client registry is initialized at boot and refreshed automatically whenever an AI Client document is saved. Parameters such as temperature, max tokens, top-p, and provider-specific options (extended thinking for Anthropic, reasoning effort for OpenAI, thinking level for Google) are all configurable from the Desk without touching code.

### AI Agent
Agents are versatile to use and however much you try, they're difficult to simplify. [AGENTS.md](./AGENTS.md) is a well-defined guide on using agents running in the background across your frappe pages, and accessible on your desk pages with a single click.

### Optical Character Recognition

Full integration with Google's Document AI supporting both synchronous and asynchronous processing modes. Working extra to support AWS Textract as well.

The synchronous mode processes a document inline inside an RQ job and writes the result back immediately. The asynchronous mode stages the file in Google Cloud Storage, starts a long-running batch operation on Google's servers, utilizes Google's storage buckets to save output, and a scheduled cron poller to detect completion and fetch the output. This mirrors how Google Document AI actually works at scale and avoids the UX problems caused by polling inside a request thread.

### RAG Pipeline

A complete Retrieval-Augmented Generation system built on FAISS, with support for multiple independent pipelines, incremental indexing, and both file-based and DocType-based data sources. This is also bound to support truly production-ready pipelines using Qdrant. I'm still exploring it for multi-tenant systems and optimal response times.

**Multiple independent pipelines:** Each RAG Data Source has an `index_name` field that maps to a named FAISS index on disk (`hr.index`, `finance.index`, `default.index`, etc.). You can run completely separate assistants, one for HR policy documents, one for finance contracts, one for product manuals, each with its own vector store, all managed from a single RAG Settings configuration.

**Versatile document support:** A data source can ingest PDF files, plain text files, or live Frappe DocType records. For DocType sources, you specify which doctype to index, optional filters to narrow the record set, and which fields to concatenate for embedding. Employee records, Items, Projects, or any custom doctype can be made searchable through the same RAG pipeline.

**Incremental indexing:** The indexing engine computes a SHA-256 hash of every file before processing it. If the hash matches the stored value from the previous run, the document is skipped entirely. No re-chunking, no embedding API calls, no index writes. Only genuinely new or changed files are processed. For updated documents, the old chunks are marked inactive in metadata before new chunks are appended, so the index never needs a full rebuild.

**Automatic indexing on save:** When a RAG Document is saved with a file attached, the system automatically queues an indexing job in the background. There is no manual trigger required. The document status transitions from `Pending` to `Indexing` to `Indexed` (or `Failed` with a full traceback) and is visible live on the document form.

**Storage layout:** Three files are written per index name under `private/files/rag/`:

```
{index_name}.index    FAISS flat-L2 vector index
{index_name}.meta     JSON list of chunk metadata
{index_name}.npy      float32 matrix of stored embeddings
```

The `.npy` file stores the raw embedding vectors alongside the FAISS index. This means the weekly compaction job, which removes chunks from deleted or updated documents, can rebuild the FAISS index entirely from stored vectors without making a single embedding API call.

**Embedding providers:** Google (`text-embedding-004`), OpenAI (`text-embedding-3-small`, `text-embedding-3-large`), are all supported. The embedding provider is configured independently from the LLM provider in RAG Settings, so you can use Google embeddings with an Anthropic LLM, or any other combination. This is a strong hint towards non-dependendable AI suite.

## Doctypes

| Doctype | Type | Purpose |
|---|---|---|
| AI Client | Standard | Stores provider, model, API key, and generation parameters |
| Document AI Settings | Singleton | Google Document AI project, location, processors, and GCS bucket |
| OCR Process | Standard | Tracks a single OCR job from queued to completed |
| RAG Settings | Singleton | Embedding provider, LLM client, chunking parameters, Top-K |
| RAG Data Source | Standard | Defines a data source and maps it to a named FAISS index |
| RAG Document | Standard | A single file or record to be indexed; triggers indexing on save |
| RAG Index Job | Standard | Background job record with status, progress, and logs |
| RAG Query Log | Standard | Persists every question, answer, latency, and user for auditing |

## Getting Started

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO
bench install-app frappe_ai
bench setup requirements --python
bench migrate
```

### Step 1: Create an AI Client

Open **AI Client** on the Desk and create a record. Choose your provider (Anthropic, OpenAI, or Google), paste your API key, and select a model. Save. The client is now available globally across all modules, in your code and on desk.

### Step 2: Configure RAG Settings

Open **RAG Settings**. Set:

- **AI Client**: the record you just created
- **Embedding Provider** and **Embedding Model**: for example `Google` and `text-embedding-004`
- **Chunk Size**: `1000`, **Chunk Overlap**: `100`
- **Top-K Results**: `5`

Optionally set a **System Prompt** to customize how the LLM frames its answers.

### Step 3: Create a RAG Data Source

Open **RAG Data Source** and create a record. Give it a title, set **Source Type** and **Index Name**`. Enable the record.

To set up a separate pipeline for a different domain, create another RAG Data Source with a different **Index Name** (for example `hr` or `finance`).

### Step 4: Add Documents

Open **RAG Document**, create a record, link it to the data source you just created, and attach a file you'd like to process. Save the document. The system will immediately queue an indexing job in the background. You can watch the status update on the form, it will move through `Pending`, `Indexing`, and settle on `Indexed` or `Failed`.

To verify the job, open **RAG Index Job** and find the most recent entry for your data source.

### Step 5: Ask Questions from the Desk

Open your RAG Data Source record. In the top-right button group labelled **RAG**, click **Ask**. Type a question in the dialog and click **Ask**. The answer will appear inline in the same dialog, generated from the content of your indexed documents.

You can also trigger a full re-index of all pending documents at any time using the **Index Now** button in the same button group.

### Step 6: Query from Code

```python
from frappe_ai.rag.query import query

result = query(
    question="What are the payment terms in the master agreement?",
    data_source_name="Finance Documents",
)
print(result["answer"])
```

### Auditing Queries

Every question asked through the system is recorded in **RAG Query Log** with the question text, response, latency in milliseconds, the user who asked, and the data source that was queried. Open the list view and filter by data source or user to review usage.

## Background Jobs and Scheduling

Indexing jobs run on the `long` queue with a two-hour timeout, so large document sets do not block other workers. The weekly compaction job (`0 3 * * 0`) removes stale chunks from deleted or updated documents by rebuilding the FAISS index from stored vectors, no API calls are made during compaction.

For OCR, an async poller runs every two minutes (`*/2 * * * *`) to check Google for completed batch operations.

## Contributing
Send clean code. I'd be happy to grill your PRs. This app uses `pre-commit` for code formatting and linting. Install it and enable it for this repository:

```bash
cd apps/frappe_ai
pre-commit install
```

Pre-commit runs ruff, eslint, prettier, and pyupgrade on every commit.

## License

MIT
