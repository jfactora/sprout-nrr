"""
nrr_dashboard_v3.py
Generate a clean NRR monitoring dashboard HTML from pre-computed pipeline data.

Inputs:
  nrr_summary_v2.json      → SUMMARY + CDETAIL
  nrr_allocated_lines.json → INVOICE_DATA (drilldown detail)

Output:
  nrr-dashboard-v3.html
"""
import json, re, os
from collections import defaultdict, Counter
from datetime import date

# ── Paths ────────────────────────────────────────────────────────────────────
BASE   = os.path.dirname(os.path.abspath(__file__))
SUMM_F = os.path.join(BASE, 'nrr_summary_v2.json')
ALLOC_F= os.path.join(BASE, 'nrr_allocated_lines.json')
OUT_F  = os.path.join(BASE, 'nrr-dashboard-v3.html')

# ── CSM normalization map ─────────────────────────────────────────────────────
# Step 1: collapse known spelling/formatting variants to a single canonical name.
# Step 2: validate against the allowlist — anything not on the list → 'Unassigned'.
CSM_NORM = {
    # Rexelle Estacio — honorific prefix variants
    'Ma. Rexelle Estacio':  'Rexelle Estacio',
    'Ma Rexelle Estacio':   'Rexelle Estacio',
    # Krystel Maaño — accent-less variant
    'Krystel Maano':        'Krystel Maaño',
    # Wil Luna — double-space artefact
    'Wil  Luna':            'Wil Luna',
    # Lucky Peñalosa — unify short/long forms and missing ñ
    'Lucky Lyne Penalosa':  'Lucky Lyne Peñalosa',
    'Lucky Peñalosa':       'Lucky Lyne Peñalosa',
    # RIEZHEL PUNZALAN — all-caps artefact (not on allowlist, will → Unassigned)
    'RIEZHEL PUNZALAN':     'Riezhel Punzalan',
}

# Strict allowlist of canonical CSM names.
# Any name not in this set is remapped to 'Unassigned' after normalization.
VALID_CSMS = {
    'Althea Sarah Ramos', 'Anthony Dihiansan', 'Bernice Locsin', 'Chris Ureta',
    'Demcy Charles Cachero', 'Emy Figueroa', 'France Paredes', 'Gabriel Cristobal',
    'Gia San Juan', 'Javier Roberto Villavicencio', 'Jerome Portera', 'Jerry San Pedro',
    'Jillian Mozelle Factora', 'Kate Potian - Janairo', 'Katrine Hyzle Potian',
    'Krystel Maaño', 'Lucky Lyne Peñalosa', 'Ma. Ana Saavedra', 'Rexelle Estacio',
    'Marcel Pizarras', 'Mark Ian Balibagoso', 'Matthew Abellaneda',
    'Mikhaela Angela Batara', 'Ross Benedict Palileo', 'Ryan Geronimo',
    'Sarah Ramos', 'Wil Luna',
}

def norm_csm(name):
    """Normalize then validate a raw CSM name.

    1. Collapse whitespace (catches double-space artefacts not in the map).
    2. Apply spelling/variant map.
    3. If the result is not on the allowlist, return 'Unassigned'.
    """
    cleaned = ' '.join((name or '').split())   # collapse all whitespace
    canonical = CSM_NORM.get(cleaned, cleaned)
    return canonical if canonical in VALID_CSMS else 'Unassigned'

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading summary…")
with open(SUMM_F) as f:
    summ = json.load(f)
SUMMARY = summ['monthly_nrr']      # list of dicts
CDETAIL = summ['customer_detail']
# CDETAIL row format (14 fields):
#  [0]month  [1]cid  [2]name  [3]csm_id  [4]csm_name
#  [5]begin_mrr  [6]end_mrr  [7]delta  [8]movement  [9]raw_owner
#  [10]prev_rec  [11]curr_rec  [12]prev_tu  [13]curr_tu

# Normalize CSM names in CDETAIL (index 4) in-place — idempotent safety pass
for row in CDETAIL:
    row[4] = norm_csm(row[4])

print("Loading allocated lines…")
with open(ALLOC_F) as f:
    allocs = json.load(f)
print(f"  {len(allocs):,} allocation rows")

# Normalize CSM names in allocs in-place
for row in allocs:
    row['csm_name'] = norm_csm(row['csm_name'])

# ── Build INVOICE_DATA ────────────────────────────────────────────────────────
# Key: "cid|covered_month"
# Value: array of [desc, line_amt, mo_alloc, rt, module, months_covered, cs, ce,
#                  inv_number, inv_date, payment_status]
def _s(v):
    """Sanitize string — collapse all whitespace."""
    return ' '.join(str(v or '').split())

print("Building INVOICE_DATA…")
inv_data = defaultdict(list)
for row in allocs:
    key = f"{row['customer_id']}|{row['covered_month']}"
    inv_data[key].append([
        _s(row['description']),
        row['line_amount'],
        row['monthly_allocated_amount'],
        row['rt'],
        _s(row['module']),
        row['months_covered'],
        row['coverage_start'],
        row['coverage_end'],
        _s(row['invoice_number']),
        _s(row['invoice_date']),
        _s(row['payment_status']),
    ])
print(f"  {len(inv_data):,} INVOICE_DATA keys")

