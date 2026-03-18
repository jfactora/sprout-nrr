"""
nrr_pipeline_v2.py
Compute covered-month MRR allocations and NRR metrics from raw invoice data.

Key rules:
  - Recurring lines : amortize across coverage_start → coverage_end
  - True-up lines   : recognize 100% in the invoice month ONLY (no amortization)
  - One-time lines  : excluded from MRR
  - New clients     : movement = 'new' for first revenue month; excluded from NRR
                      denominator until month 2
  - True-ups        : included in total MRR and NRR per COO guidance
  - Movement        : driven by recurring_delta (not total_delta) so true-up
                      volatility doesn't inflate expansion/contraction counts

Outputs:
  nrr_allocated_lines.json   — one row per covered-month per invoice line
  nrr_summary_v2.json        — SUMMARY + CDETAIL (14-field rows)

CDETAIL row format (14 fields):
  [month, cid, name, csm_id, csm_name,
   begin_mrr, end_mrr, delta, movement, raw_owner,
   prev_rec, curr_rec, prev_tu, curr_tu]
"""
import json, os, re
from collections import defaultdict, Counter
from datetime import date, datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
# NRR_OUTPUT_DIR: set this env var to write nrr_summary_v2.json elsewhere
# e.g. export NRR_OUTPUT_DIR=/path/to/sprout-nrr/data
OUT_DIR   = os.environ.get('NRR_OUTPUT_DIR', BASE)
os.makedirs(OUT_DIR, exist_ok=True)
RAW_F     = os.path.join(BASE, 'nrr_raw_invoices.json')
ALLOC_F   = os.path.join(BASE, 'nrr_allocated_lines.json')
SUMM_F    = os.path.join(OUT_DIR, 'nrr_summary_v2.json')
HS_F         = os.path.join(BASE, 'hs_companies.json')   # HubSpot company export (hs_build.py)
NS_HS_ID_MAP_F = os.path.join(BASE, 'ns_hs_id_map.json') # NS customer_id → HubSpot record ID
HS_JOIN_F    = os.path.join(BASE, 'hs_join_map.json')   # output: per-customer join results

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_COVERAGE_MONTHS  = 36   # cap anomalously long contracts
GAP_TOLERANCE_MONTHS = 3    # months gap before a returning customer is "reactivated"

# ── Module map  (item_id → display name) ─────────────────────────────────────
MODULE_MAP = {
    13: 'HR & Payroll', 17: 'HR & Payroll', 18: 'HR & Payroll',
    19: 'HR & Payroll', 20: 'HR & Payroll', 25: 'HRO',
    21: 'HRO', 149: 'HRO', 150: 'HRO', 274: 'HRO',
    356: 'HRO', 1166: 'HRO', 1168: 'HRO', 1870: 'HRO',
    27: 'Insight',
    118: 'Performance+',
    593: 'Peoplebox', 1269: 'Peoplebox',
    156: 'Instawage',
    22: 'Mobile',
    23: 'Attendance (Bundy)', 165: 'Attendance (Bundy)',
    28: 'Pulse',
    29: 'Recruit',
    30: 'Gov', 565: 'Gov',
    117: 'Wellness',
    124: 'BenAd', 668: 'BenAd',
    145: 'JazzHR',
    146: 'Olivia', 303: 'Olivia',
    147: 'Benchmark',
    148: 'Manatal',
    160: 'Geotagging',
    589: 'API',
    569: 'Disprz',
    168: 'HR & Payroll', 125: 'HR & Payroll', 275: 'HR & Payroll',
    765: 'HR & Payroll', 966: 'HR & Payroll', 2170: 'HR & Payroll',
    2270: 'HR & Payroll', 2271: 'HR & Payroll', 2272: 'HR & Payroll',
    169: 'True-up',
}
MODULE_DEFAULT = 'Other'

# ── CSM normalization + allowlist ─────────────────────────────────────────────
CSM_NORM = {
    'Ma. Rexelle Estacio': 'Rexelle Estacio',
    'Ma Rexelle Estacio':  'Rexelle Estacio',
    'Krystel Maano':       'Krystel Maaño',
    'Wil  Luna':           'Wil Luna',
    'Lucky Lyne Penalosa': 'Lucky Lyne Peñalosa',
    'Lucky Peñalosa':      'Lucky Lyne Peñalosa',
    'RIEZHEL PUNZALAN':    'Riezhel Punzalan',
}

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
    cleaned   = ' '.join((name or '').split())
    canonical = CSM_NORM.get(cleaned, cleaned)
    return canonical if canonical in VALID_CSMS else 'Unassigned'

