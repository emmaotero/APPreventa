import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# ============================================
# CONFIGURACIÓN
# ============================================
st.set_page_config(
    page_title="Sistema de Reventa",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def init_supabase() -> Client:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ============================================
# FUNCIONES DE EXCEL
# ============================================

def to_excel(df, sheet_name="Datos"):
    """Convierte DataFrame a Excel con formato"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'border': 1
        })
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            max_len = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(col_num, col_num, max_len)
    
    return output.getvalue()

def formato_moneda(valor):
    """Formatea números como moneda"""
    return f"${valor:,.2f}"

# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def obtener_productos(activos_solo=True):
    query = supabase.table("productos").select("*, categorias(nombre), proveedores(nombre)")
    if activos_solo:
        query = query.eq("activo", True)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_producto(datos):
    return supabase.table("productos").insert(datos).execute().data

def actualizar_producto(id_producto, datos):
    return supabase.table("productos").update(datos).eq("id", id_producto).execute().data

def registrar_compra(datos):
    return supabase.table("compras").insert(datos).execute().data

def obtener_compras(fecha_desde=None, fecha_hasta=None):
    query = supabase.table("compras").select("*, productos(nombre, codigo), proveedores(nombre)").order("fecha", desc=True)
    if fecha_desde:
        query = query.gte("fecha", fecha_desde)
    if fecha_hasta:
        query = query.lte("fecha", fecha_hasta)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def registrar_venta(datos):
    return supabase.table("ventas").insert(datos).execute().data

def obtener_ventas(fecha_desde=None, fecha_hasta=None):
    query = supabase.table("ventas").select("*, productos(nombre, codigo)").order("fecha", desc=True)
    if fecha_desde:
        query = query.gte("fecha", fecha_desde)
    if fecha_hasta:
        query = query.lte("fecha", fecha_hasta)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def obtener_categorias():
    response = supabase.table("categorias").select("*").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_categoria(nombre, descripcion=""):
    return supabase.table("categorias").insert({"nombre": nombre, "descripcion": descripcion}).execute().data

def obtener_proveedores():
    response = supabase.table("proveedores").select("*").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_proveedor(datos):
    return supabase.table("proveedores").insert(datos).execute().data

def obtener_stock_bajo():
    response = supabase.table("vista_stock_bajo").select("*").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def obtener_ventas_por_producto():
    response = supabase.table("vista_ventas_por_producto").select("*").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def obtener_metricas_dashboard():
    productos = obtener_productos()
    total_productos = len(productos)
    valor_stock = (productos['stock_actual'] * productos['precio_venta']).sum() if not productos.empty else 0
    
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    ventas_mes = obtener_ventas(fecha_desde=str(inicio_mes))
    
    if not ventas_mes.empty:
        ingresos_mes = ventas_mes['subtotal'].sum()
        ganancia_mes = ventas_mes['ganancia'].sum()
        cantidad_ventas_mes = len(ventas_mes)
    else:
        ingresos_mes = ganancia_mes = cantidad_ventas_mes = 0
    
    stock_bajo = obtener_stock_bajo()
    alertas_stock = len(stock_bajo)
    
    return {
        'total_productos': total_productos,
        'valor_stock': valor_stock,
        'ingresos_mes': ingresos_mes,
        'ganancia_mes': ganancia_mes,
        'cantidad_ventas_mes': cantidad_ventas_mes,
        'alertas_stock': alertas_stock
    }

# ============================================
# PÁGINAS
# ============================================

def pagina_dashboard():
    st.title("📊 Dashboard")
    metricas = obtener_metricas_dashboard()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Productos Activos", metricas['total_productos'])
    with col2:
        st.metric("Valor del Stock", formato_moneda(metricas['valor_stock']))
    with col3:
        st.metric("Ingresos del Mes", formato_moneda(metricas['ingresos_mes']))
    with col4:
        st.metric("Ganancia del Mes", formato_moneda(metricas['ganancia_mes']))
    
    st.divider()
    
    if metricas['alertas_stock'] > 0:
        st.warning(f"⚠️ **{metricas['alertas_stock']} productos** con stock bajo")
        stock_bajo = obtener_stock_bajo()
        st.dataframe(
            stock_bajo[['nombre', 'categoria', 'stock_actual', 'stock_minimo']], 
            use_container_width=True, 
            hide_index=True
        )
        st.download_button(
            label="📥 Descargar Stock Bajo (Excel)",
            data=to_excel(stock_bajo, "Stock Bajo"),
            file_name=f"stock_bajo_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def pagina_productos():
    st.title("📦 Gestión de Productos")
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Nuevo"])
    
    with tab1:
        productos = obtener_productos()
        if not productos.empty:
            productos_display = productos.copy()
            productos_display['categoria'] = productos_display['categorias'].apply(
                lambda x: x['nombre'] if x else 'Sin categoría'
            )
            productos_display['proveedor'] = productos_display['proveedores'].apply(
                lambda x: x['nombre'] if x else 'Sin proveedor'
            )
            
            st.dataframe(
                productos_display[['nombre', 'categoria', 'proveedor', 'stock_actual', 
                                  'precio_compra', 'precio_venta', 'margen_porcentaje']],
                use_container_width=True,
                hide_index=True
            )
            
            st.download_button(
                label="📥 Descargar Productos (Excel)",
                data=to_excel(productos_display[['nombre', 'categoria', 'proveedor', 
                              'stock_actual', 'precio_compra', 'precio_venta', 'margen_porcentaje']], 
                              "Productos"),
                file_name=f"productos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay productos registrados")
    
    with tab2:
        categorias = obtener_categorias()
        proveedores = obtener_proveedores()
        
        with st.form("nuevo_producto"):
            nombre = st.text_input("Nombre *")
            categoria_id = st.selectbox(
                "Categoría",
                categorias['id'].tolist(),
                format_func=lambda x: categorias[categorias['id']==x]['nombre'].values[0]
            ) if not categorias.empty else None
            
            proveedor_id = st.selectbox(
                "Proveedor",
                [None] + proveedores['id'].tolist(),
                format_func=lambda x: "Sin proveedor" if x is None else proveedores[proveedores['id']==x]['nombre'].values[0]
            ) if not proveedores.empty else None
            
            precio_compra = st.number_input("Precio Compra", min_value=0.0, step=0.01)
            precio_venta = st.number_input("Precio Venta", min_value=0.0, step=0.01)
            stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
            
            if st.form_submit_button("✅ Crear"):
                if nombre and categoria_id:
                    crear_producto({
                        'nombre': nombre,
                        'categoria_id': categoria_id,
                        'proveedor_id': proveedor_id,
                        'precio_compra': precio_compra,
                        'precio_venta': precio_venta,
                        'stock_actual': stock_inicial
                    })
                    st.success(f"✅ Producto '{nombre}' creado")
                    st.rerun()
                else:
                    st.error("Completá los campos obligatorios")

def pagina_compras():
    st.title("🛒 Gestión de Compras")
    tab1, tab2 = st.tabs(["➕ Registrar", "📋 Historial"])
    
    with tab1:
        productos = obtener_productos()
        if productos.empty:
            st.warning("No hay productos registrados")
            return
        
        with st.form("nueva_compra"):
            producto_id = st.selectbox(
                "Producto",
                productos['id'].tolist(),
                format_func=lambda x: productos[productos['id']==x]['nombre'].values[0]
            )
            cantidad = st.number_input("Cantidad", min_value=1, step=1)
            precio_unitario = st.number_input("Precio Unitario", min_value=0.01, step=0.01)
            fecha_compra = st.date_input("Fecha", value=datetime.now().date())
            
            if st.form_submit_button("✅ Registrar"):
                registrar_compra({
                    'producto_id': producto_id,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'fecha': str(fecha_compra)
                })
                st.success("✅ Compra registrada")
                st.rerun()
    
    with tab2:
        fecha_desde = st.date_input("Desde", value=datetime.now().date() - timedelta(days=30), key="comp_desde")
        fecha_hasta = st.date_input("Hasta", value=datetime.now().date(), key="comp_hasta")
        compras = obtener_compras(str(fecha_desde), str(fecha_hasta))
        
        if not compras.empty:
            compras_display = compras.copy()
            compras_display['producto'] = compras_display['productos'].apply(
                lambda x: x['nombre'] if x else 'N/A'
            )
            
            st.dataframe(
                compras_display[['fecha', 'producto', 'cantidad', 'precio_unitario', 'total']],
                use_container_width=True,
                hide_index=True
            )
            
            st.download_button(
                label="📥 Descargar Compras (Excel)",
                data=to_excel(compras_display[['fecha', 'producto', 'cantidad', 
                              'precio_unitario', 'total']], "Compras"),
                file_name=f"compras_{fecha_desde}_{fecha_hasta}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay compras en el período seleccionado")

def pagina_ventas():
    st.title("💰 Gestión de Ventas")
    tab1, tab2 = st.tabs(["➕ Registrar", "📋 Historial"])
    
    with tab1:
        productos = obtener_productos()
        if productos.empty:
            st.warning("No hay productos registrados")
            return
        
        with st.form("nueva_venta"):
            producto_id = st.selectbox(
                "Producto",
                productos['id'].tolist(),
                format_func=lambda x: f"{productos[productos['id']==x]['nombre'].values[0]} (Stock: {productos[productos['id']==x]['stock_actual'].values[0]})"
            )
            cantidad = st.number_input("Cantidad", min_value=1, step=1)
            precio_unitario = st.number_input("Precio Venta", min_value=0.01, step=0.01)
            fecha_venta = st.date_input("Fecha", value=datetime.now().date())
            
            if st.form_submit_button("✅ Registrar"):
                try:
                    registrar_venta({
                        'producto_id': producto_id,
                        'cantidad': cantidad,
                        'precio_unitario': precio_unitario,
                        'fecha': str(fecha_venta)
                    })
                    st.success("✅ Venta registrada")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    with tab2:
        fecha_desde = st.date_input("Desde", value=datetime.now().date() - timedelta(days=30), key="venta_desde")
        fecha_hasta = st.date_input("Hasta", value=datetime.now().date(), key="venta_hasta")
        ventas = obtener_ventas(str(fecha_desde), str(fecha_hasta))
        
        if not ventas.empty:
            ventas_display = ventas.copy()
            ventas_display['producto'] = ventas_display['productos'].apply(
                lambda x: x['nombre'] if x else 'N/A'
            )
            
            st.dataframe(
                ventas_display[['fecha', 'producto', 'cantidad', 'precio_unitario', 
                               'subtotal', 'ganancia', 'margen_porcentaje']],
                use_container_width=True,
                hide_index=True
            )
            
            st.download_button(
                label="📥 Descargar Ventas (Excel)",
                data=to_excel(ventas_display[['fecha', 'producto', 'cantidad', 
                              'precio_unitario', 'subtotal', 'ganancia', 'margen_porcentaje']], 
                              "Ventas"),
                file_name=f"ventas_{fecha_desde}_{fecha_hasta}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay ventas en el período seleccionado")

def pagina_proveedores():
    st.title("👥 Proveedores y Categorías")
    tab1, tab2 = st.tabs(["Proveedores", "Categorías"])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            proveedores = obtener_proveedores()
            if not proveedores.empty:
                st.dataframe(
                    proveedores[['nombre', 'contacto', 'telefono']], 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("No hay proveedores registrados")
        
        with col2:
            with st.form("nuevo_proveedor"):
                nombre = st.text_input("Nombre")
                contacto = st.text_input("Contacto")
                telefono = st.text_input("Teléfono")
                
                if st.form_submit_button("✅ Crear"):
                    if nombre:
                        crear_proveedor({
                            'nombre': nombre,
                            'contacto': contacto,
                            'telefono': telefono
                        })
                        st.success("✅ Proveedor creado")
                        st.rerun()
    
    with tab2:
        col1, col2 = st.columns([2, 1])
        with col1:
            categorias = obtener_categorias()
            if not categorias.empty:
                st.dataframe(
                    categorias[['nombre', 'descripcion']], 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("No hay categorías registradas")
        
        with col2:
            with st.form("nueva_categoria"):
                nombre = st.text_input("Nombre")
                descripcion = st.text_area("Descripción")
                
                if st.form_submit_button("✅ Crear"):
                    if nombre:
                        crear_categoria(nombre, descripcion)
                        st.success("✅ Categoría creada")
                        st.rerun()

# ============================================
# NAVEGACIÓN
# ============================================

def main():
    with st.sidebar:
        st.title("📦 Sistema de Reventa")
        st.divider()
        
        pagina = st.radio(
            "Navegación",
            ["📊 Dashboard", "📦 Productos", "🛒 Compras", "💰 Ventas", "👥 Proveedores"],
            label_visibility="collapsed"
        )
        
        st.divider()
        st.caption("v1.0.0")
    
    if pagina == "📊 Dashboard":
        pagina_dashboard()
    elif pagina == "📦 Productos":
        pagina_productos()
    elif pagina == "🛒 Compras":
        pagina_compras()
    elif pagina == "💰 Ventas":
        pagina_ventas()
    elif pagina == "👥 Proveedores":
        pagina_proveedores()

if __name__ == "__main__":
    main()
