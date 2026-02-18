"""
Streamlit UI for the Policy RAG Assistant.
Supports both blocking and streaming responses.
"""
import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ITops Assistant",
    page_icon="📘",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    streaming = st.toggle("Streaming response", value=True)
    show_retrieved = st.checkbox("Show all retrieved chunks", value=False)

    st.divider()
    st.subheader("🔍 API Health")
    if st.button("Check"):
        try:
            h = requests.get(f"{API_BASE}/health", timeout=5).json()
            ollama = h.get("ollama", {})
            if ollama.get("ok"):
                st.success(f"Ollama OK – {len(ollama.get('models', []))} model(s)")
                for m in ollama.get("models", []):
                    st.caption(f"• {m}")
            else:
                st.error(f"Ollama error: {ollama.get('error')}")
        except Exception as exc:
            st.error(f"API unreachable: {exc}")

    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Chat history display ──────────────────────────────────────────────────────
st.title("📘 ITops Assistant")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("📎 Citations"):
                for c in msg["citations"]:
                    st.write(f"**{c['source_file']}** | chunk {c['chunk_id']}")
                    if c.get("snippet"):
                        st.caption(c["snippet"])
        if msg.get("next_questions"):
            st.info("**Clarifying questions:**\n" +
                    "\n".join(f"- {q['question']}" for q in msg["next_questions"]))
        if show_retrieved and msg.get("retrieved"):
            with st.expander("🔎 Retrieved chunks"):
                for r in msg["retrieved"]:
                    st.write(f"{r['source_file']} | chunk {r['chunk_id']} | dist {r['distance']}")

# ── Input ─────────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask about IT policies or raise an incident…")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build history for API (last 8 messages = 4 turns)
    history_payload = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[-8:]
        if m["role"] in ("user", "assistant")
    ]

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        full_answer = ""

        if streaming:
            # ── Streaming path ────────────────────────────────────────────────
            try:
                resp = requests.post(
                    f"{API_BASE}/query/stream",
                    json={"question": prompt, "history": history_payload},
                    stream=True,
                    timeout=300,
                )
                resp.raise_for_status()

                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                    if line_str.startswith("data: "):
                        token = line_str[6:]
                        if token == "[DONE]":
                            break
                        if token.startswith("[ERROR]"):
                            st.error(token)
                            break
                        full_answer += token
                        answer_placeholder.markdown(full_answer + "▌")

                answer_placeholder.markdown(full_answer)

            except Exception as exc:
                st.error(f"Streaming error: {exc}")

            # Fetch structured metadata via blocking endpoint
            meta_data: dict = {}
            try:
                meta_resp = requests.post(
                    f"{API_BASE}/query",
                    json={"question": prompt, "history": history_payload},
                    timeout=300,
                )
                if meta_resp.ok:
                    meta_data = meta_resp.json()
            except Exception:
                pass

        else:
            # ── Blocking path ─────────────────────────────────────────────────
            with st.spinner("Thinking…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/query",
                        json={"question": prompt, "history": history_payload},
                        timeout=300,
                    )
                    resp.raise_for_status()
                    meta_data = resp.json()
                    full_answer = meta_data.get("answer", "")
                    answer_placeholder.markdown(full_answer)
                except Exception as exc:
                    st.error(f"API error: {exc}")
                    meta_data = {}

        # ── Render metadata ───────────────────────────────────────────────────
        citations    = meta_data.get("citations", [])
        next_qs      = meta_data.get("next_questions", [])
        missing      = meta_data.get("missing_details", [])
        retrieved    = meta_data.get("retrieved", [])

        if next_qs:
            st.info("**Clarifying questions:**\n" +
                    "\n".join(f"- {q['question']}" for q in next_qs))

        if citations:
            with st.expander("📎 Citations"):
                for c in citations:
                    st.write(f"**{c['source_file']}** | chunk {c['chunk_id']}")
                    if c.get("snippet"):
                        st.caption(c["snippet"])

        if missing:
            with st.expander("ℹ️ Missing incident details"):
                for item in missing:
                    st.write(f"- **{item['field']}**: {item['question']}")

        if show_retrieved and retrieved:
            with st.expander("🔎 Retrieved chunks"):
                for r in retrieved:
                    st.write(
                        f"{r['source_file']} | chunk {r['chunk_id']} | dist {r['distance']}"
                    )

    # Save to history
    st.session_state.messages.append({
        "role":           "assistant",
        "content":        full_answer,
        "citations":      meta_data.get("citations", []),
        "next_questions": meta_data.get("next_questions", []),
        "retrieved":      meta_data.get("retrieved", []),
    })