# ── Month helpers ─────────────────────────────────────────────────────────────
def month_add(ym: str, n: int) -> str:
    """Add n months to a YYYY-MM string."""
    y, m = map(int, ym.split('-'))
    total = y * 12 + (m - 1) + n
    return f'{total // 12:04d}-{(total % 12) + 1:02d}'

def month_diff(ym1: str, ym2: str) -> int:
    """Signed number of months from ym1 to ym2."""
    y1, m1 = map(int, ym1.split('-'))
    y2, m2 = map(int, ym2.split('-'))
    return (y2 - y1) * 12 + (m2 - m1)

def invoice_to_month(date_str: str) -> str:
    """Convert 'm/d/yyyy' or 'yyyy-mm-dd' invoice date to 'YYYY-MM'."""
    s = str(date_str).strip()
    if '/' in s:
        parts = s.split('/')
        m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        return f'{y:04d}-{m:02d}'
    if '-' in s:
        return s[:7]
    raise ValueError(f'Unrecognised date format: {date_str!r}')

def _s(v):
    """Sanitize string — collapse all whitespace/control characters."""
    return ' '.join(str(v or '').split())

# ── Step 1 : Build allocations ────────────────────────────────────────────────
def build_allocations(raw: list):
    """
    Produce one allocation row per covered month per invoice line.

    True-up rule (NEW):
      - Always allocate to invoice month only (months_covered = 1)
      - Do NOT use raw coverage_start / coverage_end
      - This prevents multi-year amortisation from bad source data

    Recurring rule:
      - Use raw coverage_start / coverage_end, capped at MAX_COVERAGE_MONTHS
    """
    allocs = []
    tu_bad_raw = []   # true-ups whose raw data had multi-month coverage (for validation)

    for row in raw:
        cls = (row.get('classification') or '').strip()
        if cls == 'one_time':
            continue

        amount = float(row.get('amount') or 0)
        rt     = 't' if cls == 'true_up' else 'r'
        module = MODULE_MAP.get(int(row.get('item_id') or 0), MODULE_DEFAULT)
        csm    = norm_csm(row.get('csm_name') or '')
        inv_month = invoice_to_month(row['invoice_date'])

        if cls == 'true_up':
            # ── True-up: single invoice-month allocation ──────────────────────
            raw_cs = row.get('coverage_start', '')
            raw_ce = row.get('coverage_end', '')
            if raw_cs and raw_ce and raw_cs != raw_ce:
                tu_bad_raw.append({
                    'invoice_number': row['invoice_number'],
                    'raw_cs': raw_cs, 'raw_ce': raw_ce,
                    'amount': amount,
                })

            allocs.append({
                'customer_id':             row['customer_id'],
                'customer_name':           _s(row['customer_name']),
                'csm_id':                  row.get('csm_id'),
                'csm_name':                csm,
                'invoice_number':          _s(row['invoice_number']),
                'invoice_date':            _s(row['invoice_date']),
                'description':             _s(row['description']),
                'module':                  module,
                'classification':          cls,
                'rt':                      rt,
                'payment_status':          'N/A',
                'line_amount':             amount,
                'coverage_start':          inv_month,
                'coverage_end':            inv_month,
                'months_covered':          1,
                'covered_month':           inv_month,
                'monthly_allocated_amount': amount,
            })

        else:
            # ── Recurring: amortise over coverage span ────────────────────────
            raw_cs = (row.get('coverage_start') or '').strip()
            raw_ce = (row.get('coverage_end')   or '').strip()

            if not raw_cs or not raw_ce:
                raw_cs = inv_month
                raw_ce = inv_month

            span   = month_diff(raw_cs, raw_ce) + 1
            months = min(max(span, 1), MAX_COVERAGE_MONTHS)
            ce     = month_add(raw_cs, months - 1)
            mo_amt = amount / months if months > 0 else amount

            for i in range(months):
                allocs.append({
                    'customer_id':             row['customer_id'],
                    'customer_name':           _s(row['customer_name']),
                    'csm_id':                  row.get('csm_id'),
                    'csm_name':                csm,
                    'invoice_number':          _s(row['invoice_number']),
                    'invoice_date':            _s(row['invoice_date']),
                    'description':             _s(row['description']),
                    'module':                  module,
                    'classification':          cls,
                    'rt':                      rt,
                    'payment_status':          'N/A',
                    'line_amount':             amount,
                    'coverage_start':          raw_cs,
                    'coverage_end':            ce,
                    'months_covered':          months,
                    'covered_month':           month_add(raw_cs, i),
                    'monthly_allocated_amount': mo_amt,
                })

    return allocs, tu_bad_raw

