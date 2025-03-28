import io
import streamlit as st
import pandas as pd
import plotly.express as px
import xlsxwriter

st.set_page_config(layout="wide")

input_and_metric_cols = st.container(border=True).columns([0.2, 0.8])

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

    # Remove unnecessary cols
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
        transfer_cols = st.columns([0.8, 0.2])

        edited_bank_transfer_df = transfer_cols[0].data_editor(bank_transfer_df,
                                                               hide_index=True,
                                                               disabled=(
                                                                   "Valutadatum",
                                                                   "Name Zahlungsbeteiligter",
                                                                   "Betrag",
                                                                   "Waehrung",
                                                                   "Verwendungszweck",
                                                                   "Buchungstext",
                                                                   "Saldo nach Buchung"),
                                                               column_order=(
                                                                   "Valutadatum",
                                                                   "Name Zahlungsbeteiligter",
                                                                   "Betrag",
                                                                   "Verwendungszweck",
                                                                   "Type",
                                                                   "Mitglied",
                                                                   "Buchungstext"), use_container_width=True,
                                                               height=450)

        saldo_fig = px.line(data_frame=bank_transfer_df, x="Valutadatum", y="Saldo nach Buchung",
                            color_discrete_sequence=["#D4A86A"])
        saldo_fig.update_traces(line={"width": 3})
        transfer_cols[1].plotly_chart(saldo_fig, use_container_width=True)

    income_df = edited_bank_transfer_df.loc[edited_bank_transfer_df["Betrag"] > 0, :]
    income_df = income_df.sort_values("Mitglied", ascending=False)
    income_df.set_index("Name Zahlungsbeteiligter", inplace=True)

    # Make separate income_dfs for members and donations
    income_members_df = income_df[income_df["Mitglied"] == True].copy()
    income_donations_df = income_df[income_df["Mitglied"] == False].copy()
    income_members_df.drop(columns=["Valutadatum_datetime", "Buchungstext", "Mitglied", "Type"], inplace=True)
    income_donations_df.drop(columns=["Valutadatum_datetime", "Buchungstext", "Mitglied", "Type"], inplace=True)

    # Group the bank tranfer df by person
    income_df["Betrag gesamt"] = income_df["Betrag"]
    grouped_income_df = income_df.groupby("Name Zahlungsbeteiligter").agg({"Betrag gesamt": "sum",
                                                                           "Betrag": lambda x: list(x),
                                                                           "Mitglied": "all",
                                                                           "Valutadatum": lambda x: list(x),
                                                                           })
    grouped_income_df = grouped_income_df.sort_values("Mitglied", ascending=False)

    income_expenses_cols = st.container().columns([0.6, 0.4])

    income_expenses_cols[0].write("#### Einnahmen")
    income_expenses_cols[0].dataframe(grouped_income_df, use_container_width=True)

    # Calculate and display the expenses
    income_expenses_cols[1].write("#### Ausgaben")
    expenses_df = edited_bank_transfer_df.loc[edited_bank_transfer_df["Betrag"] <= 0, :].copy()
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
    ]]
    expenses_df.set_index("Name Zahlungsbeteiligter", inplace=True)
    income_expenses_cols[1].data_editor(expenses_df, use_container_width=True,
                                        disabled=["Waehrung", "Betrag", "Valutadatum"])

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

    # Add the overview metrics at the top of the page
    date_and_member_cols = input_and_metric_cols[1].container().columns([0.7, 0.3])
    income_expenses_metrics_cols_top = input_and_metric_cols[1].container().columns(2)
    income_expenses_metrics_cols_bottom = input_and_metric_cols[1].container().columns(4)

    # Date range
    start_date = bank_transfer_df["Valutadatum_datetime"].min().strftime("%d.%m.%y")
    end_date = bank_transfer_df["Valutadatum_datetime"].max().strftime("%d.%m.%y")
    date_and_member_cols[0].container(border=True).metric(label="Zeitraum", value=f"{start_date} -\n   {end_date}")

    # Members
    num_members = (grouped_income_df["Mitglied"] == True).sum()
    date_and_member_cols[1].container(border=True).metric(label="Aktive Mitglieder", value=num_members)

    # Income
    total_income = overview_df.loc[overview_df["Posten"].isin(["Einnahmen durch Mitgliedschaften",
                                                               "Einnahmen durch Einmalspenden"]), "Betrag"].sum()
    income_members = overview_df.loc[overview_df["Posten"] == "Einnahmen durch Mitgliedschaften", "Betrag"].sum()
    income_donations = overview_df.loc[overview_df["Posten"] == "Einnahmen durch Einmalspenden", "Betrag"].sum()

    income_expenses_metrics_cols_top[0].container(border=True).metric(label="Einnahmen gesamt", value=f"{total_income}",
                                                                      delta="€")
    income_expenses_metrics_cols_bottom[0].container(border=True).metric(label="Mitgliedschaften",
                                                                         value=f"{income_members}",
                                                                         delta="€")
    income_expenses_metrics_cols_bottom[1].container(border=True).metric(label="Spenden", value=f"{income_donations}",
                                                                         delta="€")

    # Expenses
    total_expenses = overview_df.loc[overview_df["Posten"].isin(["Überweisungen an CANAT", "Sonstige Ausgaben"]),
    "Betrag"].sum()
    expenses_canat = overview_df.loc[overview_df["Posten"] == "Überweisungen an CANAT", "Betrag"].sum()
    expenses_misc = overview_df.loc[overview_df["Posten"] == "Sonstige Ausgaben", "Betrag"].sum()

    income_expenses_metrics_cols_top[1].container(border=True).metric(label="Ausgaben gesamt",
                                                                      value=f"{total_expenses}",
                                                                      delta="- €")
    income_expenses_metrics_cols_bottom[2].container(border=True).metric(label="an CANAT", value=f"{expenses_canat}",
                                                                         delta="- €")
    income_expenses_metrics_cols_bottom[3].container(border=True).metric(label="Sonstiges", value=f"{expenses_misc}",
                                                                         delta="- €")

    # Download
    download_cols = input_and_metric_cols[0].container().columns(2)
    if download_cols[0].button("Prepare Download", use_container_width=True):
        output_excel = io.BytesIO()

        with pd.ExcelWriter(output_excel, engine="xlsxwriter") as writer:
            # Drop certain cols for the export of edited_bank_transfer_df
            export_bank_transfer_df = edited_bank_transfer_df.drop(
                columns=["Mitglied", "Buchungstext", "Valutadatum_datetime"])
            export_bank_transfer_df.to_excel(writer, sheet_name="Kontobewegung", index=False)

            grouped_income_df.to_excel(writer, sheet_name="Einnahmen gesamt", index=False)
            income_members_df.to_excel(writer, sheet_name="Einnahmen Mitgliedschaften", index=False)
            income_donations_df.to_excel(writer, sheet_name="Einnahmen Einmalspenden", index=False)
            expenses_df.to_excel(writer, sheet_name="Ausgaben", index=False)
            overview_df.to_excel(writer, sheet_name="Übersicht", index=False)

        output_excel.seek(0)

        download_cols[1].download_button("Download", use_container_width=True, type="primary",
                                         data=output_excel,
                                         file_name="Finanzen_Amigas_CANAT.xlsx",
                                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
