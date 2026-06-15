function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const state = {
  date: localDateString(),
  data: null,
  reportText: "",
  reportId: null,
  reportMeta: null,
  reportDirty: false,
  agentDocs: "",
  templateDetailItem: null,
  reportFilters: {
    kind: "all",
    range: "",
    query: "",
    from: "",
    to: "",
  },
  filter: "all",
  timelineRange: "today",
  timelineCategoryMode: "bar",
  appChartMode: "bar",
  appPeriod: "day",
  appUsage: null,
  appUsageMeta: { days: 1, start_day: "", end_day: "", period: "day" },
  appCustomRange: { from: "", to: "" },
  heatmapRange: { from: "", to: "" },
  showPreviousRhythm: false,
  settingsTouched: false,
  dayNoteTouched: false,
  summarySeq: 0,
  logs: null,
  requestLogs: null,
  requestLogPage: 1,
  reportRangeTouched: false,
  search: {
    query: "",
    category: "",
    from: "",
    to: "",
    results: [],
    searched: false,
  },
  manualOpen: false,
  detailItem: null,
  currentView: "overview",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const pageMeta = {
  overview: { label: "今日工作", title: "你只管工作，日报交给我" },
  trends: { label: "趋势洞察", title: "近 30 天工作节奏" },
  heatmap: { label: "时段热力图", title: "时段热力图" },
  timeline: { label: "工作时间线", title: "工作时间线" },
  apps: { label: "应用记录", title: "应用记录" },
  report: { label: "生成报告", title: "生成报告" },
  "reports-history": { label: "历史报告", title: "历史报告" },
  agent: { label: "接入 Agent", title: "接入 Agent" },
  subscription: { label: "订阅", title: "订阅" },
  invite: { label: "邀请激励", title: "邀请激励" },
  privacy: { label: "隐私保护", title: "隐私保护" },
  support: { label: "客服", title: "客服" },
  notifications: { label: "通知中心", title: "通知中心" },
  help: { label: "帮助", title: "帮助" },
  settings: { label: "设置", title: "设置" },
};

const pageAliases = {
  today: "overview",
  work: "overview",
  "今日工作": "overview",
  "generate-report": "report",
  "report-config": "report",
  "生成报告": "report",
  "work-timeline": "timeline",
  "工作时间线": "timeline",
  "time-heatmap": "heatmap",
  "时段热力图": "heatmap",
  "app-records": "apps",
  applications: "apps",
  "应用记录": "apps",
  history: "reports-history",
  "report-history": "reports-history",
  "历史报告": "reports-history",
  "agent-access": "agent",
  "接入agent": "agent",
  "接入-agent": "agent",
};

function decodeViewName(value) {
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
}

function normalizeView(view) {
  const decoded = decodeViewName(String(view || "").replace(/^#/, "").trim());
  const lowered = decoded.toLowerCase();
  const compact = lowered.replace(/\s+/g, "");
  if (pageMeta[decoded]) return decoded;
  if (pageMeta[lowered]) return lowered;
  return pageAliases[decoded] || pageAliases[lowered] || pageAliases[compact] || "overview";
}

function navigateTo(view, options = {}) {
  const nextView = normalizeView(view);
  state.currentView = nextView;
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === nextView));
  $$("[data-section]").forEach((section) => {
    const active = section.dataset.section === nextView;
    section.hidden = !active;
    section.classList.toggle("page-active", active);
  });
  const meta = pageMeta[nextView] || pageMeta.overview;
  $(".page-label").textContent = meta.label;
  $(".topbar h2").textContent = meta.title;
  document.body.dataset.view = nextView;
  if (!options.skipHistory) {
    const hash = `#${nextView}`;
    if (window.location.hash !== hash) {
      const method = options.replace ? "replaceState" : "pushState";
      window.history[method](null, "", hash);
    }
  }
  window.scrollTo({ top: 0, behavior: options.instant ? "auto" : "smooth" });
}

const defaultWorkCategories = [
  "编码开发",
  "会议沟通",
  "文档写作",
  "阅读学习",
  "邮件即时通讯",
  "设计",
  "数据分析",
  "网页浏览",
];

function currentWorkCategories() {
  return new Set(state.data?.work_categories || state.data?.settings?.work_categories || defaultWorkCategories);
}

function categoryColor(name) {
  const palette = {
    编码开发: "#0f766e",
    会议沟通: "#2563eb",
    文档写作: "#7c3aed",
    阅读学习: "#0891b2",
    邮件即时通讯: "#db2777",
    设计: "#ea580c",
    数据分析: "#4f46e5",
    网页浏览: "#65a30d",
    娱乐休息: "#64748b",
    其他: "#475569",
  };
  return palette[name] || "#475569";
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  window.clearTimeout(toast._timer);
  toast._timer = window.setTimeout(() => el.classList.remove("show"), 1800);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `请求失败：${response.status}`);
  }
  return data;
}

async function textApi(path) {
  const response = await fetch(path);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `请求失败：${response.status}`);
  }
  return text;
}

async function loadSummary() {
  const seq = ++state.summarySeq;
  const params = new URLSearchParams({ date: state.date });
  if (state.heatmapRange.from) params.set("heatmap_from", state.heatmapRange.from);
  if (state.heatmapRange.to) params.set("heatmap_to", state.heatmapRange.to);
  const data = await api(`/api/summary?${params.toString()}`);
  if (seq !== state.summarySeq) return;
  state.data = data;
  render();
  loadAgentDocs().catch(() => {});
}

function render() {
  const data = state.data;
  if (!data) return;

  renderStatus(data.recording);
  renderSettings(data.settings);
  renderDesktopApp(data.desktop_app);
  renderHealth(data.health);
  renderAgent(data.model_config, data.health, data.project_context, data.settings);
  renderPrivacy(data);
  renderHelp(data);
  renderProductModules(data);
  renderNotifications(data.notifications || []);
  renderPermissions(data.permissions);
  renderAutostart(data.autostart);
  renderAutoReport(data.auto_report);
  renderStorage(data.storage);
  renderDisplays(data.displays);
  renderOverviewDisplays(data.displays);
  renderStyles(data.styles);
  renderTemplateCatalog(data.style_catalog || []);
  renderSearchControls(data.activity_categories || []);
  renderManualControls(data.activity_categories || []);
  renderOverview(data);
  renderProductivity(data.productivity);
  renderTrends(data.trends);
  renderTimeHeatmap(data.time_heatmap);
  renderAppUsage(data.app_usage || []);
  if (state.appPeriod === "day") {
    state.appUsage = data.app_usage || [];
    state.appUsageMeta = { days: 1, start_day: data.day, end_day: data.day, period: "day" };
  }
  renderAppRecords(state.appUsage || data.app_usage || [], state.appUsageMeta);
  renderActivityRhythm(data.segments || data.items || [], data.time_heatmap);
  renderTimeline(data.segments || data.items);
  renderSearchResults();
  renderReports(data.reports || []);
  renderReportHistoryTable(data.reports || []);
  renderChat(data.chat || []);
  renderDays(data.days || []);
  renderReportEditState();
  renderDayNote(data.day_note);
}

function renderStatus(recording) {
  const running = Boolean(recording.running);
  const stopping = Boolean(recording.stopping);
  const failed = Boolean(recording.last_error);
  $("#recordButton").textContent = stopping ? "正在暂停" : running ? "暂停记录" : "开始记录";
  $("#recordButton").disabled = stopping;
  $("#recordButton").classList.toggle("is-running", running);
  $("#recordButton").classList.toggle("has-error", failed);
  $("#sideDot").classList.toggle("running", running);
  $("#sideDot").classList.toggle("error", failed);
  $("#sideStatus").textContent = failed ? "记录异常" : stopping ? "正在暂停" : running ? "正在记录" : "已暂停";
  $("#sideMessage").textContent = failed ? recording.last_error : (recording.message || "等待操作");
  $("#providerStatus").textContent = recording.provider === "openai" ? "Hermes 本地网关" : "Ollama 本地模型";
}

function renderSettings(settings) {
  $("#modelProvider").textContent = settings.provider;
  $("#visionModel").textContent = settings.vision_model;
  $("#dataDir").textContent = settings.data_dir;
  $("#settingsPath").textContent = settings.settings_path || "-";
  if (!state.settingsTouched && !isSettingsFocused()) {
    $("#modelProviderInput").value = settings.provider || "openai";
    $("#modelBaseUrlInput").value = settings.base_url || "";
    $("#modelNameInput").value = settings.text_model || settings.vision_model || "";
    $("#autoRecordEnabled").checked = Boolean(settings.auto_record_enabled);
    $("#languageInput").value = settings.language || "zh-CN";
    $("#aiAnalysisSourceInput").value = settings.ai_analysis_source || "screen";
    $("#quickEnterInput").checked = settings.quick_enter_enabled !== false;
    $("#dockIconInput").checked = settings.show_dock_icon !== false;
    $("#memoryInput").checked = settings.memory_enabled !== false;
    $("#woodfishInput").checked = Boolean(settings.woodfish_enabled);
    $("#analysisPromptInput").value = settings.analysis_prompt || "";
    $("#privacyModeInput").checked = settings.privacy_mode !== false;
    $("#keepShotsInput").checked = Boolean(settings.keep_shots);
    $("#keepShotsInput").disabled = settings.privacy_mode !== false;
    $("#shotRetentionInput").value = settings.shot_retention_days ?? 7;
    $("#intervalInput").value = settings.capture_interval || 120;
    $("#idlePauseInput").value = settings.idle_pause_after || 600;
    $("#captureScopeInput").value = settings.capture_scope || "primary";
    $("#ignoreAppsInput").value = (settings.ignore_apps || []).join(", ");
    $("#ignoreKeywordsInput").value = (settings.ignore_keywords || []).join(", ");
    $("#activityCategoriesInput").value = (settings.activity_categories || []).join(", ");
    $("#workCategoriesInput").value = (settings.work_categories || []).join(", ");
    $("#customReportStylesInput").value = formatStyleMap(settings.custom_report_styles || {});
  }
}

function renderDesktopApp(app) {
  if (!app) return;
  const installed = Boolean(app.installed);
  $("#desktopAppInstallStatus").textContent = installed ? "已安装" : "未安装";
  $("#desktopAppInstallStatus").className = installed ? "good" : "bad";
  $("#desktopAppMode").textContent = installed ? (app.mode || "桌面窗口") : "等待安装";
  $("#desktopAppBundle").textContent = app.bundle_id || "-";
  $("#desktopAppPath").textContent = app.app_path || "-";
  $("#desktopAppUpdated").textContent = installed
    ? `最近更新：${formatDateTime(app.modified) || "-"} · ${app.display_name || "书赫日报助手"}${app.version ? ` ${app.version}` : ""}`
    : "生成并安装后，可在这里确认本机应用状态。";
  $("#openDesktopApp").disabled = !installed;
}

function renderDisplays(displays) {
  const select = $("#captureScopeInput");
  const list = $("#displayList");
  if (!select || !list) return;
  const items = displays?.items || [];
  const selected = displays?.selected || state.data?.settings?.capture_scope || "primary";
  if (items.length) {
    const previous = select.value || selected;
    select.innerHTML = "";
    for (const display of items) {
      const option = document.createElement("option");
      option.value = display.scope;
      option.textContent = display.name;
      select.appendChild(option);
    }
    select.value = items.some((item) => item.scope === previous) ? previous : selected;
  }
  $("#displayCount").textContent = displays?.ok ? displayScopeSummary(items, selected) : "检测失败";
  list.innerHTML = items.length
    ? items
        .filter((item) => item.index > 0)
        .map(
          (item) => `
          <button class="display-item ${item.scope === select.value ? "selected" : ""}" type="button" data-display-scope="${escapeHtml(item.scope)}">
            <strong>${escapeHtml(item.name)}</strong>
            <span>${escapeHtml(`${item.width} × ${item.height}`)}${item.primary ? " · 主显示器" : ""}</span>
            ${renderDisplayMetaChips(item, item.scope === select.value)}
            <small>坐标 ${escapeHtml(`${item.left}, ${item.top}`)}</small>
          </button>
        `,
        )
        .join("")
    : `<div class="empty display-empty">${escapeHtml(displays?.error || "暂未检测到显示器。")}</div>`;
}

function renderOverviewDisplays(displays) {
  const count = $("#overviewDisplayCount");
  const list = $("#overviewDisplayList");
  if (!count || !list) return;
  const items = displays?.items || [];
  const selected = displays?.selected || state.data?.settings?.capture_scope || "primary";
  const physical = items.filter((item) => Number(item.index || 0) > 0);
  count.textContent = displays?.ok ? displayScopeSummary(items, selected) : "检测失败";
  list.innerHTML = items.length
    ? physical
        .map(
          (item) => `
          <div class="display-item overview-display-item ${displaySelected(item, selected) ? "selected" : ""}">
            <div class="display-index">${item.index}</div>
            <div class="overview-display-body">
              <div class="overview-display-title">
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(displayStatusLabel(item, selected))}</span>
              </div>
              <div class="overview-display-facts">
                <span>${escapeHtml(`${item.width} × ${item.height}`)}</span>
                <span>${escapeHtml(`坐标 ${item.left}, ${item.top}`)}</span>
                <span>${escapeHtml(displayCaptureHint(item, selected, physical.length))}</span>
              </div>
              ${renderDisplayMetaChips(item, displaySelected(item, selected))}
            </div>
          </div>
        `,
        )
        .join("")
    : `<div class="empty display-empty">${escapeHtml(displays?.error || "暂未检测到显示器。")}</div>`;
}

function displaySelected(item, selected) {
  return item.scope === selected || selected === "all";
}

function displayStatusLabel(item, selected) {
  if (selected === "all") return "全部采集";
  if (item.scope === selected) return "当前采集";
  if (item.primary) return "主显示器";
  return "未采集";
}

function renderDisplayMetaChips(item, selected = false) {
  const chips = [];
  if (item.primary) chips.push("主显示器");
  if (selected) chips.push("当前采集");
  if (item.width && item.height) chips.push(`${item.width}×${item.height}`);
  return chips.length
    ? `<div class="display-meta-chips">${chips.map((chip) => `<em>${escapeHtml(chip)}</em>`).join("")}</div>`
    : "";
}

function displayScopeSummary(items = [], selected = "primary") {
  const physical = items.filter((item) => Number(item.index || 0) > 0);
  const count = `${physical.length} 台`;
  if (!physical.length) return count;
  if (selected === "all") return `${count} · 全部采集`;
  if (selected === "primary") return `${count} · 主显示器采集`;
  const active = physical.find((item) => item.scope === selected);
  return active ? `${count} · 采集 ${active.name}` : count;
}

function displayCaptureHint(item, selected, count) {
  if (selected === "all") return count > 1 ? "当前会采集全部显示器" : "当前默认采集";
  if (item.scope === selected) return "当前采集范围";
  if (item.primary) return "主显示器，可在设置中切换";
  return "可在设置中选择";
}

function renderHealth(health) {
  const grid = $("#healthGrid");
  if (!grid || !health) return;
  const recording = state.data?.recording || {};
  const cards = [
    {
      label: "整体状态",
      value: health.ok ? "可用" : "需处理",
      detail: health.ok ? "采集与报告基础条件已就绪" : (health.blockers || []).join("；"),
      state: health.ok ? "good" : "bad",
    },
    {
      label: "模型网关",
      value: health.model?.ready ? "已配置" : "未配置",
      detail: `${health.model?.provider || "-"} · ${health.model?.model || "-"}`,
      state: health.model?.ready ? "good" : "bad",
    },
    {
      label: "鉴权",
      value: health.model?.api_key_present ? "已配置" : "缺失",
      detail: health.model?.base_url || "-",
      state: health.model?.api_key_present ? "good" : "bad",
    },
    {
      label: "本地存储",
      value: health.storage?.data_writable ? "可写" : "不可写",
      detail: health.storage?.data_dir || "-",
      state: health.storage?.data_writable && health.storage?.shots_writable ? "good" : "bad",
    },
    {
      label: "记录器",
      value: recording.last_error ? "异常" : recording.running ? "运行中" : "已暂停",
      detail: recording.last_error || recording.message || "等待操作",
      state: recording.last_error ? "bad" : "good",
    },
  ];
  grid.innerHTML = cards
    .map(
      (card) => `
      <div class="health-card ${card.state}">
        <span>${escapeHtml(card.label)}</span>
        <strong>${escapeHtml(card.value)}</strong>
        <small>${escapeHtml(card.detail || "-")}</small>
      </div>
    `,
    )
    .join("");
}

function renderAgent(modelConfig, health, projectContext, settings) {
  if (!$("#agentProvider")) return;
  const cfg = modelConfig || {};
  const serviceUrl = window.location.origin || "http://127.0.0.1:8765";
  $("#agentProvider").textContent = cfg.provider === "openai" ? "OpenAI-compatible / Hermes" : (cfg.provider || "-");
  $("#agentModel").textContent = cfg.model || "-";
  $("#agentBaseUrl").textContent = cfg.base_url || "-";
  $("#agentServiceUrl").textContent = serviceUrl;
  $("#agentDocsUrl").textContent = `${serviceUrl}/api/agent-docs`;
  $("#agentKeyStatus").textContent = cfg.provider === "openai"
    ? (cfg.api_key_present ? `已配置${cfg.api_key_source === "keychain" ? "（钥匙串）" : ""}` : "缺失")
    : "无需 key";
  $("#agentStatusText").textContent = health?.ok ? "已就绪" : "需要处理";
  $("#agentStatusText").className = `section-meta ${health?.ok ? "good" : "bad"}`;
  renderProjectContext(projectContext, settings);
}

function renderAgentDocs(text) {
  const preview = $("#agentDocsPreview");
  if (!preview) return;
  const serviceUrl = window.location.origin || "http://127.0.0.1:8765";
  const intro = [
    "请根据下面的说明把书赫日报助手的 API 接入成你的 skill，保存到你的 skill 技能中。",
    "",
    "【服务信息】",
    `本地 HTTP 服务地址：${serviceUrl}`,
    "",
    "【强制规则 — 必须遵守】",
    `1. 每次处理用户请求前，你必须先调用 GET ${serviceUrl}/api/agent-docs 获取最新 API 文档。`,
    `   如果只拿到了服务根地址，也可以用 GET ${serviceUrl}/?format=agent 读取同一份 Markdown 文档。`,
    "   该接口返回的是一份 Markdown 格式的文档，其中详细说明当前所有可用接口、参数和响应结构。",
    "   绝对不可以依赖记忆中的固定 API 列表，必须以实时拉取的文档为准。",
    "",
    "2. 读取 Markdown 文档后，解析接口列表、参数定义、请求示例和响应结构，再动态选择接口并构造请求。",
    "",
    "3. 所有能力都只读取本机数据；不要把数据库、截图或密钥发送到外部服务，除非用户明确要求。",
    "",
    "【已知能力范围】（仅供参考，实际以 GET /api/agent-docs 返回的 Markdown 文档为准）",
    "• 今日工作、时间线、应用记录、报告历史、日报生成和项目上下文查询。",
    "",
  ].join("\n");
  preview.textContent = text ? `${intro}${text}` : `${intro}正在读取本地 API 文档...`;
}

