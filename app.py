import streamlit as st
import pandas as pd
from script import extract_invoice_data, create_dataframe_from_invoices

st.set_page_config(page_title="📄 Ekstraktor Danych z Faktur", layout="wide")
st.title("📄 Ekstraktor Danych z Faktur")

uploaded_files = st.file_uploader(
    "Prześlij faktury (PDF, JPG, PNG)",
    type=['pdf', 'jpg', 'png'],
    accept_multiple_files=True
)

if uploaded_files:
    results = []
    for file in uploaded_files:
        with st.spinner(f"Przetwarzanie {file.name}..."):
            with open(file.name, "wb") as f:
                f.write(file.read())
            data = extract_invoice_data(file.name)
            if data:
                data["plik"] = file.name
                results.append(data)
                st.success(f"✅ Odczytano {file.name}")
                st.json(data)
            else:
                st.error(f"❌ Nie udało się odczytać {file.name}")

    if results:
        df = create_dataframe_from_invoices({"faktury": results})
        st.subheader("📊 Zestawienie faktur")
        st.dataframe(df)

        st.metric("💰 Suma wszystkich faktur", f"{df['suma_brutto'].sum():.2f} PLN")
        st.metric("📈 Średnia wartość", f"{df['suma_brutto'].mean():.2f} PLN")
        st.metric("🏢 Najczęstszy dostawca", df["sprzedawca"].mode().iloc[0])
