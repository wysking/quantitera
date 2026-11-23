/**
 * QuantItera Google-Native Bridge (Google Apps Script V8)
 *
 * Replaces fragile remote GitHub MCP connectors for Gemini (Google AI Pro)
 * interactive chats and Scheduled Tasks.
 *
 * Architecture (Route A):
 *   - Downlink (GitHub -> Google Drive):
 *       Reads read-only mirror Issues (#37/#38/#39, matched by marker) from
 *       your-username/my-quantitera-workspace and updates 3 fixed Google Docs in place
 *       (preserving File IDs) inside folder "QuantItera-Cloud".
 *   - Uplink (Google -> GitHub):
 *       Scans 4 native Google channels for structured inbox request JSON:
 *         1. Gmail Drafts with subject starting with "[QUANT-INBOX]"
 *         2. Gmail Messages/Threads matching subject:"[QUANT-INBOX]"
 *         3. Google Drive folder "QuantItera-Cloud/Quant-Inbox" (Docs/txt/md/json/Sheets)
 *         4. Fixed Google Doc "QuantItera-Cloud/Quant-Inbox-Queue"
 *       Validates every request strictly against mobile/processor.py and
 *       research_engine/processor.py schemas, enforces target allowlist
 *       ("inbox" | "workspace/inbox"), checks immutability on GitHub, uploads
 *       via Fine-Grained PAT, optionally polls outbox receipts, archives source
 *       items to prevent duplicate submissions, and logs status to
 *       "Quant-4-同步日志与回执".
 *
 * Security & Ledger Contract:
 *   - Append-only: NEVER overwrites existing files in inbox/ or workspace/inbox/.
 *   - Path allowlist: ONLY creates inbox/<request_id>.json or workspace/inbox/<request_id>.json.
 *   - Zero paid APIs, zero GCP Billing, zero public Web App exposure.
 */

var BRIDGE_CONFIG = {
  DEFAULT_REPO: 'your-username/my-quantitera-workspace',
  DEFAULT_BRANCH: 'main',
  ROOT_FOLDER_NAME: 'QuantItera-Cloud',
  INBOX_FOLDER_NAME: 'Quant-Inbox',
  PROCESSED_FOLDER_NAME: 'Quant-Processed',
  REJECTED_FOLDER_NAME: 'Quant-Rejected',
  INBOX_QUEUE_DOC_NAME: 'Quant-Inbox-Queue',
  SYNC_LOG_DOC_NAME: 'Quant-4-同步日志与回执',
  QUEUE_MARKER: '--- PENDING REQUESTS BELOW ---',
  GMAIL_SUBJECT_PREFIX: '[QUANT-INBOX]',
  GMAIL_REJECTED_PREFIX: '[QUANT-REJECTED]',
  GMAIL_LABEL_SYNCED: 'quant-synced',
  GMAIL_LABEL_REJECTED: 'quant-rejected',
  MAX_PAYLOAD_BYTES: 80000,
  MAX_DOC_CHARS: 450000,
  MAX_LOG_ENTRIES: 40,
  OUTBOX_POLL_MAX_MS: 90000,
  OUTBOX_POLL_INTERVAL_MS: 15000,
  MIRROR_SPECS: [
    {
      key: 'protocols',
      marker: '<!-- gemini-mirror:protocols -->',
      issueTitle: '[Gemini Mirror] 1. 协议与指令（只读镜像）',
      docName: 'Quant-1-协议与指令',
      docPropKey: 'DOC_ID_PROTOCOLS',
      issuePropKey: 'ISSUE_NUM_PROTOCOLS',
      fpPropKey: 'SYNC_FP_PROTOCOLS'
    },
    {
      key: 'core-state',
      marker: '<!-- gemini-mirror:core-state -->',
      issueTitle: '[Gemini Mirror] 2. 核心账户、状态与最新回执（只读镜像）',
      docName: 'Quant-2-核心状态与最新回执',
      docPropKey: 'DOC_ID_CORE_STATE',
      issuePropKey: 'ISSUE_NUM_CORE_STATE',
      fpPropKey: 'SYNC_FP_CORE_STATE'
    },
    {
      key: 'research-workspace',
      marker: '<!-- gemini-mirror:research-workspace -->',
      issueTitle: '[Gemini Mirror] 3. 研究报告、前向与个人闭环（只读镜像）',
      docName: 'Quant-3-研究报告与个人闭环',
      docPropKey: 'DOC_ID_RESEARCH_WORKSPACE',
      issuePropKey: 'ISSUE_NUM_RESEARCH_WORKSPACE',
      fpPropKey: 'SYNC_FP_RESEARCH_WORKSPACE'
    }
  ]
};

var ALLOWED_TARGETS = {
  'inbox': true,
  'workspace/inbox': true
};

var REQUEST_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$/;

var ROOT_OPERATIONS = {
  record_gold_shadow_evidence: true,
  set_gold_shadow_enabled: true,
  record_asset_shadow_evidence: true,
  set_asset_shadow_enabled: true,
  register_v6_forward_plan: true,
  set_v6_forward_enabled: true,
  history_backfill: true,
  register_factor_candidate: true,
  record_factor_series: true,
  factor_validation: true,
  record_allocation_policy: true,
  portfolio_analysis: true,
  equity_analysis: true,
  research_refresh: true,
  research_validation: true,
  record_evidence: true,
  gold_analysis: true,
  redlow_analysis: true,
  market_quote: true,
  record_trade: true,
  report_trade: true,
  void_trade: true,
  save_decision: true,
  record_snapshot: true,
  record_review: true,
  classify_decision: true,
  status: true
};

var ROOT_FIELDS = {
  reference: true, asset: true, fund_name: true, side: true, amount_cny: true,
  occurred_at: true, confirmed: true, note: true, trade_date: true,
  assets: true, subjects: true, topics: true, aliases: true, horizon: true,
  status: true, confidence: true, question: true, facts: true,
  user_hypotheses: true, model_inference: true, conclusion: true,
  invalidation: true, review_at: true, supersedes: true, related_ids: true,
  source_refs: true, review_id: true, target_id: true, record_kind: true,
  refresh: true, scenario: true, policy: true, factor_candidates: true,
  candidate: true, factor_series: true, evidence: true, enabled: true
};

var ROOT_BOOL_FIELDS = {
  confirmed: true,
  refresh: true,
  enabled: true
};

var WORKSPACE_OPERATIONS = {
  save_decision: true,
  record_review: true,
  classify_decision: true,
  record_evidence: true,
  research_refresh: true,
  status: true
};

var WORKSPACE_FIELDS = {
  reference: true, asset: true, note: true, assets: true, subjects: true,
  topics: true, aliases: true, horizon: true, status: true, confidence: true,
  question: true, facts: true, user_hypotheses: true, model_inference: true,
  conclusion: true, invalidation: true, review_at: true, supersedes: true,
  related_ids: true, source_refs: true, review_id: true, target_id: true,
  record_kind: true, review_spec: true, review_result: true, evidence: true,
  factor_candidates: true
};

