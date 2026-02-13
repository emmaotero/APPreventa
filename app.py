import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import hashlib

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
# SISTEMA DE AUTENTICACIÓN
# ============================================

def hash_password(password):
    """Hashea la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def login_usuario(email, password):
    """Verifica credenciales y retorna usuario si es válido"""
    try:
        response = supabase.table("usuarios").select("*").eq("email", email).eq("password_hash", hash_password(password)).eq("activo", True).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except:
        return None

def registrar_usuario(email, nombre, password):
    """Registra un nuevo usuario"""
    try:
        nuevo_usuario = {
            'email': email,
            'nombre': nombre,
            'password_hash': hash_password(password)
        }
        response = supabase.table("usuarios").insert(nuevo_usuario).execute()
        
        # Crear categorías por defecto
        if response.data:
            usuario_id = response.data[0]['id']
            categorias_default = [
                {'nombre': 'Electrónica', 'usuario_id': usuario_id},
                {'nombre': 'Ropa', 'usuario_id': usuario_id},
                {'nombre': 'Hogar', 'usuario_id': usuario_id},
                {'nombre': 'Otros', 'usuario_id': usuario_id}
            ]
            supabase.table("categorias").insert(categorias_default).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Error al registrar: {str(e)}")
        return None

def verificar_sesion():
    """Verifica si hay una sesión activa"""
    return 'usuario' in st.session_state

def obtener_usuario_actual():
    """Obtiene el usuario de la sesión actual"""
    if 'usuario' in st.session_state:
        return st.session_state.usuario
    return None

def cerrar_sesion():
    """Cierra la sesión del usuario"""
    if 'usuario' in st.session_state:
        del st.session_state.usuario
    st.rerun()

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
            col_data = df[value].astype(str)
            if len(col_data) > 0:
                max_len = max(col_data.apply(len).max(), len(str(value))) + 2
            else:
                max_len = len(str(value)) + 2
            worksheet.set_column(col_num, col_num, max_len)
    
    return output.getvalue()

def formato_moneda(valor):
    """Formatea números como moneda"""
    return f"${valor:,.2f}"

# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

# --- PRODUCTOS ---
def obtener_productos(activos_solo=True):
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    query = supabase.table("productos").select("*, categorias(nombre), proveedores(nombre)").eq("usuario_id", usuario['id'])
    if activos_solo:
        query = query.eq("activo", True)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_producto(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("productos").insert(datos).execute().data

def actualizar_producto(id_producto, datos):
    return supabase.table("productos").update(datos).eq("id", id_producto).execute().data

def eliminar_producto(id_producto):
    return supabase.table("productos").update({"activo": False}).eq("id", id_producto).execute().data

# --- COMPRAS ---
def registrar_compra(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("compras").insert(datos).execute().data

def eliminar_compra(id_compra):
    """Elimina una compra - OJO: no revierte el stock automáticamente"""
    return supabase.table("compras").delete().eq("id", id_compra).execute().data

def obtener_compras(fecha_desde=None, fecha_hasta=None):
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    query = supabase.table("compras").select("*, productos(nombre, codigo), proveedores(nombre)").eq("usuario_id", usuario['id']).order("fecha", desc=True)
    if fecha_desde:
        query = query.gte("fecha", fecha_desde)
    if fecha_hasta:
        query = query.lte("fecha", fecha_hasta)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

# --- VENTAS ---
def registrar_venta(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("ventas").insert(datos).execute().data

def eliminar_venta(id_venta):
    """Elimina una venta - OJO: no revierte el stock automáticamente"""
    return supabase.table("ventas").delete().eq("id", id_venta).execute().data

def obtener_ventas(fecha_desde=None, fecha_hasta=None):
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    query = supabase.table("ventas").select("*, productos(nombre, codigo)").eq("usuario_id", usuario['id']).order("fecha", desc=True)
    if fecha_desde:
        query = query.gte("fecha", fecha_desde)
    if fecha_hasta:
        query = query.lte("fecha", fecha_hasta)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

# --- CATEGORÍAS ---
def obtener_categorias():
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    response = supabase.table("categorias").select("*").eq("usuario_id", usuario['id']).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_categoria(nombre, descripcion=""):
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    return supabase.table("categorias").insert({
        "nombre": nombre, 
        "descripcion": descripcion,
        "usuario_id": usuario['id']
    }).execute().data

def actualizar_categoria(id_categoria, datos):
    return supabase.table("categorias").update(datos).eq("id", id_categoria).execute().data

def eliminar_categoria(id_categoria):
    return supabase.table("categorias").delete().eq("id", id_categoria).execute().data

def generar_codigo_producto(nombre_producto, categoria_nombre):
    """Genera código único del producto: PAPHIG-PAP-0001"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    # Obtener primeras 6 letras del producto (sin espacios, mayúsculas)
    prod_code = ''.join(nombre_producto.split()).upper()[:6]
    
    # Obtener primeras 3 letras de la categoría
    cat_code = ''.join(categoria_nombre.split()).upper()[:3]
    
    # Obtener productos de esa categoría para el contador
    productos_cat = obtener_productos(activos_solo=False)
    if not productos_cat.empty:
        # Filtrar por categoría
        productos_cat['cat_nombre'] = productos_cat['categorias'].apply(
            lambda x: x['nombre'] if x else ''
        )
        productos_misma_cat = productos_cat[productos_cat['cat_nombre'] == categoria_nombre]
        contador = len(productos_misma_cat) + 1
    else:
        contador = 1
    
    # Formato: PAPHIG-PAP-0001
    codigo = f"{prod_code}-{cat_code}-{contador:04d}"
    
    return codigo

