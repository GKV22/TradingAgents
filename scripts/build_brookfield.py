"""Build Brookfield Gardens Financial Model - 5-tab OpCo/PropCo structure."""
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

OUT = r"C:\Users\geoff\OneDrive\Brookfield Gardens\Brookfield_Gardens_Financial_Model.xlsx"

DARK_GREEN = "1E4620"
WHITE = "FFFFFF"
BLUE = "0000FF"
BLACK = "000000"
GREEN_LINK = "008000"

FMT_CURR = '$#,##0.00'
FMT_PCT = '0.0%'
FMT_RATE = '0.000%'
FMT_MULT = '0.00x'

def hdr_font(): return Font(name="Arial", bold=True, color=WHITE, size=11)
def input_font(): return Font(name="Arial", color=BLUE, size=10)
def formula_font(): return Font(name="Arial", color=BLACK, size=10)
def link_font(): return Font(name="Arial", color=GREEN_LINK, size=10)
def label_font(): return Font(name="Arial", color=BLACK, size=10)
def section_font(): return Font(name="Arial", bold=True, color=BLACK, size=10)
def bold_font(): return Font(name="Arial", bold=True, color=BLACK, size=10)

def hdr_fill(): return PatternFill("solid", fgColor=DARK_GREEN)

def set_hdr(cell, value):
    cell.value = value
    cell.font = hdr_font()
    cell.fill = hdr_fill()
    cell.alignment = Alignment(horizontal="left", vertical="center")

def set_input(cell, value, fmt=FMT_CURR):
    cell.value = value
    cell.font = input_font()
    cell.number_format = fmt
    cell.alignment = Alignment(horizontal="right")

def set_label(cell, value):
    cell.value = value
    cell.font = label_font()

def set_formula(cell, formula, fmt=FMT_CURR):
    cell.value = formula
    cell.font = formula_font()
    cell.number_format = fmt
    cell.alignment = Alignment(horizontal="right")

def set_link(cell, formula, fmt=FMT_CURR):
    cell.value = formula
    cell.font = link_font()
    cell.number_format = fmt
    cell.alignment = Alignment(horizontal="right")

def set_bold_formula(cell, formula, fmt=FMT_CURR):
    cell.value = formula
    cell.font = bold_font()
    cell.number_format = fmt
    cell.alignment = Alignment(horizontal="right")

def apply_double_bottom(ws, row, col_start, col_end):
    for c in range(col_start, col_end + 1):
        ws.cell(row=row, column=c).border = Border(bottom=Side(border_style="double"))

wb = Workbook()

# ============================================================
# TAB 1: ASSUMPTIONS
# ============================================================
ws1 = wb.active
ws1.title = "Assumptions"
ws1.sheet_view.showGridLines = True
ws1.column_dimensions["A"].width = 40
ws1.column_dimensions["B"].width = 20
ws1.column_dimensions["C"].width = 35

ws1.merge_cells("A1:C1")
set_hdr(ws1["A1"], "ASSUMPTIONS & DRIVERS")
ws1.row_dimensions[1].height = 22

row = 3

def section_hdr(ws, r, title):
    ws.merge_cells(f"A{r}:C{r}")
    set_hdr(ws[f"A{r}"], title)
    return r + 1

def inp_row(ws, r, label, value, fmt=FMT_CURR, named=None):
    set_label(ws.cell(r, 1), label)
    set_input(ws.cell(r, 2), value, fmt)
    if named:
        wb.defined_names.add(DefinedName(name=named, attr_text=f"Assumptions!$B${r}"))
    return r + 1

# SECTION 1 (rows 3-8)
row = section_hdr(ws1, row, "SECTION 1: PROPERTY & ASSET COSTS (PropCo)")
# Row 4: LandCost
row = inp_row(ws1, row, "Land Purchase Price", 275000.00, FMT_CURR, "LandCost")
# Row 5: ShedCost
row = inp_row(ws1, row, "Site Prep & Sheds", 35000.00, FMT_CURR, "ShedCost")
# Row 6: ContainerCost
row = inp_row(ws1, row, "Container Hulls (Containers 1 & 2)", 11500.00, FMT_CURR, "ContainerCost")
# Row 7: SolarCost
row = inp_row(ws1, row, "Solar Power System (25kW)", 30000.00, FMT_CURR, "SolarCost")
row += 1  # Row 8 blank

# SECTION 2 (rows 9-11)
row = section_hdr(ws1, row, "SECTION 2: TECHNOLOGY ASSET COSTS (OpCo)")
# Row 10: GrowTechCost
row = inp_row(ws1, row, "Interior Grow Tech", 50000.00, FMT_CURR, "GrowTechCost")
row += 1  # Row 11 blank

# SECTION 3 (rows 12-22)
row = section_hdr(ws1, row, "SECTION 3: FINANCING PARAMETERS")
# Row 13: FSAOwnershipPct
row = inp_row(ws1, row, "FSA Ownership Loan Land Match %", 0.45, FMT_PCT, "FSAOwnershipPct")
# Row 14: FSAOwnershipRate
row = inp_row(ws1, row, "FSA Ownership Loan Interest Rate", 0.0175, FMT_RATE, "FSAOwnershipRate")
# Row 15: FSAOwnershipTerm
row = inp_row(ws1, row, "FSA Ownership Loan Term (Years)", 40, '0', "FSAOwnershipTerm")
# Row 16: MicroLoanAmt
row = inp_row(ws1, row, "FSA Operating Microloan Amount", 50000.00, FMT_CURR, "MicroLoanAmt")
# Row 17: MicroLoanRate
row = inp_row(ws1, row, "FSA Operating Microloan Interest Rate", 0.035, FMT_RATE, "MicroLoanRate")
# Row 18: MicroLoanTerm
row = inp_row(ws1, row, "FSA Operating Microloan Term (Years)", 7, '0', "MicroLoanTerm")
# Row 19: InfraLoanAmt
row = inp_row(ws1, row, "Infrastructure Loan Amount", 41500.00, FMT_CURR, "InfraLoanAmt")
# Row 20: InfraLoanRate
row = inp_row(ws1, row, "Infrastructure Loan Interest Rate", 0.0375, FMT_RATE, "InfraLoanRate")
# Row 21: InfraLoanTerm
row = inp_row(ws1, row, "Infrastructure Loan Term (Years)", 15, '0', "InfraLoanTerm")
row += 1  # Row 22 blank

