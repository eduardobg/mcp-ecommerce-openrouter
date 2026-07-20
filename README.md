# MCP Ecommerce OpenRouter

App de Streamlit que expone un agente multiagente (LangGraph) de analitica
e-commerce, con capacidades de negocio publicadas por un servidor MCP
(FastMCP) y un modelo servido via OpenRouter.

Adaptacion del notebook de clase *"MCP → LangChain → LangGraph → Multiagentes
en Google Colab"* (Sesion 4, curso de integracion de LLM), conservando el
patron **supervisor + especialistas**.

**🚀 Demo en vivo**: https://mcp-ecommerce-openrouter-rxnwtctxnnnvpexy5bqvvp.streamlit.app/
> Si alguna vez el link pide iniciar sesión en vez de abrir la app
> directamente, revisa que el acceso siga configurado como público desde el
> dashboard de [share.streamlit.io](https://share.streamlit.io) (App →
> Settings → Sharing).

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
- Una cuenta y API key de [OpenRouter](https://openrouter.ai/) (las variantes
  `:free` no tienen costo, pero requieren cuenta y pueden tener límites de
  capacidad — ver la sección de problemas comunes más abajo).

## Guía paso a paso

### 1. Crear el entorno virtual e instalar dependencias

```bash
python -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Obtener una API key de OpenRouter

1. Crea una cuenta en [openrouter.ai](https://openrouter.ai/).
2. Ve a **Settings → API Keys** ([openrouter.ai/settings/keys](https://openrouter.ai/settings/keys)) y genera una key nueva (empieza con `sk-or-v1-...`).
3. Los modelos `:free` no cobran, pero igual necesitas la key para autenticar las llamadas.

### 3. Configurar la API key en el proyecto

Elige **una** de estas tres formas (la app las busca en este orden):

```bash
# Opción A — variable de entorno (recomendada para uso local)
export OPENROUTER_API_KEY="sk-or-v1-..."          # En Windows (PowerShell): $env:OPENROUTER_API_KEY="sk-or-v1-..."

# Opción B — archivo de secretos de Streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# y edita ese archivo con tu key real (no se sube a git, ya está en .gitignore)

# Opción C — pegarla directamente en el campo "OPENROUTER_API_KEY" de la
# barra lateral al abrir la app (útil para probar rápido, pero hay que
# volver a pegarla cada vez que reinicies la app)
```

### 4. Elegir el modelo

El campo **"Modelo"** de la barra lateral trae por defecto
`nvidia/nemotron-3-ultra-550b-a55b:free`, pero puedes poner cualquier ID del
catálogo de OpenRouter que soporte *tool calling* (function calling), ya que
el agente necesita eso para usar las tools MCP.

**Problemas comunes al elegir modelo:**

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `ResourceExhausted: Worker local total request limit reached (32/32)` (error 502) | El proveedor detrás del modelo `:free` está saturado por demanda alta — es un límite de capacidad temporal, no un error del proyecto. | Cambia a otro modelo en la barra lateral y reintenta. Los modelos gratuitos más chicos suelen tener menos contención. |
| `'<modelo>' no aparece en el catálogo de OpenRouter` | El ID del modelo no existe o fue renombrado/descontinuado. | Verifica el ID exacto en [openrouter.ai/models](https://openrouter.ai/models) o prueba una alternativa de la lista de abajo. |
| `no declara soporte de tool calling` | El modelo elegido no soporta function/tool calling — el agente lo necesita para invocar las tools MCP. | Elige un modelo marcado con soporte de "tools" en el catálogo. |
| Respuestas muy lentas o con timeouts | Modelos gratuitos pueden tener latencia alta en horas pico. | Prueba de nuevo más tarde, o usa un modelo de pago si necesitas velocidad consistente. |

Alternativas gratuitas con soporte de tools que puedes pegar en el campo
"Modelo" (verificado en el catálogo de OpenRouter):

- `nvidia/nemotron-nano-9b-v2:free` — mismo proveedor que el default, modelo más chico, normalmente menos saturado.
- `openai/gpt-oss-20b:free`
- `google/gemma-4-26b-a4b-it:free`
- `google/gemma-4-31b-it:free`

Usa siempre el botón **"Validar modelo"** (paso 6) antes de preguntar, para
confirmar que el modelo elegido existe y soporta tools sin gastar una
llamada de chat en el intento.

### 5. Ejecutar la app

```bash
streamlit run app.py
```

Al iniciar, la app automáticamente:
1. Construye `data/ecommerce_demo.db` desde el CSV si no existe (o está
   desactualizado).
2. Lanza el servidor FastMCP como subproceso en `127.0.0.1:8000/mcp`.
3. Descubre las tools MCP y arma el grafo supervisor + especialistas.

La barra lateral muestra el estado del servidor MCP (🟢 activo / 🔴 con
problemas). Si necesitas reiniciarlo (por ejemplo, quedó colgado de una
corrida anterior), usa el botón **"Reiniciar servidor MCP"**.

### 6. Validar el modelo antes de preguntar

En la barra lateral, con la API key y el modelo ya configurados, presiona
**"Validar modelo"**. Esto reproduce la comprobación del notebook original
contra el catálogo de OpenRouter: confirma que el modelo existe, muestra su
precio prompt/completion, y verifica que soporte tool calling — antes de
gastar una llamada real de chat.

### 7. Hacer preguntas

Escribe preguntas de negocio en el chat. Ejemplos que ejercitan distintas
rutas del supervisor:

**Solo `data_agent`:**
- "¿Qué compró últimamente CUST007322?"
- "¿Cuáles son las categorías preferidas de CUST007322?"
- "Busca clientes Premium de Chile."

**Solo `service_agent`:**
- "¿CUST007322 tiene señales de mala experiencia?"
- "¿Cómo ha sido el desempeño de entrega para CUST007322?"

**Solo `business_agent`:**
- "¿Qué países vendieron más en 2023?"
- "¿Dónde se concentra la utilidad del negocio?"

**Cruzando varios agentes (supervisor enruta en secuencia):**
- "Resume el consumo de CUST007322 y evalúa su experiencia de servicio."
- "Busca clientes de Chile y analiza al que tenga mayor consumo."
- "Analiza el consumo de CUST007322 y dime si presenta señales de mala experiencia."

Cada respuesta incluye una traza expandible ("Traza de orquestación") con las
decisiones del supervisor, qué tool invocó cada especialista y qué devolvió
el servidor MCP.

## Despliegue en Streamlit Community Cloud (gratis)

El proyecto se puede alojar gratis en
[Streamlit Community Cloud](https://streamlit.io/cloud), que corre `app.py`
directo desde este repo de GitHub. No requiere tarjeta ni servidor propio.

### Pasos

1. Entra a [streamlit.io/cloud](https://streamlit.io/cloud) e inicia sesión
   con tu cuenta de GitHub (la misma cuenta `eduardobg`), autorizando el
   acceso — como el repo es **privado**, asegúrate de darle permiso explícito
   a Streamlit Cloud sobre este repositorio cuando te lo pida.
2. Click **"Create app"** → elige desplegar desde un repo existente.
3. Completa el formulario:
   - **Repository**: `eduardobg/mcp-ecommerce-openrouter`
   - **Branch**: `master`
   - **Main file path**: `app.py`
4. En **"Advanced settings" → "Secrets"**, pega (con tu key real):
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-..."
   ```
   `app/config.py` ya busca la key ahí automáticamente vía `st.secrets`, no
   hace falta tocar código.
