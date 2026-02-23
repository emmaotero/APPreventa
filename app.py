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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CARGAR CSS PERSONALIZADO
# ============================================
def cargar_css():
    """Carga el CSS personalizado para el diseño premium"""
    try:
        with open('style.css') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        # Si no encuentra el archivo, usar CSS inline básico
        st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
        """, unsafe_allow_html=True)

# Cargar estilos
cargar_css()

@st.cache_resource
def init_supabase() -> Client:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ============================================
# SISTEMA DE ROLES Y PERMISOS
# ============================================

def obtener_rol_usuario(email=None):
    """Obtiene el rol del usuario"""
    if not email:
        usuario = obtener_usuario_actual()
        if not usuario:
            return 'admin'
        email = usuario['email']
    
    # Primero buscar en usuarios principales
    response = supabase.table("usuarios").select("rol").eq("email", email).execute()
    if response.data:
        return response.data[0].get('rol', 'admin')
    
    # Si no está, buscar en usuarios_emprendimiento
    response = supabase.table("usuarios_emprendimiento").select("rol").eq("email", email).eq("activo", True).execute()
    if response.data:
        return response.data[0].get('rol', 'vendedor')
    
    return 'admin'  # Por defecto

def obtener_permisos_rol(rol):
    """Obtiene los permisos de un rol"""
    response = supabase.table("permisos_roles").select("permisos").eq("rol", rol).execute()
    if response.data:
        return response.data[0]['permisos']
    return {}

def tiene_permiso(permiso):
    """Verifica si el usuario actual tiene un permiso específico"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return False
    
    rol = obtener_rol_usuario(usuario['email'])
    permisos = obtener_permisos_rol(rol)
    
    return permisos.get(permiso, False)

def requiere_permiso(permiso, mensaje_error=None):
    """Función para requerir un permiso. Detiene ejecución si no lo tiene."""
    if not tiene_permiso(permiso):
        if mensaje_error:
            st.error(f"⛔ {mensaje_error}")
        else:
            st.error(f"⛔ No tenés permiso para realizar esta acción")
        st.info("💡 Contactá al administrador si necesitás acceso")
        st.stop()

def obtener_usuarios_emprendimiento():
    """Obtiene la lista de usuarios del emprendimiento actual"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    response = supabase.table("usuarios_emprendimiento").select("*").eq("usuario_principal_id", usuario['id']).order("nombre").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def agregar_usuario_emprendimiento(email, nombre, rol):
    """Agrega un usuario al emprendimiento"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    data = {
        'usuario_principal_id': usuario['id'],
        'email': email,
        'nombre': nombre,
        'rol': rol,
        'activo': True
    }
    
    return supabase.table("usuarios_emprendimiento").insert(data).execute().data

def actualizar_usuario_emprendimiento(usuario_emp_id, datos):
    """Actualiza un usuario del emprendimiento"""
    return supabase.table("usuarios_emprendimiento").update(datos).eq("id", usuario_emp_id).execute().data

def eliminar_usuario_emprendimiento(usuario_emp_id):
    """Elimina (desactiva) un usuario del emprendimiento"""
    return supabase.table("usuarios_emprendimiento").update({"activo": False}).eq("id", usuario_emp_id).execute().data

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
def obtener_productos(activos_solo=True, excluir_pausados=False):
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    query = supabase.table("productos").select("*, categorias(nombre), proveedores(nombre)").eq("usuario_id", usuario['id'])
    if activos_solo:
        query = query.eq("activo", True)
    if excluir_pausados:
        query = query.eq("pausado", False)
    response = query.execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_producto(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("productos").insert(datos).execute().data

def actualizar_producto(id_producto, datos):
    return supabase.table("productos").update(datos).eq("id", id_producto).execute().data

def eliminar_producto(id_producto, borrado_permanente=False):
    """
    Elimina un producto.
    Si borrado_permanente=True, lo borra de la BD.
    Si False, solo lo marca como inactivo.
    """
    if borrado_permanente:
        # Borrar permanentemente
        return supabase.table("productos").delete().eq("id", id_producto).execute().data
    else:
        # Solo marcar como inactivo
        return supabase.table("productos").update({"activo": False, "pausado": False}).eq("id", id_producto).execute().data

# --- IMPORTACIÓN MASIVA ---
def generar_template_importacion():
    """Genera un Excel template para importar productos"""
    template_data = {
        'nombre': ['Ejemplo: Coca Cola'],
        'marca': ['Coca Cola'],
        'categoria': ['Bebidas'],
        'variedad': ['Zero'],
        'presentacion': ['2.25 ltr'],
        'unidad': ['Unidad'],
        'precio_compra': [150.00],
        'stock_inicial': [10],
        'stock_minimo': [5],
        'proveedor': ['Distribuidora XX'],
        'ubicacion': ['Góndola A'],
        'detalle': ['Nota opcional'],
        'fecha_compra': ['2024-02-18']
    }
    
    df = pd.DataFrame(template_data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Productos', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Productos']
        
        # Formato para encabezados
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4CAF50',
            'font_color': 'white',
            'border': 1
        })
        
        # Formato para datos de ejemplo
        example_format = workbook.add_format({
            'bg_color': '#E8F5E9',
            'italic': True
        })
        
        # Aplicar formatos
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 18)
            worksheet.write(1, col_num, df.iloc[0, col_num], example_format)
        
        # Agregar instrucciones en otra hoja
        instrucciones = pd.DataFrame({
            'INSTRUCCIONES': [
                '1. Completá la hoja "Productos" con tus datos',
                '2. Campos OBLIGATORIOS: nombre, categoria, precio_compra',
                '3. Los demás campos son opcionales',
                '4. Si la categoría no existe, se creará automáticamente',
                '5. Si el proveedor no existe, se creará automáticamente',
                '6. Borrá la fila de ejemplo antes de importar',
                '7. La fecha debe estar en formato YYYY-MM-DD (ej: 2024-02-18)',
                '8. Unidades válidas: Unidad, kg, gr, ltr, ml, pack, caja, docena',
                '',
                'IMPORTANTE: No cambies los nombres de las columnas'
            ]
        })
        instrucciones.to_excel(writer, sheet_name='LEER PRIMERO', index=False)
        worksheet_inst = writer.sheets['LEER PRIMERO']
        worksheet_inst.set_column(0, 0, 60)
    
    return output.getvalue()

def validar_fila_importacion(fila, categorias_existentes, proveedores_existentes):
    """Valida una fila del Excel de importación"""
    errores = []
    
    # Validar campos obligatorios
    if pd.isna(fila.get('nombre')) or str(fila.get('nombre')).strip() == '':
        errores.append("Nombre es obligatorio")
    
    if pd.isna(fila.get('categoria')) or str(fila.get('categoria')).strip() == '':
        errores.append("Categoría es obligatoria")
    
    if pd.isna(fila.get('precio_compra')):
        errores.append("Precio de compra es obligatorio")
    else:
        try:
            float(fila.get('precio_compra'))
        except:
            errores.append("Precio de compra debe ser un número")
    
    # Validar stock si está presente
    if not pd.isna(fila.get('stock_inicial')):
        try:
            int(fila.get('stock_inicial'))
        except:
            errores.append("Stock inicial debe ser un número entero")
    
    return errores

def procesar_importacion_productos(df, usuario_id):
    """Procesa el DataFrame del Excel y carga los productos"""
    resultados = {
        'exitosos': 0,
        'errores': 0,
        'detalles': [],
        'categorias_creadas': [],
        'proveedores_creados': []
    }
    
    # Obtener categorías y proveedores existentes
    categorias_existentes = obtener_categorias()
    proveedores_existentes = obtener_proveedores()
    
    # Mapeos nombre -> id (usar nombre completo como clave)
    cat_map = {cat['nombre']: cat['id'] for _, cat in categorias_existentes.iterrows()} if not categorias_existentes.empty else {}
    prov_map = {prov['nombre']: prov['id'] for _, prov in proveedores_existentes.iterrows()} if not proveedores_existentes.empty else {}
    
    # IMPORTANTE: Registro de códigos ya usados en esta importación
    codigos_usados = set()
    
    for idx, fila in df.iterrows():
        # Saltar filas vacías
        if pd.isna(fila.get('nombre')):
            continue
        
        # Validar fila
        errores = validar_fila_importacion(fila, categorias_existentes, proveedores_existentes)
        if errores:
            resultados['errores'] += 1
            resultados['detalles'].append(f"Fila {idx + 2}: {', '.join(errores)}")
            continue
        
        try:
            # Procesar categoría
            categoria_nombre = str(fila['categoria']).strip()
            
            # Buscar si ya existe en el mapa (case-insensitive para evitar duplicados)
            categoria_id = None
            for nombre_existente, id_existente in cat_map.items():
                if nombre_existente.upper() == categoria_nombre.upper():
                    categoria_id = id_existente
                    break
            
            # Si no existe, crearla
            if not categoria_id:
                nueva_cat = crear_categoria(categoria_nombre, "")
                if nueva_cat:
                    cat_id = nueva_cat[0]['id']
                    cat_codigo = nueva_cat[0].get('codigo_categoria', '')
                    cat_map[categoria_nombre] = cat_id  # Agregar al mapa con nombre exacto
                    categoria_id = cat_id
                    resultados['categorias_creadas'].append(categoria_nombre)
                    
                    # Recargar categorías para tener la nueva
                    categorias_existentes = obtener_categorias()
            
            # Obtener código de categoría
            cat_actual = None
            for _, cat in categorias_existentes.iterrows():
                if cat['id'] == categoria_id:
                    cat_actual = cat
                    break
            
            if cat_actual is not None:
                codigo_cat = cat_actual.get('codigo_categoria', '')
                if not codigo_cat:
                    # Generar código para la categoría
                    codigo_cat = generar_codigo_categoria(categoria_nombre, categorias_existentes)
                    actualizar_categoria(categoria_id, {'codigo_categoria': codigo_cat})
            else:
                # Si por alguna razón no encontramos la categoría, generamos código genérico
                codigo_cat = generar_codigo_categoria(categoria_nombre, categorias_existentes)
            
            # Procesar proveedor (opcional)
            proveedor_id = None
            if not pd.isna(fila.get('proveedor')) and str(fila.get('proveedor')).strip() != '':
                proveedor_nombre = str(fila['proveedor']).strip()
                
                # Buscar si ya existe (case-insensitive)
                for nombre_existente, id_existente in prov_map.items():
                    if nombre_existente.upper() == proveedor_nombre.upper():
                        proveedor_id = id_existente
                        break
                
                # Si no existe, crearlo
                if not proveedor_id:
                    nuevo_prov = crear_proveedor({'nombre': proveedor_nombre})
                    if nuevo_prov:
                        prov_id = nuevo_prov[0]['id']
                        prov_map[proveedor_nombre] = prov_id
                        proveedor_id = prov_id
                        resultados['proveedores_creados'].append(proveedor_nombre)
            
            # Generar código con el código de categoría
            nombre_producto = str(fila['nombre']).strip()
            codigo = generar_codigo_producto(nombre_producto, codigo_cat, codigos_usados)
            
            # VERIFICAR SI EL PRODUCTO YA EXISTE (solo productos activos)
            productos_existentes = obtener_productos(activos_solo=True)
            producto_existente = None
            
            if not productos_existentes.empty:
                # Buscar por código
                producto_por_codigo = productos_existentes[productos_existentes['codigo'] == codigo]
                if not producto_por_codigo.empty:
                    producto_existente = producto_por_codigo.iloc[0]
                else:
                    # Buscar por nombre + categoría (por si cambió el código)
                    productos_misma_cat = productos_existentes[productos_existentes['categoria_id'] == categoria_id]
                    if not productos_misma_cat.empty:
                        producto_por_nombre = productos_misma_cat[
                            productos_misma_cat['nombre'].str.upper() == nombre_producto.upper()
                        ]
                        if not producto_por_nombre.empty:
                            producto_existente = producto_por_nombre.iloc[0]
            
            # Preparar datos del producto
            producto_data = {
                'codigo': codigo,
                'nombre': nombre_producto,
                'categoria_id': categoria_id,
                'proveedor_id': proveedor_id,
                'marca': str(fila['marca']).strip() if not pd.isna(fila.get('marca')) else None,
                'variedad': str(fila['variedad']).strip() if not pd.isna(fila.get('variedad')) else None,
                'presentacion': str(fila['presentacion']).strip() if not pd.isna(fila.get('presentacion')) else None,
                'unidad': str(fila['unidad']).strip() if not pd.isna(fila.get('unidad')) else 'Unidad',
                'ubicacion': str(fila['ubicacion']).strip() if not pd.isna(fila.get('ubicacion')) else None,
                'detalle': str(fila['detalle']).strip() if not pd.isna(fila.get('detalle')) else None,
                'precio_compra': float(fila['precio_compra']),
                'stock_actual': 0,  # IMPORTANTE: Empezar en 0, la compra lo suma
                'stock_minimo': int(fila['stock_minimo']) if not pd.isna(fila.get('stock_minimo')) else 0,
                'usuario_id': usuario_id
            }
            
            # Guardar el stock inicial por separado
            stock_inicial = int(fila['stock_inicial']) if not pd.isna(fila.get('stock_inicial')) else 0
            
            # Si el producto existe, actualizarlo en vez de crearlo
            if producto_existente is not None:
                # Actualizar producto existente
                actualizar_producto(producto_existente['id'], {
                    'precio_compra': producto_data['precio_compra'],
                    'stock_minimo': producto_data['stock_minimo'],
                    'marca': producto_data['marca'],
                    'variedad': producto_data['variedad'],
                    'presentacion': producto_data['presentacion'],
                    'unidad': producto_data['unidad'],
                    'ubicacion': producto_data['ubicacion'],
                    'detalle': producto_data['detalle'],
                    'activo': True  # Reactivar si estaba inactivo
                })
                
                # Si tiene stock inicial, agregar al stock actual
                if stock_inicial > 0:
                    # Sumar al stock existente
                    nuevo_stock = int(producto_existente['stock_actual']) + stock_inicial
                    actualizar_producto(producto_existente['id'], {'stock_actual': nuevo_stock})
                    
                    # Registrar compra
                    fecha_compra = str(fila['fecha_compra']) if not pd.isna(fila.get('fecha_compra')) else str(datetime.now().date())
                    registrar_compra({
                        'producto_id': producto_existente['id'],
                        'cantidad': stock_inicial,
                        'precio_unitario': producto_data['precio_compra'],
                        'fecha': fecha_compra,
                        'usuario_id': usuario_id
                    })
                
                resultados['exitosos'] += 1
                resultados['detalles'].append(f"✅ {nombre_producto} ({codigo}) - ACTUALIZADO")
            else:
                # Crear producto nuevo
                producto_creado_data = crear_producto(producto_data)
                
                # Si tiene stock inicial, registrar la compra (que suma al stock)
                if stock_inicial > 0 and producto_creado_data:
                    fecha_compra = str(fila['fecha_compra']) if not pd.isna(fila.get('fecha_compra')) else str(datetime.now().date())
                    
                    # Usar el ID del producto recién creado
                    producto_id_creado = producto_creado_data[0]['id']
                    
                    registrar_compra({
                        'producto_id': producto_id_creado,
                        'cantidad': stock_inicial,
                        'precio_unitario': producto_data['precio_compra'],
                        'fecha': fecha_compra,
                        'usuario_id': usuario_id
                    })
                
                resultados['exitosos'] += 1
                resultados['detalles'].append(f"✅ {nombre_producto} ({codigo}) - CREADO")
            
        except Exception as e:
            resultados['errores'] += 1
            resultados['detalles'].append(f"❌ Fila {idx + 2} ({fila.get('nombre', 'Sin nombre')}): {str(e)}")
    
    return resultados