# SECTION 4 (rows 23-29)
row = section_hdr(ws1, row, "SECTION 4: PRODUCTION DRIVERS")
# Row 24: PlantSites
row = inp_row(ws1, row, "Active Planting Sites", 8800, '#,##0', "PlantSites")
# Row 25: CropCycles
row = inp_row(ws1, row, "Annual Crop Cycles", 11.0, '#,##0.0', "CropCycles")
# Row 26: BasePrice
row = inp_row(ws1, row, "Baseline Wholesale Price per Unit", 2.25, FMT_CURR, "BasePrice")
# Row 27: PriceInflation
row = inp_row(ws1, row, "Annual Price Inflation", 0.0, FMT_PCT, "PriceInflation")
# Row 28: ScalingFactor
row = inp_row(ws1, row, "Year 4 Scaling Factor (Container 3)", 1.65, '0.00', "ScalingFactor")
row += 1  # Row 29 blank

# SECTION 5 (rows 30-45)
row = section_hdr(ws1, row, "SECTION 5: VARIABLE & FIXED EXPENSE DRIVERS")
# Row 31: COGSPct
row = inp_row(ws1, row, "COGS % of Revenue (baseline)", 0.08, FMT_PCT, "COGSPct")
# Row 32: COGSEscalation
row = inp_row(ws1, row, "Annual COGS Escalation Rate", 0.001, FMT_PCT, "COGSEscalation")
# Row 33: GrowerSalary
row = inp_row(ws1, row, "Assistant Grower Salary (Year 2 base)", 42000.00, FMT_CURR, "GrowerSalary")
# Row 34: WageInflation
row = inp_row(ws1, row, "Annual Wage Inflation", 0.03, FMT_PCT, "WageInflation")
# Row 35: OwnerICHRA
row = inp_row(ws1, row, "Owner/Family ICHRA Base (Year 2)", 30000.00, FMT_CURR, "OwnerICHRA")
# Row 36: EmpICHRA
row = inp_row(ws1, row, "Employee ICHRA Stipend Base (Year 2)", 9600.00, FMT_CURR, "EmpICHRA")
# Row 37: HealthInflation
row = inp_row(ws1, row, "Annual Health Insurance Inflation", 0.05, FMT_PCT, "HealthInflation")
# Row 38: MonthlyRent
row = inp_row(ws1, row, "Intercompany Monthly Rent (OpCo→PropCo)", 2000.00, FMT_CURR, "MonthlyRent")
# Row 39: HVACBase
row = inp_row(ws1, row, "HVAC & CO2 Base Cost per Container-Year", 4800.00, FMT_CURR, "HVACBase")
# Row 40: ContY2
row = inp_row(ws1, row, "Operational Containers Year 2", 1.0, '0.00', "ContY2")
# Row 41: ContY3
row = inp_row(ws1, row, "Operational Containers Year 3", 1.0, '0.00', "ContY3")
# Row 42: ContY4
row = inp_row(ws1, row, "Operational Containers Year 4", 1.65, '0.00', "ContY4")
# Row 43: ContY5
row = inp_row(ws1, row, "Operational Containers Year 5", 1.65, '0.00', "ContY5")
# Row 44: OpCoAdmin
row = inp_row(ws1, row, "OpCo Insurance, Legal & Admin (flat)", 3500.00, FMT_CURR, "OpCoAdmin")
row += 1  # Row 45 blank

# SECTION 6 (rows 46-54)
row = section_hdr(ws1, row, "SECTION 6: PROPCO MAINTENANCE DRIVERS")
# Row 47: PropTaxRate
row = inp_row(ws1, row, "Property Tax Rate (Horry County Ag)", 0.006, FMT_RATE, "PropTaxRate")
# Row 48: PropInsurance
row = inp_row(ws1, row, "Property Liability Insurance (annual)", 1500.00, FMT_CURR, "PropInsurance")
# Row 49: BuildingsRM
row = inp_row(ws1, row, "Buildings & Land R&M (annual)", 2000.00, FMT_CURR, "BuildingsRM")
# Row 50: EquipRM
row = inp_row(ws1, row, "Equipment R&M (annual)", 1800.00, FMT_CURR, "EquipRM")
# Row 51: PropUtilities
row = inp_row(ws1, row, "PropCo Utilities (annual)", 1200.00, FMT_CURR, "PropUtilities")
# Row 52: PropProfFees
row = inp_row(ws1, row, "PropCo Professional Fees (annual)", 1500.00, FMT_CURR, "PropProfFees")
# Row 53: PropInflation
row = inp_row(ws1, row, "PropCo Annual OpEx Inflation", 0.025, FMT_PCT, "PropInflation")
row += 1  # Row 54 blank

# SECTION 7 (rows 55-59)
row = section_hdr(ws1, row, "SECTION 7: ENERGY GRID DRIVERS")
# Row 56: SolarExportHighkWh
row = inp_row(ws1, row, "Solar Export kWh Year 2-3", 18000, '#,##0', "SolarExportHighkWh")
# Row 57: SolarExportLowkWh
row = inp_row(ws1, row, "Solar Export kWh Year 4-5", 6000, '#,##0', "SolarExportLowkWh")
# Row 58: NetMeteringRate
row = inp_row(ws1, row, "Net Metering Credit Rate ($/kWh)", 0.04, FMT_CURR, "NetMeteringRate")
row += 1  # Row 59 blank

# SECTION 8 (rows 60-66)
row = section_hdr(ws1, row, "SECTION 8: TAX DRIVERS")
# Row 61: SETaxRate
row = inp_row(ws1, row, "Federal SE Tax Rate", 0.153, FMT_PCT, "SETaxRate")
# Row 62: SEFactor
row = inp_row(ws1, row, "SE Net Earnings Factor", 0.9235, FMT_PCT, "SEFactor")
# Row 63: IncomeTaxRate
row = inp_row(ws1, row, "Combined Pass-Through Income Tax Rate", 0.18, FMT_PCT, "IncomeTaxRate")
# Row 64: SolarITC
row = inp_row(ws1, row, "Federal Solar ITC Rate (Section 48)", 0.30, FMT_PCT, "SolarITC")
# Row 65: REAPGrant
row = inp_row(ws1, row, "USDA REAP Grant Rate", 0.50, FMT_PCT, "REAPGrant")
row += 1  # Row 66 blank