async function loadAgentDocs({ notify = false } = {}) {
  if (!$("#agentDocsPreview")) return;
  const text = await textApi("/api/agent-docs");
  state.agentDocs = text;
  renderAgentDocs(text);
  if (notify) toast("Agent 文档已刷新");
}

function renderProjectContext(projectContext, settings) {
  if (!$("#projectPathsInput")) return;
  const paths = projectContext?.paths || [];
  if (!state.settingsTouched && document.activeElement !== $("#projectPathsInput")) {
    $("#projectPathsInput").value = (settings?.project_paths || []).join("\n");
  }
  const valid = paths.filter((item) => item.exists);
  const missing = paths.filter((item) => !item.exists);
  $("#agentContextStatus").textContent = valid.length ? "已接入" : "未配置";
  $("#agentContextStatus").className = valid.length ? "good" : "bad";
  $("#agentContextPaths").textContent = `${valid.length}/${paths.length || 0} 个`;
  $("#agentContextFiles").textContent = `${projectContext?.files || 0} 个`;
  $("#agentContextNote").textContent = missing.length
    ? `未找到：${missing.map((item) => item.path).join("；")}`
    : valid.length
      ? `追问时最多读取 ${projectContext?.max_files || 12} 个安全文本文件；截图和密钥不会作为项目上下文读取。`
      : "每行一个项目目录；追问日报助手会读取少量安全文本文件作为本地上下文。";
}

function renderPrivacy(data) {
  if (!$("#privacyStatusText")) return;
  const settings = data.settings || {};
  const storage = data.storage || {};
  const modelConfig = data.model_config || {};
  const privacyOk = settings.privacy_mode !== false && !settings.keep_shots && Number(storage.shot_files || 0) === 0;
  $("#privacyStatusText").textContent = privacyOk ? "隐私模式已开启" : "需要检查";
  $("#privacyStatusText").className = `section-meta ${privacyOk ? "good" : "bad"}`;
  $("#privacyDataStatus").textContent = "本地 SQLite";
  $("#privacyDataMeta").textContent = `${storage.activities || 0} 条活动 · 数据目录 ${settings.data_dir || storage.data_dir || "-"}`;
  $("#privacyShotsStatus").textContent = settings.privacy_mode !== false ? "分析后即删" : (settings.keep_shots ? "正在留存截图" : "不留存截图");
  $("#privacyShotsMeta").textContent = `${storage.shot_files || 0} 个截图文件 · ${storage.shot_size || "0 B"}`;
  $("#privacyKeyStatus").textContent = modelConfig.api_key_present
    ? (modelConfig.api_key_source === "keychain" ? "系统钥匙串" : "环境变量")
    : "未配置";
  $("#privacyKeyMeta").textContent = modelConfig.keychain_available ? "macOS Keychain 可用" : "当前平台未检测到 Keychain";
  $("#privacyNetworkStatus").textContent = "直连网关";
  $("#privacyNetworkMeta").textContent = `${modelConfig.provider || "-"} · ${modelConfig.base_url || "-"}`;
}

function renderHelp(data) {
  if (!$("#helpHealthStatus")) return;
  const health = data.health || {};
  const permissions = data.permissions || {};
  const settings = data.settings || {};
  const storage = data.storage || {};
  const model = health.model || data.model_config || {};
  const screenOk = permissions.screen_recording?.state === "granted";
  const accessOk = permissions.accessibility?.state === "granted";
  const privacyOk = settings.privacy_mode !== false && !settings.keep_shots && Number(storage.shot_files || 0) === 0;
  $("#helpHealthStatus").textContent = health.ok ? "已就绪" : "需要处理";
  $("#helpHealthStatus").className = `section-meta ${health.ok ? "good" : "bad"}`;
  $("#helpPermissionStatus").textContent = screenOk && accessOk
    ? "已授权"
    : `屏幕录制${screenOk ? "已开" : "未开"} · 辅助功能${accessOk ? "已开" : "未开"}`;
  $("#helpModelStatus").textContent = model.ready
    ? `${model.provider || "-"} · ${model.model || "-"}`
    : "未就绪";
  $("#helpPrivacyStatus").textContent = privacyOk ? "隐私模式正常" : "需要检查截图留存";
  renderReleaseInfo(data.release);
}

function renderProductModules(data) {
  const release = data.release || {};
  const url = release.url || "https://github.com/cuishuhe5-glitch/shuhe-riji/releases";
  const inviteUrl = $("#inviteReleaseUrl");
  if (inviteUrl) inviteUrl.textContent = url;
  renderVersionList(release);
}

function renderVersionList(release) {
  const list = $("#versionList");
  if (!list) return;
  const version = release?.version || "v0.1.0";
  list.innerHTML = `
    <div class="version-item">
      <span>${escapeHtml(version)}</span>
      <strong>小黑式模块补齐</strong>
      <p>新增订阅、邀请激励、客服、通知中心入口；补齐设置里的识别当前屏幕、数据导入、清理历史和版本日志。</p>
    </div>
    <div class="version-item">
      <span>v0.1.0</span>
      <strong>本地日报助手</strong>
      <p>支持本机屏幕记录、AI 识别、日报/周报/月报、历史报告、Agent 接入、隐私模式和跨平台安装包。</p>
    </div>
  `;
}

function renderNotifications(notifications) {
  const list = $("#notificationList");
  if (!list) return;
  list.innerHTML = notifications.length
    ? notifications
        .map((item) => `
          <div class="notification-item ${escapeHtml(item.level || "info")}">
            <div>
              <strong>${escapeHtml(item.title || "提醒")}</strong>
              <p>${escapeHtml(item.message || "")}</p>
            </div>
            <span>${escapeHtml(item.time || "现在")}</span>
          </div>
        `)
        .join("")
    : `<div class="empty">当前没有新的提醒。</div>`;
}

function renderReleaseInfo(release) {
  const grid = $("#releaseGrid");
  if (!grid || !release) return;
  const page = $("#releasePageLink");
  page.href = release.url || "#";
  page.textContent = release.version ? `打开 ${release.version}` : "打开发布页";
  const status = $("#releaseCheckStatus");
  if (status && !status.dataset.checked) {
    status.textContent = `当前发布版本 ${release.version || "-"}，可直接下载安装包。`;
    status.className = "release-check-status";
  }
  const assets = release.assets || [];
  grid.innerHTML = assets.length
    ? assets
        .map((asset) => {
          const sha = asset.sha256 ? `${asset.sha256.slice(0, 12)}...${asset.sha256.slice(-8)}` : "见 SHA256SUMS";
          return `
            <a class="release-item" href="${escapeHtml(asset.url || "#")}" target="_blank" rel="noreferrer">
              <span>${escapeHtml(asset.name || asset.filename || "下载")}</span>
              <strong>${escapeHtml(asset.filename || "-")}</strong>
              <small>SHA256 ${escapeHtml(sha)}</small>
            </a>
          `;
        })
        .join("")
    : `<div class="empty release-empty">还没有发布包。</div>`;
}

function renderReleaseCheck(result) {
  const status = $("#releaseCheckStatus");
  if (!status || !result) return;
  status.dataset.checked = "true";
  if (!result.ok) {
    status.textContent = `暂时无法检查更新：${result.message || "未知原因"}`;
    status.className = "release-check-status warn";
    return;
  }
  const current = result.current_version || "-";
  const latest = result.latest_version || "-";
  const checked = result.checked_at ? ` · ${result.checked_at}` : "";
  if (result.update_available) {
    status.textContent = `发现新版本 ${latest}，当前是 ${current}${checked}`;
    status.className = "release-check-status good";
    const page = $("#releasePageLink");
    if (page && result.latest_url) {
      page.href = result.latest_url;
      page.textContent = `打开 ${latest}`;
    }
    return;
  }
  status.textContent = `当前已是最新版本 ${current}${checked}`;
  status.className = "release-check-status good";
}

async function checkReleaseUpdate() {
  const button = $("#checkReleaseUpdate");
  if (button) {
    button.disabled = true;
    button.textContent = "检查中";
  }
  try {
    const data = await api("/api/release/check");
    renderReleaseCheck(data.release_check);
    toast(data.release_check?.ok ? "更新检查完成" : "暂时无法检查更新");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "检查更新";
    }
  }
}

function renderPermissions(permissions) {
  if (!permissions) return;
  setPermission(
    "screenPermission",
    permissions.screen_recording?.state,
    permissions.screen_recording?.message,
  );
  setPermission(
    "accessibilityPermission",
    permissions.accessibility?.state,
    permissions.accessibility?.message,
  );
}

function renderAutostart(autostart) {
  if (!autostart) return;
  const dot = $("#autostartDot");
  const installed = Boolean(autostart.installed);
  const loaded = Boolean(autostart.loaded);
  dot.classList.remove("granted", "missing", "unknown");
  dot.classList.add(installed && loaded ? "granted" : installed ? "unknown" : "missing");
  $("#autostartStatus").textContent = installed
    ? loaded
      ? "开机自启已启用"
      : "已安装，等待下次启动"
    : "开机自启未启用";
  $("#autostartMeta").textContent = installed
    ? "登录后自动启动菜单栏助手和本地面板。"
    : "启用后会创建本机 LaunchAgent。";
  $("#autostartPath").textContent = autostart.plist || "-";
  $("#enableAutostart").disabled = installed && loaded;
  $("#disableAutostart").disabled = !installed;
}

function setPermission(prefix, state = "unknown", message = "未检测") {
  const dot = $(`#${prefix}Dot`);
  const text = $(`#${prefix}Text`);
  dot.classList.remove("granted", "missing", "unknown");
  dot.classList.add(state === "granted" || state === "not_required" ? "granted" : state === "missing" ? "missing" : "unknown");
  text.textContent = message;
}

function renderStorage(storage) {
  if (!storage) return;
  $("#shotStorage").textContent = `${storage.shot_files} 个 / ${storage.shot_size}`;
  $("#activityStorage").textContent = `${storage.activities} 条，其中 ${storage.activities_with_shots} 条带截图`;
}

function renderLogs(logs) {
  const path = $("#logsPath");
  const list = $("#logList");
  if (!path || !list) return;
  path.textContent = logs?.dir || "-";
  const files = logs?.files || [];
  list.innerHTML = files.length
    ? files
        .map(
          (file) => `
          <article class="log-item">
            <div class="log-item-head">
              <strong>${escapeHtml(file.name)}</strong>
              <span>${escapeHtml(formatLogMeta(file))}</span>
            </div>
            <pre>${escapeHtml(file.text || "暂无内容")}</pre>
          </article>
        `,
        )
        .join("")
    : `<div class="empty log-empty">还没有日志文件。启动菜单栏助手或开机自启后会写入这里。</div>`;
}

function renderRequestLogs(requestLogs) {
  const table = $("#requestLogTable");
  if (!table) return;
  const items = requestLogs?.items || [];
  const page = requestLogs?.page || 1;
  const pages = requestLogs?.pages || 1;
  state.requestLogPage = page;
  $("#requestLogMeta").textContent = `共 ${requestLogs?.total || 0} 条记录，每页 ${requestLogs?.page_size || 20} 条`;
  $("#requestLogPage").textContent = `第 ${page} 页 / 共 ${pages} 页`;
  $("#requestLogPrev").disabled = page <= 1;
  $("#requestLogNext").disabled = page >= pages;
  table.innerHTML = items.length
    ? `
      <div class="request-log-head">
        <span>时间</span>
        <span>方法</span>
        <span>路径</span>
        <span>参数</span>
        <span>状态</span>
        <span>来源</span>
      </div>
      ${items
        .map(
          (item) => `
          <div class="request-log-row">
            <span>${escapeHtml(formatDateTime(item.time))}</span>
            <strong>${escapeHtml(item.method || "-")}</strong>
            <span>${escapeHtml(item.path || "-")}</span>
            <span>${escapeHtml(formatRequestParams(item.params))}</span>
            <span class="${Number(item.status || 0) >= 400 ? "bad" : "good"}">${escapeHtml(String(item.status || "-"))}</span>
            <span>${escapeHtml(item.source || "-")}</span>
          </div>
        `,
        )
        .join("")}
    `
    : `<div class="empty request-log-empty">暂无请求记录。</div>`;
}

function renderStyles(styles) {
  const select = $("#styleSelect");
  const autoSelect = $("#autoReportStyle");
  const previous = normalizeStyleName(select.value) || "标准";
  const autoPrevious = normalizeStyleName(autoSelect.value || state.data?.auto_report?.style) || "标准";
  select.innerHTML = "";
  autoSelect.innerHTML = "";
  for (const style of styles) {
    const option = document.createElement("option");
    option.value = style;
    option.textContent = style;
    select.appendChild(option);
    autoSelect.appendChild(option.cloneNode(true));
  }
  select.value = styles.includes(previous) ? previous : styles[0] || "标准";
  autoSelect.value = styles.includes(autoPrevious) ? autoPrevious : select.value;
  renderReportKindTabs();
  renderStyleHint();
  renderAutoReport(state.data?.auto_report);
}

function renderReportKindTabs() {
  const value = $("#kindSelect")?.value || "day";
  $$("#reportKindTabs [data-kind-value]").forEach((button) => {
    button.classList.toggle("active", button.dataset.kindValue === value);
  });
  syncReportDateRange();
  renderTemplateSelection();
}

function renderStyleHint() {
  const descriptions = state.data?.style_descriptions || {};
  const style = $("#styleSelect").value;
  $("#styleHint").textContent = descriptions[style] || "选择报告模板后会显示要求。";
  renderTemplateSelection();
  renderReportKindTabs();
}

function renderTemplateCatalog(catalog) {
  const grid = $("#templateGrid");
  if (!grid) return;
  const items = catalog.length
    ? catalog
    : (state.data?.styles || []).map((name) => ({
        name,
        prompt: state.data?.style_descriptions?.[name] || "",
        group: "内置",
        audience: "通用",
        preview: state.data?.style_descriptions?.[name] || "",
        source: "内置",
      }));
  $("#templateCount").textContent = `${items.length} 个模板`;
  grid.innerHTML = items
    .map(
      (item) => `
        <article class="template-card" role="button" tabindex="0" data-template-name="${escapeHtml(item.name)}">
          <span class="template-check">✓</span>
          <strong>${escapeHtml(item.name)}</strong>
          <small>${escapeHtml(templateCardSummary(item))}</small>
          <div class="template-card-foot">
            <em>${escapeHtml(templateSourceLabel(item))}</em>
            <span class="template-card-audience">${escapeHtml(item.audience || "通用")}</span>
            <button class="template-detail-button" type="button" data-template-detail="${escapeHtml(item.name)}">详情</button>
          </div>
        </article>
      `,
    )
    .join("")
    + `
      <article class="template-card template-add-card" role="button" tabindex="0" data-template-add>
        <span class="template-add-icon">+</span>
        <strong>添加自定义模板</strong>
        <small>写下自己的汇报口径，保存后会出现在这里。</small>
        <div class="template-card-foot">
          <em>自定义</em>
          <span>去设置</span>
        </div>
      </article>
    `;
  renderTemplateSelection();
}

function renderTemplateSelection() {
  const select = $("#styleSelect");
  const selected = select?.value || "";
  $$(".template-card").forEach((button) => {
    button.classList.toggle("selected", button.dataset.templateName === selected);
  });
  const catalog = state.data?.style_catalog || [];
  const item = catalog.find((entry) => entry.name === selected);
  const source = $("#templateSource");
  const preview = $("#templatePreview");
  if (source) source.textContent = item ? `${templateSourceLabel(item)} · ${item.audience || "通用"}` : "-";
  if (preview) preview.innerHTML = renderTemplatePreview(item, selected);
  syncReportConfigSummary();
}

function templateSourceLabel(item) {
  const value = item?.source || item?.group || "内置";
  return value.includes("云") ? "云端" : value;
}

function templateCardSummary(item) {
  const text = String(item?.prompt || item?.preview || item?.audience || "选择后按此口径生成报告。")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > 54 ? `${text.slice(0, 54)}...` : text;
}

function renderTemplatePreview(item, selected) {
  if (!item && !selected) return `<div class="empty">选择模板后查看结构。</div>`;
  const kind = reportKindLabel($("#kindSelect")?.value || "day");
  const { start, end } = currentReportRange($("#kindSelect")?.value || "day");
  const title = item?.name || selected || "报告模板";
  const source = templateSourceLabel(item);
  const instructionText = $("#reportInstructionInput")?.value.trim() || "";
  const instructionStatus = instructionText ? "自定义指令已启用" : "未加自定义指令";
  const lines = String(item?.preview || state.data?.style_descriptions?.[selected] || "今日工作\n- ...\n\n进展与产出\n- ...\n\n明日计划\n- ...")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 8);
  return `
    <div class="template-preview-head">
      <span>文</span>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <small>${escapeHtml(source)} · ${escapeHtml(kind)} · 时间范围：${escapeHtml(start)} 至 ${escapeHtml(end)}</small>
      </div>
    </div>
    <div class="template-preview-meta">
      <span>${escapeHtml(instructionStatus)}</span>
      <span>${escapeHtml(currentReportRangeLabel($("#kindSelect")?.value || "day"))}</span>
    </div>
    <div class="template-preview-lines">
      ${lines
        .map((line, index) => `
          <div class="template-preview-line">
            <i></i>
            <span>${escapeHtml(line)}</span>
            <b style="width:${Math.max(34, 92 - index * 7)}%"></b>
          </div>
        `)
        .join("")}
    </div>
    <p>实际内容将基于你的工作记录自动生成</p>
  `;
}

function findTemplateCatalogItem(name) {
  const catalog = state.data?.style_catalog || [];
  return catalog.find((entry) => entry.name === name)
    || (state.data?.styles || []).map((styleName) => ({
      name: styleName,
      prompt: state.data?.style_descriptions?.[styleName] || "",
      group: "内置",
      audience: "通用",
      preview: state.data?.style_descriptions?.[styleName] || "",
      source: "内置",
    })).find((entry) => entry.name === name);
}

function openTemplateDetail(name) {
  const item = findTemplateCatalogItem(name);
  if (!item) return;
  state.templateDetailItem = item;
  const source = templateSourceLabel(item);
  const prompt = item.prompt || state.data?.style_descriptions?.[item.name] || "暂无模板说明。";
  const preview = item.preview || prompt;
  $("#templateDetailTitle").textContent = item.name;
  $("#templateDetailMeta").textContent = `${source} · ${item.audience || "通用"}`;
  $("#templateDetailBody").innerHTML = `
    <div class="template-detail-section">
      <strong>适用场景</strong>
      <p>${escapeHtml(item.audience || item.group || "通用工作汇报")}</p>
    </div>
    <div class="template-detail-section">
      <strong>模板说明</strong>
      <p>${escapeHtml(prompt)}</p>
    </div>
    <div class="template-detail-section">
      <strong>预览结构</strong>
      <pre>${escapeHtml(preview)}</pre>
    </div>
  `;
  $("#templateDetailModal").classList.add("show");
  $("#templateDetailModal").setAttribute("aria-hidden", "false");
}

function closeTemplateDetail() {
  $("#templateDetailModal").classList.remove("show");
  $("#templateDetailModal").setAttribute("aria-hidden", "true");
  state.templateDetailItem = null;
}

