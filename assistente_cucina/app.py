import streamlit as st
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.set_page_config(page_title="AI Kitchen Agent", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "data_extracted" not in st.session_state:
    st.session_state.data_extracted = {"ingredienti": [], "preferenze": [], "vincoli_salute": []}

SYSTEM_PROMPT = """
Sei un assistente intelligente per la cucina. 
REGOLE DI PIANIFICAZIONE (Cap. 6):
1. FASE RACCOLTA: Chiedi ingredienti, quantità e scadenze.
2. ESTRAZIONE: Aggiorna sempre il JSON con i nuovi dati.
3. OUTPUT RICETTE: Solo quando hai dati sufficienti, proponi ESATTAMENTE 3 ricette complete (nome, tempo, ingredienti, preparazione).
4. FORMATO: Risposta naturale + separatore '---JSON---' + oggetto JSON.
"""

st.title("👨‍🍳 Assistente Smart Kitchen (Groq Llama-3.1)")

with st.sidebar:
    st.header("📊 Sidebar Informativa")
    st.write("Dati estratti in tempo reale:")
    st.json(st.session_state.data_extracted)
    if st.button("Reset Conversazione"):
        st.session_state.messages = []
        st.session_state.data_extracted = {"ingredienti": [], "preferenze": [], "vincoli_salute": []}
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Cosa c'è in frigo?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        msg_history = [{"role": "system", "content": SYSTEM_PROMPT}] + \
                      [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        # MODELLO AGGIORNATO QUI: llama-3.1-8b-instant
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=msg_history,
            temperature=0.7
        )
        
        res_text = response.choices[0].message.content
        if "---JSON---" in res_text:
            parts = res_text.split("---JSON---")
            ans, js = parts[0].strip(), parts[1].strip()
            try: st.session_state.data_extracted = json.loads(js)
            except: pass
        else: ans = res_text
        
        st.markdown(ans)
        st.session_state.messages.append({"role": "assistant", "content": ans})
        st.rerun()
