"""Recalculate Excel file using Microsoft Excel COM automation and check for errors."""
import json
import os

import win32com.client

path = r'C:\Users\geoff\OneDrive\Brookfield Gardens\Brookfield_Gardens_Financial_Model.xlsx'
path = os.path.abspath(path)

xl = win32com.client.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False

try:
    wb = xl.Workbooks.Open(path)
    xl.Calculate()
    wb.Save()

    # Scan for errors
    error_values = {-2146826281, -2146826246, -2146826245, -2146826252,
                    -2146826260, -2146826258, -2146826259, -2146826288}
    error_names = {
        -2146826281: '#DIV/0!',
        -2146826246: '#N/A',
        -2146826245: '#NAME?',
        -2146826252: '#NULL!',
        -2146826260: '#NUM!',
        -2146826258: '#REF!',
        -2146826259: '#VALUE!',
        -2146826288: '#VALUE!',
    }

    errors = {}
    total_formulas = 0
    results = {}

    for ws in wb.Worksheets:
        used = ws.UsedRange
        for row in used.Rows:
            for cell in row.Cells:
                if cell.HasFormula:
                    total_formulas += 1
                    v = cell.Value
                    if isinstance(v, int) and v in error_values:
                        ename = error_names.get(v, f'ERR({v})')
                        ref = f"{ws.Name}!{cell.Address}"
                        if ename not in errors:
                            errors[ename] = {"count": 0, "locations": []}
                        errors[ename]["count"] += 1
                        errors[ename]["locations"].append(ref)

    # Get key validation values
    def get_val(sheet_name, cell_addr):
        try:
            return wb.Worksheets(sheet_name).Range(cell_addr).Value
        except:
            return None

    # Tab 2: OpCo P&L - rows based on our row map
    # TOTAL_REV_ROW=7, cols B=Y2, C=Y3, D=Y4, E=Y5
    opco_rev_y2 = get_val("OpCo P&L", "B7")
    opco_lett_y4 = get_val("OpCo P&L", "D5")  # LETTUCE_ROW=5
    opco_grid_y4 = get_val("OpCo P&L", "D6")  # GRID_ROW=6
    # Tab 3: EBITDA row 19, cols C=Y2, F=Y5
    propco_ebitda_y2 = get_val("PropCo P&L & BS", "C19")
    propco_ebitda_y5 = get_val("PropCo P&L & BS", "F19")
    # Balance sheet: TOTAL_ASSETS_ROW=46, TOTAL_LE_ROW=53, col B=Day1
    total_assets_d1 = get_val("PropCo P&L & BS", "B46")
    total_le_d1 = get_val("PropCo P&L & BS", "B53")
    # DSCR: row 21, cols B-E
    dscr_y2 = get_val("Cash Flow", "B21")
    dscr_y3 = get_val("Cash Flow", "C21")
    dscr_y4 = get_val("Cash Flow", "D21")
    dscr_y5 = get_val("Cash Flow", "E21")

    result = {
        "status": "errors_found" if errors else "success",
        "total_errors": sum(e["count"] for e in errors.values()),
        "total_formulas": total_formulas,
        "error_summary": errors if errors else {},
        "validation": {
            "tab2_total_rev_y2": opco_rev_y2,
            "tab2_lettuce_y4": opco_lett_y4,
            "tab2_grid_y4": opco_grid_y4,
            "tab3_propco_ebitda_y2": propco_ebitda_y2,
            "tab3_propco_ebitda_y5": propco_ebitda_y5,
            "tab3_total_assets_day1": total_assets_d1,
            "tab3_total_le_day1": total_le_d1,
            "tab4_dscr_y2": dscr_y2,
            "tab4_dscr_y3": dscr_y3,
            "tab4_dscr_y4": dscr_y4,
            "tab4_dscr_y5": dscr_y5,
        }
    }

    print(json.dumps(result, indent=2))

except Exception as e:
    print(json.dumps({"status": "error", "message": str(e)}))
finally:
    try:
        wb.Close(False)
    except:
        pass
    xl.Quit()
