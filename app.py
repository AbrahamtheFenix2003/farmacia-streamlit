import streamlit as st
import pandas as pd
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ─── Configuración ────────────────────────────────
st.set_page_config(page_title="Carga automática farmacia", layout="wide")

# ─── Carga de archivos ────────────────────────────
st.sidebar.header("📂 Cargar archivos")
catalog_file = st.sidebar.file_uploader("Catálogo (.xlsx)", type="xlsx")
base_file    = st.sidebar.file_uploader("Base mensual (.xlsx)", type="xlsx")

@st.cache_data
def load_catalog(f):
    return pd.read_excel(f, header=6) if f else None

@st.cache_data
def load_base(f):
    return pd.read_excel(f) if f else None

df_cat    = load_catalog(catalog_file)
df_loaded = load_base(base_file)

# ─── Espera a que suban los dos archivos ──────────
if df_cat is None or df_loaded is None:
    st.sidebar.info("📥 Sube ambos archivos para continuar")
    st.stop()

# ─── Inicializa session_state ─────────────────────
if "db" not in st.session_state:
    df_loaded["CodEstab"] = df_loaded["CodEstab"].astype(str).str.zfill(7)
    st.session_state.db   = df_loaded.copy()
if "selected_code" not in st.session_state:
    st.session_state.selected_code = None

df_db = st.session_state.db

# ─── 1) Selección de producto con AgGrid ─────────
st.header("🔎 Buscar y seleccionar producto")
query = st.text_input("Buscar por código o nombre:", value="")
df_filt = df_cat[df_cat.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)] if query else df_cat

# Configura la tabla clicable
gb = GridOptionsBuilder.from_dataframe(df_filt)
gb.configure_selection("single", use_checkbox=False)
grid = AgGrid(
    df_filt,
    gridOptions=gb.build(),
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    height=300,
    fit_columns_on_grid_load=True
)

# Procesa la fila seleccionada
sel = grid["selected_rows"]
if isinstance(sel, list) and sel:
    new_code = sel[0].get("Cod_Prod")
    # Si cambió la selección, guarda y recarga la app
    if new_code != st.session_state.selected_code:
        st.session_state.selected_code = new_code
        st.experimental_rerun()

codigo = st.session_state.selected_code
if codigo:
    st.success(f"✅ Producto seleccionado: **{codigo}**")
else:
    st.info("➡️ Haz clic en una fila para seleccionar")

# ─── 2) Precios y Añadir ──────────────────────────
if codigo:
    st.subheader("💲 Precios y Añadir")
    precio_unit = st.number_input("Precio unitario (Precio 2)", min_value=0.0, format="%.2f", key="unit")
    unidades    = st.number_input("Unidades por caja",      min_value=1,   step=1,        key="box")
    precio_caja = unidades * precio_unit
    st.write(f"**Precio de caja (Precio 1):** {precio_caja:,.2f}")

    if st.button("➕ Añadir a la base", key="add"):
        if codigo in df_db["CodProd"].values:
            st.warning("⚠️ Ya existe ese CodProd.")
        else:
            nueva = {
                "CodEstab": "0021870",
                "CodProd":  codigo,
                "Precio 1": precio_caja,
                "Precio 2": precio_unit
            }
            df_db = pd.concat([df_db, pd.DataFrame([nueva])], ignore_index=True)
            st.session_state.db = df_db
            st.success("✔️ Producto añadido")

# ─── 3) Vista previa ──────────────────────────────
st.subheader("📋 Base mensual actualizada")
st.dataframe(df_db, use_container_width=True, height=300)

# ─── 4) Editar ─────────────────────────────────────
with st.expander("✏️ Editar un registro"):
    opciones = df_db["CodProd"].unique().tolist()
    edited = st.selectbox("Selecciona CodProd a editar", options=opciones, key="edit_sel")
    if edited:
        idx = df_db.index[df_db["CodProd"] == edited][0]
        curr_u = float(df_db.at[idx, "Precio 2"])
        curr_b = int(df_db.at[idx, "Precio 1"] / curr_u) if curr_u else 1

        nu = st.number_input("Nuevo precio unitario", value=curr_u, format="%.2f", key="nu")
        nb = st.number_input("Nuevas unidades por caja", value=curr_b, step=1, key="nb")
        nc = nu * nb
        st.write(f"→ Nuevo Precio caja: {nc:,.2f}")

        if st.button("💾 Guardar cambios", key="save"):
            df_db.at[idx, "Precio 2"] = nu
            df_db.at[idx, "Precio 1"] = nc
            st.session_state.db       = df_db
            st.success(f"✔️ {edited} actualizado")

# ─── 5) Eliminar ────────────────────────────────────
with st.expander("🗑️ Eliminar un registro"):
    opciones = df_db["CodProd"].unique().tolist()
    deleted = st.selectbox("Selecciona CodProd a eliminar", options=opciones, key="del_sel")
    if st.button("❌ Eliminar registro", key="del_btn"):
        st.session_state.db = df_db[df_db["CodProd"] != deleted].reset_index(drop=True)
        st.success(f"✔️ {deleted} eliminado")

# ─── 6) Descarga XLSX y CSV ────────────────────────
def to_excel_bytes(df):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="Base")
        bk = w.book; ws = w.sheets["Base"]
        fmt_txt = bk.add_format({"num_format":"@", "font":"Calibri"})
        fmt_num = bk.add_format({"num_format":"0.00","font":"Calibri"})
        for i, c in enumerate(df.columns):
            if c in ("CodEstab","CodProd"): ws.set_column(i, i, 15, fmt_txt)
            elif c in ("Precio 1","Precio 2"): ws.set_column(i, i, 15, fmt_num)
            else: ws.set_column(i, i, 15)
    return buf.getvalue()

st.download_button("⬇️ Descargar XLSX",
    data=to_excel_bytes(df_db),
    file_name="base_actualizada.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
csv_data = df_db.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Descargar CSV",
    data=csv_data,
    file_name="base_actualizada.csv",
    mime="text/csv"
)