# SECTION 9 (rows 67-73)
row = section_hdr(ws1, row, "SECTION 9: DEPRECIATION USEFUL LIVES")
# Row 68: ShedsLife
row = inp_row(ws1, row, "Infrastructure Sheds useful life (years)", 15, '0', "ShedsLife")
# Row 69: TractorCost
row = inp_row(ws1, row, "Tractor cost basis", 24500.00, FMT_CURR, "TractorCost")
# Row 70: TractorLife
row = inp_row(ws1, row, "Tractor useful life (years)", 5, '0', "TractorLife")
# Row 71: ContainerLife
row = inp_row(ws1, row, "Container Hulls useful life (years)", 7, '0', "ContainerLife")
# Row 72: SolarLife
row = inp_row(ws1, row, "Solar Power Grid useful life (years)", 5, '0', "SolarLife")

# Confirmed Assumptions cell map:
# B4=LandCost, B5=ShedCost, B6=ContainerCost, B7=SolarCost
# B13=FSAOwnershipPct, B14=FSAOwnershipRate, B15=FSAOwnershipTerm
# B16=MicroLoanAmt, B17=MicroLoanRate, B18=MicroLoanTerm
# B19=InfraLoanAmt, B20=InfraLoanRate, B21=InfraLoanTerm
# B24=PlantSites, B25=CropCycles, B26=BasePrice, B27=PriceInflation, B28=ScalingFactor
# B31=COGSPct, B32=COGSEscalation, B33=GrowerSalary, B34=WageInflation
# B35=OwnerICHRA, B36=EmpICHRA, B37=HealthInflation
# B38=MonthlyRent, B39=HVACBase, B40=ContY2, B41=ContY3, B42=ContY4, B43=ContY5, B44=OpCoAdmin
# B47=PropTaxRate, B48=PropInsurance, B49=BuildingsRM, B50=EquipRM, B51=PropUtilities, B52=PropProfFees, B53=PropInflation
# B56=SolarExportHighkWh, B57=SolarExportLowkWh, B58=NetMeteringRate
# B61=SETaxRate, B62=SEFactor, B63=IncomeTaxRate
# B68=ShedsLife, B69=TractorCost, B70=TractorLife, B71=ContainerLife, B72=SolarLife

# Short aliases
A = "Assumptions!$B$"
def a(n): return f"Assumptions!$B${n}"

# ============================================================
# TAB 2: OpCo P&L
# ============================================================
ws2 = wb.create_sheet("OpCo P&L")
ws2.sheet_view.showGridLines = True
ws2.column_dimensions["A"].width = 42
for col_ltr in ["B","C","D","E"]:
    ws2.column_dimensions[col_ltr].width = 18

ws2.merge_cells("A1:E1")
set_hdr(ws2["A1"], "OpCo PROFIT & LOSS — Years 2-5")
ws2.row_dimensions[1].height = 22

ws2["A2"].value = ""
for col, yr in enumerate(["Year 2", "Year 3", "Year 4", "Year 5"], start=2):
    c = ws2.cell(2, col)
    c.value = yr
    c.font = bold_font()
    c.alignment = Alignment(horizontal="center")

r2 = 4

# REVENUE
ws2.merge_cells(f"A{r2}:E{r2}")
set_hdr(ws2[f"A{r2}"], "REVENUE")
r2 += 1

set_label(ws2.cell(r2, 1), "Gross Lettuce Sales")
# Y2
set_formula(ws2.cell(r2, 2), f"={a(24)}*{a(25)}*{a(26)}")
# Y3
set_formula(ws2.cell(r2, 3), f"={a(24)}*{a(25)}*({a(26)}*(1+{a(27)})^1)")
# Y4
set_formula(ws2.cell(r2, 4), f"={a(24)}*{a(25)}*({a(26)}*(1+{a(27)})^2)*{a(28)}")
# Y5
set_formula(ws2.cell(r2, 5), f"={a(24)}*{a(25)}*({a(26)}*(1+{a(27)})^3)*{a(28)}")
LETTUCE_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "HEC Grid Export Credits")
# Y2,Y3: High kWh
set_formula(ws2.cell(r2, 2), f"={a(56)}*{a(58)}")
set_formula(ws2.cell(r2, 3), f"={a(56)}*{a(58)}")
# Y4,Y5: Low kWh
set_formula(ws2.cell(r2, 4), f"={a(57)}*{a(58)}")
set_formula(ws2.cell(r2, 5), f"={a(57)}*{a(58)}")
GRID_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "TOTAL REVENUE")
ws2.cell(r2, 1).font = bold_font()
for col in range(2, 6):
    set_bold_formula(ws2.cell(r2, col), f"=SUM({get_column_letter(col)}{LETTUCE_ROW}:{get_column_letter(col)}{r2-1})")
apply_double_bottom(ws2, r2, 1, 5)
TOTAL_REV_ROW = r2
r2 += 2

# OPERATING EXPENSES
ws2.merge_cells(f"A{r2}:E{r2}")
set_hdr(ws2[f"A{r2}"], "OPERATING EXPENSES")
r2 += 1

