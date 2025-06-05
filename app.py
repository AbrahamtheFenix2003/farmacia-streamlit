import streamlit as st
import pandas as pd
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ———————————
# 1) CONFIGURACIÓN BÁSICA DE STREAMLIT
# ———————————
st.set_page_config(
    page_title="Gestor de Productos (Upload Dinámico)",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📦 Gestor de Catálogo y Base de Datos (con Upload)")

# ———————————
# 2) UPLOAD DE ARCHIVOS EN SIDEBAR
# ———————————
st.sidebar.header("⚙️ Carga de Archivos (Excel)")
catalog_file = st.sidebar.file_uploader(
    label="Sube el archivo de Catálogo (.xlsx)",
    type=["xlsx"],
    accept_multiple_files=False,
    key="upload_catalog"
)

bd_file = st.sidebar.file_uploader(
    label="Sube el archivo de Base de Datos (.xlsx o .xls)",
    type=["xlsx", "xls"],
    accept_multiple_files=False,
    key="upload_bd"
)

st.sidebar.markdown(
    """
    • El catálogo debe tener columnas:  
      `Cod_Prod`, `Nom_Prod`, `Fracción` (a partir de la fila 7).  
    • La BD debe tener columnas:  
      `CodEstab`, `CodProd`, `Precio 1`, `Precio 2`.  
    """
)

# ———————————
# 3) CARGA Y NORMALIZACIÓN (una sola vez, al subir archivos)
# ———————————
def procesar_archivos(catalog_bytes: bytes, bd_bytes: bytes):
    """
    Lee los bytes de ambos Excel y devuelve dos DataFrames: df_cat, df_bd.
    Asume que el catálogo real arranca en la fila 7 de encabezados.
    Mantiene todas las columnas del catálogo para mostrarlas al seleccionar.
    """
    # 3.1) Procesar Catálogo
    df_cat = pd.read_excel(
        BytesIO(catalog_bytes),
        skiprows=6,   # fila 7 (índice 6) con encabezados reales
        engine="openpyxl",
    )
    # Renombramos solo las columnas clave, pero mantenemos el resto intacto
    df_cat = df_cat.rename(
        columns={
            "Cod_Prod": "CodProd",
            "Nom_Prod": "Nombre",
            "Fracción": "Fraccion",
        }
    )
    # Asegurar tipos numéricos en CodProd y Fraccion
    df_cat["CodProd"] = pd.to_numeric(df_cat["CodProd"], errors="coerce").astype("Int64")
    df_cat["Fraccion"] = pd.to_numeric(df_cat["Fraccion"], errors="coerce").astype("Int64")

    # 3.2) Procesar BD
    df_bd = pd.read_excel(BytesIO(bd_bytes), engine="openpyxl")
    df_bd = df_bd.rename(columns={"Precio 1": "PrecioTotal", "Precio 2": "PrecioUnit"})
    df_bd["CodProd"] = pd.to_numeric(df_bd["CodProd"], errors="coerce").astype("Int64")
    df_bd["CodEstab"] = "0021870"
    df_bd["PrecioTotal"] = pd.to_numeric(df_bd["PrecioTotal"], errors="coerce")
    df_bd["PrecioUnit"] = pd.to_numeric(df_bd["PrecioUnit"], errors="coerce")

    # 3.3) Fusionar Fracción del catálogo en la BD (para cálculos)
    df_bd = df_bd.merge(
        df_cat[["CodProd", "Fraccion"]],
        on="CodProd",
        how="left"
    )

    return df_cat, df_bd


# Solo procesamos UNA VEZ: cuando se cargan ambos archivos.
if catalog_file and bd_file:
    # Guardamos los bytes en session_state para reusarlos
    if "catalog_bytes" not in st.session_state:
        st.session_state.catalog_bytes = catalog_file.read()
    if "bd_bytes" not in st.session_state:
        st.session_state.bd_bytes = bd_file.read()

    # Si no existen los DataFrames en session_state, los procesamos ahora
    if "df_cat" not in st.session_state or "df_bd" not in st.session_state:
        try:
            df_cat, df_bd = procesar_archivos(
                st.session_state.catalog_bytes,
                st.session_state.bd_bytes
            )
            st.session_state.df_cat = df_cat.copy()
            st.session_state.df_bd = df_bd.copy()
        except Exception as e:
            st.error(f"❌ Error al leer los archivos: {e}")
            st.stop()
    else:
        df_cat = st.session_state.df_cat.copy()
        df_bd = st.session_state.df_bd.copy()
else:
    st.warning("➡️ Sube **ambos** archivos de Excel (Catálogo y BD) en la barra lateral para continuar.")
    st.stop()


# ———————————
# 4) CATÁLOGO INTERACTIVO CON FILTRO (BUSCADOR + AgGrid REDUCIDO)
# ———————————
st.subheader("🔍 Catálogo de Productos (busca por nombre o código)")

# 4.1) Campo de búsqueda
busqueda = st.text_input(
    label="Escribe parte del nombre o código del producto:",
    placeholder="Ejemplo: 'A FOLIC' o '54520' o 'flu'",
)

# 4.2) Si el usuario no ha escrito nada o menos de 2 caracteres, mostramos aviso
if not busqueda or len(busqueda.strip()) < 2:
    st.info("🔎 Ingresa al menos 2 caracteres para buscar en el catálogo.")
    st.stop()

# 4.3) Convertimos la búsqueda a minúsculas
term = busqueda.strip().lower()

# 4.4) Filtramos por CodProd o Nombre
df_filtrado = df_cat[
    df_cat["CodProd"].astype(str).str.contains(term, case=False, na=False) |
    df_cat["Nombre"].str.lower().str.contains(term)
].copy()

# 4.5) Si no hay coincidencias, informamos
if df_filtrado.empty:
    st.warning(f"❌ No se encontraron productos que contengan '{busqueda}'.")
    st.stop()

# 4.6) Renderizamos sólo el subconjunto en AgGrid
gb = GridOptionsBuilder.from_dataframe(df_filtrado)
gb.configure_default_column(filter=True, sortable=True, resizable=True)
gb.configure_selection(selection_mode="single", use_checkbox=False)
gb.configure_grid_options(domLayout="normal")

grid_response = AgGrid(
    df_filtrado,
    gridOptions=gb.build(),
    height=300,
    width="100%",
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    allow_unsafe_jscode=True,
    fit_columns_on_grid_load=True,
)

# 4.7) Detectamos si el usuario hizo clic en alguna fila del subconjunto
filas_sel = grid_response["selected_rows"]
tiene_sel = False
if filas_sel is not None:
    if isinstance(filas_sel, pd.DataFrame):
        tiene_sel = not filas_sel.empty
    else:
        tiene_sel = len(filas_sel) > 0

# Variables para la sección de selección
cod = None
fraccion = None

if tiene_sel:
    # 4.8) Extraemos esa fila como dict
    if isinstance(filas_sel, pd.DataFrame):
        fila = filas_sel.iloc[0].to_dict()
    else:
        fila = filas_sel[0]

    cod = int(fila["CodProd"])
    nombre = fila["Nombre"]
    fraccion = int(fila["Fraccion"])

    # 4.9) Mostramos todos los detalles del producto (todas las columnas del catálogo)
    st.markdown(f"**Producto seleccionado:** `{nombre}` (CodProd = {cod})")
    st.markdown("**Detalles del catálogo:**")
    for col, val in fila.items():
        if col not in ["CodProd", "Fraccion"]:
            st.write(f"- {col}: {val}")

    # 4.10) Campo para ingresar precio unitario
    precio_unit = st.number_input(
        label="💲 Precio Unitario (Precio 2)",
        min_value=0.00,
        step=0.01,
        format="%.2f",
        key="precio_unitario_input"
    )

    # 4.11) Cálculo en vivo del precio total
    precio_total_vivo = round(fraccion * precio_unit, 2)
    st.markdown(f"**Precio Total (Fracción × Unitario):** {fraccion} × {precio_unit:.2f} = **{precio_total_vivo:.2f}**")

    # 4.12) Botón para agregar a BD (con chequeo de duplicados)
    if st.button("➕ Agregar a BD"):
        cod_existentes = st.session_state.df_bd["CodProd"].dropna().astype(int).tolist()
        if cod in cod_existentes:
            st.warning(f"⚠️ El producto con CodProd={cod} ya está en la BD. No se permiten duplicados.")
        else:
            nueva = {
                "CodEstab": "0021870",
                "CodProd": cod,
                "PrecioTotal": precio_total_vivo,
                "PrecioUnit": precio_unit,
                "Fraccion": fraccion
            }
            st.session_state.df_bd = pd.concat(
                [st.session_state.df_bd, pd.DataFrame([nueva])],
                ignore_index=True
            )
            st.success(f"Se agregó `{nombre}` → PrecioTotal = {precio_total_vivo:.2f}")
            df_bd = st.session_state.df_bd.copy()

st.divider()


# ———————————
# 5) BOTÓN DE RECALCULAR PRECIOS
# ———————————
if st.button("🔄 Recalcular PrecioTotal"):
    df_bd = st.session_state.df_bd.copy()
    mask = df_bd["Fraccion"].notna() & df_bd["PrecioUnit"].notna()
    df_bd.loc[mask, "PrecioTotal"] = (df_bd.loc[mask, "Fraccion"] * df_bd.loc[mask, "PrecioUnit"]).round(2)
    st.session_state.df_bd = df_bd.copy()
    st.success("✔️ Todos los precios totales se recalcularon.")


# ———————————
# 6) EDITOR DE LA BD (sin la columna “Fraccion”)
# ———————————
st.subheader("🗂️ Base de Datos (Editable)")

df_bd_para_editar = st.session_state.df_bd.copy().drop(columns=["Fraccion"])

df_bd_editado = st.data_editor(
    df_bd_para_editar,
    num_rows="dynamic",
    use_container_width=True,
    key="bd_editor",
    hide_index=True,
    column_config={
        "CodEstab": st.column_config.Column(label="CodEstab"),
        "CodProd": st.column_config.Column(label="CodProd"),
        "PrecioTotal": st.column_config.Column(label="PrecioTotal"),
        "PrecioUnit": st.column_config.Column(label="PrecioUnit"),
    }
)

# Si el usuario editó o borró alguna fila, lo reconstruimos en session_state
if not df_bd_editado.equals(df_bd_para_editar):
    df_bd_editado["CodEstab"] = "0021870"
    mapping_fraccion = st.session_state.df_cat.set_index("CodProd")["Fraccion"]
    df_bd_editado["Fraccion"] = df_bd_editado["CodProd"].map(mapping_fraccion).astype("Int64")
    st.session_state.df_bd = df_bd_editado.copy()
    df_bd = st.session_state.df_bd.copy()

st.divider()


# ———————————
# 7) DESCARGA EN XLSX Y CSV CON FORMATO DE CELDA
# ———————————
st.subheader("⬇️ Descargar Base de Datos Actualizada")

# Preparamos el DataFrame para exportar
export_df = df_bd.copy()
export_df = export_df.rename(columns={"PrecioTotal": "Precio 1", "PrecioUnit": "Precio 2"})
export_df = export_df[["CodEstab", "CodProd", "Precio 1", "Precio 2"]]

# Convertimos “CodProd” a texto para que Excel lo trate como texto
export_df["CodProd"] = export_df["CodProd"].astype(str)

# --- Generar archivo XLSX con formatos de celda usando xlsxwriter ---
output = BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    export_df.to_excel(writer, index=False, sheet_name="BD")
    workbook  = writer.book
    worksheet = writer.sheets["BD"]

    # Columna A: CodEstab (texto), no requiere formato especial
    # Columna B: CodProd → forzar texto
    text_fmt = workbook.add_format({"num_format": "@"})
    worksheet.set_column("B:B", None, text_fmt)

    # Columnas C & D: “Precio 1” y “Precio 2” → formato numérico con dos decimales
    num_fmt = workbook.add_format({"num_format": "0.00"})
    worksheet.set_column("C:D", None, num_fmt)

data_xlsx = output.getvalue()

st.download_button(
    label="📄 Descargar XLSX",
    data=data_xlsx,
    file_name="bd_actualizada.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# CSV (CodProd ya es string)
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📄 Descargar CSV",
    data=csv_bytes,
    file_name="bd_actualizada.csv",
    mime="text/csv"
)
