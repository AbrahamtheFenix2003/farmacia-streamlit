import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Carga automática farmacia", layout="wide")

st.sidebar.header("📂 Cargar archivos")
catalog_file = st.sidebar.file_uploader("Catálogo (.xlsx)", type="xlsx")
base_file    = st.sidebar.file_uploader("Base mensual (.xlsx)", type="xlsx")

@st.cache_data
def load_catalog(uploaded):
    return pd.read_excel(uploaded, header=6) if uploaded else None

@st.cache_data
def load_base(uploaded):
    return pd.read_excel(uploaded) if uploaded else None

df_cat = load_catalog(catalog_file)
df_db  = load_base(base_file)

# ————— SOLO SI SUBIÓ AMBOS ARCHIVOS —————
if df_cat is not None and df_db is not None:

    # Normalizar CodEstab
    df_db["CodEstab"] = df_db["CodEstab"].astype(str).str.zfill(7)

    # 2. Búsqueda y selección
    st.header("🔎 Buscar producto en catálogo")
    query = st.text_input("Buscar por código o nombre:")
    df_filt = (
        df_cat[df_cat.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
        if query else
        df_cat
    )
    st.dataframe(df_filt, use_container_width=True, height=300)

    codigo = st.selectbox(
        "Selecciona el Cod_Prod a insertar:",
        options=df_filt["Cod_Prod"].unique()
    )

    # 3. Precios
    st.subheader("💲 Precios")
    precio_unit = st.number_input("Precio unitario (Precio 2)", min_value=0.0, format="%.2f")
    unidades    = st.number_input("Unidades por caja", min_value=1, step=1)
    precio_caja = unidades * precio_unit
    st.write(f"**Precio de caja (Precio 1):** {precio_caja:,.2f}")

    # 4. Añadir
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
            st.success("✔️ Añadido")

    # 5. Vista previa
    st.subheader("📋 Base mensual actualizada")
    st.dataframe(df_db, use_container_width=True, height=300)

    # 6. Descargas
    def to_excel_bytes(df):
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
            df.to_excel(w, index=False, sheet_name="Base")
            bk  = w.book
            ws  = w.sheets["Base"]
            txt = bk.add_format({"num_format":"@",    "font":"Calibri"})
            num = bk.add_format({"num_format":"0.00", "font":"Calibri"})
            for i,c in enumerate(df.columns):
                if c in ("CodEstab","CodProd"): ws.set_column(i,i,15,txt)
                elif c in ("Precio 1","Precio 2"): ws.set_column(i,i,15,num)
                else: ws.set_column(i,i,15)
        return buf.getvalue()

    st.download_button("⬇️ Descargar XLSX",
        data=to_excel_bytes(df_db),
        file_name="base_actualizada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    csv_bytes = df_db.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV",
        data=csv_bytes,
        file_name="base_actualizada.csv",
        mime="text/csv"
    )

else:
    st.sidebar.info("📥 Sube los dos archivos para comenzar")
