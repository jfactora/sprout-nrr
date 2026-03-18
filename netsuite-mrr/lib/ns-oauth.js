/**
 * ns-oauth.js
 * OAuth 1.0 Token-Based Authentication (TBA) for NetSuite REST/SuiteQL.
 * Signs requests using HMAC-SHA256 per RFC 5849.
 *
 * NetSuite-specific notes:
 *  - realm = account ID, uppercase, underscores (e.g. "1234567_SB1")
 *  - JSON request bodies are NOT included in the signature base string
 *    (OAuth only covers application/x-www-form-urlencoded bodies)
 *  - query-string params (limit, offset) ARE included in the signature
 */
'use strict';

const crypto = require('crypto');

/**
 * Percent-encode a string per RFC 3986 (stricter than encodeURIComponent).
 * @param {string} s
 * @returns {string}
 */
function pct(s) {
  return encodeURIComponent(String(s))
    .replace(/!/g, '%21')
    .replace(/'/g, '%27')
    .replace(/\(/g, '%28')
    .replace(/\)/g, '%29')
    .replace(/\*/g, '%2A');
}

/**
 * Build the OAuth Authorization header value for a NetSuite REST request.
 *
 * @param {object} opts
 * @param {string} opts.method          HTTP method, e.g. 'POST'
 * @param {string} opts.url             Full request URL including any query params
 * @param {string} opts.accountId       NetSuite account ID, e.g. '1234567' or '1234567-sb1'
 * @param {string} opts.consumerKey
 * @param {string} opts.consumerSecret
 * @param {string} opts.tokenId
 * @param {string} opts.tokenSecret
 * @returns {string}  Full Authorization header value
 */
function buildOAuthHeader({
  method,
  url,
  accountId,
  consumerKey,
  consumerSecret,
  tokenId,
  tokenSecret,
}) {
  // realm = uppercase account ID, hyphens → underscores
  const realm = accountId.toUpperCase().replace(/-/g, '_');

  const timestamp = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomBytes(16).toString('hex');

  // Separate base URL from query string
  const urlObj = new URL(url);
  const baseUrl = `${urlObj.protocol}//${urlObj.host}${urlObj.pathname}`;

  // OAuth protocol params (no oauth_signature yet, no realm)
  const oauthParams = {
    oauth_consumer_key: consumerKey,
    oauth_nonce: nonce,
    oauth_signature_method: 'HMAC-SHA256',
    oauth_timestamp: timestamp,
    oauth_token: tokenId,
    oauth_version: '1.0',
  };

  // Collect query-string params (e.g. limit=1000&offset=0)
  const queryParams = {};
  urlObj.searchParams.forEach((v, k) => {
    queryParams[k] = v;
  });

  // Merge & sort all params for the parameter string
  const allParams = { ...oauthParams, ...queryParams };
  const paramString = Object.keys(allParams)
    .sort()
    .map(k => `${pct(k)}=${pct(allParams[k])}`)
    .join('&');

  // Signature base string: METHOD & pct(baseUrl) & pct(paramString)
  const signatureBase = [
    method.toUpperCase(),
    pct(baseUrl),
    pct(paramString),
  ].join('&');

  // Signing key: pct(consumerSecret) & pct(tokenSecret)
  const signingKey = `${pct(consumerSecret)}&${pct(tokenSecret)}`;

  const signature = crypto
    .createHmac('sha256', signingKey)
    .update(signatureBase)
    .digest('base64');

  // Build the Authorization header
  const headerParts = [
    `OAuth realm="${realm}"`,
    `oauth_consumer_key="${pct(consumerKey)}"`,
    `oauth_token="${pct(tokenId)}"`,
    `oauth_signature_method="HMAC-SHA256"`,
    `oauth_timestamp="${timestamp}"`,
    `oauth_nonce="${nonce}"`,
    `oauth_version="1.0"`,
    `oauth_signature="${pct(signature)}"`,
  ];

  return headerParts.join(', ');
}

module.exports = { buildOAuthHeader, pct };