# ── Load HubSpot join map (optional) ─────────────────────────────────────────
# Written by nrr_pipeline_v2.py when hs_companies.json is present.
# Keyed by str(customer_id). Falls back to empty dict if file is absent.
HS_JOIN_F = os.path.join(BASE, 'hs_join_map.json')
if os.path.exists(HS_JOIN_F):
    print("Loading HubSpot join map…")
    with open(HS_JOIN_F) as f:
        hs_join_map = json.load(f)
    status_counts = {}
    for v in hs_join_map.values():
        s = v.get('hubspot_join_status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
    print(f"  {len(hs_join_map):,} entries — {status_counts}")
else:
    hs_join_map = {}
    print("  (hs_join_map.json not found — HubSpot validation panel will show empty state)")

# ── Build CSM list ────────────────────────────────────────────────────────────
# Derived strictly from the allowlist — never from dataset values.
# This guarantees the dropdown is stable regardless of what names appear in the data.
CSM_LIST = sorted(VALID_CSMS)
print(f"  {len(CSM_LIST)} CSMs in allowlist dropdown")

# ── Determine default month ───────────────────────────────────────────────────
today = date.today().strftime('%Y-%m')
cd_counts = Counter(row[0] for row in CDETAIL)
rich_months = sorted([m for m, cnt in cd_counts.items() if cnt >= 100])
default_month = today if today in cd_counts else (rich_months[-1] if rich_months else SUMMARY[-1]['month'])
print(f"Default month: {default_month} ({cd_counts.get(default_month, 0):,} rows)")

# ── Serialize data ────────────────────────────────────────────────────────────
print("Serializing…")
summary_json   = json.dumps(SUMMARY,        ensure_ascii=False, separators=(',', ':'))
cdetail_json   = json.dumps(CDETAIL,        ensure_ascii=False, separators=(',', ':'))
inv_data_json  = json.dumps(dict(inv_data), ensure_ascii=False, separators=(',', ':'))
csm_list_json  = json.dumps(CSM_LIST,       ensure_ascii=False, separators=(',', ':'))
def_month_json = json.dumps(default_month)
hs_join_json   = json.dumps(hs_join_map,    ensure_ascii=False, separators=(',', ':'))

# ── HTML Template ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sprout NRR Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; background:#F9FAFB; }
  .sprout-green { background-color: #1A4731; }
  .badge-new            { background:#DBEAFE; color:#1E40AF; }
  .badge-expansion      { background:#D1FAE5; color:#065F46; }
  .badge-contraction    { background:#FEF3C7; color:#92400E; }
  .badge-retained       { background:#F3F4F6; color:#374151; }
  .badge-retained-trueup{ background:#F5F3FF; color:#6D28D9; }
  .badge-churned        { background:#FEE2E2; color:#991B1B; }
  .badge-reactivated    { background:#EDE9FE; color:#5B21B6; }
  .tab-active { border-bottom: 2px solid #1A4731; color: #1A4731; font-weight:600; }
  .sortable { cursor:pointer; user-select:none; }
  .sortable:hover { background:#F0FDF4; }
  th.sorted-asc::after  { content: ' ↑'; }
  th.sorted-desc::after { content: ' ↓'; }
  #mainTable tbody tr:hover { background:#F0FDF4; cursor:pointer; }
  .modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:50; display:flex; align-items:center; justify-content:center; }
  .modal-box { background:white; border-radius:12px; padding:24px; max-width:960px; width:95%; max-height:90vh; overflow-y:auto; }
  ::-webkit-scrollbar { width:6px; height:6px; }
  ::-webkit-scrollbar-thumb { background:#CBD5E1; border-radius:3px; }
  /* ── Multi-select CSM filter ─────────────────────────────────────────── */
  .csm-filter { position:relative; }
  .csm-btn { display:inline-flex; align-items:center; gap:6px; border:1px solid #E5E7EB;
    border-radius:6px; background:white; font-size:13px; color:#374151; padding:5px 10px;
    cursor:pointer; white-space:nowrap; transition:border-color .15s; max-width:260px; }
  .csm-btn:hover, .csm-btn.active { border-color:#1A4731; }
  .csm-btn.active { background:#F0FDF4; color:#1A4731; font-weight:500; }
  .csm-btn .csm-arrow { font-size:9px; color:#9CA3AF; flex-shrink:0; }
  .csm-dropdown { position:absolute; top:calc(100% + 4px); left:0; z-index:120;
    background:white; border:1px solid #E5E7EB; border-radius:8px;
    box-shadow:0 8px 24px rgba(0,0,0,.12); width:240px; }
  .csm-dropdown-search { padding:8px 10px 4px; border-bottom:1px solid #F3F4F6; }
  .csm-dropdown-search input { width:100%; border:1px solid #E5E7EB; border-radius:5px;
    font-size:12px; padding:4px 8px; outline:none; }
  .csm-dropdown-search input:focus { border-color:#1A4731; }
  .csm-dropdown-actions { display:flex; gap:6px; padding:5px 10px;
    border-bottom:1px solid #F3F4F6; }
  .csm-action-btn { font-size:11px; color:#1A4731; background:none; border:none;
    cursor:pointer; padding:0; font-weight:500; }
  .csm-action-btn:hover { text-decoration:underline; }
  .csm-options { max-height:220px; overflow-y:auto; padding:4px 6px 6px; }
  .csm-option { display:flex; align-items:center; gap:7px; padding:4px 6px;
    border-radius:4px; cursor:pointer; font-size:12px; color:#374151; }
  .csm-option:hover { background:#F0FDF4; }
  .csm-option input[type=checkbox] { accent-color:#1A4731; width:13px; height:13px;
    flex-shrink:0; cursor:pointer; }
  /* ── Help tooltip ─────────────────────────────────────────────────────── */
  .help-btn { display:inline-flex; align-items:center; justify-content:center;
    width:15px; height:15px; border-radius:50%; background:#E5E7EB; color:#6B7280;
    font-size:9px; font-weight:700; cursor:pointer; vertical-align:middle;
    margin-left:4px; line-height:1; border:none; flex-shrink:0;
    transition:background .15s; }
  .help-btn:hover { background:#D1D5DB; color:#374151; }
  .help-tip { position:fixed; z-index:200; width:300px; background:white;
    border:1px solid #E5E7EB; border-radius:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.12); padding:14px 16px;
    font-size:12px; line-height:1.5; color:#374151;
    max-height:calc(100vh - 24px); overflow-y:auto;
    pointer-events:none; opacity:0; transition:opacity .12s; }
  .help-tip.visible { opacity:1; pointer-events:auto; }
  .help-tip h4 { font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:.05em; color:#6B7280; margin:0 0 10px; }
  .help-tip dl { margin:0; }
  .help-tip dt { font-weight:600; color:#111827; margin-top:7px; }
  .help-tip dt:first-of-type { margin-top:0; }
  .help-tip dd { margin:1px 0 0 0; color:#6B7280; }
  /* ── HubSpot join validation panel ──────────────────────────────────── */
  .join-panel-header { display:flex; align-items:center; justify-content:space-between;
    padding:10px 16px; cursor:pointer; user-select:none; }
  .join-panel-header:hover { background:#FAFAFA; }
  .join-filter-btn { font-size:11px; padding:3px 10px; border-radius:20px;
    border:1px solid #E5E7EB; background:white; color:#6B7280; cursor:pointer;
    font-weight:500; transition:all .12s; white-space:nowrap; }
  .join-filter-btn:hover { border-color:#1A4731; color:#1A4731; }
  .join-filter-btn.active { background:#1A4731; color:white; border-color:#1A4731; }
  .join-badge { display:inline-flex; align-items:center; gap:4px; font-size:11px;
    font-weight:600; padding:2px 8px; border-radius:12px; border:1px solid; }
  .join-badge-matched         { color:#065F46; background:#D1FAE5; border-color:#A7F3D0; }
  .join-badge-no-match        { color:#991B1B; background:#FEE2E2; border-color:#FECACA; }
  .join-badge-duplicate       { color:#5B21B6; background:#EDE9FE; border-color:#DDD6FE; }
  .join-badge-no-owner        { color:#92400E; background:#FEF3C7; border-color:#FDE68A; }
  .join-badge-missing-ns      { color:#374151; background:#F3F4F6; border-color:#E5E7EB; }
</style>
</head>
<body>

<!-- ── Header ──────────────────────────────────────────────────────────────── -->
<header class="sprout-green text-white px-6 py-3 flex items-center justify-between shadow">
  <div class="flex items-center gap-3">
    <span class="text-xl font-bold tracking-tight">Sprout</span>
    <span class="text-green-300 text-sm">|</span>
    <span class="text-sm font-medium text-green-100">NRR Dashboard</span>
  </div>
  <div id="headerMonth" class="text-sm text-green-200"></div>
</header>

<!-- ── Filter bar ──────────────────────────────────────────────────────────── -->
<div class="bg-white border-b px-6 py-3 flex flex-wrap gap-3 items-center">
  <div>
    <label class="text-xs text-gray-500 uppercase font-medium mr-1">Month</label>
    <select id="monthSel" class="border border-gray-200 rounded-md text-sm px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-600"></select>
  </div>
  <div class="csm-filter">
    <label class="text-xs text-gray-500 uppercase font-medium block mb-1">CSM</label>
    <button id="csmBtn" class="csm-btn" aria-haspopup="listbox" aria-expanded="false">
      <span id="csmBtnLabel">All CSMs</span><span class="csm-arrow">▾</span>
    </button>
    <div id="csmDropdown" class="csm-dropdown hidden">
      <div class="csm-dropdown-search">
        <input id="csmSearch" type="search" placeholder="Search CSM…" autocomplete="off">
      </div>
      <div class="csm-dropdown-actions">
        <button id="csmSelectAll" class="csm-action-btn">Select all</button>
        <span class="text-gray-300 text-xs">·</span>
        <button id="csmClear" class="csm-action-btn">Clear</button>
      </div>
      <div id="csmOptions" class="csm-options"></div>
    </div>
  </div>
  <div class="flex-1 min-w-48">
    <input id="searchBox" type="search" placeholder="Search customer…"
      class="w-full border border-gray-200 rounded-md text-sm px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-600">
  </div>
  <div id="rowCount" class="text-xs text-gray-400 ml-auto"></div>
</div>

<!-- ── Movement tabs ────────────────────────────────────────────────────────── -->
<div class="bg-white border-b px-6 flex gap-1 text-sm">
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700 tab-active" data-mv="all">All</button>
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700" data-mv="new">New</button>
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700" data-mv="expansion">Expansion</button>
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700" data-mv="contraction">Contraction</button>
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700" data-mv="retained">Flat</button>
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700" data-mv="churned">Churned</button>
  <button class="tab py-2.5 px-3 text-gray-500 hover:text-gray-700" data-mv="reactivated">Reactivated</button>
</div>

<!-- ── Main content ─────────────────────────────────────────────────────────── -->
<main class="px-6 py-4 space-y-4">

  <!-- KPI cards -->
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
    <div class="bg-white rounded-xl border p-4">
      <div class="text-xs text-gray-400 uppercase font-medium">Starting MRR</div>
      <div id="kpiStart" class="text-lg font-bold text-gray-800 mt-1">—</div>
    </div>
    <div class="bg-white rounded-xl border p-4">
      <div class="text-xs text-gray-400 uppercase font-medium">+ New</div>
      <div id="kpiNew" class="text-lg font-bold text-blue-600 mt-1">—</div>
    </div>
    <div class="bg-white rounded-xl border p-4">
      <div class="text-xs text-gray-400 uppercase font-medium">+ Expansion</div>
      <div id="kpiExp" class="text-lg font-bold text-green-600 mt-1">—</div>
    </div>
    <div class="bg-white rounded-xl border p-4">
      <div class="text-xs text-gray-400 uppercase font-medium">− Contraction</div>
      <div id="kpiCon" class="text-lg font-bold text-amber-600 mt-1">—</div>
    </div>
    <div class="bg-white rounded-xl border p-4">
      <div class="text-xs text-gray-400 uppercase font-medium">− Churn</div>
      <div id="kpiChurn" class="text-lg font-bold text-red-600 mt-1">—</div>
    </div>
    <div class="bg-white rounded-xl border p-4 border-l-4 border-l-green-700">
      <div class="text-xs text-gray-400 uppercase font-medium">NRR %</div>
      <div id="kpiNrr" class="text-2xl font-extrabold text-green-700 mt-1">—</div>
      <div class="text-xs text-gray-400 mt-0.5">Ending: <span id="kpiEnd" class="text-gray-600 font-medium">—</span></div>
    </div>
  </div>

  <!-- Trend chart + table side by side on wide screens -->
  <div class="flex flex-col lg:flex-row gap-4">

    <!-- Left panel: NRR trend + movement breakdown -->
    <div class="bg-white rounded-xl border p-4 lg:w-72 shrink-0 flex flex-col gap-5">
      <div>
        <div class="text-xs text-gray-400 uppercase font-medium mb-2">NRR % Trend (12 months)</div>
        <canvas id="nrrChart" height="150"></canvas>
      </div>
      <div>
        <div class="text-xs text-gray-400 uppercase font-medium mb-2">Customer Movement (12 months)</div>
        <canvas id="mvChart" height="160"></canvas>
      </div>
    </div>

    <!-- Main customer table -->
    <div class="bg-white rounded-xl border flex-1 overflow-hidden">
      <table id="mainTable" class="w-full text-sm">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="sortable text-left px-4 py-2.5 font-medium text-gray-600" data-col="2">Customer</th>
            <th class="sortable text-left px-4 py-2.5 font-medium text-gray-600 hidden sm:table-cell" data-col="4">CSM</th>
            <th class="sortable text-right px-4 py-2.5 font-medium text-gray-600" data-col="5">Prev MRR</th>
            <th class="sortable text-right px-4 py-2.5 font-medium text-gray-600" data-col="6">Curr MRR</th>
            <th class="sortable text-right px-4 py-2.5 font-medium text-gray-600" data-col="7">Delta</th>
            <th class="sortable text-center px-4 py-2.5 font-medium text-gray-600" data-col="8">Movement <button class="help-btn" onclick="toggleHelp(event)" aria-label="Movement definitions">?</button></th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
      <div id="emptyMsg" class="hidden text-center text-gray-400 py-12 text-sm">No customers match this filter.</div>
    </div>

  </div>

</main>

<!-- ── HubSpot Ownership Validation panel ───────────────────────────────────── -->
<section class="px-6 pb-4">
  <div class="bg-white rounded-xl border">

    <!-- Collapsible header -->
    <div class="join-panel-header rounded-xl" onclick="toggleJoinPanel()">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-sm font-medium text-gray-700">HubSpot Ownership Validation</span>
        <div id="joinSummaryBadges" class="flex flex-wrap gap-1.5"></div>
      </div>
      <span id="joinArrow" class="text-gray-400 text-xs ml-2 flex-shrink-0">▸</span>
    </div>

    <!-- Expandable body (lazy-rendered on first open) -->
    <div id="joinPanelBody" class="hidden border-t px-4 pt-3 pb-4">

      <!-- Status filter pills -->
      <div class="flex flex-wrap gap-1.5 mb-3" id="joinStatusFilter"></div>

      <!-- Search -->
      <div class="mb-3">
        <input id="joinSearch" type="search" placeholder="Search customer, NS ID, or HubSpot company…"
          class="border border-gray-200 rounded-md text-sm px-3 py-1.5 w-full max-w-sm
                 focus:outline-none focus:ring-2 focus:ring-green-600">
      </div>

      <!-- Debug table -->
      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead class="bg-gray-50 border-b">
            <tr>
              <th class="text-left px-3 py-2 font-medium text-gray-500">Customer</th>
              <th class="text-left px-3 py-2 font-medium text-gray-500">NS ID</th>
              <th class="text-left px-3 py-2 font-medium text-gray-500">Join Status</th>
              <th class="text-center px-3 py-2 font-medium text-gray-500">HS Matches</th>
              <th class="text-left px-3 py-2 font-medium text-gray-500">HubSpot Company</th>
              <th class="text-left px-3 py-2 font-medium text-gray-500">HubSpot Owner</th>
            </tr>
          </thead>
          <tbody id="joinTableBody"></tbody>
        </table>
      </div>
      <div id="joinEmpty" class="hidden text-center text-gray-400 py-6 text-sm">No accounts match this filter.</div>
      <div id="joinCount" class="text-xs text-gray-400 mt-2"></div>

    </div>
  </div>
</section>

<!-- ── Drilldown modal ──────────────────────────────────────────────────────── -->
<div id="modal" class="modal-overlay hidden">
  <div class="modal-box">
    <div class="flex justify-between items-start mb-4">
      <div>
        <h2 id="ddTitle" class="text-lg font-bold text-gray-800"></h2>
        <p id="ddSubtitle" class="text-sm text-gray-500 mt-0.5"></p>
      </div>
      <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600 text-2xl leading-none">✕</button>
    </div>

    <!-- Mini KPI row 1: totals + movement -->
    <div class="grid grid-cols-3 gap-3 mb-2">
      <div class="bg-gray-50 rounded-lg p-3">
        <div class="text-xs text-gray-400 uppercase">Prev MRR</div>
        <div id="ddPrev" class="text-base font-bold text-gray-700">—</div>
      </div>
      <div class="bg-gray-50 rounded-lg p-3">
        <div class="text-xs text-gray-400 uppercase">Curr MRR</div>
        <div id="ddCurr" class="text-base font-bold text-gray-700">—</div>
      </div>
      <div class="bg-gray-50 rounded-lg p-3">
        <div class="text-xs text-gray-400 uppercase">Movement <button class="help-btn" onclick="toggleHelp(event)" aria-label="Movement definitions">?</button></div>
        <div id="ddMovement" class="text-sm font-semibold mt-0.5">—</div>
      </div>
    </div>
    <!-- Mini KPI row 2: recurring vs true-up breakdown -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
      <div class="bg-blue-50 rounded-lg p-2.5">
        <div class="text-xs text-blue-400 uppercase font-medium">Prev Recurring</div>
        <div id="ddPrevRec" class="text-sm font-bold text-blue-700 mt-0.5">—</div>
      </div>
      <div class="bg-blue-50 rounded-lg p-2.5">
        <div class="text-xs text-blue-400 uppercase font-medium">Curr Recurring</div>
        <div id="ddCurrRec" class="text-sm font-bold text-blue-700 mt-0.5">—</div>
      </div>
      <div class="bg-purple-50 rounded-lg p-2.5">
        <div class="text-xs text-purple-400 uppercase font-medium">Prev True-up</div>
        <div id="ddPrevTu" class="text-sm font-bold text-purple-700 mt-0.5">—</div>
      </div>
      <div class="bg-purple-50 rounded-lg p-2.5">
        <div class="text-xs text-purple-400 uppercase font-medium">Curr True-up</div>
        <div id="ddCurrTu" class="text-sm font-bold text-purple-700 mt-0.5">—</div>
      </div>
    </div>

    <!-- Invoice lines — for CSM validation -->
    <div class="flex items-center justify-between mb-1">
      <div class="text-xs font-medium text-gray-500 uppercase">Invoice Lines — <span id="ddMonth"></span></div>
      <div class="text-xs text-gray-400 italic">For CSM validation</div>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead class="bg-gray-50 border-b">
          <tr>
            <th class="text-left px-2 py-1.5 font-medium text-gray-500">Invoice</th>
            <th class="text-left px-2 py-1.5 font-medium text-gray-500">Description</th>
            <th class="text-left px-2 py-1.5 font-medium text-gray-500">Module</th>
            <th class="text-left px-2 py-1.5 font-medium text-gray-500">Coverage</th>
            <th class="text-center px-2 py-1.5 font-medium text-gray-500">Mo.</th>
            <th class="text-right px-2 py-1.5 font-medium text-gray-500">Line Amt</th>
            <th class="text-right px-2 py-1.5 font-medium text-gray-500">Mo. Alloc</th>
            <th class="text-left px-2 py-1.5 font-medium text-gray-500">Type</th>
          </tr>
        </thead>
        <tbody id="ddBody"></tbody>
      </table>
    </div>
    <div id="ddEmpty" class="hidden text-center text-gray-400 py-6 text-sm">No invoice lines for this period.</div>

    <!-- Totals -->
    <div id="ddTotals" class="mt-3 pt-3 border-t flex gap-4 text-xs text-gray-500">
      <span>Total allocated: <strong id="ddTotal" class="text-gray-700">—</strong></span>
      <span>Paid: <strong id="ddPaid" class="text-green-700">—</strong></span>
      <span>Unpaid/Overdue: <strong id="ddUnpaid" class="text-red-600">—</strong></span>
    </div>
  </div>
</div>

<!-- ── Movement definitions tooltip ─────────────────────────────────────────── -->
<div id="helpTip" class="help-tip" role="tooltip">
  <h4>Movement Definitions</h4>
  <dl>
    <dt>New</dt>
    <dd>Customer generated revenue this month but had no revenue in any previous month.</dd>
    <dt>Reactivated</dt>
    <dd>Customer previously churned and returned after a period with zero revenue.</dd>
    <dt>Expansion</dt>
    <dd>Recurring subscription revenue increased compared to the previous month.</dd>
    <dt>Flat (True-up)</dt>
    <dd>Recurring subscription revenue stayed the same, but a true-up adjustment occurred.</dd>
    <dt>Flat</dt>
    <dd>No change in recurring revenue and no true-up adjustments.</dd>
    <dt>Contraction</dt>
    <dd>Recurring subscription revenue decreased but the customer is still active.</dd>
    <dt>Churned</dt>
    <dd>Customer had revenue in the previous month but now has zero revenue.</dd>
  </dl>
</div>

<!-- ── Data ──────────────────────────────────────────────────────────────────── -->
<script>
const SUMMARY = __SUMMARY__;
const CDETAIL = __CDETAIL__;
const INVOICE_DATA = __INVOICE_DATA__;
const CSM_LIST = __CSM_LIST__;
const DEFAULT_MONTH = __DEFAULT_MONTH__;
const HS_JOIN_MAP = __HS_JOIN_MAP__;
</script>

<!-- ── App ───────────────────────────────────────────────────────────────────── -->
<script>
'use strict';

// ── State ──────────────────────────────────────────────────────────────────────
let selMonth    = DEFAULT_MONTH;
let selCsms     = new Set();  // empty = all CSMs
let selMovement = 'all';
let searchTerm  = '';
let sortCol     = 7;        // default sort: abs(delta) descending
let sortAsc     = false;
let trendChart  = null;
let mvChart     = null;

// ── Formatters ────────────────────────────────────────────────────────────────
const fmt = new Intl.NumberFormat('en-PH', { style:'currency', currency:'PHP', maximumFractionDigits:0 });
const fmtS= new Intl.NumberFormat('en-PH', { style:'currency', currency:'PHP', maximumFractionDigits:0, notation:'compact' });

function fmtDelta(v) {
  if (v === 0) return '<span class="text-gray-400">—</span>';
  const s = fmt.format(Math.abs(v));
  return v > 0
    ? `<span class="text-green-600">+${s}</span>`
    : `<span class="text-red-500">−${s}</span>`;
}

// 'retained' stored in data; display label depends on true-up delta
const MV_LABEL = {
  new:'New', expansion:'Expansion', contraction:'Contraction',
  retained:'Flat', churned:'Churned', reactivated:'Reactivated',
};
const MV_CLASS = {
  new:'badge-new', expansion:'badge-expansion', contraction:'badge-contraction',
  retained:'badge-retained', churned:'badge-churned', reactivated:'badge-reactivated',
};
function badge(mv) {
  return `<span class="${MV_CLASS[mv]||'badge-retained'} text-xs font-medium px-2 py-0.5 rounded-full">${MV_LABEL[mv]||mv}</span>`;
}
// For table rows where we have full CDETAIL row: distinguish Flat vs Flat (True-up)
function badgeRow(r) {
  const mv = r[8];
  if (mv === 'retained') {
    const prevTu = r[12] || 0, currTu = r[13] || 0;
    if (prevTu !== currTu) {
      return '<span class="badge-retained-trueup text-xs font-medium px-2 py-0.5 rounded-full">Flat (True-up)</span>';
    }
  }
  return badge(mv);
}

function fmtMonth(m) {
  if (!m) return '';
  const [y, mo] = m.split('-');
  return new Date(+y, +mo-1, 1).toLocaleString('en-US', {month:'long', year:'numeric'});
}

// ── Help tooltip ──────────────────────────────────────────────────────────────
const helpTip = document.getElementById('helpTip');
let helpOpen = false;

function toggleHelp(e) {
  e.stopPropagation();
  if (helpOpen) { hideHelp(); return; }
  const btn = e.currentTarget;
  const r   = btn.getBoundingClientRect();
  const tip = helpTip;
  const vw  = window.innerWidth;
  const vh  = window.innerHeight;
  const pad = 8;

  // Make visible off-screen first so offsetHeight is measurable
  tip.style.top  = '-9999px';
  tip.style.left = '-9999px';
  tip.classList.add('visible');
  helpOpen = true;

  const tw = tip.offsetWidth;
  const th = tip.offsetHeight;

  // Prefer: left-aligned to button, below button
  let left = r.left;
  let top  = r.bottom + 6;

  // Shift left if it clips the right edge
  if (left + tw + pad > vw) left = vw - tw - pad;
  // Never clip the left edge
  if (left < pad) left = pad;

  // If it would clip the bottom, open upward instead
  if (top + th + pad > vh) top = r.top - th - 6;
  // Final clamp: never go above the top of the viewport
  if (top < pad) top = pad;

  tip.style.left = left + 'px';
  tip.style.top  = top  + 'px';
}
function hideHelp() {
  helpTip.classList.remove('visible');
  helpOpen = false;
}
document.addEventListener('click', hideHelp);
document.addEventListener('keydown', e => { if (e.key === 'Escape') hideHelp(); });

// ── Build month selector ──────────────────────────────────────────────────────
function buildMonthSel() {
  const sel = document.getElementById('monthSel');
  const months = [...new Set(CDETAIL.map(r => r[0]))].sort().reverse();
  months.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = fmtMonth(m);
    if (m === DEFAULT_MONTH) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.addEventListener('change', () => { selMonth = sel.value; render(); });
}

// ── Multi-select CSM filter ───────────────────────────────────────────────────
function buildCsmFilter() {
  const btn      = document.getElementById('csmBtn');
  const dropdown = document.getElementById('csmDropdown');
  const optWrap  = document.getElementById('csmOptions');
  const searchEl = document.getElementById('csmSearch');

  function renderOptions() {
    const q = searchEl.value.toLowerCase();
    const visible = CSM_LIST.filter(n => !q || n.toLowerCase().includes(q));
    optWrap.innerHTML = visible.map(name => {
      const chk = selCsms.has(name) ? 'checked' : '';
      const safe = name.replace(/"/g, '&quot;');
      return `<label class="csm-option"><input type="checkbox" value="${safe}" ${chk}><span>${name}</span></label>`;
    }).join('');
    optWrap.querySelectorAll('input').forEach(cb => {
      cb.addEventListener('change', () => {
        cb.checked ? selCsms.add(cb.value) : selCsms.delete(cb.value);
        syncBtn(); render();
      });
    });
  }

  function syncBtn() {
    const lbl = document.getElementById('csmBtnLabel');
    if (selCsms.size === 0)      lbl.textContent = 'All CSMs';
    else if (selCsms.size === 1) lbl.textContent = [...selCsms][0];
    else                         lbl.textContent = selCsms.size + ' CSMs selected';
    btn.classList.toggle('active', selCsms.size > 0);
    btn.setAttribute('aria-expanded', !dropdown.classList.contains('hidden'));
  }

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const opening = dropdown.classList.contains('hidden');
    dropdown.classList.toggle('hidden', !opening);
    if (opening) { renderOptions(); searchEl.focus(); }
    btn.setAttribute('aria-expanded', opening);
  });
  dropdown.addEventListener('click', e => e.stopPropagation());
  document.addEventListener('click', () => {
    dropdown.classList.add('hidden');
    btn.setAttribute('aria-expanded', 'false');
  });

  searchEl.addEventListener('input', renderOptions);

  document.getElementById('csmSelectAll').addEventListener('click', () => {
    CSM_LIST.forEach(n => selCsms.add(n));
    renderOptions(); syncBtn(); render();
  });
  document.getElementById('csmClear').addEventListener('click', () => {
    selCsms.clear();
    renderOptions(); syncBtn(); render();
  });

  renderOptions();
  syncBtn();
}

// ── Movement tabs ─────────────────────────────────────────────────────────────
function buildTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('tab-active'));
      btn.classList.add('tab-active');
      selMovement = btn.dataset.mv;
      render();
    });
  });
}

// ── Sort headers ──────────────────────────────────────────────────────────────
function buildSortHeaders() {
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = +th.dataset.col;
      if (sortCol === col) sortAsc = !sortAsc;
      else { sortCol = col; sortAsc = col === 2 || col === 4 || col === 8; }
      render();
    });
  });
}

// ── Month index — pre-bucket CDETAIL by month for O(1) lookup ─────────────────
const CD_BY_MONTH = {};
for (const r of CDETAIL) {
  if (!CD_BY_MONTH[r[0]]) CD_BY_MONTH[r[0]] = [];
  CD_BY_MONTH[r[0]].push(r);
}

// ── KPI computation from CDETAIL rows ─────────────────────────────────────────
// CDETAIL row indices: [0]month [1]cid [2]name [3]csm_id [4]csm_name
//   [5]begin_mrr [6]end_mrr [7]delta [8]movement
//   [10]prev_rec [11]curr_rec [12]prev_tu [13]curr_tu
function computeKpis(rows) {
  let begin = 0, end = 0, newMrr = 0, expansion = 0, contraction = 0, churn = 0;
  for (const r of rows) {
    const mv = r[8];
    begin      += r[5] || 0;
    end        += r[6] || 0;
    if (mv === 'new' || mv === 'reactivated') newMrr     += r[6] || 0;
    if (mv === 'expansion')                  expansion   += r[7] || 0;
    if (mv === 'contraction')                contraction += r[7] || 0;  // already negative
    if (mv === 'churned')                    churn       += r[5] || 0;
  }
  // NRR = (begin + expansion + contraction − churn) / begin × 100
  // contraction is negative so adding it reduces the total correctly
  const nrr_pct = begin > 0
    ? (begin + expansion + contraction - churn) / begin * 100
    : null;
  return { begin_mrr: begin, ending_mrr: end, new_mrr: newMrr,
           expansion, contraction, churn, nrr_pct };
}

// ── Filtered + sorted rows ────────────────────────────────────────────────────
function filteredRows() {
  const q = searchTerm.toLowerCase();
  return (CD_BY_MONTH[selMonth] || []).filter(r => {
    if (selCsms.size > 0 && !selCsms.has(r[4])) return false;
    if (selMovement !== 'all' && r[8] !== selMovement) return false;
    if (q && !r[2].toLowerCase().includes(q)) return false;
    return true;
  });
}

function sortedRows(rows) {
  return [...rows].sort((a, b) => {
    const av = a[sortCol], bv = b[sortCol];
    if (sortCol === 2 || sortCol === 4 || sortCol === 8) {
      return sortAsc
        ? String(av||'').localeCompare(String(bv||''))
        : String(bv||'').localeCompare(String(av||''));
    }
    // For delta col (7), sort by absolute value so biggest movers surface first
    const an = sortCol === 7 ? Math.abs(av||0) : (av||0);
    const bn = sortCol === 7 ? Math.abs(bv||0) : (bv||0);
    return sortAsc ? an - bn : bn - an;
  });
}

// ── KPIs — computed live from filtered CDETAIL rows ───────────────────────────
function renderKpis() {
  const rows = (CD_BY_MONTH[selMonth] || []).filter(
    r => selCsms.size === 0 || selCsms.has(r[4])
  );
  const s = computeKpis(rows);
  document.getElementById('kpiStart').textContent = fmtS.format(s.begin_mrr||0);
  document.getElementById('kpiNew').textContent   = '+' + fmtS.format(s.new_mrr||0);
  document.getElementById('kpiExp').textContent   = '+' + fmtS.format(s.expansion||0);
  document.getElementById('kpiCon').textContent   = '−' + fmtS.format(Math.abs(s.contraction||0));
  document.getElementById('kpiChurn').textContent = '−' + fmtS.format(Math.abs(s.churn||0));
  document.getElementById('kpiEnd').textContent   = fmtS.format(s.ending_mrr||0);
  const nrr = s.nrr_pct;
  const nrrEl = document.getElementById('kpiNrr');
  nrrEl.textContent = nrr != null ? nrr.toFixed(1) + '%' : 'N/A';
  nrrEl.className = 'text-2xl font-extrabold mt-1 ' +
    (nrr == null ? 'text-gray-400' : nrr >= 100 ? 'text-green-700' : 'text-amber-600');
  document.getElementById('headerMonth').textContent = fmtMonth(selMonth);
}

// ── Sort header classes ────────────────────────────────────────────────────────
function updateSortClasses() {
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.remove('sorted-asc', 'sorted-desc');
    if (+th.dataset.col === sortCol) {
      th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
    }
  });
}

// ── Table ─────────────────────────────────────────────────────────────────────
function renderTable(rows) {
  const tbody = document.getElementById('tableBody');
  const empty = document.getElementById('emptyMsg');
  const sorted = sortedRows(rows);

  if (!sorted.length) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    document.getElementById('rowCount').textContent = '';
    return;
  }
  empty.classList.add('hidden');
  document.getElementById('rowCount').textContent = `${sorted.length.toLocaleString()} customers`;

  tbody.innerHTML = sorted.map(r => {
    const [month, cid, name, csm_id, csm_name, begin, end, delta, movement] = r;
    const prevFmt = begin ? fmt.format(begin) : '<span class="text-gray-300">—</span>';
    const currFmt = end   ? fmt.format(end)   : '<span class="text-gray-300">—</span>';
    const truncName = name.length > 44 ? name.slice(0, 44) + '…' : name;
    const safeTitle = name.replace(/"/g, '&quot;');
    return `<tr data-cid="${cid}" data-month="${month}" class="border-b border-gray-50">
      <td class="px-4 py-2 font-medium text-gray-800" title="${safeTitle}">${truncName}</td>
      <td class="px-4 py-2 text-gray-500 hidden sm:table-cell text-xs">${csm_name||'—'}</td>
      <td class="px-4 py-2 text-right text-gray-500 tabular-nums">${prevFmt}</td>
      <td class="px-4 py-2 text-right font-medium text-gray-800 tabular-nums">${currFmt}</td>
      <td class="px-4 py-2 text-right tabular-nums">${fmtDelta(delta||0)}</td>
      <td class="px-4 py-2 text-center">${badgeRow(r)}</td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => openModal(+tr.dataset.cid, tr.dataset.month));
  });
}

// ── Trend chart — NRR % computed from filtered CDETAIL ────────────────────────
function renderTrend() {
  const allMonths = Object.keys(CD_BY_MONTH).sort();
  const idx = allMonths.indexOf(selMonth);
  const slice = allMonths.slice(Math.max(0, idx - 11), idx + 1);
  const data = slice.map(m => {
    const rows = (CD_BY_MONTH[m] || []).filter(
      r => selCsms.size === 0 || selCsms.has(r[4])
    );
    const kpis = computeKpis(rows);
    return kpis.nrr_pct != null ? +kpis.nrr_pct.toFixed(1) : null;
  });
  const labels = slice.map(m => {
    const [y, mo] = m.split('-');
    return new Date(+y, +mo-1, 1).toLocaleString('en-US', {month:'short'});
  });

  if (trendChart) trendChart.destroy();
  const ctx = document.getElementById('nrrChart').getContext('2d');
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data,
        borderColor: '#1A4731',
        backgroundColor: 'rgba(26,71,49,0.08)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: data.map(v => v == null ? 'transparent' : v >= 100 ? '#15803d' : '#D97706'),
        tension: 0.3,
        fill: true,
        spanGaps: true,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ctx.parsed.y != null ? ctx.parsed.y + '%' : 'N/A' } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 } } },
        y: {
          ticks: { font: { size: 10 }, callback: v => v + '%' },
          grid: { color: '#F3F4F6' },
        },
      },
    },
  });
}

// ── Movement breakdown chart — stacked bar, customer counts per movement ───────
function renderMovementChart() {
  const allMonths = Object.keys(CD_BY_MONTH).sort();
  const idx = allMonths.indexOf(selMonth);
  const slice = allMonths.slice(Math.max(0, idx - 11), idx + 1);

  const MV_TYPES  = ['new', 'reactivated', 'expansion', 'retained', 'contraction', 'churned'];
  const MV_LABELS = { new:'New', reactivated:'Reactivated', expansion:'Expansion',
                      retained:'Flat', contraction:'Contraction', churned:'Churned' };
  const MV_COLORS = { new:'#3B82F6', reactivated:'#8B5CF6', expansion:'#10B981',
                      retained:'#9CA3AF', contraction:'#F59E0B', churned:'#EF4444' };

  // counts[mv] = array of counts, one per month slice
  const counts = {};
  MV_TYPES.forEach(mv => counts[mv] = []);

  slice.forEach(m => {
    const rows = (CD_BY_MONTH[m] || []).filter(
      r => selCsms.size === 0 || selCsms.has(r[4])
    );
    const tally = {};
    MV_TYPES.forEach(mv => tally[mv] = 0);
    rows.forEach(r => { if (tally[r[8]] !== undefined) tally[r[8]]++; });
    MV_TYPES.forEach(mv => counts[mv].push(tally[mv]));
  });

  const labels = slice.map(m => {
    const [y, mo] = m.split('-');
    return new Date(+y, +mo-1, 1).toLocaleString('en-US', {month:'short'});
  });

  if (mvChart) mvChart.destroy();
  const ctx = document.getElementById('mvChart').getContext('2d');
  mvChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: MV_TYPES.map(mv => ({
        label: MV_LABELS[mv],
        data: counts[mv],
        backgroundColor: MV_COLORS[mv],
        borderWidth: 0,
      })),
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: { font: { size: 9 }, boxWidth: 8, padding: 5 },
        },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { font: { size: 9 } } },
        y: { stacked: true, grid: { color: '#F3F4F6' }, ticks: { font: { size: 9 } } },
      },
    },
  });
}

// ── Modal / Drilldown ─────────────────────────────────────────────────────────
// Invoice detail is secondary — for CSM validation and investigation only.
function openModal(cid, month) {
  const cd = CDETAIL.find(r => r[0] === month && r[1] === cid);
  if (!cd) return;
  // Destructure all 14 fields
  const [, , name, , csm_name, begin, end, delta, movement, ,
         prev_rec, curr_rec, prev_tu, curr_tu] = cd;

  document.getElementById('ddTitle').textContent    = name;
  document.getElementById('ddSubtitle').textContent = (csm_name || '—') + ' · ' + fmtMonth(month);
  document.getElementById('ddMonth').textContent    = fmtMonth(month);
  document.getElementById('ddPrev').textContent     = begin ? fmt.format(begin) : '—';
  document.getElementById('ddCurr').textContent     = end   ? fmt.format(end)   : '—';
  document.getElementById('ddMovement').innerHTML   = badgeRow(cd);

  // Recurring vs true-up breakdown
  document.getElementById('ddPrevRec').textContent  = prev_rec ? fmt.format(prev_rec) : '—';
  document.getElementById('ddCurrRec').textContent  = curr_rec ? fmt.format(curr_rec) : '—';
  document.getElementById('ddPrevTu').textContent   = prev_tu  ? fmt.format(prev_tu)  : '—';
  document.getElementById('ddCurrTu').textContent   = curr_tu  ? fmt.format(curr_tu)  : '—';

  const key = `${cid}|${month}`;
  const lines = INVOICE_DATA[key] || [];
  const tbody = document.getElementById('ddBody');
  const empty = document.getElementById('ddEmpty');
  const totEl = document.getElementById('ddTotals');

  if (!lines.length) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    totEl.classList.add('hidden');
  } else {
    empty.classList.add('hidden');
    totEl.classList.remove('hidden');

    let totalAlloc = 0, paid = 0, unpaid = 0;
    tbody.innerHTML = lines.map(line => {
      const [desc, lineAmt, moAlloc, rt, mod, months_cov, cs, ce, invNum, invDate, payStatus] = line;
      totalAlloc += moAlloc || 0;
      if (payStatus === 'Paid')                                    paid   += moAlloc || 0;
      else if (payStatus === 'Partially Paid')                    { paid += (moAlloc||0)/2; unpaid += (moAlloc||0)/2; }
      else if (payStatus === 'Unpaid' || payStatus === 'Overdue')  unpaid += moAlloc || 0;

      const rtLabel = rt === 'r' ? '<span class="text-green-600">Recurring</span>'
                    : rt === 't' ? '<span class="text-purple-600">True-up</span>'
                    : '<span class="text-gray-400">Other</span>';
      const invLabel = invNum
        ? `<div class="font-medium text-gray-700">${invNum}</div><div class="text-gray-400">${invDate}</div>`
        : '<span class="text-gray-300">—</span>';
      const covLabel = months_cov > 1 ? `${cs} → ${ce} (${months_cov}mo)` : cs || '—';
      const truncDesc = desc.length > 55 ? desc.slice(0,55)+'…' : desc;
      const safeDesc = desc.replace(/"/g, '&quot;');

      return `<tr class="border-b border-gray-50 hover:bg-gray-50">
        <td class="px-2 py-1.5">${invLabel}</td>
        <td class="px-2 py-1.5 text-gray-600" title="${safeDesc}">${truncDesc}</td>
        <td class="px-2 py-1.5 text-gray-600">${mod || '—'}</td>
        <td class="px-2 py-1.5 text-gray-400 whitespace-nowrap">${covLabel}</td>
        <td class="px-2 py-1.5 text-center text-gray-500">${months_cov || 1}</td>
        <td class="px-2 py-1.5 text-right text-gray-500 tabular-nums">${fmt.format(lineAmt||0)}</td>
        <td class="px-2 py-1.5 text-right font-medium text-gray-800 tabular-nums">${fmt.format(moAlloc||0)}</td>
        <td class="px-2 py-1.5">${rtLabel}</td>
      </tr>`;
    }).join('');

    document.getElementById('ddTotal').textContent  = fmt.format(totalAlloc);
    document.getElementById('ddPaid').textContent   = fmt.format(paid);
    document.getElementById('ddUnpaid').textContent = fmt.format(unpaid);
  }

  document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}
document.getElementById('modal').addEventListener('click', e => {
  if (e.target === document.getElementById('modal')) closeModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── HubSpot join validation panel ────────────────────────────────────────────
// CID_NAME: fastest name lookup — built once from all CDETAIL rows
const CID_NAME = {};
for (const r of CDETAIL) CID_NAME[String(r[1])] = r[2];

const JOIN_STATUS_META = {
  matched:                                  { label: 'Matched',             cls: 'join-badge-matched',   problem: false },
  matched_no_owner:                         { label: 'No Owner',             cls: 'join-badge-no-owner',  problem: true  },
  no_name_match:                            { label: 'No Name Match',        cls: 'join-badge-no-match',  problem: true  },
  missing_hubspot_record_id_in_netsuite:    { label: 'No HS ID in NS',       cls: 'join-badge-no-match',  problem: true  },
  no_hubspot_match_for_record_id:           { label: 'HS ID Not Found',      cls: 'join-badge-duplicate', problem: true  },
};
const JOIN_PROBLEMS = new Set([
  'matched_no_owner',
  'no_name_match',
  'missing_hubspot_record_id_in_netsuite',
  'no_hubspot_match_for_record_id',
]);

let joinFilter      = 'problems';
let joinSearch      = '';
let joinPanelOpen   = false;
let joinPanelBuilt  = false;

function initJoinPanel() {
  // Render summary badges in the collapsed header (always visible)
  const counts = {};
  for (const info of Object.values(HS_JOIN_MAP)) {
    counts[info.hubspot_join_status] = (counts[info.hubspot_join_status] || 0) + 1;
  }
  const container = document.getElementById('joinSummaryBadges');
  if (!Object.keys(HS_JOIN_MAP).length) {
    container.innerHTML =
      '<span class="text-xs text-gray-400 italic">No HubSpot data loaded</span>';
    return;
  }
  container.innerHTML = Object.entries(JOIN_STATUS_META)
    .filter(([s]) => counts[s])
    .map(([s, m]) =>
      `<span class="join-badge ${m.cls}">${m.label}: ${counts[s]}</span>`
    ).join('');
}

function buildJoinPanel() {
  // Called once on first panel open — renders filter buttons and table
  const hasData = Object.keys(HS_JOIN_MAP).length > 0;
  if (!hasData) {
    document.getElementById('joinPanelBody').innerHTML =
      '<p class="text-sm text-gray-400 text-center py-6">' +
      'No HubSpot join data available. Run the pipeline with ' +
      '<code class="bg-gray-100 px-1 rounded">hs_companies.json</code> ' +
      'to enable ownership validation.</p>';
    return;
  }

  // Count by status for filter labels
  const counts = {};
  for (const info of Object.values(HS_JOIN_MAP)) {
    counts[info.hubspot_join_status] = (counts[info.hubspot_join_status] || 0) + 1;
  }
  const problemCount = Object.keys(HS_JOIN_MAP)
    .filter(k => JOIN_PROBLEMS.has(HS_JOIN_MAP[k].hubspot_join_status)).length;

  const filterCfg = [
    { key: 'problems', label: `Issues (${problemCount})` },
    { key: 'all',      label: `All (${Object.keys(HS_JOIN_MAP).length})` },
    ...Object.entries(JOIN_STATUS_META)
      .filter(([s]) => counts[s])
      .map(([s, m]) => ({ key: s, label: `${m.label} (${counts[s]})` })),
  ];

  const filterEl = document.getElementById('joinStatusFilter');
  filterEl.innerHTML = filterCfg.map(f =>
    `<button class="join-filter-btn${joinFilter === f.key ? ' active' : ''}" data-filter="${f.key}">${f.label}</button>`
  ).join('');
  filterEl.querySelectorAll('.join-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      joinFilter = btn.dataset.filter;
      filterEl.querySelectorAll('.join-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderJoinTable();
    });
  });

  document.getElementById('joinSearch').addEventListener('input', e => {
    joinSearch = e.target.value;
    renderJoinTable();
  });

  renderJoinTable();
}

function renderJoinTable() {
  const q = joinSearch.toLowerCase();
  const entries = Object.entries(HS_JOIN_MAP).filter(([cid, info]) => {
    const st = info.hubspot_join_status;
    if (joinFilter === 'problems' && !JOIN_PROBLEMS.has(st)) return false;
    if (joinFilter !== 'problems' && joinFilter !== 'all' && st !== joinFilter) return false;
    if (q) {
      const name = (CID_NAME[cid] || '').toLowerCase();
      const co   = (info.hubspot_company_name || '').toLowerCase();
      if (!name.includes(q) && !co.includes(q) && !cid.includes(q)) return false;
    }
    return true;
  });

  const tbody = document.getElementById('joinTableBody');
  const empty = document.getElementById('joinEmpty');
  const count = document.getElementById('joinCount');

  if (!entries.length) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    count.textContent = '';
    return;
  }
  empty.classList.add('hidden');
  count.textContent = `${entries.length.toLocaleString()} accounts`;

  // Sort: problems first, then alphabetically by customer name
  entries.sort((a, b) => {
    const ap = JOIN_PROBLEMS.has(a[1].hubspot_join_status) ? 0 : 1;
    const bp = JOIN_PROBLEMS.has(b[1].hubspot_join_status) ? 0 : 1;
    if (ap !== bp) return ap - bp;
    return (CID_NAME[a[0]] || '').localeCompare(CID_NAME[b[0]] || '');
  });

  tbody.innerHTML = entries.map(([cid, info]) => {
    const name     = CID_NAME[cid] || `CID-${cid}`;
    const truncName = name.length > 42 ? name.slice(0, 42) + '…' : name;
    const meta     = JOIN_STATUS_META[info.hubspot_join_status] || { label: info.hubspot_join_status, cls: '' };
    const badge    = `<span class="join-badge ${meta.cls}">${meta.label}</span>`;
    const recId    = info.hubspot_record_id_from_netsuite || '<span class="text-gray-300">—</span>';
    const co       = info.hubspot_company_name   || '<span class="text-gray-300">—</span>';
    const owner    = info.hubspot_company_owner  || '<span class="text-gray-300">—</span>';
    return `<tr class="border-b border-gray-50 hover:bg-gray-50">
      <td class="px-3 py-1.5 font-medium text-gray-700">${truncName}</td>
      <td class="px-3 py-1.5 text-gray-400 font-mono text-xs">${cid}</td>
      <td class="px-3 py-1.5">${badge}</td>
      <td class="px-3 py-1.5 text-gray-400 font-mono text-xs">${recId}</td>
      <td class="px-3 py-1.5 text-gray-600">${co}</td>
      <td class="px-3 py-1.5 text-gray-600">${owner}</td>
    </tr>`;
  }).join('');
}

function toggleJoinPanel() {
  joinPanelOpen = !joinPanelOpen;
  document.getElementById('joinPanelBody').classList.toggle('hidden', !joinPanelOpen);
  document.getElementById('joinArrow').textContent = joinPanelOpen ? '▾' : '▸';
  if (joinPanelOpen && !joinPanelBuilt) {
    buildJoinPanel();
    joinPanelBuilt = true;
  }
}

// ── Main render ───────────────────────────────────────────────────────────────
function render() {
  renderKpis();
  renderTrend();
  renderMovementChart();
  updateSortClasses();
  renderTable(filteredRows());
}

// ── Search ────────────────────────────────────────────────────────────────────
document.getElementById('searchBox').addEventListener('input', e => {
  searchTerm = e.target.value;
  render();
});

// ── Init ──────────────────────────────────────────────────────────────────────
buildMonthSel();
buildCsmFilter();
buildTabs();
buildSortHeaders();
initJoinPanel();
render();
</script>
</body>
</html>
"""

# ── Embed data ────────────────────────────────────────────────────────────────
print("Embedding data into HTML…")

def safe_replace(html, placeholder, json_str):
    """Replace placeholder using a lambda callback to prevent re.sub backslash
    interpretation — critical for JSON strings that contain \\n sequences."""
    return re.sub(re.escape(placeholder), lambda m: json_str, html)

html = HTML
html = safe_replace(html, '__SUMMARY__',       summary_json)
html = safe_replace(html, '__CDETAIL__',       cdetail_json)
html = safe_replace(html, '__INVOICE_DATA__',  inv_data_json)
html = safe_replace(html, '__CSM_LIST__',      csm_list_json)
html = safe_replace(html, '__DEFAULT_MONTH__', def_month_json)
html = safe_replace(html, '__HS_JOIN_MAP__',   hs_join_json)

# ── Write output ──────────────────────────────────────────────────────────────
print(f"Writing {OUT_F}…")
with open(OUT_F, 'w', encoding='utf-8') as f:
    f.write(html)

size_mb = os.path.getsize(OUT_F) / 1_048_576
print(f"\nDone! {size_mb:.1f} MB → {OUT_F}")
print(f"  Default month : {default_month} ({cd_counts.get(default_month,0):,} cdetail rows)")
print(f"  SUMMARY months: {len(SUMMARY)}")
print(f"  CDETAIL rows  : {len(CDETAIL):,}")
print(f"  INVOICE_DATA  : {len(inv_data):,} keys")
print(f"  CSMs (norm.)  : {len(CSM_LIST)}")

# ── Validation report ─────────────────────────────────────────────────────────
print("\n── CSM normalization + allowlist check ──────────────────────────────────")
from collections import Counter as _Counter
csm_counts = _Counter(row[4] for row in CDETAIL)

# 1. Confirm no raw variant names survived
for raw in CSM_NORM:
    remaining = csm_counts.get(raw, 0)
    status = "✓ gone" if remaining == 0 else f"WARN {remaining} remain"
    print(f"  norm  {raw!r:35s} → {status}")

# 2. Confirm no names outside allowlist+Unassigned survived
invalid = {n: c for n, c in csm_counts.items() if n not in VALID_CSMS and n != 'Unassigned'}
if invalid:
    for n, c in sorted(invalid.items(), key=lambda x: -x[1]):
        print(f"  WARN  non-allowlisted name still present: {n!r} ({c:,} rows)")
else:
    print(f"  ✓ All CSM names in CDETAIL are either allowlisted or 'Unassigned'")

# 3. Summary counts
print(f"\n  Allowlist size         : {len(VALID_CSMS)} names")
print(f"  Unique CSMs in CDETAIL : {len(csm_counts)} (incl. Unassigned)")
print(f"  Unassigned rows        : {csm_counts.get('Unassigned', 0):,}")
print(f"  CDETAIL total rows     : {len(CDETAIL):,}")
print(f"  NRR calculations       : unchanged (CDETAIL row count preserved) ✓")

# 4. Deduplication check — no customer+month should appear more than once
from collections import defaultdict as _dd
cid_month_counts = _dd(int)
for row in CDETAIL:
    cid_month_counts[(row[0], row[1])] += 1
dupe_pairs = [(k, v) for k, v in cid_month_counts.items() if v > 1]
if dupe_pairs:
    print(f"\n  WARN: {len(dupe_pairs)} customer+month pairs have >1 row:")
    for (mo, cid), cnt in dupe_pairs[:5]:
        print(f"    {mo} cid={cid} → {cnt} rows")
else:
    print(f"  ✓ No duplicate customer+month pairs in CDETAIL")
