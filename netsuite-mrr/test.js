/**
 * test.js  — unit tests for MRR logic (no API calls needed)
 * Run: node test.js
 */
'use strict';

const assert = require('assert');
const { detectCadence, isTrueUp, invoiceMrr } = require('./lib/ns-mrr');

let passed = 0;
let failed = 0;

function test(label, fn) {
  try {
    fn();
    console.log(`  ✓ ${label}`);
    passed++;
  } catch (e) {
    console.error(`  ✗ ${label}`);
    console.error(`      ${e.message}`);
    failed++;
  }
}

// ── detectCadence ────────────────────────────────────────────────────────────
console.log('\ndetectCadence');

test('monthly — gaps ~30 days', () => {
  const invoices = [
    { tran_date: '2025-01-01', memo: 'Recurring Billing' },
    { tran_date: '2025-02-01', memo: 'Recurring Billing' },
    { tran_date: '2025-03-01', memo: 'Recurring Billing' },
  ];
  assert.strictEqual(detectCadence(invoices), 1);
});

test('quarterly — gaps ~90 days', () => {
  const invoices = [
    { tran_date: '2024-10-01', memo: 'Renewal' },
    { tran_date: '2025-01-01', memo: 'Renewal' },
    { tran_date: '2025-04-01', memo: 'Renewal' },
  ];
  assert.strictEqual(detectCadence(invoices), 3);
});

test('annual — gaps ~365 days', () => {
  const invoices = [
    { tran_date: '2023-01-01', memo: 'Recurring Billing' },
    { tran_date: '2024-01-01', memo: 'Recurring Billing' },
    { tran_date: '2025-01-01', memo: 'Recurring Billing' },
  ];
  assert.strictEqual(detectCadence(invoices), 12);
});

test('semi-annual — gaps ~180 days', () => {
  const invoices = [
    { tran_date: '2024-07-01', memo: 'Renewal' },
    { tran_date: '2025-01-01', memo: 'Renewal' },
  ];
  assert.strictEqual(detectCadence(invoices), 6);
});

test('Revised invoices excluded from gap calculation', () => {
  // Should still detect monthly from the two non-revised dates
  const invoices = [
    { tran_date: '2025-01-01', memo: 'Recurring Billing' },
    { tran_date: '2025-01-15', memo: 'Revised: Recurring Billing' }, // excluded
    { tran_date: '2025-02-01', memo: 'Recurring Billing' },
    { tran_date: '2025-03-01', memo: 'Recurring Billing' },
  ];
  assert.strictEqual(detectCadence(invoices), 1);
});

test('single invoice — recent → monthly', () => {
  // A single invoice dated 3 days ago → within 45-day window → monthly
  const recent = new Date();
  recent.setDate(recent.getDate() - 3);
  const invoices = [{ tran_date: recent.toISOString().slice(0, 10), memo: 'Renewal' }];
  assert.strictEqual(detectCadence(invoices), 1);
});

test('single invoice — ~100 days ago → quarterly', () => {
  const old = new Date();
  old.setDate(old.getDate() - 100);
  const invoices = [{ tran_date: old.toISOString().slice(0, 10), memo: 'Renewal' }];
  assert.strictEqual(detectCadence(invoices), 3);
});

test('empty array → defaults to monthly', () => {
  assert.strictEqual(detectCadence([]), 1);
});

// ── isTrueUp ─────────────────────────────────────────────────────────────────
console.log('\nisTrueUp');

test('detects "true-up"',   () => assert.ok(isTrueUp('True-up billing Q3')));
test('detects "true up"',   () => assert.ok(isTrueUp('true up Q2 2025')));
test('detects "trueup"',    () => assert.ok(isTrueUp('TrueUp adjustment')));
test('case insensitive',    () => assert.ok(isTrueUp('TRUE-UP')));
test('false for renewal',   () => assert.ok(!isTrueUp('Recurring Billing - Renewal')));
test('false for empty',     () => assert.ok(!isTrueUp('')));
test('false for undefined', () => assert.ok(!isTrueUp(undefined)));

// ── invoiceMrr ───────────────────────────────────────────────────────────────
console.log('\ninvoiceMrr');

test('foreigntotal is a string — correctly coerced', () => {
  const inv = { foreign_total: '90000', tax_total: '0' };
  const qtyMap = new Map([['42', 3]]);
  // qty=3 from line → 90000/3 = 30000
  assert.strictEqual(invoiceMrr({ ...inv, invoice_id: '42' }, qtyMap, 3, false), 30000);
});

test('qty=0 falls back to billingMonths', () => {
  const inv = { invoice_id: '99', foreign_total: '90000', tax_total: '0' };
  const qtyMap = new Map(); // no entry → qty defaults to 0
  // billingMonths=3 used as fallback
  assert.strictEqual(invoiceMrr(inv, qtyMap, 3, false), 30000);
});

test('true-up always divides by 3 regardless of qty', () => {
  const inv = { invoice_id: '77', foreign_total: '60000', tax_total: '0' };
  const qtyMap = new Map([['77', 12]]); // qty=12 (annual) but ignored for true-ups
  assert.strictEqual(invoiceMrr(inv, qtyMap, 12, true), 20000); // 60000/3
});

test('tax is subtracted before dividing', () => {
  const inv = { invoice_id: '55', foreign_total: '112000', tax_total: '12000' };
  const qtyMap = new Map([['55', 1]]);
  // amount = 112000 - 12000 = 100000; qty=1 → MRR = 100000
  assert.strictEqual(invoiceMrr(inv, qtyMap, 1, false), 100000);
});

test('monthly invoice (qty=1) — no division', () => {
  const inv = { invoice_id: '11', foreign_total: '50000', tax_total: '0' };
  const qtyMap = new Map([['11', 1]]);
  assert.strictEqual(invoiceMrr(inv, qtyMap, 1, false), 50000);
});

// ── Summary ──────────────────────────────────────────────────────────────────
console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