# ── Step 2 : Build per-client per-month MRR ───────────────────────────────────
def build_client_month_mrr(allocs: list):
    """
    Returns:
      cmm_rec  {cid: {month: recurring_mrr}}
      cmm_tu   {cid: {month: trueup_mrr}}
      csm_map  {cid: (csm_id, csm_name)}   latest assignment per customer
      name_map {cid: customer_name}
    """
    cmm_rec  = defaultdict(lambda: defaultdict(float))
    cmm_tu   = defaultdict(lambda: defaultdict(float))
    csm_map  = {}
    name_map = {}

    for row in allocs:
        cid   = row['customer_id']
        month = row['covered_month']
        amt   = row['monthly_allocated_amount']

        if row['rt'] == 't':
            cmm_tu[cid][month] += amt
        else:
            cmm_rec[cid][month] += amt

        # Keep latest CSM per customer (last write wins — sorted by allocs order)
        csm_map[cid]  = (row.get('csm_id'), row['csm_name'])
        name_map[cid] = row['customer_name']

    return cmm_rec, cmm_tu, csm_map, name_map

# ── Step 3 : Build CDETAIL ────────────────────────────────────────────────────
def build_cdetail(cmm_rec, cmm_tu, csm_map, name_map):
    """
    Produce one CDETAIL row per customer per active month.

    CDETAIL row (14 fields):
      [month, cid, name, csm_id, csm_name,
       begin_mrr, end_mrr, delta, movement, raw_owner,
       prev_rec, curr_rec, prev_tu, curr_tu]

    Movement classification uses recurring_delta (not total_delta):
      1. Churn        — end_mrr == 0 and begin_mrr > 0
      2. New          — first revenue month
      3. Reactivated  — prev_mrr == 0 and gap > GAP_TOLERANCE_MONTHS
      4. Expansion    — recurring_delta > 0
      5. Contraction  — recurring_delta < 0
      6. Retained     — recurring_delta == 0 (may still have true-up movement)
    """
    today_month = date.today().strftime('%Y-%m')

    # Collect all months each customer had any MRR
    cid_months = defaultdict(set)
    for cid, months in cmm_rec.items():
        cid_months[cid].update(months.keys())
    for cid, months in cmm_tu.items():
        cid_months[cid].update(months.keys())

    # First revenue month per customer
    first_revenue_month = {
        cid: min(months) for cid, months in cid_months.items()
    }

    rows = []

    for cid, months in cid_months.items():
        csm_id, csm_name = csm_map.get(cid, (None, 'Unassigned'))
        name             = name_map.get(cid, f'CID-{cid}')
        raw_owner        = csm_name
        frm              = first_revenue_month[cid]
        sorted_months    = sorted(months)

        # Track last active month for reactivation detection
        last_active = None

        for month in sorted_months:
            curr_rec = cmm_rec[cid].get(month, 0.0)
            curr_tu  = cmm_tu[cid].get(month, 0.0)
            curr_mrr = curr_rec + curr_tu

            prev_month = month_add(month, -1)
            prev_rec   = cmm_rec[cid].get(prev_month, 0.0)
            prev_tu    = cmm_tu[cid].get(prev_month, 0.0)
            prev_mrr   = prev_rec + prev_tu

            begin_mrr      = prev_mrr
            end_mrr        = curr_mrr
            delta          = end_mrr - begin_mrr
            rec_delta      = curr_rec - prev_rec

            # ── Movement classification ───────────────────────────────────────
            if begin_mrr > 0 and end_mrr == 0:
                movement = 'churned'
            elif month == frm:
                movement = 'new'
            elif begin_mrr == 0 and end_mrr > 0:
                if last_active is not None and month_diff(last_active, month) > GAP_TOLERANCE_MONTHS:
                    movement = 'reactivated'
                else:
                    movement = 'new'   # treat short-gap return as new (insufficient history)
            elif rec_delta > 0:
                movement = 'expansion'
            elif rec_delta < 0:
                movement = 'contraction'
            else:
                movement = 'retained'

            rows.append([
                month,
                cid,
                name,
                csm_id,
                csm_name,
                round(begin_mrr, 2),
                round(end_mrr,   2),
                round(delta,     2),
                movement,
                raw_owner,
                round(prev_rec,  2),   # index 10
                round(curr_rec,  2),   # index 11
                round(prev_tu,   2),   # index 12
                round(curr_tu,   2),   # index 13
            ])

            if end_mrr > 0:
                last_active = month

        # ── Emit churn row if customer was active but has no entry for next month ──
        if sorted_months:
            last_month = sorted_months[-1]
            last_rec   = cmm_rec[cid].get(last_month, 0.0)
            last_tu    = cmm_tu[cid].get(last_month, 0.0)
            last_total = last_rec + last_tu

            if last_total > 0:
                next_month = month_add(last_month, 1)
                # Only emit churn row if next_month is not in the future beyond today
                if next_month <= today_month and next_month not in months:
                    rows.append([
                        next_month, cid, name, csm_id, csm_name,
                        round(last_total, 2),   # begin
                        0.0,                    # end
                        round(-last_total, 2),  # delta
                        'churned',
                        raw_owner,
                        round(last_rec, 2),     # prev_rec  (was the last month's rec)
                        0.0,                    # curr_rec
                        round(last_tu,  2),     # prev_tu
                        0.0,                    # curr_tu
                    ])

    rows.sort(key=lambda r: (r[0], r[1]))
    return rows