set_label(ws2.cell(r2, 1), "COGS (Cost of Goods Sold)")
set_formula(ws2.cell(r2, 2), f"=B{TOTAL_REV_ROW}*{a(31)}")
set_formula(ws2.cell(r2, 3), f"=C{TOTAL_REV_ROW}*({a(31)}+{a(32)}*1)")
set_formula(ws2.cell(r2, 4), f"=D{TOTAL_REV_ROW}*({a(31)}+{a(32)}*2)")
set_formula(ws2.cell(r2, 5), f"=E{TOTAL_REV_ROW}*({a(31)}+{a(32)}*3)")
COGS_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Assistant Grower Labor")
set_formula(ws2.cell(r2, 2), f"={a(33)}")
set_formula(ws2.cell(r2, 3), f"={a(33)}*(1+{a(34)})^1")
set_formula(ws2.cell(r2, 4), f"={a(33)}*(1+{a(34)})^2")
set_formula(ws2.cell(r2, 5), f"={a(33)}*(1+{a(34)})^3")
LABOR_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Total ICHRA Health Insurance")
set_formula(ws2.cell(r2, 2), f"={a(35)}+{a(36)}")
set_formula(ws2.cell(r2, 3), f"=B{r2}*(1+{a(37)})^1")
set_formula(ws2.cell(r2, 4), f"=B{r2}*(1+{a(37)})^2")
set_formula(ws2.cell(r2, 5), f"=B{r2}*(1+{a(37)})^3")
ICHRA_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Intercompany Rent to PropCo")
for col in range(2, 6):
    set_formula(ws2.cell(r2, col), f"={a(38)}*12")
RENT_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "HVAC & CO2")
set_formula(ws2.cell(r2, 2), f"={a(39)}*{a(40)}")
set_formula(ws2.cell(r2, 3), f"={a(39)}*{a(41)}")
set_formula(ws2.cell(r2, 4), f"={a(39)}*{a(42)}")
set_formula(ws2.cell(r2, 5), f"={a(39)}*{a(43)}")
HVAC_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Insurance, Legal & Admin")
for col in range(2, 6):
    set_formula(ws2.cell(r2, col), f"={a(44)}")
ADMIN_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "TOTAL OPERATING EXPENSES")
ws2.cell(r2, 1).font = bold_font()
for col in range(2, 6):
    set_bold_formula(ws2.cell(r2, col), f"=SUM({get_column_letter(col)}{COGS_ROW}:{get_column_letter(col)}{r2-1})")
apply_double_bottom(ws2, r2, 1, 5)
TOTAL_EXP_ROW = r2
r2 += 2

# NET OPERATING
ws2.merge_cells(f"A{r2}:E{r2}")
set_hdr(ws2[f"A{r2}"], "NET OPERATING INCOME & TAX")
r2 += 1

set_label(ws2.cell(r2, 1), "EBIT (Operating Income)")
ws2.cell(r2, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws2.cell(r2, col), f"={c}{TOTAL_REV_ROW}-{c}{TOTAL_EXP_ROW}")
EBIT_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Self-Employment Tax")
for col in range(2, 6):
    c = get_column_letter(col)
    set_formula(ws2.cell(r2, col), f"=IF({c}{EBIT_ROW}>0,{c}{EBIT_ROW}*{a(62)}*{a(61)},0)")
SE_TAX_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Income Tax (Pass-Through)")
for col in range(2, 6):
    c = get_column_letter(col)
    set_formula(ws2.cell(r2, col), f"=IF({c}{EBIT_ROW}>0,MAX(0,({c}{EBIT_ROW}-{c}{SE_TAX_ROW})*{a(63)}),0)")
INC_TAX_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "TOTAL TAX LIABILITY")
ws2.cell(r2, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws2.cell(r2, col), f"={c}{SE_TAX_ROW}+{c}{INC_TAX_ROW}")
apply_double_bottom(ws2, r2, 1, 5)
TOTAL_TAX_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "NET POST-TAX CASH FLOW")
ws2.cell(r2, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws2.cell(r2, col), f"={c}{EBIT_ROW}-{c}{TOTAL_TAX_ROW}")
apply_double_bottom(ws2, r2, 1, 5)
OPCO_NPTCF_ROW = r2
r2 += 1

set_label(ws2.cell(r2, 1), "Net Profit Margin %")
for col in range(2, 6):
    c = get_column_letter(col)
    set_formula(ws2.cell(r2, col), f"=IF({c}{TOTAL_REV_ROW}<>0,{c}{OPCO_NPTCF_ROW}/{c}{TOTAL_REV_ROW},0)", FMT_PCT)

# ============================================================
# TAB 3: PropCo P&L & BS
# ============================================================
ws3 = wb.create_sheet("PropCo P&L & BS")
ws3.sheet_view.showGridLines = True
ws3.column_dimensions["A"].width = 42
for col_ltr in ["B","C","D","E","F"]:
    ws3.column_dimensions[col_ltr].width = 16

ws3.merge_cells("A1:F1")
set_hdr(ws3["A1"], "PropCo PROFIT & LOSS & BALANCE SHEET")
ws3.row_dimensions[1].height = 22

ws3["A2"].value = ""
for col, lbl in enumerate(["Day 1", "Year 2", "Year 3", "Year 4", "Year 5"], start=2):
    c = ws3.cell(2, col)
    c.value = lbl
    c.font = bold_font()
    c.alignment = Alignment(horizontal="center")

r3 = 4

# SECTION A: PropCo P&L
ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "SECTION A: PropCo P&L (Years 2-5)")
r3 += 1

ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "REVENUE")
r3 += 1

set_label(ws3.cell(r3, 1), "Intercompany Rental Income")
ws3.cell(r3, 2).value = ""
for col, ocol in enumerate(["B","C","D","E"], start=3):
    set_link(ws3.cell(r3, col), f"='OpCo P&L'!{ocol}{RENT_ROW}")
RENTAL_INC_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL REVENUE")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_bold_formula(ws3.cell(r3, col), f"={get_column_letter(col)}{RENTAL_INC_ROW}")
apply_double_bottom(ws3, r3, 1, 6)
P3_TOTAL_REV_ROW = r3
r3 += 2

ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "OPERATING EXPENSES")
r3 += 1

# Property Taxes: (LandCost+ShedCost+ContainerCost+SolarCost)*PropTaxRate*(1+PropInflation)^n
# B4=LandCost, B5=ShedCost, B6=ContainerCost, B7=SolarCost, B47=PropTaxRate, B53=PropInflation
set_label(ws3.cell(r3, 1), "Property Taxes")
ws3.cell(r3, 2).value = ""
for n, col in enumerate(range(3, 7)):
    set_formula(ws3.cell(r3, col), f"=({a(4)}+{a(5)}+{a(6)}+{a(7)})*{a(47)}*(1+{a(53)})^{n}")
