/**
 * ns-suiteql.js
 * Thin SuiteQL REST client with automatic pagination.
 *
 * Endpoint:
 *   POST https://{account}.suitetalk.api.netsuite.com/services/rest/query/v1/suiteql
 *   ?limit=1000&offset=<n>
 *
 * Response shape:
 *   { items: [...], hasMore: bool, offset: n, count: n, totalResults: n }
 */
'use strict';

const https = require('https');
const { buildOAuthHeader } = require('./ns-oauth');

/**
 * Format account ID for the SuiteQL host URL.
 * NetSuite uses lowercase + hyphens:  '1234567_SB1' → '1234567-sb1'
 * @param {string} id
 * @returns {string}
 */
function fmtAccountForUrl(id) {
  return id.toLowerCase().replace(/_/g, '-');
}

/**
 * Make a single paginated SuiteQL POST request.
 *
 * @param {object} cfg         Credentials config (accountId, consumerKey, etc.)
 * @param {string} sql         SuiteQL query string
 * @param {number} offset
 * @param {number} limit       Rows per page, max 1000
 * @returns {Promise<{items: object[], hasMore: boolean, totalResults: number}>}
 */
function suiteqlPage(cfg, sql, offset = 0, limit = 1000) {
  const host = `${fmtAccountForUrl(cfg.accountId)}.suitetalk.api.netsuite.com`;
  const path = `/services/rest/query/v1/suiteql?limit=${limit}&offset=${offset}`;
  const url = `https://${host}${path}`;

  const authHeader = buildOAuthHeader({
    method: 'POST',
    url,
    accountId: cfg.accountId,
    consumerKey: cfg.consumerKey,
    consumerSecret: cfg.consumerSecret,
    tokenId: cfg.tokenId,
    tokenSecret: cfg.tokenSecret,
  });

  const body = JSON.stringify({ q: sql });

  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        hostname: host,
        path,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
          Authorization: authHeader,
          prefer: 'transient',   // required by NetSuite SuiteQL REST
        },
      },
      res => {
        let raw = '';
        res.on('data', chunk => (raw += chunk));
        res.on('end', () => {
          if (res.statusCode >= 400) {
            return reject(
              new Error(
                `SuiteQL HTTP ${res.statusCode} at offset=${offset}: ${raw.slice(0, 400)}`
              )
            );
          }
          try {
            resolve(JSON.parse(raw));
          } catch (e) {
            reject(new Error(`SuiteQL JSON parse error: ${e.message}\n${raw.slice(0, 200)}`));
          }
        });
      }
    );
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

/**
 * Execute a SuiteQL query, automatically walking all pages.
 *
 * @param {object} cfg   Credentials config
 * @param {string} sql   SuiteQL query (no ROWNUM / OFFSET — handled internally)
 * @param {number} [pageSize=1000]
 * @returns {Promise<object[]>}  All rows across all pages
 */
async function suiteqlAll(cfg, sql, pageSize = 1000) {
  const rows = [];
  let offset = 0;
  let hasMore = true;

  while (hasMore) {
    const page = await suiteqlPage(cfg, sql, offset, pageSize);
    if (page.items && page.items.length > 0) {
      rows.push(...page.items);
    }
    hasMore = page.hasMore === true;
    offset += pageSize;
  }

  return rows;
}

module.exports = { suiteqlAll, suiteqlPage };
