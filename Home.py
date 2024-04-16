import io

import streamlit as st
import pandas as pd
import plotly.express as px
import xlsxwriter

st.set_page_config(layout="wide")

# Upload the bank transfer data as a .csv
uploaded_file = st.file_uploader("Kontoauszug")

if uploaded_file:
    bank_transfer_df = df = pd.read_csv(uploaded_file, sep=";")
    # Replace the german decimal seperator by a better one
    bank_transfer_df["Betrag"] = bank_transfer_df["Betrag"].str.replace(",", ".")
    bank_transfer_df["Saldo nach Buchung"] = bank_transfer_df["Saldo nach Buchung"].str.replace(",", ".")
    bank_transfer_df["Betrag"] = bank_transfer_df["Betrag"].astype("float")

    # Add cols for Type and Mitglied
    bank_transfer_df["Type"] = None
    bank_transfer_df["Mitglied"] = None

    bank_transfer_df = bank_transfer_df[[
        "Valutadatum",
        "Name Zahlungsbeteiligter",
        "Betrag",
        "Waehrung",
        "Verwendungszweck",
        "Type",
        "Mitglied",
        "Buchungstext",
        "Saldo nach Buchung",
        ]]

    bank_transfer_df["Type"] = None
    bank_transfer_df.loc[(bank_transfer_df["Betrag"] > 0) & (bank_transfer_df["Buchungstext"] ==
                                                             "Dauerauftragsgutschr"), "Type"] = "Mitgliedschaft"
    bank_transfer_df.loc[(bank_transfer_df["Betrag"] > 0) & (bank_transfer_df["Buchungstext"] ==
                                                             "Überweisungsgutschr."), "Type"] = "Einmalspende"
    bank_transfer_df.loc[(bank_transfer_df["Betrag"] < 0) & (bank_transfer_df["Buchungstext"] ==
                                                             "Internet-Ausl.-Überweisung"), "Type"] = "Spende an CANAT"
    bank_transfer_df.loc[(bank_transfer_df["Betrag"] < 0) & (bank_transfer_df["Buchungstext"] !=
                                                             "Internet-Ausl.-Überweisung"), "Type"] = "Sonstige Ausgabe"

    bank_transfer_df["Mitglied"] = False
    bank_transfer_df.loc[bank_transfer_df["Type"] == "Mitgliedschaft", "Mitglied"] = True

    edited_bank_transfer_df = st.data_editor(bank_transfer_df,
                   hide_index=True,
                   disabled=(
        "Valutadatum",
        "Name Zahlungsbeteiligter",
        "Betrag",
        "Waehrung",
        "Verwendungszweck",
        "Type",
        "Buchungstext",
        "Saldo nach Buchung"))

    #st.subheader("Income")
    income_df = edited_bank_transfer_df.loc[edited_bank_transfer_df["Betrag"] > 0, :]
    income_df = income_df.sort_values("Mitglied", ascending=False)
    income_df.set_index("Name Zahlungsbeteiligter", inplace=True)
    #st.dataframe(income_df, hide_index=True, height=200)


    st.subheader("Aggregated Incomes")
    income_df["Betrag gesamt"] = income_df["Betrag"]
    grouped_income_df = income_df.groupby("Name Zahlungsbeteiligter").agg({"Betrag gesamt":"sum",
                                                                           "Betrag": lambda x: list(x),
                                                                           "Mitglied": "all",
                                                                           "Valutadatum":lambda x: list(x),
    })
    grouped_income_df = grouped_income_df.sort_values("Mitglied", ascending=False)
    st.dataframe(grouped_income_df)


    st.subheader("Expenses")
    expenses_df = edited_bank_transfer_df.loc[edited_bank_transfer_df["Betrag"] <= 0, :]
    expenses_df.drop(columns=["Mitglied"], inplace=True)
    expenses_df.sort_values("Name Zahlungsbeteiligter", ascending=False, inplace=True)

    expenses_df.loc[expenses_df["Verwendungszweck"].str.contains("GLS Beitrag"), "Type"] = "GLS Beitrag"
    expenses_df.loc[(expenses_df["Verwendungszweck"].str.contains("Abschluss")) &
                    (expenses_df["Name Zahlungsbeteiligter"].isna()), "Type"] = "Kontoführungsgebühr"
    expenses_df.loc[expenses_df["Type"] == "Kontoführungsgebühr", "Name Zahlungsbeteiligter"] = "GLS Bank"

    # Make the expenses_df a bit more pretty
    expenses_df = expenses_df[[
        "Name Zahlungsbeteiligter",
        "Type",
        "Betrag",
        "Waehrung",
        "Valutadatum",
        #"Buchungstext",
        #"Verwendungszweck",
        #"Saldo nach Buchung"
        ]]
    expenses_df.set_index("Name Zahlungsbeteiligter", inplace=True)

    st.dataframe(expenses_df, height=200)


    st.subheader("Overview")
    overview_df = pd.DataFrame({
        "Posten": [
        "Einnamhmen durch Mitgliedschaften",
        "Einnahmen durch Einmalspenden",
        "Überweisungen an CANAT",
        "Sonstige Ausgaben"],
        "Betrag": [
        income_df.loc[income_df["Mitglied"] == True, "Betrag"].sum(),
        income_df.loc[income_df["Mitglied"] == False, "Betrag"].sum(),
        expenses_df.loc[expenses_df["Type"] == "Spende an CANAT", "Betrag"].sum(),
        expenses_df.loc[expenses_df["Type"] == "Sonstige Ausgabe", "Betrag"].sum()

        ]})

    st.dataframe(overview_df, hide_index=True)

    if st.button("Prepare Download"):

        output_excel = io.BytesIO()

        with pd.ExcelWriter(output_excel, engine="xlsxwriter") as writer:
            edited_bank_transfer_df.to_excel(writer, sheet_name="Kontobewegung")
            grouped_income_df.to_excel(writer, sheet_name="Einnahmen")
            expenses_df.to_excel(writer, sheet_name="Ausgaben")
            overview_df.to_excel(writer, sheet_name="Übersicht")

            #writer.save()

        output_excel.seek(0)

        st.download_button("Download", data=output_excel, file_name="Finanzen_Amigas_CANAT.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


    st.subheader("Saldo")
    saldo_fig = px.line(data_frame=bank_transfer_df, x="Valutadatum", y="Saldo nach Buchung")
    st.plotly_chart(saldo_fig)