function openCustomTemplateSettings() {
  navigateTo("settings");
  window.setTimeout(() => {
    const input = $("#customReportStylesInput");
    input?.scrollIntoView({ block: "center", behavior: "smooth" });
    input?.focus();
    toast("在这里添加自定义报告模板");
  }, 80);
}

function focusReportInstruction() {
  const card = $("#reportInstructionCard");
  const input = $("#reportInstructionInput");
  if (!card || !input) return;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("is-focused");
  input.focus();
  toast("已定位到自定义指令");
}

function renderSearchControls(categories) {
  const select = $("#searchCategory");
  if (!select) return;
  const previous = select.value;
  select.innerHTML = `<option value="">全部分类</option>`;
  for (const name of categories) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  select.value = categories.includes(previous) ? previous : "";
}

function renderManualControls(categories) {
  const select = $("#manualCategory");
  if (!select) return;
  const previous = select.value;
  select.innerHTML = "";
  for (const name of categories) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  select.value = categories.includes(previous)
    ? previous
    : categories.includes("文档写作")
      ? "文档写作"
      : categories[0] || "";
  resetManualActivity(false);
}

function renderOverview(data) {
  const topCategory = data.categories[0];
  const topApp = data.top_apps[0];
  if ($("#timelineFromDate")) $("#timelineFromDate").value = state.search.from || data.day;
  if ($("#timelineToDate")) $("#timelineToDate").value = state.search.to || data.day;
  syncReportDateRange({ force: !state.reportRangeTouched });
  $("#totalCount").textContent = data.total;
  $("#topCategory").textContent = topCategory ? topCategory.name : "暂无";
  $("#topCategoryMeta").textContent = topCategory ? `${topCategory.percent}% / ${topCategory.count} 条` : "等待记录";
  $("#topApp").textContent = topApp ? topApp.name : "暂无";
  $("#topAppMeta").textContent = topApp ? `${topApp.count} 条活动` : "等待记录";
  $("#donutTotal").textContent = data.total;

  let angle = 0;
  const parts = data.categories.map((cat) => {
    const start = angle;
    angle += cat.percent * 3.6;
    return `${cat.color} ${start}deg ${angle}deg`;
  });
  $("#donutChart").style.background = parts.length
    ? `conic-gradient(${parts.join(", ")}, var(--line-soft) ${angle}deg 360deg)`
    : "conic-gradient(var(--line-soft) 0deg 360deg)";

  $("#categoryLegend").innerHTML = data.categories.length
    ? data.categories
        .map(
          (cat) => `
          <div class="legend-row">
            <span class="legend-swatch" style="background:${cat.color}"></span>
            <span>${cat.name}</span>
            <span class="bar"><span style="width:${cat.percent}%; background:${cat.color}"></span></span>
            <strong>${cat.percent}%</strong>
          </div>
        `,
        )
        .join("")
    : `<div class="empty">还没有可统计的活动。<br />点击开始记录，或先用命令行导入几条记录。</div>`;
  $("#workOverviewEmpty").hidden = Number(data.total || 0) > 0;
  renderTodayStatus(data);
  renderQuickStart(data);
}

function renderTodayStatus(data) {
  const total = Number(data.total || 0);
  const running = Boolean(data.recording?.running);
  const reports = data.reports || [];
  const hasDayReport = reports.some((item) => item.day === data.day && reportKindValue(item.kind) === "day");
  if ($("#todayRecordStatus")) $("#todayRecordStatus").textContent = total ? `今日 ${total} 条记录` : "等待记录";
  if ($("#todayRecordingStatus")) $("#todayRecordingStatus").textContent = running ? "后台记录中" : "后台已暂停";
  if ($("#todayReportStatus")) {
    $("#todayReportStatus").textContent = hasDayReport ? "日报已生成" : total ? "可生成日报" : "暂无报告素材";
  }
}

function setQuickStep(id, ok, text) {
  const el = $(`#${id}`);
  if (!el) return;
  el.classList.toggle("done", Boolean(ok));
  el.classList.toggle("todo", !ok);
  const textEl = $(`#${id.replace("Step", "Text")}`);
  if (textEl) textEl.textContent = text;
}

function renderQuickStart(data) {
  const card = $("#quickStartCard");
  if (!card) return;
  const screenOk = data.permissions?.screen_recording?.state === "granted";
  const accessOk = data.permissions?.accessibility?.state === "granted";
  const modelOk = Boolean(data.health?.model?.ready);
  const running = Boolean(data.recording?.running);
  const hasToday = Number(data.total || 0) > 0;
  const ready = screenOk && accessOk && modelOk;
  card.classList.toggle("is-done", hasToday);
  $("#quickStartTitle").textContent = hasToday ? "今日记录已开始" : ready ? "准备就绪，可以开始记录" : "开始前需要处理";
  $("#quickStartText").textContent = hasToday
    ? "今天已经有活动素材，继续后台记录即可累积更完整的日报上下文。"
    : ready
      ? "建议先记录一次当前屏幕，确认时间线、分类和应用识别都能正常写入。"
      : "先处理权限或模型连接，处理好后再开始记录。";
  $("#quickStartBadge").textContent = hasToday ? `${data.total} 条` : running ? "记录中" : ready ? "可记录" : "待处理";
  setQuickStep("quickPermissionStep", screenOk && accessOk, screenOk && accessOk ? "屏幕录制和辅助功能已授权" : "需要打开屏幕录制/辅助功能");
  setQuickStep("quickModelStep", modelOk, modelOk ? `${data.health?.model?.provider || "-"} · ${data.health?.model?.model || "-"}` : "模型网关未就绪");
  setQuickStep("quickRecordStep", running || hasToday, running ? "后台记录正在运行" : hasToday ? `今日已有 ${data.total} 条记录` : "尚未开始记录");
}

function renderAutoReport(autoReport) {
  if (!autoReport) return;
  $("#autoReportEnabled").checked = Boolean(autoReport.enabled);
  $("#autoReportTime").value = autoReport.time || "18:30";
  if ($("#autoReportStyle").children.length) {
    $("#autoReportStyle").value = normalizeStyleName(autoReport.style) || "标准";
  }
  $("#autoReportEnabledText").textContent = autoReport.enabled ? "已启用" : "未启用";
  $("#autoReportPlanText").textContent = `${autoReport.time || "18:30"} · ${autoReport.style || "标准"}`;
  $("#autoReportLastText").textContent = autoReport.last_day || "未生成";
  $("#autoReportRunText").textContent = autoReport.last_error ? "异常" : autoReport.running ? "运行中" : "待命";
  $("#autoReportRunText").className = autoReport.last_error ? "bad" : autoReport.running ? "good" : "";
  const enabled = autoReport.enabled ? `已启用，每天 ${autoReport.time} 自动生成` : "未启用自动日报";
  const last = autoReport.last_day ? `；上次：${autoReport.last_day}` : "";
  const error = autoReport.last_error ? `；错误：${autoReport.last_error}` : "";
  $("#autoReportStatus").textContent = `${enabled}${last}。${autoReport.message || ""}${error}`;
}

function renderProductivity(productivity) {
  if (!productivity) return;
  $("#productivityScore").textContent = productivity.score || 0;
  $("#productivityLabel").textContent = productivity.label || "暂无数据";
  $("#productivityWorkPercent").textContent = `${productivity.work_percent || 0}%`;
  $("#productivityLongest").textContent = productivity.longest_focus_label || "暂无";
  $("#productivityRestSegments").textContent = productivity.rest_segments || 0;
  $("#productivitySuggestion").textContent = productivity.suggestion || "开始记录后会根据当天活动给出效率洞察。";
}

function renderAppUsage(appUsage) {
  const list = $("#appUsageList");
  if (!list) return;
  const total = appUsage.reduce((sum, item) => sum + (Number(item.minutes) || 0), 0);
  $("#appUsageMeta").textContent = total ? `约 ${formatDuration(total)}` : "按时间线估算";
  list.innerHTML = appUsage.length
    ? appUsage
        .map(
          (item) => `
          <article class="app-usage-row">
            <div class="app-usage-icon">${renderUsageIcon(item)}</div>
            <div class="app-usage-main">
              <div class="app-usage-title">
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(item.label)} · ${escapeHtml(item.top_category || "其他")}</span>
              </div>
              <div class="app-usage-bar">
                <span style="width:${Math.max(2, item.percent || 0)}%"></span>
              </div>
            </div>
            <div class="app-usage-percent">${item.percent || 0}%</div>
          </article>
        `,
        )
        .join("")
    : `<div class="empty app-usage-empty">还没有应用用时统计。</div>`;
}

function renderAppRecords(appUsage, meta = state.appUsageMeta) {
  const table = $("#appRecordsTable");
  if (!table) return;
  const total = appUsage.reduce((sum, item) => sum + (Number(item.minutes) || 0), 0);
  const days = Math.max(1, Number(meta?.days) || 1);
  const periodLabel = appPeriodLabel(meta?.period || state.appPeriod);
  const rangeLabel = meta?.start_day && meta?.end_day && meta.start_day !== meta.end_day ? `${meta.start_day} 至 ${meta.end_day}` : meta?.end_day || state.date;
  $("#appRecordsMeta").textContent = total ? `${periodLabel} · ${appUsage.length} 个应用 · 约 ${formatDuration(total)}` : `${periodLabel} · 按时间线估算`;
  if ($("#appDetailMeta")) {
    const clickHint = appUsage.length ? "点击应用查看对应时间线" : "暂无可查看应用";
    $("#appDetailMeta").textContent = `${rangeLabel} · Top ${Math.min(20, appUsage.length)} · ${clickHint}`;
  }
  if ($("#appTotalCount")) $("#appTotalCount").textContent = appUsage.length;
  if ($("#appTotalTime")) $("#appTotalTime").textContent = total ? formatDuration(total) : "0秒";
  if ($("#appDailyAverage")) $("#appDailyAverage").textContent = total ? formatDuration(Math.max(1, Math.round(total / days))) : "0秒";
  syncAppCustomRange(meta);
  renderAppPageChart(appUsage);
  table.innerHTML = appUsage.length
    ? `
      <div class="app-records-head">
        <span>应用名称</span>
        <span>使用时长</span>
        <span>占比</span>
        <span>首次使用</span>
        <span>最后使用</span>
      </div>
      ${appUsage
        .map(
          (item) => `
          <button class="app-record-row" type="button" data-app-search="${escapeHtml(item.name)}" title="查看 ${escapeHtml(item.name)} 的时间线记录">
            <div class="app-record-name">
              <div class="app-usage-icon">${renderUsageIcon(item)}</div>
              <strong>${escapeHtml(item.name)}</strong>
            </div>
            <span>${escapeHtml(item.label || formatDuration(item.minutes || 0))}</span>
            <span>${escapeHtml(appShareLabel(item, total))}</span>
            <span>${escapeHtml(item.first_time || "--:--")}</span>
            <span>${escapeHtml(item.last_time || "--:--")}</span>
          </button>
        `,
        )
        .join("")}
    `
    : renderAppEmptyState("暂无应用记录", "开始记录后会按应用汇总使用时长、占比和首次/最后使用时间。");
}

function renderAppEmptyState(title, text) {
  return `
    <div class="empty app-empty-state">
      <span>▦</span>
      <strong>${title}</strong>
      <p>${text}</p>
    </div>
  `;
}

function appShareLabel(item, total) {
  if (!total) return "0.00%";
  const value = (Number(item.minutes) || 0) / total * 100;
  return `${value.toFixed(2)}%`;
}

function appPeriodLabel(period) {
  return { day: "今日", week: "本周", month: "本月", custom: "自定义" }[period] || "当前";
}

function setAppPeriodActive(period = state.appPeriod) {
  $$(".app-periods [data-app-period]").forEach((button) => {
    button.classList.toggle("active", button.dataset.appPeriod === period);
  });
  $("#appCustomRange")?.toggleAttribute("hidden", period !== "custom");
}

function syncAppCustomRange(meta = state.appUsageMeta) {
  const fromInput = $("#appFromDate");
  const toInput = $("#appToDate");
  if (!fromInput || !toInput) return;
  const from = meta?.period === "custom" ? meta.start_day : state.appCustomRange.from || addDays(state.date, -6);
  const to = meta?.period === "custom" ? meta.end_day : state.appCustomRange.to || state.date;
  fromInput.value = from || addDays(state.date, -6);
  toInput.value = to || state.date;
  if (meta?.period === "custom") {
    state.appCustomRange = { from: fromInput.value, to: toInput.value };
  }
}

function readAppCustomRange() {
  let from = $("#appFromDate")?.value || state.appCustomRange.from || addDays(state.date, -6);
  let to = $("#appToDate")?.value || state.appCustomRange.to || state.date;
  if (from > to) [from, to] = [to, from];
  state.appCustomRange = { from, to };
  if ($("#appFromDate")) $("#appFromDate").value = from;
  if ($("#appToDate")) $("#appToDate").value = to;
  return state.appCustomRange;
}

async function loadAppUsage(period = "day") {
  const params = new URLSearchParams({ date: state.date, period });
  if (period === "custom") {
    const range = readAppCustomRange();
    params.set("from", range.from);
    params.set("to", range.to);
  }
  const result = await api(`/api/app-usage?${params.toString()}`);
  const summary = result.app_usage_summary || {};
  state.appPeriod = summary.period || period;
  state.appUsage = summary.app_usage || [];
  state.appUsageMeta = {
    days: summary.days || 1,
    start_day: summary.start_day || state.date,
    end_day: summary.end_day || state.date,
    period: state.appPeriod,
  };
  setAppPeriodActive(state.appPeriod);
  renderAppRecords(state.appUsage, state.appUsageMeta);
  toast(`已显示${appPeriodLabel(state.appPeriod)}应用记录`);
}

function renderAppPageChart(appUsage) {
  const chart = $("#appPageChart");
  if (!chart) return;
  $$(".app-chart-modes [data-app-chart-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.appChartMode === state.appChartMode);
  });
  const rows = appUsage.slice(0, 20);
  if (!rows.length) {
    chart.innerHTML = renderAppEmptyState("暂无应用时长数据", "打开后台记录后，这里会显示 Top 20 应用时长分布。");
    return;
  }
  if (state.appChartMode === "pie") {
    const stops = [];
    let cursor = 0;
    rows.forEach((item, index) => {
      const value = Math.max(0, Number(item.percent) || 0);
      const next = Math.min(100, cursor + value);
      const color = appChartColor(index);
      stops.push(`${color} ${cursor}% ${next}%`);
      cursor = next;
    });
    if (cursor < 100) stops.push(`#edf2f0 ${cursor}% 100%`);
    chart.innerHTML = `
      <div class="app-pie-layout">
        <div class="app-pie" style="background: conic-gradient(${stops.join(", ")})">
          <span>${rows.length}</span>
        </div>
        <div class="app-pie-list">
          ${rows
            .map(
              (item, index) => `
              <button class="app-pie-item" type="button" data-app-search="${escapeHtml(item.name)}">
                <i style="background:${appChartColor(index)}"></i>
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(item.label || formatDuration(item.minutes || 0))}</span>
                <em>${item.percent || 0}%</em>
              </button>
            `,
            )
            .join("")}
        </div>
      </div>
    `;
    return;
  }
  chart.innerHTML = `
    <div class="app-bar-chart">
      ${rows
        .map(
          (item) => `
          <button class="app-bar-row" type="button" data-app-search="${escapeHtml(item.name)}">
            <strong>${escapeHtml(item.name)}</strong>
            <span class="app-bar-track"><i style="width:${Math.max(2, item.percent || 0)}%"></i></span>
            <em>${escapeHtml(item.label || formatDuration(item.minutes || 0))}</em>
          </button>
        `,
        )
        .join("")}
    </div>
  `;
}

function appChartColor(index) {
  const colors = ["#54c7a5", "#65b7f3", "#f4b860", "#ea6f7b", "#9b8af7", "#5fb8a8", "#d28ff2", "#8cc766"];
  return colors[index % colors.length];
}

function renderActivityRhythm(items, heatmap = state.data?.time_heatmap) {
  const chart = $("#activityRhythm");
  if (!chart) return;
  if (state.showPreviousRhythm && heatmap?.days?.length) {
    renderOverviewHeatmapRhythm(heatmap);
    return;
  }
  chart.classList.remove("is-heatmap");
  const buckets = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    count: 0,
    work: 0,
    rest: 0,
    categories: new Map(),
  }));
  for (const item of items || []) {
    const raw = item.start_ts || item.ts;
    const date = raw ? new Date(raw) : null;
    if (!date || Number.isNaN(date.getTime())) continue;
    const bucket = buckets[date.getHours()];
    const count = Math.max(1, Number(item.count) || 1);
    bucket.count += count;
    if (currentWorkCategories().has(item.category)) bucket.work += count;
    else bucket.rest += count;
    bucket.categories.set(item.category || "其他", (bucket.categories.get(item.category || "其他") || 0) + count);
  }
  const max = Math.max(...buckets.map((bucket) => bucket.count), 0);
  const activeHours = buckets.filter((bucket) => bucket.count > 0).length;
  const total = buckets.reduce((sum, bucket) => sum + bucket.count, 0);
  $("#activityRhythmMeta").textContent = total ? `${activeHours} 个活跃小时 · ${total} 条记录` : "按有效记录估算";
  if (!total) {
    chart.innerHTML = `<div class="empty rhythm-empty">还没有小时分布数据。</div>`;
    return;
  }
  chart.innerHTML = buckets
    .map((bucket) => {
      const height = max ? Math.max(8, Math.round((bucket.count / max) * 100)) : 0;
      const workPercent = bucket.count ? Math.round((bucket.work / bucket.count) * 100) : 0;
      const restPercent = bucket.count ? 100 - workPercent : 0;
      const topCategory = [...bucket.categories.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "无记录";
      const label = `${String(bucket.hour).padStart(2, "0")}:00`;
      return `
        <div class="rhythm-hour" title="${label} · ${bucket.count} 条 · ${topCategory}">
          <div class="rhythm-track">
            <span class="rhythm-work" style="height:${height ? Math.max(2, Math.round((height * workPercent) / 100)) : 0}%"></span>
            <span class="rhythm-rest" style="height:${height ? Math.max(2, Math.round((height * restPercent) / 100)) : 0}%"></span>
          </div>
          <small>${bucket.hour % 3 === 0 ? String(bucket.hour).padStart(2, "0") : ""}</small>
        </div>
      `;
    })
    .join("");
}

function renderOverviewHeatmapRhythm(heatmap) {
  const chart = $("#activityRhythm");
  const days = heatmap?.days || [];
  chart.classList.add("is-heatmap");
  const activeDays = days.filter((day) => Number(day.total || 0) > 0).length;
  const total = days.reduce((sum, day) => sum + (Number(day.total) || 0), 0);
  $("#activityRhythmMeta").textContent = total ? `${activeDays} 天有记录 · ${total} 条` : "近三日暂无时段记录";
  chart.innerHTML = days.length
    ? days
        .map(
          (day) => `
          <div class="overview-heatmap-row">
            <div class="overview-heatmap-label">
              <strong>${escapeHtml(day.label || day.day)}</strong>
              <span>${day.total || 0} 条</span>
            </div>
            <div class="overview-heatmap-cells">
              ${(day.hours || [])
                .map(
                  (hour) => `
                  <span class="overview-heat-cell level-${hour.level || 0}" title="${escapeHtml(`${day.day} ${String(hour.hour).padStart(2, "0")}:00 · ${hour.count || 0} 条`)}">${hour.count ? escapeHtml(String(hour.count)) : ""}</span>
                `,
                )
                .join("")}
            </div>
          </div>
        `,
        )
        .join("")
    : `<div class="empty rhythm-empty">还没有小时分布数据。</div>`;
}

