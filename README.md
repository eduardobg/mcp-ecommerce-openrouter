# MCP Ecommerce OpenRouter

App de Streamlit que expone un agente multiagente (LangGraph) de analitica
e-commerce, con capacidades de negocio publicadas por un servidor MCP
(FastMCP) y un modelo servido via OpenRouter.

Adaptacion del notebook de clase *"MCP → LangChain → LangGraph → Multiagentes
en Google Colab"* (Sesion 4, curso de integracion de LLM), conservando el
patron **supervisor + especialistas**.

## Arquitectura

```
Usuario
  |
Streamlit (app.py)
  |
LangGraph: supervisor -> {data_agent | service_agent | business_agent}
  |
ChatOpenAI configurado contra OpenRouter
  |
Tools adaptadas desde MCP (langchain-mcp-adapters)
  |
FastMCP Server por HTTP (subprocess, mcp_server/server.py)
  |
SQLite: tabla orders (generada desde data/ecommerce_orders_dataset.csv)
```

| Agente | Responsabilidad | Tools autorizadas |
|---|---|---|
| `data_agent` | Clientes, consumo, ordenes y categorias | `buscar_clientes`, `resumen_consumo_cliente`, `ordenes_recientes_cliente`, `consumo_por_categoria` |
| `service_agent` | Experiencia de servicio | `buscar_clientes`, `metricas_experiencia_cliente` |
| `business_agent` | Analisis agregado del negocio | `ranking_ventas_por_pais` |
| `supervisor` | Enrutamiento y termino del flujo | No ejecuta tools |

Cada tool MCP encapsula su propia consulta SQL parametrizada: el LLM nunca ve
ni redacta SQL libre.

## Requisitos

- Python 3.11+
- Una API key de [OpenRouter](https://openrouter.ai/) (las variantes `:free`
  no tienen costo pero requieren cuenta y pueden tener limites de tasa).

## Instalacion y ejecucion local

```bash
python -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configura la API key con una de estas opciones:
export OPENROUTER_API_KEY="sk-or-v1-..."          # variable de entorno
# o copia .streamlit/secrets.toml.example a .streamlit/secrets.toml y edítalo
# o simplemente pégala en el campo de la barra lateral al abrir la app

streamlit run app.py
```

Al iniciar, la app:
1. Construye `data/ecommerce_demo.db` desde el CSV si no existe (o esta
   desactualizado).
2. Lanza el servidor FastMCP como subproceso en `127.0.0.1:8000/mcp`.
3. Descubre las tools MCP y arma el grafo supervisor + especialistas.

## Uso

Escribe preguntas de negocio en el chat, por ejemplo:

- "¿CUST007322 tiene señales de mala experiencia?"
- "¿Qué países vendieron más en 2023?"
- "Resume el consumo de CUST007322 y evalúa su experiencia de servicio."

Cada respuesta incluye una traza expandible con las decisiones del supervisor,
las tools invocadas y lo que devolvió MCP.

El botón **"Validar modelo"** en la barra lateral reproduce la comprobación
del notebook contra el catálogo de OpenRouter (existencia, precio y soporte
de tool calling) antes de usarlo.

## Estructura del repo

```
mcp-ecommerce-openrouter/
├── app.py                  # entrypoint Streamlit
├── app/
│   ├── config.py            # paths y defaults de OpenRouter/MCP
│   ├── db.py                 # construccion idempotente de SQLite desde el CSV
│   ├── mcp_runtime.py         # arranque del subprocess MCP + descubrimiento de tools
│   └── graph.py               # grafo LangGraph: supervisor + especialistas
├── mcp_server/
│   └── server.py             # servidor FastMCP con las 6 tools de negocio
├── data/
│   └── ecommerce_orders_dataset.csv
└── requirements.txt
```

## Creditos

Basado en el material de clase de la Sesion 4 (LangGraph como capa de
orquestacion), curso *Certified AI LLM Solution Architect* — BSG Institute.
