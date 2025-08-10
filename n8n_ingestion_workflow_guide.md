# n8n Ingestion Workflow Guide

This guide provides a step-by-step recipe for building the data ingestion workflow in n8n. This workflow takes a document, processes it through the `typhoon-ocr` service, chunks and embeds the text using the `chunker-service`, and finally stores the result in Qdrant.

**Prerequisites:**
*   You have successfully run `docker compose up` and all services are running.
*   You have created a collection in Qdrant. For this example, we'll assume the collection is named `legal_docs`.
*   You have installed the custom `Typhoon OCR` node in your n8n instance.

---

### Workflow Overview

`Start` -> `Typhoon OCR` -> `HTTP Request (Chunker)` -> `Split In Batches` -> `HTTP Request (Qdrant Upsert)`

---

### Node 1: Start

This node will be used to manually trigger the workflow and upload a file.

*   **Node Type:** Manual
*   **Configuration:**
    1.  Click **Add Field**.
    2.  Select **File**.
    3.  Set **Field Name** to `sourceFile`. This name is important as the Typhoon OCR node expects it.

---

### Node 2: Typhoon OCR

This is the custom node that processes the document.

*   **Node Type:** Typhoon OCR
*   **Configuration:**
    1.  **Source File:**
        *   Click the "Expression" button (`ƒx`).
        *   Set the value to: `{{ $json.sourceFile }}`
    2.  **Page Number:**
        *   Set to `1` or use an expression if you want to control it dynamically.
    3.  **Use Unstructured:**
        *   Set to **`true`** (toggle on). This enables the advanced layout analysis.
    4.  **Perform Text Cleanup:**
        *   Set to **`true`** (toggle on). This cleans the extracted text.
*   **Output:** This node will output a JSON object containing the result from the `typhoon-ocr` service. The key field will be `result`, which is a list of structured elements (e.g., `{ "type": "Title", "text": "..." }`).

---

### Node 3: HTTP Request (to Chunker Service)

This node sends the structured text elements to the `chunker-service` to be split and embedded.

*   **Node Type:** HTTP Request
*   **Configuration:**
    1.  **Method:** `POST`
    2.  **URL:** `http://chunker-service:8001/chunk_and_embed`
    3.  **Authentication:** `None`
    4.  **Send Body:** `true`
    5.  **Body Content Type:** `JSON`
    6.  **Body:**
        *   Click the "Add Expression" button.
        *   Set the key to `elements` and the value to the following expression: `{{ $json.result }}`
        *   (Optional) You can add other parameters like `model`, `chunk_size`, etc. here if you want to override the defaults. Click "Add Field" in the JSON body editor.
            *   Key: `model`, Value: `mxbai-embed-large` (or your preferred model)
            *   Key: `chunk_size`, Value: `1000`
            *   Key: `chunk_overlap`, Value: `200`
*   **Output:** This node will output a JSON object which is a list of chunks. Each chunk object contains `text`, `embedding`, and `metadata`.

---

### Node 4: Split In Batches

The previous node returns a single item containing a list of all chunks. We need to process each chunk individually to store it in Qdrant. The `Split In Batches` node does exactly this.

*   **Node Type:** Split In Batches
*   **Configuration:**
    1.  **Field to Split:**
        *   Use the expression: `{{ $json.body }}`
    2.  **Batch Size:**
        *   Set to `1`. This will make the node output one item for each chunk.

---

### Node 5: HTTP Request (Qdrant Upsert)

This final node takes each individual chunk and its embedding and "upserts" it into the Qdrant collection.

*   **Node Type:** HTTP Request
*   **Configuration:**
    1.  **Method:** `PUT`
    2.  **URL:**
        *   Use the expression: `http://qdrant:6333/collections/legal_docs/points?wait=true`
        *   Replace `legal_docs` with your actual collection name.
    3.  **Authentication:** `None`
    4.  **Send Body:** `true`
    5.  **Body Content Type:** `JSON`
    6.  **Body:**
        *   This part is crucial. We need to construct the JSON payload that the Qdrant API expects.
        *   Use the "Add Expression" option and construct the following structure:
        ```json
        {
          "points": [
            {
              "id": "{{ $guid() }}",
              "vector": {{ $json.embedding }},
              "payload": {
                "text": "{{ $json.text }}",
                "metadata": {{ $json.metadata }}
              }
            }
          ]
        }
        ```
        *   **Explanation:**
            *   `"id": "{{ $guid() }}"`: We generate a unique GUID for each point in Qdrant.
            *   `"vector": {{ $json.embedding }}`: We pass the embedding vector from the previous node.
            *   `"payload"`: We store the original text and the metadata as the payload. This is what you get back when you search.

---

After setting up these five nodes, you can run the workflow by uploading a PDF or image file in the "Start" node. You can then check your Qdrant dashboard to see the points being added to your collection.
