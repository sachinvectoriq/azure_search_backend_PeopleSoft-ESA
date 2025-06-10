from flask import Flask, request, jsonify
import base64
import json
import re
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
import os
app = Flask(__name__)
user_conversations = {}
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")

def safe_base64_decode(data):
    if data.startswith("https"):
        return data
    try:
        valid_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        data = data.rstrip()
        while data and data[-1] not in valid_chars:
            data = data[:-1]
        while len(data) % 4 == 1:
            data = data[:-1]
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        decoded = base64.b64decode(data).decode("utf-8", errors="ignore")
        decoded = decoded.strip().rstrip("\uFFFD").rstrip("?").strip()
        decoded = re.sub(r'\.(docx|pdf|pptx|xlsx)[0-9]+$', r'.\1', decoded, flags=re.IGNORECASE)
        return decoded
    except Exception as e:
        return f"[Invalid Base64] {data} - {str(e)}"

def search_and_answer_query(user_query, user_id):
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    AZURE_SEARCH_SERVICE = "https://aiconciergeserach.search.windows.net"
    index_name = "index-peoplesoft"
    deployment_name = "ocm-gpt-4o"

    openai_client = AzureOpenAI(
        api_version="2025-01-01-preview",
        azure_endpoint="https://ai-hubdevaiocm273154123411.cognitiveservices.azure.com/",
        azure_ad_token_provider=token_provider
    )

    search_client = SearchClient(
        endpoint=AZURE_SEARCH_SERVICE,
        index_name=index_name,
        credential=credential
    )

    if user_id not in user_conversations:
        user_conversations[user_id] = {"history": [], "chat": ""}

    user_conversations[user_id]["history"].append(user_query)
    if len(user_conversations[user_id]["history"]) > 3:
        user_conversations[user_id]["history"] = user_conversations[user_id]["history"][-3:]

    history_queries = " ".join(user_conversations[user_id]["history"])

    def fetch_chunks(query_text, k_value, start_index):
        vector_query = VectorizableTextQuery(text=query_text, k_nearest_neighbors=5, fields="text_vector")
        search_results = search_client.search(
            search_text=query_text,
            vector_queries=[vector_query],
            select=["title", "chunk", "parent_id"],
            top=k_value,
            semantic_configuration_name="index-peoplesoft-semantic-configuration",
            query_type="semantic"
        )
        chunks = []
        sources = []
        for i, doc in enumerate(search_results):
            title = doc.get("title", "N/A")
            chunk_content = doc.get("chunk", "N/A").replace("\n", " ").replace("\t", " ").strip()
            parent_id_encoded = doc.get("parent_id", "Unknown Document")
            parent_id_decoded = safe_base64_decode(parent_id_encoded)
            chunk_id = start_index + i
            chunks.append({
                "id": chunk_id,
                "title": title,
                "chunk": chunk_content,
                "parent_id": parent_id_decoded
            })
            sources.append(
                f"Source ID: [{chunk_id}]\nContent: {chunk_content}\nDocument: {parent_id_decoded}"
            )
        return chunks, sources

    # First call: history
    history_chunks, history_sources = fetch_chunks(history_queries, 5, 1)
    # Second call: current query
    standalone_chunks, standalone_sources = fetch_chunks(user_query, 5, 6)

    all_chunks = history_chunks + standalone_chunks
    all_sources = history_sources + standalone_sources
    sources_formatted = "\n\n---\n\n".join(all_sources)

    conversation_history = user_conversations[user_id]["chat"]

    prompt_template = """
You are an AI assistant expert in PeopleSoft HR and Finance. Your role is to answer user queries based solely on Sources. Ensure that all answers are detailed, clear, and provide step-by-step procedures where applicable.

---

**Guidelines**

**Scope of Responses**:
- All answers must strictly adhere to Sources. Do not extrapolate, assume, or provide answers beyond the content available in the Sources.
- Use clear, technical, and precise language tailored for PeopleSoft HR and Finance users.

**Step-by-step Procedures**:
- If the query involves a procedural task (e.g., setting up a module, fixing an issue, or configuring settings), provide a detailed, sequential explanation of steps.

**Clarity in Explanations**:
- Define technical terms or acronyms when first used.
- Illustrate relationships or distinctions between PeopleSoft features or modules, if required.

**Structure**:
- Begin each response with a brief **Summary** of the topic or task being addressed.
- Include sections like **Step-by-Step Process**, **Key Considerations**, or **FAQs** if applicable.

**External References**:
- Each fact must be followed immediately by the citation in square brackets, e.g., [3]. Only cite the chunk ID that directly supports the statement.

---

**Steps for Complex Queries**

When responding to a query requiring a detailed process or multi-step solution:

1. Clarify the purpose of the task or configuration.
2. Use numbered lists to structure step-by-step processes clearly.
3. Highlight user actions (e.g., "Navigate to...", "Click on...", "Enter the value...").
4. Emphasize key settings, dependencies, or potential pitfalls (if documented).
5. If the query involves troubleshooting, focus on identifying and resolving documented common errors.

---

**Output Format**

- **Summary**: Begin with a one-sentence overview of the issue or query.
- **Detailed Response**:
  - Provide an explanation or definition if required.
  - Include the procedural steps in a numbered list (if applicable).
  - If there are additional considerations, guide the user accordingly.
- Always structure the response in clear **Markdown formatting** for easy readability.
- Avoid unnecessary verbosity.

---

**Notes**

- **Documentation Dependency**: If unable to ascertain an answer due to missing documentation, clearly state so and recommend consulting the relevant PeopleSoft resource or support.
- **Complex Examples**: For multifaceted workflows, split processes into sub-sections or bullet points for better organization.

---

**Example Query**: *How can I configure a new Pay Calendar in PeopleSoft?*

**Summary**: Configuring a Pay Calendar in PeopleSoft involves defining pay period schedules that align with your organization's payroll processing requirements.

**Detailed Response**:

1. **Log in to PeopleSoft**: Use your PeopleSoft admin credentials to access the system.
2. **Navigate to Pay Calendar Setup**:
   - Go to the navigation path: `Setup HRMS > Product Related > Payroll Setup > Pay Calendars`.
3. **Add a New Calendar**:
   - Click on the **Add a New Value** tab.
4. **Enter Pay Calendar Information**:
   - Specify the following fields:
     - **Pay Group**: Select the applicable pay group from the drop-down list.
     - **Calendar ID**: Enter a unique identifier for the calendar.
     - **Pay Period Begin and End Dates**: Define the date range for each pay period cycle.
     - **Payment Date**: Enter the date employees will be paid.
5. **Save the Pay Calendar**:
   - Verify all entered details and click the **Save** button to finalize.

**Key Considerations**:
- Ensure the Pay Calendar aligns with payroll processing deadlines and applicable regulations.
- Refer to [Chapter X: Pay Calendars] in PeopleSoft Payroll documentation for additional guidance.


Conversation History:
{conversation_history}

Sources:
{sources}

User Question: {query}

Respond with:
- An answer citing sources inline like [1], [2], especially where the answer is clearly supported.
"""

    prompt = prompt_template.format(
        conversation_history=conversation_history,
        sources=sources_formatted,
        query=user_query
    )

    response = openai_client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
            
            ],
        model=deployment_name,
        temperature=0.7
    )

    full_reply = response.choices[0].message.content.strip()

    # Standardize citation format: [1, 2] not [12] or [1,2]
    original_ids = list(map(int, re.findall(r"\[(\d+(?:,\s*\d+)*?)\]", full_reply)))
    flat_ids = []
    for match in re.findall(r"\[(.*?)\]", full_reply):
        parts = match.split(",")
        for p in parts:
            if p.strip().isdigit():
                flat_ids.append(int(p.strip()))

    unique_original_ids = []
    for i in flat_ids:
        if i not in unique_original_ids:
            unique_original_ids.append(i)

    id_mapping = {old_id: new_id + 1 for new_id, old_id in enumerate(unique_original_ids)}

    def replace_citation_ids(text, mapping):
        def repl(match):
            nums = match.group(1).split(",")
            new_nums = sorted(set(mapping.get(int(n.strip()), int(n.strip())) for n in nums if n.strip().isdigit()))
            return f"[{', '.join(map(str, new_nums))}]"
        return re.sub(r"\[(.*?)\]", repl, text)

    ai_response = replace_citation_ids(full_reply, id_mapping)

    citations = []
    seen = set()
    for old_id in unique_original_ids:
        new_id = id_mapping[old_id]
        for chunk in all_chunks:
            if chunk["id"] == old_id and old_id not in seen:
                seen.add(old_id)
                updated_chunk = chunk.copy()
                updated_chunk["id"] = new_id
                citations.append(updated_chunk)

    user_conversations[user_id]["chat"] += f"\nUser: {user_query}\nAI: {ai_response}"

    follow_up_prompt = f"""
Based only on the following chunks of source material, generate 3 follow-up questions the user might ask.
Only use the content in the sources. Do not invent new facts.

Format:
Q1: <question>
Q2: <question>
Q3: <question>

SOURCES:
{citations}
    """

    follow_up_response = openai_client.chat.completions.create(
        messages=[{"role": "user", "content": follow_up_prompt}],
        model=deployment_name
    )
    follow_ups_raw = follow_up_response.choices[0].message.content.strip()

    return {
        "query": user_query,
        "ai_response": ai_response,
        "citations": citations,
        "follow_ups": follow_ups_raw
    }

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Missing 'query' in request body"}), 400

    user_id = data.get("user_id", "default_user")
    try:
        result = search_and_answer_query(data["query"], user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