var REVIEW_SPEC_KEYS = {
  kind: true, checks: true, milestones: true, errors: true,
  evidence_gaps: true, mechanisms: true, next_hypotheses: true,
  competing_explanations: true
};

var MARKET_CHECK_KEYS = [
  'claim', 'history_key', 'symbol', 'venue', 'currency',
  'return_kind', 'metric', 'start', 'end', 'operator', 'threshold'
];

var REVIEW_RESULT_KEYS = {
  supported: true, refuted: true, errors: true, evidence_gaps: true,
  mechanisms: true, next_hypotheses: true, competing_explanations: true
};

// ============================================================================
// Pure Parsing, Sanitization & Validation Helpers (Unit-Tested in Node.js)
// ============================================================================

function utf8ByteLength(str) {
  if (typeof Utilities !== 'undefined' && Utilities.newBlob) {
    return Utilities.newBlob(str, 'text/plain; charset=utf-8').getBytes().length;
  }
  if (typeof Buffer !== 'undefined') {
    return Buffer.byteLength(str, 'utf8');
  }
  return unescape(encodeURIComponent(str)).length;
}

function toBase64Utf8(str) {
  if (typeof Utilities !== 'undefined' && Utilities.base64Encode && Utilities.newBlob) {
    return Utilities.base64Encode(Utilities.newBlob(str, 'text/plain; charset=utf-8').getBytes());
  }
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(str, 'utf8').toString('base64');
  }
  throw new Error('Base64 encoder unavailable');
}

function fromBase64Utf8(b64) {
  var clean = String(b64 || '').replace(/\s+/g, '');
  if (typeof Utilities !== 'undefined' && Utilities.base64Decode && Utilities.newBlob) {
    return Utilities.newBlob(Utilities.base64Decode(clean)).getDataAsString('UTF-8');
  }
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(clean, 'base64').toString('utf8');
  }
  throw new Error('Base64 decoder unavailable');
}

function sha256Hex(str) {
  if (typeof Utilities !== 'undefined' && Utilities.computeDigest) {
    var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, str, Utilities.Charset.UTF_8);
    return bytes.map(function (b) {
      var v = b < 0 ? b + 256 : b;
      return (v < 16 ? '0' : '') + v.toString(16);
    }).join('');
  }
  if (typeof require === 'function') {
    return require('crypto').createHash('sha256').update(str, 'utf8').digest('hex');
  }
  throw new Error('SHA-256 unavailable');
}

function formatBeijingTime(dateObj) {
  var d = dateObj || new Date();
  var utcMs = d.getTime() + d.getTimezoneOffset() * 60000;
  var bj = new Date(utcMs + 8 * 3600000);
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  return bj.getFullYear() + '-' + pad(bj.getMonth() + 1) + '-' + pad(bj.getDate()) +
    ' ' + pad(bj.getHours()) + ':' + pad(bj.getMinutes()) + ':' + pad(bj.getSeconds()) + ' +08:00';
}

function sanitizeRawText(text) {
  return String(text || '')
    .replace(/^\uFEFF/, '')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .replace(/\u00A0/g, ' ')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n');
}

/**
 * Parses target and request_id hint from a Gmail subject or Drive filename.
 * Supported examples:
 *   "[QUANT-INBOX] inbox/chat-20261121-133000-abc123"
 *   "[QUANT-INBOX] workspace/inbox/chat-20261121-133000-abc123.json"
 *   "workspace__chat-20261121-133000-abc123"
 */
function parseHintFromLabel(label) {
  var text = sanitizeRawText(label).trim();
  if (!text) return {};
  var pathMatch = text.match(/(workspace\/inbox|inbox)\/([A-Za-z0-9][A-Za-z0-9_-]{2,63})(?:\.json)?/i);
  if (pathMatch) {
    return {
      target: pathMatch[1].toLowerCase(),
      request_id: pathMatch[2]
    };
  }
  var idOnly = text
    .replace(/^\[QUANT-INBOX\]\s*/i, '')
    .replace(/\.json$/i, '')
    .trim();
  if (REQUEST_ID_RE.test(idOnly)) {
    return { request_id: idOnly };
  }
  return {};
}

/**
 * Extracts balanced JSON objects/arrays from free-form text (fenced blocks first).
 */
function extractJsonCandidates(rawText) {
  var text = sanitizeRawText(rawText).trim();
  if (!text) return [];

  var fenced = [];
  var fenceRe = /```(?:json)?\s*\n([\s\S]*?)```/gi;
  var m;
  while ((m = fenceRe.exec(text)) !== null) {
    var inner = m[1].trim();
    if (inner) fenced.push(inner);
  }
  if (fenced.length > 0) {
    return fenced;
  }

  // Fallback: scan balanced top-level { ... } or [ ... ] blocks
  var blocks = [];
  var i = 0;
  while (i < text.length) {
    var ch = text[i];
    if (ch !== '{' && ch !== '[') {
      i++;
      continue;
    }
    var openCh = ch;
    var closeCh = ch === '{' ? '}' : ']';
    var depth = 0;
    var inStr = false;
    var escaped = false;
    var start = i;
    var foundEnd = -1;
    for (var j = i; j < text.length; j++) {
      var c = text[j];
      if (inStr) {
        if (escaped) {
          escaped = false;
        } else if (c === '\\') {
          escaped = true;
        } else if (c === '"') {
          inStr = false;
        }
        continue;
      }
      if (c === '"') {
        inStr = true;
      } else if (c === openCh) {
        depth++;
      } else if (c === closeCh) {
        depth--;
        if (depth === 0) {
          foundEnd = j;
          break;
        }
      }
    }
    if (foundEnd !== -1) {
      blocks.push(text.slice(start, foundEnd + 1));
      i = foundEnd + 1;
    } else {
      blocks.push(text.slice(start));
      break;
    }
  }
  return blocks;
}

/**
 * Strictly parses a JSON candidate. Never blindly replaces Chinese curly quotes
 * inside valid JSON strings; only reports a clear error if curly quotes broke syntax.
 */
