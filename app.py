import streamlit as st
import pandas as pd
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="Carga automática farmacia", layout="wide")

# 1) Carga de archivos
st.sidebar.header("📂 Cargar archivos")
catalog_file = st.sidebar.file_uploader("Catálogo (.xlsx)", type="xlsx")
base_file    = st.sidebar.file_uploader("Base mensual (.xlsx)", type="xlsx")

@st.cache_data
def load_catalog(f): return pd.read_excel(f, header=6) if f else None
@st.cache_data
def load_base(f):    return pd.read_excel(f)         if f else None

df_cat    = load_catalog(catalog_file)
df_loaded = load_base(base_file)

if df_cat is not None and df_loaded is not None:

    # inicializar base en session_state
    if "db" not in st.session_state:
        df_loaded["CodEstab"] = df_loaded["CodEstab"].astype(str).str.zfill(7)
        st.session_state.db = df_loaded.copy()
    df_db = st.session_state.db

    # 2) AgGrid clicable
    st.header("🔎 Buscar producto en catálogo")
    query = st.text_input("Buscar por código o nombre:")
    df_filt = df_cat[df_cat.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)] if query else df_cat

    gb = GridOptionsBuilder.from_dataframe(df_filt)
    gb.configure_selection("single", use_checkbox=False)
    grid = AgGrid(
        df_filt,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=300,
        fit_columns_on_grid_load=True
    )

    selected = grid["selected_rows"]
    # guardamos la selección en session_state para persistirla
    if isinstance(selected, list) and len(selected) > 0:
        st.session_state.selected_code = selected[0]["Cod_Prod"]

    # recuperamos la selección (o None)
    codigo = st.session_state.get("selected_code", None)

    if codigo:
        st.success(f"✅ Producto seleccionado: **{codigo}**")

        # 3) Precios
        st.subheader("💲 Precios")
        precio_unit = st.number_input("Precio unitario (Precio 2)", min_value=0.0, format="%.2f")
        unidades    = st.number_input("Unidades por caja", min_value=1, step=1)
        precio_caja = unidades * precio_unit
        st.write(f"**Precio de caja (Precio 1):** {precio_caja:,.2f}")

        # 4) Añadir
        if st.button("➕ Añadir a la base"):
            if codigo in df_db["CodProd"].values:
                st.warning("⚠️ Ya existe ese CodProd.")
            else:
                nueva = {"CodEstab":"0021870","CodProd":codigo,"Precio 1":precio_caja,"Precio 2":precio_unit}
                st.session_state.db = pd.concat([df_db, pd.DataFrame([nueva])], ignore_index=True)
                st.success("✔️ Producto añadido")
            df_db = st.session_state.db

    # 5) Vista previa
    st.subheader("📋 Base mensual actualizada")
    st.dataframe(df_db, use_container_width=True, height=300)

    # … aquí seguirían editar, eliminar y descargas …

else:
    st.sidebar.info("📥 Sube los dos archivos para comenzar")
