/**
 * netsuite-mrr.js
 * Entry point — load credentials from environment and run MRR computation.
 *
 * Required environment variables:
 *   NS_ACCOUNT_ID        e.g. "1234567" or "1234567-SB1"
 *   NS_CONSUMER_KEY      Integration record → Consumer Key
 *   NS_CONSUMER_SECRET   Integration record → Consumer Secret
 *   NS_TOKEN_ID          Access Token → Token ID
 *   NS_TOKEN_SECRET      Access Token → Token Secret
 *
 * Usage (CLI):
 *   node netsuite-mrr.js
 *
 * Usage (module):
 *   const { getMrr } = require('./netsuite-mrr');
 *   const mrrMap = await getMrr();        // returns Map<hubspotId, AccountMrr>
 *   const mrrArr = await getMrr({ asArray: true });  // returns AccountMrr[]
 */
'use strict';

const { computeMrr } = require('./lib/ns-mrr');

/**
 * Load and validate credentials from process.env.
 * All values are .trim()-ed — Vercel and some CI systems append \n to secrets.
 *
 * @returns {object}
 */
function loadConfig() {
  const required = [
    'NS_ACCOUNT_ID',
    'NS_CONSUMER_KEY',
    'NS_CONSUMER_SECRET',
    'NS_TOKEN_ID',
    'NS_TOKEN_SECRET',
  ];

  const missing = required.filter(k => !process.env[k]);
  if (missing.length) {
    throw new Error(`Missing required env vars: ${missing.join(', ')}`);
  }

  return {
    accountId:      process.env.NS_ACCOUNT_ID.trim(),
    consumerKey:    process.env.NS_CONSUMER_KEY.trim(),
    consumerSecret: process.env.NS_CONSUMER_SECRET.trim(),
    tokenId:        process.env.NS_TOKEN_ID.trim(),
    tokenSecret:    process.env.NS_TOKEN_SECRET.trim(),
  };
}

/**
 * Fetch and compute MRR for all matched accounts.
 *
 * @param {object} [opts]
 * @param {boolean} [opts.asArray=false]  Return an array instead of a Map
 * @param {object}  [opts.config]         Override credentials (for testing)
 * @returns {Promise<Map|object[]>}
 */
async function getMrr({ asArray = false, config } = {}) {
  const cfg = config || loadConfig();
  const mrrMap = await computeMrr(cfg);

  if (asArray) {
    return [...mrrMap.values()].sort((a, b) =>
      b.currentMrr - a.currentMrr
    );
  }
  return mrrMap;
}

module.exports = { getMrr, loadConfig };

// ── CLI runner ──────────────────────────────────────────────────────────────
if (require.main === module) {
  (async () => {
    try {
      // Load .env if dotenv is available
      try { require('dotenv').config(); } catch (_) { /* optional */ }

      console.log('Fetching invoices from NetSuite…');
      const accounts = await getMrr({ asArray: true });

      console.log(`\nMRR Results (${accounts.length} accounts)\n`);
      console.log(
        ['HubSpot ID', 'Company', 'Sub Period', 'Cadence', 'Current MRR', 'Starting MRR', 'Invoices']
          .join('\t')
      );

      for (const a of accounts) {
        const cadenceLabel = { 1: 'Monthly', 3: 'Quarterly', 6: 'Semi-ann', 12: 'Annual' }[a.billingMonths] || a.billingMonths;
        console.log(
          [
            a.hubspotCompanyId,
            a.companyName,
            a.subscriptionPeriod || '—',
            cadenceLabel,
            a.currentMrr.toLocaleString('en-PH', { style: 'currency', currency: 'PHP' }),
            a.startingMrr.toLocaleString('en-PH', { style: 'currency', currency: 'PHP' }),
            a.invoiceCount,
          ].join('\t')
        );
      }

      console.log(`\nTotal current MRR: ${
        accounts
          .reduce((s, a) => s + a.currentMrr, 0)
          .toLocaleString('en-PH', { style: 'currency', currency: 'PHP' })
      }`);
    } catch (err) {
      console.error('Error:', err.message);
      process.exit(1);
    }
  })();
}
