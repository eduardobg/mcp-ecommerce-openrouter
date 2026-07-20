"""
Grafo multiagente: supervisor + especialistas (data_agent, service_agent,
business_agent). Traduccion directa de los Pasos 18-20 del notebook, con las
tools MCP repartidas bajo minimo privilegio.
"""

from typing import Annotated, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field


class MultiAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    next_agent: str


class RouteDecision(BaseModel):
    next_agent: Literal["data_agent", "service_agent", "business_agent", "FINISH"] = Field(
        description="Siguiente especialista o FINISH cuando exista una respuesta suficiente."
    )


SUPERVISOR_PROMPT = """
Eres el supervisor de un equipo de analitica e-commerce.

Decide el siguiente paso segun el historial de mensajes:
- data_agent: clientes, consumo, ordenes recientes y categorias.
- service_agent: rating, devoluciones y desempeno de entrega.
- business_agent: rankings agregados de ventas y utilidad por pais.
- FINISH: solo si un especialista ya genero una respuesta suficiente para el usuario.

No contestes directamente la consulta ni ejecutes tools. Puedes enrutar a mas
de un especialista en secuencia si la pregunta lo exige.
"""

DATA_PROMPT = """
Eres data_agent. Te especializas en clientes, consumo, ordenes y categorias.
Usa exclusivamente tus tools asignadas para afirmaciones basadas en datos.
Responde en espanol de forma concisa y con evidencia.
"""

SERVICE_PROMPT = """
Eres service_agent. Te especializas en experiencia de servicio: devoluciones,
rating y desempeno de entrega.
Usa exclusivamente tus tools asignadas para afirmaciones basadas en datos.
Responde en espanol de forma concisa y con evidencia.
"""

BUSINESS_PROMPT = """
Eres business_agent. Te especializas en analisis agregado de negocio por pais.
Usa exclusivamente tus tools asignadas para afirmaciones basadas en datos.
Responde en espanol de forma concisa y con evidencia.
"""


def _build_supervisor_node(llm: BaseChatModel):
    supervisor_llm = llm.with_structured_output(RouteDecision, method="function_calling")

    async def supervisor_node(state: MultiAgentState) -> dict:
        decision = await supervisor_llm.ainvoke(
            [
                {"role": "system", "content": SUPERVISOR_PROMPT},
                *state["messages"],
            ]
        )
        return {"next_agent": decision.next_agent}

    return supervisor_node


def _route_from_supervisor(state: MultiAgentState) -> str:
    return state["next_agent"]


def _build_specialist_node(llm: BaseChatModel, prompt: str, allowed_tools: list):
    specialist_llm = llm.bind_tools(allowed_tools)

    async def specialist_node(state: MultiAgentState) -> dict:
        response = await specialist_llm.ainvoke(
            [
                {"role": "system", "content": prompt},
                *state["messages"],
            ]
        )
        return {"messages": [response]}

    return specialist_node


def build_multiagent_graph(llm: BaseChatModel, tools_por_nombre: dict):
    """
    Construye y compila el StateGraph supervisor + especialistas.

    Devuelve (graph, memory) -- memory es el MemorySaver usado como
    checkpointer, util para inspeccionar o reiniciar el estado si hace falta.
    """
    data_tools = [
        tools_por_nombre["buscar_clientes"],
        tools_por_nombre["resumen_consumo_cliente"],
        tools_por_nombre["ordenes_recientes_cliente"],
        tools_por_nombre["consumo_por_categoria"],
    ]
    service_tools = [
        tools_por_nombre["buscar_clientes"],
        tools_por_nombre["metricas_experiencia_cliente"],
    ]
    business_tools = [
        tools_por_nombre["ranking_ventas_por_pais"],
    ]

    builder = StateGraph(MultiAgentState)

    builder.add_node("supervisor", _build_supervisor_node(llm))

    builder.add_node("data_agent", _build_specialist_node(llm, DATA_PROMPT, data_tools))
    builder.add_node("data_tools", ToolNode(data_tools))

    builder.add_node("service_agent", _build_specialist_node(llm, SERVICE_PROMPT, service_tools))
    builder.add_node("service_tools", ToolNode(service_tools))

    builder.add_node("business_agent", _build_specialist_node(llm, BUSINESS_PROMPT, business_tools))
    builder.add_node("business_tools", ToolNode(business_tools))

    builder.add_edge(START, "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "data_agent": "data_agent",
            "service_agent": "service_agent",
            "business_agent": "business_agent",
            "FINISH": END,
        },
    )

    builder.add_conditional_edges(
        "data_agent", tools_condition, {"tools": "data_tools", "__end__": "supervisor"}
    )
    builder.add_edge("data_tools", "data_agent")

    builder.add_conditional_edges(
        "service_agent", tools_condition, {"tools": "service_tools", "__end__": "supervisor"}
    )
    builder.add_edge("service_tools", "service_agent")

    builder.add_conditional_edges(
        "business_agent", tools_condition, {"tools": "business_tools", "__end__": "supervisor"}
    )
    builder.add_edge("business_tools", "business_agent")

    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    return graph, memory