function renderTrends(trends) {
  if (!trends) return;
  $("#trendRange").textContent = `${trends.start_day} 至 ${trends.end_day}`;
  $("#trendActiveDays").textContent = `${trends.active_days || 0} 天`;
  $("#trendAverage").textContent = `日均 ${trends.average || 0} 条`;
  $("#trendWorkPercent").textContent = `${trends.work_percent || 0}%`;
  $("#trendTopApp").textContent = trends.top_app || "暂无";
  $("#trendTopCategory").textContent = trends.top_category ? `主要分类：${trends.top_category}` : "暂无分类";

  const series = trends.series || [];
  $("#trendChart").innerHTML = series.length
    ? series
        .map((item, index) => {
          const height = item.count ? Math.max(8, item.percent || 0) : 0;
          const showLabel = index === 0 || index === series.length - 1 || index % 5 === 0;
          return `
            <button class="trend-bar" data-trend-day="${escapeHtml(item.day)}" title="${escapeHtml(item.day)} · ${item.count || 0} 条 · 工作 ${item.work_percent || 0}%">
              <span style="height:${height}%"></span>
              <small>${showLabel ? escapeHtml(formatTrendDay(item.day)) : ""}</small>
            </button>
          `;
        })
        .join("")
    : `<div class="empty trend-empty">还没有趋势数据。</div>`;
  renderCalendarHeatmap(series);
}

function renderCalendarHeatmap(series) {
  const grid = $("#calendarHeatmap");
  if (!grid) return;
  const rows = series || [];
  const max = Math.max(...rows.map((item) => item.count || 0), 0);
  const active = rows.filter((item) => (item.count || 0) > 0).length;
  $("#calendarHeatmapMeta").textContent = max ? `${active} 天有记录 · 峰值 ${max} 条` : "按记录量着色";
  grid.innerHTML = rows.length
    ? rows
        .map((item) => {
          const count = item.count || 0;
          const level = max ? Math.ceil((count / max) * 4) : 0;
          const label = formatCalendarDay(item.day);
          return `
            <button class="heat-day level-${level}" data-trend-day="${escapeHtml(item.day)}" title="${escapeHtml(item.day)} · ${count} 条 · 工作 ${item.work_percent || 0}%">
              <span>${escapeHtml(label.day)}</span>
              <small>${escapeHtml(label.weekday)}</small>
            </button>
          `;
        })
        .join("")
    : `<div class="empty trend-empty">还没有日历数据。</div>`;
}

function renderTimeHeatmap(heatmap) {
  const container = $("#timeHeatmap");
  if (!container) return;
  const days = heatmap?.days || [];
  const total = days.reduce((sum, item) => sum + (Number(item.total) || 0), 0);
  const activeDays = days.filter((item) => Number(item.total || 0) > 0).length;
  const workMinutes = days.reduce((sum, day) => sum + heatmapDayMinutes(day), 0);
  const start = days[0]?.day || addDays(state.date, -6);
  const end = days[days.length - 1]?.day || state.date;
  const requestedFrom = $("#heatmapFromDate")?.value || state.heatmapRange.from || start;
  const requestedTo = $("#heatmapToDate")?.value || state.heatmapRange.to || end;
  state.heatmapRange = { from: start, to: end };
  if ($("#heatmapFromDate")) $("#heatmapFromDate").value = start;
  if ($("#heatmapToDate")) $("#heatmapToDate").value = end;
  if ($("#heatmapTotalRecords")) $("#heatmapTotalRecords").textContent = total;
  if ($("#heatmapFocusTime")) $("#heatmapFocusTime").textContent = total ? formatDuration(workMinutes) : "0min";
  if ($("#heatmapActiveDays")) $("#heatmapActiveDays").textContent = activeDays;
  if ($("#heatmapDailyAverage")) $("#heatmapDailyAverage").textContent = days.length ? Math.round(total / days.length) : 0;
  if ($("#heatmapSlogan")) $("#heatmapSlogan").textContent = total ? "专注工作本身，剩下的交给书赫" : "专注工作本身，剩下的交给书赫";
  renderHeatmapPeakHour(days);
  container.innerHTML = days.length
    ? days
        .map(
          (day) => `
          <div class="time-heatmap-row">
            <div class="time-heatmap-label">
              <strong>${escapeHtml(day.label)}</strong>
              <span>${day.total || 0} 条 · ${formatDuration(heatmapDayMinutes(day))}</span>
            </div>
            <div class="time-heatmap-cells">
              ${(day.hours || [])
                .map(
                  (hour) => `
                  <button class="time-cell heatmap-cell level-${hour.level || 0}" type="button" title="${escapeHtml(heatmapHourTitle(day, hour))}">
                    ${hour.count ? `<span>${hour.count}</span>` : ""}
                  </button>
                `,
                )
                .join("")}
            </div>
          </div>
        `,
        )
        .join("")
    : `<div class="empty time-heatmap-empty">还没有时段热力数据。</div>`;
  syncHeatmapRangeStatus(heatmap, { requestedFrom, requestedTo });
}

function renderHeatmapPeakHour(days = []) {
  const target = $("#heatmapPeakHour");
  if (!target) return;
  const peak = days
    .flatMap((day) => (day.hours || []).map((hour) => ({ day, hour })))
    .filter(({ hour }) => Number(hour?.count || 0) > 0)
    .sort((a, b) => Number(b.hour.count || 0) - Number(a.hour.count || 0))[0];
  if (!peak) {
    target.textContent = "暂无活跃时段";
    return;
  }
  const hour = String(peak.hour.hour ?? 0).padStart(2, "0");
  const category = peak.hour.top_category ? ` · ${peak.hour.top_category}` : "";
  target.textContent = `最活跃：${peak.day.label || peak.day.day} ${hour}:00 · ${peak.hour.count || 0} 条${category}`;
}

function heatmapHourTitle(day, hour) {
  const count = Number(hour?.count) || 0;
  const label = `${day.day} ${String(hour?.hour ?? 0).padStart(2, "0")}:00`;
  const category = hour?.top_category ? ` · ${hour.top_category}` : "";
  return `${label} · ${count} 条 · 约 ${formatDuration(count)}${category}`;
}

function heatmapDayMinutes(day) {
  const explicit = Number(day?.total_minutes);
  if (Number.isFinite(explicit) && explicit >= 0) return explicit;
  return (day?.hours || []).reduce((sum, hour) => sum + (Number(hour.count) || 0), 0);
}

function readHeatmapRange() {
  const fallbackTo = state.heatmapRange.to || state.date;
  const fallbackFrom = state.heatmapRange.from || addDays(fallbackTo, -6);
  let from = $("#heatmapFromDate")?.value || fallbackFrom;
  let to = $("#heatmapToDate")?.value || fallbackTo;
  if (from > to) [from, to] = [to, from];
  return { from, to };
}