PROP_TAX_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Property Liability Insurance")
ws3.cell(r3, 2).value = ""
for n, col in enumerate(range(3, 7)):
    set_formula(ws3.cell(r3, col), f"={a(48)}*(1+{a(53)})^{n}")
PROP_INS_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Buildings & Land R&M")
ws3.cell(r3, 2).value = ""
for n, col in enumerate(range(3, 7)):
    set_formula(ws3.cell(r3, col), f"={a(49)}*(1+{a(53)})^{n}")
BLDG_RM_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Equipment R&M")
ws3.cell(r3, 2).value = ""
for n, col in enumerate(range(3, 7)):
    set_formula(ws3.cell(r3, col), f"={a(50)}*(1+{a(53)})^{n}")
EQUIP_RM_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Utilities")
ws3.cell(r3, 2).value = ""
for n, col in enumerate(range(3, 7)):
    set_formula(ws3.cell(r3, col), f"={a(51)}*(1+{a(53)})^{n}")
UTIL_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Professional Fees")
ws3.cell(r3, 2).value = ""
for n, col in enumerate(range(3, 7)):
    set_formula(ws3.cell(r3, col), f"={a(52)}*(1+{a(53)})^{n}")
PROF_FEES_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL PROPCO OPEX")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_bold_formula(ws3.cell(r3, col), f"=SUM({get_column_letter(col)}{PROP_TAX_ROW}:{get_column_letter(col)}{r3-1})")
apply_double_bottom(ws3, r3, 1, 6)
TOTAL_PROPCO_OPEX_ROW = r3
r3 += 2

ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "EARNINGS")
r3 += 1

set_label(ws3.cell(r3, 1), "PROPCO EBITDA")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{P3_TOTAL_REV_ROW}-{c}{TOTAL_PROPCO_OPEX_ROW}")
PROPCO_EBITDA_ROW = r3
r3 += 1

# Depreciation
set_label(ws3.cell(r3, 1), "Depreciation - Sheds")
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_formula(ws3.cell(r3, col), f"={a(5)}/{a(68)}")
DEPR_SHEDS_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Depreciation - Tractor")
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_formula(ws3.cell(r3, col), f"={a(69)}/{a(70)}")
DEPR_TRACTOR_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Depreciation - Container Hulls")
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_formula(ws3.cell(r3, col), f"={a(6)}/{a(71)}")
DEPR_CONTAINER_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Depreciation - Solar Grid")
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_formula(ws3.cell(r3, col), f"={a(7)}/{a(72)}")
DEPR_SOLAR_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL DEPRECIATION")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    set_bold_formula(ws3.cell(r3, col), f"=SUM({get_column_letter(col)}{DEPR_SHEDS_ROW}:{get_column_letter(col)}{r3-1})")
apply_double_bottom(ws3, r3, 1, 6)
TOTAL_DEPR_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "PROPCO EBIT")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{PROPCO_EBITDA_ROW}-{c}{TOTAL_DEPR_ROW}")
PROPCO_EBIT_ROW = r3
r3 += 2

ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "INTEREST EXPENSE")
r3 += 1

# FSA Ownership: principal = B4*B13, rate=B14, term=B15
# Note: periods for Y2=(1-12), Y3=(13-24), Y4=(25-36), Y5=(37-48)
set_label(ws3.cell(r3, 1), "FSA Farm Ownership Loan Interest")
ws3.cell(r3, 2).value = ""
periods = [(1,12),(13,24),(25,36),(37,48)]
for col, (start,end) in zip(range(3,7), periods):
    set_formula(ws3.cell(r3, col),
        f"=-CUMIPMT({a(14)}/12,{a(15)}*12,{a(4)}*{a(13)},{start},{end},0)")
OWNERSHIP_INT_ROW = r3
r3 += 1

# Infrastructure: principal=B19, rate=B20, term=B21
set_label(ws3.cell(r3, 1), "Infrastructure Loan Interest")
ws3.cell(r3, 2).value = ""
for col, (start,end) in zip(range(3,7), periods):
    set_formula(ws3.cell(r3, col),
        f"=-CUMIPMT({a(20)}/12,{a(21)}*12,{a(19)},{start},{end},0)")
INFRA_INT_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL INTEREST EXPENSE")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{OWNERSHIP_INT_ROW}+{c}{INFRA_INT_ROW}")
apply_double_bottom(ws3, r3, 1, 6)
TOTAL_INT_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "PROPCO NET INCOME (EBT)")
ws3.cell(r3, 1).font = bold_font()
ws3.cell(r3, 2).value = ""
for col in range(3, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{PROPCO_EBIT_ROW}-{c}{TOTAL_INT_ROW}")
apply_double_bottom(ws3, r3, 1, 6)
PROPCO_NET_INC_ROW = r3
r3 += 3

# SECTION B: Balance Sheet
ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "SECTION B: PropCo BALANCE SHEET")
r3 += 1

ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "ASSETS")
r3 += 1

set_label(ws3.cell(r3, 1), "Cash")
set_formula(ws3.cell(r3, 2), "=0")
# Will fill Y2-Y5 after Tab 4 is built (placeholders as 0 for now)
BS_CASH_ROW = r3
r3 += 1

ws3[f"A{r3}"].value = "Fixed Assets at Cost:"
ws3[f"A{r3}"].font = section_font()
ws3.merge_cells(f"A{r3}:F{r3}")
r3 += 1

set_label(ws3.cell(r3, 1), "  Land")
for col in range(2, 7):
    set_formula(ws3.cell(r3, col), f"={a(4)}")
LAND_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "  Sheds")
for col in range(2, 7):
    set_formula(ws3.cell(r3, col), f"={a(5)}")
SHEDS_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "  Tractor")
for col in range(2, 7):
    set_formula(ws3.cell(r3, col), f"={a(69)}")
TRACTOR_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "  Container Hulls")
for col in range(2, 7):
    set_formula(ws3.cell(r3, col), f"={a(6)}")
CONTAINERS_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "  Solar System")
for col in range(2, 7):
    set_formula(ws3.cell(r3, col), f"={a(7)}")
