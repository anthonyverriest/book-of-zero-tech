---
layout: post
title: "RAG Indexing: chunking, embedding, and storage"
nav_order: 8
---

A 50-page PDF goes into your RAG system. The model hallucinates, misses key details, or mixes facts from unrelated sections. The root cause is often bad chunking. The real question this page answers: how do you turn a pile of messy documents into an index from which the retrieval stage can find the right passage, and the LLM can answer from it?

We start with a smaller question: how do you make **one** document findable? You clean it, cut it into pieces, turn each piece into a vector, and store the vectors with labels. Each of those steps sets a ceiling on everything after it. Chunking in particular is not preprocessing; it is architecture. A chunk is your retrieval unit, your context boundary, and your quality ceiling. Get it wrong and no amount of prompt engineering or model scaling will save you.

Our example runs through the whole guide. Acme builds an internal policy assistant over a corpus that holds an HR handbook (PDF), a HIPAA compliance guide (PDF), wiki pages scraped from the intranet, scanned contracts, some Python code, and a few public reports. In eight parts, we clean those documents, chunk them, embed them, label them, store them, measure the result, build the pipeline, and plan the costs.

---

## On this page

- [Key concepts](#key-concepts)
- [Part 1: Clean text before you cut it](#part-1-clean-text-before-you-cut-it)
  - [Cleaning PDF documents](#cleaning-pdf-documents)
  - [Cleaning web scrapes](#cleaning-web-scrapes)
  - [Cleaning OCR output](#cleaning-ocr-output)
  - [Preprocessing checklist](#preprocessing-checklist)
- [Part 2: A chunk is the unit retrieval can find](#part-2-a-chunk-is-the-unit-retrieval-can-find)
  - [Character splitting](#character-splitting)
  - [Recursive character splitting](#recursive-character-splitting)
  - [Document-specific splitting](#document-specific-splitting)
  - [Semantic chunking](#semantic-chunking)
  - [Agentic splitting](#agentic-splitting)
  - [Alternative representations](#alternative-representations)
  - [Late chunking](#late-chunking)
  - [Knowledge graph extraction (GraphRAG)](#knowledge-graph-extraction-graphrag)
  - [Visual-native indexing (ColPali)](#visual-native-indexing-colpali)
- [Part 3: An embedding turns meaning into distance](#part-3-an-embedding-turns-meaning-into-distance)
  - [Model selection](#model-selection)
  - [Fine-tuning embeddings](#fine-tuning-embeddings)
  - [Trade-offs](#trade-offs)
- [Part 4: Metadata lets retrieval find the right text from the right source](#part-4-metadata-lets-retrieval-find-the-right-text-from-the-right-source)
  - [What metadata to track](#what-metadata-to-track)
  - [Metadata structure](#metadata-structure)
  - [Contextual chunk headers (CCH)](#contextual-chunk-headers-cch)
- [Part 5: A vector database trades a little recall for a lot of speed](#part-5-a-vector-database-trades-a-little-recall-for-a-lot-of-speed)
  - [In-memory vs persistent](#in-memory-vs-persistent)
  - [Index types](#index-types)
  - [Quantization](#quantization)
  - [Production patterns](#production-patterns)
- [Part 6: Measure chunking before you change it](#part-6-measure-chunking-before-you-change-it)
  - [Intrinsic metrics](#intrinsic-metrics-chunk-quality)
  - [Extrinsic metrics](#extrinsic-metrics-retrieval-quality)
  - [Evaluation workflow](#evaluation-workflow)
- [Part 7: A production index updates itself without a rebuild](#part-7-a-production-index-updates-itself-without-a-rebuild)
  - [Prototype pipeline](#prototype-pipeline)
  - [Production pipeline](#production-pipeline)
  - [Incremental updates](#incremental-updates)
- [Part 8: Indexing has costs you can estimate in advance](#part-8-indexing-has-costs-you-can-estimate-in-advance)
  - [Indexing costs](#indexing-costs)
  - [Storage costs](#storage-costs)
  - [Query costs](#query-costs)
  - [Total cost of ownership](#total-cost-of-ownership)
  - [Comparison matrix](#comparison-matrix)
  - [Vendor landscape](#vendor-landscape)
- [Common pitfalls](#common-pitfalls)
- [Best practices](#best-practices)
- [Recap](#recap)
- [Exercise](#exercise)

---

## Key concepts

- **Chunk**: The atomic retrieval unit in RAG. A contiguous text segment that must be meaningful in isolation.
- **Chunk size**: Target length in tokens or characters. Typical range: 256-800 tokens. Smaller chunks increase precision at the cost of context.
- **Chunk overlap**: Tokens shared between consecutive chunks to prevent information loss at boundaries. Typical: 10-20% of chunk size.
- **Embedding**: A dense vector encoding semantic meaning. Similar meanings cluster together in high-dimensional space.
- **Vector database**: Storage optimized for approximate nearest neighbor (ANN) search over embeddings. Linear search doesn't scale past 10K chunks.
- **Semantic chunking**: Splitting based on meaning via embedding similarity rather than syntax. 10-100x slower than recursive splitting but higher quality for heterogeneous documents.

---

## Part 1: Clean text before you cut it

Acme's HR handbook has "CONFIDENTIAL" and "Page 12 of 87" on every page. Leave them in, and every chunk carries them. Real-world documents are messy. PDFs often include headers, footers, and watermarks. OCR can introduce garbled text. Web scrapes often include nav menus and ads.

Why does that matter for retrieval? An embedding summarizes everything in a chunk. Repeated wrapper text pulls every chunk's embedding toward the same point, which makes chunks harder to tell apart. And a word that appears everywhere stops being useful for matching: if every page says "CONFIDENTIAL", that term becomes much less useful for retrieval. So remove recurring boilerplate before chunking, and embeddings focus on the content.

### Cleaning PDF documents

PDFs are common offenders: text extraction tools often preserve layout artifacts that should not be embedded.

#### Common PDF artifacts to remove

**Headers and footers**: page numbers ("Page 1", "1 of 87"), document titles, watermarks ("DRAFT", "CONFIDENTIAL"), dates.

**Layout artifacts**: horizontal separators, table borders, multi-column mixing.

**OCR errors** (scanned PDFs): character substitution, missing/extra spaces, phantom characters from image noise.

#### Cleaning pipeline

```python
import re

from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

PAGE_NUMBER_PATTERN = r'\b[Pp]age \d+\b'
PAGE_RANGE_PATTERN = r'\b\d+ of \d+\b'
CONFIDENTIAL_PATTERN = r'\bCONFIDENTIAL\b'
COPYRIGHT_PATTERN = r'Copyright © \d{4}.*'
SEPARATOR_PATTERN = r'[-─=]{3,}'
WHITESPACE_PATTERN = r'[ \t]+'
BLANK_LINES_PATTERN = r'\n{3,}'


def clean_pdf_text(pdf_path: str) -> str:
    """Extract text from a PDF and strip common layout artifacts."""
    assert pdf_path, "pdf_path must be a non-empty string"
    config_parser = ConfigParser({"output_format": "markdown"})
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        renderer=config_parser.get_renderer(),
    )
    rendered = converter(pdf_path)
    text = rendered.markdown

    text = re.sub(PAGE_NUMBER_PATTERN, '', text)
    text = re.sub(PAGE_RANGE_PATTERN, '', text)
    text = re.sub(CONFIDENTIAL_PATTERN, '', text, flags=re.IGNORECASE)
    text = re.sub(COPYRIGHT_PATTERN, '', text)
    text = re.sub(SEPARATOR_PATTERN, '', text)
    text = re.sub(WHITESPACE_PATTERN, ' ', text)
    text = re.sub(BLANK_LINES_PATTERN, '\n\n', text)
    return text.strip()
```

For production systems with heterogeneous PDFs, use ML-based document parsing:

- **Docling** (IBM): ML-based document understanding, handles complex layouts
- **Azure Document Intelligence**: Cloud API, best for forms/tables/receipts
- **Google Document AI**: Cloud API, strong on tables/forms, supports 200+ languages
- **AWS Textract**: Similar to Azure, good for scanned documents

```python
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

client = DocumentIntelligenceClient(endpoint="<endpoint>", credential=AzureKeyCredential("<key>"))

with open("financial_report.pdf", "rb") as f:
    poller = client.begin_analyze_document(
        "prebuilt-layout",
        body=f,
        content_type="application/pdf",
        output_content_format="markdown",  # default is plain text
    )

result = poller.result()
markdown = result.content
```

**Strip page furniture with patterns for simple PDFs, and switch to ML-based parsing when layouts get complex.**

### Cleaning web scrapes

Acme's wiki pages come with a navigation bar, a cookie banner, and a footer on every page. Web pages have navigation, ads, and boilerplate that pollute chunks. Remove nav elements, cookie banners, footers, and ads before chunking.

```python
from trafilatura import fetch_url, extract

def clean_web_page(url: str) -> str:
    """Extract main content from a web page, stripping boilerplate."""
    downloaded = fetch_url(url)
    return extract(downloaded, include_comments=False, include_tables=True)
```

**Manual alternative** using BeautifulSoup:

```python
import re

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT_SECONDS = 10

def clean_web_page_manual(url: str) -> str:
    """Extract main content from a web page using BeautifulSoup."""
    assert url, "url must be a non-empty string"
    soup = BeautifulSoup(requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS).content, 'html.parser')
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for element in soup.find_all(['nav', 'header', 'footer', 'aside']):
        element.decompose()
    for element in soup.find_all(class_=re.compile(r'ad|banner|cookie|popup|subscribe', re.I)):
        element.decompose()
    main = soup.find('main') or soup.find('article') or soup.find('body')
    text = main.get_text(separator='\n', strip=True)
    return '\n\n'.join(line for line in text.split('\n') if line.strip())
```

**Keep only the main content of a web page; navigation and banners are noise to an embedding.**

### Cleaning OCR output

The scanned contracts go through OCR. OCR quality varies widely. Common errors include character substitution (l/1/I, O/0, rn/m), missing spaces, and extra spaces.

These heuristics are corpus-specific examples, not universal defaults. Validate them on sample documents before applying them broadly.

```python
import re

def clean_ocr_text(text: str) -> str:
    """Normalize whitespace and rejoin hyphenated words in OCR output."""
    text = re.sub(r'[ \t]{2,}', ' ', text)         # collapse multiple spaces
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)    # rejoin hyphenated line breaks
    text = re.sub(r'\n{3,}', '\n\n', text)           # collapse blank lines
    return text.strip()
```

Regex-based character fixes (l/1/I, O/0, rn/m) are tempting but fragile. Replace every "rn" with "m", and "turn" becomes "tum". If OCR quality is poor, prefer re-scanning at higher resolution (300+ DPI), preprocessing images (deskew, denoise, binarize), or using stronger OCR systems such as Azure Computer Vision, AWS Textract, or surya.

**Fix whitespace in OCR output with patterns, and fix character errors at the source with better scans or better OCR.**

### Preprocessing checklist

**Quality checks**: Sample documents from each format and source type, manually review cleaned text. Verify important content is not removed (tables, equations, technical terms). Generate test queries from sample chunks and confirm cleaned content can still answer them.

**Deduplication**: Remove exact and near-duplicate content before chunking. Repeated text (boilerplate paragraphs, copied sections across documents) inflates index size and skews retrieval toward redundant results. Use MinHash or exact-match hashing at the document or paragraph level.

**Automated validation**: Spot-check that cleaned text retains the bulk of original length. If cleaning removes a large fraction, investigate what is being stripped. Most frequent terms in cleaned output should be domain-relevant, not artifacts like "Page" or "Confidential". Embed sample chunks and verify similar chunks cluster together.

**Monitoring in production**: Track cleaning metrics (% artifacts removed, text length before/after). Set alert thresholds based on your corpus baseline, and flag documents where text retention drops well below the norm.

**Over-cleaning vs under-cleaning**: Over-cleaning removes important content (dates, dollar amounts). Under-cleaning wastes embedding capacity on boilerplate. Heuristic-based cleaning (regex) is fast but brittle; ML-based parsing (marker, docling) is slower but handles edge cases. Invest in ML-based parsing for messy documents (scanned PDFs, web scrapes, OCR).

What cleaning does not tell you: whether the chunks will be good. Clean text is necessary for a good index, not sufficient.

**Clean until boilerplate is gone and content is intact, then verify both with samples and length checks.**

---

## Part 2: A chunk is the unit retrieval can find

Clean text is still one long string per document. Retrieval cannot return "page 34 of the handbook, roughly"; it returns pieces. So we cut each document into chunks, and each strategy below fixes a limitation of the one before it.

Start with recursive character splitting for most use cases. Move to document-specific or semantic approaches when you've measured that chunking is the bottleneck.

### Character splitting

The simplest cut: split text every N characters. Baseline for ablation studies only; never use in production.

```python
def character_split(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into fixed-size character chunks with overlap."""
    assert chunk_size > overlap >= 0, "chunk_size must exceed overlap, and overlap must be non-negative"
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks
```

It splits mid-sentence, mid-word, mid-thought. You get `"...the capital of France is Par"` and `"ris. The Eiffel Tower..."`. The retrieval system can't match either chunk to a query about France's capital.

Notice the overlap. Each chunk starts `chunk_size - overlap` characters after the previous one: with 1,000 and 200, every 800 characters. A 10,000-character document gives about 10,000 / 800 ≈ 13 chunks instead of 10. That is about 25% more chunks to embed and store, which makes sense, because 200 / 800 = 25%. Overlap buys safety at the boundaries, and you pay for it in index size.

**Fixed-size cuts ignore meaning; keep them only as the baseline you compare against.**

### Recursive character splitting

The fix for mid-sentence cuts: prefer natural boundaries. Split on paragraph breaks, then sentences, then words, respecting a maximum chunk size. This is your default.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", " ", ""],
)
chunks = splitter.split_text(document_text)
```

It tries paragraph boundaries first, falls back to newlines, then spaces, then characters. Chunks respect natural boundaries most of the time. The overlap ensures context spanning boundaries is captured.

Using `from_tiktoken_encoder` measures chunk size in **tokens**, not characters. That is critical because a 1000-character chunk might be 250 or 400 tokens depending on content, and models count tokens.

**Parameter tuning**: 256 tokens for high precision (FAQ, product specs), 500 tokens general use, 1000+ for long-context models. Overlap 10-20% of chunk size.

**Recursive splitting at 500 tokens with 10-20% overlap is the default to beat.**

### Document-specific splitting

Recursive splitting knows about paragraphs, not about documents. Acme's wiki has headings, its repository has functions, its reports have tables. When explicit hierarchy exists, use document structure (markdown headers, code syntax, PDF layout) to guide splitting.

#### Markdown documents

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)
md_chunks = markdown_splitter.split_text(markdown_document)
```

Headers signal topic boundaries. Metadata enables filtered search: "find authentication methods in the API section."

#### Code files

```python
code_splitter = RecursiveCharacterTextSplitter.from_language(
    language="python", chunk_size=1000, chunk_overlap=200,
)
code_chunks = code_splitter.split_text(python_code)
```

It prioritizes splitting at class definitions, then function definitions, then blank lines. Splitting mid-function produces unreadable chunks.

#### PDFs and multi-modal documents

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("document.pdf")
markdown = result.document.export_to_markdown()
```

It keeps tables intact and preserves section hierarchy. Use for scientific papers, reports, presentations.

**When a document has structure, cut along it: headers for markdown, functions for code, layout for PDFs.**

### Semantic chunking

Some documents have no reliable structure. A meeting transcript or a scraped page changes topic without a heading. The fix is to split when the topic changes using embedding similarity, not at fixed intervals.

```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

semantic_splitter = SemanticChunker(
    embeddings=OpenAIEmbeddings(),
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=95,  # split where the distance exceeds the 95th percentile
)
semantic_chunks = semantic_splitter.split_text(document_text)
```

> `langchain-experimental` is no longer actively maintained. Pin its version, or port the ~100-line algorithm described below into your own code.

The algorithm splits text into sentences, then combines each sentence with its neighbors (a buffer window of 1-2 sentences on each side) before embedding. This ensures each embedding captures local context, not an isolated sentence. It then computes cosine similarities between consecutive combined-sentence embeddings and splits where similarity drops below the threshold (a topic boundary). Works well for heterogeneous documents where structure doesn't match semantics (transcripts, web scrapes, unformatted reports).

**Cost**: 10-100x slower than recursive splitting. For 10K words (~500 sentences), that's ~500 sentence embeddings (batched). Run an ablation: if semantic chunking improves Hit Rate@5 by <5% over recursive splitting, it's not worth it.

**Split by meaning only where structure fails, and only if it measurably beats recursive splitting.**

### Agentic splitting

The next step up is to ask an LLM where the boundaries are. Experimental and expensive ($0.01-0.10 per document, 5-10s latency, non-deterministic).

{% raw %}
```python
from langchain_core.prompts import PromptTemplate

prompt = PromptTemplate.from_template("""
Split this text into coherent chunks of 300-800 tokens at topic boundaries.
Each chunk must be self-contained. Output JSON: [{{"chunk_text": "...", "summary": "..."}}]

Document: {document}
""")
response = llm.invoke(prompt.format(document=document_text))
```
{% endraw %}

Reserve for high-stakes applications (legal, medical) where chunking quality is critical and cost/latency don't matter. **Practical alternative**: use agentic chunking to label 100 documents, then train a lightweight boundary-detection model.

**LLM-chosen boundaries are a last resort, best used to label training data for a cheaper splitter.**

### Alternative representations

So far, every chunk is a literal slice of the source. That breaks down for content that embeds poorly in its original form, like a table of benefit tiers in the HR handbook. Instead of embedding raw chunks, create derivative representations that improve retrieval.

**Table summaries**: Tables embed poorly as raw text. Summarize them with an LLM, embed the summary, and store the original table for the generation step.

```python
summary = llm.invoke(f"Summarize this table in 2-3 sentences:\n{table_html}")
# Embed and index the summary
# Store the original table in metadata for the LLM to use at generation time
```

**Image descriptions**: Extract images from PDFs and generate text descriptions with a vision model. Embed the description for retrieval, pass the original image or description to the LLM.

**Document summaries**: Generate a summary of each full document and index it as a separate chunk. Queries about "the main argument" or "overall conclusion" match the summary instead of a random paragraph.

**Parent-child chunks**: Embed small chunks (200-400 tokens) for precise retrieval, but store a reference to their parent section (1000-2000 tokens). At retrieval time, return the parent instead of the child so the LLM has full context. Store the parent ID in chunk metadata.

```python
parent_chunks = splitter.split_text(document_text)  # 1500 tokens each
for i, parent in enumerate(parent_chunks):
    children = child_splitter.split_text(parent)  # 300 tokens each
    for child in children:
        index_chunk(child, metadata={"parent_id": i, "parent_text": parent})
# At retrieval: match on child embedding, return parent_text to LLM
```

With 1,500-token parents and 300-token children, each parent holds about five children. A query matches one precise 300-token child, and the LLM reads the 1,500-token section around it. Precision for search, context for generation.

**Your retrieval unit does not have to be a literal slice of the document; index whatever retrieves best.**

### Late chunking

Standard RAG embeds chunks independently, discarding document context. A chunk containing "it committed to net zero" has no idea "it" refers to the company named two sentences earlier. Late chunking solves this without adding LLM calls.

**How it works**: instead of chunking first and embedding each chunk in isolation, pass the entire document through the embedding model's transformer layers first. Every token now carries the full document's contextual signal (via attention). Only then apply chunk boundaries and mean-pool each group of token vectors into a single chunk embedding.

An analogy: standard chunking hands each reader one page torn from a book. Late chunking lets every reader skim the whole book first, then asks each one to summarize their page.

```python
from transformers import AutoModel, AutoTokenizer
import torch

model_name = "jinaai/jina-embeddings-v3"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(model_name, trust_remote_code=True)

document = "Acme Corp was founded in 1998. It specializes in industrial robotics..."
chunk_boundaries = [0, 512, 1024, 1536]  # token offsets

inputs = tokenizer(document, return_tensors="pt", truncation=True, max_length=8192)
with torch.no_grad():
    token_embeddings = model(**inputs).last_hidden_state.squeeze(0)  # [seq_len, dim]

chunk_embeddings = []
for start, end in zip(chunk_boundaries, chunk_boundaries[1:] + [token_embeddings.size(0)]):
    chunk_embeddings.append(token_embeddings[start:end].mean(dim=0))
```

**Comparison with CCH**: contextual chunk headers (CCH) add explicit context by prepending "Document: Acme Corp Report / Section: Financials" to each chunk before embedding, at the cost of LLM API calls to generate those headers. Late chunking adds implicit context by preserving cross-token attention, at zero LLM cost, using only the embedding model already in your pipeline.

Both methods address the same root problem (context loss at chunk boundaries) and can be combined: embed with late chunking, then apply CCH-style prefixes for domain framing.

**Constraints**: requires a long-context embedding model. `jina-embeddings-v3` processes up to 8 192 tokens (~5 000 words). A 50-page PDF won't fit in one pass, so split into sections first and apply late chunking per section. For very long documents, standard chunking with CCH remains practical.

**When to use**: documents with frequent anaphora or cross-sentence dependencies (transcripts, narrative reports, legal filings). **Skip when** your documents are already self-contained paragraphs (FAQ, product descriptions) or exceed your model's context window.

**Embed the whole document before cutting it, so each chunk remembers what "it" refers to.**

### Knowledge graph extraction (GraphRAG)

Every strategy so far assumes the answer lives in one place. Here is where that expectation fails. "What are the common risks across all acquisition targets?" has no single matching chunk. Standard dense retrieval finds chunks that are semantically similar to a query. It fails when the answer requires connecting facts across many documents. Knowledge graph indexing builds an explicit entity-relationship layer that enables these structural queries.

**How indexing works**: for each text chunk, an LLM extracts named entities and the relationships between them. These become nodes and edges in a knowledge graph. Microsoft's GraphRAG then runs community detection (Leiden algorithm) over the graph and generates LLM summaries of each community. These summaries are stored as additional retrievable chunks.

```text
Indexing pipeline:
  Documents → Chunks → Entity extraction (LLM) → Relationship extraction (LLM)
           → Community detection → Community summaries (LLM) → Graph + vector store
```

This indexing is expensive: multiple LLM calls per chunk, plus summary generation. Expect $0.05–$2.00 per document depending on length and LLM price. For Acme's 2,000 documents, that is roughly $100 to $4,000 per full build. Build the graph offline and treat it as a pre-computed artifact, not a real-time step.

**FastGraphRAG variant**: replaces LLM-based entity extraction with NLP libraries (spaCy, NLTK) to extract noun phrases. Cheaper and faster, but misses implicit relationships and domain-specific entities that require reasoning.

**When to use**: corpora where the answer requires traversing relationships (org charts, supply chains, investigative research). Standard vector RAG outperforms GraphRAG on factoid and lookup queries. For retrieval-side details (local vs global search, community summary retrieval, hybrid graph+dense queries), see [RAG Retrieval: GraphRAG]({{ site.baseurl }}/docs/genai/rag/retrieval/page/#graphrag-knowledge-graph-retrieval).

**Cost warning**: since GraphRAG 1.0, `graphrag update` processes only new documents and merges them into the existing index, but community detection and community summaries are still recomputed over the whole graph. Only adopt GraphRAG if your use case requires structural reasoning and you have budget for regular re-summarization.

**Build a knowledge graph only when answers live across documents, and budget for rebuilding its summaries.**

### Visual-native indexing (ColPali)

The public reports in Acme's corpus are full of charts. Standard PDF indexing relies on OCR → layout parsing → text chunking → embedding. This pipeline loses information: charts become broken text, tables become misaligned rows, visual diagrams are dropped entirely. ColPali eliminates the pipeline: it embeds raw page images directly.

**How it works**: a vision-language model (PaliGemma-3B, or QWen2-VL for ColQwen) processes each page as an image and produces patch-level token embeddings, typically 256–1 024 patch vectors per page. At query time, a query text is encoded into token vectors and matched via late interaction (ColBERT-style max-similarity scoring across patches). No OCR, no chunking, no text extraction.

```python
from colpali_engine.models import ColPali, ColPaliProcessor
import torch
from pdf2image import convert_from_path

model = ColPali.from_pretrained("vidore/colpali-v1.2", torch_dtype=torch.bfloat16).eval()
processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.2")

pages = convert_from_path("document.pdf")
page_embeddings = []
for page_image in pages:
    inputs = processor.process_images([page_image])
    with torch.no_grad():
        page_embeddings.append(model(**inputs))  # [num_patches, dim] per page
```

**When ColPali outperforms text pipelines**: visually-rich documents where figures, charts, infographics, and layout carry meaning that OCR cannot preserve. Annual reports, scientific papers with dense plots, slide decks.

**Constraints**:
- Multi-vector storage: each page produces hundreds of vectors instead of one, significantly increasing index size and query cost. A 50-page report at 1,024 patches per page is about 51,000 vectors, where text chunking might produce 100. Vector databases need multi-vector support (Qdrant, Vespa).
- GPU required at both index and query time; ColPali is not CPU-friendly.
- Pure-text PDFs see no retrieval benefit over text-based pipelines and incur unnecessary storage overhead.

**When to skip**: text-heavy documents (policy manuals, contracts, documentation) where OCR + recursive splitting already achieves >85% Hit Rate@5.

**Index page images directly when the meaning is in the visuals, and pay for it in vectors and GPUs.**

**So far:** we clean documents so embeddings see content, not furniture. We cut them recursively by default, by structure when it exists, by meaning when it does not, and into derivative forms when the raw text embeds poorly. Late chunking keeps document context, GraphRAG connects facts across documents, and ColPali keeps what lives in images.

---

## Part 3: An embedding turns meaning into distance

A chunk is still text, and a database cannot compare meanings of text directly. An embedding model turns each chunk into a vector, so that "how similar are these two passages?" becomes "how close are these two points?".

Work it in two dimensions. Say the model maps "How many vacation days do I get?" to (1, 0), the handbook's leave policy chunk to (0.8, 0.6), and a chunk about server backups to (0, 1). Cosine similarity is the dot product divided by the lengths, and all three vectors have length 1 here. Query vs leave policy: 1 × 0.8 + 0 × 0.6 = 0.8. Query vs backups: 1 × 0 + 0 × 1 = 0. The leave policy wins, which makes sense, because it points in nearly the same direction as the question. Real models do the same thing with hundreds or thousands of dimensions.

What an embedding does not tell you: whether a passage answers the question. It measures similarity of meaning. A chunk that restates the question can score higher than the chunk with the answer.

### Model selection

Choose based on these criteria:

- **Benchmark scores**: Check the [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard) for your task type (retrieval, STS, classification). A 2-point MTEB difference typically translates to 5-10% improvement in Hit Rate@5.
- **Dimensions**: Higher dimensions (1024-3072) capture more nuance but cost more storage and slower search. Many modern models support **Matryoshka representations**, letting you truncate embeddings to fewer dimensions with graceful quality degradation. That is useful for trading off storage against quality without retraining.
- **Hosting model**: API-based (OpenAI, Cohere, Voyage) for fast iteration. Self-hosted open-source (sentence-transformers, HuggingFace) for cost control and data privacy.
- **Language support**: Multilingual models exist but typically underperform monolingual ones. Match the model to your corpus language(s).
- **Instruction-tuned models**: Some models accept a task prefix (e.g., "Represent this document for retrieval:") that improves quality for specific use cases. Use these when your retrieval task is well-defined.

**Pick the embedding model on retrieval benchmarks for your task, then on dimensions, hosting, and language.**

### Fine-tuning embeddings

A general model may not know that Acme's "PTO bank" and "leave balance" mean the same thing. Fine-tune when your domain diverges from training data (medical jargon, legal language, internal terminology) and you have 1000+ labeled query-document pairs.

```python
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
    losses,
)

model = SentenceTransformer("BAAI/bge-large-en-v1.5")
train_dataset = Dataset.from_dict({
    "anchor": ["what is HIPAA?"],
    "positive": ["HIPAA is the Health Insurance Portability..."],
    "negative": ["The capital of France..."],
})
args = SentenceTransformerTrainingArguments(
    output_dir="models/bge-finetuned",
    num_train_epochs=3,
    per_device_train_batch_size=16,
)
trainer = SentenceTransformerTrainer(
    model=model,
    args=args,
    train_dataset=train_dataset,
    loss=losses.MultipleNegativesRankingLoss(model),  # uses in-batch negatives too
)
trainer.train()
```

Skip if pre-trained models already hit your quality target or your domain is covered by general web text.

**Fine-tune embeddings only when your vocabulary is unusual and you have at least a thousand labeled pairs.**

### Trade-offs

- **Dimensions**: Each float32 number takes 4 bytes, so a 768-dim vector takes 768 × 4 = 3,072 bytes, about 3KB per chunk. For 1M chunks: 3GB. 3072 dims = 12GB. Higher dimensions capture more nuance but cost more storage and slower search. If available, use Matryoshka truncation to find the sweet spot.
- **Speed**: Batch embedding (10-100 chunks per call) amortizes API overhead. For large corpora, estimate total embedding time before committing to a model.
- **Quality**: Better embeddings improve retrieval, but if your LLM is bad at using context, fix the prompt first.

**Every extra dimension costs 4 bytes per chunk, so multiply by your chunk count before you choose.**

---

## Part 4: Metadata lets retrieval find the right text from the right source

Embeddings find similar text. But an Acme employee asking about leave policy wants the **current** handbook, not the 2019 draft, and an engineer must not see the legal team's confidential notes. Similarity alone cannot express "current" or "allowed". Metadata transforms retrieval from "find similar text" to "find the right text from the right source at the right time." It enables filtering, ranking, attribution, and access control.

### What metadata to track

**Document-level** (applies to all chunks from a document):

- **source**: Document origin (filename, URL, database ID). Enables tracing chunks back to source.
- **doc_type**: Category (pdf, markdown, code, email). Enables type-specific filtering.
- **created_at / updated_at**: Timestamps (ISO 8601). Enables recency filtering.
- **author / owner**: Creator or responsible party. Enables authority-based ranking.
- **category / tags**: Topic classification. Enables domain filtering.
- **version**: Document version number. Enables version-specific retrieval.
- **access_level**: Permission level (public, internal, confidential). Enables basic access control.
- **roles / departments / permissions / owner_id**: RBAC fields for hard security filtering. See [retrieval RBAC]({{ site.baseurl }}/docs/genai/rag/retrieval/page/#hard-security-filtering-rbac) for implementation.

**Chunk-level** (specific to individual chunks):

- **chunk_index**: Position within document. Enables ordering and context reconstruction.
- **section / heading**: Section hierarchy. Enables section filtering.
- **page_number**: Page in original document (PDFs). Enables citation.
- **word_count**: Chunk size (word-level approximation via `len(chunk.split())`). Enables quality monitoring.

**Derived** (computed during indexing):

- **embedding_model**: Model used. Enables compatibility checking.
- **indexed_at**: When chunk was indexed. Enables incremental update tracking.
- **doc_hash**: SHA256 of source document. Enables change detection and idempotency.

**Track where each chunk came from, when, who may see it, and how it was indexed.**

### Metadata structure

Store metadata as flat key-value pairs, not nested objects. Vector databases index flat fields efficiently but struggle with nested structures.

```python
metadata = {
    "source": "handbook.pdf",
    "doc_type": "pdf",
    "category": "hr",
    "created_at": "2024-01-15T10:30:00Z",
    "section": "Benefits",
}
```

**Full metadata attachment example**:

```python
import hashlib
from datetime import datetime, timezone

from qdrant_client.models import PointStruct

chunks = splitter.split_text(document_text)
embeddings = model.encode(chunks)

for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
    metadata = {
        "source": "hipaa_guide.pdf",
        "doc_type": "pdf",
        "category": "compliance",
        "author": "legal-team",
        "created_at": "2024-01-15T10:30:00Z",
        "version": "v2.3",
        "access_level": "internal",
        "roles": ["legal", "compliance", "engineering"],
        "departments": ["legal"],
        "permissions": ["read"],
        "owner_id": "legal-team",
        "chunk_index": i,
        "section": extract_section(chunk),
        "page_number": extract_page(chunk),
        "word_count": len(chunk.split()),
        "embedding_model": "all-mpnet-base-v2",
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "doc_hash": hashlib.sha256(document_text.encode()).hexdigest(),
    }

    client.upsert(
        collection_name="documents",
        points=[PointStruct(id=i, vector=embedding.tolist(), payload={"text": chunk, **metadata})]
    )
```

**Metadata enables**: filtered retrieval ("only legal-team PDFs"), recency boosting, attribution ("Source: hipaa_guide.pdf, Page 5"), access control via RBAC fields, deduplication via doc_hash.

**Keep metadata flat, and attach it at indexing time, because adding it later means reindexing.**

### Contextual chunk headers (CCH)

Metadata sits beside the chunk. The embedding still sees only the chunk's text. Chunks often lack context about where they came from. "Nike has committed to reducing emissions by 50%" is meaningless without knowing it's from the "Nike Climate Impact Report 2025" under "Environmental Commitments."

CCH fixes that by prepending document and section context to chunks before embedding, significantly improving retrieval precision for ambiguous chunks. CCH is a cheap, rule-based approximation of Anthropic's [contextual retrieval](https://www.anthropic.com/news/contextual-retrieval), which uses an LLM to write chunk-specific context. In Anthropic's tests, contextual embeddings alone reduced top-20 retrieval failures by 35%, contextual embeddings plus contextual BM25 by 49%, and adding reranking by 67%. Expect smaller gains from headers alone, and measure on your own corpus.

**How it works**: Parse document structure, prepend context header (title + section hierarchy) to each chunk before embedding. Store both contextualized text (for embedding/search) and original text (for LLM generation).

```python
def create_contextual_chunks(document: str, doc_title: str, chunk_size: int = 500) -> list[dict]:
    """Prepend document and section context to each chunk before embedding."""
    sections = extract_document_structure(document, doc_title)
    all_chunks = []

    for section_header, section_text in sections:
        chunks = split_text(section_text, chunk_size=chunk_size, overlap=50)
        for i, chunk in enumerate(chunks):
            context_header = f"Document: {doc_title}\nSection: {section_header}\n\n"
            all_chunks.append({
                'text_for_embedding': context_header + chunk,
                'text_for_generation': chunk,
                'metadata': {'doc_title': doc_title, 'section': section_header, 'chunk_index': i}
            })
    return all_chunks
```

**Context header formats**:

**Minimal** (title only):
```
Document: Nike Climate Impact Report 2025

Nike has committed to reducing emissions by 50% by 2030...
```

**Standard** (title + section):
```
Document: Nike Climate Impact Report 2025
Section: Environmental Commitments

Nike has committed to reducing emissions by 50% by 2030...
```

**Rich** (title + section + metadata):
```
Document: Nike Climate Impact Report 2025
Section: Environmental Commitments > Emission Reduction Goals
Type: Annual Report
Date: 2025-01-15

Nike has committed to reducing emissions by 50% by 2030...
```

**Full indexing implementation**:

```python
doc_title = "Nike Climate Impact Report 2025"
document_text = load_document("nike_climate_report.md")
chunks = create_contextual_chunks(document_text, doc_title, chunk_size=500)

texts_for_embedding = [chunk['text_for_embedding'] for chunk in chunks]
embeddings = model.encode(texts_for_embedding)

for chunk, embedding in zip(chunks, embeddings):
    client.upsert(
        collection_name="documents",
        points=[PointStruct(
            id=chunk['metadata']['chunk_index'],
            vector=embedding.tolist(),
            payload={
                'text_for_embedding': chunk['text_for_embedding'],
                'text_for_generation': chunk['text_for_generation'],
                'doc_title': chunk['metadata']['doc_title'],
                'section': chunk['metadata']['section'],
                'chunk_index': chunk['metadata']['chunk_index'],
            }
        )]
    )

query_results = client.query_points(collection_name="documents", query=query_embedding, limit=5).points
llm_context = [result.payload['text_for_generation'] for result in query_results]
```

**Optimization**: Use abbreviated headers for frequently repeated metadata:

```python
"Document: Nike Climate Impact Report 2025\nSection: Environmental Commitments\n\n"

"Doc: Nike Climate 2025 | Env Commitments\n\n"
```

**When to use**: Documents with clear hierarchy (reports, academic papers, legal docs), multi-document corpora, chunks that lack self-contained context. **When to skip**: Already self-contained documents (FAQs, product descriptions), single-document retrieval, or when simple chunking achieves acceptable quality.

**Trade-offs**: Improves retrieval precision and makes chunks self-contained. Costs 10-50 extra tokens per chunk for headers, increases embedding costs, and requires structure parsing. On 500-token chunks, 10-50 tokens is a 2-10% increase in embedding cost. A/B test on your corpus before committing.

**Prepend title and section to each chunk before embedding, and keep the clean text for the LLM.**

**So far:** each chunk becomes a vector whose distance to a query reflects similarity of meaning. Model choice and dimensions trade quality against storage. Metadata adds source, time, and permissions so retrieval can filter, and contextual headers put that context into the embedding itself.

---

## Part 5: A vector database trades a little recall for a lot of speed

You've chunked and embedded. Now you need a database optimized for "find the 5 closest vectors" across millions of chunks.

Start with one query and every chunk. Comparing the query to all 1M of Acme's chunk vectors is exact, and it works. But it costs 1M comparisons per query, and that grows with every document you add. Linear search doesn't scale past 10K chunks. The fix is an approximate index that checks a small, well-chosen fraction of the vectors and almost always finds the same top results.

### In-memory vs persistent

**In-memory** (FAISS, Annoy): microsecond latency, no network overhead. Works for <10M chunks (~60GB at 1536 dims). Requires reloading on restart.

```python
import faiss
import numpy as np

EMBEDDING_DIM = 1536
HNSW_M = 32

index = faiss.IndexHNSWFlat(EMBEDDING_DIM, HNSW_M)
index.add(embeddings)
distances, indices = index.search(query_embedding[np.newaxis, :], k=5)
```

**Persistent** (Pinecone, Weaviate, Qdrant, Milvus): scales to billions, supports metadata filtering. Network latency (5-20ms) but handles larger-than-RAM datasets.

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

EMBEDDING_DIM = 1536
QDRANT_PORT = 6333

client = QdrantClient("localhost", port=QDRANT_PORT)
client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
)
client.upsert(collection_name="documents", points=points)
results = client.query_points(collection_name="documents", query=query_embedding.tolist(), limit=5).points
```

Use in-memory for <1M chunks, single-machine, <10ms latency requirements. Use persistent for >1M chunks, metadata filtering, multi-service access.

**Use an in-memory index for small, single-machine workloads, and a persistent database when you need scale or filters.**

### Index types

| Algorithm | Recall@10 | Latency | Memory | When to use |
|-----------|-----------|---------|--------|-------------|
| **HNSW** | 95-99% | <10ms | High (~1.5x vectors) | Default. Best recall/latency trade-off. |
| **IVF** | 80-95% | <5ms | Low (1.5x vectors) | Memory-constrained. |
| **IVF+SQ** | 90-97% | <5ms | Low (0.25x vectors) | Production default when memory is a constraint. |
| **IVF+PQ** | 80-95% | <5ms | Low (0.03–0.1x vectors) | Billion-scale. Better recall than PQ alone. |
| **Flat** (brute-force) | 100% | Linear in N | 1x vectors | <10K chunks. Ground truth for ablations. |

HNSW is your default. Tune with `M=32, efConstruction=200, efSearch=50` for balanced performance (95% recall, <10ms). Increase for higher recall, decrease for speed.

**Recall@10**: probability that the true top-10 nearest neighbors appear in the approximate top-10. At 95%, about 9.5 of the true 10 show up on average. When you're retrieving 50 and reranking to 5, recall matters less, so optimize for latency.

What index recall does not tell you: whether the nearest neighbors are the right answers. It compares the approximate search with exact search over the same embeddings. If the embeddings are poor, a 100% recall index faithfully returns poor results.

**Start with HNSW, and judge index recall against exact search, not against answer quality.**

### Quantization

Indexes make search fast. They do not make vectors smaller, and at scale, memory becomes the limit. Quantization compresses vector representations to reduce memory and speed up distance calculations. It is independent of the index algorithm: you can apply SQ or PQ on top of HNSW or IVF. Three methods are available in modern vector databases.

Take one 1536-dim float32 vector: 1536 × 4 = 6,144 bytes, about 6 KB. Here is what each method does to it.

**Scalar Quantization (SQ)**: maps each float32 component (4 bytes) to int8 (1 byte), so 6,144 bytes become 1,536: a 4× memory reduction. Distance calculations on int8 values are faster and remain highly accurate. Recall loss is typically <2% compared to float32. This is the **production default** in Qdrant and Milvus when memory reduction is needed.

```python
from qdrant_client.models import (
    Distance,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(type=ScalarType.INT8, quantile=0.99, always_ram=True)
    ),
)
```

**Product Quantization (PQ)**: divides a vector into M sub-vectors, quantizes each sub-vector using a learned codebook of K centroids, and stores only the centroid index (1 byte per sub-vector). With 96 sub-vectors, the 6,144-byte vector compresses to 96 bytes: a 64× reduction. Recall loss is significant (~10–20%) and build time is slow (codebook training requires a representative sample of your corpus). Use only when RAM is the hard constraint at billion scale.

**Binary Quantization (BQ)**: maps each float32 to a single bit (1/32 size), so 1,536 dimensions take 192 bytes. Recall loss is high for general embeddings but close to SQ for some high-dimensional models (e.g. OpenAI `text-embedding-3-large`, Cohere Embed v4) when combined with oversampling and rescoring against the original vectors. Supported by Qdrant, Weaviate, Milvus, Elasticsearch (BBQ) and pgvector. Up to ~40× faster search for compatible models; verify recall on your corpus.

| Method | Compression | Recall loss | Build speed | Best for |
|--------|-------------|-------------|-------------|----------|
| **SQ (int8)** | 4× | <2% | Fast | Default memory reduction |
| **PQ** | 32–64× | 10–20% | Slow | Billion-scale, disk-constrained |
| **BQ** | 32× | <5% (qualified models) | Fast | High-dim commercial embeddings |

**Rule of thumb**: start with SQ. Only adopt PQ if SQ doesn't fit within your RAM budget and you've verified recall remains acceptable on your corpus.

**Quantize with int8 first; move to stronger compression only when memory forces it and recall survives it.**

### Production patterns

1. **Build index offline**: Use a staging index, build fully, then hot-swap. Don't block queries during indexing.
2. **Shard by metadata**: Split by time, domain, or access pattern. Search shards selectively.
3. **Monitor recall**: Track both retrieval metrics (correct chunk in top-5?) and end-to-end metrics (LLM answered correctly?).
4. **Quantize**: apply Scalar Quantization (int8) first: 4× memory reduction with <2% recall loss. See [Quantization](#quantization) for the SQ → PQ → BQ decision tree.

**Build offline and swap, shard by access pattern, and watch recall in production.**

---

## Part 6: Measure chunking before you change it

Part 2 offered nine chunking strategies. Which one should Acme use? You cannot tell by reading chunks. The real goal is retrieval quality (did we find the right chunk?) and generation quality (did the LLM answer correctly?). But you can measure chunking quality independently.

### Intrinsic metrics (chunk quality)

**Chunk coherence**: Embed each sentence in a chunk, compute pairwise cosine similarity. High similarity = coherent. Target >0.7.

```python
from sklearn.metrics.pairwise import cosine_similarity

def chunk_coherence(chunk: str) -> float:
    """Compute average pairwise cosine similarity of sentence embeddings within a chunk."""
    sentences = chunk.split('. ')
    if len(sentences) < 2:
        return 1.0
    embeddings = model.encode(sentences)
    similarities = cosine_similarity(embeddings)
    n = len(similarities)
    return (similarities.sum() - n) / (n * (n - 1))
```

The last line looks odd, so take it apart with three sentences. The similarity matrix is 3 × 3, so it has 9 entries. The 3 on the diagonal compare each sentence with itself and are always 1. Subtracting `n` removes them, and dividing by `n × (n − 1)` = 6 averages the remaining off-diagonal pairs. The result is the average similarity between different sentences.

**Boundary preservation**: Count splits that occur mid-sentence. Lower is better.

**Chunk size variance**: Coefficient of variation (std/mean). Target <0.3. Chunks of 400, 500, and 600 tokens have a mean of 500 and a standard deviation of about 82, so CV ≈ 0.16. High variance means some chunks are too small (no context) or too large (diluted relevance).

What intrinsic metrics do not tell you: whether users find answers. A perfectly coherent chunk can still be the wrong chunk.

**Intrinsic metrics catch broken chunks cheaply, before you have labeled queries.**

### Extrinsic metrics (retrieval quality)

Requires labeled query-document pairs.

**Hit Rate@k**: Fraction of queries where the correct chunk appears in top-k results. If 82 of 100 test queries find their correct chunk in the top 5, Hit Rate@5 = 0.82. Target >0.9.

**MRR (Mean Reciprocal Rank)**: Average of 1/rank for the first correct chunk. 1.0 = always rank 1.

**NDCG@k**: Accounts for graded relevance. See [ML Evaluation]({{ site.baseurl }}/docs/machine-learning/evaluation/page/#part-5-ranking-metrics-care-about-position) for details.

**Extrinsic metrics answer the question that matters: does the right chunk come back near the top?**

### Evaluation workflow

1. **Create test set**: 100-500 queries with labeled correct chunks.
2. **Baseline**: Recursive splitting with default parameters.
3. **Ablations**: Vary chunk sizes (256, 500, 800), overlaps (0%, 10%, 20%), and strategies.
4. **Measure**: Hit Rate@5, MRR, chunk coherence per configuration.
5. **Select**: Maximize Hit Rate@5 subject to latency constraints. If two configs differ by <2%, pick the simpler one.

**Example results**:

| Configuration | Hit Rate@5 | MRR | Coherence | Indexing Time (1K docs) |
|---------------|------------|-----|-----------|-------------------------|
| Character split (baseline) | 0.65 | 0.42 | 0.55 | 5 min |
| Recursive (500 tokens, 10% overlap) | 0.82 | 0.61 | 0.74 | 8 min |
| Recursive (500 tokens, 20% overlap) | 0.85 | 0.65 | 0.78 | 10 min |
| Semantic (embedding-based) | 0.88 | 0.68 | 0.82 | 45 min |

You might expect the most sophisticated strategy to win. Read the table again. Recursive (500 tokens, 20% overlap) wins. Semantic chunking adds 3 points of Hit Rate (0.85 → 0.88) at 45 / 10 = 4.5x the indexing time. That is not worth it unless you're in a high-stakes regime. LLM-based semantic chunking is even slower (hours) with similar gains.

**Choose the chunking configuration with labeled queries, and prefer the simpler one when the gain is small.**

**So far:** a vector database answers "nearest vectors" with an approximate index that keeps recall near 95% at a fraction of the cost, and quantization shrinks each vector by 4× to 64×. Intrinsic metrics catch broken chunks, and Hit Rate@5 on labeled queries picks the chunking configuration.

---

## Part 7: A production index updates itself without a rebuild

### Prototype pipeline

Get documents indexed and searchable in <50 lines.

```python
import faiss
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

CHUNK_OVERLAP = 64

documents = ["RAG stands for Retrieval-Augmented Generation...", "..."]

model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
# Size chunks in the embedding model's own tokens: all-mpnet-base-v2 truncates
# anything beyond max_seq_length (384) without warning.
splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
    model.tokenizer, chunk_size=model.max_seq_length - 2, chunk_overlap=CHUNK_OVERLAP
)
chunks = splitter.split_text("\n\n".join(documents))

embeddings = model.encode(chunks, show_progress_bar=True)

index = faiss.IndexFlatL2(embeddings.shape[1])
index.add(embeddings.astype('float32'))
faiss.write_index(index, "index.faiss")
```

Notice the chunk size. You might reach for the 500-token default from Part 2. But `all-mpnet-base-v2` reads at most 384 tokens and silently drops the rest. A 500-token chunk would be embedded as its first 384 tokens, and the last quarter would be unsearchable. So the splitter sizes chunks with the model's own tokenizer and limit.

Exact search (IndexFlatL2) is fine for <10K chunks. No optimization, no metadata, but it works for prototypes and demos.

**A prototype index is a splitter, an embedding model, and a flat index, sized to the model's token limit.**

### Production pipeline

The prototype breaks as soon as a document changes: you either reindex everything or end up with stale and duplicate chunks. Production adds metadata tracking, incremental updates, ANN indexes, error handling, and monitoring.

```python
import hashlib
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

CHUNK_OVERLAP = 64
QDRANT_PORT = 6333
POINT_ID_MODULUS = 2**63


class ProductionIndexer:
    """Chunk, embed, and upsert documents into a Qdrant collection with idempotency."""

    def __init__(self, collection_name: str = "documents"):
        self.model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        # Count tokens with the embedding model's own tokenizer and stay under its
        # max_seq_length (384 for all-mpnet-base-v2); longer chunks are silently truncated.
        self.splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
            self.model.tokenizer,
            chunk_size=self.model.max_seq_length - 2,  # leave room for special tokens
            chunk_overlap=CHUNK_OVERLAP,
        )
        self.client = QdrantClient("localhost", port=QDRANT_PORT)
        self.collection_name = collection_name

    def split(self, source: str, metadata: dict) -> list[str]:
        """Split source text into chunks using the default recursive splitter."""
        return self.splitter.split_text(source)

    def index_document(self, doc_id: str, text: str, metadata: dict) -> int:
        """Index a single document, skipping unchanged content and replacing stale chunks."""
        doc_hash = hashlib.sha256(text.encode()).hexdigest()

        existing = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter={"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
            limit=1,
        )
        if existing[0] and existing[0][0].payload.get("doc_hash") == doc_hash:
            logger.debug("Document %s unchanged, skipping", doc_id)
            return 0

        if existing[0]:
            logger.info("Replacing stale chunks for document %s", doc_id)
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={"filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}},
            )

        chunks = self.split(text, metadata)
        embeddings = self.model.encode(chunks)
        points = [
            PointStruct(
                id=int(hashlib.sha256(f"{doc_id}-{i}".encode()).hexdigest()[:16], 16) % POINT_ID_MODULUS,
                vector=emb.tolist(),
                payload={"doc_id": doc_id, "doc_hash": doc_hash, "chunk_index": i, "text": chunk, **metadata},
            )
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info("Indexed %d chunks for document %s", len(chunks), doc_id)
        return len(chunks)
```

The hash is the key idea. If the HR handbook has not changed, its SHA256 matches the stored `doc_hash`, and the indexer skips it in one lookup. If it changed, the old chunks are deleted before the new ones go in, so no stale chunk survives.

**Batch indexing**:

```python
def index_batch(self, documents: list[dict]) -> dict:
    """Index multiple documents, collecting per-batch statistics."""
    stats = {"total_docs": len(documents), "total_chunks": 0, "failed": 0}
    for doc in documents:
        try:
            chunks = self.index_document(doc["doc_id"], doc["text"], doc.get("metadata", {}))
            stats["total_chunks"] += chunks
        except (ConnectionError, ValueError, KeyError) as e:
            stats["failed"] += 1
            logger.error("Document %s failed: %s", doc.get("doc_id"), e)
    return stats
```

**Multi-document type indexer**: Route to appropriate splitters based on document type.

```python
from langchain_text_splitters import (
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None

CODE_CHUNK_SIZE = 1000
CODE_CHUNK_OVERLAP = 200


class MultiTypeIndexer(ProductionIndexer):
    """Override ProductionIndexer.split so index_document() routes by doc_type."""

    def __init__(self, collection_name: str = "documents"):
        super().__init__(collection_name)
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
            strip_headers=False,
        )
        self.code_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.PYTHON, chunk_size=CODE_CHUNK_SIZE, chunk_overlap=CODE_CHUNK_OVERLAP,
        )

    def split(self, source: str, metadata: dict) -> list[str]:
        """Split by doc_type. For "pdf", `source` is a file path or URL, not extracted text."""
        doc_type = metadata.get("doc_type", "text")
        if doc_type == "markdown":
            return [chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
                    for chunk in self.markdown_splitter.split_text(source)]
        if doc_type == "code":
            return self.code_splitter.split_text(source)
        if doc_type == "pdf":
            assert DocumentConverter is not None, "docling is required for PDF splitting"
            converter = DocumentConverter()
            result = converter.convert(source)
            markdown = result.document.export_to_markdown()
            return [chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
                    for chunk in self.markdown_splitter.split_text(markdown)]
        return super().split(source, metadata)
```

Type-specific splitting prevents splitting mid-table (PDF), mid-function (code), or losing header context (markdown). Tag chunks with `doc_type` for type filtering at retrieval time. For Acme's mixed corpus, the wiki goes through the markdown path, the repository through the code path, and the handbook through Docling.

Key additions over prototype: idempotency (doc_hash skips unchanged documents), change detection, metadata attachment, error handling, and logging.

**A document hash makes indexing idempotent: unchanged documents cost one lookup, changed ones replace their old chunks.**

### Incremental updates

Don't rebuild the entire index when you add 10 new documents. The `ProductionIndexer` above handles this: new documents are appended, updated documents have old chunks deleted and new ones inserted.

Rebuild only when parameters change: chunk size, embedding model, or index algorithm. Rebuilding a 1M chunk index takes hours; incremental updates take seconds.

Why must a model change trigger a full rebuild? Because two embedding models place text in different spaces. A query embedded with the new model cannot be compared with chunks embedded by the old one, any more than coordinates in two different maps.

**Update content incrementally, and rebuild only when the chunking, the embedding model, or the index changes.**

---

## Part 8: Indexing has costs you can estimate in advance

RAG indexing has real costs: embedding API calls, storage, compute, and team time. These sections provide concrete numbers for budgeting, vendor selection, and staffing.

### Indexing costs

**Embedding API costs** scale linearly with token count. Check your provider's current per-token rate and multiply:

`total_cost = (doc_count × avg_tokens_per_doc) × price_per_token`

| Document Count | Avg Tokens/Doc | Total Tokens |
|----------------|----------------|--------------|
| 10,000 docs | 500 | 5M tokens |
| 100,000 docs | 500 | 50M tokens |
| 1,000,000 docs | 500 | 500M tokens |
| 1,000,000 docs | 2000 (long docs) | 2B tokens |

Read the first row: 10,000 × 500 = 5,000,000 tokens. Multiply by your provider's price per token, and that is the cost of one full embedding pass. Remember that overlap adds to it: 20% overlap means roughly 25% more tokens embedded, as we saw in Part 2.

Most providers offer a **batch tier** (delayed processing window) at ~50% discount. Use batch for initial indexing, standard for incremental updates.

**Cost optimization**: Batch documents per API call, use the batch tier for bulk indexing, and consider self-hosted models (e.g., SentenceTransformers on GPU) when API spend dominates and you already have GPU/ops capacity.

**Embedding cost is total tokens times price, so estimate it from document count, length, and overlap.**

### Storage costs

**Storage calculation**: `num_chunks × (vector_dim × 4 bytes + metadata_size)`. Example: 1M chunks, 768-dim, 500 bytes metadata = 1M × (3,072 + 500) bytes = 3.57 GB.

| Provider type | Relative cost | Notes |
|---------------|---------------|-------|
| **Managed SaaS** (Pinecone, Weaviate Cloud) | $$$ | Zero ops, pay-per-use or monthly minimum, fastest TTM |
| **Hybrid cloud** (Qdrant Cloud, Weaviate Plus) | $$ | Your infra + managed control plane, some free tiers available |
| **Self-hosted** (Qdrant, Milvus) | $ | Full control, requires DevOps (0.5+ FTE) |
| **In-memory** (FAISS) | Server cost only | Not persistent, prototype/research use, <10M chunks |

Always use each vendor's **pricing calculator** for accurate estimates. Pricing models vary (per-GB, per-vector-dimension, per-read-unit) and change frequently.

**Optimization**: Quantize to float16 (50% storage savings, <1% quality loss), implement document TTL, monitor metadata size.

**Storage is chunks times bytes per vector plus metadata; quantization and TTLs keep it in check.**

### Query costs

Query costs have three components, ranked by typical magnitude:

1. **Reranking** (cross-encoder, GPU): most expensive per query, 10-100× embedding cost
2. **Vector search** (managed): included in plan or usage-based; self-hosted is near-zero marginal cost
3. **Query embedding**: negligible; a typical 30-50 token query costs a fraction of a cent per 1K queries at current API rates

**Rule of thumb**: At low-to-moderate query volumes (<100K/day), embedding and search costs are dwarfed by the fixed monthly cost of your vector database. Reranking is the main variable cost to watch.

**At moderate volume, the database plan dominates query cost, and reranking is the variable to watch.**

### Total cost of ownership

| Component | Managed SaaS | Hybrid Cloud | Self-Hosted |
|-----------|-------------|--------------|-------------|
| Infra cost | Highest | Medium | Lowest |
| Query cost | Usage-based | Usage-based | Near-zero marginal |
| Ops overhead | ~0 FTE | ~0.1 FTE | 0.5+ FTE |
| Time to production | Weeks | Weeks | Months |

**When does self-hosted break even?** Only when infrastructure savings exceed the cost of ops labor. Typically this requires >100K queries/day or >5M chunks and a team that already has Kubernetes/DevOps capacity. Below that, managed services save money because labor cost dominates infrastructure cost.

**Verify current pricing**: [OpenAI Embeddings](https://platform.openai.com/docs/pricing), [Pinecone](https://www.pinecone.io/pricing/), [Qdrant](https://qdrant.tech/pricing/), [Weaviate](https://weaviate.io/pricing)

**Self-hosting pays off only when infrastructure savings exceed the people needed to run it.**

### Comparison matrix

| Factor | Self-Hosted (Qdrant/Milvus) | Managed SaaS (Pinecone/Weaviate Cloud) |
|--------|------------------------------|----------------------------------------|
| Relative infra cost | Lower (server/VM costs only) | Higher (convenience premium) |
| Time to production | 8-12 weeks | 2-4 weeks |
| Engineering overhead | 0.5-1 FTE ops | ~0 FTE |
| Control & customization | Full | Limited |
| Vendor lock-in | None | High |
| Compliance | DIY | Vendor-certified (SOC 2, HIPAA BAA) |

### Vendor landscape

| Vendor | Best for | Pricing model |
|--------|----------|---------------|
| **Pinecone** | Fast TTM, small teams, SOC 2/HIPAA | Per-GB storage + per-read/write unit |
| **Weaviate Cloud** | GraphQL, multi-modal, open-source preference | Per-vector-dimension + storage |
| **Qdrant Cloud** | Cost-conscious, RBAC filtering, hybrid deploy | Resource-based (RAM/CPU/storage), free tier available |
| **Qdrant Self-Hosted** | Scale optimization, full control, data sovereignty | Server cost + ops labor |
| **Milvus Self-Hosted** | Billion-scale, GPU acceleration, research | Server cost + 1-2 FTE ops |
| **pgvector** (PostgreSQL) | Teams already running Postgres, avoiding new infra | Included in Postgres hosting cost |
| **ChromaDB** | Fast RAG prototyping, Python-native, embedded use | Free (open-source), cloud option emerging |
| **FAISS In-Memory** | Benchmarking, research, <1M chunks | Server cost only |

**Choose the vendor by team capacity, compliance needs, and scale, then confirm the numbers with its pricing calculator.**

**So far:** a prototype index fits in a page of code, a production one adds hashes for idempotent updates and type-aware splitting, and a rebuild is needed only when parameters change. Costs follow simple arithmetic: tokens times price for embedding, chunks times bytes for storage, and people for operations.

---

## Common pitfalls

**Chunking without overlap**: If chunk N ends with "The solution is" and chunk N+1 starts with "to use caching", neither chunk answers "What's the solution?". Add 10-20% overlap.

**Using character count instead of token count**: A 1000-character chunk might be 250 or 400 tokens depending on content. Use `from_tiktoken_encoder` or count tokens explicitly with `tiktoken`.

**Chunks longer than the embedding model's limit**: Models such as `all-mpnet-base-v2` silently truncate past their maximum sequence length. Size chunks with the model's own tokenizer.

**Ignoring chunk size distribution**: If 10% of chunks are <100 tokens or >2000 tokens, your splitting produces outliers that hurt retrieval.

**Reindexing everything on every change**: Incremental updates are 100x faster. Only rebuild when parameters change.

**Embedding before chunking**: Chunk first, embed chunks. You can't split a vector without re-embedding.

**Losing document metadata**: If you only store chunk text, you can't filter by author, date, or category. Always attach metadata.

**Mixing incompatible embeddings**: Switching models requires full reindex. New and old embeddings live in different spaces.

**Skipping evaluation**: You don't know if recursive splitting beats semantic chunking until you measure Hit Rate@5. Evaluate every strategy change.

**Chunking code like prose**: Use code-aware splitters. A chunk containing `def foo(x:` without the closing `)` confuses retrieval.

**Trusting layout-agnostic PDF extraction**: `pypdf`'s `PdfReader(...).pages[i].extract_text()` loses all layout. Tables become unreadable. Use layout-aware parsers like Docling, LlamaParse, or Marker.

**Hardcoding chunk size**: Different use cases need different sizes. FAQ queries want 500 tokens for precision; explanations want 1500 for context.

**Not monitoring index growth**: A document updated 100 times creates 100x chunks without deletion. Implement TTL or version limits.

---

## Best practices

**Start with recursive splitting.** 500-token chunks, 100-token overlap, default separators. Works for most use cases. Move to smarter splitting only when you've measured that chunking is the bottleneck.

**Measure retrieval quality, not generation quality, when tuning chunking.** If Hit Rate@5 is 90% but the LLM hallucinates, chunking is not the problem. Track MRR and NDCG@k alongside Hit Rate for a complete picture.

**Overlap usually helps.** 10-20% prevents information loss at boundaries. Test with your retriever; some sparse models (e.g. SPLADE) show no benefit.

**Use metadata for filtering.** Attach structure (sections, timestamps, authors) to chunks. Filter at retrieval time. It reduces search space and improves relevance compared to post-processing.

**Don't chunk code like prose.** Use code-aware splitters that respect syntax boundaries.

**PDF structure matters.** Use layout-aware parsers (Docling, LlamaParse, Marker) that preserve tables and section boundaries.

**Quantize embeddings in production.** Scalar Quantization (int8) is the default first step: 4× memory reduction with <2% recall loss. Only move to Product Quantization if SQ doesn't fit your RAM budget; PQ's 32–64× compression comes with 10–20% recall loss.

**Reindex incrementally.** Full reindex only for parameter changes, not content updates.

**Monitor chunk size distribution.** Outliers (<100 or >2000 tokens) hurt retrieval.

**Implement RBAC metadata for enterprise.** Add roles, departments, owner_id at indexing time for hard security filtering at retrieval time without reindexing. For complex hierarchies (users in hundreds of groups), consider post-retrieval authorization instead of metadata explosion.

**Consider parent-child indexing.** Embed small chunks for precision, but return the parent section for context. Balances retrieval accuracy with LLM context needs.

**Index for hybrid search.** Maintain both vector and keyword (BM25) indexes. Dense + sparse retrieval consistently outperforms either alone, especially for exact-match terms. Vector databases like Qdrant and Weaviate support sparse vectors natively; for others, maintain a separate BM25 index (e.g. Elasticsearch, tantivy).

**Test on real queries.** Sample 500 production queries, label correct chunks, measure Hit Rate@5. This is your ground truth.

---

## Recap

- Clean documents first: strip page furniture, navigation, and OCR noise, and deduplicate.
- Default to recursive splitting at about 500 tokens with 10-20% overlap, measured in tokens.
- Split by structure when it exists, by meaning when it does not, and index derivative forms for content that embeds poorly.
- Use late chunking or contextual headers when chunks lose document context, GraphRAG for cross-document questions, and ColPali for visually rich pages.
- Choose embedding models on retrieval benchmarks, and size chunks to the model's token limit.
- Attach flat metadata at indexing time for filtering, attribution, and access control.
- Start with HNSW and int8 quantization; go further only when memory forces it.
- Pick chunking configurations with Hit Rate@5 on labeled queries.
- Make indexing idempotent with document hashes, and rebuild only when parameters change.
- Estimate costs from tokens, bytes, and people before you choose a vendor.

---

## Exercise

Take one long document you know well, such as a handbook or a long README. Split it with `RecursiveCharacterTextSplitter.from_tiktoken_encoder` at 256, 500, and 800 tokens, each with 10% overlap. For each setting, count the chunks and compute the coefficient of variation of chunk sizes. Then write five questions whose answers you know are in the document, embed the chunks and the questions with one model, and check in which position the right chunk comes back for each question. Which chunk size gives the best Hit Rate@3, and how many more chunks did it cost you?