async function refreshHeatmapRange() {
  const button = $("#refreshHeatmap");
  const originalText = button?.textContent || "生成热力图";
  if (button) {
    button.disabled = true;
    button.textContent = "生成中...";
  }
  state.heatmapRange = readHeatmapRange();
  try {
    await loadSummary();
    toast("热力图已生成");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
}

function syncHeatmapRangeStatus(heatmap = state.data?.time_heatmap, requested = {}) {
  const status = $("#heatmapRangeStatus");
  if (!status) return;
  const days = heatmap?.days || [];
  const start = heatmap?.start_day || days[0]?.day || state.heatmapRange.from || addDays(state.date, -6);
  const end = heatmap?.end_day || days[days.length - 1]?.day || state.heatmapRange.to || state.date;
  const requestedFrom = requested.requestedFrom || $("#heatmapFromDate")?.value || start;
  const requestedTo = requested.requestedTo || $("#heatmapToDate")?.value || end;
  const clipped = requestedFrom && requestedTo && (requestedFrom !== start || requestedTo !== end);
  const total = days.reduce((sum, item) => sum + (Number(item.total) || 0), 0);
  const suffix = clipped ? "，已按最近 31 天显示" : "";
  status.textContent = `当前区间：${start} 至 ${end} · ${total} 条记录${suffix}`;
}

function renderUsageIcon(item) {
  if (item.icon_url) {
    return `<img src="${escapeHtml(item.icon_url)}" alt="${escapeHtml(item.name)} 图标" />`;
  }
  return `<span>${escapeHtml((item.name || "?").slice(0, 1).toUpperCase())}</span>`;
}

function renderTimeline(items) {
  $$(".timeline-quick-ranges [data-timeline-range]").forEach((button) => {
    const active = button.dataset.timelineRange === state.timelineRange;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  const sourceItems = state.search.searched ? state.search.results : items;
  const filtered = filteredTimelineItems(sourceItems);
  renderTimelineSummary(sourceItems, filtered);

  $("#timeline").innerHTML = filtered.length
    ? filtered
        .map(
          (item) => `
          <article class="timeline-row" data-timeline-id="${escapeHtml(item.id)}" tabindex="0">
            <div class="time">${formatTimeRange(item)}</div>
            <div class="thumb app-thumb">${renderIcon(item)}</div>
            <div class="row-main">
              <div class="row-title">
                <span class="summary">${escapeHtml(item.summary)}</span>
              </div>
              <div class="row-sub">${escapeHtml(formatMeta(item))}</div>
              ${renderSummaries(item)}
            </div>
            <div class="tag">${escapeHtml(item.category)}${item.count > 1 ? ` · ${item.count}` : ""}</div>
          </article>
        `,
        )
        .join("")
    : renderTimelineEmpty(sourceItems);
}

function renderTimelineEmpty(items) {
  const hasSourceItems = Boolean(items?.length);
  const searched = Boolean(state.search.searched);
  const title = searched ? "没有匹配记录" : hasSourceItems ? "这个筛选下没有记录" : "当天暂无工作记录";
  const text = searched
    ? "换个关键词、放宽日期范围，或清空搜索后查看全部活动。"
    : hasSourceItems
      ? "调整时间范围、关键词或工作/休息筛选后再试。"
      : "软件已在后台自动截图记录，开始工作后稍等片刻即可看到记录。";
  return `
    <div class="empty timeline-empty-state">
      <span>⌁</span>
      <strong>${title}</strong>
      <p>${text}</p>
    </div>
  `;
}

function filteredTimelineItems(items = state.data?.segments || state.data?.items || []) {
  return items
    .filter((item) => {
      if (state.filter === "all") return true;
      const isWork = currentWorkCategories().has(item.category);
      return state.filter === "work" ? isWork : !isWork;
    })
    .filter((item) => timelineRangeMatches(item));
}

function timelineRangeMatches(item) {
  if (state.timelineRange === "today") return true;
  const minutes = Number(state.timelineRange || 0);
  if (!minutes) return true;
  const time = item.start_time || item.time || "";
  const itemMinutes = timeToMinutes(time);
  if (itemMinutes == null) return true;
  const now = new Date();
  const current = state.date === localDateString(now) ? now.getHours() * 60 + now.getMinutes() : 24 * 60;
  return itemMinutes >= Math.max(0, current - minutes);
}

function timeToMinutes(value) {
  const match = String(value || "").match(/(\d{1,2}):(\d{2})/);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return hour * 60 + minute;
}

function renderTimelineSummary(items, filtered) {
  const total = filtered.length;
  const workMinutes = filtered.reduce((sum, item) => {
    const minutes = Number(item.minutes || item.duration_minutes || item.count || 1);
    return currentWorkCategories().has(item.category) ? sum + minutes : sum;
  }, 0);
  const first = filtered[0]?.time || filtered[0]?.start_time || "";
  const last = filtered[filtered.length - 1]?.time || filtered[filtered.length - 1]?.end_time || "";
  if ($("#timelineRecordCount")) $("#timelineRecordCount").textContent = total;
  if ($("#timelineFocusTime")) $("#timelineFocusTime").textContent = workMinutes ? formatDuration(workMinutes) : "0min";
  if ($("#timelineActivePeriod")) $("#timelineActivePeriod").textContent = first && last ? `${first}-${last}` : "暂无";
  renderTimelineCategoryChart(items);
}

function timelineFilterLabel() {
  const type = state.filter === "work" ? "工作" : state.filter === "rest" ? "休息" : "全部";
  const range = { 30: "近30分", 60: "近1小时", 120: "近2小时", today: "今天" }[state.timelineRange] || "当前范围";
  return `${type} · ${range}`;
}

function buildTimelineLogText(items = filteredTimelineItems()) {
  const header = [
    "书赫日报助手 - 活动时间线",
    `日期：${state.date}`,
    `筛选：${timelineFilterLabel()}`,
    `记录数：${items.length}`,
  ];
  if (!items.length) {
    return `${header.join("\n")}\n\n当天暂无工作记录。`;
  }
  const lines = items.map((item) => {
    const app = item.app || "未知应用";
    const title = item.window_title ? `《${item.window_title}》` : "";
    const count = item.count && item.count > 1 ? ` · ${item.count} 条` : "";
    return `- ${formatTimeRange(item)} [${item.category || "未分类"}] ${item.summary || "无摘要"}（${app}${title}${count}）`;
  });
  return `${header.join("\n")}\n\n${lines.join("\n")}`;
}

async function copyTimelineLog() {
  const text = buildTimelineLogText();
  await copyText(text);
  const count = filteredTimelineItems().length;
  toast(count ? `已复制 ${count} 条时间线日志` : "已复制空时间线提示");
}

function reuseTimelineDayDraft() {
  const items = filteredTimelineItems();
  if (!state.manualOpen) toggleManualActivity();
  setManualRecordMode("text");
  resetManualActivity(false);
  const nextDay = addDays(state.date, 1);
  $("#manualDay").value = nextDay;
  $("#manualTitle").value = `${state.date} 工作状态复用`;
  $("#manualApp").value = "书赫日报助手";
  $("#manualWindow").value = "工作时间线复用草稿";
  $("#manualSummary").value = buildTimelineReuseDraft(items, nextDay);
  updateManualSaveState();
  $("#manualSummary").focus();
  $("#manualActivityForm").scrollIntoView({ behavior: "smooth", block: "center" });
  toast(items.length ? `已生成 ${items.length} 条记录的复用草稿` : "已生成空时间线复用草稿");
}

function buildTimelineReuseDraft(items = [], targetDay = addDays(state.date, 1)) {
  const header = [
    `复用 ${state.date} 工作状态到 ${targetDay}`,
    `筛选范围：${timelineFilterLabel()}`,
  ];
  if (!items.length) {
    return `${header.join("\n")}\n\n当前筛选暂无记录。可以把这段改成邻近日期的实际工作安排，再保存为补记。`;
  }
  const lines = items.slice(0, 12).map((item) => {
    const app = item.app || "未知应用";
    const title = item.window_title ? `《${item.window_title}》` : "";
    return `- ${formatTimeRange(item)} ${item.summary || "无摘要"}（${app}${title}）`;
  });
  const suffix = items.length > 12 ? `\n- 另有 ${items.length - 12} 条记录，可按需补充。` : "";
  return `${header.join("\n")}\n\n${lines.join("\n")}${suffix}\n\n请按邻近日期实际情况修改后再保存。`;
}

function renderTimelineCategoryChart(items) {
  const chart = $("#timelineCategoryChart");
  if (!chart) return;
  const enabled = $("#showTimelineCategory")?.checked !== false;
  $(".timeline-category-card")?.classList.toggle("is-collapsed", !enabled);
  $$(".timeline-category-modes [data-timeline-category-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.timelineCategoryMode === state.timelineCategoryMode);
  });
  if (!enabled) {
    chart.innerHTML = "";
    $("#timelineCategoryMeta").textContent = "已隐藏分类时长分布";
    return;
  }
  const counts = new Map();
  for (const item of items) {
    const value = Number(item.minutes || item.duration_minutes || item.count || 1);
    counts.set(item.category || "其他", (counts.get(item.category || "其他") || 0) + value);
  }
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  const max = Math.max(...rows.map(([, value]) => value), 0);
  const total = rows.reduce((sum, [, value]) => sum + value, 0);
  $("#timelineCategoryMeta").textContent = rows.length ? `${rows.length} 个分类 · 约 ${formatDuration(total)}` : "按时间段估算";
  if (rows.length && state.timelineCategoryMode === "pie") {
    let cursor = 0;
    const stops = rows.map(([name, value]) => {
      const percent = total ? Math.round((value / total) * 1000) / 10 : 0;
      const next = Math.min(100, cursor + percent);
      const color = categoryColor(name);
      const stop = `${color} ${cursor}% ${next}%`;
      cursor = next;
      return stop;
    });
    if (cursor < 100) stops.push(`#edf2f0 ${cursor}% 100%`);
    chart.innerHTML = `
      <div class="timeline-category-pie-layout">
        <div class="app-pie timeline-category-pie" style="background: conic-gradient(${stops.join(", ")})">
          <span>${rows.length}</span>
        </div>
        <div class="timeline-category-pie-list">
          ${rows
            .map(([name, value]) => {
              const percent = total ? Math.round((value / total) * 100) : 0;
              return `
                <div class="timeline-category-pie-item">
                  <i style="background:${categoryColor(name)}"></i>
                  <strong>${escapeHtml(name)}</strong>
                  <span>${formatDuration(value)}</span>
                  <em>${percent}%</em>
                </div>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
    return;
  }
  chart.innerHTML = rows.length
    ? rows
        .map(([name, value]) => `
          <div class="category-duration-row">
            <span>${escapeHtml(name)}</span>
            <div class="bar"><span style="width:${max ? Math.max(3, Math.round(value / max * 100)) : 0}%; background:${categoryColor(name)}"></span></div>
            <strong>${formatDuration(value)}</strong>
          </div>
        `)
        .join("")
    : `<div class="empty timeline-category-empty">暂无分类时长数据。</div>`;
}

function findTimelineItem(id) {
  const items = state.data?.segments || state.data?.items || [];
  return items.find((item) => String(item.id) === String(id))
    || state.search.results.find((item) => String(item.id) === String(id));
}

function openTimelineDetail(item) {
  if (!item) return;
  state.detailItem = item;
  const editable = editableItem(item);
  $("#detailTitle").textContent = item.summary || "记录详情";
  $("#detailBody").innerHTML = `
    <div class="detail-shot">
      ${renderDetailShot(item)}
    </div>
    <div class="detail-meta-grid">
      ${detailField("时间", formatTimeRange(item).replace("\n", " · "))}
      ${detailField("分类", item.category || "-")}
      ${detailField("应用", item.app || "未知应用")}
      ${detailField("窗口", item.window_title || "-")}
      ${detailField("日期", item.day || "-")}
      ${detailField("记录数", item.count ? `${item.count} 条` : "1 条")}
    </div>
    ${renderDetailSummaries(item)}
    ${renderActivityEditor(editable, item)}
  `;
  $("#detailModal").classList.add("show");
  $("#detailModal").setAttribute("aria-hidden", "false");
}

function closeTimelineDetail() {
  $("#detailModal").classList.remove("show");
  $("#detailModal").setAttribute("aria-hidden", "true");
  state.detailItem = null;
}

function renderDetailShot(item) {
  const shotUrl = item.latest_shot_url || item.shot_url || item.items?.find((entry) => entry.shot_url)?.shot_url || "";
  if (shotUrl) {
    return `<img src="${escapeHtml(shotUrl)}" alt="活动截图" />`;
  }
  return `<div class="detail-shot-empty">没有保留截图<br /><span>可能关闭了截图留存，或已清理截图文件。</span></div>`;
}

function renderDetailSummaries(item) {
  const summaries = item.summaries || item.items?.map((entry) => entry.summary) || [item.summary];
  const unique = [...new Set(summaries.filter(Boolean))];
  if (!unique.length) return "";
  return `
    <div class="detail-summaries">
      <strong>识别摘要</strong>
      ${unique.map((summary) => `<p>${escapeHtml(summary)}</p>`).join("")}
    </div>
  `;
}

function editableItem(item) {
  return item.items?.[0] || item;
}

function renderActivityEditor(activity, sourceItem) {
  if (!activity?.id || String(activity.id).startsWith("seg-")) return "";
  const categories = state.data?.activity_categories || [...defaultWorkCategories, "娱乐休息", "其他"];
  return `
    <form class="activity-editor" data-activity-editor data-activity-id="${escapeHtml(activity.id)}">
      <div class="editor-head">
        <strong>修正记录</strong>
        <span>${sourceItem.count && sourceItem.count > 1 ? `当前时间段包含 ${sourceItem.count} 条记录，本次编辑第 1 条。` : "修改后会影响报告生成。"}</span>
      </div>
      <label>
        <span>摘要</span>
        <textarea id="activitySummaryInput" rows="3">${escapeHtml(activity.summary || "")}</textarea>
      </label>
      <div class="editor-grid">
        <label>
          <span>分类</span>
          <select id="activityCategoryInput">
            ${categories.map((name) => `<option value="${escapeHtml(name)}" ${name === activity.category ? "selected" : ""}>${escapeHtml(name)}</option>`).join("")}
          </select>
        </label>
        <label>
          <span>应用</span>
          <input id="activityAppInput" value="${escapeHtml(activity.app || "")}" />
        </label>
      </div>
      <label>
        <span>窗口标题</span>
        <input id="activityWindowInput" value="${escapeHtml(activity.window_title || "")}" />
      </label>
      <div class="editor-actions">
        <button class="button primary" id="saveActivity" type="submit">保存修正</button>
        <button class="button danger-subtle" id="deleteActivity" type="button">删除记录</button>
      </div>
    </form>
  `;
}

function detailField(label, value) {
  return `
    <div class="detail-field">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderReports(reports) {
  const list = $("#reportList");
  if (!list) return;
  list.innerHTML = reports.length
    ? reports
        .map(
          (item) => `
          <article class="report-item">
            <button type="button" data-report-load="${item.id}">
              <strong>${escapeHtml(item.title)}</strong>
              <span>${escapeHtml(item.kind)} · ${escapeHtml(item.style)} · ${escapeHtml(formatDateTime(item.created_at))}</span>
            </button>
            <button class="report-delete" type="button" title="删除报告" data-report-delete="${item.id}">×</button>
          </article>
        `,
        )
        .join("")
    : `<div class="empty report-empty">还没有历史报告。</div>`;
}

function renderReportHistoryTable(reports) {
  const table = $("#historyReportTable");
  if (!table) return;
  renderHistoryFilters();
  const filtered = filterReports(reports || []);
  const meta = $("#historyFilterMeta");
  if (meta) {
    const scope = historyFilterScope();
    const countText = filtered.length === (reports.length || 0) ? `共 ${filtered.length} 份` : `共 ${filtered.length} 份 / 全部 ${reports.length || 0} 份`;
    meta.textContent = `${scope} · ${countText}`;
  }
  table.innerHTML = filtered.length
    ? `
      <div class="history-report-head">
        <span>标题</span>
        <span>内容预览</span>
        <span>类型</span>
        <span>模板</span>
        <span>生成时间</span>
        <span>操作</span>
      </div>
      ${filtered
        .map(
          (item) => `
          <div class="history-report-row">
            <strong>${escapeHtml(item.title)}</strong>
            <span class="history-report-preview">${escapeHtml(compactReportPreview(item.preview))}</span>
            <span>${escapeHtml(item.kind)}</span>
            <span>${escapeHtml(item.style)}</span>
            <span>${escapeHtml(formatDateTime(item.created_at))}</span>
            <div class="history-report-actions">
              <button class="text-button" type="button" data-report-load="${item.id}">载入</button>
              <button class="text-button" type="button" data-history-report-delete="${item.id}">删除</button>
            </div>
          </div>
        `,
        )
        .join("")}
    `
    : renderHistoryReportEmpty(reports || []);
}

function renderHistoryReportEmpty(reports) {
  const hasReports = Boolean(reports?.length);
  const title = hasReports ? "当前筛选没有报告" : "暂无报告记录，去生成第一份吧";
  const text = hasReports ? "换个关键词、放宽日期范围，或清空筛选后查看全部报告。" : "生成日报、周报或月报后，会在这里统一查看和管理。";
  return `
    <div class="empty report-empty history-report-empty">
      <span>◷</span>
      <strong>${title}</strong>
      <p>${text}</p>
      <button class="button primary compact-button" type="button" data-history-generate>去生成报告</button>
    </div>
  `;
}

function compactReportPreview(value) {
  return String(value || "暂无内容预览").replace(/\s+/g, " ").trim().slice(0, 80);
}

function renderHistoryFilters() {
  $$("#historyKindFilter [data-report-kind]").forEach((button) => {
    button.classList.toggle("active", button.dataset.reportKind === state.reportFilters.kind);
  });
  $$("#historyRangeFilter [data-report-range]").forEach((button) => {
    button.classList.toggle("active", button.dataset.reportRange === state.reportFilters.range);
  });
  if ($("#historySearchInput") && $("#historySearchInput").value !== state.reportFilters.query) {
    $("#historySearchInput").value = state.reportFilters.query;
  }
  if ($("#historyFromDate") && $("#historyFromDate").value !== state.reportFilters.from) {
    $("#historyFromDate").value = state.reportFilters.from;
  }
  if ($("#historyToDate") && $("#historyToDate").value !== state.reportFilters.to) {
    $("#historyToDate").value = state.reportFilters.to;
  }
  const hasFilters = hasHistoryFilters();
  $("#historyClearFilters")?.toggleAttribute("disabled", !hasFilters);
}

function filterReports(reports) {
  const { kind, from, to, query } = state.reportFilters;
  const needle = String(query || "").trim().toLowerCase();
  return reports.filter((item) => {
    if (kind !== "all" && item.kind !== kind) return false;
    if (from && String(item.day || "") < from) return false;
    if (to && String(item.day || "") > to) return false;
    if (needle && ![item.title, item.kind, item.style, item.preview].some((value) => String(value || "").toLowerCase().includes(needle))) return false;
    return true;
  });
}

function historyRangeDates(range) {
  const today = new Date(`${localDateString()}T00:00:00`);
  if (range === "7" || range === "30") {
    return {
      from: localDateString(new Date(today.getTime() - (Number(range) - 1) * 86400000)),
      to: localDateString(today),
    };
  }
  if (range === "week") {
    const day = today.getDay() || 7;
    return {
      from: localDateString(new Date(today.getTime() - (day - 1) * 86400000)),
      to: localDateString(today),
    };
  }
  if (range === "month") {
    return {
      from: `${localDateString().slice(0, 7)}-01`,
      to: localDateString(today),
    };
  }
  return { from: "", to: "" };
}

function hasHistoryFilters() {
  const { kind, from, to, query, range } = state.reportFilters;
  return kind !== "all" || Boolean(from || to || query || range);
}

function historyFilterScope() {
  const { kind, from, to, query, range } = state.reportFilters;
  const parts = [];
  parts.push(kind === "all" ? "全部报告" : kind);
  if (range) {
    parts.push({ week: "本周", month: "本月", 7: "最近 7 天", 30: "最近 30 天" }[range] || "日期筛选");
  } else if (from || to) {
    parts.push(`${from || "最早"} 至 ${to || "今天"}`);
  }
  if (query) parts.push(`搜索：${query}`);
  return parts.join(" · ");
}

function clearHistoryFilters() {
  state.reportFilters = {
    kind: "all",
    range: "",
    query: "",
    from: "",
    to: "",
  };
  renderReportHistoryTable(state.data?.reports || []);
  toast("已清空历史报告筛选");
}

function renderChat(messages) {
  const list = $("#chatList");
  if (!list) return;
  list.innerHTML = messages.length
    ? messages
        .map(
          (item) => `
          <article class="chat-item">
            <div class="chat-question">
              <span>${chatScopeLabel(item.scope)} · ${escapeHtml(formatDateTime(item.created_at))}</span>
              <button class="text-button" type="button" data-chat-delete="${item.id}">删除</button>
            </div>
            <strong>${escapeHtml(item.question)}</strong>
            <p>${escapeHtml(item.answer)}</p>
          </article>
        `,
        )
        .join("")
    : `<div class="empty chat-empty">还没有追问。可以问“今天主要产出是什么？”或“日报里该突出哪些风险？”</div>`;
}

function chatScopeLabel(scope) {
  return { day: "当天", week: "近 7 天", month: "近 30 天" }[scope] || "当天";
}

function setReportPreview(text, { reportId = state.reportId, dirty = false, meta = state.reportMeta } = {}) {
  state.reportText = text || "";
  state.reportId = reportId || null;
  state.reportMeta = meta || null;
  state.reportDirty = dirty;
  $("#reportPreview").textContent = state.reportText || "报告内容为空。";
  renderReportEditState();
}

function getReportPreviewText() {
  return ($("#reportPreview").textContent || "").trim();
}

function reportCharCount(text) {
  return String(text || "").replace(/\s/g, "").length;
}

function renderReportEditState() {
  const saveButton = $("#saveReportEdits");
  if (!saveButton) return;
  saveButton.disabled = !state.reportId || !state.reportDirty;
  saveButton.textContent = state.reportId && !state.reportDirty ? "已保存" : "保存修改";
  const text = getReportPreviewText();
  const meta = state.reportMeta || {};
  const kind = meta.kind || reportKindLabel($("#kindSelect")?.value);
  const day = meta.day || state.date;
  const range = meta.range || reportRangeLabel(day, kind);
  const style = meta.style || $("#styleSelect")?.value || "标准";
  const generated = Boolean(state.reportId);
  $("#reportCurrentMeta").textContent = generated ? `${range} · ${kind} · ${style}` : "未生成报告";
  $("#reportWordCount").textContent = `${generated ? reportCharCount(text) : 0} 字`;
  $("#reportSaveState").textContent = !generated ? "未生成" : state.reportDirty ? "有未保存修改" : "已保存";
  $("#reportSaveState").className = !generated ? "muted" : state.reportDirty ? "dirty" : "saved";
}

function renderDayNote(dayNote) {
  if (!dayNote) return;
  const input = $("#dayNoteInput");
  if (!state.dayNoteTouched && document.activeElement !== input) {
    input.value = dayNote.note || "";
  }
  $("#dayNoteStatus").textContent = dayNote.updated_at
    ? `已保存：${formatDateTime(dayNote.updated_at)}`
    : "尚未保存备注。";
}

function renderSearchResults() {
  const container = $("#searchResults");
  if (!container) return;
  if (!state.search.searched) {
    container.innerHTML = "";
    return;
  }
  const results = state.search.results || [];
  container.innerHTML = `
    <div class="search-head">
      <strong>${results.length ? `找到 ${results.length} 条记录` : "没有匹配记录"}</strong>
      <span>${escapeHtml(formatSearchScope())}</span>
    </div>
    ${
      results.length
        ? `<div class="search-list">
            ${results.map(renderSearchItem).join("")}
          </div>`
        : `<div class="empty search-empty">换个关键词或放宽日期范围再试。</div>`
    }
  `;
}

function renderSearchItem(item) {
  return `
    <article class="search-item" data-search-id="${escapeHtml(item.id)}" tabindex="0">
      <div>
        <strong>${escapeHtml(item.summary)}</strong>
        <span>${escapeHtml(formatMeta(item))}</span>
      </div>
      <em>${escapeHtml(formatDateTime(item.ts))}</em>
    </article>
  `;
}

function formatSearchScope() {
  const parts = [];
  if (state.search.query) parts.push(`关键词：${state.search.query}`);
  if (state.search.category) parts.push(`分类：${state.search.category}`);
  if (state.search.from || state.search.to) parts.push(`${state.search.from || "最早"} 至 ${state.search.to || "今天"}`);
  return parts.join(" · ") || "全部活动";
}

function renderDays(days) {
  const list = $("#dayList");
  if (!list) return;
  list.innerHTML = days.length
    ? days
        .map(
          (item) => `
          <button class="day-item ${item.day === state.date ? "active" : ""}" type="button" data-day="${escapeHtml(item.day)}">
            <span>
              <strong>${escapeHtml(formatDayLabel(item.day))}</strong>
              <span>${escapeHtml(formatDayRange(item))}</span>
              ${renderDayReportBadge(item.reports)}
            </span>
            <span class="day-count">${item.count}</span>
          </button>
        `,
        )
        .join("")
    : `<div class="empty day-empty">还没有历史记录。<br />开始记录后会出现在这里。</div>`;
}

function renderDayReportBadge(reports) {
  const count = Number(reports?.count || 0);
  if (!count) return "";
  const kind = reports.latest_kind || "报告";
  return `<small class="day-report-badge">${escapeHtml(kind)}已生成${count > 1 ? ` · ${count}` : ""}</small>`;
}

function formatTimeRange(item) {
  const start = item.start_time || item.time;
  const end = item.end_time && item.end_time !== start ? `-${item.end_time}` : "";
  const duration = item.duration_minutes && item.duration_minutes > 1 ? `\n${item.duration_minutes}m` : "";
  return `${start}${end}${duration}`;
}

function renderIcon(item) {
  const icon = item.app_icon_url || item.items?.find((entry) => entry.app_icon_url)?.app_icon_url || "";
  if (icon) {
    return `<img src="${icon}" alt="${escapeHtml(item.app || "应用")} 图标" />`;
  }
  const label = (item.app || item.category || "?").trim().slice(0, 1).toUpperCase();
  return `<span class="app-fallback">${escapeHtml(label)}</span>`;
}

function renderSummaries(item) {
  if (!item.summaries || item.summaries.length <= 1) return "";
  const unique = [...new Set(item.summaries)].slice(0, 3);
  return `<div class="summary-list">${unique.map((summary) => `<span>${escapeHtml(summary)}</span>`).join("")}</div>`;
}

function formatMeta(item) {
  const app = item.app || "未知应用";
  const title = item.window_title ? `《${item.window_title}》` : "";
  const count = item.count && item.count > 1 ? ` · ${item.count} 条记录` : "";
  return `${app}${title} · ${item.day}${count}`;
}

function formatDateTime(value) {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 16);
}

function formatLogMeta(file) {
  const size = formatBytes(file.size || 0);
  const modified = formatDateTime(file.modified || "");
  return modified ? `${size} · ${modified}` : size;
}

function formatRequestParams(params) {
  if (!params || !Object.keys(params).length) return "-";
  return Object.entries(params)
    .map(([key, values]) => `${key}=${Array.isArray(values) ? values.join(",") : values}`)
    .join("&");
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDuration(minutes) {
  const value = Number(minutes) || 0;
  if (value < 60) return `${value} 分钟`;
  const hours = Math.floor(value / 60);
  const mins = value % 60;
  return mins ? `${hours} 小时 ${mins} 分钟` : `${hours} 小时`;
}

function formatDayLabel(day) {
  const date = new Date(`${day}T00:00:00`);
  if (Number.isNaN(date.getTime())) return day;
  const names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${day.slice(5)} ${names[date.getDay()]}`;
}

function formatTrendDay(day) {
  return String(day || "").slice(8);
}

function formatCalendarDay(day) {
  const date = new Date(`${day}T00:00:00`);
  const names = ["日", "一", "二", "三", "四", "五", "六"];
  if (Number.isNaN(date.getTime())) {
    return { day: String(day || "").slice(-2), weekday: "" };
  }
  return { day: String(date.getDate()), weekday: names[date.getDay()] };
}

function formatDayRange(item) {
  if (!item.first_time || !item.last_time) return `${item.count} 条记录`;
  if (item.first_time === item.last_time) return `${item.first_time} · ${item.count} 条`;
  return `${item.first_time}-${item.last_time} · ${item.count} 条`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[char];
  });
}

async function loadRequestLogs({ show = false, notify = false, page = state.requestLogPage || 1 } = {}) {
  const result = await api(`/api/request-logs?page=${encodeURIComponent(page)}`);
  state.requestLogs = result.request_logs;
  renderRequestLogs(state.requestLogs);
  if (show) openRequestLogModal();
  if (notify) toast("请求日志已刷新");
}

function changeRequestLogPage(delta) {
  const current = state.requestLogs?.page || state.requestLogPage || 1;
  const pages = state.requestLogs?.pages || 1;
  const next = Math.min(Math.max(1, current + delta), pages);
  if (next === current) return;
  loadRequestLogs({ page: next }).catch((error) => toast(error.message));
}

function openRequestLogModal() {
  $("#requestLogModal").classList.add("show");
  $("#requestLogModal").setAttribute("aria-hidden", "false");
}

function closeRequestLogModal() {
  $("#requestLogModal").classList.remove("show");
  $("#requestLogModal").setAttribute("aria-hidden", "true");
}

async function clearRequestLogs() {
  const result = await api("/api/request-logs/clear", { method: "POST", body: "{}" });
  state.requestLogs = result.request_logs;
  renderRequestLogs(state.requestLogs);
  toast(`已清空 ${result.cleared || 0} 条请求日志`);
}

function normalizeStyleName(style) {
  return String(style || "").trim().toLowerCase() === "okr" ? "OKR" : style;
}

function reportKindLabel(kind) {
  return { day: "日报", week: "周报", month: "月报" }[kind] || kind || "报告";
}

function reportKindValue(kind) {
  return { 日报: "day", 周报: "week", 月报: "month" }[kind] || (["day", "week", "month"].includes(kind) ? kind : "");
}

function addDays(day, offset) {
  const date = new Date(`${day}T00:00:00`);
  if (Number.isNaN(date.getTime())) return day;
  date.setDate(date.getDate() + offset);
  return localDateString(date);
}

function reportRangeLabel(day, kind) {
  const value = reportKindValue(kind);
  if (value === "week") return `${addDays(day, -6)} ~ ${day}`;
  if (value === "month") return `${addDays(day, -29)} ~ ${day}`;
  return day;
}

function reportRangeForKind(kind, day = state.date) {
  const value = reportKindValue(kind);
  if (value === "week") return { start: addDays(day, -6), end: day };
  if (value === "month") return { start: addDays(day, -29), end: day };
  return { start: day, end: day };
}