# --- PROVEEDORES ---
def obtener_proveedores():
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    response = supabase.table("proveedores").select("*").eq("usuario_id", usuario['id']).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_proveedor(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("proveedores").insert(datos).execute().data

def actualizar_proveedor(id_proveedor, datos):
    return supabase.table("proveedores").update(datos).eq("id", id_proveedor).execute().data

def eliminar_proveedor(id_proveedor):
    return supabase.table("proveedores").delete().eq("id", id_proveedor).execute().data

# --- COSTOS FIJOS ---
def obtener_costos_fijos():
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    response = supabase.table("costos_fijos").select("*").eq("usuario_id", usuario['id']).eq("activo", True).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_costo_fijo(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("costos_fijos").insert(datos).execute().data

def actualizar_costo_fijo(id_costo, datos):
    return supabase.table("costos_fijos").update(datos).eq("id", id_costo).execute().data

def eliminar_costo_fijo(id_costo):
    return supabase.table("costos_fijos").update({"activo": False}).eq("id", id_costo).execute().data

def calcular_costos_mes_actual():
    """Calcula el total de costos fijos del mes actual"""
    costos = obtener_costos_fijos()
    if costos.empty:
        return 0
    
    hoy = datetime.now().date()
    total = 0
    
    for _, costo in costos.iterrows():
        # Verificar que el costo esté activo en este mes
        if costo['fecha_inicio'] > str(hoy):
            continue
        if costo['fecha_fin'] and costo['fecha_fin'] < str(hoy):
            continue
            
        # Calcular monto según frecuencia
        if costo['frecuencia'] == 'mensual':
            total += costo['monto']
        elif costo['frecuencia'] == 'anual':
            total += costo['monto'] / 12
        # Los costos únicos no se suman al mensual recurrente
    
    return total

# --- REPORTES ---
def obtener_stock_bajo():
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    response = supabase.table("vista_stock_bajo").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    df = pd.DataFrame(response.data)
    # Filtrar por productos del usuario
    productos_usuario = obtener_productos(activos_solo=False)
    if productos_usuario.empty:
        return pd.DataFrame()
    df = df[df['id'].isin(productos_usuario['id'])]
    return df

def obtener_ventas_por_producto():
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    response = supabase.table("vista_ventas_por_producto").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    df = pd.DataFrame(response.data)
    # Filtrar por productos del usuario
    productos_usuario = obtener_productos(activos_solo=False)
    if productos_usuario.empty:
        return pd.DataFrame()
    df = df[df['id'].isin(productos_usuario['id'])]
    return df

def obtener_metricas_dashboard():
    productos = obtener_productos()
    total_productos = len(productos)
    valor_stock = (productos['stock_actual'] * productos['precio_venta']).sum() if not productos.empty else 0
    
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    ventas_mes = obtener_ventas(fecha_desde=str(inicio_mes))
    
    if not ventas_mes.empty:
        ingresos_mes = ventas_mes['subtotal'].sum()
        ganancia_bruta_mes = ventas_mes['ganancia'].sum()
        cantidad_ventas_mes = len(ventas_mes)
    else:
        ingresos_mes = ganancia_bruta_mes = cantidad_ventas_mes = 0
    
    # Calcular ganancia neta (descontando costos fijos)
    costos_fijos_mes = calcular_costos_mes_actual()
    ganancia_neta_mes = ganancia_bruta_mes - costos_fijos_mes
    
    stock_bajo = obtener_stock_bajo()
    alertas_stock = len(stock_bajo)
    
    return {
        'total_productos': total_productos,
        'valor_stock': valor_stock,
        'ingresos_mes': ingresos_mes,
        'ganancia_bruta_mes': ganancia_bruta_mes,
        'ganancia_neta_mes': ganancia_neta_mes,
        'costos_fijos_mes': costos_fijos_mes,
        'cantidad_ventas_mes': cantidad_ventas_mes,
        'alertas_stock': alertas_stock
    }

# ============================================
# PÁGINA DE LOGIN
# ============================================

def pagina_login():
    st.title("🔐 Sistema de Reventa")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
        
        with tab1:
            st.subheader("Iniciar Sesión")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Ingresar")
                
                if submitted:
                    if email and password:
                        usuario = login_usuario(email, password)
                        if usuario:
                            st.session_state.usuario = usuario
                            st.success(f"¡Bienvenido {usuario['nombre']}!")
                            st.rerun()
                        else:
                            st.error("Email o contraseña incorrectos")
                    else:
                        st.error("Completá todos los campos")
        
        with tab2:
            st.subheader("Crear Cuenta")
            with st.form("registro_form"):
                nuevo_email = st.text_input("Email", key="reg_email")
                nuevo_nombre = st.text_input("Nombre completo", key="reg_nombre")
                nueva_password = st.text_input("Contraseña", type="password", key="reg_pass")
                confirmar_password = st.text_input("Confirmar contraseña", type="password", key="reg_conf")
                
                registrar = st.form_submit_button("Crear Cuenta")
                
                if registrar:
                    if not (nuevo_email and nuevo_nombre and nueva_password and confirmar_password):
                        st.error("Completá todos los campos")
                    elif nueva_password != confirmar_password:
                        st.error("Las contraseñas no coinciden")
                    elif len(nueva_password) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres")
                    else:
                        usuario = registrar_usuario(nuevo_email, nuevo_nombre, nueva_password)
                        if usuario:
                            st.success("¡Cuenta creada! Podés iniciar sesión ahora")
                        else:
                            st.error("Error al crear la cuenta. El email puede estar en uso.")

# ============================================
# PÁGINAS PRINCIPALES
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
        st.metric("Ganancia Bruta", formato_moneda(metricas['ganancia_bruta_mes']))
    
    # Mostrar ganancia neta vs costos fijos
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Costos Fijos Mensuales", formato_moneda(metricas['costos_fijos_mes']))
    with col2:
        delta_color = "normal" if metricas['ganancia_neta_mes'] >= 0 else "inverse"
        st.metric(
            "Ganancia Neta", 
            formato_moneda(metricas['ganancia_neta_mes']),
            delta=f"{metricas['cantidad_ventas_mes']} ventas"
        )
    with col3:
        if metricas['ganancia_bruta_mes'] > 0:
            margen_neto = (metricas['ganancia_neta_mes'] / metricas['ganancia_bruta_mes'] * 100)
            st.metric("Margen Neto", f"{margen_neto:.1f}%")
    
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
    tab1, tab2, tab3 = st.tabs(["📋 Lista", "➕ Nuevo", "✏️ Editar/Eliminar"])
    
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
            
            # Mostrar con código y campos adicionales
            columnas_mostrar = ['codigo', 'nombre', 'marca', 'variedad', 'presentacion', 
                              'categoria', 'proveedor', 'stock_actual', 'precio_compra', 
                              'precio_venta', 'margen_porcentaje']
            
            st.dataframe(
                productos_display[columnas_mostrar],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "codigo": "Código",
                    "nombre": "Producto",
                    "marca": "Marca",
                    "variedad": "Variedad",
                    "presentacion": "Presentación",
                    "categoria": "Categoría",
                    "proveedor": "Proveedor",
                    "stock_actual": "Stock",
                    "precio_compra": st.column_config.NumberColumn("P. Compra", format="$%.2f"),
                    "precio_venta": st.column_config.NumberColumn("P. Venta", format="$%.2f"),
                    "margen_porcentaje": st.column_config.NumberColumn("Margen %", format="%.1f%%")
                }
            )
            
            st.download_button(
                label="📥 Descargar Productos (Excel)",
                data=to_excel(productos_display[columnas_mostrar], "Productos"),
                file_name=f"productos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay productos registrados")
    
    with tab2:
        categorias = obtener_categorias()
        proveedores = obtener_proveedores()
        
        with st.form("nuevo_producto"):
            st.subheader("Información Básica")
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Nombre del Producto *")
                categoria_id = st.selectbox(
                    "Categoría *",
                    categorias['id'].tolist(),
                    format_func=lambda x: categorias[categorias['id']==x]['nombre'].values[0]
                ) if not categorias.empty else None
                
                proveedor_id = st.selectbox(
                    "Proveedor",
                    [None] + proveedores['id'].tolist(),
                    format_func=lambda x: "Sin proveedor" if x is None else proveedores[proveedores['id']==x]['nombre'].values[0]
                ) if not proveedores.empty else None
            
            with col2:
                marca = st.text_input("Marca")
                variedad = st.text_input("Variedad")
                presentacion = st.text_input("Presentación")
            
            detalle = st.text_area("Detalle / Otro")
            
            st.divider()
            st.subheader("Precios y Stock")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                precio_compra = st.number_input("Precio Compra *", min_value=0.0, step=0.01)
            with col2:
                precio_venta = st.number_input("Precio Venta *", min_value=0.0, step=0.01)
            with col3:
                stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
            
            # Mostrar código que se generará
            if nombre and categoria_id:
                cat_nombre = categorias[categorias['id']==categoria_id]['nombre'].values[0]
                codigo_preview = generar_codigo_producto(nombre, cat_nombre)
                st.info(f"📋 Código que se asignará: **{codigo_preview}**")
            
            if st.form_submit_button("✅ Crear Producto"):
                if nombre and categoria_id:
                    cat_nombre = categorias[categorias['id']==categoria_id]['nombre'].values[0]
                    codigo_generado = generar_codigo_producto(nombre, cat_nombre)
                    
                    crear_producto({
                        'codigo': codigo_generado,
                        'nombre': nombre,
                        'categoria_id': categoria_id,
                        'proveedor_id': proveedor_id,
                        'marca': marca if marca else None,
                        'variedad': variedad if variedad else None,
                        'presentacion': presentacion if presentacion else None,
                        'detalle': detalle if detalle else None,
                        'precio_compra': precio_compra,
                        'precio_venta': precio_venta,
                        'stock_actual': stock_inicial
                    })
                    st.success(f"✅ Producto '{nombre}' creado con código {codigo_generado}")
                    st.rerun()
                else:
                    st.error("Completá los campos obligatorios (*)")
    
    with tab3:
        productos = obtener_productos(activos_solo=False)
        if productos.empty:
            st.info("No hay productos para editar")
            return
        
        producto_seleccionado = st.selectbox(
            "Seleccionar producto",
            productos['id'].tolist(),
            format_func=lambda x: f"{productos[productos['id']==x]['codigo'].values[0]} - {productos[productos['id']==x]['nombre'].values[0]}"
        )
        
        if producto_seleccionado:
            prod = productos[productos['id']==producto_seleccionado].iloc[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("✏️ Editar Producto")
                
                categorias = obtener_categorias()
                proveedores = obtener_proveedores()
                
                with st.form("editar_producto"):
                    st.write(f"**Código:** {prod['codigo']}")
                    
                    nuevo_nombre = st.text_input("Nombre", value=prod['nombre'])
                    
                    # Categoría editable
                    if not categorias.empty:
                        # Encontrar índice de la categoría actual
                        cat_actual_id = prod['categoria_id']
                        if cat_actual_id and cat_actual_id in categorias['id'].values:
                            indice_actual = categorias[categorias['id']==cat_actual_id].index[0]
                        else:
                            indice_actual = 0
                        
                        nueva_categoria_id = st.selectbox(
                            "Categoría",
                            categorias['id'].tolist(),
                            format_func=lambda x: categorias[categorias['id']==x]['nombre'].values[0],
                            index=indice_actual
                        )
                    else:
                        nueva_categoria_id = None
                    
                    # Proveedor editable
                    if not proveedores.empty:
                        prov_actual_id = prod['proveedor_id']
                        opciones_prov = [None] + proveedores['id'].tolist()
                        
                        if prov_actual_id and prov_actual_id in proveedores['id'].values:
                            indice_prov = opciones_prov.index(prov_actual_id)
                        else:
                            indice_prov = 0
                        
                        nuevo_proveedor_id = st.selectbox(
                            "Proveedor",
                            opciones_prov,
                            format_func=lambda x: "Sin proveedor" if x is None else proveedores[proveedores['id']==x]['nombre'].values[0],
                            index=indice_prov
                        )
                    else:
                        nuevo_proveedor_id = None
                    
                    nueva_marca = st.text_input("Marca", value=prod['marca'] if prod['marca'] else "")
                    nueva_variedad = st.text_input("Variedad", value=prod['variedad'] if prod['variedad'] else "")
                    nueva_presentacion = st.text_input("Presentación", value=prod['presentacion'] if prod['presentacion'] else "")
                    nuevo_detalle = st.text_area("Detalle", value=prod['detalle'] if prod['detalle'] else "")
                    
                    st.divider()
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        nuevo_precio_compra = st.number_input("Precio Compra", value=float(prod['precio_compra']), step=0.01)
                        nuevo_precio_venta = st.number_input("Precio Venta", value=float(prod['precio_venta']), step=0.01)
                    with col_b:
                        nuevo_stock_minimo = st.number_input("Stock Mínimo", value=int(prod['stock_minimo']), step=1)
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        actualizar_producto(producto_seleccionado, {
                            'nombre': nuevo_nombre,
                            'categoria_id': nueva_categoria_id,
                            'proveedor_id': nuevo_proveedor_id,
                            'marca': nueva_marca if nueva_marca else None,
                            'variedad': nueva_variedad if nueva_variedad else None,
                            'presentacion': nueva_presentacion if nueva_presentacion else None,
                            'detalle': nuevo_detalle if nuevo_detalle else None,
                            'precio_compra': nuevo_precio_compra,
                            'precio_venta': nuevo_precio_venta,
                            'stock_minimo': nuevo_stock_minimo
                        })
                        st.success("✅ Producto actualizado")
                        st.rerun()
            
            with col2:
                st.subheader("🗑️ Eliminar")
                st.warning(f"**Producto:** {prod['nombre']}")
                st.write(f"**Código:** {prod['codigo']}")
                st.write(f"Stock actual: {prod['stock_actual']}")
                
                if st.button("🗑️ Eliminar Producto", type="secondary"):
                    eliminar_producto(producto_seleccionado)
                    st.success("✅ Producto eliminado")
                    st.rerun()

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
        col1, col2 = st.columns([3, 1])
        with col1:
            fecha_desde = st.date_input("Desde", value=datetime.now().date() - timedelta(days=30), key="comp_desde")
        with col2:
            fecha_hasta = st.date_input("Hasta", value=datetime.now().date(), key="comp_hasta")
        
        compras = obtener_compras(str(fecha_desde), str(fecha_hasta))
        
        if not compras.empty:
            compras_display = compras.copy()
            compras_display['producto'] = compras_display['productos'].apply(
                lambda x: x['nombre'] if x else 'N/A'
            )
            
            # Mostrar con opción de eliminar
            for idx, compra in compras_display.iterrows():
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(f"**{compra['fecha']}** - {compra['producto']} - {compra['cantidad']} unidades - {formato_moneda(compra['total'])}")
                with col2:
                    if st.button("🗑️", key=f"del_compra_{compra['id']}"):
                        eliminar_compra(compra['id'])
                        st.warning("⚠️ Compra eliminada. Recordá ajustar el stock manualmente si es necesario.")
                        st.rerun()
            
            st.divider()
            
            st.download_button(
                label="📥 Descargar Compras (Excel)",
                data=to_excel(compras_display[['fecha', 'producto', 'cantidad', 
                              'precio_unitario', 'total']], "Compras"),
                file_name=f"compras_{fecha_desde}_{fecha_hasta}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Resumen
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Compras", len(compras))
            with col2:
                st.metric("Inversión Total", formato_moneda(compras_display['total'].sum()))
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
        col1, col2 = st.columns([3, 1])
        with col1:
            fecha_desde = st.date_input("Desde", value=datetime.now().date() - timedelta(days=30), key="venta_desde")
        with col2:
            fecha_hasta = st.date_input("Hasta", value=datetime.now().date(), key="venta_hasta")
        
        ventas = obtener_ventas(str(fecha_desde), str(fecha_hasta))
        
        if not ventas.empty:
            ventas_display = ventas.copy()
            ventas_display['producto'] = ventas_display['productos'].apply(
                lambda x: x['nombre'] if x else 'N/A'
            )
            
            # Mostrar con opción de eliminar
            for idx, venta in ventas_display.iterrows():
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(f"**{venta['fecha']}** - {venta['producto']} - {venta['cantidad']} unidades - {formato_moneda(venta['subtotal'])} (Ganancia: {formato_moneda(venta['ganancia'])})")
                with col2:
                    if st.button("🗑️", key=f"del_venta_{venta['id']}"):
                        eliminar_venta(venta['id'])
                        st.warning("⚠️ Venta eliminada. Recordá ajustar el stock manualmente si es necesario.")
                        st.rerun()
            
            st.divider()
            
            st.download_button(
                label="📥 Descargar Ventas (Excel)",
                data=to_excel(ventas_display[['fecha', 'producto', 'cantidad', 
                              'precio_unitario', 'subtotal', 'ganancia', 'margen_porcentaje']], 
                              "Ventas"),
                file_name=f"ventas_{fecha_desde}_{fecha_hasta}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Resumen
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Ventas", len(ventas))
            with col2:
                st.metric("Ingresos", formato_moneda(ventas_display['subtotal'].sum()))
            with col3:
                st.metric("Ganancia Total", formato_moneda(ventas_display['ganancia'].sum()))
        else:
            st.info("No hay ventas en el período seleccionado")

def pagina_costos_fijos():
    st.title("💸 Costos Fijos")
    
    tab1, tab2, tab3 = st.tabs(["📋 Mis Costos", "➕ Nuevo Costo", "✏️ Editar/Eliminar"])
    
    with tab1:
        costos = obtener_costos_fijos()
        
        if not costos.empty:
            # Calcular total mensual
            total_mensual = calcular_costos_mes_actual()
            st.metric("Total Mensual Estimado", formato_moneda(total_mensual))
            st.divider()
            
            # Mostrar tabla
            costos_display = costos.copy()
            costos_display['monto_display'] = costos_display['monto'].apply(formato_moneda)
            
            st.dataframe(
                costos_display[['nombre', 'frecuencia', 'monto_display', 'fecha_inicio', 'fecha_fin', 'descripcion']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Concepto",
                    "frecuencia": "Frecuencia",
                    "monto_display": "Monto",
                    "fecha_inicio": "Desde",
                    "fecha_fin": "Hasta",
                    "descripcion": "Notas"
                }
            )
            
            st.download_button(
                label="📥 Descargar Costos (Excel)",
                data=to_excel(costos_display[['nombre', 'frecuencia', 'monto', 'fecha_inicio', 'fecha_fin', 'descripcion']], "Costos Fijos"),
                file_name=f"costos_fijos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay costos fijos registrados")
    
    with tab2:
        with st.form("nuevo_costo"):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Concepto *", placeholder="Ej: Alquiler local")
                monto = st.number_input("Monto *", min_value=0.01, step=0.01)
                frecuencia = st.selectbox("Frecuencia *", ["mensual", "anual", "unico"])
            
            with col2:
                fecha_inicio = st.date_input("Fecha Inicio *", value=datetime.now().date())
                fecha_fin = st.date_input("Fecha Fin (opcional)", value=None)
                descripcion = st.text_area("Notas")
            
            if st.form_submit_button("✅ Registrar Costo"):
                if nombre and monto > 0:
                    nuevo_costo = {
                        'nombre': nombre,
                        'monto': monto,
                        'frecuencia': frecuencia,
                        'fecha_inicio': str(fecha_inicio),
                        'fecha_fin': str(fecha_fin) if fecha_fin else None,
                        'descripcion': descripcion
                    }
                    crear_costo_fijo(nuevo_costo)
                    st.success(f"✅ Costo '{nombre}' registrado")
                    st.rerun()
                else:
                    st.error("Completá los campos obligatorios")
    
    with tab3:
        costos = obtener_costos_fijos()
        if costos.empty:
            st.info("No hay costos para editar")
            return
        
        costo_seleccionado = st.selectbox(
            "Seleccionar costo",
            costos['id'].tolist(),
            format_func=lambda x: f"{costos[costos['id']==x]['nombre'].values[0]} - {formato_moneda(costos[costos['id']==x]['monto'].values[0])}"
        )
        
        if costo_seleccionado:
            costo = costos[costos['id']==costo_seleccionado].iloc[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("✏️ Editar")
                with st.form("editar_costo"):
                    nuevo_nombre = st.text_input("Concepto", value=costo['nombre'])
                    nuevo_monto = st.number_input("Monto", value=float(costo['monto']), step=0.01)
                    nueva_descripcion = st.text_area("Notas", value=costo['descripcion'] if costo['descripcion'] else "")
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        actualizar_costo_fijo(costo_seleccionado, {
                            'nombre': nuevo_nombre,
                            'monto': nuevo_monto,
                            'descripcion': nueva_descripcion
                        })
                        st.success("✅ Costo actualizado")
                        st.rerun()
            
            with col2:
                st.subheader("🗑️ Eliminar")
                st.warning(f"**Costo:** {costo['nombre']}")
                st.write(f"Monto: {formato_moneda(costo['monto'])}")
                st.write(f"Frecuencia: {costo['frecuencia']}")
                
                if st.button("🗑️ Eliminar Costo", type="secondary"):
                    eliminar_costo_fijo(costo_seleccionado)
                    st.success("✅ Costo eliminado")
                    st.rerun()

def pagina_proveedores():
    st.title("👥 Proveedores y Categorías")
    tab1, tab2 = st.tabs(["Proveedores", "Categorías"])
    
    with tab1:
        subtab1, subtab2, subtab3 = st.tabs(["📋 Lista", "➕ Nuevo", "✏️ Editar/Eliminar"])
        
        with subtab1:
            proveedores = obtener_proveedores()
            if not proveedores.empty:
                st.dataframe(
                    proveedores[['nombre', 'contacto', 'telefono']], 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("No hay proveedores registrados")
        
        with subtab2:
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
        
        with subtab3:
            proveedores = obtener_proveedores()
            if proveedores.empty:
                st.info("No hay proveedores")
                return
            
            prov_seleccionado = st.selectbox(
                "Seleccionar proveedor",
                proveedores['id'].tolist(),
                format_func=lambda x: proveedores[proveedores['id']==x]['nombre'].values[0],
                key="select_prov"
            )
            
            if prov_seleccionado:
                prov = proveedores[proveedores['id']==prov_seleccionado].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("✏️ Editar")
                    with st.form("editar_proveedor"):
                        nuevo_nombre = st.text_input("Nombre", value=prov['nombre'])
                        nuevo_contacto = st.text_input("Contacto", value=prov['contacto'] if prov['contacto'] else "")
                        nuevo_telefono = st.text_input("Teléfono", value=prov['telefono'] if prov['telefono'] else "")
                        
                        if st.form_submit_button("💾 Guardar"):
                            actualizar_proveedor(prov_seleccionado, {
                                'nombre': nuevo_nombre,
                                'contacto': nuevo_contacto,
                                'telefono': nuevo_telefono
                            })
                            st.success("✅ Proveedor actualizado")
                            st.rerun()
                
                with col2:
                    st.subheader("🗑️ Eliminar")
                    st.warning(f"**{prov['nombre']}**")
                    if st.button("🗑️ Eliminar Proveedor", key="del_prov"):
                        eliminar_proveedor(prov_seleccionado)
                        st.success("✅ Proveedor eliminado")
                        st.rerun()
    
    with tab2:
        subtab1, subtab2, subtab3 = st.tabs(["📋 Lista", "➕ Nueva", "✏️ Editar/Eliminar"])
        
        with subtab1:
            categorias = obtener_categorias()
            if not categorias.empty:
                st.dataframe(
                    categorias[['nombre', 'descripcion']], 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("No hay categorías registradas")
        
        with subtab2:
            with st.form("nueva_categoria"):
                nombre = st.text_input("Nombre")
                descripcion = st.text_area("Descripción")
                
                if st.form_submit_button("✅ Crear"):
                    if nombre:
                        crear_categoria(nombre, descripcion)
                        st.success("✅ Categoría creada")
                        st.rerun()
        
        with subtab3:
            categorias = obtener_categorias()
            if categorias.empty:
                st.info("No hay categorías")
                return
            
            cat_seleccionada = st.selectbox(
                "Seleccionar categoría",
                categorias['id'].tolist(),
                format_func=lambda x: categorias[categorias['id']==x]['nombre'].values[0],
                key="select_cat"
            )
            
            if cat_seleccionada:
                cat = categorias[categorias['id']==cat_seleccionada].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("✏️ Editar")
                    with st.form("editar_categoria"):
                        nuevo_nombre = st.text_input("Nombre", value=cat['nombre'])
                        nueva_descripcion = st.text_area("Descripción", value=cat['descripcion'] if cat['descripcion'] else "")
                        
                        if st.form_submit_button("💾 Guardar"):
                            actualizar_categoria(cat_seleccionada, {
                                'nombre': nuevo_nombre,
                                'descripcion': nueva_descripcion
                            })
                            st.success("✅ Categoría actualizada")
                            st.rerun()
                
                with col2:
                    st.subheader("🗑️ Eliminar")
                    st.warning(f"**{cat['nombre']}**")
                    st.write(f"{cat['descripcion']}")
                    if st.button("🗑️ Eliminar Categoría", key="del_cat"):
                        eliminar_categoria(cat_seleccionada)
                        st.success("✅ Categoría eliminada")
                        st.rerun()

# ============================================
# NAVEGACIÓN PRINCIPAL
# ============================================

def main():
    # Verificar si hay sesión activa
    if not verificar_sesion():
        pagina_login()
        return
    
    # Si hay sesión, mostrar app principal
    usuario = obtener_usuario_actual()
    
    with st.sidebar:
        st.title("📦 Sistema de Reventa")
        st.write(f"👤 {usuario['nombre']}")
        st.divider()
        
        pagina = st.radio(
            "Navegación",
            ["📊 Dashboard", "📦 Productos", "🛒 Compras", "💰 Ventas", "💸 Costos Fijos", "👥 Proveedores"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        if st.button("🚪 Cerrar Sesión"):
            cerrar_sesion()
        
        st.caption("v2.0.0")
    
    if pagina == "📊 Dashboard":
        pagina_dashboard()
    elif pagina == "📦 Productos":
        pagina_productos()
    elif pagina == "🛒 Compras":
        pagina_compras()
    elif pagina == "💰 Ventas":
        pagina_ventas()
    elif pagina == "💸 Costos Fijos":
        pagina_costos_fijos()
    elif pagina == "👥 Proveedores":
        pagina_proveedores()

if __name__ == "__main__":
    main()
