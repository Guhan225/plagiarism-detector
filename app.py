import os
import streamlit as st
import requests
from PyPDF2 import PdfReader
import docx
from io import BytesIO
from sentence_transformers import SentenceTransformer, util

# ====== CONFIG ======
API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyCktIrx3v-RN9FuzzdkXIz_65PfyrDnUe4")
CX = os.environ.get("GOOGLE_CX", "c36ce09de453a4ec8")

# Load transformer model once
@st.cache_resource
def load_model():
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

model = load_model()

# ====== HELPERS ======
def extract_text_from_file(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")
        elif name.endswith(".pdf"):
            reader = PdfReader(BytesIO(uploaded_file.read()))
            return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        elif name.endswith(".docx"):
            doc = docx.Document(BytesIO(uploaded_file.read()))
            return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""
    return ""

def google_search(query):
    if not API_KEY or not CX:
        return {"error": "Missing API_KEY or CX"}
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": API_KEY, "cx": CX, "q": query}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def check_plagiarism(text, max_checks=5, similarity_threshold=0.85):
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 30]
    if not sentences:
        return {"status": "no_text", "message": "Not enough text to check."}

    results = []
    checked = 0
    for sent in sentences[:max_checks]:
        checked += 1
        res = google_search(sent[:200])
        if "error" in res:
            return {"status": "error", "message": res["error"]}

        items = res.get("items", [])
        matches = []
        for it in items:
            snippet = (it.get("snippet") or "")
            title = it.get("title") or ""
            link = it.get("link")

            # compute semantic similarity between sentence and snippet
            emb1 = model.encode(sent, convert_to_tensor=True)
            emb2 = model.encode(snippet, convert_to_tensor=True)
            score = float(util.cos_sim(emb1, emb2))
            
            if score >= similarity_threshold:
                matches.append({"title": title, "link": link, "score": score, "snippet": snippet})

        results.append({"sentence": sent, "matches": matches})

    plagiarized = any(len(r["matches"]) > 0 for r in results)
    return {"status": "ok", "checked": checked, "any_matched": plagiarized, "results": results}

# ====== STREAMLIT UI ======
st.set_page_config(page_title="Hybrid Plagiarism Checker", layout="centered")
st.title("🧠 Hybrid Plagiarism Checker (Google + NLP Similarity)")

st.markdown("""
This version detects both **exact** and **paraphrased** plagiarism using:
- 🔍 Google Custom Search for online matches  
- 🤖 Transformer model (`all-MiniLM-L6-v2`) for semantic similarity
""")

col1, col2 = st.columns(2)
with col1:
    mode = st.radio("Input type:", ["Paste text", "Upload file"])
with col2:
    max_checks = st.slider("Sentences to check", 1, 10, 5)

text = ""
if mode == "Paste text":
    text = st.text_area("Paste your text:", height=250)
else:
    uploaded = st.file_uploader("Upload file (.txt, .pdf, .docx)", type=["txt","pdf","docx"])
    if uploaded:
        text = extract_text_from_file(uploaded)
        st.success("✅ Text extracted. Preview:")
        st.write(text[:500] + ("..." if len(text)>500 else ""))

if st.button("Check plagiarism"):
    if not text.strip():
        st.warning("Please provide some text.")
    else:
        st.info("Checking... This may take a few seconds ⏳")
        output = check_plagiarism(text, max_checks=max_checks)
        if output["status"] == "error":
            st.error("Error: " + output["message"])
        elif output["status"] == "no_text":
            st.warning(output["message"])
        else:
            if output["any_matched"]:
                st.error("⚠️ Possible plagiarism found!")
                for r in output["results"]:
                    if r["matches"]:
                        st.markdown(f"**Sentence:** {r['sentence'][:300]}...")
                        for m in r["matches"]:
                            st.markdown(f"- [{m['title']}]({m['link']}) (Similarity: {m['score']:.2f})")
                            st.caption(m["snippet"][:300])
                        st.write("---")
            else:
                st.success("✅ No significant plagiarism found!")

st.caption("Powered by Google Custom Search + Sentence Transformers.")