function currentReportRange(kind = $("#kindSelect")?.value || "day") {
  const fallback = reportRangeForKind(kind);
  const start = $("#reportStartDate")?.value || fallback.start;
  const end = $("#reportEndDate")?.value || fallback.end;
  return start <= end ? { start, end } : { start: end, end: start };
}

function currentReportRangeLabel(kind = $("#kindSelect")?.value || "day") {
  const { start, end } = currentReportRange(kind);
  return start === end ? start : `${start} ~ ${end}`;
}

function syncReportConfigSummary() {
  const el = $("#reportConfigSummary");
  if (!el) return;
  const kindValue = $("#kindSelect")?.value || "day";
  const kind = reportKindLabel(kindValue);
  const range = currentReportRangeLabel(kindValue);
  const template = $("#styleSelect")?.value || "标准";
  const hasInstruction = Boolean($("#reportInstructionInput")?.value.trim());
  const instruction = hasInstruction ? "已加自定义指令" : "未加自定义指令";
  el.textContent = `当前配置：${kind} · ${range} · ${template} · ${instruction}`;
  syncReportInstructionButton(hasInstruction);
}

function syncReportInstructionButton(hasInstruction = Boolean($("#reportInstructionInput")?.value.trim())) {
  const button = $("#clearReportInstruction");
  if (!button) return;
  button.textContent = hasInstruction ? "已加指令" : "自定义指令";
  button.classList.toggle("has-report-instruction", hasInstruction);
  button.setAttribute("aria-pressed", hasInstruction ? "true" : "false");
}

function syncReportDateRange({ force = false } = {}) {
  const startInput = $("#reportStartDate");
  const endInput = $("#reportEndDate");
  if (!startInput || !endInput) return;
  if (state.reportRangeTouched && !force) return;
  const range = reportRangeForKind($("#kindSelect")?.value || "day");
  startInput.value = range.start;
  endInput.value = range.end;
  syncReportConfigSummary();
}

function handleReportKindChange() {
  state.reportRangeTouched = false;
  syncReportDateRange({ force: true });
  renderReportKindTabs();
  renderTemplateSelection();
}

function safeDownloadName(value) {
  return String(value || "书赫报告")
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90) || "书赫报告";
}

async function toggleRecording() {
  const running = state.data?.recording?.running;
  const endpoint = running ? "/api/recording/stop" : "/api/recording/start";
  const result = await api(endpoint, { method: "POST", body: "{}" });
  state.data.recording = result;
  renderStatus(result);
  toast(running ? "已暂停记录" : "已开始后台记录");
}

async function captureNow() {
  const buttons = [$("#captureNowButton"), $("#settingsCaptureNow")].filter(Boolean);
  const labels = buttons.map((button) => button.textContent);
  buttons.forEach((button) => {
    button.disabled = true;
    button.textContent = "识别中";
  });
  try {
    const result = await api("/api/recording/capture-now", { method: "POST", body: "{}" });
    if (result.summary) {
      state.date = result.summary.day;
      $("#dateInput").value = state.date;
      state.data = result.summary;
      render();
    } else {
      state.data.recording = result;
      renderStatus(result);
    }
    toast(result.skipped ? result.message || "本次已跳过" : "已记录当前屏幕");
  } catch (error) {
    toast(error.message);
  } finally {
    buttons.forEach((button, index) => {
      button.disabled = false;
      button.textContent = labels[index] || "立即记录";
    });
  }
}

async function saveSettings() {
  const button = $("#saveSettings");
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const saved = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        keep_shots: $("#keepShotsInput").checked,
        privacy_mode: $("#privacyModeInput").checked,
        auto_record_enabled: $("#autoRecordEnabled").checked,
        language: $("#languageInput").value,
        ai_analysis_source: $("#aiAnalysisSourceInput").value,
        quick_enter_enabled: $("#quickEnterInput").checked,
        show_dock_icon: $("#dockIconInput").checked,
        memory_enabled: $("#memoryInput").checked,
        woodfish_enabled: $("#woodfishInput").checked,
        analysis_prompt: $("#analysisPromptInput").value,
        shot_retention_days: Number($("#shotRetentionInput").value),
        capture_interval: Number($("#intervalInput").value),
        idle_pause_after: Number($("#idlePauseInput").value),
        capture_scope: $("#captureScopeInput").value,
        ignore_apps: splitList($("#ignoreAppsInput").value),
        ignore_keywords: splitList($("#ignoreKeywordsInput").value),
        activity_categories: splitList($("#activityCategoriesInput").value),
        work_categories: splitList($("#workCategoriesInput").value),
        custom_report_styles: parseStyleMap($("#customReportStylesInput").value),
      }),
    });
    state.settingsTouched = false;
    state.data.settings = { ...state.data.settings, ...saved.settings };
    state.data.activity_categories = saved.settings.activity_categories || state.data.activity_categories || [];
    state.data.work_categories = saved.settings.work_categories || state.data.work_categories || [];
    state.data.displays = state.data.displays
      ? { ...state.data.displays, selected: saved.settings.capture_scope || state.data.displays.selected }
      : state.data.displays;
    state.data.storage = saved.storage || state.data.storage;
    state.data.styles = saved.styles || state.data.styles || [];
    state.data.style_descriptions = saved.style_descriptions || state.data.style_descriptions || {};
    renderSettings(state.data.settings);
    renderDisplays(state.data.displays);
    renderStorage(state.data.storage);
    renderPrivacy(state.data);
    renderStyles(state.data.styles);
    renderSearchControls(state.data.activity_categories);
    renderManualControls(state.data.activity_categories);
    toast("设置已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "保存设置";
  }
}

async function saveModelConfig() {
  const button = $("#saveModelConfig");
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const result = await api("/api/model-config", {
      method: "POST",
      body: JSON.stringify({
        provider: $("#modelProviderInput").value,
        base_url: $("#modelBaseUrlInput").value,
        model: $("#modelNameInput").value,
        api_key: $("#modelApiKeyInput").value,
      }),
    });
    $("#modelApiKeyInput").value = "";
    const cfg = result.model_config || {};
    state.data.settings = {
      ...state.data.settings,
      provider: cfg.provider,
      base_url: cfg.base_url,
      text_model: cfg.model,
      vision_model: cfg.model,
    };
    if (result.health) {
      state.data.health = result.health;
      renderHealth(result.health);
    }
    renderSettings(state.data.settings);
    const keySource = cfg.api_key_source === "keychain" ? "，key 已保存到钥匙串" : (cfg.api_key_present ? "，key 已配置" : "");
    $("#modelConfigStatus").textContent = `网关配置已保存到 ${cfg.env_path || "本机 env.sh"}${keySource}`;
    toast("模型配置已保存");
  } catch (error) {
    $("#modelConfigStatus").textContent = error.message;
    toast("模型配置保存失败");
  } finally {
    button.disabled = false;
    button.textContent = "保存";
  }
}

async function saveAgentContext() {
  const button = $("#saveAgentContext");
  button.disabled = true;
  button.textContent = "保存中";
  const paths = $("#projectPathsInput").value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  try {
    const saved = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({ project_paths: paths }),
    });
    state.data.settings = { ...state.data.settings, ...(saved.settings || {}) };
    state.data.project_context = saved.project_context || state.data.project_context;
    renderProjectContext(state.data.project_context, state.data.settings);
    $("#agentContextNote").textContent = "项目上下文已保存。";
    toast("项目上下文已保存");
  } catch (error) {
    $("#agentContextNote").textContent = error.message;
    toast("保存失败");
  } finally {
    button.disabled = false;
    button.textContent = "保存";
  }
}

async function saveAutoReport() {
  const button = $("#saveAutoReport");
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const result = await api("/api/auto-report", {
      method: "POST",
      body: JSON.stringify({
        enabled: $("#autoReportEnabled").checked,
        time: $("#autoReportTime").value,
        style: $("#autoReportStyle").value,
      }),
    });
    state.data.settings = { ...state.data.settings, ...result.settings };
    state.data.auto_report = result.auto_report;
    renderAutoReport(result.auto_report);
    toast("自动日报设置已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "保存";
  }
}

async function runAutoReportNow() {
  const button = $("#runAutoReportNow");
  button.disabled = true;
  button.textContent = "生成中";
  try {
    const result = await api("/api/auto-report/run-now", {
      method: "POST",
      body: JSON.stringify({ day: state.date }),
    });
    if (result.summary) {
      state.data = result.summary;
      state.data.reports = result.reports || state.data.reports || [];
      render();
    }
    toast(result.skipped ? result.message || "没有记录可生成" : "自动日报已生成并归档");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "立即生成";
  }
}

async function openPermission(kind) {
  await api("/api/permissions/open", {
    method: "POST",
    body: JSON.stringify({ kind }),
  });
  toast("已打开系统设置");
}

async function openLocalPath(kind) {
  const result = await api("/api/open-path", {
    method: "POST",
    body: JSON.stringify({ kind }),
  });
  toast(result.opened?.path ? `已打开：${result.opened.path}` : "已打开目录");
}

async function refreshLogs() {
  const button = $("#refreshLogs");
  button.disabled = true;
  button.textContent = "刷新中";
  try {
    const result = await api("/api/logs");
    state.logs = result.logs;
    renderLogs(result.logs);
    toast("运行日志已刷新");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "刷新";
  }
}

async function createBackup() {
  const button = $("#createBackup");
  button.disabled = true;
  button.textContent = "生成中";
  $("#backupStatus").textContent = "正在打包本地数据...";
  try {
    const result = await api("/api/backup", {
      method: "POST",
      body: JSON.stringify({
        include_shots: $("#backupIncludeShots").checked,
      }),
    });
    const backup = result.backup;
    $("#backupStatus").textContent = backup?.path
      ? `${backup.path}（${backup.size_label || formatBytes(backup.size)}）`
      : "备份已生成";
    toast("本地备份已生成");
  } catch (error) {
    $("#backupStatus").textContent = error.message;
    toast("备份生成失败");
  } finally {
    button.disabled = false;
    button.textContent = "生成备份";
  }
}

async function testModelConnection(buttonSelector = "#testModelConnection", statusSelector = "#modelTestStatus") {
  const button = $(buttonSelector);
  const status = $(statusSelector);
  button.disabled = true;
  button.textContent = "测试中";
  status.textContent = "正在连接模型网关...";
  try {
    const result = await api("/api/model-test", {
      method: "POST",
      body: "{}",
    });
    const test = result.test || {};
    const found = test.model_found === true ? "目标模型已找到" : test.model_found === false ? "未在列表中看到目标模型" : "已读取模型列表";
    status.textContent = `${test.provider || "-"} · ${test.base_url || "-"} · ${found} · ${test.models_count || 0} 个模型 · ${test.elapsed_ms || 0}ms`;
    toast("模型连接正常");
  } catch (error) {
    status.textContent = error.message;
    toast("模型连接失败");
  } finally {
    button.disabled = false;
    button.textContent = "测试连接";
  }
}

async function exportActivities(scope, triggerButton = null) {
  const button = triggerButton || (scope === "day" ? $("#exportDayActivities") : $("#exportAllActivities"));
  const originalText = button?.textContent || "";
  button.disabled = true;
  button.textContent = "导出中";
  $("#exportStatus").textContent = "正在导出活动记录...";
  try {
    const result = await api("/api/export/activities", {
      method: "POST",
      body: JSON.stringify({
        day: scope === "day" ? state.date : "",
      }),
    });
    renderExportResult(result.export, "活动记录");
    toast("活动记录已导出");
  } catch (error) {
    $("#exportStatus").textContent = error.message;
    toast("活动导出失败");
  } finally {
    button.disabled = false;
    button.textContent = originalText || (scope === "day" ? "导出当天活动" : "导出全部活动");
  }
}

async function exportTimelineActivities(triggerButton = null) {
  const button = triggerButton || $("#timelineExportData");
  const originalText = button?.textContent || "";
  const from = $("#timelineFromDate")?.value || state.search.from || state.date;
  const to = $("#timelineToDate")?.value || state.search.to || from;
  button.disabled = true;
  button.textContent = "导出中";
  $("#exportStatus").textContent = "正在导出当前时间线范围...";
  try {
    const result = await api("/api/export/activities", {
      method: "POST",
      body: JSON.stringify({ from, to }),
    });
    renderExportResult(result.export, "时间线活动");
    const range = from === to ? from : `${from} 至 ${to}`;
    toast(`已导出 ${range} 的活动记录`);
  } catch (error) {
    $("#exportStatus").textContent = error.message;
    toast("时间线导出失败");
  } finally {
    button.disabled = false;
    button.textContent = originalText || "导出数据";
  }
}

async function exportReportsData() {
  const button = $("#exportReports");
  button.disabled = true;
  button.textContent = "导出中";
  $("#exportStatus").textContent = "正在导出历史报告...";
  try {
    const result = await api("/api/export/reports", {
      method: "POST",
      body: "{}",
    });
    renderExportResult(result.export, "历史报告");
    toast("历史报告已导出");
  } catch (error) {
    $("#exportStatus").textContent = error.message;
    toast("报告导出失败");
  } finally {
    button.disabled = false;
    button.textContent = "导出报告";
  }
}

async function importJsonFile(file) {
  if (!file) return;
  $("#exportStatus").textContent = "正在读取 JSON 文件...";
  try {
    const text = await file.text();
    const payload = JSON.parse(text);
    const result = await api("/api/import/json", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("#exportStatus").textContent = `导入完成：报告 ${result.imported?.reports || 0} 份，活动 ${result.imported?.activities || 0} 条。`;
    if (result.summary) {
      state.data = result.summary;
      render();
    }
    toast("JSON 数据已导入");
  } catch (error) {
    $("#exportStatus").textContent = error.message;
    toast("导入失败");
  } finally {
    $("#importJsonFile").value = "";
  }
}

async function clearAllData() {
  const confirmText = window.prompt("这会清空活动、报告、备注、聊天和截图。请输入 清空历史 继续。");
  if (confirmText !== "清空历史") {
    toast("已取消清除");
    return;
  }
  const button = $("#clearAllData");
  button.disabled = true;
  button.textContent = "清除中";
  $("#dangerStatus").textContent = "正在清除本机历史数据...";
  try {
    const result = await api("/api/storage/clear-all", { method: "POST", body: "{}" });
    $("#dangerStatus").textContent = `已清除：活动 ${result.cleared?.activities || 0} 条，报告 ${result.cleared?.reports || 0} 份，截图 ${result.cleared?.shots || 0} 个。`;
    if (result.summary) {
      state.data = result.summary;
      render();
    }
    toast("历史数据已清除");
  } catch (error) {
    $("#dangerStatus").textContent = error.message;
    toast("清除失败");
  } finally {
    button.disabled = false;
    button.textContent = "清除全部历史";
  }
}

function renderExportResult(exported, label) {
  $("#exportStatus").textContent = exported?.path
    ? `${label}：${exported.path}（${exported.rows || 0} 行，${exported.size_label || formatBytes(exported.size)}）`
    : `${label}已导出`;
}

function diagnosticsText() {
  const data = state.data || {};
  const health = data.health || {};
  const recording = data.recording || {};
  const model = data.model_config || {};
  const storage = data.storage || {};
  const permissions = data.permissions || {};
  return [
    "书赫日报助手诊断信息",
    `日期：${new Date().toLocaleString()}`,
    `版本：${data.release?.version || "-"}`,
    `记录状态：${recording.running ? "运行中" : "已暂停"} / ${recording.message || "-"}`,
    `健康状态：${health.ok ? "OK" : "需要处理"}`,
    `模型：${model.provider || "-"} ${model.model || "-"} ${model.base_url || "-"}`,
    `权限：屏幕录制 ${permissions.screen_recording?.state || "-"}，辅助功能 ${permissions.accessibility?.state || "-"}`,
    `存储：活动 ${storage.activities || 0} 条，报告 ${storage.reports || 0} 份，截图 ${storage.shot_files || 0} 个`,
    `数据目录：${data.settings?.data_dir || storage.data_dir || "-"}`,
  ].join("\n");
}

async function setAutostart(enabled) {
  const enableButton = $("#enableAutostart");
  const disableButton = $("#disableAutostart");
  enableButton.disabled = true;
  disableButton.disabled = true;
  try {
    const result = await api(enabled ? "/api/autostart/install" : "/api/autostart/uninstall", {
      method: "POST",
      body: "{}",
    });
    state.data.autostart = result.autostart;
    renderAutostart(result.autostart);
    toast(enabled ? "已启用开机自启" : "已关闭开机自启");
  } catch (error) {
    toast(error.message);
    if (state.data?.autostart) renderAutostart(state.data.autostart);
  }
}

async function clearShots() {
  const button = $("#clearShots");
  button.disabled = true;
  button.textContent = "清理中";
  try {
    const result = await api("/api/storage/clear-shots", { method: "POST", body: "{}" });
    state.data.storage = result.storage;
    state.data.items = state.data.items.map((item) => ({ ...item, shot_url: "", shot_path: "" }));
    state.data.segments = (state.data.segments || []).map((item) => ({
      ...item,
      latest_shot_url: "",
      items: (item.items || []).map((entry) => ({ ...entry, shot_url: "", shot_path: "" })),
    }));
    renderStorage(result.storage);
    renderPrivacy(state.data);
    renderTimeline(state.data.segments || state.data.items);
    toast(`已清理 ${result.removed} 个截图`);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "清理截图文件";
  }
}

function splitList(value) {
  return String(value)
    .replace(/，/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseStyleMap(value) {
  const result = {};
  String(value || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const index = line.indexOf("=");
      if (index <= 0) return;
      const name = line.slice(0, index).trim();
      const text = line.slice(index + 1).trim();
      if (name && text) result[name] = text;
    });
  return result;
}

function formatStyleMap(map) {
  return Object.entries(map || {})
    .map(([name, text]) => `${name}=${text}`)
    .join("\n");
}

function isSettingsFocused() {
  return [
    "modelProviderInput",
    "modelBaseUrlInput",
    "modelNameInput",
    "modelApiKeyInput",
    "languageInput",
    "aiAnalysisSourceInput",
    "quickEnterInput",
    "dockIconInput",
    "memoryInput",
    "woodfishInput",
    "analysisPromptInput",
    "autoReportEnabled",
    "autoReportTime",
    "autoReportStyle",
    "autoRecordEnabled",
    "privacyModeInput",
    "keepShotsInput",
    "shotRetentionInput",
    "intervalInput",
    "idlePauseInput",
    "captureScopeInput",
    "ignoreAppsInput",
    "ignoreKeywordsInput",
    "activityCategoriesInput",
    "workCategoriesInput",
    "customReportStylesInput",
  ].includes(document.activeElement?.id);
}

async function generateReport() {
  const button = $("#generateReport");
  const kind = $("#kindSelect").value;
  const style = $("#styleSelect").value;
  const { start, end } = currentReportRange(kind);
  button.disabled = true;
  button.textContent = "生成中";
  setReportPreview("正在调用本地模型生成报告...", { reportId: null, dirty: false, meta: null });
  try {
    const result = await api("/api/report", {
      method: "POST",
      body: JSON.stringify({
        date: end,
        start_date: start,
        end_date: end,
        kind,
        style,
        instruction: $("#reportInstructionInput").value,
      }),
    });
    setReportPreview(result.text || "模型没有返回内容。", {
      reportId: result.report_id || null,
      dirty: false,
      meta: result.report_id ? { day: end, range: currentReportRangeLabel(kind), kind: reportKindLabel(kind), style } : null,
    });
    state.data.reports = result.reports || state.data.reports || [];
    renderReports(state.data.reports);
    renderReportHistoryTable(state.data.reports);
    toast(result.skipped ? "没有活动素材，未生成报告" : "报告已生成");
  } catch (error) {
    setReportPreview(error.message, { reportId: null, dirty: false, meta: null });
    toast("报告生成失败");
  } finally {
    button.disabled = false;
    button.textContent = "生成";
  }
}

async function refreshReports() {
  const result = await api("/api/reports");
  state.data.reports = result.reports || [];
  renderReports(state.data.reports);
  renderReportHistoryTable(state.data.reports);
  toast("历史报告已刷新");
}

async function sendChatQuestion() {
  const button = $("#sendChatQuestion");
  const input = $("#chatQuestion");
  const question = input.value.trim();
  if (!question) {
    toast("先输入一个问题");
    input.focus();
    return;
  }
  button.disabled = true;
  button.textContent = "思考中";
  $("#chatStatus").textContent = "正在根据本地记录回答...";
  try {
    const result = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        date: state.date,
        scope: $("#chatScope").value,
        question,
      }),
    });
    input.value = "";
    state.data.chat = result.chat || state.data.chat || [];
    renderChat(state.data.chat);
    const files = result.message?.project_context?.files || 0;
    $("#chatStatus").textContent = files
      ? `已结合 ${files} 个项目文件；聊天记录只保存在本地数据库。`
      : "聊天记录只保存在本地数据库。";
    toast("已回答");
  } catch (error) {
    $("#chatStatus").textContent = error.message;
    toast("追问失败");
  } finally {
    button.disabled = false;
    button.textContent = "发送";
  }
}

