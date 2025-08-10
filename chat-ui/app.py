import streamlit as st
import requests
import json

# --- Page Configuration ---
st.set_page_config(
    page_title="Legal RAG Chatbot",
    page_icon="⚖️",
    layout="centered"
)

# --- App Title ---
st.title("⚖️ Legal RAG Chatbot")
st.caption("A smart chatbot for querying your legal documents.")

# --- N8N Webhook Configuration ---
# IMPORTANT: Replace this with the actual Webhook URL from your n8n Retrieval Workflow
N8N_WEBHOOK_URL = "YOUR_N8N_RETRIEVAL_WORKFLOW_WEBHOOK_URL_HERE"

# --- Session State Initialization ---
# This ensures that the message history is preserved between user interactions
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "สวัสดีครับ ผมเป็นผู้ช่วย AI สำหรับเอกสารกฎหมาย มีอะไรให้ช่วยเหลือครับ?"}
    ]

# --- Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Main Chat Logic ---
if prompt := st.chat_input("Ask a question about your documents..."):
    # Add user's message to history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display a spinner while waiting for the assistant's response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            if N8N_WEBHOOK_URL == "YOUR_N8N_RETRIEVAL_WORKFLOW_WEBHOOK_URL_HERE":
                st.error("Please configure the n8n Webhook URL in the `chat-ui/app.py` file first.")
            else:
                try:
                    # The n8n webhook expects a JSON body with the query
                    payload = {"query": prompt}
                    response = requests.post(N8N_WEBHOOK_URL, json=payload)
                    response.raise_for_status() # Raise an exception for bad status codes

                    # The response from the n8n workflow should contain the final answer.
                    # We assume the n8n workflow is configured to return a JSON object
                    # with a key like "answer" or "response".
                    # Here, we access the 'response' from the Ollama generation.
                    # You might need to adjust the keys based on your n8n workflow's final output.
                    try:
                        # n8n returns a list of items, we take the first one.
                        # The Ollama generate node returns a JSON string in the 'response' field.
                        ollama_response_str = response.json()[0]['json']['body']['response']
                        assistant_response = json.loads(ollama_response_str).get("response", "Sorry, I could not extract a valid answer.")
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        assistant_response = f"Error parsing the response from n8n. Please check the n8n workflow's output structure.\n\nRaw Response: `{response.text}`"

                    st.markdown(assistant_response)
                    # Add assistant's response to history
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})

                except requests.exceptions.RequestException as e:
                    st.error(f"Could not connect to the n8n webhook. Error: {e}")
