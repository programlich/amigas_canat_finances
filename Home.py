import io

import streamlit as st
import pandas as pd
import plotly.express as px
import xlsxwriter

st.set_page_config(layout="wide")

input_and_metric_cols = st.container(border=True).columns([0.15, 0.3, 0.3, 0.3])

# Upload the bank transfer data as a .csv
uploaded_file = input_and_metric_cols[0].container(border=True).file_uploader("Kontoauszug")

if uploaded_file:
    bank_transfer_df = df = pd.read_csv(uploaded_file, sep=";")

    # Replace the german decimal seperator by a better one
    bank_transfer_df["Betrag"] = bank_transfer_df["Betrag"].str.replace(",", ".")
    bank_transfer_df["Saldo nach Buchung"] = bank_transfer_df["Saldo nach Buchung"].str.replace(",", ".")
    bank_transfer_df["Betrag"] = bank_transfer_df["Betrag"].astype("float")

    # Create datetime objects from the Valutadatum col and sort the df according to these
    bank_transfer_df["Valutadatum_datetime"] = pd.to_datetime(bank_transfer_df["Valutadatum"], format="%d.%m.%Y",
                                                              errors="coerce")
    bank_transfer_df.sort_values("Valutadatum_datetime", inplace=True, ignore_index=True)

    # Add cols for Type and Mitglied
    bank_transfer_df["Type"] = None
    bank_transfer_df["Mitglied"] = None

    bank_transfer_df = bank_transfer_df[[
        "Valutadatum",
        "Valutadatum_datetime",
        "Name Zahlungsbeteiligter",
        "Betrag",
        "Waehrung",
        "Verwendungszweck",
        "Type",
        "Mitglied",
        "Buchungstext",
        "Saldo nach Buchung",
    ]]

    # Add Type column to df and fill it with values according to the values of other cols
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

    # Create an editable bank tranfer df to manually set a donation to be from a member or not
    with st.expander("Überweisungen", expanded=True):
        transfer_cols = st.columns([0.8,0.2])
        edited_bank_transfer_df = transfer_cols[0].data_editor(bank_transfer_df,
                                             hide_index=True,
                                             disabled=(
                                                 "Valutadatum",
                                                 "Name Zahlungsbeteiligter",
                                                 "Betrag",
                                                 "Waehrung",
                                                 "Verwendungszweck",
                                                 "Type",
                                                 "Buchungstext",
                                                 "Saldo nach Buchung"),
                                             column_order=(
                                                 "Valutadatum",
                                                 "Name Zahlungsbeteiligter",
                                                 "Betrag",
                                                 "Verwendungszweck",
                                                 "Type",
                                                 "Mitglied",
                                                 "Buchungstext"), use_container_width=True, height=450)

        saldo_fig = px.line(data_frame=bank_transfer_df, x="Valutadatum", y="Saldo nach Buchung")
        transfer_cols[1].plotly_chart(saldo_fig, use_container_width=True)

    income_df = edited_bank_transfer_df.loc[edited_bank_transfer_df["Betrag"] > 0, :]
    income_df = income_df.sort_values("Mitglied", ascending=False)
    income_df.set_index("Name Zahlungsbeteiligter", inplace=True)

    # Group the bank tranfer df by person
    income_df["Betrag gesamt"] = income_df["Betrag"]
    grouped_income_df = income_df.groupby("Name Zahlungsbeteiligter").agg({"Betrag gesamt": "sum",
                                                                           "Betrag": lambda x: list(x),
                                                                           "Mitglied": "all",
                                                                           "Valutadatum": lambda x: list(x),
                                                                           })
    grouped_income_df = grouped_income_df.sort_values("Mitglied", ascending=False)

    income_expenses_cols = st.container().columns([0.6,0.4])

    income_expenses_cols[0].write("#### Einnahmen")
    income_expenses_cols[0].dataframe(grouped_income_df, use_container_width=True)

    # Calculate and display the expenses
    income_expenses_cols[1].write("#### Ausgaben")
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
    income_expenses_cols[1].dataframe(expenses_df, use_container_width=True)

    overview_df = pd.DataFrame({
        "Posten": [
            "Einnahmen durch Mitgliedschaften",
            "Einnahmen durch Einmalspenden",
            "Überweisungen an CANAT",
            "Sonstige Ausgaben"],
        "Betrag": [
            income_df.loc[income_df["Mitglied"] == True, "Betrag"].sum(),
            income_df.loc[income_df["Mitglied"] == False, "Betrag"].sum(),
            expenses_df.loc[expenses_df["Type"] == "Spende an CANAT", "Betrag"].sum(),
            expenses_df.loc[expenses_df["Type"] == "Sonstige Ausgabe", "Betrag"].sum()
        ]})
    st.dataframe(overview_df)
    # Add the overview metrics at the top of the page
    # Date range
    start_date = bank_transfer_df["Valutadatum_datetime"].min().strftime("%d.%m.%Y")
    end_date = bank_transfer_df["Valutadatum_datetime"].max().strftime("%d.%m.%Y")
    input_and_metric_cols[1].container(border=True).metric(label="Zeitraum", value=f"{start_date} -\n   {end_date}")

    # Members
    num_members = (grouped_income_df["Mitglied"] == True).sum()
    input_and_metric_cols[1].container(border=True).metric(label="Aktive Mitglieder", value=num_members)

    # Income
    total_income = overview_df.loc[overview_df["Posten"].isin(["Einnahmen durch Mitgliedschaften",
                                                               "Einnahmen durch Einmalspenden"]), "Betrag"].sum()
    income_members = overview_df.loc[overview_df["Posten"] == "Einnahmen durch Mitgliedschaften", "Betrag"].sum()
    income_donations = overview_df.loc[overview_df["Posten"] == "Einnahmen durch Einmalspenden", "Betrag"].sum()

    input_and_metric_cols[2].container(border=True).metric(label="Einnahmen gesamt", value=f"{total_income}",
                                                           delta="€")
    income_cols = input_and_metric_cols[2].container().columns(2)
    income_cols[0].container(border=True).metric(label="Mitgliedschaften", value=f"{income_members}",
                                                 delta="€")
    income_cols[1].container(border=True).metric(label="Spenden", value=f"{income_donations}",
                                                 delta="€")

    # Expenses
    total_expenses = overview_df.loc[overview_df["Posten"].isin(["Überweisungen an CANAT", "Sonstige Ausgaben"]),
    "Betrag"].sum()
    expenses_canat = overview_df.loc[overview_df["Posten"] == "Überweisungen an CANAT", "Betrag"].sum()
    expenses_misc = overview_df.loc[overview_df["Posten"] == "Sonstige Ausgaben", "Betrag"].sum()

    input_and_metric_cols[3].container(border=True).metric(label="Ausgaben gesamt", value=f"{-total_expenses}",
                                                           delta="- €")
    expenses_cols = input_and_metric_cols[3].container().columns(2)
    expenses_cols[0].container(border=True).metric(label="an CANAT", value=f"{-expenses_canat}", delta="- €")
    expenses_cols[1].container(border=True).metric(label="Sonstiges", value=f"{-expenses_misc}", delta="- €")



    download_cols = input_and_metric_cols[0].container().columns(2)
    if download_cols[0].button("Prepare Download", use_container_width=True):
        output_excel = io.BytesIO()

        with pd.ExcelWriter(output_excel, engine="xlsxwriter") as writer:
            edited_bank_transfer_df.to_excel(writer, sheet_name="Kontobewegung")
            grouped_income_df.to_excel(writer, sheet_name="Einnahmen")
            expenses_df.to_excel(writer, sheet_name="Ausgaben")
            overview_df.to_excel(writer, sheet_name="Übersicht")

        output_excel.seek(0)

        download_cols[1].download_button("Download", use_container_width=True, type="primary",
                                         data=output_excel,
                                         file_name="Finanzen_Amigas_CANAT.xlsx",
                                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