async function deleteChatMessage(id) {
  const result = await api(`/api/chat/${encodeURIComponent(id)}/delete?date=${encodeURIComponent(state.date)}`, {
    method: "POST",
    body: "{}",
  });
  state.data.chat = result.chat || [];
  renderChat(state.data.chat);
  toast(result.ok ? "已删除追问" : "追问不存在");
}

async function refreshDays() {
  const result = await api("/api/days");
  state.data.days = result.days || [];
  renderDays(state.data.days);
  toast("历史日期已刷新");
}

async function saveDayNote() {
  const button = $("#saveDayNote");
  button.disabled = true;
  button.textContent = "保存中";
  state.summarySeq += 1;
  try {
    const result = await api("/api/day-note", {
      method: "POST",
      body: JSON.stringify({
        day: state.date,
        note: $("#dayNoteInput").value,
      }),
    });
    state.dayNoteTouched = false;
    state.data.day_note = result.day_note;
    renderDayNote(result.day_note);
    toast(result.day_note?.note ? "备注已保存" : "备注已清空");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "保存";
  }
}

async function runSearch() {
  const button = $("#runSearch");
  button.disabled = true;
  button.textContent = "搜索中";
  state.search.query = $("#searchQuery").value.trim();
  state.search.category = $("#searchCategory").value;
  state.search.from = $("#searchFrom").value;
  state.search.to = $("#searchTo").value;
  try {
    const params = new URLSearchParams({
      q: state.search.query,
      category: state.search.category,
      from: state.search.from,
      to: state.search.to,
      limit: "100",
    });
    const result = await api(`/api/search?${params.toString()}`);
    state.search.results = result.search?.items || [];
    state.search.searched = true;
    syncTimelineSearchStatus();
    renderSearchResults();
    renderTimeline(state.search.results);
    toast(`找到 ${state.search.results.length} 条记录`);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "搜索";
  }
}

function toggleManualActivity() {
  state.manualOpen = !state.manualOpen;
  $("#manualActivityForm").classList.toggle("open", state.manualOpen);
  $("#toggleManualActivity").textContent = state.manualOpen ? "收起" : "展开";
  if (state.manualOpen) {
    $("#manualSummary").focus();
  }
}

function resetManualActivity(clearSummary = true) {
  const now = new Date();
  $("#manualDay").value = state.date || localDateString(now);
  $("#manualTime").value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  if (clearSummary) {
    $("#manualTitle").value = "";
    $("#manualSummary").value = "";
    $("#manualApp").value = "";
    $("#manualWindow").value = "";
  }
  updateManualSaveState();
}

function setManualRecordMode(mode = "text") {
  const textActive = mode === "text";
  $("#manualTextMode").classList.toggle("active", textActive);
  $("#manualImageMode").classList.toggle("active", !textActive);
}

function composeManualSummary() {
  const title = $("#manualTitle").value.trim();
  const content = $("#manualSummary").value.trim();
  if (title && content) return `${title}\n\n${content}`;
  return content;
}

function updateManualSaveState() {
  $("#saveManualActivity").disabled = !$("#manualSummary").value.trim();
}

function applyManualFormat(format) {
  const input = $("#manualSummary");
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? start;
  const selected = input.value.slice(start, end);
  const fallback = selected || "内容";
  const stripHeading = (value) => value.split("\n").map((line) => line.replace(/^#{1,6}\s+/, "")).join("\n");
  const replacements = {
    bold: `**${fallback}**`,
    italic: `*${fallback}*`,
    underline: `<u>${fallback}</u>`,
    strike: `~~${fallback}~~`,
    unordered: selected ? selected.split("\n").map((line) => `- ${line}`).join("\n") : "- 内容",
    ordered: selected ? selected.split("\n").map((line, index) => `${index + 1}. ${line}`).join("\n") : "1. 内容",
    divider: selected ? `${selected}\n\n---` : "\n---\n",
    h1: `# ${fallback}`,
    h2: `## ${fallback}`,
    h3: `### ${fallback}`,
    paragraph: stripHeading(fallback),
  };
  const next = replacements[format] || fallback;
  input.setRangeText(next, start, end, "select");
  input.focus();
  updateManualSaveState();
}

async function saveManualActivity(event) {
  event.preventDefault();
  if (!$("#manualSummary").value.trim()) {
    updateManualSaveState();
    return;
  }
  const button = $("#saveManualActivity");
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const result = await api("/api/activities/create", {
      method: "POST",
      body: JSON.stringify({
        day: $("#manualDay").value || state.date,
        time: $("#manualTime").value,
        category: $("#manualCategory").value,
        summary: composeManualSummary(),
        app: $("#manualApp").value,
        window_title: $("#manualWindow").value,
      }),
    });
    if (result.summary) {
      state.data = result.summary;
      state.date = state.data.day;
      $("#dateInput").value = state.date;
      render();
    }
    resetManualActivity(true);
    toast("补记已保存");
  } catch (error) {
    toast(error.message);
  } finally {
    button.textContent = "保存补记";
    updateManualSaveState();
  }
}

function clearSearch() {
  $("#searchQuery").value = "";
  if ($("#timelineQuickSearch")) $("#timelineQuickSearch").value = "";
  $("#searchCategory").value = "";
  $("#searchFrom").value = "";
  $("#searchTo").value = "";
  state.search = {
    query: "",
    category: "",
    from: "",
    to: "",
    results: [],
    searched: false,
  };
  syncTimelineSearchStatus();
  renderSearchResults();
  renderTimeline(state.data?.segments || state.data?.items || []);
}

function syncTimelineSearchStatus() {
  const status = $("#timelineSearchStatus");
  if (!status) return;
  const query = state.search.query || $("#timelineQuickSearch")?.value.trim() || "";
  const range = state.search.from || state.search.to ? `${state.search.from || "最早"} 至 ${state.search.to || "今天"}` : "当前日期";
  if (state.search.searched) {
    status.textContent = query ? `搜索：${query} · ${range} · ${state.search.results.length} 条结果` : `已显示 ${range} 的搜索结果`;
    status.classList.toggle("active", Boolean(query || state.search.from || state.search.to));
    return;
  }
  status.textContent = query ? `按 Enter 搜索“${query}”` : "输入关键词后按 Enter 搜索摘要、应用或窗口。";
  status.classList.toggle("active", Boolean(query));
}

function searchAppRecords(appName) {
  if (!appName) return;
  const meta = state.appUsageMeta || {};
  const from = meta.start_day || state.date;
  const to = meta.end_day || state.date;
  $("#searchQuery").value = appName;
  $("#searchCategory").value = "";
  $("#searchFrom").value = from;
  $("#searchTo").value = to;
  state.search = {
    ...state.search,
    query: appName,
    category: "",
    from,
    to,
  };
  navigateTo("timeline");
  runSearch();
}

function selectDay(day) {
  if (!day || day === state.date) return;
  state.date = day;
  state.dayNoteTouched = false;
  state.reportRangeTouched = false;
  state.appPeriod = "day";
  state.appUsage = null;
  state.appUsageMeta = { days: 1, start_day: day, end_day: day, period: "day" };
  $("#dateInput").value = day;
  loadSummary().catch((error) => toast(error.message));
}

async function loadReport(id) {
  const result = await api(`/api/reports/${encodeURIComponent(id)}`);
  const report = result.report;
  setReportPreview(report.body || "", {
    reportId: report.id || null,
    dirty: false,
    meta: report ? { day: report.day, range: reportRangeLabel(report.day, report.kind), kind: report.kind, style: report.style, title: report.title } : null,
  });
  if (report.day) {
    state.date = report.day;
    state.reportRangeTouched = false;
    $("#dateInput").value = report.day;
    syncReportDateRange({ force: true });
    loadSummary().catch((error) => toast(error.message));
  }
  const kindValue = reportKindValue(report.kind);
  if (kindValue) $("#kindSelect").value = kindValue;
  if (report.style && Array.from($("#styleSelect").options).some((option) => option.value === report.style)) {
    $("#styleSelect").value = report.style;
    renderStyleHint();
  }
  toast("已载入历史报告");
}

async function saveReportEdits() {
  if (!state.reportId) {
    toast("请先生成或载入一份报告");
    return;
  }
  const body = getReportPreviewText();
  if (!body) {
    toast("报告正文不能为空");
    return;
  }
  const button = $("#saveReportEdits");
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const result = await api(`/api/reports/${encodeURIComponent(state.reportId)}/update`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
    setReportPreview(result.report?.body || body, { reportId: state.reportId, dirty: false });
    state.data.reports = result.reports || state.data.reports || [];
    renderReports(state.data.reports);
    renderReportHistoryTable(state.data.reports);
    toast("报告修改已保存");
  } catch (error) {
    toast(error.message);
    renderReportEditState();
  }
}

async function deleteReport(id) {
  const result = await api(`/api/reports/${encodeURIComponent(id)}/delete`, {
    method: "POST",
    body: "{}",
  });
  state.data.reports = result.reports || [];
  renderReports(state.data.reports);
  renderReportHistoryTable(state.data.reports);
  toast(result.ok ? "已删除报告" : "报告不存在");
}

async function saveActivity(event) {
  event.preventDefault();
  const form = event.target.closest("[data-activity-editor]");
  const id = form?.dataset.activityId;
  if (!id) return;
  const button = $("#saveActivity");
  button.disabled = true;
  button.textContent = "保存中";
  try {
    const result = await api(`/api/activities/${encodeURIComponent(id)}/update`, {
      method: "POST",
      body: JSON.stringify({
        summary: $("#activitySummaryInput").value,
        category: $("#activityCategoryInput").value,
        app: $("#activityAppInput").value,
        window_title: $("#activityWindowInput").value,
      }),
    });
    if (result.summary) {
      state.data = result.summary;
      state.date = state.data.day;
      $("#dateInput").value = state.date;
      render();
    }
    closeTimelineDetail();
    toast("活动记录已修正");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "保存修正";
  }
}

async function deleteActivity() {
  const form = document.querySelector("[data-activity-editor]");
  const id = form?.dataset.activityId;
  if (!id) return;
  if (!window.confirm("删除这条活动记录？这会影响后续日报统计。")) return;
  const button = $("#deleteActivity");
  button.disabled = true;
  button.textContent = "删除中";
  try {
    const result = await api(`/api/activities/${encodeURIComponent(id)}/delete`, {
      method: "POST",
      body: "{}",
    });
    if (result.summary) {
      state.data = result.summary;
      state.date = state.data.day;
      $("#dateInput").value = state.date;
      render();
    }
    closeTimelineDetail();
    toast("活动记录已删除");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "删除记录";
  }
}

async function copyReport() {
  const text = getReportPreviewText();
  if (!text || text === "报告内容为空。") {
    toast("没有可复制的报告");
    return;
  }
  await copyText(text);
  toast("已复制报告");
}

async function copyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (copied) return;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  throw new Error("复制失败，请手动选择内容复制");
}

function detailCopyText(item) {
  const summaries = item.summaries || item.items?.map((entry) => entry.summary) || [item.summary];
  const unique = [...new Set(summaries.filter(Boolean))];
  return [
    `时间：${formatTimeRange(item).replace("\n", " · ")}`,
    `日期：${item.day || "-"}`,
    `分类：${item.category || "-"}`,
    `应用：${item.app || "未知应用"}`,
    `窗口：${item.window_title || "-"}`,
    `摘要：${unique.join("；") || item.summary || "-"}`,
  ].join("\n");
}

async function copyDetailMaterial() {
  if (!state.detailItem) {
    toast("请先打开一条活动详情");
    return;
  }
  await copyText(detailCopyText(state.detailItem));
  toast("已复制活动素材");
}

function downloadReport() {
  const text = getReportPreviewText();
  if (!text || text === "报告内容为空。") {
    toast("没有可导出的报告");
    return;
  }
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const meta = state.reportMeta || {};
  const kind = meta.kind || reportKindLabel($("#kindSelect").value);
  const style = meta.style || $("#styleSelect").value || "标准";
  const day = meta.day || state.date;
  const range = meta.range || reportRangeLabel(day, kind);
  link.href = url;
  link.download = `${safeDownloadName(`书赫${kind}-${range}-${style}`)}.md`;
  link.click();
  URL.revokeObjectURL(url);
  toast("已导出 Markdown");
}

async function archiveReport() {
  if (!state.reportId) {
    toast("请先生成或载入一份报告");
    return;
  }
  if (state.reportDirty) {
    await saveReportEdits();
  }
  const result = await api(`/api/reports/${encodeURIComponent(state.reportId)}/export`, {
    method: "POST",
    body: "{}",
  });
  toast(result.export?.path ? `已归档：${result.export.path}` : "已归档报告");
}

async function archiveAllReports() {
  const button = $("#archiveAllReports");
  button.disabled = true;
  button.textContent = "归档中";
  try {
    const result = await api("/api/reports/export-all", {
      method: "POST",
      body: "{}",
    });
    const exported = result.export || {};
    toast(exported.count ? `已归档 ${exported.count} 份报告` : "没有历史报告可归档");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "归档全部";
  }
}

