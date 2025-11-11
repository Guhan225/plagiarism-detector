# Cell 2: create app.py
%%writefile /content/app.py
import os
import streamlit as st
import requests
from PyPDF2 import PdfReader
import docx
from io import BytesIO

# Read API key and CX from environment (set in Colab before running the app)
API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyCktIrx3v-RN9FuzzdkXIz_65PfyrDnUe4")
CX = os.environ.get("GOOGLE_CX", "c36ce09de453a4ec8")

def extract_text_from_file(uploaded_file):
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")
        elif name.endswith(".pdf"):
            # PdfReader can accept a file-like object
            reader = PdfReader(BytesIO(uploaded_file.read()))
            pages = []
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    pages.append(t)
            return "\n".join(pages)
        elif name.endswith(".docx"):
            # write to temp file-like object
            tmp = uploaded_file.read()
            doc = docx.Document(BytesIO(tmp))
            return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
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

def check_plagiarism_text(text, max_checks=5):
    # split into sentences by period; filter short ones
    sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 30]
    if not sentences:
        return {"status": "no_text", "message": "Not enough text to check."}
    results = []
    checked = 0
    for sent in sentences[:max_checks]:
        checked += 1
        q = sent[:200]  # shorten query
        res = google_search(q)
        if "error" in res:
            return {"status": "error", "message": res["error"]}
        items = res.get("items", [])
        matched = False
        match_info = []
        for it in items:
            snippet = (it.get("snippet") or "").lower()
            title = it.get("title")
            link = it.get("link")
            # simple containment check of first 50 chars
            if sent[:50].lower() in snippet or sent[:50].lower() in (title or "").lower():
                matched = True
                match_info.append({"title": title, "link": link, "snippet": it.get("snippet","")})
        results.append({"sentence": sent, "matched": matched, "matches": match_info})
    # decide final verdict: if any sentence matched -> plagiarism
    any_matched = any(r["matched"] for r in results)
    return {"status": "ok", "checked": checked, "any_matched": any_matched, "results": results}

# Streamlit UI
st.set_page_config(page_title="Web Plagiarism Checker", layout="centered")
st.title("🌐 Plagiarism Checker (Google Custom Search)")

st.markdown("""
Upload a `.txt`, `.pdf` or `.docx` file or paste text.  
This tool checks small chunks of the text against Google Custom Search results (programmable search).
""")

col1, col2 = st.columns(2)
with col1:
    mode = st.radio("Input type:", ["Paste text", "Upload file"])
with col2:
    max_checks = st.slider("Number of sentence checks (speed vs thoroughness)", 1, 10, 5)

text = ""
if mode == "Paste text":
    text = st.text_area("Paste your text here:", height=250)
else:
    uploaded = st.file_uploader("Upload file (.txt/.pdf/.docx)", type=["txt","pdf","docx"])
    if uploaded:
        text = extract_text_from_file(uploaded)
        st.success("File text extracted. Preview (first 500 chars):")
        st.write(text[:500] + ("..." if len(text)>500 else ""))

if st.button("Check plagiarism"):
    if not text or not text.strip():
        st.warning("Provide text or upload a file first.")
    else:
        st.info("Checking online sources now (may take a few seconds)...")
        out = check_plagiarism_text(text, max_checks=max_checks)
        if out.get("status") == "error":
            st.error("Error while searching: " + out.get("message"))
        elif out.get("status") == "no_text":
            st.warning(out.get("message"))
        else:
            if out.get("any_matched"):
                st.error("⚠️ Plagiarism detected (one or more chunks matched online).")
                st.subheader("Matched chunks and sources")
                for r in out["results"]:
                    if r["matched"]:
                        st.markdown(f"**Sentence:** {r['sentence'][:300]}...")
                        for m in r["matches"]:
                            st.markdown(f"- [{m['title']}]({m['link']})")
                            st.caption(m.get("snippet","")[:300])
                        st.write("---")
            else:
                st.success("✅ No plagiarism detected (no significant matches found).")

st.markdown("---")
st.caption("Notes: This is a heuristic check using Google Custom Search; use higher 'Number of sentence checks' for better coverage, but watch API quota.")
