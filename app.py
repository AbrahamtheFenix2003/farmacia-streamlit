import streamlit as st
import pandas as pd
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ─── Configuración de la página ────────────────────
st.set_page_config(page_title="Carga automática farmacia", layout="wide")

# ─── Subida de archivos ────────────────────────────
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

if df_cat is None or df_loaded is None:
    st.sidebar.info("📥 Sube ambos archivos para continuar")
    st.stop()

# ─── Inicializar base en session_state ────────────
if "db" not in st.session_state:
    # normalizar CodEstab a 7 dígitos
    df_loaded["CodEstab"] = df_loaded["CodEstab"].astype(str).str.zfill(7)
    st.session_state.db   = df_loaded.copy()

df_db = st.session_state.db

# ─── 1) Buscar y seleccionar con AgGrid ───────────
st.header("🔎 Buscar producto en catálogo")
query = st.text_input("Buscar por código o nombre:")
df_filt = (
    df_cat[df_cat.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
    if query else
    df_cat
)

# configurar AgGrid
gb = GridOptionsBuilder.from_dataframe(df_filt)
gb.configure_selection("single", use_checkbox=False)
grid_opts = gb.build()

grid_resp = AgGrid(
    df_filt,
    gridOptions=grid_opts,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    height=300,
    fit_columns_on_grid_load=True
)

# procesar selección
selected = grid_resp["selected_rows"]
if isinstance(selected, list) and len(selected) > 0:
    st.session_state.selected_code = selected[0]["Cod_Prod"]

codigo = st.session_state.get("selected_code", None)

if codigo:
    st.success(f"✅ Producto seleccionado: **{codigo}**")
else:
    st.info("➡️ Haz clic en una fila para seleccionar el producto")

# ─── 2) Precios y añadir (solo tras selección) ────
if codigo:
    st.subheader("💲 Precios")
    precio_unit = st.number_input("Precio unitario (Precio 2)", min_value=0.0, format="%.2f")
    unidades    = st.number_input("Unidades por caja",      min_value=1,   step=1)
    precio_caja = unidades * precio_unit
    st.write(f"**Precio de caja (Precio 1):** {precio_caja:,.2f}")

    if st.button("➕ Añadir a la base"):
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

# ─── 4) Editar un registro ────────────────────────
with st.expander("✏️ Editar un registro"):
    prod_edit = st.selectbox(
        "Selecciona CodProd a editar",
        options=df_db["CodProd"].unique(),
        key="edit_prod"
    )
    if prod_edit:
        idx = df_db.index[df_db["CodProd"] == prod_edit][0]
        curr_unit  = float(df_db.at[idx, "Precio 2"])
        curr_units = int(df_db.at[idx, "Precio 1"] / curr_unit) if curr_unit else 1

        new_unit  = st.number_input("Nuevo precio unitario", value=curr_unit, format="%.2f", key="new_unit")
        new_units = st.number_input("Nuevas unidades por caja", value=curr_units, step=1, key="new_units")
        new_caja  = new_unit * new_units
        st.write(f"→ Nuevo precio de caja: {new_caja:,.2f}")

        if st.button("💾 Guardar cambios", key="save_edit"):
            df_db.at[idx, "Precio 2"] = new_unit
            df_db.at[idx, "Precio 1"] = new_caja
            st.session_state.db       = df_db
            st.success(f"✔️ {prod_edit} actualizado")

# ─── 5) Eliminar un registro ───────────────────────
with st.expander("🗑️ Eliminar un registro"):
    prod_del = st.selectbox(
        "Selecciona CodProd a eliminar",
        options=df_db["CodProd"].unique(),
        key="del_prod"
    )
    if st.button("❌ Eliminar registro", key="apply_delete"):
        st.session_state.db = df_db[df_db["CodProd"] != prod_del].reset_index(drop=True)
        st.success(f"✔️ {prod_del} eliminado")

# ─── 6) Descargas ──────────────────────────────────
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="Base")
        bk = w.book
        ws = w.sheets["Base"]
        fmt_txt = bk.add_format({"num_format":"@",    "font":"Calibri"})
        fmt_num = bk.add_format({"num_format":"0.00", "font":"Calibri"})
        for i, c in enumerate(df.columns):
            if c in ("CodEstab","CodProd"):
                ws.set_column(i, i, 15, fmt_txt)
            elif c in ("Precio 1","Precio 2"):
                ws.set_column(i, i, 15, fmt_num)
            else:
                ws.set_column(i, i, 15)
    return buf.getvalue()

st.download_button(
    "⬇️ Descargar base_actualizada.xlsx",
    data=to_excel_bytes(df_db),
    file_name="base_actualizada.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

csv_bytes = df_db.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Descargar base_actualizada.csv",
    data=csv_bytes,
    file_name="base_actualizada.csv",
    mime="text/csv"
)