# ── Step 4 : Build monthly SUMMARY ───────────────────────────────────────────
def build_summary(cdetail: list) -> list:
    """
    Aggregate CDETAIL rows into one SUMMARY dict per month.

    NRR formula:
      begin_mrr = sum of begin_mrr for expansion + contraction + churned + retained
      ending_mrr = begin_mrr + Σexpansion + Σcontraction + Σchurn
      nrr_pct = ending_mrr / begin_mrr * 100
    """
    by_month = defaultdict(list)
    for row in cdetail:
        by_month[row[0]].append(row)

    summary = []
    for month in sorted(by_month):
        rows = by_month[month]

        begin_mrr            = 0.0
        new_mrr              = 0.0
        expansion            = 0.0
        contraction          = 0.0
        churn                = 0.0
        reactivated_mrr      = 0.0
        insuff_history_mrr   = 0.0
        total_mrr            = 0.0

        for r in rows:
            mv   = r[8]
            beg  = r[5]
            end  = r[6]
            dlt  = r[7]
            total_mrr += end

            if mv == 'new':
                new_mrr += end
            elif mv == 'reactivated':
                reactivated_mrr += end
            elif mv == 'expansion':
                begin_mrr += beg
                expansion += dlt
            elif mv == 'contraction':
                begin_mrr += beg
                contraction += dlt
            elif mv == 'churned':
                begin_mrr += beg
                churn += dlt         # negative
            elif mv == 'retained':
                begin_mrr += beg
                # delta adds to ending_mrr indirectly (delta≈0 for pure flat,
                # but can be nonzero if true-up changed — still counted in ending)
                expansion += max(dlt, 0)       # true-up growth → expansion bucket
                contraction += min(dlt, 0)     # true-up loss → contraction bucket

        ending_mrr = begin_mrr + expansion + contraction + churn
        nrr_pct    = round(ending_mrr / begin_mrr * 100, 2) if begin_mrr > 0 else None

        summary.append({
            'month':                    month,
            'begin_mrr':                round(begin_mrr,          2),
            'new_mrr':                  round(new_mrr,            2),
            'expansion':                round(expansion,          2),
            'contraction':              round(contraction,        2),
            'churn':                    round(churn,              2),
            'reactivated_mrr':          round(reactivated_mrr,   2),
            'insufficient_history_mrr': round(insuff_history_mrr, 2),
            'ending_mrr':               round(ending_mrr,         2),
            'total_mrr':                round(total_mrr,          2),
            'nrr_pct':                  nrr_pct,
        })

    return summary

# ── Step 5 : Validation helpers ───────────────────────────────────────────────
def validate(allocs, tu_bad_raw, cdetail):
    print('\n── True-up allocation validation ────────────────────────────────────────')

    # All true-up rows must have months_covered == 1
    tu_allocs = [r for r in allocs if r['rt'] == 't']
    bad_tu    = [r for r in tu_allocs if r['months_covered'] != 1]
    if bad_tu:
        print(f'  FAIL: {len(bad_tu)} true-up rows have months_covered > 1:')
        for r in bad_tu[:5]:
            print(f'    {r["invoice_number"]} months={r["months_covered"]}')
    else:
        print(f'  ✓  All {len(tu_allocs):,} true-up rows have months_covered = 1')

    if tu_bad_raw:
        print(f'\n  Note: {len(tu_bad_raw)} true-up invoices had multi-month raw coverage')
        print(f'  (overridden to invoice month — these are now correct):')
        for b in sorted(tu_bad_raw, key=lambda x: -x['amount'])[:10]:
            print(f'    {b["invoice_number"]}  raw {b["raw_cs"]}→{b["raw_ce"]}  '
                  f'amt={b["amount"]:,.0f}')

    print('\n── CDETAIL validation ───────────────────────────────────────────────────')
    movements = Counter(r[8] for r in cdetail)
    print(f'  Movements: {dict(sorted(movements.items()))}')
    dups = Counter((r[0], r[1]) for r in cdetail)
    bad_dups = [(k, v) for k, v in dups.items() if v > 1]
    if bad_dups:
        print(f'  WARN: {len(bad_dups)} duplicate customer+month pairs')
    else:
        print(f'  ✓  No duplicate customer+month pairs')

    print(f'\n  Total CDETAIL rows : {len(cdetail):,}')
    print(f'  Unique customers   : {len({r[1] for r in cdetail}):,}')

