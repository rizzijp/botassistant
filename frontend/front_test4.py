import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
import os
import uuid
import streamlit.components.v1 as components

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Data Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- VARIABLES DE ENTORNO ---
DEFAULT_API_URL = "http://127.0.0.1:8000/api/ask" 
#DEFAULT_API_URL = "https://botassistant-api.onrender.com/api/ask" 
API_URL = os.getenv("BACKEND_URL", DEFAULT_API_URL)
DEFAULT_USER_ID = 999 

# --- GESTIÓN DE SESIÓN ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# --- CSS: OPTIMIZACIÓN PARA LAPTOP 13" (NO SCROLL) ---
st.markdown("""
    <style>
    /* 1. Eliminar Headers/Footers y Padding excesivo */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Padding mínimo para aprovechar cada pixel de la pantalla */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100%;
    }

    /* 2. Input Flotante Compacto */
    .stChatInput {
        position: fixed !important;
        bottom: 10px !important;
        right: 2rem !important;
        width: 23% !important; /* Ajustado al ancho de la columna derecha */
        z-index: 1000 !important;
        background-color: white;
        padding-bottom: 0px !important;
    }
    
    /* Ajuste para que el input no se vea gigante */
    .stChatInput input {
        font-size: 14px !important;
        padding: 8px !important;
    }

    /* 3. Métricas Compactas */
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem !important; /* Números más pequeños */
    }
    
    /* 4. Separador vertical sutil */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        border-left: 1px solid #eee;
        padding-left: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- JAVASCRIPT: AUTO-SCROLL ---
def scroll_to_bottom():
    js = f"""
    <script>
        function scrollDown() {{
            var chatContainer = window.parent.document.querySelector('.stChatMessageContainer');
            if (chatContainer) {{
                var scrollers = window.parent.document.querySelectorAll('.stVerticalBlockBorderWrapper');
                if (scrollers.length > 0) {{
                    var lastScroller = scrollers[scrollers.length - 1];
                    lastScroller.scrollTop = lastScroller.scrollHeight; 
                }}
            }}
        }}
        setTimeout(scrollDown, 300);
    </script>
    """
    components.html(js, height=0, width=0)

# --- ESTADO ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "latest_response" not in st.session_state:
    st.session_state.latest_response = None
if "current_viz_type" not in st.session_state:
    st.session_state.current_viz_type = "table"

# --- FUNCIONES ---
def format_sql_query(sql_text):
    if not sql_text: return ""
    keywords = ["SELECT", "FROM", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", 
                "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "AND", "OR"]
    formatted_sql = sql_text
    for kw in keywords:
        pattern = re.compile(f"\\b{kw}\\b", re.IGNORECASE)
        formatted_sql = pattern.sub(f"\n{kw.upper()}", formatted_sql)
    return formatted_sql.strip()

# AHORA ACEPTA MODEL_NAME
def get_api_response(message_text, model_name):
    payload = {
        "user_id": DEFAULT_USER_ID,
        "session_id": st.session_state.session_id,
        "message": message_text,
        "model": model_name 
    }
    try:
        response = requests.post(API_URL, json=payload)
        try:
            return response.json()
        except:
            response.raise_for_status()
            return {"error": "Error sin respuesta JSON"}
    except Exception as e:
        return {"error": str(e)}

def render_visualization(data, viz_type, title, columns):
    df = pd.DataFrame(data)
    
    VIZ_HEIGHT = 450 

    if df.empty:
        st.info("Sin datos numéricos.")
        return

    for col in df.columns:
        try: df[col] = pd.to_numeric(df[col])
        except: pass

    x_col = columns[0] if columns else df.columns[0]
    y_col = columns[-1] if columns else df.columns[-1]
    if len(df.columns) > 1 and x_col == y_col: y_col = df.columns[1]

    if x_col in ['year', 'month', 'day', 'sale_timestamp', 'sale_date', 'dia']:
        try: df = df.sort_values(by=x_col, ascending=True)
        except: pass

    try:
        if viz_type == "number":
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                val = df.iloc[0][y_col] if not df.empty else 0
                st.metric(label="Resultado", value=f"{val:,.2f}" if isinstance(val, (int, float)) else str(val))
        
        elif viz_type == "table":
            st.dataframe(df.style.format(precision=2), use_container_width=True, height=VIZ_HEIGHT)
        
        elif viz_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, title=title, text_auto='.2s')
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=VIZ_HEIGHT)
            st.plotly_chart(fig, use_container_width=True)
        
        elif viz_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=title, markers=True)
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=VIZ_HEIGHT)
            st.plotly_chart(fig, use_container_width=True)
        
        elif viz_type == "pie":
            if len(df.columns) >= 2:
                fig = px.pie(df, names=x_col, values=y_col, title=title)
                fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=VIZ_HEIGHT)
                st.plotly_chart(fig, use_container_width=True)
            else: 
                st.warning("Datos insuficientes.")
        else:
            st.dataframe(df, height=VIZ_HEIGHT)
            
    except Exception as e:
        st.error(f"Error visual: {e}")

# --- LAYOUT PRINCIPAL (75% Viz - 25% Chat) ---
col_viz, col_chat = st.columns([3, 1])

# --- COLUMNA DERECHA: CHAT ---
with col_chat:
    # 1. Cabecera y Selector en línea
    c_head, c_sel = st.columns([1, 1])
    
    with c_head:
        st.markdown("#### 💬 Chat")
        
    with c_sel:
        # SELECTOR DE MODELO VISIBLE
        selected_model = st.selectbox(
            "Modelo IA", 
            options=["llama-3", "llama-fast"],
            index=0,
            label_visibility="collapsed",
            help="Elige entre precisión (llama-3) o velocidad (llama-fast)"
        )

    # Caption informativo
    if selected_model == "llama-3":
        st.caption("🧠 Modelo: Llama-3 (70b) - Más preciso")
    else:
        st.caption("⚡ Modelo: Llama-Fast (8b) - Más rápido")
    
    # 📏 ALTURA FIJA REAJUSTADA (500px)
    chat_container = st.container(height=500)
    
    with chat_container:
        if not st.session_state.messages:
            st.info(f"¡Hola! Estoy usando **{selected_model}**. Pregunta sobre tus datos.")
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        st.markdown('<div style="height: 50px;"></div>', unsafe_allow_html=True)

# --- COLUMNA IZQUIERDA: VISUALIZACIÓN ---
with col_viz:
    if st.session_state.latest_response:
        resp = st.session_state.latest_response
        
        # Header Compacto
        c1, c2 = st.columns([4, 1])
        with c1: 
            st.markdown(f"### {resp.get('viz_title', 'Resultados')}")
            with c2: 
                opciones_validas = ["table", "bar", "line", "pie", "number"]
                
                # 1. Recuperar tipo del backend, si viene "text" o nulo, forzamos a "table"
                backend_viz = resp.get("tipo_grafica", "table")
                if backend_viz not in opciones_validas:
                    backend_viz = "table"

                # 2. Saneamiento del estado
                if st.session_state.current_viz_type is None or st.session_state.current_viz_type not in opciones_validas:
                    st.session_state.current_viz_type = backend_viz

                # 3. Selector seguro
                new_viz = st.selectbox(
                    "Vista", 
                    opciones_validas, 
                    index=opciones_validas.index(st.session_state.current_viz_type),
                    label_visibility="collapsed",
                    key="viz_selector_main_unique"
                )
                
                # 4. Actualizar estado
                if new_viz != st.session_state.current_viz_type:
                    st.session_state.current_viz_type = new_viz
                    st.rerun()
        
        # Renderizado
        render_visualization(
            resp.get("datos", []), 
            st.session_state.current_viz_type, 
            "", 
            resp.get("columnas", [])
        )
        
        # Expander para SQL
        sql_gen = resp.get("sql_generado")
        if sql_gen:
            with st.expander("🛠️ SQL", expanded=False):
                st.code(format_sql_query(sql_gen), language="sql")
    else:
        st.markdown("<div style='text-align: center; margin-top: 150px; color: #ccc;'><h1>📊</h1><h3>Tu Data Dashboard</h3></div>", unsafe_allow_html=True)

# --- INPUT (FIXED BOTTOM RIGHT) ---
prompt = st.chat_input("Escribe tu consulta...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Pasamos el modelo seleccionado a la API
    with st.spinner(f"Consultando a {selected_model}..."):
        resp = get_api_response(prompt, selected_model)
    
    if resp:
        st.session_state.latest_response = resp
        st.session_state.current_viz_type = resp.get("tipo_grafica", "table")
        
        bot_msg = resp.get("mensaje") 
        if not bot_msg: bot_msg = "Datos recibidos."
        
        st.session_state.messages.append({"role": "assistant", "content": bot_msg})
    else:
        st.session_state.messages.append({"role": "assistant", "content": "❌ Error de conexión."})
    
    scroll_to_bottom()
    
    st.rerun()