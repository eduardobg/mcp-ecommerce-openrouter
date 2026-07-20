"""
Entrypoint de Streamlit: analitica e-commerce via MCP + LangGraph multiagente.

Arquitectura (igual que el notebook de clase, Parte III):

    Usuario -> Streamlit -> LangGraph (supervisor + especialistas)
        -> ChatOpenAI contra OpenRouter -> tools MCP -> FastMCP (subprocess HTTP)
        -> SQLite (tabla orders)
"""

import asyncio
import uuid

import requests
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app import config, db, mcp_runtime
from app.graph import build_multiagent_graph

st.set_page_config(page_title="Ecommerce Analytics · MCP + LangGraph", page_icon="🛒", layout="wide")

db.build_database(config.CSV_PATH, config.DB_PATH)


@st.cache_resource(show_spinner="Iniciando servidor MCP...")
def get_mcp_runtime() -> mcp_runtime.McpRuntime:
    return mcp_runtime.ensure_running_and_discover()


@st.cache_resource(show_spinner="Construyendo grafo multiagente...")
def get_graph(model: str, api_key: str):
    runtime = get_mcp_runtime()
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=config.OPENROUTER_BASE_URL,
        default_headers=config.OPENROUTER_HEADERS,
        temperature=0,
    )
    graph, _memory = build_multiagent_graph(llm, runtime.tools_por_nombre)
    return graph


def validar_modelo(model: str) -> None:
    try:
        resp = requests.get(f"{config.OPENROUTER_BASE_URL}/models", timeout=30)
        resp.raise_for_status()
        modelos = resp.json().get("data", [])
        info = next((m for m in modelos if m.get("id") == model), None)
        if info is None:
            st.sidebar.error(f"'{model}' no aparece en el catalogo de OpenRouter.")
            return
        parametros = set(info.get("supported_parameters", []))
        soporta_tools = "tools" in parametros
        pricing = info.get("pricing", {})
        if soporta_tools:
            st.sidebar.success(
                f"{info.get('name', model)} encontrado. "
                f"Precio prompt/completion: {pricing.get('prompt')} / {pricing.get('completion')}. "
                "Soporta tools: si."
            )
        else:
            st.sidebar.error(
                f"{info.get('name', model)} no declara soporte de tool calling; "
                "este laboratorio lo requiere."
            )
    except requests.RequestException as error:
        st.sidebar.error(f"No fue posible consultar el catalogo de OpenRouter: {error}")


async def _run_and_trace(graph, pregunta: str, thread_id: str, status, trace_lines: list[str]) -> str:
    config_run = {"configurable": {"thread_id": thread_id}}

    async for update in graph.astream(
        {"messages": [HumanMessage(content=pregunta)]},
        config=config_run,
        stream_mode="updates",
    ):
        for node_name, state_update in update.items():
            if node_name == "supervisor" and "next_agent" in state_update:
                linea = f"🧭 Supervisor decide: `{state_update['next_agent']}`"
                trace_lines.append(linea)
                status.write(linea)

            for mensaje in state_update.get("messages", []):
                if isinstance(mensaje, AIMessage) and mensaje.tool_calls:
                    for llamada in mensaje.tool_calls:
                        linea = f"🧠 [{node_name}] solicita tool `{llamada['name']}` args=`{llamada['args']}`"
                        trace_lines.append(linea)
                        status.write(linea)
                elif isinstance(mensaje, ToolMessage):
                    vista = str(mensaje.content)[:400]
                    linea = f"⚡ MCP respondio: {vista}"
                    trace_lines.append(linea)
                    status.write(linea)
                elif isinstance(mensaje, AIMessage) and mensaje.content:
                    linea = f"📝 [{node_name}]: {str(mensaje.content)[:400]}"
                    trace_lines.append(linea)
                    status.write(linea)

    final_state = await graph.aget_state(config_run)
    return final_state.values["messages"][-1].content


# --- Sidebar: configuracion ---
st.sidebar.header("Configuracion OpenRouter")

default_key = config.get_openrouter_api_key() or ""
api_key = st.sidebar.text_input("OPENROUTER_API_KEY", value=default_key, type="password")
model = st.sidebar.text_input(
    "Modelo",
    value=config.DEFAULT_MODEL,
    help="Cualquier modelo del catalogo de OpenRouter que soporte tool calling.",
)

if st.sidebar.button("Validar modelo"):
    validar_modelo(model)

st.sidebar.divider()
st.sidebar.header("Servidor MCP")
mcp_status_placeholder = st.sidebar.empty()

if st.sidebar.button("Reiniciar servidor MCP"):
    try:
        get_mcp_runtime().stop()
    except Exception:
        pass
    get_mcp_runtime.clear()
    get_graph.clear()
    st.rerun()

try:
    runtime = get_mcp_runtime()
    if runtime.is_port_open():
        mcp_status_placeholder.success(f"🟢 Activo en {config.MCP_URL} ({len(runtime.tools)} tools)")
    else:
        mcp_status_placeholder.error("🔴 El servidor no responde en el puerto esperado.")
except Exception as error:
    mcp_status_placeholder.error(f"🔴 No se pudo iniciar el servidor MCP: {error}")
    st.stop()

st.sidebar.divider()
st.sidebar.markdown(
    """
    **Agentes especialistas**
    - `data_agent` → clientes, consumo, ordenes, categorias
    - `service_agent` → devoluciones, rating, entrega
    - `business_agent` → ranking de ventas por pais
    - `supervisor` → enruta, no ejecuta tools
    """
)

# --- Main: chat ---
st.title("🛒 Analitica E-commerce — MCP + LangGraph Multiagente")
st.caption("Supervisor + especialistas sobre tools MCP de solo lectura. Proveedor de modelo: OpenRouter.")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

for turno in st.session_state.messages:
    with st.chat_message(turno["role"]):
        st.markdown(turno["content"])
        if turno.get("trace"):
            with st.expander("Traza de orquestacion"):
                for linea in turno["trace"]:
                    st.markdown(linea)

pregunta = st.chat_input("Pregunta sobre clientes, servicio o ventas...")

if pregunta:
    if not api_key:
        st.error("Ingresa tu OPENROUTER_API_KEY en la barra lateral antes de continuar.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": pregunta, "trace": []})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        trace_lines: list[str] = []
        status = st.status("Orquestando agentes...", expanded=True)
        try:
            graph = get_graph(model, api_key)
            respuesta_final = asyncio.run(
                _run_and_trace(graph, pregunta, st.session_state.thread_id, status, trace_lines)
            )
            status.update(label="Orquestacion completa", state="complete")
            st.markdown(respuesta_final)
        except Exception as error:
            status.update(label="Error durante la orquestacion", state="error")
            respuesta_final = f"Ocurrio un error: {error}"
            st.error(respuesta_final)

        st.session_state.messages.append(
            {"role": "assistant", "content": respuesta_final, "trace": trace_lines}
        )
