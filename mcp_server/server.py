"""
Servidor MCP de Analitica E-commerce
------------------------------------
Cada tool corresponde a una pregunta de negocio y a una consulta SQL explicita.
Adaptado del notebook de clase: mismas tools, mismo SQL parametrizado.

Transporte: HTTP / Streamable HTTP
Host/puerto configurables via MCP_HOST / MCP_PORT (default 127.0.0.1:8000).
"""

import json
import os
import sqlite3
from pathlib import Path

from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("ECOMMERCE_DB_PATH", REPO_ROOT / "data" / "ecommerce_demo.db"))

MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP(
    name="Ecommerce Analytics MCP",
    instructions=(
        "Servidor de analisis de e-commerce. "
        "Todas las herramientas son de solo lectura. "
        "Usa buscar_clientes si no conoces el Customer_ID exacto."
    ),
)


def ejecutar_sql(sql: str, parametros: tuple = ()) -> list[dict]:
    """
    Helper tecnico: abre SQLite y transforma las filas a diccionarios.
    La consulta SQL NO llega desde el LLM: cada tool define su propio SQL.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        filas = conn.execute(sql, parametros).fetchall()
    return [dict(fila) for fila in filas]


@mcp.tool()
def buscar_clientes(texto: str, limite: int = 10) -> str:
    """
    Busca clientes por Customer_ID, pais, ciudad o segmento.

    Pregunta que resuelve:
    - "Busca clientes Premium"
    - "Encuentra clientes de Chile"
    - "Existe el cliente CUST007322?"

    Args:
        texto: Texto de busqueda, por ejemplo "Premium", "Chile" o "CUST007322".
        limite: Maximo de clientes a devolver. Entre 1 y 25.
    """
    limite = max(1, min(limite, 25))
    patron = f"%{texto.strip()}%"

    sql = """
        SELECT
            Customer_ID,
            MAX(Country) AS Country,
            MAX(City) AS City,
            MAX(Customer_Segment) AS Customer_Segment,
            MAX(Membership_Status) AS Membership_Status,
            COUNT(*) AS Total_Orders,
            ROUND(SUM(Order_Amount), 2) AS Total_Spent
        FROM orders
        WHERE Customer_ID LIKE ?
           OR Country LIKE ?
           OR City LIKE ?
           OR Customer_Segment LIKE ?
        GROUP BY Customer_ID
        ORDER BY Total_Spent DESC
        LIMIT ?
    """

    filas = ejecutar_sql(sql, (patron, patron, patron, patron, limite))
    return json.dumps(filas or [{"message": "No se encontraron clientes"}], ensure_ascii=False)


@mcp.tool()
def resumen_consumo_cliente(customer_id: str) -> str:
    """
    Resume el consumo historico de un cliente identificado por Customer_ID exacto.

    Pregunta que resuelve:
    - "Cuanto ha consumido CUST007322?"
    - "Cual es su ticket promedio?"
    - "Desde cuando compra este cliente?"

    Args:
        customer_id: Identificador exacto del cliente, por ejemplo "CUST007322".
    """

    sql = """
        SELECT
            Customer_ID,
            COUNT(*) AS Total_Orders,
            ROUND(SUM(Order_Amount), 2) AS Total_Spent,
            ROUND(AVG(Order_Amount), 2) AS Average_Order_Value,
            SUM(Quantity) AS Units_Purchased,
            ROUND(SUM(Discount_Amount), 2) AS Total_Discounts,
            MIN(Order_Date) AS First_Order_Date,
            MAX(Order_Date) AS Last_Order_Date,
            ROUND(MAX(Customer_Lifetime_Value), 2) AS Customer_Lifetime_Value
        FROM orders
        WHERE Customer_ID = ?
        GROUP BY Customer_ID
    """

    filas = ejecutar_sql(sql, (customer_id,))
    return json.dumps(filas or [{"message": "Cliente no encontrado"}], ensure_ascii=False)


@mcp.tool()
def ordenes_recientes_cliente(customer_id: str, limite: int = 5) -> str:
    """
    Lista las ordenes mas recientes de un cliente.

    Pregunta que resuelve:
    - "Que compro ultimamente CUST007322?"
    - "Cual fue su ultimo pedido?"
    - "Que productos adquirio y cuanto pago?"

    Args:
        customer_id: Identificador exacto del cliente.
        limite: Maximo de ordenes a devolver. Entre 1 y 20.
    """
    limite = max(1, min(limite, 20))

    sql = """
        SELECT
            Order_ID,
            Order_Date,
            Product_Category,
            Product_Subcategory,
            Brand,
            Quantity,
            Unit_Price,
            Discount_Amount,
            Order_Amount,
            Payment_Method,
            Shipping_Method,
            Order_Status,
            Returned
        FROM orders
        WHERE Customer_ID = ?
        ORDER BY Order_Date DESC, Order_ID DESC
        LIMIT ?
    """

    filas = ejecutar_sql(sql, (customer_id, limite))
    return json.dumps(filas or [{"message": "No hay ordenes para este cliente"}], ensure_ascii=False)


@mcp.tool()
def consumo_por_categoria(customer_id: str) -> str:
    """
    Resume cuanto ha gastado un cliente por categoria de producto.

    Pregunta que resuelve:
    - "Que categorias prefiere CUST007322?"
    - "En que tipo de productos gasta mas?"
    - "Cuales son sus habitos de compra?"

    Args:
        customer_id: Identificador exacto del cliente.
    """

    sql = """
        SELECT
            Product_Category,
            COUNT(*) AS Total_Orders,
            SUM(Quantity) AS Units_Purchased,
            ROUND(SUM(Order_Amount), 2) AS Total_Spent,
            ROUND(AVG(Order_Amount), 2) AS Average_Order_Value
        FROM orders
        WHERE Customer_ID = ?
        GROUP BY Product_Category
        ORDER BY Total_Spent DESC
    """

    filas = ejecutar_sql(sql, (customer_id,))
    return json.dumps(filas or [{"message": "Cliente no encontrado"}], ensure_ascii=False)


@mcp.tool()
def metricas_experiencia_cliente(customer_id: str) -> str:
    """
    Calcula metricas de experiencia y postventa de un cliente.

    Pregunta que resuelve:
    - "Tiene muchas devoluciones?"
    - "Como evalua sus compras?"
    - "Ha tenido problemas de despacho?"

    Args:
        customer_id: Identificador exacto del cliente.
    """

    sql = """
        SELECT
            Customer_ID,
            COUNT(*) AS Total_Orders,
            SUM(CASE WHEN Returned = 'Yes' THEN 1 ELSE 0 END) AS Returned_Orders,
            ROUND(
                100.0 * SUM(CASE WHEN Returned = 'Yes' THEN 1 ELSE 0 END) / COUNT(*),
                2
            ) AS Return_Rate_Percent,
            ROUND(AVG(Review_Rating), 2) AS Average_Review_Rating,
            ROUND(AVG(Delivery_Days), 2) AS Average_Delivery_Days,
            SUM(CASE WHEN Order_Status <> 'Delivered' THEN 1 ELSE 0 END) AS Non_Delivered_Orders
        FROM orders
        WHERE Customer_ID = ?
        GROUP BY Customer_ID
    """

    filas = ejecutar_sql(sql, (customer_id,))
    return json.dumps(filas or [{"message": "Cliente no encontrado"}], ensure_ascii=False)


@mcp.tool()
def ranking_ventas_por_pais(year: int = 2023, limite: int = 10) -> str:
    """
    Entrega un ranking de ventas y utilidad por pais para un anio.

    Pregunta que resuelve:
    - "Que paises venden mas en 2023?"
    - "Donde se concentra la facturacion?"
    - "Que pais genera mas utilidad?"

    Args:
        year: Anio a analizar, por ejemplo 2023.
        limite: Numero maximo de paises del ranking. Entre 1 y 20.
    """
    limite = max(1, min(limite, 20))

    sql = """
        SELECT
            Country,
            COUNT(*) AS Total_Orders,
            ROUND(SUM(Order_Amount), 2) AS Revenue,
            ROUND(SUM(Profit_Amount), 2) AS Profit,
            ROUND(AVG(Order_Amount), 2) AS Average_Order_Value
        FROM orders
        WHERE Year = ?
        GROUP BY Country
        ORDER BY Revenue DESC
        LIMIT ?
    """

    filas = ejecutar_sql(sql, (year, limite))
    return json.dumps(filas, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