SOLAR_ROW_BS = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Total Fixed Assets at Cost")
ws3.cell(r3, 1).font = bold_font()
for col in range(2, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"=SUM({c}{LAND_ROW}:{c}{r3-1})")
TOTAL_FA_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Less: Accumulated Depreciation")
set_formula(ws3.cell(r3, 2), "=0")
set_formula(ws3.cell(r3, 3), f"=C{TOTAL_DEPR_ROW}")
set_formula(ws3.cell(r3, 4), f"=C{TOTAL_DEPR_ROW}+D{TOTAL_DEPR_ROW}")
set_formula(ws3.cell(r3, 5), f"=C{TOTAL_DEPR_ROW}+D{TOTAL_DEPR_ROW}+E{TOTAL_DEPR_ROW}")
set_formula(ws3.cell(r3, 6), f"=C{TOTAL_DEPR_ROW}+D{TOTAL_DEPR_ROW}+E{TOTAL_DEPR_ROW}+F{TOTAL_DEPR_ROW}")
ACCUM_DEPR_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Net Fixed Assets")
ws3.cell(r3, 1).font = bold_font()
for col in range(2, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{TOTAL_FA_ROW}-{c}{ACCUM_DEPR_ROW}")
NET_FA_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL ASSETS")
ws3.cell(r3, 1).font = bold_font()
for col in range(2, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{BS_CASH_ROW}+{c}{NET_FA_ROW}")
apply_double_bottom(ws3, r3, 1, 6)
TOTAL_ASSETS_ROW = r3
r3 += 2

ws3.merge_cells(f"A{r3}:F{r3}")
set_hdr(ws3[f"A{r3}"], "LIABILITIES & EQUITY")
r3 += 1

# FSA Ownership Loan Balance
# Day 1: B4*B13
# Year N: principal + CUMPRINC(rate/12, term*12, principal, 1, N*12, 0)
set_label(ws3.cell(r3, 1), "FSA Ownership Loan Balance")
set_formula(ws3.cell(r3, 2), f"={a(4)}*{a(13)}")
cumprinc_own = lambda n: f"={a(4)}*{a(13)}+CUMPRINC({a(14)}/12,{a(15)}*12,{a(4)}*{a(13)},1,{n*12},0)"
set_formula(ws3.cell(r3, 3), cumprinc_own(1))
set_formula(ws3.cell(r3, 4), cumprinc_own(2))
set_formula(ws3.cell(r3, 5), cumprinc_own(3))
set_formula(ws3.cell(r3, 6), cumprinc_own(4))
OWNERSHIP_LOAN_ROW = r3
r3 += 1

# Infrastructure Loan Balance
set_label(ws3.cell(r3, 1), "Infrastructure Loan Balance")
set_formula(ws3.cell(r3, 2), f"={a(19)}")
cumprinc_infra = lambda n: f"={a(19)}+CUMPRINC({a(20)}/12,{a(21)}*12,{a(19)},1,{n*12},0)"
set_formula(ws3.cell(r3, 3), cumprinc_infra(1))
set_formula(ws3.cell(r3, 4), cumprinc_infra(2))
set_formula(ws3.cell(r3, 5), cumprinc_infra(3))
set_formula(ws3.cell(r3, 6), cumprinc_infra(4))
INFRA_LOAN_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL LIABILITIES")
ws3.cell(r3, 1).font = bold_font()
for col in range(2, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{OWNERSHIP_LOAN_ROW}+{c}{INFRA_LOAN_ROW}")
TOTAL_LIAB_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "Owner's Capital")
# Day 1: Total Assets - Total Liabilities
set_formula(ws3.cell(r3, 2), f"=B{TOTAL_ASSETS_ROW}-B{TOTAL_LIAB_ROW}")
# Year N: Day1 + cumulative PropCo Net Income
set_formula(ws3.cell(r3, 3), f"=B{r3}+C{PROPCO_NET_INC_ROW}")
set_formula(ws3.cell(r3, 4), f"=B{r3}+C{PROPCO_NET_INC_ROW}+D{PROPCO_NET_INC_ROW}")
set_formula(ws3.cell(r3, 5), f"=B{r3}+C{PROPCO_NET_INC_ROW}+D{PROPCO_NET_INC_ROW}+E{PROPCO_NET_INC_ROW}")
set_formula(ws3.cell(r3, 6), f"=B{r3}+C{PROPCO_NET_INC_ROW}+D{PROPCO_NET_INC_ROW}+E{PROPCO_NET_INC_ROW}+F{PROPCO_NET_INC_ROW}")
OWNERS_CAP_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "TOTAL LIABILITIES & EQUITY")
ws3.cell(r3, 1).font = bold_font()
for col in range(2, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{TOTAL_LIAB_ROW}+{c}{OWNERS_CAP_ROW}")
apply_double_bottom(ws3, r3, 1, 6)
TOTAL_LE_ROW = r3
r3 += 1

set_label(ws3.cell(r3, 1), "BALANCE CHECK (should = 0)")
ws3.cell(r3, 1).font = bold_font()
for col in range(2, 7):
    c = get_column_letter(col)
    set_bold_formula(ws3.cell(r3, col), f"={c}{TOTAL_ASSETS_ROW}-{c}{TOTAL_LE_ROW}")
BS_CHECK_ROW = r3

# ============================================================
# TAB 4: Cash Flow
# ============================================================
ws4 = wb.create_sheet("Cash Flow")
ws4.sheet_view.showGridLines = True
ws4.column_dimensions["A"].width = 48
for col_ltr in ["B","C","D","E"]:
    ws4.column_dimensions[col_ltr].width = 18

ws4.merge_cells("A1:E1")
set_hdr(ws4["A1"], "CASH FLOW STATEMENT — Years 2-5")
ws4.row_dimensions[1].height = 22

ws4["A2"].value = ""
for col, yr in enumerate(["Year 2", "Year 3", "Year 4", "Year 5"], start=2):
    c = ws4.cell(2, col)
    c.value = yr
    c.font = bold_font()
    c.alignment = Alignment(horizontal="center")

r4 = 4

ws4.merge_cells(f"A{r4}:E{r4}")
set_hdr(ws4[f"A{r4}"], "SECTION 1: OpCo CASH FLOW")
r4 += 1

set_label(ws4.cell(r4, 1), "Net Post-Tax Cash Flow (OpCo)")
for col, ocol in enumerate(["B","C","D","E"], start=2):
    set_link(ws4.cell(r4, col), f"='OpCo P&L'!{ocol}{OPCO_NPTCF_ROW}")
OPCO_CF_ROW = r4
r4 += 1

# FSA Microloan: rate=B17, term=B18, principal=B16
set_label(ws4.cell(r4, 1), "Less: FSA Microloan Principal Paid")
for col, (start, end) in zip(range(2, 6), periods):
    set_formula(ws4.cell(r4, col),
        f"=-CUMPRINC({a(17)}/12,{a(18)}*12,{a(16)},{start},{end},0)")
MICRO_PRINC_ROW = r4
r4 += 1

set_label(ws4.cell(r4, 1), "NET OPCO REINVESTMENT CASH")
ws4.cell(r4, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws4.cell(r4, col), f"={c}{OPCO_CF_ROW}-{c}{MICRO_PRINC_ROW}")
apply_double_bottom(ws4, r4, 1, 5)
OPCO_NET_CF_ROW = r4
r4 += 3

ws4.merge_cells(f"A{r4}:E{r4}")
set_hdr(ws4[f"A{r4}"], "SECTION 2: PropCo CASH FLOW")
r4 += 1

set_label(ws4.cell(r4, 1), "PropCo Net Income (EBT)")
for col, pcol in enumerate(["C","D","E","F"], start=2):
    set_link(ws4.cell(r4, col), f"='PropCo P&L & BS'!{pcol}{PROPCO_NET_INC_ROW}")
PROPCO_CF_NI_ROW = r4
r4 += 1

set_label(ws4.cell(r4, 1), "Add Back: Total Non-Cash Depreciation")
for col, pcol in enumerate(["C","D","E","F"], start=2):
    set_link(ws4.cell(r4, col), f"='PropCo P&L & BS'!{pcol}{TOTAL_DEPR_ROW}")
PROPCO_CF_DEPR_ROW = r4
r4 += 1

# FSA Ownership Principal: rate=B14, term=B15, principal=B4*B13
set_label(ws4.cell(r4, 1), "Less: FSA Ownership Loan Principal Paid")
for col, (start, end) in zip(range(2, 6), periods):
    set_formula(ws4.cell(r4, col),
        f"=-CUMPRINC({a(14)}/12,{a(15)}*12,{a(4)}*{a(13)},{start},{end},0)")
OWNERSHIP_PRINC_ROW = r4
r4 += 1

# Infrastructure Principal: rate=B20, term=B21, principal=B19
set_label(ws4.cell(r4, 1), "Less: Infrastructure Loan Principal Paid")
for col, (start, end) in zip(range(2, 6), periods):
    set_formula(ws4.cell(r4, col),
        f"=-CUMPRINC({a(20)}/12,{a(21)}*12,{a(19)},{start},{end},0)")
INFRA_PRINC_ROW = r4
r4 += 1

set_label(ws4.cell(r4, 1), "TRUE PROPCO NET RETAINED CASH")
ws4.cell(r4, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws4.cell(r4, col),
        f"={c}{PROPCO_CF_NI_ROW}+{c}{PROPCO_CF_DEPR_ROW}-{c}{OWNERSHIP_PRINC_ROW}-{c}{INFRA_PRINC_ROW}")
apply_double_bottom(ws4, r4, 1, 5)
PROPCO_NET_RETAINED_ROW = r4
r4 += 3

ws4.merge_cells(f"A{r4}:E{r4}")
set_hdr(ws4[f"A{r4}"], "DEBT SERVICE COVERAGE RATIO (DSCR)")
r4 += 1

set_label(ws4.cell(r4, 1), "EBITDA (PropCo)")
for col, pcol in enumerate(["C","D","E","F"], start=2):
    set_link(ws4.cell(r4, col), f"='PropCo P&L & BS'!{pcol}{PROPCO_EBITDA_ROW}")
DSCR_EBITDA_ROW = r4
r4 += 1

set_label(ws4.cell(r4, 1), "Total Annual Debt Service (Principal + Interest)")
for col, pcol in enumerate(["C","D","E","F"], start=2):
    c = get_column_letter(col)
    set_formula(ws4.cell(r4, col),
        f"={c}{OWNERSHIP_PRINC_ROW}+{c}{INFRA_PRINC_ROW}+'PropCo P&L & BS'!{pcol}{OWNERSHIP_INT_ROW}+'PropCo P&L & BS'!{pcol}{INFRA_INT_ROW}")
DSCR_DS_ROW = r4
r4 += 1

set_label(ws4.cell(r4, 1), "DSCR")
ws4.cell(r4, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws4.cell(r4, col),
        f"=IF({c}{DSCR_DS_ROW}<>0,{c}{DSCR_EBITDA_ROW}/{c}{DSCR_DS_ROW},0)", FMT_MULT)
apply_double_bottom(ws4, r4, 1, 5)
DSCR_ROW = r4

# Now go back and fill Tab 3 BS Cash row with Tab 4 links
set_link(ws3.cell(BS_CASH_ROW, 3), f"='Cash Flow'!B{PROPCO_NET_RETAINED_ROW}")
set_link(ws3.cell(BS_CASH_ROW, 4), f"='Cash Flow'!B{PROPCO_NET_RETAINED_ROW}+'Cash Flow'!C{PROPCO_NET_RETAINED_ROW}")
set_link(ws3.cell(BS_CASH_ROW, 5), f"='Cash Flow'!B{PROPCO_NET_RETAINED_ROW}+'Cash Flow'!C{PROPCO_NET_RETAINED_ROW}+'Cash Flow'!D{PROPCO_NET_RETAINED_ROW}")
set_link(ws3.cell(BS_CASH_ROW, 6), f"='Cash Flow'!B{PROPCO_NET_RETAINED_ROW}+'Cash Flow'!C{PROPCO_NET_RETAINED_ROW}+'Cash Flow'!D{PROPCO_NET_RETAINED_ROW}+'Cash Flow'!E{PROPCO_NET_RETAINED_ROW}")

# ============================================================
# TAB 5: Combined CF Matrix
# ============================================================
ws5 = wb.create_sheet("Combined CF Matrix")
ws5.sheet_view.showGridLines = True
ws5.column_dimensions["A"].width = 48
for col_ltr in ["B","C","D","E"]:
    ws5.column_dimensions[col_ltr].width = 18

ws5.merge_cells("A1:E1")
set_hdr(ws5["A1"], "COMBINED CASH FLOW MATRIX — Years 2-5")
ws5.row_dimensions[1].height = 22

ws5["A2"].value = ""
for col, yr in enumerate(["Year 2", "Year 3", "Year 4", "Year 5"], start=2):
    c = ws5.cell(2, col)
    c.value = yr
    c.font = bold_font()
    c.alignment = Alignment(horizontal="center")

r5 = 4

ws5.merge_cells(f"A{r5}:E{r5}")
set_hdr(ws5[f"A{r5}"], "COMBINED ENTERPRISE INFLOWS")
r5 += 1

set_label(ws5.cell(r5, 1), "OpCo Post-Tax Cash")
for col, cf_col in enumerate(["B","C","D","E"], start=2):
    set_link(ws5.cell(r5, col), f"='Cash Flow'!{cf_col}{OPCO_NET_CF_ROW}")
OPCO_INFLOW_ROW = r5
r5 += 1

set_label(ws5.cell(r5, 1), "PropCo Net Retained Cash")
for col, cf_col in enumerate(["B","C","D","E"], start=2):
    set_link(ws5.cell(r5, col), f"='Cash Flow'!{cf_col}{PROPCO_NET_RETAINED_ROW}")
PROPCO_INFLOW_ROW = r5
r5 += 1

set_label(ws5.cell(r5, 1), "GLOBAL CASH INFLOWS")
ws5.cell(r5, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws5.cell(r5, col), f"={c}{OPCO_INFLOW_ROW}+{c}{PROPCO_INFLOW_ROW}")
apply_double_bottom(ws5, r5, 1, 5)
GLOBAL_INFLOWS_ROW = r5
r5 += 3

ws5.merge_cells(f"A{r5}:E{r5}")
set_hdr(ws5[f"A{r5}"], "COMBINED DEBT AMORTIZATION OUTFLOWS")
r5 += 1

set_label(ws5.cell(r5, 1), "FSA Microloan Principal (OpCo)")
for col, cf_col in enumerate(["B","C","D","E"], start=2):
    set_link(ws5.cell(r5, col), f"='Cash Flow'!{cf_col}{MICRO_PRINC_ROW}")
MICRO_OUT_ROW = r5
r5 += 1

set_label(ws5.cell(r5, 1), "FSA Ownership Principal (PropCo)")
for col, cf_col in enumerate(["B","C","D","E"], start=2):
    set_link(ws5.cell(r5, col), f"='Cash Flow'!{cf_col}{OWNERSHIP_PRINC_ROW}")
OWNERSHIP_OUT_ROW = r5
r5 += 1

set_label(ws5.cell(r5, 1), "FSA Infrastructure Principal (PropCo)")
for col, cf_col in enumerate(["B","C","D","E"], start=2):
    set_link(ws5.cell(r5, col), f"='Cash Flow'!{cf_col}{INFRA_PRINC_ROW}")
INFRA_OUT_ROW = r5
r5 += 1

set_label(ws5.cell(r5, 1), "GLOBAL PRINCIPAL DEBT SERVICE")
ws5.cell(r5, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws5.cell(r5, col), f"={c}{MICRO_OUT_ROW}+{c}{OWNERSHIP_OUT_ROW}+{c}{INFRA_OUT_ROW}")
apply_double_bottom(ws5, r5, 1, 5)
GLOBAL_DEBT_SVC_ROW = r5
r5 += 3

set_label(ws5.cell(r5, 1), "MASTER NET CASH RESERVE")
ws5.cell(r5, 1).font = bold_font()
for col in range(2, 6):
    c = get_column_letter(col)
    set_bold_formula(ws5.cell(r5, col), f"={c}{GLOBAL_INFLOWS_ROW}-{c}{GLOBAL_DEBT_SVC_ROW}")
apply_double_bottom(ws5, r5, 1, 5)
MASTER_NET_ROW = r5
r5 += 2

set_label(ws5.cell(r5, 1), "CUMULATIVE FARM RETAINED RESERVES")
ws5.cell(r5, 1).font = bold_font()
set_bold_formula(ws5.cell(r5, 2), f"=B{MASTER_NET_ROW}")
set_bold_formula(ws5.cell(r5, 3), f"=B{r5}+C{MASTER_NET_ROW}")
set_bold_formula(ws5.cell(r5, 4), f"=B{r5}+C{MASTER_NET_ROW}+D{MASTER_NET_ROW}")
set_bold_formula(ws5.cell(r5, 5), f"=B{r5}+C{MASTER_NET_ROW}+D{MASTER_NET_ROW}+E{MASTER_NET_ROW}")
apply_double_bottom(ws5, r5, 1, 5)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
wb.save(OUT)
print(f"Saved: {OUT}")
print("\nKey row numbers for verification:")
print(f"Tab2 TOTAL_REV_ROW={TOTAL_REV_ROW}, OPCO_NPTCF_ROW={OPCO_NPTCF_ROW}")
print(f"Tab3 PROPCO_NET_INC_ROW={PROPCO_NET_INC_ROW}, TOTAL_DEPR_ROW={TOTAL_DEPR_ROW}")
print(f"Tab3 OWNERSHIP_INT_ROW={OWNERSHIP_INT_ROW}, INFRA_INT_ROW={INFRA_INT_ROW}")
print(f"Tab3 PROPCO_EBITDA_ROW={PROPCO_EBITDA_ROW}, TOTAL_ASSETS_ROW={TOTAL_ASSETS_ROW}")
print(f"Tab4 OPCO_NET_CF_ROW={OPCO_NET_CF_ROW}, PROPCO_NET_RETAINED_ROW={PROPCO_NET_RETAINED_ROW}")
print(f"Tab4 MICRO_PRINC_ROW={MICRO_PRINC_ROW}, OWNERSHIP_PRINC_ROW={OWNERSHIP_PRINC_ROW}")
print(f"Tab4 INFRA_PRINC_ROW={INFRA_PRINC_ROW}, DSCR_ROW={DSCR_ROW}")
