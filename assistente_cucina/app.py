import streamlit as st
import os
import json
from groq import Groq
from dotenv import load_dotenv
import urllib.parse

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.set_page_config(page_title="Multi-Agent Kitchen", layout="wide")

# 1. GESTIONE STATO E TOKEN (Richiesta 3)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "data_extracted" not in st.session_state:
    st.session_state.data_extracted = {"ingredienti": [], "vincoli": [], "image_prompt": ""}
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0

TOKEN_LIMIT = 15000  # Soglia di sicurezza per il piano gratuito

# 2. DEFINIZIONE PROMPT MULTI-AGENTE (Richiesta 2)
CHEF_PROMPT = """
Sei lo CHEF. Il tuo compito è generare 3 ricette basandoti ESATTAMENTE sui dati forniti.
Rispetta dosi, scadenze e vincoli di salute (es. no sale).
Dopo le ricette, scrivi '---JSON_DATA---' e il JSON aggiornato con un 'image_prompt' per la ricetta migliore.
"""

CRITIC_PROMPT = """
Sei il CRITICO GASTRONOMICO. Il tuo compito è verificare che lo CHEF non abbia fatto errori.
Controlla:
1. Ha usato gli ingredienti corretti?
2. Ha rispettato i vincoli di salute (es. se l'utente ha detto 'niente sale', lo Chef ha messo il sale?)?
3. Le quantità sono sensate?

Rispondi SOLO in questo formato:
ESITO: [APPROVATO oppure RIFIUTATO]
MOTIVAZIONE: [Spiega perché, se hai rifiutato]
"""

st.title("👨‍🍳 Sistema Multi-Agente: Chef & Critico")

# SIDEBAR POTENZIATA
with st.sidebar:
    st.header("📊 Monitoraggio Sistema")
    
    # Visualizzazione Token (Richiesta 3)
    token_perc = (st.session_state.total_tokens / TOKEN_LIMIT)
    st.metric("Token Utilizzati", f"{st.session_state.total_tokens} / {TOKEN_LIMIT}")
    st.progress(min(token_perc, 1.0))
    
    if st.session_state.total_tokens > TOKEN_LIMIT * 0.9:
        st.warning("⚠️ Attenzione: Sei vicino al limite di token!")

    st.divider()
    st.subheader("🛒 Dispensa & Vincoli")
    st.json(st.session_state.data_extracted)
    
    if st.button("Reset Totale"):
        st.session_state.messages = []
        st.session_state.total_tokens = 0
        st.session_state.data_extracted = {"ingredienti": [], "vincoli": [], "image_prompt": ""}
        st.rerun()

# Logica Chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Cosa cuciniamo?"):
    if st.session_state.total_tokens >= TOKEN_LIMIT:
        st.error("ERRORE: Limite token raggiunto. Impossibile continuare la sessione.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        # In questo passo abbiamo impostato la struttura, nel prossimo 
        # implementeremo il ciclo di validazione Chef -> Critico.
        st.info("Struttura pronta. Clicca 'fatto' per attivare il ciclo Multi-Agente.")

    with st.chat_message("assistant"):
        # --- FASE 1: CHIAMATA ALLO CHEF ---
        msg_chef = [{"role": "system", "content": CHEF_PROMPT}] + \
                   [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        
        res_chef = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=msg_chef,
            temperature=0.7
        )
        
        chef_text = res_chef.choices[0].message.content
        st.session_state.total_tokens += res_chef.usage.total_tokens # Aggiorna token (Richiesta 3)

        # --- FASE 2: IL CRITICO VALUTA (Richiesta 2) ---
        msg_critic = [
            {"role": "system", "content": CRITIC_PROMPT},
            {"role": "user", "content": f"Ecco la proposta dello Chef:\n{chef_text}\n\nRicorda i vincoli: {st.session_state.data_extracted}"}
        ]
        
        res_critic = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=msg_critic,
            temperature=0.1
        )
        
        critic_feedback = res_critic.choices[0].message.content
        st.session_state.total_tokens += res_critic.usage.total_tokens # Aggiorna token

        # Mostriamo il processo di "pensiero" del sistema (Reflection)
        with st.expander("🔍 Log di Validazione Multi-Agente"):
            st.write("**Proposta Chef:**", chef_text)
            st.write("**Verdetto Critico:**", critic_feedback)

        # --- FASE 3: ESITO FINALE ---
        if "APPROVATO" in critic_feedback:
            # Pulizia JSON e visualizzazione
            if "---JSON_DATA---" in chef_text:
                parts = chef_text.split("---JSON_DATA---")
                final_answer = parts[0].strip()
                try: st.session_state.data_extracted = json.loads(parts[1].strip())
                except: pass
            else:
                final_answer = chef_text
            
            st.success("✅ Ricetta approvata dal Critico!")
            st.markdown(final_answer)
            
            # Mostra immagine (Richiesta facoltativa precedente)
            p_img = st.session_state.data_extracted.get("image_prompt")
            if p_img:
                encoded = urllib.parse.quote(p_img)
                st.image(f"https://image.pollinations.ai/prompt/{encoded}?width=500&nologo=true")
            
            st.session_state.messages.append({"role": "assistant", "content": final_answer})
        else:
            error_msg = f"❌ Lo Chef ha commesso degli errori. Il Critico ha rifiutato: {critic_feedback}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})

        st.rerun()