function parseJsonStrict(candidate) {
  try {
    return JSON.parse(candidate);
  } catch (err) {
    if (/[“”‘’]/.test(candidate)) {
      throw new Error('JSON 解析失败（检测到弯引号 “”/‘’，可能被富文本替换，请使用标准英文双引号 "）：' + err.message);
    }
    throw new Error('JSON 解析失败：' + err.message);
  }
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function isStringArray(v) {
  if (!Array.isArray(v)) return false;
  for (var i = 0; i < v.length; i++) {
    if (typeof v[i] !== 'string') return false;
  }
  return true;
}

function validateWorkspaceSubSchemas(op, inputs) {
  if (op === 'save_decision' && Object.prototype.hasOwnProperty.call(inputs, 'review_spec')) {
    var spec;
    try {
      spec = JSON.parse(inputs.review_spec);
    } catch (e) {
      throw new Error('workspace/inbox 的 review_spec 不是合法 JSON 字符串：' + e.message);
    }
    if (!isPlainObject(spec)) {
      throw new Error('review_spec 必须是 JSON 对象');
    }
    var specKeys = Object.keys(spec);
    for (var i = 0; i < specKeys.length; i++) {
      if (!REVIEW_SPEC_KEYS[specKeys[i]]) {
        throw new Error('review_spec 包含非法字段：' + specKeys[i]);
      }
    }
    if (spec.kind !== 'market' && spec.kind !== 'research' && spec.kind !== 'policy') {
      throw new Error('review_spec.kind 必须为 market、research 或 policy');
    }
    if (spec.kind === 'market') {
      if (!Array.isArray(spec.checks) || spec.checks.length === 0) {
        throw new Error('review_spec.kind=market 时 checks 必须为非空数组');
      }
      for (var cIdx = 0; cIdx < spec.checks.length; cIdx++) {
        var chk = spec.checks[cIdx];
        if (!isPlainObject(chk)) {
          throw new Error('review_spec.checks[' + cIdx + '] 必须是对象');
        }
        var chkKeys = Object.keys(chk);
        if (chkKeys.length !== MARKET_CHECK_KEYS.length) {
          throw new Error('review_spec.checks[' + cIdx + '] 必须严格包含 11 个字段');
        }
        for (var kIdx = 0; kIdx < MARKET_CHECK_KEYS.length; kIdx++) {
          if (!Object.prototype.hasOwnProperty.call(chk, MARKET_CHECK_KEYS[kIdx])) {
            throw new Error('review_spec.checks[' + cIdx + '] 缺少字段：' + MARKET_CHECK_KEYS[kIdx]);
          }
        }
      }
    }
    if (Object.prototype.hasOwnProperty.call(spec, 'milestones')) {
      if (!Array.isArray(spec.milestones) || spec.milestones.length > 10) {
        throw new Error('review_spec.milestones 必须为最多 10 项的数组');
      }
      for (var mIdx = 0; mIdx < spec.milestones.length; mIdx++) {
        var ms = spec.milestones[mIdx];
        if (!isPlainObject(ms) || Object.keys(ms).length !== 2 ||
            typeof ms.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(ms.date) ||
            typeof ms.condition !== 'string') {
          throw new Error('review_spec.milestones[' + mIdx + '] 须为 {"date":"YYYY-MM-DD","condition":"..."} 对象');
        }
      }
    }
  }

  if (op === 'record_review' && Object.prototype.hasOwnProperty.call(inputs, 'review_result')) {
    var res;
    try {
      res = JSON.parse(inputs.review_result);
    } catch (e2) {
      throw new Error('workspace/inbox 的 review_result 不是合法 JSON 字符串：' + e2.message);
    }
    if (!isPlainObject(res)) {
      throw new Error('review_result 必须是 JSON 对象');
    }
    var resKeys = Object.keys(res);
    for (var r = 0; r < resKeys.length; r++) {
      if (!REVIEW_RESULT_KEYS[resKeys[r]]) {
        throw new Error('review_result 包含非法字段：' + resKeys[r]);
      }
      if (!isStringArray(res[resKeys[r]])) {
        throw new Error('review_result.' + resKeys[r] + ' 必须是字符串数组');
      }
    }
    if (inputs.status === 'awaiting_evaluation') {
      if (!Array.isArray(res.evidence_gaps) || res.evidence_gaps.length === 0) {
        throw new Error('record_review status=awaiting_evaluation 时 evidence_gaps 必须非空');
      }
    }
  }
}

/**
 * Validates a normalized {target, request_id, payload} request strictly matching
 * mobile/processor.py (target="inbox") or research_engine/processor.py (target="workspace/inbox").
 */
function validateBridgeRequest(req) {
  if (!isPlainObject(req)) {
    throw new Error('请求外层必须是 JSON 对象');
  }
  var target = req.target;
  if (typeof target !== 'string' || !ALLOWED_TARGETS[target]) {
    throw new Error('target 仅允许 "inbox" 或 "workspace/inbox"，收到：' + String(target));
  }
  var requestId = req.request_id;
  if (typeof requestId !== 'string' || !REQUEST_ID_RE.test(requestId)) {
    throw new Error('request_id 须为 3—64 位字母、数字、横线或下划线，且以字母或数字开头：' + String(requestId));
  }
  var payload = req.payload;
  if (!isPlainObject(payload)) {
    throw new Error('payload 必须是 JSON 对象');
  }
  var topKeys = Object.keys(payload).sort();
  if (topKeys.length !== 3 || topKeys[0] !== 'inputs' || topKeys[1] !== 'operation' || topKeys[2] !== 'version') {
    throw new Error('payload 必须包含且仅包含 version、operation、inputs');
  }
  if (typeof payload.version !== 'number' || payload.version !== 1 || Math.floor(payload.version) !== 1) {
    throw new Error('payload.version 必须为数字 1');
  }
  var op = payload.operation;
  var inputs = payload.inputs;
  if (!isPlainObject(inputs)) {
    throw new Error('payload.inputs 必须是 JSON 对象');
  }

  var isWorkspace = target === 'workspace/inbox';
  var opMap = isWorkspace ? WORKSPACE_OPERATIONS : ROOT_OPERATIONS;
  var fieldMap = isWorkspace ? WORKSPACE_FIELDS : ROOT_FIELDS;

  if (typeof op !== 'string' || !opMap[op]) {
    throw new Error(target + ' 不支持的操作：' + String(op));
  }

  var inputKeys = Object.keys(inputs);
  for (var i = 0; i < inputKeys.length; i++) {
    var name = inputKeys[i];
    if (!fieldMap[name]) {
      throw new Error(target + ' 的 inputs 包含无效字段：' + name);
    }
    var val = inputs[name];
    if (!isWorkspace && ROOT_BOOL_FIELDS[name]) {
      if (typeof val !== 'boolean') {
        throw new Error(name + ' 须为 JSON 布尔值');
      }
    } else if (typeof val !== 'string') {
      throw new Error(name + ' 须为字符串');
    }
  }

  if (isWorkspace) {
    if (Object.prototype.hasOwnProperty.call(inputs, 'review_spec') && op !== 'save_decision') {
      throw new Error('review_spec 仅支持 save_decision');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'review_result') && op !== 'record_review') {
      throw new Error('review_result 仅支持 record_review');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'evidence') && op !== 'record_evidence') {
      throw new Error('evidence 仅支持 record_evidence');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'factor_candidates') && op !== 'save_decision' && op !== 'record_review') {
      throw new Error('factor_candidates 仅支持 save_decision 或 record_review');
    }
    validateWorkspaceSubSchemas(op, inputs);
  } else {
    if (Object.prototype.hasOwnProperty.call(inputs, 'scenario') && op !== 'portfolio_analysis') {
      throw new Error('scenario 仅支持 portfolio_analysis');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'policy') && op !== 'record_allocation_policy') {
      throw new Error('policy 仅支持 record_allocation_policy');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'refresh') &&
        op !== 'portfolio_analysis' && op !== 'equity_analysis' && op !== 'research_refresh') {
      throw new Error('refresh 仅支持研究刷新操作');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'candidate') && op !== 'register_factor_candidate') {
      throw new Error('candidate 仅支持 register_factor_candidate');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'factor_candidates') && op !== 'save_decision') {
      throw new Error('factor_candidates 仅支持 save_decision');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'factor_series') && op !== 'record_factor_series') {
      throw new Error('factor_series 仅支持 record_factor_series');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'evidence') &&
        op !== 'record_gold_shadow_evidence' && op !== 'record_asset_shadow_evidence') {
      throw new Error('evidence 仅支持影子证据记录操作');
    }
    if (Object.prototype.hasOwnProperty.call(inputs, 'enabled') &&
        op !== 'set_gold_shadow_enabled' && op !== 'set_asset_shadow_enabled' && op !== 'set_v6_forward_enabled') {
      throw new Error('enabled 仅支持影子/前向撤回控制操作');
    }
  }

  var canonicalJson = JSON.stringify(payload, null, 2) + '\n';
  var bytes = utf8ByteLength(canonicalJson);
  if (bytes > BRIDGE_CONFIG.MAX_PAYLOAD_BYTES) {
    throw new Error('请求超过 80KB 限制（当前 ' + bytes + ' 字节）');
  }

  var repoPath = target + '/' + requestId + '.json';
  var outboxPath = (isWorkspace ? 'workspace/outbox/' : 'outbox/') + requestId + '.json';

  return {
    target: target,
    request_id: requestId,
    repoPath: repoPath,
    outboxPath: outboxPath,
    payload: payload,
    canonicalJson: canonicalJson,
    sha256: sha256Hex(canonicalJson)
  };
}