# --- COMPRAS ---
def registrar_compra(datos):
    usuario = obtener_usuario_actual()
    if usuario:
        datos['usuario_id'] = usuario['id']
    return supabase.table("compras").insert(datos).execute().data

def eliminar_compra(id_compra):
    """Elimina una compra - OJO: no revierte el stock automáticamente"""
    return supabase.table("compras").delete().eq("id", id_compra).execute().data

# --- AJUSTES DE INVENTARIO ---
def registrar_ajuste_inventario(producto_id, cantidad_nueva, motivo, notas=""):
    """Registra un ajuste manual de inventario"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    # Obtener stock actual
    producto = supabase.table("productos").select("stock_actual").eq("id", producto_id).execute().data
    if not producto:
        return None
    
    cantidad_anterior = producto[0]['stock_actual']
    diferencia = cantidad_nueva - cantidad_anterior
    
    # Registrar ajuste
    ajuste_data = {
        'producto_id': producto_id,
        'usuario_id': usuario['id'],
        'cantidad_anterior': cantidad_anterior,
        'cantidad_nueva': cantidad_nueva,
        'diferencia': diferencia,
        'motivo': motivo,
        'notas': notas,
        'fecha': str(datetime.now().date())
    }
    
    response = supabase.table("ajustes_inventario").insert(ajuste_data).execute()
    
    # Actualizar stock del producto
    supabase.table("productos").update({"stock_actual": cantidad_nueva}).eq("id", producto_id).execute()
    
    return response.data

def obtener_ajustes_producto(producto_id):
    """Obtiene el historial de ajustes de un producto"""
    response = supabase.table("ajustes_inventario").select("*").eq("producto_id", producto_id).order("created_at", desc=True).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

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
    query = supabase.table("ventas").select("*, productos(nombre, codigo), clientes(dni, nombre)").eq("usuario_id", usuario['id']).order("fecha", desc=True)
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
    
    # Obtener categorías existentes para evitar duplicados de código
    categorias_existentes = obtener_categorias()
    
    # Generar código único
    codigo_categoria = generar_codigo_categoria(nombre, categorias_existentes)
    
    return supabase.table("categorias").insert({
        "nombre": nombre, 
        "descripcion": descripcion,
        "codigo_categoria": codigo_categoria,
        "usuario_id": usuario['id']
    }).execute().data

def actualizar_categoria(id_categoria, datos):
    return supabase.table("categorias").update(datos).eq("id", id_categoria).execute().data

def eliminar_categoria(id_categoria):
    return supabase.table("categorias").delete().eq("id", id_categoria).execute().data

def generar_codigo_categoria(nombre_categoria, categorias_existentes):
    """Genera código de categoría único tomando letras significativas"""
    # Limpiar y separar palabras
    palabras = nombre_categoria.upper().replace('-', ' ').replace('_', ' ').split()
    
    # Filtrar palabras comunes poco significativas
    palabras_ignorar = ['PARA', 'DE', 'LA', 'EL', 'LOS', 'LAS', 'Y', 'A', 'EN']
    palabras_significativas = [p for p in palabras if p not in palabras_ignorar and len(p) > 1]
    
    if not palabras_significativas:
        palabras_significativas = palabras
    
    # Estrategia 1: Primeras 2-3 letras de las primeras 2 palabras más significativas
    if len(palabras_significativas) >= 2:
        codigo = palabras_significativas[0][:3] + palabras_significativas[1][:3]
    elif len(palabras_significativas) == 1:
        codigo = palabras_significativas[0][:6]
    else:
        codigo = ''.join(palabras)[:6]
    
    codigo = codigo.upper()
    
    # Verificar si ya existe en categorías del usuario
    codigos_existentes = []
    if not categorias_existentes.empty:
        for _, cat in categorias_existentes.iterrows():
            if 'codigo_categoria' in cat and cat['codigo_categoria']:
                codigos_existentes.append(cat['codigo_categoria'].upper())
    
    # Si el código ya existe, agregar más letras
    if codigo in codigos_existentes:
        # Intentar con más caracteres
        for longitud in range(len(codigo) + 1, 10):
            texto_completo = ''.join(palabras_significativas)
            nuevo_codigo = texto_completo[:longitud].upper()
            if nuevo_codigo not in codigos_existentes:
                codigo = nuevo_codigo
                break
        
        # Si aún así hay conflicto, agregar número
        if codigo in codigos_existentes:
            contador = 1
            while f"{codigo}{contador}" in codigos_existentes:
                contador += 1
            codigo = f"{codigo}{contador}"
    
    return codigo[:8]  # Máximo 8 caracteres

def generar_codigo_producto(nombre_producto, codigo_categoria, codigos_ya_usados=None):
    """Genera código único del producto: TABNAT-0001"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    # Si no se pasa lista de códigos usados, crear una vacía
    if codigos_ya_usados is None:
        codigos_ya_usados = set()
    
    # Obtener productos ACTIVOS de esa categoría para el contador
    productos_cat = obtener_productos(activos_solo=True)
    
    # Contar cuántos códigos existen con este prefijo
    contador = 0
    if not productos_cat.empty and 'codigo' in productos_cat.columns:
        for _, prod in productos_cat.iterrows():
            if prod.get('codigo') and prod['codigo'].startswith(codigo_categoria + '-'):
                contador += 1
    
    # También contar los códigos generados en esta sesión
    contador += len([c for c in codigos_ya_usados if c.startswith(codigo_categoria + '-')])
    
    # Generar código único
    while True:
        contador += 1
        codigo = f"{codigo_categoria}-{contador:04d}"
        
        # Verificar que no exista en la BD ni en los recién generados
        existe_en_bd = False
        if not productos_cat.empty:
            existe_en_bd = (productos_cat['codigo'] == codigo).any()
        
        if not existe_en_bd and codigo not in codigos_ya_usados:
            codigos_ya_usados.add(codigo)
            return codigo
        
        # Si existe, incrementar y reintentar
        if contador > 9999:  # Límite de seguridad
            return f"{codigo_categoria}-{hash(nombre_producto) % 10000:04d}"

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

# --- LISTA DE PRECIOS ---
def obtener_lista_precios():
    """Obtiene lista de precios con datos calculados"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    # Obtener productos activos
    productos = obtener_productos(activos_solo=True)
    if productos.empty:
        return pd.DataFrame()
    
    # Obtener lista de precios existente
    response = supabase.table("lista_precios").select("*").eq("usuario_id", usuario['id']).execute()
    lista_precios = pd.DataFrame(response.data) if response.data else pd.DataFrame()
    
    # Crear DataFrame con todos los productos
    resultado = []
    for _, prod in productos.iterrows():
        precio_costo = float(prod['precio_compra'])
        
        # Buscar si tiene precio en lista
        if not lista_precios.empty and prod['id'] in lista_precios['producto_id'].values:
            precio_data = lista_precios[lista_precios['producto_id'] == prod['id']].iloc[0]
            margen_teorico = float(precio_data['margen_teorico'])
            precio_final = float(precio_data['precio_final']) if precio_data['precio_final'] else None
        else:
            margen_teorico = 30.0  # Default
            precio_final = None
        
        # Calcular precio sugerido
        precio_sugerido = round(precio_costo * (1 + margen_teorico / 100), 2)
        
        # Calcular margen real si hay precio final
        if precio_final:
            margen_real = round(((precio_final - precio_costo) / precio_costo) * 100, 2) if precio_costo > 0 else 0
        else:
            margen_real = margen_teorico
            precio_final = precio_sugerido
        
        resultado.append({
            'producto_id': prod['id'],
            'codigo': prod['codigo'],
            'nombre': prod['nombre'],
            'precio_costo': precio_costo,
            'margen_teorico': margen_teorico,
            'precio_sugerido': precio_sugerido,
            'precio_final': precio_final,
            'margen_real': margen_real
        })
    
    return pd.DataFrame(resultado)

def guardar_precio(producto_id, margen_teorico, precio_final):
    """Guarda o actualiza el precio de un producto"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    # Verificar si ya existe
    response = supabase.table("lista_precios").select("*").eq("producto_id", producto_id).eq("usuario_id", usuario['id']).execute()
    
    datos = {
        'margen_teorico': margen_teorico,
        'precio_final': precio_final
    }
    
    if response.data and len(response.data) > 0:
        # Actualizar
        return supabase.table("lista_precios").update(datos).eq("producto_id", producto_id).eq("usuario_id", usuario['id']).execute().data
    else:
        # Crear
        datos['producto_id'] = producto_id
        datos['usuario_id'] = usuario['id']
        return supabase.table("lista_precios").insert(datos).execute().data

# --- CLIENTES ---
def buscar_cliente_por_dni(dni):
    """Busca un cliente por DNI"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    response = supabase.table("clientes").select("*").eq("dni", dni).eq("usuario_id", usuario['id']).execute()
    return response.data[0] if response.data else None

def buscar_clientes(termino):
    """Busca clientes por DNI, nombre o teléfono"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    # Buscar por múltiples campos
    response = supabase.table("clientes").select("*").eq("usuario_id", usuario['id']).or_(
        f"dni.ilike.%{termino}%,nombre.ilike.%{termino}%,telefono.ilike.%{termino}%"
    ).limit(10).execute()
    
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def crear_cliente(datos):
    """Crea un nuevo cliente"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return None
    
    datos['usuario_id'] = usuario['id']
    return supabase.table("clientes").insert(datos).execute().data

def actualizar_cliente(cliente_id, datos):
    """Actualiza un cliente existente"""
    return supabase.table("clientes").update(datos).eq("id", cliente_id).execute().data

def obtener_clientes():
    """Obtiene todos los clientes del usuario"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    response = supabase.table("clientes").select("*").eq("usuario_id", usuario['id']).order("nombre").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def obtener_clientes_frecuentes():
    """Obtiene clientes frecuentes (vista)"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    response = supabase.table("vista_clientes_frecuentes").select("*").eq("usuario_id", usuario['id']).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def obtener_clientes_inactivos():
    """Obtiene clientes inactivos (más de 30 días sin comprar)"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    response = supabase.table("vista_clientes_inactivos").select("*").eq("usuario_id", usuario['id']).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

