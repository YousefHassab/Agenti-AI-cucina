import streamlit as st
import os
import json
from groq import Groq
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.set_page_config(page_title="AI Kitchen Multi-Agent", layout="wide")

# 1. INIZIALIZZAZIONE STATO
if "messages" not in st.session_state:
    st.session_state.messages = []
if "data_extracted" not in st.session_state:
    st.session_state.data_extracted = {"ingredienti": [], "vincoli": []}
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0

TOKEN_LIMIT = 15000

# 2. SIDEBAR (Monitoraggio e Strategia Anti-Blocco)
with st.sidebar:
    st.header("⚖️ Monitoraggio Risorse")
    st.metric("Token Consumati", f"{st.session_state.total_tokens} / {TOKEN_LIMIT}")
    
    progress = min(st.session_state.total_tokens / TOKEN_LIMIT, 1.0)
    st.progress(progress)
    
    if st.session_state.total_tokens >= TOKEN_LIMIT:
        st.error("🛑 LIMITE RAGGIUNTO: Il sistema è bloccato per esaurimento token.")

    st.divider()
    st.header("🗄️ Stato Dispensa")
    data = st.session_state.data_extracted
    
    # PROTEZIONE ANTI-CRASH: controlliamo che ogni ingrediente sia un dizionario
    for ing in data.get("ingredienti", []):
        if isinstance(ing, dict):
            st.write(f"🍴 {ing.get('nome', 'Sconosciuto')} ({ing.get('qta','?')})")
        else:
            st.write(f"🍴 {ing}") # Se è una stringa, la scriviamo così com'è
            
    for v in data.get("vincoli", []):
        st.error(f"🚫 {v}")
    
    if st.button("Reset Totale"):
        st.session_state.messages = []
        st.session_state.total_tokens = 0
        st.session_state.data_extracted = {"ingredienti": [], "vincoli": []}
        st.rerun()

# 3. PROMPT AGENTI
CHEF_PROMPT = "Sei lo CHEF. Proponi 3 ricette. Alla fine scrivi '---JSON---' e il JSON aggiornato con ingredienti, vincoli e un 'image_prompt'."
CRITIC_PROMPT = "Sei il CRITICO. Rispondi 'ESITO: APPROVATO' se la ricetta rispetta i vincoli, altrimenti 'ESITO: RIFIUTATO' con i motivi."

st.title("👨‍🍳 Multi-Agent Kitchen: Chef & Critico")

# Visualizzazione Chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

# 4. LOGICA DI CONTROLLO BLOCCANTE
if prompt := st.chat_input("Inserisci ingredienti o vincoli..."):
    if st.session_state.total_tokens >= TOKEN_LIMIT:
        # Se siamo fuori limite, mostriamo solo l'errore e non facciamo nulla
        st.error("❌ OPERAZIONE NEGATA: Limite di 15.000 token raggiunto. Reset necessario per continuare.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # CHIAMATA CHEF
                history = [{"role": "system", "content": CHEF_PROMPT}] + \
                          [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                
                res_chef = client.chat.completions.create(model="llama-3.1-8b-instant", messages=history)
                chef_out = res_chef.choices[0].message.content
                st.session_state.total_tokens += res_chef.usage.total_tokens

                # CHIAMATA CRITICO
                critic_in = [
                    {"role": "system", "content": CRITIC_PROMPT},
                    {"role": "user", "content": f"Ricetta Chef: {chef_out}\nVincoli attuali: {st.session_state.data_extracted}"}
                ]
                res_critic = client.chat.completions.create(model="llama-3.1-8b-instant", messages=critic_in)
                critic_out = res_critic.choices[0].message.content
                st.session_state.total_tokens += res_critic.usage.total_tokens

                with st.status("🧐 Validazione Critico...", expanded=False):
                    st.write(critic_out)

                # PULIZIA JSON
                if "---JSON---" in chef_out:
                    parts = chef_out.split("---JSON---")
                    final_text = parts[0].strip()
                    try: 
                        st.session_state.data_extracted = json.loads(parts[1].strip())
                    except: pass
                else:
                    final_text = chef_out

                if "APPROVATO" in critic_out:
                    st.success("✅ Approvato!")
                    st.markdown(final_text)
                    p_img = st.session_state.data_extracted.get("image_prompt")
                    if p_img:
                        st.image(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p_img)}?width=500")
                else:
                    st.error("❌ Rifiutato dal Critico!")
                    st.info(critic_out)
                
                st.session_state.messages.append({"role": "assistant", "content": final_text})
                st.rerun()

            except Exception as e:
                st.error(f"Si è verificato un errore durante l'elaborazione. Prova a resettare.")