/**
 * Extracts and validates one or more requests from a raw text source (Gmail/Doc/File).
 * Supports:
 *   1. Envelope object: {"target":"inbox","request_id":"...","payload":{...}}
 *   2. Envelope array: [ {...}, {...} ]
 *   3. Multiple JSON blocks in one document/message
 *   4. Raw payload {"version":1,"operation":...,"inputs":...} when labelHint supplies target & request_id
 */
function parseRequestsFromText(rawText, labelHint) {
  var candidates = extractJsonCandidates(rawText);
  if (candidates.length === 0) {
    throw new Error('未在正文中找到任何 JSON 请求块');
  }
  var hint = parseHintFromLabel(labelHint || '');
  var items = [];

  for (var i = 0; i < candidates.length; i++) {
    var parsed = parseJsonStrict(candidates[i]);
    var list = Array.isArray(parsed) ? parsed : [parsed];
    for (var j = 0; j < list.length; j++) {
      var obj = list[j];
      if (!isPlainObject(obj)) {
        throw new Error('JSON 数组第 ' + j + ' 项不是对象');
      }
      var normalized;
      if (Object.prototype.hasOwnProperty.call(obj, 'payload')) {
        normalized = {
          target: obj.target || hint.target,
          request_id: obj.request_id || hint.request_id,
          payload: obj.payload
        };
      } else if (Object.prototype.hasOwnProperty.call(obj, 'version') && Object.prototype.hasOwnProperty.call(obj, 'operation')) {
        normalized = {
          target: hint.target,
          request_id: hint.request_id,
          payload: obj
        };
      } else {
        throw new Error('JSON 缺少 payload 或 version/operation 字段');
      }
      items.push(validateBridgeRequest(normalized));
    }
  }
  return items;
}

function assembleMirrorDocText(spec, issue, comments, repo, syncedAtText) {
  var parts = [];
  parts.push('【只读自动同步镜像 · 严禁手动修改本文件】');
  parts.push('最后同步时间（北京时间）：' + syncedAtText);
  parts.push('来源仓库：' + repo + ' · Issue #' + issue.number + '（updated_at: ' + (issue.updated_at || 'unknown') + '）');
  parts.push('写入通道：请勿直接修改本文档；新建请求请输出标准 JSON 信封到 Gmail（主题 [QUANT-INBOX]）或 Quant-Inbox。');
  parts.push('====================================================================');
  parts.push(String(issue.body || '').trim());

  for (var i = 0; i < comments.length; i++) {
    parts.push('\n====================================================================');
    parts.push('--- 补充段 ' + (i + 1) + '（updated_at: ' + (comments[i].updated_at || 'unknown') + '）---');
    parts.push(String(comments[i].body || '').trim());
  }

  var full = parts.join('\n\n');
  if (full.length > BRIDGE_CONFIG.MAX_DOC_CHARS) {
    var suffix = '\n\n... [超出单文档字符上限已截断，完整归档在私有 GitHub 仓库] ...';
    full = full.slice(0, BRIDGE_CONFIG.MAX_DOC_CHARS - suffix.length) + suffix;
  }
  return full;
}

function extractQueueBody(fullDocText) {
  var text = sanitizeRawText(fullDocText);
  var idx = text.indexOf(BRIDGE_CONFIG.QUEUE_MARKER);
  if (idx === -1) {
    return { header: null, pending: text.trim() };
  }
  var splitAt = idx + BRIDGE_CONFIG.QUEUE_MARKER.length;
  return {
    header: text.slice(0, splitAt),
    pending: text.slice(splitAt).trim()
  };
}

// ============================================================================
// GitHub REST API Client (Fine-Grained PAT, single-repo scoped)
// ============================================================================

function getBridgeSettings_(props) {
  var p = props || PropertiesService.getScriptProperties();
  var token = (p.getProperty('GITHUB_TOKEN') || '').trim();
  if (!token) {
    throw new Error('缺少 ScriptProperty: GITHUB_TOKEN。请先在项目设置或 setupProperties() 中填入单仓 Fine-Grained PAT。');
  }
  return {
    token: token,
    repo: (p.getProperty('GITHUB_REPO') || BRIDGE_CONFIG.DEFAULT_REPO).trim(),
    branch: (p.getProperty('GITHUB_BRANCH') || BRIDGE_CONFIG.DEFAULT_BRANCH).trim(),
    notifyEmail: (p.getProperty('NOTIFY_EMAIL') || '').trim()
  };
}

function githubRequest_(settings, method, path, bodyObj, allow404, deps) {
  var fetchFn = (deps && deps.fetch) || UrlFetchApp.fetch;
  var sleepFn = (deps && deps.sleep) || Utilities.sleep;
  var url = 'https://api.github.com' + path;
  var headers = {
    'Authorization': 'Bearer ' + settings.token,
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'quantitera-google-bridge',
    'X-GitHub-Api-Version': '2022-11-28'
  };
  var options = {
    method: method,
    headers: headers,
    muteHttpExceptions: true
  };
  if (bodyObj !== undefined && bodyObj !== null) {
    options.contentType = 'application/json; charset=utf-8';
    options.payload = JSON.stringify(bodyObj);
  }

  for (var attempt = 1; attempt <= 3; attempt++) {
    var resp = fetchFn(url, options);
    var code = resp.getResponseCode();
    var text = resp.getContentText();
    if (allow404 && code === 404) {
      return { status: 404, data: null };
    }
    if (code >= 200 && code < 300) {
      return { status: code, data: text ? JSON.parse(text) : null };
    }
    if ((code === 429 || code === 500 || code === 502 || code === 503 || code === 504) && attempt < 3) {
      sleepFn(1000 * attempt);
      continue;
    }
    throw new Error('GitHub API ' + method + ' ' + path + ' 失败 (' + code + '): ' + text.slice(0, 500));
  }
}