def obtener_historial_cliente(cliente_id):
    """Obtiene el historial de compras de un cliente"""
    response = supabase.table("ventas").select("*, productos(nombre, codigo)").eq("cliente_id", cliente_id).order("fecha", desc=True).execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()

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
    
    # Productos con stock (los que realmente cuentan)
    productos_con_stock = productos[productos['stock_actual'] > 0] if not productos.empty else pd.DataFrame()
    total_con_stock = len(productos_con_stock)
    
    # Valor de stock a precio de costo (solo productos con stock)
    valor_stock = (productos_con_stock['stock_actual'] * productos_con_stock['precio_compra']).sum() if not productos_con_stock.empty else 0
    
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
        'total_con_stock': total_con_stock,
        'valor_stock': valor_stock,
        'ingresos_mes': ingresos_mes,
        'ganancia_bruta_mes': ganancia_bruta_mes,
        'ganancia_neta_mes': ganancia_neta_mes,
        'costos_fijos_mes': costos_fijos_mes,
        'cantidad_ventas_mes': cantidad_ventas_mes,
        'alertas_stock': alertas_stock
    }

def obtener_productos_mas_vendidos(limite=5):
    """Obtiene los productos más vendidos del mes"""
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    ventas = obtener_ventas(fecha_desde=str(inicio_mes))
    
    if ventas.empty:
        return pd.DataFrame()
    
    # Agrupar por producto
    ventas_agrupadas = ventas.groupby('producto_id').agg({
        'cantidad': 'sum',
        'subtotal': 'sum',
        'ganancia': 'sum'
    }).reset_index()
    
    # Ordenar por cantidad vendida
    ventas_agrupadas = ventas_agrupadas.sort_values('cantidad', ascending=False).head(limite)
    
    # Obtener nombres de productos
    productos = obtener_productos(activos_solo=False)
    if not productos.empty:
        ventas_agrupadas = ventas_agrupadas.merge(
            productos[['id', 'nombre', 'codigo']], 
            left_on='producto_id', 
            right_on='id', 
            how='left'
        )
    
    return ventas_agrupadas

