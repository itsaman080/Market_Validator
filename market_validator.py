import os
import requests
import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---- Config ----
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("GOOGLE_CSE_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---- Models ----
embedder = SentenceTransformer("all-MiniLM-L6-v2")
llm_client = Groq(api_key=GROQ_API_KEY)

# ---- Google Search ----
def google_search(query, num_results=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": CSE_ID, "q": query, "num": num_results}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("items", [])

# ---- Cosine Similarity ----
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# ---- Competitor Search ----
def check_idea(user_idea, top_n=5):
    idea_embedding = embedder.encode(user_idea)
    results = google_search(user_idea)
    if not results:
        return []

    matches = []
    for item in results:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")
        combined_text = f"{title}. {snippet}"

        try:
            result_embedding = embedder.encode(combined_text)
            similarity = cosine_similarity(idea_embedding, result_embedding)
            matches.append((similarity, title, link, snippet))
        except Exception as e:
            continue

    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[:top_n]

# ---- LLM Summary ----
def summarize_results(user_idea, matches):
    context = "\n".join(
        [f"{i+1}. {m[1]} ({m[2]})\n{m[3]}" for i, m in enumerate(matches)]
    )
    prompt = f"""
You are a startup consultant. A founder has this idea: "{user_idea}"

Here are the top competitors from the market:
{context}

Analyze:
1. Which competitors are most similar to the idea?
2. What market gap still exists?
3. Is this idea unique or crowded?

Give a clear, concise report.
    """
    chat_completion = llm_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return chat_completion.choices[0].message.content

# ---- STREAMLIT UI ----
st.set_page_config(page_title="Market Validator", layout="wide")
st.title("💡 AI Market Validator Tool")
st.write("Enter your startup or business idea to see top competitors and market insights.")

user_idea = st.text_input("Enter your startup/business idea:")

if st.button("Check Market"):
    if user_idea.strip() == "":
        st.warning("Please enter an idea!")
    else:
        with st.spinner("🔎 Searching for similar businesses..."):
            competitors = check_idea(user_idea)

        if not competitors:
            st.error("❌ No results found.")
        else:
            st.subheader("✅ Top Similar Businesses:")
            for i, (score, title, link, snippet) in enumerate(competitors, 1):
                st.markdown(f"**{i}. [{title}]({link})**")
                st.markdown(f"*Similarity Score:* {score:.2f}")
                st.markdown(f"{snippet}\n")

            st.subheader("🧠 Market Validation Report:")
            with st.spinner("Generating AI market analysis..."):
                report = summarize_results(user_idea, competitors)
            st.write(report)