/**
 * Uploads one validated request immutably to inbox/<id>.json or workspace/inbox/<id>.json.
 * Never overwrites an existing file.
 */
function uploadRequestToGitHub_(settings, req, deps) {
  var contentPath = '/repos/' + settings.repo + '/contents/' + req.repoPath;
  var existing = githubRequest_(settings, 'GET', contentPath + '?ref=' + encodeURIComponent(settings.branch), null, true, deps);

  if (existing.status === 200 && existing.data) {
    var remoteText = fromBase64Utf8(existing.data.content || '');
    var remoteSha256 = sha256Hex(remoteText);
    if (remoteSha256 === req.sha256) {
      return {
        status: 'already_exists_identical',
        repoPath: req.repoPath,
        outboxPath: req.outboxPath,
        commitSha: existing.data.sha || null
      };
    }
    throw new Error('GitHub 已存在同名请求但内容不同（严禁覆盖已提交请求）：' + req.repoPath + '，请更换新的 request_id');
  }

  var res = githubRequest_(settings, 'PUT', contentPath, {
    message: 'Google Bridge: submit ' + req.repoPath,
    branch: settings.branch,
    content: toBase64Utf8(req.canonicalJson)
  }, false, deps);

  return {
    status: 'uploaded',
    repoPath: req.repoPath,
    outboxPath: req.outboxPath,
    commitSha: res.data && res.data.commit ? res.data.commit.sha : null
  };
}

function fetchOutboxReceipt_(settings, outboxPath, deps) {
  var path = '/repos/' + settings.repo + '/contents/' + outboxPath + '?ref=' + encodeURIComponent(settings.branch);
  var res = githubRequest_(settings, 'GET', path, null, true, deps);
  if (res.status === 404 || !res.data) {
    return null;
  }
  try {
    return JSON.parse(fromBase64Utf8(res.data.content || ''));
  } catch (e) {
    return { status: 'parse_error', error: e.message };
  }
}

// ============================================================================
// Google Drive / Docs Resource Management (Preserves Fixed File IDs)
// ============================================================================

function getOrCreateFolder_(parentFolder, name, propKey, props) {
  var savedId = propKey ? props.getProperty(propKey) : null;
  if (savedId) {
    try {
      var byId = DriveApp.getFolderById(savedId);
      if (!byId.isTrashed()) return byId;
    } catch (e) {
      // Fallback to search by name
    }
  }
  var iter = parentFolder ? parentFolder.getFoldersByName(name) : DriveApp.getFoldersByName(name);
  var folder = iter.hasNext() ? iter.next() : (parentFolder ? parentFolder.createFolder(name) : DriveApp.createFolder(name));
  if (propKey) props.setProperty(propKey, folder.getId());
  return folder;
}

function getOrCreateDocId_(parentFolder, name, propKey, props, initialText) {
  var savedId = propKey ? props.getProperty(propKey) : null;
  if (savedId) {
    try {
      var fileById = DriveApp.getFileById(savedId);
      if (!fileById.isTrashed()) return savedId;
    } catch (e) {
      // Fallback to search by name
    }
  }
  var iter = parentFolder.getFilesByName(name);
  while (iter.hasNext()) {
    var f = iter.next();
    if (!f.isTrashed() && f.getMimeType() === MimeType.GOOGLE_DOCS) {
      if (propKey) props.setProperty(propKey, f.getId());
      return f.getId();
    }
  }
  var doc = DocumentApp.create(name);
  if (initialText) {
    doc.getBody().setText(initialText);
    doc.saveAndClose();
  }
  var docId = doc.getId();
  DriveApp.getFileById(docId).moveTo(parentFolder);
  if (propKey) props.setProperty(propKey, docId);
  return docId;
}

function ensureWorkspaceLayout_(props) {
  var root = getOrCreateFolder_(null, BRIDGE_CONFIG.ROOT_FOLDER_NAME, 'FOLDER_ID_ROOT', props);
  var inbox = getOrCreateFolder_(root, BRIDGE_CONFIG.INBOX_FOLDER_NAME, 'FOLDER_ID_INBOX', props);
  var processed = getOrCreateFolder_(root, BRIDGE_CONFIG.PROCESSED_FOLDER_NAME, 'FOLDER_ID_PROCESSED', props);
  var rejected = getOrCreateFolder_(root, BRIDGE_CONFIG.REJECTED_FOLDER_NAME, 'FOLDER_ID_REJECTED', props);

  var queueTemplate = [
    '【QuantItera 请求投递队列 · 可由 Gemini 或手机手动写入】',
    '使用说明：将标准 JSON 信封写在下方分隔线之后，Apps Script 每 5 分钟自动校验并推入 GitHub。',
    '同步成功后会自动归档到 Quant-Processed 并清空下方待办区。',
    '',
    BRIDGE_CONFIG.QUEUE_MARKER,
    ''
  ].join('\n');

  var queueDocId = getOrCreateDocId_(root, BRIDGE_CONFIG.INBOX_QUEUE_DOC_NAME, 'DOC_ID_INBOX_QUEUE', props, queueTemplate);
  var logDocId = getOrCreateDocId_(root, BRIDGE_CONFIG.SYNC_LOG_DOC_NAME, 'DOC_ID_SYNC_LOG', props,
    '【QuantItera Google Bridge 同步日志与回执（最新记录在最上方）】\n');

  var mirrorDocIds = {};
  for (var i = 0; i < BRIDGE_CONFIG.MIRROR_SPECS.length; i++) {
    var spec = BRIDGE_CONFIG.MIRROR_SPECS[i];
    mirrorDocIds[spec.key] = getOrCreateDocId_(root, spec.docName, spec.docPropKey, props,
      '【初始化中：等待首次从 GitHub 同步 ' + spec.docName + '】');
  }

  return {
    root: root,
    inbox: inbox,
    processed: processed,
    rejected: rejected,
    queueDocId: queueDocId,
    logDocId: logDocId,
    mirrorDocIds: mirrorDocIds
  };
}

function appendSyncLog_(logDocId, lines) {
  if (!lines || lines.length === 0) return;
  var logDoc = DocumentApp.openById(logDocId);
  var header = '【QuantItera Google Bridge 同步日志与回执（最新记录在最上方）】';
  var existing = sanitizeRawText(logDoc.getBody().getText());
  var entries = existing.split('\n---\n').filter(function (s) {
    return s.trim() && s.trim() !== header;
  });
  var newEntry = '[' + formatBeijingTime() + ']\n' + lines.join('\n');
  entries.unshift(newEntry);
  if (entries.length > BRIDGE_CONFIG.MAX_LOG_ENTRIES) {
    entries = entries.slice(0, BRIDGE_CONFIG.MAX_LOG_ENTRIES);
  }
  logDoc.getBody().setText(header + '\n---\n' + entries.join('\n---\n'));
  logDoc.saveAndClose();
}

