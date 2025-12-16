import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import re
import os
import uuid

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Data Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- VARIABLES DE ENTORNO ---
# IMPORTANTE: Cambia esta URL por la URL real de tu proyecto en Render
# Debe terminar en /api/ask
DEFAULT_API_URL = "https://botassistant-api.onrender.com/api/ask" 

# Intenta leer de variable de entorno, si no usa la default
API_URL = os.getenv("BACKEND_URL", DEFAULT_API_URL)
DEFAULT_USER_ID = 999 

# --- GESTIÓN DE SESIÓN ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# --- ESTILOS CSS (FIX SCROLL) ---
st.markdown("""
    <style>
    /* 1. Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 2. Layout Principal */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
    }

    /* 3. Input Flotante */
    .stChatInput {
        position: fixed !important;
        bottom: 0px !important;
        right: 20px !important;
        width: 24% !important;
        z-index: 999 !important;
        background-color: white;
    }

    /* 4. Métricas y Tablas */
    .stMetric {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 10px;
        text-align: center;
    }
    
    /* 5. Separador vertical */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        border-left: 1px solid #ddd;
        padding-left: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

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
                "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT"]
    formatted_sql = sql_text
    for kw in keywords:
        pattern = re.compile(f"\\b{kw}\\b", re.IGNORECASE)
        formatted_sql = pattern.sub(f"\n{kw.upper()}", formatted_sql)
    return formatted_sql.strip()

def get_api_response(message_text):
    # ADAPTACIÓN: El backend espera 'message', 'session_id', 'user_id', 'model'
    payload = {
        "user_id": DEFAULT_USER_ID,
        "session_id": st.session_state.session_id,
        "message": message_text,  # Antes era 'question'
        "model": "llama-3"       # Opcional, pero recomendado enviar
    }
    
    try:
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def render_visualization(data, viz_type, title, columns):
    df = pd.DataFrame(data)
    
    if df.empty:
        st.info("La consulta no retornó datos numéricos para graficar.")
        return

    # Limpieza tipos
    for col in df.columns:
        try: df[col] = pd.to_numeric(df[col])
        except: pass

    # Definición de Ejes
    # Si el backend nos da columnas explícitas, las usamos
    x_col = columns[0] if columns else df.columns[0]
    y_col = columns[-1] if columns else df.columns[-1]
    
    # Si solo hay 1 columna, no podemos hacer X vs Y, duplicamos
    if len(df.columns) > 1 and x_col == y_col: 
        y_col = df.columns[1]

    # Ordenar tiempo si detectamos columnas de fecha
    if x_col in ['year', 'month', 'day', 'sale_timestamp', 'sale_date']:
        try:
            df = df.sort_values(by=x_col, ascending=True)
        except:
            pass

    try:
        if viz_type == "number":
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                # Tomamos el primer valor de la primera columna numérica que encontremos
                val = df.iloc[0][y_col] if not df.empty else 0
                st.metric(label="Resultado", value=f"{val:,.2f}" if isinstance(val, (int, float)) else str(val))
        
        elif viz_type == "table":
            st.dataframe(df.style.format(precision=2), use_container_width=True, height=500)
        
        elif viz_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, title=title, text_auto='.2s')
            st.plotly_chart(fig, use_container_width=True)
        
        elif viz_type == "line":
            fig = px.line(df, x=x_col, y=y_col, title=title, markers=True)
            st.plotly_chart(fig, use_container_width=True)
        
        elif viz_type == "pie":
            if len(df.columns) >= 2:
                fig = px.pie(df, names=x_col, values=y_col, title=title)
                st.plotly_chart(fig, use_container_width=True)
            else: 
                st.warning("Datos insuficientes para Pie chart.")
        else:
            st.dataframe(df)
            
    except Exception as e:
        st.error(f"Error visualizando datos: {e}")

# --- LAYOUT ---
col_viz, col_chat = st.columns([3, 1])

# COLUMNA DERECHA: CHAT
with col_chat:
    st.subheader("💬 Chat")
    
    chat_container = st.container(height=600)
    
    with chat_container:
        if not st.session_state.messages:
            st.info("¡Hola! Pregúntame sobre ventas, empleados o productos.")
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # Espacio para evitar superposición con input
        st.markdown('<div style="height: 100px;"></div>', unsafe_allow_html=True)

# COLUMNA IZQUIERDA: VISUALIZACIÓN
with col_viz:
    if st.session_state.latest_response:
        resp = st.session_state.latest_response
        
        # Título y Selector
        c1, c2 = st.columns([3, 1])
        with c1: 
            st.title("Resultados")
        with c2: 
            # Permitir cambiar el gráfico manualmente
            # Mapeamos 'tipo_grafica' del backend a los tipos de Streamlit
            backend_viz = resp.get("tipo_grafica", "table")
            if backend_viz not in ["table", "bar", "line", "pie", "number"]:
                backend_viz = "table"
                
            # Sincronizamos estado
            if st.session_state.current_viz_type is None:
                st.session_state.current_viz_type = backend_viz

            new_viz = st.selectbox(
                "Gráfico", 
                ["table", "bar", "line", "pie", "number"], 
                index=["table", "bar", "line", "pie", "number"].index(st.session_state.current_viz_type),
                label_visibility="collapsed"
            )
            
            if new_viz != st.session_state.current_viz_type:
                st.session_state.current_viz_type = new_viz
                st.rerun()
        
        st.divider()
        
        # Renderizado Principal
        # ADAPTACIÓN: Claves del backend ('datos', 'columnas')
        render_visualization(
            resp.get("datos", []), 
            st.session_state.current_viz_type, 
            "", 
            resp.get("columnas", [])
        )
        
        st.write("")
        # ADAPTACIÓN: Clave backend 'sql_generado'
        sql_gen = resp.get("sql_generado")
        if sql_gen:
            with st.expander("🛠️ Ver SQL Generado"):
                st.code(format_sql_query(sql_gen), language="sql")
    else:
        st.markdown("<h3 style='text-align: center; margin-top: 20%; color: #aaa;'>⬅️ Escribe tu consulta a la derecha para ver los datos</h3>", unsafe_allow_html=True)

# INPUT FLOTANTE
prompt = st.chat_input("Ej: Ventas totales por categoria...")

if prompt:
    # 1. Mostrar mensaje usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 2. Llamada a API
    with st.spinner("Analizando datos..."):
        resp = get_api_response(prompt)
    
    # 3. Procesar Respuesta
    if resp and "error" not in resp:
        st.session_state.latest_response = resp
        # Actualizamos el tipo de gráfica con lo que diga el backend
        st.session_state.current_viz_type = resp.get("tipo_grafica", "table")
        
        # Mensaje del Asistente (Viene del backend en el campo 'mensaje')
        bot_msg = resp.get("mensaje", "Aquí tienes los datos.")
        
        st.session_state.messages.append({"role": "assistant", "content": bot_msg})
    else:
        err = resp.get("error", "Error desconocido") if resp else "Sin conexión"
        st.session_state.messages.append({"role": "assistant", "content": f"❌ Error: {err}"})
        
    st.rerun()