5. Click **"Deploy"**. El primer arranque tarda unos minutos: instala
   dependencias, construye la base SQLite desde el CSV y levanta el servidor
   MCP interno.
6. Abre la URL pública que te asigna Streamlit Cloud, usa "Validar modelo" en
   la barra lateral y prueba una pregunta.

*(Estos pasos requieren tu sesión de navegador/GitHub — no puedo ejecutarlos
por ti, pero si algo falla puedes pegarme el log de Streamlit Cloud y te
ayudo a diagnosticarlo.)*

### Diferencias a vigilar frente a correrlo local

- **Memoria compartida (1 GB)**: el tier gratis reparte esa RAM entre
  Streamlit, el subproceso MCP y pandas/langchain/langgraph. Debería alcanzar
  para las 30,000 filas del dataset, pero es la primera sospecha si ves
  errores de memoria.
- **El subproceso del servidor MCP es el punto menos estándar de esta
  arquitectura en un hosting gestionado**: la app lanza `mcp_server/server.py`
  con `subprocess.Popen` bindeado a `127.0.0.1:8000` (puerto interno, nunca
  expuesto afuera). Esto debería funcionar igual que localmente porque es
  solo otro proceso dentro del mismo contenedor, pero si el indicador de
  "Servidor MCP" en la barra lateral nunca queda en 🟢 tras desplegar, es la
  primera pista a revisar.
- **Sleep / cold start**: si la app no recibe tráfico por un tiempo,
  Streamlit Cloud la "duerme"; el siguiente request tarda más porque
  reconstruye la base SQLite y relanza el servidor MCP (es idempotente, solo
  más lento la primera vez).

## Solución de problemas

- **El servidor MCP no arranca / puerto 8000 ocupado**: usa "Reiniciar
  servidor MCP" en la barra lateral. Si persiste, verifica que ningún otro
  proceso esté usando el puerto 8000 en tu máquina.
- **Error 502 / `ResourceExhausted`**: ver la tabla de la sección "Elegir el
  modelo" — cambia de modelo.
- **"Ingresa tu OPENROUTER_API_KEY..."**: falta configurar la key (paso 3 en
  local, o el panel de Secrets en Streamlit Community Cloud).
- **La app tarda en el primer arranque**: es normal — está construyendo la
  base SQLite (30,000 filas) y levantando el servidor MCP la primera vez.

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
