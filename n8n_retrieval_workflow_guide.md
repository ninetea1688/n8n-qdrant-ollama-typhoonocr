# n8n Retrieval Workflow Guide

This guide provides a step-by-step recipe for building the retrieval and generation workflow in n8n. This workflow takes a user's query, uses the `retrieval-service` to find relevant document chunks from Qdrant, and then uses Ollama's generation endpoint to create a final answer.

**Prerequisites:**
*   You have successfully built and run the Ingestion Workflow to populate your Qdrant collection.
*   You have a generative LLM pulled in Ollama (e.g., `ollama pull llama3`).

---

### Workflow Overview

`Start` -> `HTTP Request (Retrieval)` -> `Code (Format Context)` -> `HTTP Request (Ollama Generate)`

---

### Node 1: Start

This node will be used to manually trigger the workflow and input a query.

*   **Node Type:** Manual
*   **Configuration:**
    1.  Click **Add Field**.
    2.  Select **String**.
    3.  Set **Field Name** to `query`.
    4.  Set a **Default Value** for testing, e.g., "What are the key regulations regarding...?"

---

### Node 2: HTTP Request (to Retrieval Service)

This node sends the user's query to our new `retrieval-service`.

*   **Node Type:** HTTP Request
*   **Configuration:**
    1.  **Method:** `POST`
    2.  **URL:** `http://retrieval-service:8002/search`
    3.  **Authentication:** `None`
    4.  **Send Body:** `true`
    5.  **Body Content Type:** `JSON`
    6.  **Body:**
        *   Use the "Add Expression" option.
        *   Create the following structure:
        ```json
        {
          "query": "{{ $json.query }}",
          "collection_name": "legal_docs",
          "top_k": 5
        }
        ```
        *   **Note:** Replace `legal_docs` with your actual collection name. `top_k` controls how many results to retrieve.

*   **Output:** This node will output a list of search results, where each item has a `payload` (containing the `text` and `metadata`) and a `score`.

---

### Node 3: Code (Format Context)

This node takes the list of retrieved documents and formats them into a single block of text that we can insert into our final prompt.

*   **Node Type:** Code
*   **Configuration:**
    1.  **Language:** `JavaScript`
    2.  **Code:**
        ```javascript
        // Get the results from the previous node
        const results = $input.all();

        // Format each result into a string
        const contextStrings = results.map((item, index) => {
          const text = item.json.payload.text;
          const source = item.json.payload.metadata.filename || 'N/A';
          const page = item.json.payload.metadata.page_number || 'N/A';
          return `Context [${index + 1}]:\nSource: ${source}, Page: ${page}\nContent: ${text}\n---`;
        });

        // Join all context strings into a single block
        const finalContext = contextStrings.join('\n\n');

        // Return the formatted context and the original query
        return {
          context: finalContext,
          query: $('Start').item.json.query // Pass the original query along
        };
        ```

*   **Output:** This node will output a single item with two fields: `context` (a long string of all retrieved text) and `query`.

---

### Node 4: HTTP Request (Ollama Generate)

This final node sends the formatted context and the user's query to an LLM in Ollama to generate a coherent answer.

*   **Node Type:** HTTP Request
*   **Configuration:**
    1.  **Method:** `POST`
    2.  **URL:** `http://ollama:11434/api/generate`
    3.  **Authentication:** `None`
    4.  **Send Body:** `true`
    5.  **Body Content Type:** `JSON`
    6.  **Body:**
        *   Use the "Add Expression" option and construct the following structure:
        ```json
        {
          "model": "llama3",
          "stream": false,
          "prompt": "Based on the following context, please provide a detailed answer to the user's question. If the context is not sufficient, say that you cannot find the answer in the provided documents.\n\n---\n\nCONTEXT:\n{{ $json.context }}\n\n---\n\nUSER'S QUESTION:\n{{ $json.query }}\n\n---\n\nANSWER:"
        }
        ```
        *   **Note:**
            *   Replace `llama3` with the name of the generative model you have in Ollama.
            *   Setting `stream` to `false` makes n8n wait for the full response.
            *   The prompt engineering here is crucial. This example prompt instructs the model on how to behave.

*   **Output:** The `body` of the output from this node will contain the final generated answer in the `response` field. You can then connect this to a webhook response, a chat message, or any other output you need.