function bindEvents() {
  $("#dateInput").value = state.date;
  $("#dateInput").addEventListener("change", (event) => {
    state.date = event.target.value;
    state.dayNoteTouched = false;
    state.reportRangeTouched = false;
    state.appPeriod = "day";
    state.appUsage = null;
    state.appUsageMeta = { days: 1, start_day: state.date, end_day: state.date, period: "day" };
    state.appCustomRange = { from: addDays(state.date, -6), to: state.date };
    loadSummary().catch((error) => toast(error.message));
  });
  $("#refreshButton").addEventListener("click", () => loadSummary().then(() => toast("已刷新")));
  $("#recordButton").addEventListener("click", () => toggleRecording().catch((error) => toast(error.message)));
  $("#captureNowButton").addEventListener("click", () => captureNow().catch((error) => toast(error.message)));
  $("#quickCaptureNow").addEventListener("click", () => captureNow().catch((error) => toast(error.message)));
  $("#quickStartRecording").addEventListener("click", () => {
    if (!state.data?.recording?.running) {
      toggleRecording().catch((error) => toast(error.message));
    } else {
      toast("后台记录已经在运行");
    }
  });
  $("#quickOpenHelp").addEventListener("click", () => {
    navigateTo("help");
  });
  $("#showPreviousRhythm").addEventListener("change", (event) => {
    state.showPreviousRhythm = event.target.checked;
    renderActivityRhythm(state.data?.segments || state.data?.items || [], state.data?.time_heatmap);
  });
  $("#settingsCaptureNow").addEventListener("click", () => captureNow().catch((error) => toast(error.message)));
  $("#generateReport").addEventListener("click", generateReport);
  $("#styleSelect").addEventListener("change", renderStyleHint);
  $("#kindSelect").addEventListener("change", handleReportKindChange);
  $("#reportKindTabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-kind-value]");
    if (!button) return;
    $("#kindSelect").value = button.dataset.kindValue;
    handleReportKindChange();
  });
  $("#reportStartDate").addEventListener("change", () => {
    state.reportRangeTouched = true;
    renderTemplateSelection();
  });
  $("#reportEndDate").addEventListener("change", (event) => {
    state.reportRangeTouched = true;
    state.date = event.target.value || state.date;
    $("#dateInput").value = state.date;
    renderTemplateSelection();
  });
  $("#templateGrid").addEventListener("click", (event) => {
    if (event.target.closest("[data-template-add]")) {
      openCustomTemplateSettings();
      return;
    }
    const detailButton = event.target.closest("[data-template-detail]");
    if (detailButton) {
      event.stopPropagation();
      openTemplateDetail(detailButton.dataset.templateDetail);
      return;
    }
    const card = event.target.closest("[data-template-name]");
    if (!card) return;
    $("#styleSelect").value = card.dataset.templateName;
    renderStyleHint();
  });
  $("#templateGrid").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (event.target.closest("[data-template-add]")) {
      event.preventDefault();
      openCustomTemplateSettings();
      return;
    }
    const card = event.target.closest("[data-template-name]");
    if (!card) return;
    event.preventDefault();
    $("#styleSelect").value = card.dataset.templateName;
    renderStyleHint();
  });
  $("#templateDetailClose").addEventListener("click", closeTemplateDetail);
  $("#templateDetailBackdrop").addEventListener("click", closeTemplateDetail);
  $("#clearReportInstruction").addEventListener("click", focusReportInstruction);
  $("#reportInstructionInput").addEventListener("input", () => {
    $("#reportInstructionCard")?.classList.remove("is-focused");
    renderTemplateSelection();
  });
  $("#saveDayNote").addEventListener("click", () => saveDayNote().catch((error) => toast(error.message)));
  $("#dayNoteInput").addEventListener("input", () => {
    state.dayNoteTouched = true;
    $("#dayNoteStatus").textContent = "有未保存备注";
  });
  $("#saveReportEdits").addEventListener("click", () => saveReportEdits().catch((error) => toast(error.message)));
  $("#reportPreview").addEventListener("input", () => {
    if (state.reportId) {
      state.reportDirty = getReportPreviewText() !== state.reportText;
    }
    renderReportEditState();
  });
  $("#copyReport").addEventListener("click", () => copyReport().catch((error) => toast(error.message)));
  $("#downloadReport").addEventListener("click", downloadReport);
  $("#archiveReport").addEventListener("click", () => archiveReport().catch((error) => toast(error.message)));
  $("#archiveAllReports").addEventListener("click", () => archiveAllReports().catch((error) => toast(error.message)));
  $("#privacyModeInput").addEventListener("change", () => {
    if ($("#privacyModeInput").checked) $("#keepShotsInput").checked = false;
    $("#keepShotsInput").disabled = $("#privacyModeInput").checked;
    state.settingsTouched = true;
  });
  $("#captureScopeInput").addEventListener("change", () => {
    renderDisplays(state.data?.displays);
    state.settingsTouched = true;
  });
  $("#overviewOpenDisplaySettings").addEventListener("click", () => {
    navigateTo("settings");
    setTimeout(() => {
      $("#captureScopeInput")?.scrollIntoView({ behavior: "smooth", block: "center" });
      $("#captureScopeInput")?.focus();
    }, 80);
  });
  $("#displayList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-display-scope]");
    if (!button) return;
    $("#captureScopeInput").value = button.dataset.displayScope;
    renderDisplays(state.data?.displays);
    state.settingsTouched = true;
  });
  $("#sendChatQuestion").addEventListener("click", () => sendChatQuestion().catch((error) => toast(error.message)));
  $("#chatQuestion").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      sendChatQuestion().catch((error) => toast(error.message));
    }
  });
  $("#chatList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-chat-delete]");
    if (button) deleteChatMessage(button.dataset.chatDelete).catch((error) => toast(error.message));
  });
  $("#refreshDays").addEventListener("click", () => refreshDays().catch((error) => toast(error.message)));
  $("#dayList").addEventListener("click", (event) => {
    const dayButton = event.target.closest("[data-day]");
    if (dayButton) selectDay(dayButton.dataset.day);
  });
  $("#trendChart").addEventListener("click", (event) => {
    const dayButton = event.target.closest("[data-trend-day]");
    if (dayButton) selectDay(dayButton.dataset.trendDay);
  });
  $("#calendarHeatmap").addEventListener("click", (event) => {
    const dayButton = event.target.closest("[data-trend-day]");
    if (dayButton) selectDay(dayButton.dataset.trendDay);
  });
  $("#refreshReports").addEventListener("click", () => refreshReports().catch((error) => toast(error.message)));
  $("#historyRefreshReports").addEventListener("click", () => refreshReports().catch((error) => toast(error.message)));
  $("#historyOpenReportsDir").addEventListener("click", () => openLocalPath("reports").catch((error) => toast(error.message)));
  $("#historyClearFilters").addEventListener("click", clearHistoryFilters);
  $("#historyKindFilter").addEventListener("click", (event) => {
    const button = event.target.closest("[data-report-kind]");
    if (!button) return;
    state.reportFilters.kind = button.dataset.reportKind;
    renderReportHistoryTable(state.data?.reports || []);
  });
  $("#historyRangeFilter").addEventListener("click", (event) => {
    const button = event.target.closest("[data-report-range]");
    if (!button) return;
    state.reportFilters.range = button.dataset.reportRange;
    const dates = historyRangeDates(state.reportFilters.range);
    state.reportFilters.from = dates.from;
    state.reportFilters.to = dates.to;
    renderReportHistoryTable(state.data?.reports || []);
  });
  $("#historySearchInput").addEventListener("input", (event) => {
    state.reportFilters.query = event.target.value;
    renderReportHistoryTable(state.data?.reports || []);
  });
  $("#historyFromDate").addEventListener("change", (event) => {
    state.reportFilters.from = event.target.value;
    state.reportFilters.range = "";
    renderReportHistoryTable(state.data?.reports || []);
  });
  $("#historyToDate").addEventListener("change", (event) => {
    state.reportFilters.to = event.target.value;
    state.reportFilters.range = "";
    renderReportHistoryTable(state.data?.reports || []);
  });
  $("#historyReportTable").addEventListener("click", (event) => {
    const generateButton = event.target.closest("[data-history-generate]");
    const loadButton = event.target.closest("[data-report-load]");
    const deleteButton = event.target.closest("[data-history-report-delete]");
    if (generateButton) {
      navigateTo("report");
    } else if (deleteButton) {
      deleteReport(deleteButton.dataset.historyReportDelete).catch((error) => toast(error.message));
    } else if (loadButton) {
      loadReport(loadButton.dataset.reportLoad).catch((error) => toast(error.message));
    }
  });
  $("#runSearch").addEventListener("click", () => runSearch());
  $("#clearSearch").addEventListener("click", clearSearch);
  $("#timelineQuickSearch").addEventListener("input", (event) => {
    $("#searchQuery").value = event.target.value;
    state.search.query = event.target.value;
    state.search.results = [];
    state.search.searched = false;
    syncTimelineSearchStatus();
    renderSearchResults();
    renderTimeline(state.data?.segments || state.data?.items || []);
  });
  $("#timelineClearSearch").addEventListener("click", clearSearch);
  $("#timelineQuickSearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      $("#searchQuery").value = event.target.value;
      runSearch();
    }
  });
  $("#timelineFromDate").addEventListener("change", (event) => {
    $("#searchFrom").value = event.target.value;
    state.search.from = event.target.value;
  });
  $("#timelineToDate").addEventListener("change", (event) => {
    $("#searchTo").value = event.target.value;
    state.search.to = event.target.value;
  });
  $("#refreshHeatmap").addEventListener("click", () => refreshHeatmapRange().catch((error) => toast(error.message)));
  $("#heatmapFromDate").addEventListener("change", (event) => {
    state.heatmapRange.from = event.target.value;
    syncHeatmapRangeStatus();
  });
  $("#heatmapToDate").addEventListener("change", (event) => {
    state.heatmapRange.to = event.target.value;
    syncHeatmapRangeStatus();
  });
  $("#timelineExportData").addEventListener("click", (event) => exportTimelineActivities(event.currentTarget));
  $("#copyTimelineLog").addEventListener("click", () => copyTimelineLog().catch((error) => toast(error.message)));
  $("#reuseTimelineDay").addEventListener("click", reuseTimelineDayDraft);
  $("#timelineAddRecord").addEventListener("click", () => {
    if (!state.manualOpen) toggleManualActivity();
    setManualRecordMode("text");
    resetManualActivity(false);
    $("#manualSummary").focus();
  });
  $$(".timeline-quick-ranges [data-timeline-range]").forEach((button) => {
    button.addEventListener("click", () => {
      state.timelineRange = button.dataset.timelineRange || "today";
      renderTimeline(state.data?.segments || state.data?.items || []);
    });
  });
  $("#showTimelineCategory").addEventListener("change", () => renderTimeline(state.data?.segments || state.data?.items || []));
  $$(".timeline-category-modes [data-timeline-category-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.timelineCategoryMode = button.dataset.timelineCategoryMode || "bar";
      renderTimelineCategoryChart(state.data?.segments || state.data?.items || []);
    });
  });
  $("#appRecordsTable").addEventListener("click", (event) => {
    const button = event.target.closest("[data-app-search]");
    if (button) searchAppRecords(button.dataset.appSearch);
  });
  $("#appPageChart").addEventListener("click", (event) => {
    const button = event.target.closest("[data-app-search]");
    if (button) searchAppRecords(button.dataset.appSearch);
  });
  $$(".app-chart-modes [data-app-chart-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.appChartMode = button.dataset.appChartMode || "bar";
      renderAppPageChart(state.appUsage || state.data?.app_usage || []);
    });
  });
  $$(".app-periods [data-app-period]").forEach((button) => {
    button.addEventListener("click", () => loadAppUsage(button.dataset.appPeriod || "day").catch((error) => toast(error.message)));
  });
  $("#appFromDate").addEventListener("change", (event) => {
    state.appCustomRange.from = event.target.value;
  });
  $("#appToDate").addEventListener("change", (event) => {
    state.appCustomRange.to = event.target.value;
  });
  $("#applyAppRange").addEventListener("click", () => loadAppUsage("custom").catch((error) => toast(error.message)));
  $("#toggleManualActivity").addEventListener("click", toggleManualActivity);
  $("#manualActivityForm").addEventListener("submit", saveManualActivity);
  $("#resetManualActivity").addEventListener("click", () => resetManualActivity(true));
  $("#manualTitle").addEventListener("input", updateManualSaveState);
  $("#manualSummary").addEventListener("input", updateManualSaveState);
  $("#manualTextMode").addEventListener("click", () => {
    setManualRecordMode("text");
    $("#manualSummary").focus();
  });
  $("#manualImageMode").addEventListener("click", () => {
    setManualRecordMode("image");
    toast("传图记录入口已预留，当前先使用文本记录");
    setManualRecordMode("text");
  });
  $$(".manual-editor-toolbar [data-manual-format]").forEach((button) => {
    button.addEventListener("click", () => applyManualFormat(button.dataset.manualFormat));
  });
  $("#searchQuery").addEventListener("keydown", (event) => {
    if (event.key === "Enter") runSearch();
  });
  $("#searchResults").addEventListener("click", (event) => {
    const row = event.target.closest("[data-search-id]");
    if (row) openTimelineDetail(findTimelineItem(row.dataset.searchId));
  });
  $("#searchResults").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const row = event.target.closest("[data-search-id]");
    if (row) {
      event.preventDefault();
      openTimelineDetail(findTimelineItem(row.dataset.searchId));
    }
  });
  $("#reportList").addEventListener("click", (event) => {
    const loadButton = event.target.closest("[data-report-load]");
    const deleteButton = event.target.closest("[data-report-delete]");
    if (deleteButton) {
      deleteReport(deleteButton.dataset.reportDelete).catch((error) => toast(error.message));
    } else if (loadButton) {
      loadReport(loadButton.dataset.reportLoad).catch((error) => toast(error.message));
    }
  });
  $("#saveSettings").addEventListener("click", () => saveSettings().catch((error) => toast(error.message)));
  $("#saveModelConfig").addEventListener("click", () => saveModelConfig().catch((error) => toast(error.message)));
  $("#saveAgentContext").addEventListener("click", () => saveAgentContext().catch((error) => toast(error.message)));
  $("#refreshAgentDocs").addEventListener("click", () => loadAgentDocs({ notify: true }).catch((error) => toast(error.message)));
  $("#copyAgentDocs").addEventListener("click", async () => {
    try {
      if (!state.agentDocs) await loadAgentDocs();
      const text = $("#agentDocsPreview").textContent || state.agentDocs;
      await copyText(text);
      toast("Agent 接入说明已复制");
    } catch (error) {
      toast(error.message);
    }
  });
  $("#copyAgentServiceUrl").addEventListener("click", async () => {
    const url = $("#agentServiceUrl").textContent.trim();
    await copyText(url);
    toast("Agent 服务地址已复制");
  });
  $("#copyAgentDocsUrl").addEventListener("click", async () => {
    const url = $("#agentDocsUrl").textContent.trim();
    await copyText(url);
    toast("Agent 文档接口已复制");
  });
  $("#saveAutoReport").addEventListener("click", () => saveAutoReport().catch((error) => toast(error.message)));
  $("#runAutoReportNow").addEventListener("click", () => runAutoReportNow().catch((error) => toast(error.message)));
  $("#openScreenSettings").addEventListener("click", () => openPermission("screen_recording").catch((error) => toast(error.message)));
  $("#openAccessibilitySettings").addEventListener("click", () => openPermission("accessibility").catch((error) => toast(error.message)));
  $("#enableAutostart").addEventListener("click", () => setAutostart(true));
  $("#disableAutostart").addEventListener("click", () => setAutostart(false));
  $("#openDataDir").addEventListener("click", () => openLocalPath("data").catch((error) => toast(error.message)));
  $("#openReportsDir").addEventListener("click", () => openLocalPath("reports").catch((error) => toast(error.message)));
  $("#openLogsDir").addEventListener("click", () => openLocalPath("logs").catch((error) => toast(error.message)));
  $("#agentOpenLogs").addEventListener("click", () => loadRequestLogs({ show: true, page: 1 }).catch((error) => toast(error.message)));
  $("#requestLogClose").addEventListener("click", closeRequestLogModal);
  $("#requestLogBackdrop").addEventListener("click", closeRequestLogModal);
  $("#refreshRequestLogs").addEventListener("click", () => loadRequestLogs({ notify: true }).catch((error) => toast(error.message)));
  $("#clearRequestLogs").addEventListener("click", () => clearRequestLogs().catch((error) => toast(error.message)));
  $("#requestLogPrev").addEventListener("click", () => changeRequestLogPage(-1));
  $("#requestLogNext").addEventListener("click", () => changeRequestLogPage(1));
  $("#openBackupsDir").addEventListener("click", () => openLocalPath("backups").catch((error) => toast(error.message)));
  $("#openExportsDir").addEventListener("click", () => openLocalPath("exports").catch((error) => toast(error.message)));
  $("#openDesktopApp").addEventListener("click", () => openLocalPath("app").catch((error) => toast(error.message)));
  $("#openApplicationsDir").addEventListener("click", () => openLocalPath("applications").catch((error) => toast(error.message)));
  $("#testAgentConnection").addEventListener("click", () => testModelConnection("#testAgentConnection", "#agentTestStatus"));
  $("#openAgentSettings").addEventListener("click", () => {
    navigateTo("settings");
  });
  $("#privacyClearShots").addEventListener("click", () => clearShots().catch((error) => toast(error.message)));
  $("#privacyCreateBackup").addEventListener("click", () => createBackup().then(() => {
    $("#privacyActionStatus").textContent = $("#backupStatus").textContent;
  }));
  $("#privacyOpenData").addEventListener("click", () => openLocalPath("data").catch((error) => toast(error.message)));
  $("#helpOpenScreenSettings").addEventListener("click", () => openPermission("screen_recording").catch((error) => toast(error.message)));
  $("#helpOpenAccessibilitySettings").addEventListener("click", () => openPermission("accessibility").catch((error) => toast(error.message)));
  $("#helpTestAgent").addEventListener("click", () => testModelConnection("#helpTestAgent", "#helpStatus"));
  $("#helpOpenDataDir").addEventListener("click", () => openLocalPath("data").catch((error) => toast(error.message)));
  $("#helpOpenLogsDir").addEventListener("click", () => openLocalPath("logs").catch((error) => toast(error.message)));
  $("#helpOpenSettings").addEventListener("click", () => {
    navigateTo("settings");
  });
  $("#checkReleaseUpdate").addEventListener("click", () => checkReleaseUpdate().catch((error) => toast(error.message)));
  $("#subscriptionOpenRelease").addEventListener("click", () => {
    const url = state.data?.release?.url;
    if (url) window.open(url, "_blank", "noreferrer");
  });
  $("#copyInviteText").addEventListener("click", async () => {
    const url = state.data?.release?.url || $("#inviteReleaseUrl")?.textContent || "";
    const text = `${$("#inviteCopy")?.textContent || "这是书赫日报助手，数据默认只在电脑本地。"}\n\n下载地址：${url}`;
    await copyText(text);
    toast("邀请文案已复制");
  });
  $("#copyReleaseUrl").addEventListener("click", async () => {
    await copyText(state.data?.release?.url || $("#inviteReleaseUrl")?.textContent || "");
    toast("下载链接已复制");
  });
  $("#supportOpenHelp").addEventListener("click", () => {
    navigateTo("help");
  });
  $("#supportTestAgent").addEventListener("click", () => testModelConnection("#supportTestAgent", "#supportStatus"));
  $("#supportOpenLogs").addEventListener("click", () => openLocalPath("logs").catch((error) => toast(error.message)));
  $("#supportOpenData").addEventListener("click", () => openLocalPath("data").catch((error) => toast(error.message)));
  $("#copyDiagnostics").addEventListener("click", async () => {
    await copyText(diagnosticsText());
    $("#supportStatus").textContent = "诊断信息已复制，不包含 API Key。";
    toast("诊断信息已复制");
  });
  $("#refreshNotifications").addEventListener("click", async () => {
    const result = await api("/api/notifications");
    state.data.notifications = result.notifications || [];
    renderNotifications(state.data.notifications);
    toast("通知中心已刷新");
  });
  $("#createBackup").addEventListener("click", () => createBackup());
  $("#testModelConnection").addEventListener("click", () => testModelConnection());
  $("#exportDayActivities").addEventListener("click", (event) => exportActivities("day", event.currentTarget));
  $("#exportAllActivities").addEventListener("click", (event) => exportActivities("all", event.currentTarget));
  $("#exportReports").addEventListener("click", () => exportReportsData());
  $("#importJsonData").addEventListener("click", () => $("#importJsonFile").click());
  $("#importJsonFile").addEventListener("change", (event) => importJsonFile(event.target.files?.[0]));
  $("#clearAllData").addEventListener("click", () => clearAllData());
  $("#versionOpenRelease").addEventListener("click", () => {
    const url = state.data?.release?.url;
    if (url) window.open(url, "_blank", "noreferrer");
  });
  $("#refreshLogs").addEventListener("click", () => refreshLogs());
  $("#clearShots").addEventListener("click", () => clearShots().catch((error) => toast(error.message)));
  $("#timeline").addEventListener("click", (event) => {
    const row = event.target.closest("[data-timeline-id]");
    if (row) openTimelineDetail(findTimelineItem(row.dataset.timelineId));
  });
  $("#timeline").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const row = event.target.closest("[data-timeline-id]");
    if (row) {
      event.preventDefault();
      openTimelineDetail(findTimelineItem(row.dataset.timelineId));
    }
  });
  $("#detailClose").addEventListener("click", closeTimelineDetail);
  $("#copyDetail").addEventListener("click", () => copyDetailMaterial().catch((error) => toast(error.message)));
  $("#detailBackdrop").addEventListener("click", closeTimelineDetail);
  $("#detailBody").addEventListener("submit", (event) => {
    if (event.target.closest("[data-activity-editor]")) {
      saveActivity(event);
    }
  });
  $("#detailBody").addEventListener("click", (event) => {
    if (event.target.closest("#deleteActivity")) {
      deleteActivity().catch((error) => toast(error.message));
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeTimelineDetail();
    if (event.key === "Escape") closeTemplateDetail();
  });

  [
    "modelProviderInput",
    "modelBaseUrlInput",
    "modelNameInput",
    "modelApiKeyInput",
    "languageInput",
    "aiAnalysisSourceInput",
    "quickEnterInput",
    "dockIconInput",
    "memoryInput",
    "woodfishInput",
    "analysisPromptInput",
    "autoReportEnabled",
    "autoReportTime",
    "autoReportStyle",
    "autoRecordEnabled",
    "privacyModeInput",
    "keepShotsInput",
    "shotRetentionInput",
    "intervalInput",
    "idlePauseInput",
    "captureScopeInput",
    "ignoreAppsInput",
    "ignoreKeywordsInput",
    "activityCategoriesInput",
    "workCategoriesInput",
    "customReportStylesInput",
  ].forEach((id) => {
    $(`#${id}`).addEventListener("input", () => {
      state.settingsTouched = true;
    });
  });

  $$(".timeline-stats .segmented [data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".timeline-stats .segmented [data-filter]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.filter = button.dataset.filter;
      renderTimeline(state.data?.segments || state.data?.items || []);
    });
  });

  $$(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      navigateTo(button.dataset.view);
    });
  });
}

navigateTo(normalizeView(window.location.hash), { replace: true, instant: true });
bindEvents();
window.addEventListener("hashchange", () => navigateTo(window.location.hash, { replace: true, instant: true }));
loadSummary().catch((error) => toast(error.message));
window.setInterval(() => loadSummary().catch(() => {}), 15000);
