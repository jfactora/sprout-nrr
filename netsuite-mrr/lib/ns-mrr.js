/**
 * ns-mrr.js
 * MRR calculation from NetSuite invoice data.
 *
 * Flow:
 *   1. Fetch invoices matching the memo filter (recurring, renewal, revised,
 *      true-up, etc.) joined to the customer record for HubSpot ID + sub period.
 *   2. Fetch per-invoice qty from transactionline.
 *   3. Group by HubSpot Company ID.
 *   4. Per account: detect billing cadence → compute current MRR & starting MRR.
 */
'use strict';

const { suiteqlAll } = require('./ns-suiteql');

// ─── Queries ────────────────────────────────────────────────────────────────

/**
 * Returns all invoices matching memo keywords.
 * - foreigntotal − taxtotal  = invoice amount ex-tax
 * - REPLACE on custentitycustentity16 strips accidental commas
 * - BUILTIN.DF(custentity3)  = subscription period display value
 */
const INVOICE_SQL = `
SELECT
  t.id                                              AS invoice_id,
  t.tranid                                          AS invoice_number,
  TO_CHAR(t.trandate, 'YYYY-MM-DD')                 AS tran_date,
  t.entity                                          AS customer_id,
  c.companyname                                     AS company_name,
  REPLACE(c.custentitycustentity16, ',', '')        AS hubspot_company_id,
  BUILTIN.DF(c.custentity3)                         AS subscription_period,
  t.foreigntotal                                    AS foreign_total,
  t.taxtotal                                        AS tax_total,
  t.memo
FROM transaction t
JOIN customer c ON c.id = t.entity
WHERE t.abbrevtype = 'INV'
  AND t.voided = 'F'
  AND (
       LOWER(t.memo) LIKE '%recurring billing%'
    OR LOWER(t.memo) LIKE '%renewal%'
    OR LOWER(t.memo) LIKE '%revised%'
    OR LOWER(t.memo) LIKE '%true-up%'
    OR LOWER(t.memo) LIKE '%true up%'
    OR LOWER(t.memo) LIKE '%trueup%'
  )
ORDER BY t.entity, t.trandate
`.trim();

/**
 * Returns minimum absolute non-zero qty per invoice from non-mainline,
 * non-tax lines. Used as the billing-months divisor.
 */
function qtySQL(invoiceIds) {
  // SuiteQL IN list is capped at 1000; callers must chunk if needed
  const ids = invoiceIds.join(', ');
  return `
SELECT
  tl.transaction                    AS invoice_id,
  MIN(ABS(tl.quantity))             AS qty
FROM transactionline tl
WHERE tl.transaction IN (${ids})
  AND tl.mainline   = 'F'
  AND tl.istaxline  = 'F'
  AND tl.quantity  <> 0
GROUP BY tl.transaction
  `.trim();
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Check if a memo string looks like a true-up invoice. */
function isTrueUp(memo) {
  const m = (memo || '').toLowerCase();
  return m.includes('true-up') || m.includes('true up') || m.includes('trueup');
}

/** Check if this is a "Revised:" invoice (excluded from cadence calc). */
function isRevised(memo) {
  return /^revised[:\s]/i.test((memo || '').trim());
}

/**
 * Median of a numeric array (sorted in place).
 * Returns null for empty arrays.
 */
function median(arr) {
  if (!arr.length) return null;
  arr.sort((a, b) => a - b);
  const mid = Math.floor(arr.length / 2);
  return arr.length % 2 === 0 ? (arr[mid - 1] + arr[mid]) / 2 : arr[mid];
}

/**
 * Detect billing cadence (months) from a list of subscription invoices.
 *
 * Uses median gap between unique invoice dates (Revised: excluded).
 * Falls back to days-since-single-invoice for solo invoices.
 *
 * @param {object[]} subInvoices  Subscription (non-true-up) invoice rows
 * @returns {1|3|6|12}            Billing months per period
 */
function detectCadence(subInvoices) {
  // Unique dates from non-revised invoices, sorted ascending
  const dates = [
    ...new Set(
      subInvoices
        .filter(inv => !isRevised(inv.memo))
        .map(inv => inv.tran_date)
    ),
  ].sort();

  if (dates.length >= 2) {
    // Gaps in days between consecutive dates
    const gaps = [];
    for (let i = 1; i < dates.length; i++) {
      const diff =
        (new Date(dates[i]) - new Date(dates[i - 1])) / (1000 * 60 * 60 * 24);
      gaps.push(diff);
    }
    const med = median(gaps);
    if (med <= 45) return 1;
    if (med <= 105) return 3;
    if (med <= 195) return 6;
    return 12;
  }

  if (dates.length === 1) {
    // Single invoice — guess from days since that invoice
    const daysSince =
      (Date.now() - new Date(dates[0]).getTime()) / (1000 * 60 * 60 * 24);
    if (daysSince <= 45) return 1;
    if (daysSince <= 105) return 3;
    if (daysSince <= 195) return 6;
    return 12;
  }

  // No usable invoices — default to monthly
  return 1;
}

/**
 * Compute the MRR contribution from a single invoice row.
 *
 * @param {object} inv          Invoice row (with .foreign_total, .tax_total)
 * @param {Map}    qtyMap       invoice_id → qty from transactionline
 * @param {number} billingMonths Detected cadence (1/3/6/12)
 * @param {boolean} isTrueUpInv Override divisor to 3 if this is a true-up
 * @returns {number}
 */
function invoiceMrr(inv, qtyMap, billingMonths, isTrueUpInv = false) {
  // foreigntotal comes back as string — coerce before arithmetic
  const amount = Number(inv.foreign_total) - Number(inv.tax_total);
  const lineQty = qtyMap.get(String(inv.invoice_id)) || 0;
  const divisor = isTrueUpInv
    ? 3                                         // true-ups always /3
    : lineQty > 0 ? lineQty : billingMonths;    // use qty, else detected cadence
  return amount / divisor;
}

/**
 * Latest invoice in an array (by tran_date). Returns null if empty.
 */
function latestInvoice(invoices) {
  if (!invoices.length) return null;
  return invoices.reduce((best, inv) =>
    inv.tran_date > best.tran_date ? inv : best
  );
}

/**
 * Latest invoice dated at least 6 months before today.
 */
function startingInvoice(invoices) {
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - 6);
  const old = invoices.filter(inv => new Date(inv.tran_date) <= cutoff);
  return latestInvoice(old);
}

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Fetch all relevant invoices and compute per-account MRR.
 *
 * @param {object} cfg  NetSuite credentials (accountId, consumerKey, …)
 * @returns {Promise<Map<string, AccountMrr>>}
 *   Keyed by HubSpot Company ID (string).
 *
 * AccountMrr shape:
 *   {
 *     hubspotCompanyId: string,
 *     companyName: string,
 *     subscriptionPeriod: string,
 *     billingMonths: 1|3|6|12,
 *     currentMrr: number,
 *     startingMrr: number,
 *     invoiceCount: number,
 *   }
 */