def obtener_productos_sin_movimiento(dias=30):
    """Obtiene productos que no se han vendido en X días"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    fecha_limite = (datetime.now() - timedelta(days=dias)).date()
    
    # Obtener todos los productos activos
    productos = obtener_productos()
    if productos.empty:
        return pd.DataFrame()
    
    # Obtener ventas recientes
    ventas = obtener_ventas(fecha_desde=str(fecha_limite))
    
    if ventas.empty:
        # Todos los productos sin movimiento
        return productos[['codigo', 'nombre', 'stock_actual']]
    
    # Productos que SÍ se vendieron
    productos_vendidos = ventas['producto_id'].unique()
    
    # Filtrar productos sin ventas
    sin_movimiento = productos[~productos['id'].isin(productos_vendidos)]
    
    return sin_movimiento[['codigo', 'nombre', 'stock_actual']] if not sin_movimiento.empty else pd.DataFrame()
    sin_movimiento = productos[~productos['id'].isin(productos_vendidos)]
    
    return sin_movimiento[['codigo', 'nombre', 'stock_actual']] if not sin_movimiento.empty else pd.DataFrame()

def obtener_ventas_por_dia(dias=30):
    """Obtiene ventas agrupadas por día para gráficos"""
    fecha_desde = (datetime.now() - timedelta(days=dias)).date()
    ventas = obtener_ventas(fecha_desde=str(fecha_desde))
    
    if ventas.empty:
        return pd.DataFrame()
    
    # Agrupar por fecha
    ventas_por_dia = ventas.groupby('fecha').agg({
        'subtotal': 'sum',
        'ganancia': 'sum',
        'id': 'count'
    }).reset_index()
    
    ventas_por_dia.columns = ['fecha', 'ingresos', 'ganancia', 'cantidad_ventas']
    
    return ventas_por_dia

def obtener_ventas_por_dia_periodo(fecha_desde, fecha_hasta):
    """Obtiene ventas agrupadas por día para un período específico"""
    ventas = obtener_ventas(fecha_desde=str(fecha_desde), fecha_hasta=str(fecha_hasta))
    
    if ventas.empty:
        return pd.DataFrame()
    
    # Agrupar por fecha
    ventas_por_dia = ventas.groupby('fecha').agg({
        'subtotal': 'sum',
        'ganancia': 'sum',
        'id': 'count'
    }).reset_index()
    
    ventas_por_dia.columns = ['fecha', 'ingresos', 'ganancia', 'cantidad_ventas']
    
    return ventas_por_dia

def obtener_productos_mas_vendidos_periodo(fecha_desde, fecha_hasta, limite=5):
    """Obtiene los productos más vendidos de un período específico"""
    ventas = obtener_ventas(fecha_desde=str(fecha_desde), fecha_hasta=str(fecha_hasta))
    
    if ventas.empty:
        return pd.DataFrame()
    
    # Agrupar por producto
    ventas_agrupadas = ventas.groupby('producto_id').agg({
        'cantidad': 'sum',
        'subtotal': 'sum',
        'ganancia': 'sum'
    }).reset_index()
    
    # Ordenar por cantidad vendida
    ventas_agrupadas = ventas_agrupadas.sort_values('cantidad', ascending=False).head(limite)
    
    # Obtener nombres de productos
    productos = obtener_productos(activos_solo=False)
    if not productos.empty:
        ventas_agrupadas = ventas_agrupadas.merge(
            productos[['id', 'nombre', 'codigo']], 
            left_on='producto_id', 
            right_on='id', 
            how='left'
        )
    
    return ventas_agrupadas

def obtener_ventas_por_categoria_periodo(fecha_desde, fecha_hasta):
    """Obtiene ventas agrupadas por categoría para un período específico"""
    ventas = obtener_ventas(fecha_desde=str(fecha_desde), fecha_hasta=str(fecha_hasta))
    
    if ventas.empty:
        return pd.DataFrame()
    
    # Obtener productos con categoría
    productos = obtener_productos(activos_solo=False)
    if productos.empty:
        return pd.DataFrame()
    
    # Merge ventas con productos
    ventas_con_categoria = ventas.merge(
        productos[['id', 'categorias']], 
        left_on='producto_id', 
        right_on='id', 
        how='left'
    )
    
    # Extraer nombre de categoría
    ventas_con_categoria['categoria'] = ventas_con_categoria['categorias'].apply(
        lambda x: x['nombre'] if x else 'Sin categoría'
    )
    
    # Agrupar por categoría
    por_categoria = ventas_con_categoria.groupby('categoria').agg({
        'subtotal': 'sum',
        'ganancia': 'sum'
    }).reset_index()
    
    return por_categoria.sort_values('subtotal', ascending=False)

def obtener_productos_sin_movimiento_periodo(fecha_desde, fecha_hasta):
    """Obtiene productos que no se han vendido en un período específico"""
    usuario = obtener_usuario_actual()
    if not usuario:
        return pd.DataFrame()
    
    # Obtener todos los productos activos
    productos = obtener_productos()
    if productos.empty:
        return pd.DataFrame()
    
    # Obtener ventas del período
    ventas = obtener_ventas(fecha_desde=str(fecha_desde), fecha_hasta=str(fecha_hasta))
    
    if ventas.empty:
        # Todos los productos sin movimiento
        return productos[['codigo', 'nombre', 'stock_actual']]
    
    # Productos que SÍ se vendieron
    productos_vendidos = ventas['producto_id'].unique()
    
    # Filtrar productos sin ventas
    sin_movimiento = productos[~productos['id'].isin(productos_vendidos)]
    
    return sin_movimiento[['codigo', 'nombre', 'stock_actual']] if not sin_movimiento.empty else pd.DataFrame()

def obtener_ventas_por_categoria():
    """Obtiene ventas del mes agrupadas por categoría"""
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    ventas = obtener_ventas(fecha_desde=str(inicio_mes))
    
    if ventas.empty:
        return pd.DataFrame()
    
    # Obtener productos con categoría
    productos = obtener_productos(activos_solo=False)
    if productos.empty:
        return pd.DataFrame()
    
    # Merge ventas con productos
    ventas_con_categoria = ventas.merge(
        productos[['id', 'categorias']], 
        left_on='producto_id', 
        right_on='id', 
        how='left'
    )
    
    # Extraer nombre de categoría
    ventas_con_categoria['categoria'] = ventas_con_categoria['categorias'].apply(
        lambda x: x['nombre'] if x else 'Sin categoría'
    )
    
    # Agrupar por categoría
    por_categoria = ventas_con_categoria.groupby('categoria').agg({
        'subtotal': 'sum',
        'ganancia': 'sum'
    }).reset_index()
    
    return por_categoria.sort_values('subtotal', ascending=False)

def obtener_metricas_clientes():
    """Obtiene métricas de clientes"""
    clientes = obtener_clientes()
    
    if clientes.empty:
        return {
            'total_clientes': 0,
            'clientes_con_compras': 0,
            'clientes_nuevos_mes': 0,
            'ticket_promedio_cliente': 0
        }
    
    total_clientes = len(clientes)
    clientes_con_compras = len(clientes[clientes['total_compras'] > 0])
    
    # Clientes nuevos este mes
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    clientes_nuevos = len(clientes[pd.to_datetime(clientes['created_at']).dt.date >= inicio_mes])
    
    # Ticket promedio
    if clientes_con_compras > 0:
        ticket_promedio = clientes['total_gastado'].sum() / clientes['total_compras'].sum()
    else:
        ticket_promedio = 0
    
    return {
        'total_clientes': total_clientes,
        'clientes_con_compras': clientes_con_compras,
        'clientes_nuevos_mes': clientes_nuevos,
        'ticket_promedio_cliente': ticket_promedio
    }

def obtener_comparativa_mes_anterior():
    """Compara métricas del mes actual con el anterior"""
    hoy = datetime.now().date()
    inicio_mes_actual = hoy.replace(day=1)
    
    # Mes anterior
    if inicio_mes_actual.month == 1:
        inicio_mes_anterior = inicio_mes_actual.replace(year=inicio_mes_actual.year - 1, month=12)
    else:
        inicio_mes_anterior = inicio_mes_actual.replace(month=inicio_mes_actual.month - 1)
    
    fin_mes_anterior = inicio_mes_actual - timedelta(days=1)
    
    # Ventas mes actual
    ventas_actual = obtener_ventas(fecha_desde=str(inicio_mes_actual))
    ingresos_actual = ventas_actual['subtotal'].sum() if not ventas_actual.empty else 0
    ganancia_actual = ventas_actual['ganancia'].sum() if not ventas_actual.empty else 0
    
    # Ventas mes anterior
    ventas_anterior = obtener_ventas(fecha_desde=str(inicio_mes_anterior), fecha_hasta=str(fin_mes_anterior))
    ingresos_anterior = ventas_anterior['subtotal'].sum() if not ventas_anterior.empty else 0
    ganancia_anterior = ventas_anterior['ganancia'].sum() if not ventas_anterior.empty else 0
    
    # Calcular variación
    if ingresos_anterior > 0:
        variacion_ingresos = ((ingresos_actual - ingresos_anterior) / ingresos_anterior) * 100
    else:
        variacion_ingresos = 100 if ingresos_actual > 0 else 0
    
    if ganancia_anterior > 0:
        variacion_ganancia = ((ganancia_actual - ganancia_anterior) / ganancia_anterior) * 100
    else:
        variacion_ganancia = 100 if ganancia_actual > 0 else 0
    
    return {
        'ingresos_actual': ingresos_actual,
        'ingresos_anterior': ingresos_anterior,
        'variacion_ingresos': variacion_ingresos,
        'ganancia_actual': ganancia_actual,
        'ganancia_anterior': ganancia_anterior,
        'variacion_ganancia': variacion_ganancia
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
    # Banner de bienvenida
    usuario = obtener_usuario_actual()
    if usuario:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
            border: 1px solid #1e40af;
        ">
            <h1 style="color: white; margin: 0; font-size: 2rem; font-weight: 700;">
                👋 Hola, {usuario['nombre']}
            </h1>
            <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
                Bienvenido a tu panel de control • <span style="color: #f97316; font-weight: 600;">Sistema de Reventa</span>
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.title("📊 Dashboard")
    
    # === FILTROS GLOBALES ===
    st.sidebar.subheader("🔍 Filtros de Período")
    
    # Opciones rápidas
    periodo_rapido = st.sidebar.selectbox(
        "Período rápido",
        ["Personalizado", "Últimos 7 días", "Últimos 30 días", "Este mes", "Mes pasado", "Últimos 3 meses", "Este año"],
        key="periodo_selector"
    )
    
    hoy = datetime.now().date()
    
    # Calcular fechas según período seleccionado
    if periodo_rapido == "Últimos 7 días":
        fecha_desde_default = hoy - timedelta(days=7)
        fecha_hasta_default = hoy
    elif periodo_rapido == "Últimos 30 días":
        fecha_desde_default = hoy - timedelta(days=30)
        fecha_hasta_default = hoy
    elif periodo_rapido == "Este mes":
        fecha_desde_default = hoy.replace(day=1)
        fecha_hasta_default = hoy
    elif periodo_rapido == "Mes pasado":
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
        fecha_desde_default = ultimo_dia_mes_pasado.replace(day=1)
        fecha_hasta_default = ultimo_dia_mes_pasado
    elif periodo_rapido == "Últimos 3 meses":
        fecha_desde_default = hoy - timedelta(days=90)
        fecha_hasta_default = hoy
    elif periodo_rapido == "Este año":
        fecha_desde_default = hoy.replace(month=1, day=1)
        fecha_hasta_default = hoy
    else:  # Personalizado
        fecha_desde_default = hoy - timedelta(days=30)
        fecha_hasta_default = hoy
    
    # Mostrar siempre los controles de fecha
    st.sidebar.write("**Ajustar fechas:**")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        fecha_desde = st.date_input(
            "Desde", 
            value=fecha_desde_default, 
            key="dash_desde",
            max_value=hoy
        )
    with col2:
        fecha_hasta = st.date_input(
            "Hasta", 
            value=fecha_hasta_default, 
            key="dash_hasta",
            max_value=hoy
        )
    
    st.sidebar.info(f"📅 Analizando: {fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}")
    
    tab1, tab2, tab3 = st.tabs(["📈 Resumen General", "🛒 Análisis de Ventas", "👥 Análisis de Clientes"])
    
    with tab1:
        # === MÉTRICAS PRINCIPALES ===
        metricas = obtener_metricas_dashboard()
        comparativa = obtener_comparativa_mes_anterior()
        
        # Obtener ventas del período seleccionado
        ventas_periodo = obtener_ventas(fecha_desde=str(fecha_desde), fecha_hasta=str(fecha_hasta))
        
        if not ventas_periodo.empty:
            ingresos_periodo = ventas_periodo['subtotal'].sum()
            ganancia_periodo = ventas_periodo['ganancia'].sum()
            cantidad_ventas = len(ventas_periodo)
            ticket_promedio = ingresos_periodo / cantidad_ventas if cantidad_ventas > 0 else 0
        else:
            ingresos_periodo = ganancia_periodo = cantidad_ventas = ticket_promedio = 0
        
        st.subheader(f"💰 Desempeño del Período ({fecha_desde.strftime('%d/%m')} - {fecha_hasta.strftime('%d/%m')})")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Ingresos", 
                formato_moneda(ingresos_periodo),
                delta=f"{cantidad_ventas} ventas"
            )
        
        with col2:
            st.metric(
                "Ganancia Bruta", 
                formato_moneda(ganancia_periodo)
            )
        
        with col3:
            # Calcular costos fijos proporcionales al período
            dias_periodo = (fecha_hasta - fecha_desde).days + 1
            costos_periodo = (metricas['costos_fijos_mes'] / 30) * dias_periodo
            ganancia_neta = ganancia_periodo - costos_periodo
            
            st.metric(
                "Ganancia Neta", 
                formato_moneda(ganancia_neta)
            )
        
        with col4:
            st.metric("Ticket Promedio", formato_moneda(ticket_promedio))
        
        st.divider()
        
        # === INVENTARIO Y COSTOS ===
        st.subheader("📦 Inventario y Costos")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Productos con Stock", metricas["total_con_stock"], delta=f"{metricas['total_productos']} total")
        
        with col2:
            st.metric("Valor del Stock", formato_moneda(metricas['valor_stock']))
        
        with col3:
            st.metric("Costos Fijos/Mes", formato_moneda(metricas['costos_fijos_mes']))
        
        with col4:
            if ganancia_periodo > 0:
                margen = (ganancia_neta / ganancia_periodo * 100)
                st.metric("Margen Neto", f"{margen:.1f}%")
            else:
                st.metric("Margen Neto", "0%")
        
        st.divider()
        
        # === GRÁFICO DE VENTAS ===
        dias_grafico = (fecha_hasta - fecha_desde).days + 1
        st.subheader(f"📊 Evolución de Ventas ({dias_grafico} días)")
        ventas_por_dia = obtener_ventas_por_dia_periodo(fecha_desde, fecha_hasta)
        
        if not ventas_por_dia.empty:
            import plotly.express as px
            
            fig = px.line(
                ventas_por_dia, 
                x='fecha', 
                y='ingresos',
                title='Ingresos Diarios',
                labels={'fecha': 'Fecha', 'ingresos': 'Ingresos ($)'}
            )
            fig.update_traces(line_color='#1f77b4', line_width=3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True, key="grafico_evolucion_ventas")
        else:
            st.info("No hay ventas en el período seleccionado")
        
        st.divider()
        
        # === ALERTAS ===
        if metricas['alertas_stock'] > 0:
            st.warning(f"⚠️ **{metricas['alertas_stock']} productos** con stock bajo del mínimo")
            with st.expander("Ver productos con stock bajo"):
                stock_bajo = obtener_stock_bajo()
                st.dataframe(
                    stock_bajo[['codigo', 'nombre', 'stock_actual', 'stock_minimo']], 
                    use_container_width=True, 
                    hide_index=True
                )
        
        # Productos pausados
        productos_pausados = obtener_productos(activos_solo=False)
        if not productos_pausados.empty:
            pausados = productos_pausados[productos_pausados.get('pausado', False) == True]
            if not pausados.empty:
                st.info(f"⏸️ Tenés **{len(pausados)} productos pausados**")
    
    with tab2:
        st.subheader(f"🛒 Análisis de Ventas ({fecha_desde.strftime('%d/%m')} - {fecha_hasta.strftime('%d/%m')})")
        
        # === TOP PRODUCTOS ===
        st.write("**🏆 Top 5 Productos Más Vendidos**")
        top_productos = obtener_productos_mas_vendidos_periodo(fecha_desde, fecha_hasta, 5)
        
        if not top_productos.empty:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(
                    top_productos[['codigo', 'nombre', 'cantidad', 'subtotal', 'ganancia']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "codigo": "Código",
                        "nombre": "Producto",
                        "cantidad": st.column_config.NumberColumn("Unidades", format="%d"),
                        "subtotal": st.column_config.NumberColumn("Ingresos", format="$%.2f"),
                        "ganancia": st.column_config.NumberColumn("Ganancia", format="$%.2f")
                    }
                )
            
            with col2:
                import plotly.express as px
                fig = px.pie(
                    top_productos, 
                    values='subtotal', 
                    names='nombre',
                    title='Ingresos por Producto'
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key="grafico_pie_top_productos")
        else:
            st.info("No hay ventas en el período seleccionado")
        
        st.divider()
        
        # === VENTAS POR CATEGORÍA ===
        st.write("**📊 Ventas por Categoría**")
        ventas_categoria = obtener_ventas_por_categoria_periodo(fecha_desde, fecha_hasta)
        
        if not ventas_categoria.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.dataframe(
                    ventas_categoria,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "categoria": "Categoría",
                        "subtotal": st.column_config.NumberColumn("Ingresos", format="$%.2f"),
                        "ganancia": st.column_config.NumberColumn("Ganancia", format="$%.2f")
                    }
                )
            
            with col2:
                import plotly.express as px
                fig = px.bar(
                    ventas_categoria, 
                    x='categoria', 
                    y='subtotal',
                    title='Ingresos por Categoría',
                    labels={'categoria': 'Categoría', 'subtotal': 'Ingresos ($)'}
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True, key="grafico_bar_categoria_tab2")
        else:
            st.info("No hay ventas por categoría")
        
        st.divider()
        
        # === PRODUCTOS SIN MOVIMIENTO ===
        dias_sin_mov = (fecha_hasta - fecha_desde).days + 1
        st.write(f"**💤 Productos Sin Movimiento (Últimos {dias_sin_mov} días)**")
        sin_movimiento = obtener_productos_sin_movimiento_periodo(fecha_desde, fecha_hasta)
        
        if not sin_movimiento.empty:
            st.warning(f"⚠️ {len(sin_movimiento)} productos sin ventas en el período")
            st.dataframe(
                sin_movimiento,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "codigo": "Código",
                    "nombre": "Producto",
                    "stock_actual": st.column_config.NumberColumn("Stock", format="%d")
                }
            )
        else:
            st.success("✅ Todos los productos han tenido movimiento")
        
        st.divider()
        
        # === COMPARATIVA MENSUAL (solo si es un período mensual) ===
        if periodo_rapido in ["Este mes", "Mes pasado"]:
            st.write("**📅 Comparativa vs Mes Anterior**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "Ingresos Mes Anterior",
                    formato_moneda(comparativa['ingresos_anterior'])
                )
                st.metric(
                    "Ingresos Mes Actual",
                    formato_moneda(comparativa['ingresos_actual']),
                    delta=f"{comparativa['variacion_ingresos']:+.1f}%"
                )
            
            with col2:
                st.metric(
                    "Ganancia Mes Anterior",
                    formato_moneda(comparativa['ganancia_anterior'])
                )
                st.metric(
                    "Ganancia Mes Actual",
                    formato_moneda(comparativa['ganancia_actual']),
                    delta=f"{comparativa['variacion_ganancia']:+.1f}%"
                )
    
    with tab3:
        st.subheader(f"👥 Análisis de Clientes ({fecha_desde.strftime('%d/%m')} - {fecha_hasta.strftime('%d/%m')})")
        
        metricas_clientes = obtener_metricas_clientes()
        
        # === MÉTRICAS DE CLIENTES ===
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Clientes", metricas_clientes['total_clientes'])
        
        with col2:
            st.metric("Con Compras", metricas_clientes['clientes_con_compras'])
        
        with col3:
            # Clientes que compraron en el período
            if not ventas_periodo.empty:
                clientes_periodo = ventas_periodo['cliente_id'].nunique()
                st.metric("Compraron en Período", clientes_periodo)
            else:
                st.metric("Compraron en Período", 0)
        
        with col4:
            if not ventas_periodo.empty and cantidad_ventas > 0:
                ticket_prom_periodo = ingresos_periodo / cantidad_ventas
                st.metric("Ticket Prom. Período", formato_moneda(ticket_prom_periodo))
            else:
                st.metric("Ticket Prom. Período", formato_moneda(0))
        
        st.divider()
        
        # === TOP CLIENTES ===
        st.write("**🏆 Top 10 Mejores Clientes (Histórico)**")
        clientes_frecuentes = obtener_clientes_frecuentes()
        
        if not clientes_frecuentes.empty:
            top_clientes = clientes_frecuentes.head(10)
            st.dataframe(
                top_clientes[['nombre', 'dni', 'categoria_cliente', 'total_compras', 'total_gastado', 'ticket_promedio']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Cliente",
                    "dni": "DNI",
                    "categoria_cliente": "Categoría",
                    "total_compras": st.column_config.NumberColumn("Compras", format="%d"),
                    "total_gastado": st.column_config.NumberColumn("Total Gastado", format="$%.2f"),
                    "ticket_promedio": st.column_config.NumberColumn("Ticket Prom.", format="$%.2f")
                }
            )
        else:
            st.info("No hay clientes con compras registradas")
        
        st.divider()
        
        # === CLIENTES INACTIVOS ===
        st.write("**😴 Clientes Inactivos (+30 días sin comprar)**")
        clientes_inactivos = obtener_clientes_inactivos()
        
        if not clientes_inactivos.empty:
            st.warning(f"⚠️ {len(clientes_inactivos)} clientes inactivos")
            st.dataframe(
                clientes_inactivos[['nombre', 'dni', 'telefono', 'ultima_compra', 'dias_sin_comprar']].head(10),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Cliente",
                    "dni": "DNI",
                    "telefono": "Teléfono",
                    "ultima_compra": "Última Compra",
                    "dias_sin_comprar": st.column_config.NumberColumn("Días", format="%d")
                }
            )
        else:
            st.success("✅ No hay clientes inactivos")
    
    with tab1:
        # === MÉTRICAS PRINCIPALES ===
        metricas = obtener_metricas_dashboard()
        comparativa = obtener_comparativa_mes_anterior()
        
        st.subheader("💰 Desempeño del Mes")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            variacion_ing = comparativa['variacion_ingresos']
            delta_ing = f"{variacion_ing:+.1f}%" if variacion_ing != 0 else "0%"
            st.metric(
                "Ingresos del Mes", 
                formato_moneda(metricas['ingresos_mes']),
                delta=delta_ing
            )
        
        with col2:
            variacion_gan = comparativa['variacion_ganancia']
            delta_gan = f"{variacion_gan:+.1f}%" if variacion_gan != 0 else "0%"
            st.metric(
                "Ganancia Bruta", 
                formato_moneda(metricas['ganancia_bruta_mes']),
                delta=delta_gan
            )
        
        with col3:
            st.metric(
                "Ganancia Neta", 
                formato_moneda(metricas['ganancia_neta_mes']),
                delta=f"{metricas['cantidad_ventas_mes']} ventas"
            )
        
        with col4:
            if metricas['cantidad_ventas_mes'] > 0:
                ticket_promedio = metricas['ingresos_mes'] / metricas['cantidad_ventas_mes']
                st.metric("Ticket Promedio", formato_moneda(ticket_promedio))
            else:
                st.metric("Ticket Promedio", formato_moneda(0))
        
        st.divider()
        
        # === INVENTARIO Y COSTOS ===
        st.subheader("📦 Inventario y Costos")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Productos con Stock", metricas["total_con_stock"], delta=f"{metricas['total_productos']} total")
        
        with col2:
            st.metric("Valor del Stock", formato_moneda(metricas['valor_stock']))
        
        with col3:
            st.metric("Costos Fijos", formato_moneda(metricas['costos_fijos_mes']))
        
        with col4:
            if metricas['ganancia_bruta_mes'] > 0:
                margen_neto = (metricas['ganancia_neta_mes'] / metricas['ganancia_bruta_mes'] * 100)
                st.metric("Margen Neto", f"{margen_neto:.1f}%")
            else:
                st.metric("Margen Neto", "0%")
        
        st.divider()
        
        # === GRÁFICO DE VENTAS ===
        st.subheader("📊 Evolución de Ventas (Últimos 30 días)")
        ventas_por_dia = obtener_ventas_por_dia(30)
        
        if not ventas_por_dia.empty:
            import plotly.express as px
            
            fig = px.line(
                ventas_por_dia, 
                x='fecha', 
                y='ingresos',
                title='Ingresos Diarios',
                labels={'fecha': 'Fecha', 'ingresos': 'Ingresos ($)'}
            )
            fig.update_traces(line_color='#1f77b4', line_width=3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True, key="grafico_line_ventas_tab1")
        else:
            st.info("No hay ventas en los últimos 30 días para mostrar")
        
        st.divider()
        
        # === ALERTAS ===
        if metricas['alertas_stock'] > 0:
            st.warning(f"⚠️ **{metricas['alertas_stock']} productos** con stock bajo del mínimo")
            with st.expander("Ver productos con stock bajo"):
                stock_bajo = obtener_stock_bajo()
                st.dataframe(
                    stock_bajo[['codigo', 'nombre', 'stock_actual', 'stock_minimo']], 
                    use_container_width=True, 
                    hide_index=True
                )
        
        # Productos pausados
        productos_pausados = obtener_productos(activos_solo=False)
        if not productos_pausados.empty:
            pausados = productos_pausados[productos_pausados.get('pausado', False) == True]
            if not pausados.empty:
                st.info(f"⏸️ Tenés **{len(pausados)} productos pausados**")
    
    with tab2:
        st.subheader("🛒 Análisis de Ventas")
        
        # === TOP PRODUCTOS ===
        st.write("**🏆 Top 5 Productos Más Vendidos (Este Mes)**")
        top_productos = obtener_productos_mas_vendidos(5)
        
        if not top_productos.empty:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(
                    top_productos[['codigo', 'nombre', 'cantidad', 'subtotal', 'ganancia']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "codigo": "Código",
                        "nombre": "Producto",
                        "cantidad": st.column_config.NumberColumn("Unidades", format="%d"),
                        "subtotal": st.column_config.NumberColumn("Ingresos", format="$%.2f"),
                        "ganancia": st.column_config.NumberColumn("Ganancia", format="$%.2f")
                    }
                )
            
            with col2:
                import plotly.express as px
                fig = px.pie(
                    top_productos, 
                    values='subtotal', 
                    names='nombre',
                    title='Ingresos por Producto'
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True, key="grafico_pie_productos_tab2")
        else:
            st.info("No hay ventas este mes")
        
        st.divider()
        
        # === VENTAS POR CATEGORÍA ===
        st.write("**📊 Ventas por Categoría (Este Mes)**")
        ventas_categoria = obtener_ventas_por_categoria()
        
        if not ventas_categoria.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.dataframe(
                    ventas_categoria,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "categoria": "Categoría",
                        "subtotal": st.column_config.NumberColumn("Ingresos", format="$%.2f"),
                        "ganancia": st.column_config.NumberColumn("Ganancia", format="$%.2f")
                    }
                )
            
            with col2:
                import plotly.express as px
                fig = px.bar(
                    ventas_categoria, 
                    x='categoria', 
                    y='subtotal',
                    title='Ingresos por Categoría',
                    labels={'categoria': 'Categoría', 'subtotal': 'Ingresos ($)'}
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True, key="grafico_bar_categoria_comparativa")
        else:
            st.info("No hay ventas por categoría")
        
        st.divider()
        
        # === PRODUCTOS SIN MOVIMIENTO ===
        st.write("**💤 Productos Sin Movimiento (Últimos 30 días)**")
        sin_movimiento = obtener_productos_sin_movimiento(30)
        
        if not sin_movimiento.empty:
            st.warning(f"⚠️ {len(sin_movimiento)} productos sin ventas en el último mes")
            st.dataframe(
                sin_movimiento,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "codigo": "Código",
                    "nombre": "Producto",
                    "stock_actual": st.column_config.NumberColumn("Stock", format="%d")
                }
            )
        else:
            st.success("✅ Todos los productos han tenido movimiento")
        
        st.divider()
        
        # === COMPARATIVA MENSUAL ===
        st.write("**📅 Comparativa vs Mes Anterior**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Ingresos Mes Anterior",
                formato_moneda(comparativa['ingresos_anterior'])
            )
            st.metric(
                "Ingresos Mes Actual",
                formato_moneda(comparativa['ingresos_actual']),
                delta=f"{comparativa['variacion_ingresos']:+.1f}%"
            )
        
        with col2:
            st.metric(
                "Ganancia Mes Anterior",
                formato_moneda(comparativa['ganancia_anterior'])
            )
            st.metric(
                "Ganancia Mes Actual",
                formato_moneda(comparativa['ganancia_actual']),
                delta=f"{comparativa['variacion_ganancia']:+.1f}%"
            )
    
    with tab3:
        st.subheader("👥 Análisis de Clientes")
        
        metricas_clientes = obtener_metricas_clientes()
        
        # === MÉTRICAS DE CLIENTES ===
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Clientes", metricas_clientes['total_clientes'])
        
        with col2:
            st.metric("Con Compras", metricas_clientes['clientes_con_compras'])
        
        with col3:
            st.metric("Nuevos Este Mes", metricas_clientes['clientes_nuevos_mes'])
        
        with col4:
            st.metric("Ticket Promedio", formato_moneda(metricas_clientes['ticket_promedio_cliente']))
        
        st.divider()
        
        # === TOP CLIENTES ===
        st.write("**🏆 Top 10 Mejores Clientes**")
        clientes_frecuentes = obtener_clientes_frecuentes()
        
        if not clientes_frecuentes.empty:
            top_clientes = clientes_frecuentes.head(10)
            st.dataframe(
                top_clientes[['nombre', 'dni', 'categoria_cliente', 'total_compras', 'total_gastado', 'ticket_promedio']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Cliente",
                    "dni": "DNI",
                    "categoria_cliente": "Categoría",
                    "total_compras": st.column_config.NumberColumn("Compras", format="%d"),
                    "total_gastado": st.column_config.NumberColumn("Total Gastado", format="$%.2f"),
                    "ticket_promedio": st.column_config.NumberColumn("Ticket Prom.", format="$%.2f")
                }
            )
        else:
            st.info("No hay clientes con compras registradas")
        
        st.divider()
        
        # === CLIENTES INACTIVOS ===
        st.write("**😴 Clientes Inactivos (+30 días sin comprar)**")
        clientes_inactivos = obtener_clientes_inactivos()
        
        if not clientes_inactivos.empty:
            st.warning(f"⚠️ {len(clientes_inactivos)} clientes inactivos")
            st.dataframe(
                clientes_inactivos[['nombre', 'dni', 'telefono', 'ultima_compra', 'dias_sin_comprar']].head(10),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Cliente",
                    "dni": "DNI",
                    "telefono": "Teléfono",
                    "ultima_compra": "Última Compra",
                    "dias_sin_comprar": st.column_config.NumberColumn("Días", format="%d")
                }
            )
        else:
            st.success("✅ No hay clientes inactivos")

def pagina_productos():
    st.title("📦 Gestión de Stock")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Lista", "➕ Nuevo", "📤 Importación Masiva", "✏️ Editar/Eliminar", "⚠️ Avanzado"])
    
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
            
            # Mostrar con código y campos adicionales (sin precio_venta ni margen)
            columnas_mostrar = ['codigo', 'nombre', 'marca', 'variedad', 'presentacion', 
                              'categoria', 'proveedor', 'stock_actual', 'precio_compra', 'unidad']
            
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
                    "precio_compra": st.column_config.NumberColumn("Precio Costo", format="$%.2f"),
                    "unidad": "Unidad"
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
                    unidad = st.selectbox("Unidad", ["Unidad", "kg", "gr", "ltr", "ml", "pack", "caja", "docena"])
                    ubicacion = st.text_input("Ubicación Física")
                
                detalle = st.text_area("Detalle / Otro")
                
                st.divider()
                st.subheader("Precios y Stock")
                
                col1, col2 = st.columns(2)
                with col1:
                    precio_compra = st.number_input("Precio Costo *", min_value=0.0, step=0.01)
                    stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
                with col2:
                    stock_minimo = st.number_input("Stock Mínimo", min_value=0, step=1, value=0)
                
                # Mostrar código que se generará
                if nombre and categoria_id:
                    cat_seleccionada = categorias[categorias['id']==categoria_id].iloc[0]
                    codigo_cat = cat_seleccionada.get('codigo_categoria', '')
                    if not codigo_cat:
                        # Si la categoría no tiene código, generarlo
                        cat_nombre = cat_seleccionada['nombre']
                        codigo_cat = generar_codigo_categoria(cat_nombre, categorias)
                    codigo_preview = f"{codigo_cat}-0001"
                    st.info(f"📋 Código que se asignará: **{codigo_preview}** (aproximado)")
                
                if st.form_submit_button("✅ Crear Producto"):
                    if nombre and categoria_id:
                        cat_seleccionada = categorias[categorias['id']==categoria_id].iloc[0]
                        codigo_cat = cat_seleccionada.get('codigo_categoria', '')
                        
                        if not codigo_cat:
                            # Si la categoría no tiene código, generarlo y actualizarla
                            cat_nombre = cat_seleccionada['nombre']
                            codigo_cat = generar_codigo_categoria(cat_nombre, categorias)
                            actualizar_categoria(categoria_id, {'codigo_categoria': codigo_cat})
                    
                    codigo_generado = generar_codigo_producto(nombre, codigo_cat)
                    
                    crear_producto({
                        'codigo': codigo_generado,
                        'nombre': nombre,
                        'categoria_id': categoria_id,
                        'proveedor_id': proveedor_id,
                        'marca': marca if marca else None,
                        'variedad': variedad if variedad else None,
                        'presentacion': presentacion if presentacion else None,
                        'unidad': unidad if unidad else 'Unidad',
                        'ubicacion': ubicacion if ubicacion else None,
                        'detalle': detalle if detalle else None,
                        'precio_compra': precio_compra,
                        'stock_actual': stock_inicial,
                        'stock_minimo': stock_minimo
                    })
                    st.success(f"✅ Producto '{nombre}' creado con código {codigo_generado}")
                    st.rerun()
                else:
                    st.error("Completá los campos obligatorios (*)")
    
    with tab3:
            st.subheader("📤 Importación Masiva de Productos")
            
            st.info("""
            **¿Cómo funciona?**
            1. Descargá el template de Excel
            2. Completalo con tus productos
            3. Subí el archivo y revisá el preview
            4. Confirmá la importación
            
            ✨ Las categorías y proveedores que no existan se crearán automáticamente
            """)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.download_button(
                    label="📥 Descargar Template Excel",
                    data=generar_template_importacion(),
                    file_name=f"template_productos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            
            with col2:
                st.write("**Campos obligatorios:**")
                st.write("• Nombre del producto")
                st.write("• Categoría")  
                st.write("• Precio de compra")
        
        st.divider()
        
        # Subir archivo
        archivo_subido = st.file_uploader(
            "Subí tu archivo Excel completado",
            type=['xlsx', 'xls'],
            help="El archivo debe tener las mismas columnas que el template"
        )
        
        if archivo_subido:
            try:
                # Leer el Excel
                df = pd.read_excel(archivo_subido, sheet_name='Productos')
                
                # Mostrar preview
                st.success(f"✅ Archivo cargado: {len(df)} filas detectadas")
                
                with st.expander("👀 Ver preview de los datos", expanded=True):
                    st.dataframe(df.head(10), use_container_width=True)
                    if len(df) > 10:
                        st.caption(f"Mostrando las primeras 10 filas de {len(df)} totales")
                
                # Botón para procesar
                if st.button("🚀 Importar Productos", type="primary"):
                    usuario = obtener_usuario_actual()
                    
                    with st.spinner("Procesando importación..."):
                        resultados = procesar_importacion_productos(df, usuario['id'])
                    
                    # Mostrar resultados
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("✅ Productos procesados", resultados['exitosos'])
                    with col2:
                        st.metric("❌ Errores", resultados['errores'])
                    
                    if resultados['categorias_creadas']:
                        st.success(f"🏷️ Categorías creadas: {', '.join(resultados['categorias_creadas'])}")
                    
                    if resultados['proveedores_creados']:
                        st.success(f"👥 Proveedores creados: {', '.join(resultados['proveedores_creados'])}")
                    
                    # Mostrar detalles (expandido por defecto si hay errores)
                    with st.expander("📋 Ver detalles de la importación", expanded=(resultados['errores'] > 0)):
                        for detalle in resultados['detalles']:
                            if "❌" in detalle:
                                st.error(detalle)
                            else:
                                st.success(detalle)
                    
                    if resultados['exitosos'] > 0:
                        st.balloons()
                        st.success(f"🎉 Importación completada! {resultados['exitosos']} productos procesados")
                    
                    if resultados['errores'] > 0:
                        st.warning(f"⚠️ {resultados['errores']} filas tuvieron errores. Revisá los detalles arriba.")
                
            except Exception as e:
                st.error(f"Error al leer el archivo: {str(e)}")
                st.info("Asegurate de que el archivo tenga una hoja llamada 'Productos' con las columnas correctas")
    
    with tab4:
        productos = obtener_productos(activos_solo=True)  # Solo productos activos
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
                        try:
                            if cat_actual_id and cat_actual_id in categorias['id'].values:
                                # Convertir a lista para usar .index()
                                lista_ids = categorias['id'].tolist()
                                indice_actual = lista_ids.index(cat_actual_id)
                            else:
                                indice_actual = 0
                        except:
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
                        
                        try:
                            if prov_actual_id and prov_actual_id in proveedores['id'].values:
                                indice_prov = opciones_prov.index(prov_actual_id)
                            else:
                                indice_prov = 0
                        except:
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
                    
                    col_x, col_y = st.columns(2)
                    with col_x:
                        nueva_unidad = st.selectbox(
                            "Unidad", 
                            ["Unidad", "kg", "gr", "ltr", "ml", "pack", "caja", "docena"],
                            index=["Unidad", "kg", "gr", "ltr", "ml", "pack", "caja", "docena"].index(prod['unidad']) if prod.get('unidad') in ["Unidad", "kg", "gr", "ltr", "ml", "pack", "caja", "docena"] else 0
                        )
                    with col_y:
                        nueva_ubicacion = st.text_input("Ubicación", value=prod['ubicacion'] if prod['ubicacion'] else "")
                    
                    nuevo_detalle = st.text_area("Detalle", value=prod['detalle'] if prod['detalle'] else "")
                    
                    st.divider()
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        nuevo_precio_compra = st.number_input("Precio Costo", value=float(prod['precio_compra']), step=0.01)
                    with col_b:
                        nuevo_stock_minimo = st.number_input("Stock Mínimo", value=int(prod['stock_minimo']), step=1, help="Alerta cuando el stock baja de este número")
                    with col_c:
                        producto_pausado = st.checkbox("⏸️ Pausar Producto", value=prod.get('pausado', False), help="No aparecerá en ventas ni compras")
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        # Si cambió la categoría, regenerar el código
                        if nueva_categoria_id != prod['categoria_id']:
                            cat_nueva = categorias[categorias['id']==nueva_categoria_id].iloc[0]
                            codigo_cat_nuevo = cat_nueva.get('codigo_categoria', '')
                            
                            if not codigo_cat_nuevo:
                                # Generar código para la categoría si no tiene
                                codigo_cat_nuevo = generar_codigo_categoria(cat_nueva['nombre'], categorias)
                                actualizar_categoria(nueva_categoria_id, {'codigo_categoria': codigo_cat_nuevo})
                            
                            nuevo_codigo = generar_codigo_producto(nuevo_nombre, codigo_cat_nuevo)
                            st.info(f"La categoría cambió. Nuevo código: {nuevo_codigo}")
                            
                            actualizar_producto(producto_seleccionado, {
                                'codigo': nuevo_codigo,
                                'nombre': nuevo_nombre,
                                'categoria_id': nueva_categoria_id,
                                'proveedor_id': nuevo_proveedor_id,
                                'marca': nueva_marca if nueva_marca else None,
                                'variedad': nueva_variedad if nueva_variedad else None,
                                'presentacion': nueva_presentacion if nueva_presentacion else None,
                                'unidad': nueva_unidad if nueva_unidad else 'Unidad',
                                'ubicacion': nueva_ubicacion if nueva_ubicacion else None,
                                'detalle': nuevo_detalle if nuevo_detalle else None,
                                'precio_compra': nuevo_precio_compra,
                                'stock_minimo': nuevo_stock_minimo,
                                'pausado': producto_pausado
                            })
                        else:
                            actualizar_producto(producto_seleccionado, {
                                'nombre': nuevo_nombre,
                                'categoria_id': nueva_categoria_id,
                                'proveedor_id': nuevo_proveedor_id,
                                'marca': nueva_marca if nueva_marca else None,
                                'variedad': nueva_variedad if nueva_variedad else None,
                                'presentacion': nueva_presentacion if nueva_presentacion else None,
                                'unidad': nueva_unidad if nueva_unidad else 'Unidad',
                                'ubicacion': nueva_ubicacion if nueva_ubicacion else None,
                                'detalle': nuevo_detalle if nuevo_detalle else None,
                                'precio_compra': nuevo_precio_compra,
                                'stock_minimo': nuevo_stock_minimo,
                                'pausado': producto_pausado
                            })
                        
                        st.success("✅ Producto actualizado")
                        st.rerun()
            
            with col2:
                # AJUSTE DE STOCK
                st.subheader("📦 Ajustar Stock")
                st.info(f"**Stock actual:** {prod['stock_actual']} unidades")
                
                with st.form("ajustar_stock"):
                    nuevo_stock = st.number_input(
                        "Nuevo stock", 
                        min_value=0, 
                        value=int(prod['stock_actual']), 
                        step=1,
                        help="Ingresá la cantidad correcta de stock"
                    )
                    
                    motivo = st.selectbox(
                        "Motivo del ajuste",
                        ["Corrección de inventario", "Pérdida", "Robo", "Deterioro", "Devolución", "Otro"]
                    )
                    
                    notas_ajuste = st.text_area("Notas (opcional)", placeholder="Ej: Encontré 5 unidades más en el depósito")
                    
                    if st.form_submit_button("💾 Guardar Ajuste", type="primary"):
                        if nuevo_stock != prod['stock_actual']:
                            registrar_ajuste_inventario(
                                producto_seleccionado,
                                nuevo_stock,
                                motivo,
                                notas_ajuste
                            )
                            diferencia = nuevo_stock - prod['stock_actual']
                            if diferencia > 0:
                                st.success(f"✅ Stock ajustado: +{diferencia} unidades")
                            else:
                                st.success(f"✅ Stock ajustado: {diferencia} unidades")
                            st.rerun()
                        else:
                            st.warning("⚠️ El stock no cambió")
                
                # Historial de ajustes
                ajustes = obtener_ajustes_producto(producto_seleccionado)
                if not ajustes.empty:
                    with st.expander(f"📜 Historial de ajustes ({len(ajustes)})"):
                        for _, ajuste in ajustes.head(5).iterrows():
                            diferencia_signo = f"+{ajuste['diferencia']}" if ajuste['diferencia'] > 0 else str(ajuste['diferencia'])
                            st.write(f"**{ajuste['fecha']}** - {ajuste['motivo']}")
                            st.caption(f"{ajuste['cantidad_anterior']} → {ajuste['cantidad_nueva']} ({diferencia_signo})")
                            if ajuste.get('notas'):
                                st.caption(f"💬 {ajuste['notas']}")
                            st.divider()
                
                st.divider()
                
                # ELIMINAR
                st.subheader("🗑️ Eliminar")
                st.warning(f"**Producto:** {prod['nombre']}")
                st.write(f"**Código:** {prod['codigo']}")
                st.write(f"Stock actual: {prod['stock_actual']}")
                
                if st.button("🗑️ Eliminar Producto", type="secondary"):
                    eliminar_producto(producto_seleccionado)
                    st.success("✅ Producto eliminado")
                    st.rerun()
    
    with tab5:
        st.subheader("⚠️ Opciones Avanzadas")
        st.warning("**Cuidado:** Estas acciones son irreversibles")
        
        st.divider()
        
        # Borrar inventario completo
        st.subheader("🗑️ Borrar Todo el Inventario")
        st.write("Esta acción eliminará TODOS los productos del stock (se marcarán como inactivos).")
        st.write("**Nota:** El historial de compras y ventas se mantendrá.")
        
        confirmar = st.checkbox("Entiendo que esta acción es irreversible")
        
        if confirmar:
            palabra_confirmacion = st.text_input("Escribí 'BORRAR TODO' para confirmar")
            
            if st.button("🗑️ BORRAR TODO EL INVENTARIO", type="secondary"):
                if palabra_confirmacion == "BORRAR TODO":
                    # Obtener todos los productos (activos e inactivos)
                    productos = obtener_productos(activos_solo=False)
                    if not productos.empty:
                        for _, prod in productos.iterrows():
                            eliminar_producto(prod['id'], borrado_permanente=True)  # BORRADO PERMANENTE
                        st.success(f"✅ {len(productos)} productos eliminados permanentemente del inventario")
                        st.balloons()
                        st.rerun()
                    else:
                        st.info("No hay productos para eliminar")
                else:
                    st.error("Debés escribir exactamente 'BORRAR TODO' para confirmar")

def pagina_compras():
    st.title("🛒 Gestión de Compras")
    tab1, tab2 = st.tabs(["➕ Registrar", "📋 Historial"])
    
    with tab1:
        productos = obtener_productos(excluir_pausados=True)
        if productos.empty:
            st.warning("No hay productos disponibles")
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
        productos = obtener_productos(excluir_pausados=True)
        if productos.empty:
            st.warning("No hay productos disponibles para vender")
            return
        
        # Inicializar session state para cliente
        if 'cliente_venta' not in st.session_state:
            st.session_state.cliente_venta = None
        
        # Búsqueda de cliente
        st.subheader("1️⃣ Cliente")
        col_dni, col_buscar, col_limpiar = st.columns([3, 1, 1])
        
        with col_dni:
            dni_cliente = st.text_input("DNI del Cliente (opcional)", max_chars=20, help="Dejá vacío para venta sin cliente", key="dni_input")
        
        with col_buscar:
            st.write("")  # Espaciado
            if st.button("🔍 Buscar", use_container_width=True):
                if dni_cliente:
                    cliente = buscar_cliente_por_dni(dni_cliente)
                    if cliente:
                        st.session_state.cliente_venta = cliente
                    else:
                        st.session_state.cliente_venta = None
        
        with col_limpiar:
            st.write("")  # Espaciado
            if st.button("🗑️ Limpiar", use_container_width=True):
                st.session_state.cliente_venta = None
                st.rerun()
        
        # Mostrar cliente seleccionado
        if st.session_state.cliente_venta:
            st.success(f"✅ **{st.session_state.cliente_venta['nombre']}** - DNI: {st.session_state.cliente_venta['dni']} - Tel: {st.session_state.cliente_venta.get('telefono', 'N/A')}")
            mostrar_form_nuevo_cliente = False
        elif dni_cliente:
            st.warning(f"⚠️ Cliente con DNI {dni_cliente} no encontrado")
            mostrar_form_nuevo_cliente = st.checkbox("➕ Registrar cliente nuevo")
        else:
            mostrar_form_nuevo_cliente = False
        
        # Formulario de nuevo cliente (si es necesario)
        if mostrar_form_nuevo_cliente and dni_cliente:
            with st.expander("📝 Datos del nuevo cliente", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    nuevo_nombre = st.text_input("Nombre Completo *", key="venta_nuevo_nombre")
                    nuevo_telefono = st.text_input("Teléfono", key="venta_nuevo_tel")
                with col2:
                    nuevo_email = st.text_input("Email", key="venta_nuevo_email")
                    nuevas_notas = st.text_input("Notas", key="venta_nuevo_notas")
                
                if st.button("💾 Guardar Cliente"):
                    if nuevo_nombre:
                        resultado = crear_cliente({
                            'dni': dni_cliente,
                            'nombre': nuevo_nombre,
                            'telefono': nuevo_telefono if nuevo_telefono else None,
                            'email': nuevo_email if nuevo_email else None,
                            'notas': nuevas_notas if nuevas_notas else None
                        })
                        if resultado:
                            st.success(f"✅ Cliente {nuevo_nombre} registrado")
                            st.session_state.cliente_venta = resultado[0]
                            st.rerun()
                    else:
                        st.error("El nombre es obligatorio")
        
        st.divider()
        
        # Formulario de venta
        st.subheader("2️⃣ Datos de la Venta")
        
        # Selector de producto FUERA del form para poder reaccionar
        producto_id = st.selectbox(
            "Producto *",
            productos['id'].tolist(),
            format_func=lambda x: f"{productos[productos['id']==x]['codigo'].values[0]} - {productos[productos['id']==x]['nombre'].values[0]} (Stock: {productos[productos['id']==x]['stock_actual'].values[0]})",
            key="selector_producto_venta"
        )
        
        # Obtener precios del producto seleccionado
        precio_sugerido = None
        precio_definido = None
        precio_con_descuento = None
        precio_con_recargo = None
        
        lista_precios = obtener_lista_precios()
        if not lista_precios.empty and producto_id:
            producto_precio = lista_precios[lista_precios['producto_id'] == producto_id]
            if not producto_precio.empty:
                # Precio sugerido (calculado con el margen teórico)
                precio_sugerido = float(producto_precio.iloc[0]['precio_sugerido'])
                # Precio definido (el que estableciste en la lista)
                precio_definido = float(producto_precio.iloc[0]['precio_final'])
                
                # Calcular precios con descuento y recargo (usando valores por defecto)
                descuento_default = 10.0  # 10%
                recargo_default = 15.0    # 15%
                
                precio_con_descuento = precio_definido * (1 - descuento_default / 100)
                precio_con_recargo = precio_definido * (1 + recargo_default / 100)
        
        # Mostrar precios de referencia en cards
        if precio_definido:
            st.markdown("### 💰 Precios de Referencia")
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            
            with col_p1:
                st.info(f"""
                **💡 Precio Sugerido**  
                {formato_moneda(precio_sugerido)}
                """)
            
            with col_p2:
                st.success(f"""
                **💵 Precio Definido**  
                {formato_moneda(precio_definido)}
                """)
            
            with col_p3:
                st.success(f"""
                **🔽 Con Descuento 10%**  
                {formato_moneda(precio_con_descuento)}
                """)
            
            with col_p4:
                st.warning(f"""
                **🔼 Con Recargo 15%**  
                {formato_moneda(precio_con_recargo)}
                """)
            
            st.caption("💡 Estos son precios de referencia. Podés cargar el precio que quieras abajo.")
        
        with st.form("nueva_venta"):
            col1, col2, col3 = st.columns(3)
            with col1:
                cantidad = st.number_input("Cantidad *", min_value=1, step=1)
            with col2:
                precio_unitario = st.number_input(
                    "Precio Venta *", 
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    help="Ingresá el precio al que vas a vender"
                )
            with col3:
                fecha_venta = st.date_input("Fecha", value=datetime.now().date())
            
            # Mostrar total solo si precio > 0
            if precio_unitario > 0:
                total_venta = cantidad * precio_unitario
                st.info(f"💵 **Total de la venta:** {formato_moneda(total_venta)}")
            
            if st.form_submit_button("✅ Registrar Venta", type="primary"):
                if precio_unitario <= 0:
                    st.error("❌ El precio de venta debe ser mayor a 0")
                else:
                    try:
                        # Usar cliente de session_state
                        cliente_id_venta = None
                        if st.session_state.cliente_venta:
                            cliente_id_venta = st.session_state.cliente_venta['id']
                        
                        registrar_venta({
                            'producto_id': producto_id,
                            'cantidad': cantidad,
                            'precio_unitario': precio_unitario,
                            'fecha': str(fecha_venta),
                            'cliente_id': cliente_id_venta
                        })
                        st.success("✅ Venta registrada")
                        # Limpiar cliente después de registrar
                        st.session_state.cliente_venta = None
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
            ventas_display['cliente'] = ventas_display['clientes'].apply(
                lambda x: f"{x['nombre']} ({x['dni']})" if x else 'Sin cliente'
            )
            
            # Mostrar con opción de eliminar
            for idx, venta in ventas_display.iterrows():
                col1, col2 = st.columns([5, 1])
                with col1:
                    cliente_info = f" - Cliente: {venta['cliente']}" if venta['cliente'] != 'Sin cliente' else ""
                    st.write(f"**{venta['fecha']}** - {venta['producto']} - {venta['cantidad']} unidades - {formato_moneda(venta['subtotal'])} (Ganancia: {formato_moneda(venta['ganancia'])}){cliente_info}")
                with col2:
                    if st.button("🗑️", key=f"del_venta_{venta['id']}"):
                        eliminar_venta(venta['id'])
                        st.warning("⚠️ Venta eliminada. Recordá ajustar el stock manualmente si es necesario.")
                        st.rerun()
            
            st.divider()
            
            st.download_button(
                label="📥 Descargar Ventas (Excel)",
                data=to_excel(ventas_display[['fecha', 'producto', 'cliente', 'cantidad', 
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
    st.title("👥 Proveedores")
    
    tab1, tab2, tab3 = st.tabs(["📋 Lista", "➕ Nuevo", "✏️ Editar/Eliminar"])
    
    with tab1:
        proveedores = obtener_proveedores()
        if not proveedores.empty:
            st.dataframe(
                proveedores[['nombre', 'contacto', 'telefono']], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No hay proveedores registrados")
    
    with tab2:
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
    
    with tab3:
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

def pagina_categorias():
    st.title("🏷️ Categorías")
    
    tab1, tab2, tab3 = st.tabs(["📋 Lista", "➕ Nueva", "✏️ Editar/Eliminar"])
    
    with tab1:
        categorias = obtener_categorias()
        if not categorias.empty:
            # Asegurar que todas tengan código
            categorias_display = categorias.copy()
            if 'codigo_categoria' in categorias_display.columns:
                st.dataframe(
                    categorias_display[['codigo_categoria', 'nombre', 'descripcion']], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "codigo_categoria": "Código",
                        "nombre": "Nombre",
                        "descripcion": "Descripción"
                    }
                )
            else:
                st.dataframe(
                    categorias_display[['nombre', 'descripcion']], 
                    use_container_width=True, 
                    hide_index=True
                )
        else:
            st.info("No hay categorías registradas")
    
    with tab2:
        with st.form("nueva_categoria"):
            nombre = st.text_input("Nombre *")
            descripcion = st.text_area("Descripción")
            
            if st.form_submit_button("✅ Crear Categoría"):
                if nombre:
                    crear_categoria(nombre, descripcion)
                    st.success(f"✅ Categoría '{nombre}' creada")
                    st.rerun()
                else:
                    st.error("El nombre es obligatorio")
    
    with tab3:
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

def pagina_usuarios():
    st.title("⚙️ Gestión de Usuarios")
    
    # Solo ADMIN puede acceder
    requiere_permiso('gestionar_usuarios', 'Solo el administrador puede gestionar usuarios')
    
    st.info("💡 Agregá empleados o colaboradores para que puedan usar el sistema con diferentes niveles de acceso")
    
    tab1, tab2, tab3 = st.tabs(["📋 Usuarios Activos", "➕ Agregar Usuario", "📖 Roles y Permisos"])
    
    with tab1:
        usuarios = obtener_usuarios_emprendimiento()
        
        if usuarios.empty:
            st.info("No hay usuarios adicionales. Podés agregar empleados o colaboradores.")
        else:
            st.subheader(f"👥 Usuarios del emprendimiento ({len(usuarios)})")
            
            for _, user in usuarios.iterrows():
                with st.expander(f"{'🟢' if user['activo'] else '🔴'} {user['nombre']} ({user['email']})"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Rol:** {user['rol'].capitalize()}")
                    
                    with col2:
                        st.write(f"**Estado:** {'Activo' if user['activo'] else 'Inactivo'}")
                    
                    with col3:
                        if st.button(f"🗑️ Desactivar", key=f"del_{user['id']}"):
                            eliminar_usuario_emprendimiento(user['id'])
                            st.success(f"✅ Usuario {user['nombre']} desactivado")
                            st.rerun()
    
    with tab2:
        st.subheader("➕ Agregar Nuevo Usuario")
        
        with st.form("nuevo_usuario_emp"):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Nombre completo *")
                email = st.text_input("Email *", help="El usuario usará este email para iniciar sesión")
            
            with col2:
                rol = st.selectbox(
                    "Rol *",
                    ["vendedor", "consulta", "repositor"],
                    format_func=lambda x: {
                        'vendedor': '💰 Vendedor - Registra ventas',
                        'consulta': '📊 Consulta - Solo lectura',
                        'repositor': '📦 Repositor - Gestiona stock'
                    }[x]
                )
            
            st.info("""
            **Nota importante:** El usuario deberá registrarse primero en la app con este email.
            Una vez registrado, cuando inicie sesión verá solo las secciones permitidas según su rol.
            """)
            
            if st.form_submit_button("➕ Agregar Usuario", type="primary"):
                if nombre and email:
                    # Verificar que el email no exista ya
                    usuarios_existentes = obtener_usuarios_emprendimiento()
                    if not usuarios_existentes.empty and email in usuarios_existentes['email'].values:
                        st.error("⚠️ Este email ya está agregado")
                    else:
                        agregar_usuario_emprendimiento(email, nombre, rol)
                        st.success(f"✅ Usuario {nombre} agregado con rol {rol}")
                        st.balloons()
                        st.rerun()
                else:
                    st.error("⚠️ Completá todos los campos obligatorios")
    
    with tab3:
        st.subheader("📖 Descripción de Roles")
        
        st.markdown("""
        ### 🔑 ADMIN (Administrador)
        **Acceso total al sistema**
        - ✅ Ver y editar todo
        - ✅ Gestionar usuarios
        - ✅ Eliminar datos
        - ✅ Configuración avanzada
        - ✅ Importación masiva
        
        ---
        
        ### 💰 VENDEDOR
        **Enfocado en ventas diarias**
        - ✅ Ver stock (solo lectura)
        - ✅ Registrar ventas
        - ✅ Agregar/editar clientes
        - ✅ Ver dashboard
        - ❌ No ve costos
        - ❌ No edita productos
        - ❌ No elimina datos
        
        ---
        
        ### 📊 CONSULTA
        **Solo lectura de reportes**
        - ✅ Ver dashboard
        - ✅ Ver reportes
        - ✅ Ver stock
        - ✅ Ver ventas
        - ❌ No puede editar nada
        - ❌ No ve costos
        
        ---
        
        ### 📦 REPOSITOR
        **Gestión de inventario**
        - ✅ Ver y editar stock
        - ✅ Registrar compras
        - ✅ Importación masiva
        - ✅ Ajustar inventario
        - ❌ No registra ventas
        - ❌ No ve costos
        """)

def pagina_lista_precios():
    st.title("💰 Lista de Precios")
    
    st.info("""
    **¿Cómo funciona?**
    - **Margen Teórico %**: Editalo y el Precio Sugerido se recalcula automáticamente
    - **Precio Final**: El precio base de venta (editable)
    - **Descuento/Recargo %**: Aplicá porcentajes para calcular precios especiales
    - Los cambios se guardan al hacer click en "Guardar Cambios"
    """)
    
    # Controles para descuento y recargo globales
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.write("**Cálculo de Precios Especiales:**")
    with col2:
        descuento_global = st.number_input("Descuento % (global)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, help="Se aplica sobre Precio Final")
    with col3:
        recargo_global = st.number_input("Recargo % (global)", min_value=0.0, max_value=500.0, value=15.0, step=1.0, help="Se aplica sobre Precio Final")
    
    lista = obtener_lista_precios()
    
    if lista.empty:
        st.warning("No hay productos en stock. Primero cargá productos.")
        return
    
    # Calcular precios con descuento y recargo
    lista['precio_con_descuento'] = lista['precio_final'] * (1 - descuento_global / 100)
    lista['precio_con_recargo'] = lista['precio_final'] * (1 + recargo_global / 100)
    
    # Redondear
    lista['precio_con_descuento'] = lista['precio_con_descuento'].round(2)
    lista['precio_con_recargo'] = lista['precio_con_recargo'].round(2)
    
    # Ocultar producto_id de la vista
    lista_display = lista[['codigo', 'nombre', 'precio_costo', 'margen_teorico', 'precio_sugerido', 
                           'precio_final', 'margen_real', 'precio_con_descuento', 'precio_con_recargo']].copy()
    
    # Configurar columnas editables
    columnas_config = {
        'codigo': st.column_config.TextColumn("Código", disabled=True, width="small"),
        'nombre': st.column_config.TextColumn("Producto", disabled=True, width="medium"),
        'precio_costo': st.column_config.NumberColumn("Precio Costo", disabled=True, format="$%.2f", width="small"),
        'margen_teorico': st.column_config.NumberColumn("Margen %", min_value=0, max_value=500, step=1, format="%.1f", width="small"),
        'precio_sugerido': st.column_config.NumberColumn("Sugerido", disabled=True, format="$%.2f", width="small"),
        'precio_final': st.column_config.NumberColumn("Final", min_value=0, step=0.01, format="$%.2f", width="small"),
        'margen_real': st.column_config.NumberColumn("Real %", disabled=True, format="%.2f", width="small"),
        'precio_con_descuento': st.column_config.NumberColumn(f"c/ Desc. {descuento_global:.0f}%", disabled=True, format="$%.2f", width="small"),
        'precio_con_recargo': st.column_config.NumberColumn(f"c/ Rec. {recargo_global:.0f}%", disabled=True, format="$%.2f", width="small")
    }
    
    # Mostrar tabla editable
    edited_df = st.data_editor(
        lista_display,
        column_config=columnas_config,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key="editor_precios",
        disabled=False
    )
    
    # Recalcular automáticamente precio sugerido y margen real
    for idx in range(len(edited_df)):
        precio_costo = edited_df.iloc[idx]['precio_costo']
        margen_teorico = edited_df.iloc[idx]['margen_teorico']
        precio_final = edited_df.iloc[idx]['precio_final']
        
        # Recalcular precio sugerido
        edited_df.at[idx, 'precio_sugerido'] = round(precio_costo * (1 + margen_teorico / 100), 2)
        
        # Recalcular margen real
        if precio_costo > 0:
            edited_df.at[idx, 'margen_real'] = round(((precio_final - precio_costo) / precio_costo) * 100, 2)
        
        # Recalcular descuento y recargo
        edited_df.at[idx, 'precio_con_descuento'] = round(precio_final * (1 - descuento_global / 100), 2)
        edited_df.at[idx, 'precio_con_recargo'] = round(precio_final * (1 + recargo_global / 100), 2)
    
    # Botón para guardar cambios
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("💾 Guardar Cambios", type="primary"):
            try:
                cambios = 0
                for idx in range(len(edited_df)):
                    # Obtener producto_id del dataframe original
                    producto_id = lista.iloc[idx]['producto_id']
                    margen_teorico = edited_df.iloc[idx]['margen_teorico']
                    precio_final = edited_df.iloc[idx]['precio_final']
                    
                    # Guardar
                    guardar_precio(producto_id, margen_teorico, precio_final)
                    cambios += 1
                
                if cambios > 0:
                    st.success(f"✅ {cambios} precio(s) actualizado(s)")
                    st.rerun()
                else:
                    st.info("No se detectaron cambios")
            except Exception as e:
                st.error(f"Error al guardar: {str(e)}")
    
    # Botón para descargar
    with col2:
        st.download_button(
            label="📥 Descargar Lista de Precios (Excel)",
            data=to_excel(edited_df, "Lista de Precios"),
            file_name=f"lista_precios_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Estadísticas
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        margen_promedio = edited_df['margen_real'].mean()
        st.metric("Margen Promedio", f"{margen_promedio:.1f}%")
    with col2:
        precio_max = edited_df['precio_final'].max()
        st.metric("Precio Más Alto", formato_moneda(precio_max))
    with col3:
        precio_min = edited_df['precio_final'].min()
        st.metric("Precio Más Bajo", formato_moneda(precio_min))
    with col4:
        promedio_descuento = edited_df['precio_con_descuento'].mean()
        st.metric(f"Promedio c/ Desc.", formato_moneda(promedio_descuento))

def pagina_clientes():
    st.title("👥 Gestión de Clientes")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Lista", "➕ Nuevo Cliente", "📊 Reportes", "✏️ Editar"])
    
    with tab1:
        clientes = obtener_clientes()
        
        if not clientes.empty:
            # Mostrar estadísticas rápidas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Clientes", len(clientes))
            with col2:
                clientes_activos = clientes[clientes['total_compras'] > 0]
                st.metric("Clientes con Compras", len(clientes_activos))
            with col3:
                if not clientes.empty and 'total_gastado' in clientes.columns:
                    promedio = clientes['total_gastado'].mean()
                    st.metric("Gasto Promedio", formato_moneda(promedio))
            
            st.divider()
            
            # Buscador
            busqueda = st.text_input("🔍 Buscar por DNI, nombre o teléfono")
            
            if busqueda:
                clientes_filtrados = clientes[
                    clientes['dni'].str.contains(busqueda, case=False, na=False) |
                    clientes['nombre'].str.contains(busqueda, case=False, na=False) |
                    clientes['telefono'].astype(str).str.contains(busqueda, case=False, na=False)
                ]
            else:
                clientes_filtrados = clientes
            
            # Mostrar tabla
            st.dataframe(
                clientes_filtrados[['dni', 'nombre', 'telefono', 'email', 'total_compras', 'total_gastado']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "dni": "DNI",
                    "nombre": "Nombre",
                    "telefono": "Teléfono",
                    "email": "Email",
                    "total_compras": st.column_config.NumberColumn("Compras", format="%d"),
                    "total_gastado": st.column_config.NumberColumn("Total Gastado", format="$%.2f")
                }
            )
            
            # Descargar
            st.download_button(
                label="📥 Descargar Clientes (Excel)",
                data=to_excel(clientes_filtrados[['dni', 'nombre', 'telefono', 'email', 
                                                   'total_compras', 'total_gastado', 'notas']], "Clientes"),
                file_name=f"clientes_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay clientes registrados")
    
    with tab2:
        st.subheader("Registrar Nuevo Cliente")
        
        with st.form("nuevo_cliente"):
            col1, col2 = st.columns(2)
            
            with col1:
                dni = st.text_input("DNI *", max_chars=20)
                nombre = st.text_input("Nombre Completo *")
                telefono = st.text_input("Teléfono")
            
            with col2:
                email = st.text_input("Email")
                direccion = st.text_area("Dirección")
                notas = st.text_area("Notas")
            
            if st.form_submit_button("✅ Registrar Cliente"):
                if dni and nombre:
                    # Verificar si ya existe
                    cliente_existe = buscar_cliente_por_dni(dni)
                    if cliente_existe:
                        st.error(f"⚠️ Ya existe un cliente con DNI {dni}")
                    else:
                        crear_cliente({
                            'dni': dni,
                            'nombre': nombre,
                            'telefono': telefono if telefono else None,
                            'email': email if email else None,
                            'direccion': direccion if direccion else None,
                            'notas': notas if notas else None
                        })
                        st.success(f"✅ Cliente {nombre} registrado")
                        st.rerun()
                else:
                    st.error("DNI y Nombre son obligatorios")
    
    with tab3:
        st.subheader("📊 Análisis de Clientes")
        
        # Top clientes
        clientes_frecuentes = obtener_clientes_frecuentes()
        if not clientes_frecuentes.empty:
            st.write("**🏆 Top 10 Clientes**")
            top10 = clientes_frecuentes.head(10)
            st.dataframe(
                top10[['nombre', 'dni', 'categoria_cliente', 'total_compras', 'total_gastado', 'ticket_promedio']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Cliente",
                    "dni": "DNI",
                    "categoria_cliente": "Categoría",
                    "total_compras": st.column_config.NumberColumn("Compras", format="%d"),
                    "total_gastado": st.column_config.NumberColumn("Total", format="$%.2f"),
                    "ticket_promedio": st.column_config.NumberColumn("Ticket Promedio", format="$%.2f")
                }
            )
        
        st.divider()
        
        # Clientes inactivos
        clientes_inactivos = obtener_clientes_inactivos()
        if not clientes_inactivos.empty:
            st.write("**😴 Clientes Inactivos (+30 días sin comprar)**")
            st.dataframe(
                clientes_inactivos[['nombre', 'dni', 'telefono', 'ultima_compra', 'dias_sin_comprar']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "nombre": "Cliente",
                    "dni": "DNI",
                    "telefono": "Teléfono",
                    "ultima_compra": "Última Compra",
                    "dias_sin_comprar": st.column_config.NumberColumn("Días sin Comprar", format="%d")
                }
            )
    
    with tab4:
        clientes = obtener_clientes()
        if clientes.empty:
            st.info("No hay clientes para editar")
            return
        
        cliente_seleccionado = st.selectbox(
            "Seleccionar cliente",
            clientes['id'].tolist(),
            format_func=lambda x: f"{clientes[clientes['id']==x]['dni'].values[0]} - {clientes[clientes['id']==x]['nombre'].values[0]}"
        )
        
        if cliente_seleccionado:
            cliente = clientes[clientes['id']==cliente_seleccionado].iloc[0]
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("✏️ Editar Datos")
                with st.form("editar_cliente"):
                    nuevo_nombre = st.text_input("Nombre", value=cliente['nombre'])
                    nuevo_telefono = st.text_input("Teléfono", value=cliente['telefono'] if cliente['telefono'] else "")
                    nuevo_email = st.text_input("Email", value=cliente['email'] if cliente['email'] else "")
                    nueva_direccion = st.text_area("Dirección", value=cliente['direccion'] if cliente['direccion'] else "")
                    nuevas_notas = st.text_area("Notas", value=cliente['notas'] if cliente['notas'] else "")
                    
                    if st.form_submit_button("💾 Guardar"):
                        actualizar_cliente(cliente_seleccionado, {
                            'nombre': nuevo_nombre,
                            'telefono': nuevo_telefono if nuevo_telefono else None,
                            'email': nuevo_email if nuevo_email else None,
                            'direccion': nueva_direccion if nueva_direccion else None,
                            'notas': nuevas_notas if nuevas_notas else None
                        })
                        st.success("✅ Cliente actualizado")
                        st.rerun()
            
            with col2:
                st.subheader("📊 Estadísticas")
                st.metric("Compras Totales", int(cliente['total_compras']))
                st.metric("Total Gastado", formato_moneda(float(cliente['total_gastado'])))
                if cliente['total_compras'] > 0:
                    ticket_prom = float(cliente['total_gastado']) / int(cliente['total_compras'])
                    st.metric("Ticket Promedio", formato_moneda(ticket_prom))
                
                # Ver historial
                if st.button("📜 Ver Historial de Compras"):
                    historial = obtener_historial_cliente(cliente_seleccionado)
                    if not historial.empty:
                        st.write("**Últimas compras:**")
                        historial_display = historial.copy()
                        historial_display['producto'] = historial_display['productos'].apply(
                            lambda x: x['nombre'] if x else 'N/A'
                        )
                        st.dataframe(
                            historial_display[['fecha', 'producto', 'cantidad', 'subtotal']].head(10),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info("Sin compras registradas")

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
    rol = obtener_rol_usuario(usuario['email'])
    
    with st.sidebar:
        st.title("📦 Sistema de Reventa")
        st.write(f"👤 {usuario['nombre']}")
        
        # Mostrar rol si no es admin
        if rol != 'admin':
            rol_emoji = {
                'vendedor': '💰',
                'consulta': '📊',
                'repositor': '📦'
            }
            st.caption(f"{rol_emoji.get(rol, '👤')} {rol.capitalize()}")
        
        st.divider()
        
        # Menú adaptativo según rol
        menu_items = []
        
        if tiene_permiso('ver_dashboard'):
            menu_items.append("📊 Dashboard")
        
        if tiene_permiso('ver_stock'):
            menu_items.append("📦 Stock")
        
        if tiene_permiso('ver_stock'):
            menu_items.append("💰 Lista de Precios")
        
        if tiene_permiso('ver_ventas') or tiene_permiso('registrar_ventas'):
            menu_items.append("💵 Ventas")
        
        if tiene_permiso('editar_stock'):
            menu_items.append("🛒 Compras")
        
        if tiene_permiso('ver_clientes'):
            menu_items.append("👥 Clientes")
        
        if tiene_permiso('ver_costos'):
            menu_items.append("💸 Costos Fijos")
        
        if tiene_permiso('editar_stock'):
            menu_items.append("🏪 Proveedores")
            menu_items.append("🏷️ Categorías")
        
        if tiene_permiso('gestionar_usuarios'):
            menu_items.append("⚙️ Usuarios")
        
        pagina = st.radio(
            "Navegación",
            menu_items,
            label_visibility="collapsed"
        )
        
        st.divider()
        
        if st.button("🚪 Cerrar Sesión"):
            cerrar_sesion()
        
        st.caption("v2.1.0")
    
    if pagina == "📊 Dashboard":
        pagina_dashboard()
    elif pagina == "📦 Stock":
        pagina_productos()
    elif pagina == "💰 Lista de Precios":
        pagina_lista_precios()
    elif pagina == "🛒 Compras":
        pagina_compras()
    elif pagina == "💵 Ventas":
        pagina_ventas()
    elif pagina == "👥 Clientes":
        pagina_clientes()
    elif pagina == "💸 Costos Fijos":
        pagina_costos_fijos()
    elif pagina == "🏪 Proveedores":
        pagina_proveedores()
    elif pagina == "🏷️ Categorías":
        pagina_categorias()
    elif pagina == "⚙️ Usuarios":
        pagina_usuarios()
    elif pagina == "🏪 Proveedores":
        pagina_proveedores()
    elif pagina == "🏷️ Categorías":
        pagina_categorias()

if __name__ == "__main__":
    main()