function notifyErrorIfConfigured_(settings, subject, body) {
  if (!settings.notifyEmail) return;
  try {
    MailApp.sendEmail(settings.notifyEmail, '[Quant Bridge 告警] ' + subject, body);
  } catch (e) {
    // Do not break sync cycle on mail quota issue
  }
}

// ============================================================================
// Downlink Sync: GitHub Mirror Issues (#37/#38/#39) -> 3 Fixed Google Docs
// ============================================================================

function resolveMirrorIssueNumber_(settings, spec, props, deps) {
  var cached = props.getProperty(spec.issuePropKey);
  if (cached) {
    var num = parseInt(cached, 10);
    if (!isNaN(num) && num > 0) {
      var check = githubRequest_(settings, 'GET', '/repos/' + settings.repo + '/issues/' + num, null, true, deps);
      if (check.status === 200 && check.data && check.data.state === 'open' &&
          (String(check.data.body || '').indexOf(spec.marker) !== -1 || check.data.title === spec.issueTitle)) {
        return check.data;
      }
    }
  }

  var listRes = githubRequest_(settings, 'GET', '/repos/' + settings.repo + '/issues?state=open&per_page=100', null, false, deps);
  var issues = listRes.data || [];
  for (var i = 0; i < issues.length; i++) {
    var iss = issues[i];
    if (iss.pull_request) continue;
    if (String(iss.body || '').indexOf(spec.marker) !== -1 || iss.title === spec.issueTitle) {
      props.setProperty(spec.issuePropKey, String(iss.number));
      return iss;
    }
  }
  throw new Error('未在仓库 ' + settings.repo + ' 中找到镜像 Issue：' + spec.issueTitle);
}

function fetchAllIssueComments_(settings, issueNumber, deps) {
  var all = [];
  var page = 1;
  while (true) {
    var res = githubRequest_(
      settings,
      'GET',
      '/repos/' + settings.repo + '/issues/' + issueNumber + '/comments?per_page=100&page=' + page,
      null,
      false,
      deps
    );
    var batch = res.data || [];
    for (var i = 0; i < batch.length; i++) all.push(batch[i]);
    if (batch.length < 100) break;
    page++;
  }
  return all;
}

function overwriteMirrorDoc_(docId, fullText, deps) {
  if (deps && deps.writeDoc) {
    deps.writeDoc(docId, fullText);
    return;
  }
  if (typeof Drive !== 'undefined' && Drive.Files && Drive.Files.update) {
    var blob = Utilities.newBlob(fullText, 'text/plain; charset=utf-8');
    Drive.Files.update({ mimeType: 'application/vnd.google-apps.document' }, docId, blob);
    return;
  }
  var doc = DocumentApp.openById(docId);
  doc.getBody().setText(fullText);
  doc.saveAndClose();
}

function syncDownlinkMirrors_(settings, props, layout, forceRefresh, deps) {
  var logs = [];
  var updatedCount = 0;
  var nowText = formatBeijingTime();

  for (var i = 0; i < BRIDGE_CONFIG.MIRROR_SPECS.length; i++) {
    var spec = BRIDGE_CONFIG.MIRROR_SPECS[i];
    var issue = resolveMirrorIssueNumber_(settings, spec, props, deps);
    var fp = [issue.number, issue.updated_at || '', issue.comments || 0].join('|');
    var prevFp = props.getProperty(spec.fpPropKey) || '';

    if (!forceRefresh && fp === prevFp) {
      continue;
    }

    var comments = fetchAllIssueComments_(settings, issue.number, deps);
    var fullText = assembleMirrorDocText(spec, issue, comments, settings.repo, nowText);
    overwriteMirrorDoc_(layout.mirrorDocIds[spec.key], fullText, deps);

    props.setProperty(spec.fpPropKey, fp);
    updatedCount++;
    var msg = '下行更新 ' + spec.docName + '（Issue #' + issue.number + '，' + fullText.length + ' 字符）';
    logs.push(msg);
    if (typeof Logger !== 'undefined' && Logger.log) {
      Logger.log(msg);
    }
  }

  return { updatedCount: updatedCount, logs: logs };
}

// ============================================================================
// Uplink Sync: Gmail Drafts + Gmail Threads + Drive Inbox + Queue Doc -> GitHub
// ============================================================================

function getOrCreateGmailLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}

function processSourceRequests_(settings, rawText, labelHint, sourceDesc, deps) {
  var parsedRequests = parseRequestsFromText(rawText, labelHint);
  var results = [];
  for (var i = 0; i < parsedRequests.length; i++) {
    var req = parsedRequests[i];
    var up = uploadRequestToGitHub_(settings, req, deps);
    results.push({
      source: sourceDesc,
      request_id: req.request_id,
      target: req.target,
      operation: req.payload.operation,
      repoPath: up.repoPath,
      outboxPath: up.outboxPath,
      uploadStatus: up.status,
      commitSha: up.commitSha
    });
  }
  return results;
}

function syncUplinkGmailDrafts_(settings, logs, uploadedList, deps) {
  var drafts = GmailApp.getDrafts();
  var prefixLower = BRIDGE_CONFIG.GMAIL_SUBJECT_PREFIX.toLowerCase();

  for (var i = 0; i < drafts.length; i++) {
    var draft = drafts[i];
    var msg = draft.getMessage();
    var subject = String(msg.getSubject() || '').trim();
    if (subject.toLowerCase().indexOf(prefixLower) !== 0) {
      continue;
    }
    var body = msg.getPlainBody() || '';
    try {
      var res = processSourceRequests_(settings, body, subject, 'Gmail草稿:' + subject, deps);
      for (var r = 0; r < res.length; r++) {
        uploadedList.push(res[r]);
        logs.push('上行成功 [Gmail草稿] ' + res[r].repoPath + ' (' + res[r].operation + ', ' + res[r].uploadStatus + ')');
      }
      draft.deleteDraft();
    } catch (err) {
      var errText = String(err.message || err);
      logs.push('上行拒绝 [Gmail草稿] ' + subject + ' -> ' + errText);
      var newSubject = BRIDGE_CONFIG.GMAIL_REJECTED_PREFIX + ' ' + subject.replace(/^\[QUANT-INBOX\]\s*/i, '');
      draft.update(msg.getTo() || '', newSubject, '【Bridge 校验失败】\n' + errText + '\n\n--- 原文 ---\n' + body);
      notifyErrorIfConfigured_(settings, 'Gmail 草稿校验失败', '主题：' + subject + '\n原因：' + errText);
    }
  }
}

