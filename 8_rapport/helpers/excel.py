from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

def schrijf_excel(tabellen: dict[str, pd.DataFrame], pad: Path) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(pad, engine="openpyxl") as writer:
        geschreven = False
        for naam, df in tabellen.items():
            if df.empty:
                continue
            sheet = excel_sheetnaam(naam)
            excel_veilig_df(df).to_excel(writer, sheet_name=sheet, index=False)
            geschreven = True
            ws = writer.book[sheet]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for column_cells in ws.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 45)
        if not geschreven:
            pd.DataFrame(
                [{"Melding": "Geen complete voorzieningenruns gevonden voor rapporttabellen."}]
            ).to_excel(writer, sheet_name="geen_data", index=False)


def excel_sheetnaam(naam: str) -> str:
    sheet = re.sub(r"[\[\]:*?/\\]", "_", naam).strip()
    return (sheet or "tabel")[:31]


def excel_veilig_df(df: pd.DataFrame) -> pd.DataFrame:
    veilig = df.replace([float("inf"), -float("inf")], pd.NA).copy()
    for kolom in veilig.select_dtypes(include=["object", "string"]).columns:
        veilig[kolom] = veilig[kolom].map(excel_veilige_waarde)
    return veilig


def excel_veilige_waarde(waarde: object) -> object:
    if pd.isna(waarde):
        return ""
    tekst = ILLEGAL_CHARACTERS_RE.sub("", str(waarde))
    return tekst[:32767]
