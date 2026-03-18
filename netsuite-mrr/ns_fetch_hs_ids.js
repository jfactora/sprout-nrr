/**
 * ns_fetch_hs_ids.js
 * Fetch the HubSpot Record ID stored on every NetSuite customer entity
 * (field: custentitycustentity16) and write ns_hs_id_map.json.
 *
 * Usage:
 *   node ns_fetch_hs_ids.js
 *
 * Reads credentials from .env (same vars as netsuite-mrr.js).
 *
 * Output: ../ns_hs_id_map.json
 *   [{ customer_id, customer_name, hubspot_record_id }]
 *   Only rows where hubspot_record_id is non-empty are written.
 *   A second file, ns_hs_id_map_all.json, includes ALL customers
 *   (useful for diagnosing coverage gaps).
 */
'use strict';

try { require('dotenv').config(); } catch (_) { /* optional */ }

const fs   = require('fs');
const path = require('path');
const { suiteqlAll } = require('./lib/ns-suiteql');

function loadConfig() {
  const required = [
    'NS_ACCOUNT_ID', 'NS_CONSUMER_KEY', 'NS_CONSUMER_SECRET',
    'NS_TOKEN_ID',   'NS_TOKEN_SECRET',
  ];
  const missing = required.filter(k => !process.env[k]);
  if (missing.length) throw new Error(`Missing env vars: ${missing.join(', ')}`);
  return {
    accountId:      process.env.NS_ACCOUNT_ID.trim(),
    consumerKey:    process.env.NS_CONSUMER_KEY.trim(),
    consumerSecret: process.env.NS_CONSUMER_SECRET.trim(),
    tokenId:        process.env.NS_TOKEN_ID.trim(),
    tokenSecret:    process.env.NS_TOKEN_SECRET.trim(),
  };
}

// custentitycustentity16 = "HubSpot Record ID" custom field on NS customer
const SQL = `
SELECT
  c.id                                              AS customer_id,
  c.companyname                                     AS customer_name,
  REPLACE(NVL(c.custentitycustentity16, ''), ',', '') AS hubspot_record_id
FROM customer c
ORDER BY c.id
`.trim();

(async () => {
  const cfg = loadConfig();
  const OUT_DIR = path.join(__dirname, '..');   // Desktop

  console.log('Fetching NetSuite customer → HubSpot Record ID mapping…');
  const rows = await suiteqlAll(cfg, SQL);
  console.log(`  ${rows.length.toLocaleString()} total customer records`);

  // All customers (for coverage diagnostics)
  const allRows = rows.map(r => ({
    customer_id:       Number(r.customer_id),
    customer_name:     (r.customer_name || '').trim(),
    hubspot_record_id: (r.hubspot_record_id || '').trim(),
  }));

  // Only those with a HubSpot Record ID set
  const mappedRows = allRows.filter(r => r.hubspot_record_id);
  console.log(`  ${mappedRows.length.toLocaleString()} customers have a HubSpot Record ID`);
  console.log(`  ${(allRows.length - mappedRows.length).toLocaleString()} customers have NO HubSpot Record ID`);

  // Write primary output (mapped only)
  const outPath = path.join(OUT_DIR, 'ns_hs_id_map.json');
  fs.writeFileSync(outPath, JSON.stringify(mappedRows, null, 2), 'utf8');
  console.log(`\nWritten: ${outPath}  (${mappedRows.length.toLocaleString()} rows)`);

  // Write full output (all customers, for gap analysis)
  const allPath = path.join(OUT_DIR, 'ns_hs_id_map_all.json');
  fs.writeFileSync(allPath, JSON.stringify(allRows, null, 2), 'utf8');
  console.log(`Written: ${allPath}  (${allRows.length.toLocaleString()} rows)`);

  // Spot-check: Knack Global
  const knack = allRows.filter(r =>
    r.customer_name.toLowerCase().includes('knack')
  );
  if (knack.length) {
    console.log('\nSpot-check (Knack):');
    knack.forEach(r =>
      console.log(`  customer_id=${r.customer_id}  name=${r.customer_name}  hubspot_record_id=${r.hubspot_record_id || '(empty)'}`)
    );
  }

  console.log('\nNext step: python3 nrr_pipeline_v2.py');
})().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