async function computeMrr(cfg) {
  // ── 1. Fetch invoices ──────────────────────────────────────────────────────
  const rawInvoices = await suiteqlAll(cfg, INVOICE_SQL);
  if (!rawInvoices.length) {
    return new Map();
  }

  // ── 2. Fetch qty for all invoices (chunk into ≤1000 per IN clause) ─────────
  const allIds = rawInvoices.map(r => r.invoice_id);
  const qtyMap = new Map(); // invoice_id(string) → qty(number)

  const CHUNK = 999; // stay safely under the 1000-item SuiteQL IN limit
  for (let i = 0; i < allIds.length; i += CHUNK) {
    const chunk = allIds.slice(i, i + CHUNK);
    const rows = await suiteqlAll(cfg, qtySQL(chunk));
    for (const row of rows) {
      qtyMap.set(String(row.invoice_id), Number(row.qty));
    }
  }

  // ── 3. Group by HubSpot Company ID ────────────────────────────────────────
  /** @type {Map<string, object[]>} */
  const byAccount = new Map();
  for (const inv of rawInvoices) {
    const hsId = (inv.hubspot_company_id || '').trim();
    if (!hsId) continue; // skip invoices with no HubSpot mapping
    if (!byAccount.has(hsId)) byAccount.set(hsId, []);
    byAccount.get(hsId).push(inv);
  }

  // ── 4. Compute MRR per account ────────────────────────────────────────────
  const results = new Map();

  for (const [hsId, invoices] of byAccount) {
    const subInvoices = invoices.filter(inv => !isTrueUp(inv.memo));
    const tuInvoices  = invoices.filter(inv => isTrueUp(inv.memo));

    const billingMonths = detectCadence(subInvoices);

    // Current MRR
    const latestSub = latestInvoice(subInvoices);
    const latestTu  = latestInvoice(tuInvoices);

    const currentMrr =
      (latestSub ? invoiceMrr(latestSub, qtyMap, billingMonths, false) : 0) +
      (latestTu  ? invoiceMrr(latestTu,  qtyMap, billingMonths, true)  : 0);

    // Starting MRR (6+ months ago baseline)
    const startSub = startingInvoice(subInvoices);
    const startTu  = startingInvoice(tuInvoices);

    const startingMrr =
      (startSub ? invoiceMrr(startSub, qtyMap, billingMonths, false) : 0) +
      (startTu  ? invoiceMrr(startTu,  qtyMap, billingMonths, true)  : 0);

    // Use meta from the most recent invoice for display
    const ref = latestSub || latestTu || invoices[0];

    results.set(hsId, {
      hubspotCompanyId:   hsId,
      companyName:        ref.company_name,
      subscriptionPeriod: ref.subscription_period || null,
      billingMonths,
      currentMrr:  Math.round(currentMrr  * 100) / 100,
      startingMrr: Math.round(startingMrr * 100) / 100,
      invoiceCount: invoices.length,
    });
  }

  return results;
}

module.exports = { computeMrr, detectCadence, isTrueUp, invoiceMrr };