# ── Step 2b : HubSpot join map ────────────────────────────────────────────────
# NS IDs to trace verbosely through the join — add any ID you want to debug.
HS_DEBUG_IDS = {'12961'}

def _norm_ns_id(raw) -> str:
    """Normalize a NetSuite ID to a plain integer string."""
    s = str(raw or '').strip()
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s


_NORM_NAME_SUFFIXES = [
    ', INC.', ', INC', ' INC.', ' INC',
    ', CORP.', ', CORP', ' CORP.', ' CORP',
    ', LTD.', ', LTD', ' LTD',
    ', LLC', ' LLC',
    ', CO., LTD', ', CO.', ' CO.',
    ', OPC', ' OPC',
    ' PHILIPPINES', ' PHILS.', ' PHILS', ' PHIL.',
    ', THE',
]


def _norm_name(raw: str) -> str:
    """Normalize a company name for fuzzy matching.

    Uppercases, strips legal suffixes and punctuation so that
    'Knack Global Philippines, Inc.' matches 'KNACK GLOBAL'.
    """
    n = (raw or '').upper().strip()
    for suf in _NORM_NAME_SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)].rstrip(', ')
    n = re.sub(r'[^A-Z0-9 ]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def build_hs_join_map(name_map, ns_hs_id_map, hs_by_hs_id):
    """
    Build a per-customer HubSpot join validation map.

    Join key: NetSuite.customer_id → ns_hs_id_map → hubspot_record_id → hs_by_hs_id

    Architecture:
      NetSuite customer  →  HubSpot Record ID stored in NetSuite (custentitycustentity16)
                         →  HubSpot company record (matched by record ID)
                         →  HubSpot Company owner  →  csm_name

    Parameters:
      name_map      {customer_id: company_name}      NS customers (for display / debug)
      ns_hs_id_map  {str(customer_id): str(hs_id)}  from ns_hs_id_map.json
      hs_by_hs_id   {str(hubspot_id): co_dict}       from hs_companies.json

    Join statuses:
      matched                              — HS record found, Company owner resolved
      matched_no_owner                     — HS record found, Company owner is blank
      missing_hubspot_record_id_in_netsuite — NS customer has no HS Record ID stored
      no_hubspot_match_for_record_id       — HS Record ID not found in hs_companies.json

    Each join_map entry includes these validation fields:
      hubspot_record_id_from_netsuite  — raw HS ID stored in NS (or '' if absent)
      matched_hubspot_record_id        — ID of the matched HS company (or None)
      hubspot_company_name             — matched HS company name (or None)
      hubspot_company_owner            — resolved HS Company owner full name (or None)
      ns_company_name                  — NS customer name (for display)

    Returns:
      join_map  {str(cid): {validation fields above}}
      hs_stats  {str: int/float}  counters + hubspot_coverage_rate
    """
    join_map = {}
    for cid, ns_company_name in name_map.items():
        key          = str(cid)
        hs_record_id = ns_hs_id_map.get(key, '').strip()

        if not hs_record_id:
            join_map[key] = {
                'hubspot_join_status':             'missing_hubspot_record_id_in_netsuite',
                'hubspot_record_id_from_netsuite': '',
                'matched_hubspot_record_id':       None,
                'hubspot_company_name':            None,
                'hubspot_company_owner':           None,
                'ns_company_name':                 ns_company_name,
            }
        elif hs_record_id not in hs_by_hs_id:
            join_map[key] = {
                'hubspot_join_status':             'no_hubspot_match_for_record_id',
                'hubspot_record_id_from_netsuite': hs_record_id,
                'matched_hubspot_record_id':       None,
                'hubspot_company_name':            None,
                'hubspot_company_owner':           None,
                'ns_company_name':                 ns_company_name,
            }
        else:
            co      = hs_by_hs_id[hs_record_id]
            co_name = _s(co.get('company_name') or '') or None
            owner   = _s(co.get('owner_name')   or '') or None
            join_map[key] = {
                'hubspot_join_status':             'matched' if owner else 'matched_no_owner',
                'hubspot_record_id_from_netsuite': hs_record_id,
                'matched_hubspot_record_id':       hs_record_id,
                'hubspot_company_name':            co_name,
                'hubspot_company_owner':           owner,
                'ns_company_name':                 ns_company_name,
            }

    status_counts = Counter(v['hubspot_join_status'] for v in join_map.values())
    matched       = status_counts.get('matched', 0)
    total         = len(name_map)
    coverage_rate = matched / total * 100 if total else 0.0

    hs_stats = {
        'total_ns_customers':      total,
        'total_hs_companies':      len(hs_by_hs_id),
        'hubspot_coverage_rate':   round(coverage_rate, 2),
        **status_counts,
    }
    return join_map, hs_stats


def build_hs_join_map_by_name(name_map, hs_by_norm_name):
    """
    Name-based fallback join — used when ns_hs_id_map.json is unavailable.

    Joins NetSuite customer name → _norm_name() → HubSpot company name.
    Same output structure as build_hs_join_map so downstream code is shared.

    Join statuses:
      matched          — name matched, Company owner resolved
      matched_no_owner — name matched, Company owner is blank
      no_name_match    — normalized name not found in HubSpot
    """
    join_map = {}
    for cid, ns_company_name in name_map.items():
        key = str(cid)
        nn  = _norm_name(ns_company_name)
        co  = hs_by_norm_name.get(nn)

        if co is None:
            join_map[key] = {
                'hubspot_join_status':             'no_name_match',
                'hubspot_record_id_from_netsuite': '',
                'matched_hubspot_record_id':       None,
                'hubspot_company_name':            None,
                'hubspot_company_owner':           None,
                'ns_company_name':                 ns_company_name,
            }
        else:
            owner   = _s(co.get('owner_name')   or '') or None
            co_name = _s(co.get('company_name') or '') or None
            hs_id   = str(co.get('hubspot_id', '') or '')
            join_map[key] = {
                'hubspot_join_status':             'matched' if owner else 'matched_no_owner',
                'hubspot_record_id_from_netsuite': hs_id,
                'matched_hubspot_record_id':       hs_id or None,
                'hubspot_company_name':            co_name,
                'hubspot_company_owner':           owner,
                'ns_company_name':                 ns_company_name,
            }

    status_counts = Counter(v['hubspot_join_status'] for v in join_map.values())
    matched       = status_counts.get('matched', 0)
    total         = len(name_map)
    coverage_rate = matched / total * 100 if total else 0.0

    hs_stats = {
        'total_ns_customers':    total,
        'total_hs_companies':    len(hs_by_norm_name),
        'hubspot_coverage_rate': round(coverage_rate, 2),
        **status_counts,
    }
    return join_map, hs_stats


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('Loading raw invoices…')
    with open(RAW_F) as f:
        raw = json.load(f)
    print(f'  {len(raw):,} raw invoice lines')
    cls_counts = Counter(r.get('classification','') for r in raw)
    print(f'  Classifications: {dict(cls_counts)}')

    # ── Step 1: allocations ───────────────────────────────────────────────────
    print('\nBuilding allocations…')
    allocs, tu_bad_raw = build_allocations(raw)
    print(f'  {len(allocs):,} allocation rows')
    tu_count  = sum(1 for r in allocs if r['rt'] == 't')
    rec_count = sum(1 for r in allocs if r['rt'] == 'r')
    print(f'  Recurring: {rec_count:,}   True-up: {tu_count:,}')

    # ── Step 2: MRR by client / month ─────────────────────────────────────────
    print('\nBuilding client-month MRR…')
    cmm_rec, cmm_tu, csm_map, name_map = build_client_month_mrr(allocs)
    print(f'  {len(cmm_rec):,} customers with recurring MRR')
    print(f'  {len(cmm_tu):,} customers with true-up MRR')

    # ── Step 2b: HubSpot join ─────────────────────────────────────────────────
    # Primary (ID-based): NS.customer_id → ns_hs_id_map → hubspot_record_id → HS company
    # Fallback (name-based): used when ns_hs_id_map.json is unavailable
    # HubSpot is the ONLY source of CSM assignment. NetSuite csm_name is never used.
    hs_join_map = {}
    hs_missing  = not os.path.exists(HS_F)
    ns_missing  = not os.path.exists(NS_HS_ID_MAP_F)

    if hs_missing:
        print('\n  ERROR: hs_companies.json missing — run hs_build.py first.')
        print('  All accounts will be Unassigned until this file is present.')
        for cid in csm_map:
            csm_map[cid] = (csm_map[cid][0], 'Unassigned')
    else:
        print('\nLoading HubSpot companies…')
        with open(HS_F) as f:
            hs_companies = json.load(f)
        hs_by_hs_id = {
            str(co['hubspot_id']): co
            for co in hs_companies
            if co.get('hubspot_id')
        }
        print(f'  {len(hs_companies):,} total HS records, '
              f'{len(hs_by_hs_id):,} indexed by hubspot_id')

        if ns_missing:
            # ── Fallback: name-based join ────────────────────────────────────
            print('\n  WARN: ns_hs_id_map.json not found — using name-based join (fallback).')
            print('  To switch to ID-based join: node netsuite-mrr/ns_fetch_hs_ids.js')
            hs_by_norm_name = {
                _norm_name(co['company_name']): co
                for co in hs_companies
                if co.get('company_name')
            }
            hs_join_map, hs_stats = build_hs_join_map_by_name(name_map, hs_by_norm_name)
            join_mode = 'name-based (fallback)'
        else:
            # ── Primary: ID-based join ───────────────────────────────────────
            print('Loading NS → HubSpot Record ID map…')
            with open(NS_HS_ID_MAP_F) as f:
                ns_hs_raw = json.load(f)
            ns_hs_id_map = {
                str(r['customer_id']): str(r['hubspot_record_id']).strip()
                for r in ns_hs_raw
                if r.get('hubspot_record_id')
            }
            print(f'  {len(ns_hs_id_map):,} NS customers with a HubSpot Record ID')
            hs_join_map, hs_stats = build_hs_join_map(name_map, ns_hs_id_map, hs_by_hs_id)
            join_mode = 'ID-based'

        # ── Apply join results to csm_map (shared for both modes) ────────────
        str_to_cid   = {str(cid): cid for cid in csm_map}
        hs_overrides = 0
        norm_misses  = []

        for key, info in hs_join_map.items():
            cid = str_to_cid.get(key)
            if cid is None:
                continue
            csm_id = csm_map[cid][0]
            status = info['hubspot_join_status']

            if status == 'matched':
                raw_owner  = info['hubspot_company_owner'] or ''
                owner_norm = norm_csm(raw_owner)
                csm_map[cid] = (csm_id, owner_norm)
                hs_overrides += 1
                if owner_norm == 'Unassigned':
                    norm_misses.append((key, info['ns_company_name'], raw_owner))
            else:
                csm_map[cid] = (csm_id, 'Unassigned')

        # ── Coverage summary ──────────────────────────────────────────────────
        total_ns  = hs_stats['total_ns_customers']
        n_matched = hs_stats.get('matched', 0)
        cov_rate  = hs_stats['hubspot_coverage_rate']

        print(f'\n── HubSpot join — coverage summary ({join_mode}) ─────────────────────────')
        print(f'  {"total_ns_customers":<45s}: {total_ns:,}')
        print(f'  {"total_hs_companies":<45s}: {hs_stats["total_hs_companies"]:,}')
        print(f'  {"matched (owner assigned)":<45s}: {n_matched:,}')
        for status_key in ['matched_no_owner', 'no_name_match',
                           'missing_hubspot_record_id_in_netsuite',
                           'no_hubspot_match_for_record_id']:
            n = hs_stats.get(status_key, 0)
            if n:
                print(f'  {status_key:<45s}: {n:,}')
        print(f'  {"hubspot_coverage_rate":<45s}: {cov_rate:.1f}%')
        print(f'\n  HubSpot CSM assignments applied: {hs_overrides:,}')

        if norm_misses:
            print(f'\n  WARN: {len(norm_misses)} matched owners not in VALID_CSMS → Unassigned:')
            for ckey, ns_nm, raw in norm_misses[:20]:
                print(f'    cid={ckey}  {ns_nm!r:45s}  raw_owner={raw!r}')

        # ── Validation sample: 5 matched accounts ────────────────────────────
        sample_matched = [
            (k, v) for k, v in hs_join_map.items()
            if v['hubspot_join_status'] == 'matched'
        ][:5]
        if sample_matched:
            print('\n── Sample matched accounts ──────────────────────────────────────────────')
            print(f'  {"NS company name":<42s}  {"HS record ID":<14s}  '
                  f'{"HS company name":<32s}  HS Company owner')
            print(f'  {"─"*42}  {"─"*14}  {"─"*32}  {"─"*20}')
            for k, v in sample_matched:
                ns_nm     = v['ns_company_name'][:42]
                rec_id    = (v['hubspot_record_id_from_netsuite'] or '')
                co_nm     = (v['hubspot_company_name'] or '')[:32]
                owner     = v['hubspot_company_owner'] or ''
                cid_orig  = str_to_cid.get(k)
                final_csm = csm_map[cid_orig][1] if cid_orig else '?'
                print(f'  {ns_nm:<42s}  {rec_id:<14s}  {co_nm:<32s}  '
                      f'{owner:<25s}  → {final_csm}')

        # ── Debug: top 20 unmatched accounts ────────────────────────────────
        no_match_status = ('no_name_match' if ns_missing
                           else 'missing_hubspot_record_id_in_netsuite')
        no_match_rows = [
            (k, v['ns_company_name'])
            for k, v in hs_join_map.items()
            if v['hubspot_join_status'] == no_match_status
        ]
        no_match_rows.sort(key=lambda x: x[1].upper())
        print(f'\n── {no_match_status} — top 20 of {len(no_match_rows):,} ─────────')
        print(f'  {"cid":>6s}  {"NS company name"}')
        print(f'  {"─"*6}  {"─"*50}')
        for ckey, ns_nm in no_match_rows[:20]:
            print(f'  {ckey:>6s}  {ns_nm}')
        if len(no_match_rows) > 20:
            print(f'  … and {len(no_match_rows) - 20:,} more')

        print(f'\nWriting {HS_JOIN_F}…')
        with open(HS_JOIN_F, 'w') as f:
            json.dump(hs_join_map, f, separators=(',', ':'))
        print(f'  {os.path.getsize(HS_JOIN_F) / 1_024:.0f} KB')

    # ── Step 3: CDETAIL ───────────────────────────────────────────────────────
    print('\nBuilding CDETAIL…')
    cdetail = build_cdetail(cmm_rec, cmm_tu, csm_map, name_map)
    print(f'  {len(cdetail):,} CDETAIL rows')

    # ── Step 4: SUMMARY ───────────────────────────────────────────────────────
    print('\nBuilding SUMMARY…')
    summary = build_summary(cdetail)
    print(f'  {len(summary)} monthly summary rows')

    # ── Validation ────────────────────────────────────────────────────────────
    validate(allocs, tu_bad_raw, cdetail)

    # ── Write nrr_allocated_lines.json ────────────────────────────────────────
    print(f'\nWriting {ALLOC_F}…')
    with open(ALLOC_F, 'w') as f:
        json.dump(allocs, f, separators=(',', ':'))
    print(f'  {os.path.getsize(ALLOC_F)/1e6:.1f} MB')

    # ── Write nrr_summary_v2.json ─────────────────────────────────────────────
    # CDETAIL rows: convert to list of lists for compact storage
    print(f'\nWriting {SUMM_F}…')
    out = {
        'generated_at': date.today().isoformat(),
        'algorithm':    'coverage_month_allocation_v3_tu_fix',
        'monthly_nrr':  summary,
        'customer_detail': cdetail,
        'validation': {
            'total_raw_lines':      len(raw),
            'total_alloc_rows':     len(allocs),
            'total_cdetail_rows':   len(cdetail),
            'total_customers':      len(name_map),
            'tu_invoices_corrected': len(tu_bad_raw),
        },
    }
    with open(SUMM_F, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f'  {os.path.getsize(SUMM_F)/1e6:.1f} MB')

    # ── Spot-check March 2026 ─────────────────────────────────────────────────
    print('\n── March 2026 spot-check ────────────────────────────────────────────────')
    mar26 = [r for r in cdetail if r[0] == '2026-03']
    print(f'  CDETAIL rows  : {len(mar26):,}')
    s = next((s for s in summary if s['month'] == '2026-03'), None)
    if s:
        print(f'  begin_mrr     : {s["begin_mrr"]:>15,.2f}')
        print(f'  expansion     : {s["expansion"]:>15,.2f}')
        print(f'  contraction   : {s["contraction"]:>15,.2f}')
        print(f'  churn         : {s["churn"]:>15,.2f}')
        print(f'  ending_mrr    : {s["ending_mrr"]:>15,.2f}')
        print(f'  total_mrr     : {s["total_mrr"]:>15,.2f}')
        print(f'  nrr_pct       : {s["nrr_pct"]}%')
    # Top 5 by end MRR
    mar26_sorted = sorted(mar26, key=lambda r: r[6], reverse=True)
    print(f'\n  Top 5 by current MRR:')
    for r in mar26_sorted[:5]:
        print(f'    {r[2][:40]:40s}  {r[8]:12s}  '
              f'rec {r[11]:>10,.0f}  tu {r[13]:>10,.0f}  '
              f'end {r[6]:>12,.0f}')

    print('\nDone.')
