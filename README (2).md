# 📦 Sistema de Gestión de Reventa

Sistema completo para gestionar negocios de reventa con control de stock, compras, ventas y reportes automáticos.

## 🚀 Características

✅ **Gestión de Productos**
- Alta/baja/modificación de productos
- Categorías y proveedores asociados
- Control de stock automático
- Alertas de stock bajo

✅ **Registro de Compras**
- Actualización automática de stock
- Historial completo
- Asociación con proveedores

✅ **Registro de Ventas**
- Validación de stock disponible
- Cálculo automático de ganancias
- Análisis de márgenes

✅ **Dashboard y Reportes**
- Métricas en tiempo real
- Gráficos de ventas
- Top productos vendidos
- Análisis por período

## 📋 Requisitos Previos

1. **Python 3.8+** instalado
2. **Cuenta en Supabase** (gratuita)
3. **Git** (opcional, para clonar el repo)

## 🔧 Instalación

### 1. Configurar Supabase

1. Creá un proyecto en [Supabase](https://supabase.com)
2. Andá al **SQL Editor**
3. Copiá y ejecutá el contenido de `schema_reventa.sql`
4. Anotá las credenciales:
   - Project URL (Settings > API)
   - anon/public key (Settings > API)

### 2. Configurar el Proyecto

```bash
# Clonar o descargar el proyecto
cd sistema-reventa

# Instalar dependencias
pip install -r requirements.txt

# Configurar credenciales
# Editá el archivo .streamlit/secrets.toml con tus datos de Supabase
```

### 3. Ejecutar la Aplicación

```bash
streamlit run app.py
```

La app se abrirá en tu navegador en `http://localhost:8501`

## 📁 Estructura del Proyecto

```
sistema-reventa/
│
├── app.py                      # Aplicación principal de Streamlit
├── schema_reventa.sql          # Schema de base de datos
├── requirements.txt            # Dependencias Python
├── .streamlit/
│   └── secrets.toml           # Credenciales (NO commitear)
└── README.md                   # Este archivo
```

## 🎯 Uso Básico

### Primer Uso

1. **Crear Categorías**: Andá a "Proveedores" > "Categorías" y creá al menos una categoría
2. **Crear Proveedor**: Andá a "Proveedores" y registrá tus proveedores
3. **Crear Productos**: Andá a "Productos" > "Nuevo Producto" y cargá tu catálogo
4. **Registrar Compras**: Andá a "Compras" para cargar stock
5. **Registrar Ventas**: Andá a "Ventas" para registrar tus ventas

### Flujo de Trabajo

1. **Compra de mercadería**: Registrás en "Compras" → Se suma automáticamente al stock
2. **Venta**: Registrás en "Ventas" → Se resta del stock y calcula la ganancia
3. **Dashboard**: Revisás métricas y reportes

## 💡 Características Técnicas

### Automatizaciones (via SQL Triggers)

- ✅ Stock se actualiza automáticamente en compras/ventas
- ✅ Ganancias se calculan automáticamente
- ✅ Márgenes se recalculan al cambiar precios
- ✅ Validación de stock antes de vender

### Gestión de Precios

**Opción 1: Precio Manual**
- Ingresás el precio de venta manualmente

**Opción 2: Margen Automático**
- Ingresás el % de margen deseado
- El sistema calcula el precio de venta

### Reportes Disponibles

1. **Dashboard Principal**: Métricas del mes actual
2. **Stock Bajo**: Productos que necesitan reposición
3. **Ventas por Producto**: Ranking de productos más vendidos
4. **Compras por Proveedor**: Análisis de proveedores
5. **Análisis Temporal**: Ventas por día/mes

## 🔒 Seguridad

- Las credenciales están en `secrets.toml` (no se suben a Git)
- Supabase maneja automáticamente la autenticación
- Para producción, activá Row Level Security en Supabase

## 🚀 Deploy en Streamlit Cloud

1. Subí el código a GitHub (sin el archivo secrets.toml)
2. Andá a [share.streamlit.io](https://share.streamlit.io)
3. Conectá tu repo
4. Agregá los secrets en la configuración de la app

## 🐛 Troubleshooting

### Error de conexión a Supabase
- Verificá que las credenciales en `secrets.toml` sean correctas
- Asegurate de que el proyecto de Supabase esté activo

### Error al registrar venta (stock insuficiente)
- El sistema valida automáticamente el stock
- Registrá una compra primero para aumentar el stock

### Los gráficos no se ven
- Asegurate de tener `plotly` instalado
- Verificá que haya datos de ventas registradas

## 📞 Soporte

Si tenés problemas:
1. Revisá que el schema SQL se haya ejecutado correctamente
2. Verificá las credenciales de Supabase
3. Chequeá los logs de Streamlit en la terminal

## 📝 Notas

- El sistema usa UTC para las fechas
- Los precios se manejan con 2 decimales
- El stock no puede ser negativo (validado por base de datos)
- Los triggers SQL mantienen la integridad de los datos

---

**Desarrollado con:**
- 🐍 Python + Streamlit
- 🐘 Supabase (PostgreSQL)
- 📊 Plotly para gráficos
