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
def load_catalog(uploaded):
    return pd.read_excel(uploaded, header=6) if uploaded else None

@st.cache_data
def load_base(uploaded):
    return pd.read_excel(uploaded) if uploaded else None

df_cat    = load_catalog(catalog_file)
df_loaded = load_base(base_file)

if df_cat is not None and df_loaded is not None:

    # ── Inicializar session_state ────────────────────
    if "db" not in st.session_state:
        df_loaded["CodEstab"] = df_loaded["CodEstab"].astype(str).str.zfill(7)
        st.session_state.db = df_loaded.copy()
    df_db = st.session_state.db

    # ── 2) Búsqueda y selección con clic ─────────────
    st.header("🔎 Buscar producto en catálogo")
    query = st.text_input("Buscar por código o nombre:")
    df_filt = (
        df_cat[df_cat.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
        if query else df_cat
    )

    # Configura AgGrid para selección de fila única
    gb = GridOptionsBuilder.from_dataframe(df_filt)
    gb.configure_selection("single", use_checkbox=False)
    grid_options = gb.build()

    grid_resp = AgGrid(
        df_filt,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        height=300,
        fit_columns_on_grid_load=True
    )

    selected = grid_resp["selected_rows"]
    # Evitamos el ValueError comprobando la longitud
    if isinstance(selected, list) and len(selected) > 0:
        row0   = selected[0]
        codigo = row0.get("Cod_Prod")
        st.success(f"Producto seleccionado: **{codigo}**")
    else:
        codigo = None
        st.info("➡️ Haz clic en una fila para seleccionar el producto")

    # ── 3) Precios y cálculo (solo si hay selección) ──
    if codigo:
        st.subheader("💲 Precios")
        precio_unit = st.number_input("Precio unitario (Precio 2)", min_value=0.0, format="%.2f")
        unidades    = st.number_input("Unidades por caja", min_value=1, step=1)
        precio_caja = unidades * precio_unit
        st.write(f"**Precio de caja (Precio 1):** {precio_caja:,.2f}")

        # ── 4) Añadir registro ───────────────────────────
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
                st.session_state.db = pd.concat(
                    [df_db, pd.DataFrame([nueva])],
                    ignore_index=True
                )
                st.success("✔️ Producto añadido")
            df_db = st.session_state.db

    # ── 5) Vista previa ──────────────────────────────
    st.subheader("📋 Base mensual actualizada")
    st.dataframe(df_db, use_container_width=True, height=300)

    # ── 6) Editar un registro ────────────────────────
    with st.expander("✏️ Editar un registro"):
        prod_edit = st.selectbox(
            "Selecciona CodProd a editar",
            options=df_db["CodProd"].unique(),
            key="edit_prod"
        )
        if prod_edit:
            idx        = df_db.index[df_db["CodProd"] == prod_edit][0]
            curr_unit  = float(df_db.at[idx, "Precio 2"])
            curr_units = int(df_db.at[idx, "Precio 1"] / curr_unit) if curr_unit else 1

            new_unit  = st.number_input(
                "Nuevo precio unitario",
                value=curr_unit,
                format="%.2f",
                key="new_unit"
            )
            new_units = st.number_input(
                "Nuevas unidades por caja",
                value=curr_units,
                step=1,
                key="new_units"
            )
            new_caja  = new_unit * new_units
            st.write(f"→ Nuevo precio de caja: {new_caja:,.2f}")

            if st.button("💾 Guardar cambios", key="save_edit"):
                df_db.at[idx, "Precio 2"] = new_unit
                df_db.at[idx, "Precio 1"] = new_caja
                st.session_state.db       = df_db
                st.success(f"✔️ {prod_edit} actualizado")
                df_db = st.session_state.db

    # ── 7) Eliminar un registro ───────────────────────
    with st.expander("🗑️ Eliminar un registro"):
        prod_del = st.selectbox(
            "Selecciona CodProd a eliminar",
            options=df_db["CodProd"].unique(),
            key="del_prod"
        )
        if st.button("❌ Eliminar registro", key="apply_delete"):
            st.session_state.db = df_db[df_db["CodProd"] != prod_del].reset_index(drop=True)
            st.success(f"✔️ {prod_del} eliminado")
            df_db = st.session_state.db

    # ── 8) Descargas ──────────────────────────────────
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

else:
    st.sidebar.info("📥 Sube los dos archivos para comenzar")