function syncUplinkGmailThreads_(settings, logs, uploadedList, deps) {
  var query = 'subject:"' + BRIDGE_CONFIG.GMAIL_SUBJECT_PREFIX + '" -label:' +
    BRIDGE_CONFIG.GMAIL_LABEL_SYNCED + ' -label:' + BRIDGE_CONFIG.GMAIL_LABEL_REJECTED + ' -in:drafts -in:trash';
  var threads = GmailApp.search(query, 0, 20);
  if (threads.length === 0) return;

  var syncedLabel = getOrCreateGmailLabel_(BRIDGE_CONFIG.GMAIL_LABEL_SYNCED);
  var rejectedLabel = getOrCreateGmailLabel_(BRIDGE_CONFIG.GMAIL_LABEL_REJECTED);

  for (var i = 0; i < threads.length; i++) {
    var thread = threads[i];
    var msgs = thread.getMessages();
    var latestMsg = msgs[msgs.length - 1];
    var subject = String(latestMsg.getSubject() || '').trim();
    var body = latestMsg.getPlainBody() || '';
    try {
      var res = processSourceRequests_(settings, body, subject, 'Gmail邮件:' + subject, deps);
      for (var r = 0; r < res.length; r++) {
        uploadedList.push(res[r]);
        logs.push('上行成功 [Gmail邮件] ' + res[r].repoPath + ' (' + res[r].operation + ', ' + res[r].uploadStatus + ')');
      }
      thread.addLabel(syncedLabel);
      thread.markRead();
    } catch (err) {
      var errText = String(err.message || err);
      logs.push('上行拒绝 [Gmail邮件] ' + subject + ' -> ' + errText);
      thread.addLabel(rejectedLabel);
      notifyErrorIfConfigured_(settings, 'Gmail 邮件校验失败', '主题：' + subject + '\n原因：' + errText);
    }
  }
}

function readDriveInboxFileText_(file) {
  var mime = file.getMimeType();
  if (mime === MimeType.GOOGLE_DOCS) {
    return DocumentApp.openById(file.getId()).getBody().getText();
  }
  if (mime === MimeType.GOOGLE_SHEETS) {
    var ss = SpreadsheetApp.openById(file.getId());
    var sheet = ss.getSheets()[0];
    var values = sheet.getDataRange().getValues();
    var chunks = [];
    for (var r = 0; r < values.length; r++) {
      for (var c = 0; c < values[r].length; c++) {
        var cell = String(values[r][c] || '').trim();
        if (cell.indexOf('{') !== -1 && cell.indexOf('operation') !== -1) {
          chunks.push(cell);
        }
      }
    }
    return chunks.join('\n\n');
  }
  var name = file.getName().toLowerCase();
  if (mime === MimeType.PLAIN_TEXT || mime === 'application/json' || mime === 'text/markdown' ||
      name.endsWith('.json') || name.endsWith('.txt') || name.endsWith('.md')) {
    return file.getBlob().getDataAsString('UTF-8');
  }
  throw new Error('不支持的 Drive 收件箱文件类型：' + mime + '（' + file.getName() + '）');
}

function syncUplinkDriveInboxFolder_(settings, layout, logs, uploadedList, deps) {
  var iter = layout.inbox.getFiles();
  var files = [];
  while (iter.hasNext()) {
    var f = iter.next();
    if (!f.isTrashed()) files.push(f);
  }
  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    var name = file.getName();
    try {
      var rawText = readDriveInboxFileText_(file);
      var res = processSourceRequests_(settings, rawText, name, 'Drive文件:' + name, deps);
      for (var r = 0; r < res.length; r++) {
        uploadedList.push(res[r]);
        logs.push('上行成功 [Drive收件箱] ' + res[r].repoPath + ' (' + res[r].operation + ', ' + res[r].uploadStatus + ')');
      }
      file.moveTo(layout.processed);
    } catch (err) {
      var errText = String(err.message || err);
      logs.push('上行拒绝 [Drive收件箱] ' + name + ' -> ' + errText);
      if (file.getMimeType() === MimeType.GOOGLE_DOCS) {
        try {
          var doc = DocumentApp.openById(file.getId());
          doc.getBody().insertParagraph(0, '【Bridge 校验失败】' + errText);
          doc.saveAndClose();
        } catch (ignore) {}
      }
      file.moveTo(layout.rejected);
      notifyErrorIfConfigured_(settings, 'Drive 收件箱文件校验失败', '文件：' + name + '\n原因：' + errText);
    }
  }
}

function syncUplinkDriveQueueDoc_(settings, props, layout, logs, uploadedList, deps) {
  var queueFile = DriveApp.getFileById(layout.queueDocId);
  var mtime = String(queueFile.getLastUpdated().getTime());
  if (props.getProperty('LAST_QUEUE_MTIME') === mtime) {
    return;
  }

  var doc = DocumentApp.openById(layout.queueDocId);
  var fullText = doc.getBody().getText();
  var split = extractQueueBody(fullText);
  if (!split.pending) {
    props.setProperty('LAST_QUEUE_MTIME', mtime);
    return;
  }

  var stamp = formatBeijingTime().replace(/[:\s+]/g, '-');
  try {
    var res = processSourceRequests_(settings, split.pending, BRIDGE_CONFIG.INBOX_QUEUE_DOC_NAME, 'Drive队列文档', deps);
    for (var r = 0; r < res.length; r++) {
      uploadedList.push(res[r]);
      logs.push('上行成功 [Drive队列] ' + res[r].repoPath + ' (' + res[r].operation + ', ' + res[r].uploadStatus + ')');
    }
    layout.processed.createFile('queue-synced-' + stamp + '.txt', split.pending, MimeType.PLAIN_TEXT);
    var resetHeader = split.header || (BRIDGE_CONFIG.QUEUE_MARKER);
    doc.getBody().setText(resetHeader + '\n\n');
    doc.saveAndClose();
    props.setProperty('LAST_QUEUE_MTIME', String(DriveApp.getFileById(layout.queueDocId).getLastUpdated().getTime()));
  } catch (err) {
    var errText = String(err.message || err);
    logs.push('上行拒绝 [Drive队列] -> ' + errText);
    layout.rejected.createFile(
      'queue-rejected-' + stamp + '.txt',
      '【Bridge 校验失败】\n' + errText + '\n\n--- 原文 ---\n' + split.pending,
      MimeType.PLAIN_TEXT
    );
    var resetHeaderErr = split.header || (BRIDGE_CONFIG.QUEUE_MARKER);
    doc.getBody().setText(resetHeaderErr + '\n\n');
    doc.saveAndClose();
    props.setProperty('LAST_QUEUE_MTIME', String(DriveApp.getFileById(layout.queueDocId).getLastUpdated().getTime()));
    notifyErrorIfConfigured_(settings, 'Drive 队列文档校验失败', '原因：' + errText + '\n原文已移至 Quant-Rejected。');
  }
}

function pollNewOutboxReceipts_(settings, uploadedList, logs, deps) {
  var fresh = uploadedList.filter(function (x) { return x.uploadStatus === 'uploaded'; });
  if (fresh.length === 0) return false;

  var sleepFn = (deps && deps.sleep) || Utilities.sleep;
  var deadline = Date.now() + BRIDGE_CONFIG.OUTBOX_POLL_MAX_MS;
  var resolved = {};
  var anyReceived = false;

  while (Date.now() < deadline) {
    sleepFn(BRIDGE_CONFIG.OUTBOX_POLL_INTERVAL_MS);
    var remaining = 0;
    for (var i = 0; i < fresh.length; i++) {
      var item = fresh[i];
      if (resolved[item.request_id]) continue;
      var receipt = fetchOutboxReceipt_(settings, item.outboxPath, deps);
      if (receipt) {
        resolved[item.request_id] = receipt;
        anyReceived = true;
        var summary = '回执确认 ' + item.outboxPath + ' -> status=' + receipt.status;
        if (receipt.error) summary += ' | error=' + receipt.error;
        if (receipt.result && receipt.result.event_id) summary += ' | event_id=' + receipt.result.event_id;
        logs.push(summary);
        if (receipt.status === 'rejected') {
          notifyErrorIfConfigured_(settings, 'GitHub 回执拒绝 ' + item.request_id, JSON.stringify(receipt, null, 2));
        }
      } else {
        remaining++;
      }
    }
    if (remaining === 0) break;
  }

  for (var j = 0; j < fresh.length; j++) {
    if (!resolved[fresh[j].request_id]) {
      logs.push('回执等待中 ' + fresh[j].outboxPath + '（GitHub Actions 处理中，下轮自动刷新到 Quant-2）');
    }
  }
  return anyReceived;
}

// ============================================================================
// Public Entrypoints (Run from Apps Script Editor & Time Triggers)
// ============================================================================

/**
 * Main scheduled entrypoint (recommended: every 5 minutes).
 * Runs uplink (Google -> GitHub) then downlink (GitHub -> Google Docs).
 */
function runBridgeCycle() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(25000)) {
    Logger.log('Another QuantItera bridge cycle is already running; skipping.');
    return;
  }
  try {
    var props = PropertiesService.getScriptProperties();
    var settings = getBridgeSettings_(props);
    var layout = ensureWorkspaceLayout_(props);
    var logs = [];
    var uploadedList = [];

    // 1. Uplink: Gmail Drafts -> Gmail Threads -> Drive Inbox Folder -> Drive Queue Doc
    syncUplinkGmailDrafts_(settings, logs, uploadedList);
    syncUplinkGmailThreads_(settings, logs, uploadedList);
    syncUplinkDriveInboxFolder_(settings, layout, logs, uploadedList);
    syncUplinkDriveQueueDoc_(settings, props, layout, logs, uploadedList);

    // 2. If new requests were uploaded, wait briefly for GitHub Actions outbox receipt
    var receivedOutbox = pollNewOutboxReceipts_(settings, uploadedList, logs);

    // 3. Downlink: GitHub Mirror Issues (#37/#38/#39) -> 3 Fixed Google Docs
    var down = syncDownlinkMirrors_(settings, props, layout, receivedOutbox);
    for (var i = 0; i < down.logs.length; i++) {
      logs.push(down.logs[i]);
    }

    // 4. Write log only when something happened (keeps Quant-4 clean & readable)
    if (logs.length > 0) {
      appendSyncLog_(layout.logDocId, logs);
      Logger.log(logs.join('\n'));
    }
  } finally {
    lock.releaseLock();
  }
}

/**
 * Force full downlink refresh immediately (useful right after setup or manual check).
 */
function forceRefreshMirrors() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(25000)) {
    throw new Error('无法获取锁，请稍后重试');
  }
  try {
    var props = PropertiesService.getScriptProperties();
    var settings = getBridgeSettings_(props);
    var layout = ensureWorkspaceLayout_(props);
    var down = syncDownlinkMirrors_(settings, props, layout, true);
    appendSyncLog_(layout.logDocId, ['手动全量刷新完成'].concat(down.logs));
    Logger.log('Force refresh completed:\n' + down.logs.join('\n'));
  } finally {
    lock.releaseLock();
  }
}

/**
 * One-time interactive initialization helper:
 *   1. Before running, set GITHUB_TOKEN in Project Settings -> Script Properties.
 *   2. Verifies GitHub API access, creates/binds Drive folders & Docs, runs full sync.
 */
function initializeAndTest() {
  var props = PropertiesService.getScriptProperties();
  var settings = getBridgeSettings_(props);
  var repoRes = githubRequest_(settings, 'GET', '/repos/' + settings.repo, null, false);
  Logger.log('GitHub 连接正常：' + repoRes.data.full_name + ' (private=' + repoRes.data.private + ')');

  var layout = ensureWorkspaceLayout_(props);
  var down = syncDownlinkMirrors_(settings, props, layout, true);
  var summary = [
    '初始化自检通过！',
    '仓库：' + repoRes.data.full_name,
    'Root Folder ID: ' + layout.root.getId(),
    'Quant-1 Doc ID: ' + layout.mirrorDocIds['protocols'],
    'Quant-2 Doc ID: ' + layout.mirrorDocIds['core-state'],
    'Quant-3 Doc ID: ' + layout.mirrorDocIds['research-workspace'],
    'Quant-4 Log ID: ' + layout.logDocId,
    'Quant-Inbox Folder ID: ' + layout.inbox.getId(),
    'Quant-Inbox-Queue Doc ID: ' + layout.queueDocId
  ].concat(down.logs);

  appendSyncLog_(layout.logDocId, summary);
  Logger.log(summary.join('\n'));
}

/**
 * Installs a single 5-minute time-driven trigger for runBridgeCycle() (idempotent).
 */
function installTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'runBridgeCycle') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('runBridgeCycle')
    .timeBased()
    .everyMinutes(5)
    .create();
  Logger.log('已安装 5 分钟定时触发器：runBridgeCycle');
}

/**
 * Removes all triggers installed by this bridge.
 */
function uninstallTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'runBridgeCycle') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  Logger.log('已移除所有 runBridgeCycle 触发器');
}

// CommonJS export hook for local Node.js unit tests (ignored in Apps Script V8)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    BRIDGE_CONFIG: BRIDGE_CONFIG,
    sanitizeRawText: sanitizeRawText,
    parseHintFromLabel: parseHintFromLabel,
    extractJsonCandidates: extractJsonCandidates,
    parseJsonStrict: parseJsonStrict,
    validateBridgeRequest: validateBridgeRequest,
    parseRequestsFromText: parseRequestsFromText,
    assembleMirrorDocText: assembleMirrorDocText,
    extractQueueBody: extractQueueBody,
    uploadRequestToGitHub_: uploadRequestToGitHub_,
    fetchOutboxReceipt_: fetchOutboxReceipt_,
    resolveMirrorIssueNumber_: resolveMirrorIssueNumber_,
    syncDownlinkMirrors_: syncDownlinkMirrors_,
    processSourceRequests_: processSourceRequests_,
    pollNewOutboxReceipts_: pollNewOutboxReceipts_
  };
}
