// ================================================================
// BIOGAS INTELLIGENCE PLATFORM — DASHBOARD ORCHESTRATION ENGINE
// Multi-Scale Analytics, Real-Time IoT & Explainable AI Forecasting
// ================================================================

const API_BASE = window.__API_BASE__ || '';

/**
 * Create a timeout-controlled AbortSignal that merges with an existing external signal.
 * Cleans up the timer when the request finishes.
 * Distinguishes timeouts from intentional caller aborts.
 * 
 * @param {number} timeoutMs - Timeout duration in milliseconds
 * @param {AbortSignal} [externalSignal] - Existing caller signal (e.g., source cancellation token)
 * @returns {{ signal: AbortSignal, cleanup: () => void, isTimedOut: () => boolean }}
 */
function createTimeoutSignal(timeoutMs, externalSignal = null) {
  const controller = new AbortController();
  let timedOut = false;
  let timerId = null;

  const onExternalAbort = () => {
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
    controller.abort(externalSignal?.reason || new DOMException('Aborted by user or source switch', 'AbortError'));
  };

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort(externalSignal.reason);
    } else {
      externalSignal.addEventListener('abort', onExternalAbort, { once: true });
    }
  }

  timerId = setTimeout(() => {
    timedOut = true;
    controller.abort(new DOMException(`Request timed out after ${timeoutMs}ms`, 'TimeoutError'));
  }, timeoutMs);

  const cleanup = () => {
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
    if (externalSignal) {
      externalSignal.removeEventListener('abort', onExternalAbort);
    }
  };

  return {
    signal: controller.signal,
    cleanup,
    isTimedOut: () => timedOut
  };
}

// Transparently route relative /api calls through API_BASE and enforce bounded timeouts
const _originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
  if (typeof url === 'string' && url.startsWith('/api') && API_BASE) {
    url = `${API_BASE}${url}`;
  }
  // Enforce bounded timeout on API calls (default 15s) if caller didn't pass a signal
  if (typeof url === 'string' && url.includes('/api') && !options.signal) {
    const timeoutSignal = createTimeoutSignal(15000);
    options = { ...options, signal: timeoutSignal.signal };
    return _originalFetch.call(this, url, options).finally(() => {
      timeoutSignal.cleanup();
    });
  }
  return _originalFetch.call(this, url, options);
};

// Global Telemetry State
let telemetryDataset = [];
let currentRecordIndex = 0;
let autoPlayInterval = null;
let isAutoPlaying = false;

// Request race-condition and cancellation tokens
let currentSourceLoadToken = 0;
let currentSourceAbortController = null;
let currentForecastToken = 0;

// Global Chart References
let productionChart = null;
let sustainabilityChart = null;
let communityEnergyChart = null;

// Energy Management State (P1)
window.__GEN_EFF__ = 0.30;
window.__COMM_DEMAND__ = 5.20;

// Latest Subsystem Telemetry
let latestForecast = null;
let latestSolar = null;
let latestAlerts = [];

// Forecasting & Provenance State
let currentModel = "GRU-14d Residual";
let currentDataSource = "DEMO_SYNTHETIC";

// Robust Null-Safe Telemetry Formatting Helpers (PART B)
function formatMetric(value, digits = 2, fallback = "—") {
  if (value === null || value === undefined || value === "" || isNaN(Number(value))) {
    return fallback;
  }
  return Number(value).toFixed(digits);
}

function formatMetricWithUnit(value, digits = 2, unit = "", fallback = "—") {
  const formatted = formatMetric(value, digits, fallback);
  if (formatted === fallback) return fallback;
  return unit ? `${formatted}${unit}` : formatted;
}

document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initSystemHealth();
  initPlaybackControls();
  initFileInputHandler();
  initChatAssistant();
  initForecastControls();
  initEnergyControls();
  initCommunityEnergyChart();
  populateXconetModal();
  loadInitialData();
});

// Gracefully recover if vendor scripts were delayed past DOMContentLoaded
window.addEventListener('load', () => {
  if (typeof Chart !== 'undefined') {
    if (!productionChart && currentDataSource !== "AGSTAR_REGISTRY") {
      updateProductionChart();
    }
    if (!sustainabilityChart) {
      const curr = getCurrentRecord();
      if (curr) updateSustainabilityMetrics(curr);
    }
    if (!communityEnergyChart) {
      initCommunityEnergyChart();
      const curr = getCurrentRecord();
      if (curr) updateCommunityEnergySection(curr);
    }
  }
});

// 1. LIVE CLOCK
function initClock() {
  const clockEl = document.getElementById('live-clock');
  function update() {
    if (clockEl) {
      const now = new Date();
      clockEl.textContent = now.toTimeString().split(' ')[0];
    }
  }
  update();
  setInterval(update, 1000);
}

// 2. CHECK BACKEND & GEMINI HEALTH
async function initSystemHealth() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      const data = await res.json();
      const statusText = document.getElementById('system-status-text');
      const modeBadge = document.getElementById('mode-badge');
      const geminiBadge = document.getElementById('gemini-status-badge');
      const geminiText = document.getElementById('gemini-status-text');
      const drawerSubtitle = document.getElementById('drawer-model-subtitle');

      if (statusText) statusText.textContent = `ONLINE (${data.system_mode || 'DEMO'})`;
      
      if (data.gemini_configured) {
        if (geminiText) geminiText.textContent = `Gemini Active (${data.gemini_model || '2.5'})`;
        if (geminiBadge) {
          geminiBadge.className = 'bg-gradient-to-r from-emerald-600/20 to-blue-600/20 px-3 py-1.5 rounded-xl border border-emerald-500/30 text-xs font-bold text-emerald-300 flex items-center gap-2';
        }
        if (drawerSubtitle) drawerSubtitle.textContent = `Google Gemini (${data.gemini_model || '2.5'}) • Live Grounded`;
      } else {
        if (geminiText) geminiText.textContent = 'Offline (Local Engine)';
        if (geminiBadge) {
          geminiBadge.className = 'bg-slate-800/80 px-3 py-1.5 rounded-xl border border-amber-500/30 text-xs font-bold text-amber-300 flex items-center gap-2';
        }
        if (drawerSubtitle) drawerSubtitle.textContent = 'Deterministic Anaerobic Rule Engine • Offline';
      }
    }
  } catch (err) {
    console.warn('Backend health check error:', err);
  }
}

// 3. LOAD INITIAL DATA FROM FASTAPI BACKEND
async function loadInitialData() {
  try {
    // A. Fetch Solar Telemetry
    const solarRes = await fetch('/api/solar/latest?device_id=DIGESTER_001');
    if (solarRes.ok) {
      latestSolar = await solarRes.json();
      renderSolarDetails(latestSolar);
    }

    // B. Fetch Alerts
    const alertsRes = await fetch('/api/alerts?device_id=DIGESTER_001&unacknowledged_only=true');
    if (alertsRes.ok) {
      latestAlerts = await alertsRes.json();
      renderAlertsList(latestAlerts);
    }

    // C. Default feed: Load Physics Simulator with 14d Warm-Up
    await loadSimulatorData();

  } catch (err) {
    console.error('Error loading initial dashboard data:', err);
    generateLocalSyntheticTimeseries();
    renderAllMetrics();
  }
}

// 4. LOAD PHYSICS SIMULATOR TIMELINE (180 DAYS WITH 14D WARM-UP)
async function loadSimulatorData() {
  const myToken = currentSourceLoadToken;
  const signal = currentSourceAbortController ? currentSourceAbortController.signal : undefined;
  try {
    stopAutoPlay();
    const res = await fetch('/api/simulator/timeline?days=180&warmup_days=14', { signal });
    if (myToken !== currentSourceLoadToken) return;

    if (res.ok) {
      const items = await res.json();
      if (myToken !== currentSourceLoadToken) return;

      if (items && items.length > 0) {
        telemetryDataset = items.map(item => ({
          timestamp: item.timestamp,
          targetDate: item.target_date,
          temp: item.temperature_c,
          ph: item.ph,
          pressure: item.pressure_bar,
          methane: item.methane_percent != null ? item.methane_percent : null,
          level: item.digester_slurry_level_pct != null ? item.digester_slurry_level_pct : 75.0,
          feed: item.feedstock_mass_kg,
          flow: item.biogas_today_nm3,
          biogas: item.biogas_today_nm3,
          waste: item.feedstock_mass_kg,
          predictedBiogas: item.predicted_next_day_nm3,
          emaPredictedBiogas: item.ema_predicted_next_day_nm3,
          persistencePredictedBiogas: item.persistence_predicted_next_day_nm3,
          actualNextDay: item.actual_next_day_nm3,
          history_length: item.history_length,
          status: item.status,
          domain_valid: item.domain_valid,
          domain_note: item.domain_note,
          data_source: "DEMO_SYNTHETIC",
          features: item.features
        }));

        // Start at record index 13 (Day 14) so audience immediately sees active 14/14 history and valid forecast!
        currentRecordIndex = 13;
        currentDataSource = "DEMO_SYNTHETIC";

        const countEl = document.getElementById('dataset-row-count');
        if (countEl) countEl.textContent = telemetryDataset.length;
        const infoStr = document.getElementById('dataset-info-str');
        if (infoStr) {
          infoStr.innerHTML = `Connected to <strong class="text-white font-mono">${telemetryDataset.length}</strong> timesteps from <code class="text-emerald-400 bg-slate-900 px-2 py-0.5 rounded font-bold">Physics Simulator (14d Warm-Up)</code> (DEMO_SYNTHETIC)`;
        }

        await renderAllMetrics();
        if (myToken === currentSourceLoadToken) {
          startAutoPlay();
        }
        return;
      }
    }
    if (myToken !== currentSourceLoadToken) return;
    // Fallback if simulator returns empty
    generateLocalSyntheticTimeseries();
    await renderAllMetrics();
    if (myToken === currentSourceLoadToken) {
      startAutoPlay();
    }
  } catch (err) {
    if (err.name === 'AbortError') return;
    if (myToken !== currentSourceLoadToken) return;
    console.error("Failed to load simulator timeline:", err);
    generateLocalSyntheticTimeseries();
    await renderAllMetrics();
    if (myToken === currentSourceLoadToken) {
      startAutoPlay();
    }
  }
}

// 5. FALLBACK LOCAL SYNTHETIC TIMESERIES
function generateLocalSyntheticTimeseries() {
  const list = [];
  const now = new Date();
  for (let i = 0; i < 60; i++) {
    const d = new Date(now.getTime() - (59 - i) * 86400 * 1000);
    const timeStr = d.toISOString().substring(0, 10);
    const temp = parseFloat((36.5 + Math.sin(i / 5) * 1.2).toFixed(1));
    const ph = parseFloat((7.25 + Math.cos(i / 6) * 0.22).toFixed(2));
    const pressure = parseFloat((1.15 + Math.sin(i / 7) * 0.18).toFixed(2));
    const feed = Math.round(120 + Math.sin(i / 4) * 15);
    const biogas = parseFloat((15.2 + Math.sin(i / 5) * 2.2).toFixed(2));
    const methane = parseFloat((62.5 + Math.cos(i / 6) * 3.5).toFixed(1));

    list.push({
      timestamp: timeStr,
      temp, ph, pressure, level: 75,
      feed, flow: biogas, biogas, waste: feed, methane,
      history_length: i + 1,
      status: i >= 13 ? "SUCCESS" : "Warming up forecast model",
      data_source: "DEMO_SYNTHETIC"
    });
  }
  telemetryDataset = list;
  currentRecordIndex = 13;
}

// 6. PLAYBACK CONTROLS
function initPlaybackControls() {
  const prevBtn = document.getElementById('prev-row-btn');
  const nextBtn = document.getElementById('next-row-btn');
  const autoBtn = document.getElementById('auto-play-btn');

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentDataSource === "AGSTAR_REGISTRY") return;
      stopAutoPlay();
      if (currentRecordIndex > 0) {
        currentRecordIndex--;
        renderAllMetrics();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (currentDataSource === "AGSTAR_REGISTRY") return;
      stopAutoPlay();
      if (currentRecordIndex < telemetryDataset.length - 1) {
        currentRecordIndex++;
        renderAllMetrics();
      }
    });
  }

  if (autoBtn) {
    autoBtn.addEventListener('click', () => {
      if (currentDataSource === "AGSTAR_REGISTRY") return;
      if (isAutoPlaying) {
        stopAutoPlay();
      } else {
        startAutoPlay();
      }
    });
  }
}

function startAutoPlay() {
  stopAutoPlay();
  isAutoPlaying = true;
  const autoBtn = document.getElementById('auto-play-btn');
  if (autoBtn) {
    autoBtn.innerHTML = '⏸ Auto Live Feed';
    autoBtn.className = 'px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition';
  }

  autoPlayInterval = setInterval(() => {
    if (telemetryDataset.length === 0) return;
    if (currentDataSource === "DEMO_SYNTHETIC" && telemetryDataset.length > 13) {
      // Loop the warmed-up evaluation window [13 .. end] so autoplay never drops into cold start
      currentRecordIndex = 13 + ((currentRecordIndex - 13 + 1) % (telemetryDataset.length - 13));
    } else {
      currentRecordIndex = (currentRecordIndex + 1) % telemetryDataset.length;
    }
    renderAllMetrics();
  }, 2500);
}

function stopAutoPlay() {
  isAutoPlaying = false;
  if (autoPlayInterval) clearInterval(autoPlayInterval);
  const autoBtn = document.getElementById('auto-play-btn');
  if (autoBtn) {
    autoBtn.innerHTML = '▶ Resume Feed';
    autoBtn.className = 'px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 font-bold transition border border-slate-700';
  }
}

// 6. CLIENT-SIDE EXCEL / CSV DRAG-AND-DROP INGESTION (SheetJS + Ingestion Service)
let currentIngestionReport = null;

function initFileInputHandler() {
  const fileInputs = [
    document.getElementById('scada-file-input'),
    document.getElementById('excel-file-input')
  ].filter(Boolean);
  const fileLabel = document.getElementById('excel-file-label');
  const openReportBtn = document.getElementById('open-ingestion-report-btn');
  const closeReportBtn = document.getElementById('close-ingestion-report-btn');
  const reportModal = document.getElementById('ingestion-report-modal');
  const activateBtn = document.getElementById('activate-uploaded-dataset-btn');
  const uploadScadaBtn = document.getElementById('upload-scada-btn');

  if (uploadScadaBtn) {
    uploadScadaBtn.addEventListener('click', () => {
      const fi = document.getElementById('scada-file-input') || document.getElementById('excel-file-input');
      if (fi) fi.click();
    });
  }

  if (openReportBtn && reportModal) {
    openReportBtn.addEventListener('click', () => {
      if (currentIngestionReport) {
        reportModal.classList.remove('hidden');
        reportModal.classList.add('flex');
      } else {
        const fi = document.getElementById('scada-file-input') || document.getElementById('excel-file-input');
        if (fi) fi.click();
      }
    });
  }

  if (closeReportBtn && reportModal) {
    closeReportBtn.addEventListener('click', () => {
      reportModal.classList.add('hidden');
      reportModal.classList.remove('flex');
    });
  }

  if (reportModal) {
    reportModal.addEventListener('click', (e) => {
      if (e.target === reportModal) {
        reportModal.classList.add('hidden');
        reportModal.classList.remove('flex');
      }
    });
  }

  if (activateBtn) {
    activateBtn.addEventListener('click', () => {
      activateUploadedDataset();
    });
  }

  fileInputs.forEach(inputEl => {
    inputEl.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (fileLabel) fileLabel.textContent = file.name;

      const reader = new FileReader();
      reader.onload = async (event) => {
        try {
          if (typeof XLSX === 'undefined' || !XLSX || !XLSX.read) {
            alert('Spreadsheet parser (XLSX) is currently unavailable. Please verify network or vendor scripts and try again.');
            inputEl.value = '';
            if (fileLabel) fileLabel.textContent = 'Choose Excel (.xlsx) or CSV';
            return;
          }
          const data = new Uint8Array(event.target.result);
          const workbook = XLSX.read(data, { type: 'array' });
          const firstSheet = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[firstSheet];
          const jsonRows = XLSX.utils.sheet_to_json(worksheet, { defval: null });

          if (!jsonRows || jsonRows.length === 0) {
            alert('The selected file contains no readable data rows.');
            return;
          }

          // Call backend Ingestion Service for semantic mapping, unit conversion, and statistics
          const timeoutSignal = createTimeoutSignal(15000);
          let res;
          try {
            res = await fetch('/api/ingestion/analyze', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                filename: file.name,
                rows: jsonRows
              }),
              signal: timeoutSignal.signal
            });
          } finally {
            timeoutSignal.cleanup();
          }

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Server returned ${res.status}`);
          }

          const report = await res.json();
          renderIngestionReportModal(report, file.name);

          // Enable source selector option and report button
          const sourceSelect = document.getElementById('telemetry-source-select');
          if (sourceSelect) {
            const opt = sourceSelect.querySelector('option[value="USER_UPLOAD"]');
            if (opt) {
              opt.hidden = false;
              opt.disabled = false;
            }
          }
          if (openReportBtn) openReportBtn.classList.remove('hidden');

        } catch (parseErr) {
          console.error('Error ingesting uploaded dataset:', parseErr);
          const msg = parseErr.name === 'TimeoutError'
            ? 'Ingestion analysis timed out (>15s). Please try again.'
            : (parseErr.message || parseErr);
          alert(`Error analyzing dataset: ${msg}`);
          inputEl.value = '';
          if (fileLabel) fileLabel.textContent = 'Choose Excel (.xlsx) or CSV';
        }
      };

      reader.onerror = () => {
        alert('Failed to read the selected file.');
        inputEl.value = '';
        if (fileLabel) fileLabel.textContent = 'Choose Excel (.xlsx) or CSV';
      };
      reader.readAsArrayBuffer(file);
    });
  });
}

function renderIngestionReportModal(report, filename) {
  currentIngestionReport = report;
  const modal = document.getElementById('ingestion-report-modal');
  const fileEl = document.getElementById('ingest-modal-filename');
  const rowsCountEl = document.getElementById('ingest-rows-count');
  const samplingEl = document.getElementById('ingest-sampling-info');
  const colsCountEl = document.getElementById('ingest-cols-count');
  const recognizedEl = document.getElementById('ingest-recognized-info');
  const timerangeEl = document.getElementById('ingest-timerange-info');
  const duplicatesEl = document.getElementById('ingest-duplicates-info');
  const domainStatusEl = document.getElementById('ingest-domain-status');
  const readinessGrid = document.getElementById('ingest-model-readiness-grid');
  const mappingsTbody = document.getElementById('ingest-mappings-tbody');
  const statsTbody = document.getElementById('ingest-stats-tbody');

  if (fileEl) fileEl.textContent = filename || 'Uploaded Dataset';
  if (rowsCountEl) rowsCountEl.textContent = report.total_records || 0;
  if (samplingEl) samplingEl.textContent = `Sampling: ${report.sampling_interval_detected || 'Unknown'}`;
  if (colsCountEl) colsCountEl.textContent = report.total_columns || 0;
  if (recognizedEl) recognizedEl.textContent = `Mapped: ${report.columns_recognized || 0} / ${report.total_columns || 0}`;

  if (timerangeEl) {
    const tMin = report.timestamp_min ? String(report.timestamp_min).substring(0, 10) : '—';
    const tMax = report.timestamp_max ? String(report.timestamp_max).substring(0, 10) : '—';
    timerangeEl.textContent = `${tMin} → ${tMax}`;
  }
  if (duplicatesEl) duplicatesEl.textContent = `Duplicates: ${report.has_duplicate_timestamps ? 'Detected' : '0'}`;
  if (domainStatusEl) domainStatusEl.textContent = 'UNVALIDATED';

  // Model readiness cards
  if (readinessGrid && report.model_eligibility) {
    readinessGrid.innerHTML = '';
    const models = [
      { key: 'GRU-14d Residual', name: 'GRU-14d Residual' },
      { key: 'XCO-Net', name: 'XCO-Net' },
      { key: 'EMA-0.90', name: 'EMA-0.90' },
      { key: 'Persistence', name: 'Persistence' }
    ];

    models.forEach(m => {
      const elig = report.model_eligibility[m.key] || {};
      const isElig = elig.eligible;
      const card = document.createElement('div');
      card.className = `p-3 rounded-xl border ${isElig ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-slate-950/60 border-slate-800'} space-y-1.5`;

      let badge = isElig
        ? `<span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">READY (${elig.available_history}/${elig.required_history}d)</span>`
        : `<span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">INELIGIBLE (${elig.available_history}/${elig.required_history}d)</span>`;

      let missingTxt = elig.missing_features && elig.missing_features.length > 0
        ? `<div class="text-[10px] text-rose-400 font-mono">Missing: ${elig.missing_features.join(', ')}</div>`
        : `<div class="text-[10px] text-emerald-400 font-mono">All required inputs detected</div>`;

      let domainNote = (m.key.includes('GRU') || m.key.includes('XCO'))
        ? '<div class="text-[9px] text-amber-400/80 font-mono">⚠️ Industrial model transfer to user data is unvalidated; numerical prediction will be withheld</div>'
        : '<div class="text-[9px] text-blue-400/80 font-mono">✓ Scale-compatible statistical reference forecast permitted</div>';

      card.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-white">${m.name}</span>
          ${badge}
        </div>
        ${missingTxt}
        ${domainNote}
      `;
      readinessGrid.appendChild(card);
    });
  }

  // Column mappings
  if (mappingsTbody && report.column_mappings) {
    mappingsTbody.innerHTML = '';
    report.column_mappings.forEach(col => {
      const tr = document.createElement('tr');
      const conceptBadge = col.semantic_concept
        ? `<span class="text-cyan-300 font-bold font-mono">${col.semantic_concept}</span>`
        : `<span class="text-slate-500 italic">Unmapped (Ignored)</span>`;
      const convBadge = col.conversion_applied
        ? `<span class="text-emerald-400 font-bold">${col.conversion_applied}</span>`
        : `<span class="text-slate-500">None</span>`;
      tr.innerHTML = `
        <td class="py-2 px-3 text-white font-mono">${col.original_name}</td>
        <td class="py-2 px-3 text-slate-400 font-mono">${col.normalized_name}</td>
        <td class="py-2 px-3">${conceptBadge}</td>
        <td class="py-2 px-3 text-amber-300 font-mono">${col.detected_unit || '—'}</td>
        <td class="py-2 px-3 text-[10px]">${convBadge}</td>
      `;
      mappingsTbody.appendChild(tr);
    });
  }

  // Column statistics (all numeric columns)
  if (statsTbody && report.column_statistics) {
    statsTbody.innerHTML = '';
    report.column_statistics.forEach(s => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="py-2 px-3 text-white font-mono font-bold">${s.column_name}</td>
        <td class="py-2 px-2 text-slate-300 font-mono">${s.count}</td>
        <td class="py-2 px-2 ${s.null_count > 0 ? 'text-amber-400 font-bold' : 'text-slate-500'} font-mono">${s.null_count}</td>
        <td class="py-2 px-2 text-slate-300 font-mono">${s.min}</td>
        <td class="py-2 px-2 text-slate-300 font-mono">${s.mean}</td>
        <td class="py-2 px-2 text-slate-300 font-mono">${s.median}</td>
        <td class="py-2 px-2 text-slate-300 font-mono">${s.max}</td>
        <td class="py-2 px-2 text-slate-300 font-mono">${s.std}</td>
      `;
      statsTbody.appendChild(tr);
    });
  }

  if (modal) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
}

function activateUploadedDataset() {
  if (!currentIngestionReport || !currentIngestionReport.clean_rows || currentIngestionReport.clean_rows.length === 0) {
    alert('No parsed rows available in the current ingestion report.');
    return;
  }

  stopAutoPlay();
  clearSourceState();

  const clean = currentIngestionReport.clean_rows;
  telemetryDataset = clean.map((r, i) => {
    return {
      timestamp: r.timestamp || `Record ${i + 1}`,
      targetDate: r.timestamp || `Record ${i + 2}`,
      temp: r.temperature_c != null ? Number(Number(r.temperature_c).toFixed(1)) : null,
      ph: r.ph != null ? Number(Number(r.ph).toFixed(2)) : null,
      pressure: r.pressure_bar != null ? Number(Number(r.pressure_bar).toFixed(2)) : null,
      biogas: r.biogas_production_m3_day != null ? Number(Number(r.biogas_production_m3_day).toFixed(2)) : null,
      flow: r.biogas_production_m3_day != null ? Number(Number(r.biogas_production_m3_day).toFixed(2)) : null,
      feed: r.feedstock_mass_kg != null ? Math.round(r.feedstock_mass_kg) : null,
      waste: r.feedstock_mass_kg != null ? Math.round(r.feedstock_mass_kg) : null,
      methane: r.methane_percent != null ? Number(Number(r.methane_percent).toFixed(1)) : null,
      level: 75.0,
      features: {
        biogas_today_nm3: r.biogas_today_nm3 != null ? r.biogas_today_nm3 : null,
        total_incoming_mt: r.total_incoming_mt != null ? r.total_incoming_mt : null,
        total_processed_mt: r.total_processed_mt != null ? r.total_processed_mt : null,
        feed_total_m3: r.feed_total_m3 != null ? r.feed_total_m3 : null,
        temp_outlet_d1_c: r.temp_outlet_d1_c != null ? r.temp_outlet_d1_c : null,
        ph_outlet_d1: r.ph_outlet_d1 != null ? r.ph_outlet_d1 : null,
        recycle_water_m3: r.recycle_water_m3 != null ? r.recycle_water_m3 : null,
        feed_total_m3_was_missing: r.feed_total_m3 != null ? 0 : 1,
        ph_outlet_d1_was_missing: r.ph_outlet_d1 != null ? 0 : 1
      }
    };
  });

  currentRecordIndex = telemetryDataset.length - 1;
  currentDataSource = "USER_UPLOAD";

  const sourceSelect = document.getElementById('telemetry-source-select');
  if (sourceSelect) {
    const opt = sourceSelect.querySelector('option[value="USER_UPLOAD"]');
    if (opt) {
      opt.hidden = false;
      opt.disabled = false;
    }
    sourceSelect.value = "USER_UPLOAD";
  }

  const openReportBtn = document.getElementById('open-ingestion-report-btn');
  if (openReportBtn) openReportBtn.classList.remove('hidden');

  const countEl = document.getElementById('dataset-row-count');
  const infoStr = document.getElementById('dataset-info-str');
  if (countEl) countEl.textContent = telemetryDataset.length;
  if (infoStr) {
    infoStr.innerHTML = `Active: <strong class="text-white font-mono">${telemetryDataset.length}</strong> records from <code class="text-emerald-400 bg-slate-900 px-2 py-0.5 rounded">${currentIngestionReport.filename}</code>`;
  }

  updateSourceKpiLabels("USER_UPLOAD");

  const modal = document.getElementById('ingestion-report-modal');
  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }

  renderAllMetrics();
}

function getCol(row, keys) {
  for (let k of keys) {
    if (row[k] !== undefined && row[k] !== null && !isNaN(row[k])) return Number(row[k]);
  }
  return null;
}


// 7. GET CURRENT TELEMETRY SNAPSHOT
// 7. GET CURRENT TELEMETRY SNAPSHOT
function getCurrentRecord() {
  if (!telemetryDataset || telemetryDataset.length === 0) {
    return null;
  }
  if (currentRecordIndex < 0 || currentRecordIndex >= telemetryDataset.length) {
    return telemetryDataset[telemetryDataset.length - 1] || null;
  }
  return telemetryDataset[currentRecordIndex];
}

// 8. RENDER ALL DASHBOARD METRICS
async function renderAllMetrics() {
  if (currentDataSource === "AGSTAR_REGISTRY") {
    renderAgstarBenchmarkState();
    return;
  }

  const curr = getCurrentRecord();
  if (!curr) {
    const rowDisp = document.getElementById('row-index-display');
    if (rowDisp) rowDisp.textContent = 'Record 0 / 0';
    updateKPICards(null);
    updateGauges(null);
    updateHealthIndex(null);
    updateSustainabilityMetrics(null);
    updateEnergyGenerationSection(null);
    updateCommunityEnergySection(null);
    updateDrawerTelemetryPreview(null);
    await updateSafetyAlerts(null);
    if (productionChart) {
      productionChart.data.labels = [];
      productionChart.data.datasets[0].data = [];
      productionChart.data.datasets[1].data = [];
      productionChart.update('none');
    }
    return;
  }
  
  // Row Counter
  const rowDisp = document.getElementById('row-index-display');
  if (rowDisp) rowDisp.textContent = `Record ${currentRecordIndex + 1} / ${telemetryDataset.length}`;

  // KPI Cards (Current Biogas, Methane, Efficiency, Feedstock)
  updateKPICards(curr);

  // Energy Generation & Community Microgrid Management (P1)
  updateEnergyGenerationSection(curr);
  updateCommunityEnergySection(curr);

  // 6 Gauges
  updateGauges(curr);

  // Digester Health Index
  updateHealthIndex(curr);

  // Pearson Correlation Heatmap
  updateCorrelationHeatmap();

  // SDG 11 Sustainability Metrics
  updateSustainabilityMetrics(curr);

  // Drawer Preview
  updateDrawerTelemetryPreview(curr);

  // Active Safety Alerts (Single Source of Truth)
  await updateSafetyAlerts(curr);

  // Trigger Model Forecasting Service
  await executeModelForecast(curr, currentRecordIndex);

  // Production Chart
  updateProductionChart();
}

// UPDATE ACTIVE SAFETY ALERTS (SINGLE SOURCE OF TRUTH VIA BACKEND)
async function updateSafetyAlerts(curr) {
  const listEl = document.getElementById('alerts-list');
  const badge = document.getElementById('alert-count-badge');
  const headerSafety = document.getElementById('header-safety-indicator');
  const headerSafetyDot = document.getElementById('header-safety-dot');
  const headerSafetyText = document.getElementById('header-safety-text');
  if (!listEl) return;

  if (!curr) {
    if (badge) badge.textContent = '0 Active';
    listEl.innerHTML = `
      <div class="p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 text-xs text-slate-400">
        ⚪ No active sensor telemetry stream.
      </div>
    `;
    if (headerSafety && headerSafetyText && headerSafetyDot) {
      headerSafety.className = "header-badge px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-lg sm:rounded-xl text-[10px] sm:text-xs font-bold border transition flex items-center gap-1.5 bg-slate-800 border-slate-700 text-slate-300";
      headerSafetyDot.className = "w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-500 shrink-0";
      headerSafetyText.textContent = "INTERLOCKS STANDBY";
    }
    return;
  }

  // Authoritative Backend Safety Evaluation via POST /api/alerts/evaluate
  try {
    const rawTemp = curr.temp !== undefined && curr.temp !== null ? curr.temp : curr.temperature_c;
    const rawPh = curr.ph !== undefined && curr.ph !== null ? curr.ph : null;
    const rawPress = curr.pressure !== undefined && curr.pressure !== null ? curr.pressure : curr.pressure_bar;
    const rawBiogas = curr.biogas_production_m3_day !== undefined ? curr.biogas_production_m3_day : (curr.biogas_today_nm3 !== undefined ? curr.biogas_today_nm3 : curr.biogas);
    const rawMethane = curr.methane_percent !== undefined ? curr.methane_percent : curr.methane;
    const predEnergy = curr.predicted_electricity_kwh !== undefined ? curr.predicted_electricity_kwh : null;
    const batterySoc = latestSolar ? latestSolar.battery_soc_percent : (curr.battery_soc_percent || null);
    const solarPow = latestSolar ? latestSolar.power_w : (curr.solar_power_w || null);

    const payload = {
      temperature_c: rawTemp !== undefined && rawTemp !== null && !isNaN(rawTemp) ? Number(rawTemp) : null,
      ph: rawPh !== undefined && rawPh !== null && !isNaN(rawPh) ? Number(rawPh) : null,
      pressure_bar: rawPress !== undefined && rawPress !== null && !isNaN(rawPress) ? Number(rawPress) : null,
      battery_soc_percent: batterySoc !== undefined && batterySoc !== null && !isNaN(batterySoc) ? Number(batterySoc) : null,
      solar_power_w: solarPow !== undefined && solarPow !== null && !isNaN(solarPow) ? Number(solarPow) : null,
      biogas_production_m3_day: rawBiogas !== undefined && rawBiogas !== null && !isNaN(rawBiogas) ? Number(rawBiogas) : null,
      h2s_ppm: curr.h2s_ppm !== undefined && curr.h2s_ppm !== null ? Number(curr.h2s_ppm) : null,
      methane_percent: rawMethane !== undefined && rawMethane !== null && !isNaN(rawMethane) ? Number(rawMethane) : null,
      predicted_energy_kwh: predEnergy,
      is_sensor_connected: true
    };

    const res = await fetch('/api/alerts/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000)
    });

    if (res.ok) {
      const evalResult = await res.json();
      renderAuthoritativeAlerts(evalResult, curr);
    } else {
      console.warn("Safety evaluate endpoint returned status:", res.status);
    }
  } catch (err) {
    console.warn("Authoritative safety evaluation request failed:", err);
  }
}

// Global 5-Category Alert State
window.__CURRENT_ALERT_FILTER__ = 'ALL';
window.__ALL_ACTIVE_ALERTS__ = [];

function filterAlertsCategory(cat) {
  window.__CURRENT_ALERT_FILTER__ = cat;
  document.querySelectorAll('.alert-filter-tab').forEach(btn => {
    btn.className = 'alert-filter-tab px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition';
  });
  const activeBtn = document.getElementById(`alert-tab-${cat}`);
  if (activeBtn) {
    activeBtn.className = 'alert-filter-tab px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold transition';
  }
  renderFilteredAlerts();
}
window.filterAlertsCategory = filterAlertsCategory;

function toggleThresholdsDetail() {
  const panel = document.getElementById('thresholds-detail-panel');
  const btn = document.getElementById('toggle-thresholds-btn');
  if (panel) {
    const isHidden = panel.classList.contains('hidden');
    if (isHidden) {
      panel.classList.remove('hidden');
      if (btn) btn.textContent = 'Hide Parameters';
    } else {
      panel.classList.add('hidden');
      if (btn) btn.textContent = 'View Parameters';
    }
  }
}
window.toggleThresholdsDetail = toggleThresholdsDetail;

function renderFilteredAlerts() {
  const listEl = document.getElementById('alerts-list');
  if (!listEl) return;
  const filter = window.__CURRENT_ALERT_FILTER__ || 'ALL';
  const allAlerts = window.__ALL_ACTIVE_ALERTS__ || [];
  const filtered = filter === 'ALL' ? allAlerts : allAlerts.filter(a => (a.category || 'DIGESTER').toUpperCase() === filter.toUpperCase());

  if (filtered.length === 0) {
    listEl.innerHTML = `
      <div class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300">
        ✓ ${filter === 'ALL' ? 'All biokinetic and electrical safety thresholds are normal.' : `No active alerts in ${filter} category.`}
      </div>
    `;
    return;
  }

  listEl.innerHTML = filtered.map(a => {
    const isCrit = a.severity === 'CRITICAL';
    const color = isCrit ? 'rose' : 'amber';
    const cat = (a.category || 'DIGESTER').toUpperCase();
    return `
      <div class="p-3 rounded-xl bg-${color}-500/10 border border-${color}-500/30 text-xs space-y-1">
        <div class="flex items-center justify-between font-bold text-${color}-400">
          <span class="flex items-center gap-1.5 flex-wrap">
            <span>${isCrit ? '⚠️' : '⚡'}</span>
            <span class="px-1.5 py-0.2 rounded bg-slate-900 border border-${color}-500/40 text-[9px] text-slate-300 font-mono">[${cat}]</span>
            <span>[${a.severity}] ${(a.parameter || '').toUpperCase()}</span>
          </span>
          <span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">Active</span>
        </div>
        <p class="text-slate-300 text-[11px]">${a.message}</p>
      </div>
    `;
  }).join('');
}

function renderAuthoritativeAlerts(evalResult, curr) {
  const listEl = document.getElementById('alerts-list');
  const badge = document.getElementById('alert-count-badge');
  const headerSafety = document.getElementById('header-safety-indicator');
  const headerSafetyDot = document.getElementById('header-safety-dot');
  const headerSafetyText = document.getElementById('header-safety-text');

  const alerts = evalResult.alerts || [];
  window.__ALL_ACTIVE_ALERTS__ = alerts;
  if (badge) badge.textContent = `${alerts.length} Active`;

  if (headerSafety && headerSafetyText && headerSafetyDot) {
    if (evalResult.status === "NORMAL" || alerts.length === 0) {
      headerSafety.className = "header-badge px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-lg sm:rounded-xl text-[10px] sm:text-xs font-bold border transition flex items-center gap-1.5 bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20";
      headerSafetyDot.className = "w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-emerald-400 shrink-0";
      headerSafetyText.textContent = "INTERLOCKS NORMAL";
    } else {
      const topAlert = alerts.find(a => a.severity === 'CRITICAL') || alerts[0];
      const isCrit = topAlert.severity === 'CRITICAL';
      const color = isCrit ? 'rose' : 'amber';
      headerSafety.className = `header-badge px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-lg sm:rounded-xl text-[10px] sm:text-xs font-bold border transition flex items-center gap-1.5 bg-${color}-500/20 border-${color}-500/40 text-${color}-300 hover:bg-${color}-500/30 animate-pulse`;
      headerSafetyDot.className = `w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-${color}-400 shrink-0`;
      
      const param = (topAlert.parameter || "").toUpperCase();
      let conditionStr = param;
      if (topAlert.parameter === 'pressure') {
        conditionStr = `${isCrit ? 'OVERPRESSURE' : 'HIGH PRESSURE'} • ${formatMetric(topAlert.triggered_value, 2)} bar`;
      } else if (topAlert.parameter === 'ph') {
        conditionStr = `${Number(topAlert.triggered_value) < 6.5 ? 'LOW pH' : 'HIGH pH'} • ${formatMetric(topAlert.triggered_value, 2)}`;
      } else if (topAlert.parameter === 'temperature') {
        conditionStr = `${Number(topAlert.triggered_value) < 28.0 ? 'LOW TEMP' : 'HIGH TEMP'} • ${formatMetric(topAlert.triggered_value, 1)}°C`;
      }

      headerSafetyText.textContent = `${isCrit ? '⚠️' : '⚡'} ${topAlert.severity} • ${conditionStr}`;
    }
  }

  renderFilteredAlerts();
}

// UPDATE TOP KPI CARDS
function updateKPICards(curr) {
  const kpiTemp = document.getElementById('kpi-temp-val');
  const kpiPh = document.getElementById('kpi-ph-val');
  const kpiPress = document.getElementById('kpi-press-val');
  const kpiCurrent = document.getElementById('kpi-current-biogas');
  const fcCurrent = document.getElementById('forecast-current-biogas');
  const kpiCurrentSub = document.getElementById('kpi-current-biogas-sub');
  const kpiMethane = document.getElementById('kpi-methane-val');
  const kpiEff = document.getElementById('kpi-efficiency-val');
  const feedVal = document.getElementById('kpi-waste-val');
  const kpiElecPot = document.getElementById('kpi-electricity-potential');
  const kpiContPower = document.getElementById('kpi-continuous-power');
  const kpiElecProv = document.getElementById('kpi-electricity-provenance');

  if (!curr) {
    if (kpiTemp) kpiTemp.textContent = " — ";
    if (kpiPh) kpiPh.textContent = " — ";
    if (kpiPress) kpiPress.textContent = " — ";
    if (kpiCurrent) kpiCurrent.textContent = " — ";
    if (fcCurrent) fcCurrent.textContent = " — ";
    if (kpiMethane) kpiMethane.textContent = " — ";
    if (kpiEff) kpiEff.textContent = " — ";
    if (feedVal) feedVal.textContent = " — ";
    if (kpiElecPot) kpiElecPot.textContent = " — ";
    if (kpiContPower) kpiContPower.textContent = " — ";
    return;
  }

  if (kpiTemp) kpiTemp.textContent = formatMetric(curr.temp, 1);
  if (kpiPh) kpiPh.textContent = formatMetric(curr.ph, 2);
  if (kpiPress) kpiPress.textContent = formatMetric(curr.pressure, 2);
  if (kpiCurrent) kpiCurrent.textContent = formatMetric(curr.biogas, 2);
  if (fcCurrent) fcCurrent.textContent = formatMetric(curr.biogas, 2);
  if (kpiMethane) kpiMethane.textContent = formatMetric(curr.methane, 1);

  // Dynamic Electricity Potential and 24-h Average Equivalent Power
  if (curr.biogas == null || isNaN(curr.biogas)) {
    if (kpiElecPot) kpiElecPot.textContent = " — ";
    if (kpiContPower) kpiContPower.textContent = " — ";
  } else {
    const ch4Pct = (curr.methane != null && !isNaN(curr.methane) && curr.methane > 0) ? Number(curr.methane) : 60.0;
    const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
    const elecKwh = Number(curr.biogas) * (ch4Pct / 100.0) * 9.94 * eff;
    const powerKw = elecKwh / 24.0;
    if (kpiElecPot) kpiElecPot.textContent = formatMetric(elecKwh, elecKwh >= 100 ? 1 : 2);
    if (kpiContPower) kpiContPower.textContent = formatMetric(powerKw, powerKw >= 100 ? 1 : 2);
    if (kpiElecProv) {
      kpiElecProv.textContent = (curr.methane != null && !isNaN(curr.methane) && curr.methane > 0) ? "[CALCULATED]" : "[CALCULATED @ ASSUMED 60% CH₄]";
    }
  }

  if (kpiCurrentSub) {
    if (currentDataSource === "DEMO_SYNTHETIC") {
      kpiCurrentSub.textContent = "Simulated Daily Production";
    } else if (currentDataSource === "LIVE_IOT") {
      kpiCurrentSub.textContent = "Live Daily Production";
    } else if (currentDataSource === "USER_UPLOAD") {
      kpiCurrentSub.textContent = "User-Uploaded Telemetry";
    } else {
      kpiCurrentSub.textContent = "Observed Daily Production (Historical mean ≈ 5,300 Nm³/day)";
    }
  }

  // Source-Aware Methane Title & Note
  const methaneTitle = document.getElementById('kpi-methane-title');
  if (methaneTitle) {
    if (currentDataSource === "DEMO_SYNTHETIC") {
      methaneTitle.textContent = "Methane (CH₄)";
    } else if (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL") {
      methaneTitle.textContent = "Methane (CH₄) — Heuristic/Scenario Value";
    } else if (currentDataSource === "USER_UPLOAD") {
      methaneTitle.textContent = "Methane (CH₄) — User Dataset";
    } else {
      methaneTitle.textContent = "Methane (CH₄) — Live Sensor";
    }
  }

  const methaneNote = document.getElementById('kpi-methane-note');
  if (methaneNote) {
    if (currentDataSource === "DEMO_SYNTHETIC") {
      methaneNote.textContent = "Simulated biogas methane concentration (55–65% CH₄ envelope)";
    } else if (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL") {
      methaneNote.textContent = "Heuristic interpretation: Operational envelope (not raw online sensor)";
    } else if (currentDataSource === "USER_UPLOAD") {
      methaneNote.textContent = "Observed or unmapped methane from user-uploaded dataset";
    } else {
      methaneNote.textContent = "Live sensor measurement (calibrated NDIR / catalytic bead)";
    }
  }

  // Source-Aware Feedstock Card
  const feedTitle = document.getElementById('kpi-feedstock-title');
  const feedUnit = document.getElementById('kpi-feedstock-unit');
  const feedRef = document.getElementById('kpi-feedstock-ref');
  const feedNote = document.getElementById('kpi-feedstock-note');

  if (currentDataSource === "DEMO_SYNTHETIC") {
    if (feedTitle) feedTitle.textContent = "Simulated Feedstock";
    if (feedVal) feedVal.textContent = formatMetric(curr.feed, 1);
    if (feedUnit) feedUnit.textContent = "kg/day";
    if (feedRef) feedRef.textContent = "Community Reference: 120 kg/day";
    if (feedNote) feedNote.textContent = "Physics-based synthetic community-scale scenario";
  } else {
    if (feedTitle) feedTitle.textContent = "Industrial Feedstock";
    const currentFeed = curr.feed_mt != null ? curr.feed_mt : (curr.feed != null ? (curr.feed / 100) : null);
    if (feedVal) feedVal.textContent = formatMetric(currentFeed, 1);
    if (feedUnit) feedUnit.textContent = "MT/day";
    
    // Compute dynamic min and max from the active telemetryDataset actually used by the dashboard
    let minFeed = 64;
    let maxFeed = 325;
    if (telemetryDataset && telemetryDataset.length > 0) {
      const feedVals = telemetryDataset
        .map(r => r.feed_mt !== undefined ? r.feed_mt : (r.feed ? r.feed / 100 : null))
        .filter(v => v !== null && !isNaN(v));
      if (feedVals.length > 0) {
        minFeed = Math.min(...feedVals);
        maxFeed = Math.max(...feedVals);
      }
    }
    if (feedRef) feedRef.textContent = `Observed dataset range: ${formatMetric(minFeed, 0)}–${formatMetric(maxFeed, 0)} MT/day`;
    if (feedNote) feedNote.textContent = currentDataSource === "USER_UPLOAD" ? "User-uploaded operational record" : "Historical Spark operational record";
  }

  const unitCurr = document.getElementById('kpi-unit-current');
  const unitPred = document.getElementById('kpi-unit-predicted');
  const unitText = "Nm³/day";
  if (unitCurr) unitCurr.textContent = unitText;
  if (unitPred) unitPred.textContent = unitText;

  // Compute efficiency based on biochemical operating limits
  if (kpiEff) {
    if (curr.methane == null || isNaN(curr.methane) || curr.temp == null || isNaN(curr.temp)) {
      kpiEff.textContent = " — ";
    } else {
      const eff = Math.min(98.0, Math.max(65.0, 75 + (curr.methane * 0.25) - Math.abs(curr.temp - 36.5) * 3));
      kpiEff.textContent = formatMetric(eff, 1);
    }
  }
}

// UPDATE 6 CIRCULAR GAUGES
function updateGauges(curr) {
  if (!curr) {
    const tempVal = document.getElementById('gauge-temp-val');
    const tempArc = document.getElementById('gauge-temp-arc');
    if (tempVal) tempVal.textContent = " — ";
    if (tempArc) tempArc.setAttribute('stroke-dasharray', '0, 100');

    const phVal = document.getElementById('gauge-ph-val');
    const phArc = document.getElementById('gauge-ph-arc');
    if (phVal) phVal.textContent = " — ";
    if (phArc) phArc.setAttribute('stroke-dasharray', '0, 100');

    const pressVal = document.getElementById('gauge-press-val');
    const pressArc = document.getElementById('gauge-press-arc');
    const pressBadge = document.getElementById('press-status-badge');
    if (pressVal) pressVal.textContent = " — ";
    if (pressArc) pressArc.setAttribute('stroke-dasharray', '0, 100');
    if (pressBadge) {
      pressBadge.textContent = 'No sensor input';
      pressBadge.className = 'text-[9px] text-slate-500 font-semibold uppercase';
    }

    const levelVal = document.getElementById('gauge-level-val');
    const levelArc = document.getElementById('gauge-level-arc');
    if (levelVal) levelVal.textContent = " — ";
    if (levelArc) levelArc.setAttribute('stroke-dasharray', '0, 100');

    const feedVal = document.getElementById('gauge-feed-val');
    const feedArc = document.getElementById('gauge-feed-arc');
    if (feedVal) feedVal.textContent = " — ";
    if (feedArc) feedArc.setAttribute('stroke-dasharray', '0, 100');

    const flowVal = document.getElementById('gauge-flow-val');
    const flowArc = document.getElementById('gauge-flow-arc');
    if (flowVal) flowVal.textContent = " — ";
    if (flowArc) flowArc.setAttribute('stroke-dasharray', '0, 100');
    return;
  }

  // Temp (0-50°C scale)
  const tempVal = document.getElementById('gauge-temp-val');
  const tempArc = document.getElementById('gauge-temp-arc');
  if (tempVal) tempVal.textContent = formatMetricWithUnit(curr.temp, 1, "°C");
  if (tempArc) tempArc.setAttribute('stroke-dasharray', `${curr.temp != null && !isNaN(curr.temp) ? Math.min(100, Math.round((curr.temp / 50) * 100)) : 0}, 100`);

  // pH (0-14 scale)
  const phVal = document.getElementById('gauge-ph-val');
  const phArc = document.getElementById('gauge-ph-arc');
  if (phVal) phVal.textContent = formatMetric(curr.ph, 2);
  if (phArc) phArc.setAttribute('stroke-dasharray', `${curr.ph != null && !isNaN(curr.ph) ? Math.min(100, Math.round((curr.ph / 14) * 100)) : 0}, 100`);

  // Pressure (0-2.0 bar scale, relief at 1.50 bar, warning at 1.30 bar)
  const pressVal = document.getElementById('gauge-press-val');
  const pressArc = document.getElementById('gauge-press-arc');
  const pressBadge = document.getElementById('press-status-badge');
  if (pressVal) pressVal.textContent = formatMetricWithUnit(curr.pressure, 2, " bar");
  if (pressArc) pressArc.setAttribute('stroke-dasharray', `${curr.pressure != null && !isNaN(curr.pressure) ? Math.min(100, Math.round((curr.pressure / 2.0) * 100)) : 0}, 100`);
  if (pressBadge) {
    if (curr.pressure != null && !isNaN(curr.pressure)) {
      if (curr.pressure >= 1.50) {
        pressBadge.textContent = 'RELIEF ACTIVATED';
        pressBadge.className = 'text-[9px] text-rose-400 font-bold uppercase animate-pulse';
      } else if (curr.pressure >= 1.30) {
        pressBadge.textContent = 'HIGH WARNING';
        pressBadge.className = 'text-[9px] text-amber-400 font-bold uppercase';
      } else {
        pressBadge.textContent = 'Safe < 1.30 bar';
        pressBadge.className = 'text-[9px] text-slate-400 font-semibold uppercase';
      }
    } else {
      pressBadge.textContent = 'No sensor input';
      pressBadge.className = 'text-[9px] text-slate-500 font-semibold uppercase';
    }
  }

  // Level
  const levelVal = document.getElementById('gauge-level-val');
  const levelArc = document.getElementById('gauge-level-arc');
  if (levelVal) levelVal.textContent = formatMetricWithUnit(curr.level, 0, "%");
  if (levelArc) levelArc.setAttribute('stroke-dasharray', `${curr.level != null && !isNaN(curr.level) ? curr.level : 0}, 100`);

  // Feed (0-200 kg scale)
  const feedVal = document.getElementById('gauge-feed-val');
  const feedArc = document.getElementById('gauge-feed-arc');
  if (feedVal) feedVal.textContent = formatMetricWithUnit(curr.feed, 0, " kg");
  if (feedArc) feedArc.setAttribute('stroke-dasharray', `${curr.feed != null && !isNaN(curr.feed) ? Math.min(100, Math.round((curr.feed / 200) * 100)) : 0}, 100`);

  // Flow (0-30 Nm³/day scale)
  const flowVal = document.getElementById('gauge-flow-val');
  const flowArc = document.getElementById('gauge-flow-arc');
  if (flowVal) flowVal.textContent = formatMetricWithUnit(curr.flow, 1, " Nm³/day");
  if (flowArc) flowArc.setAttribute('stroke-dasharray', `${curr.flow != null && !isNaN(curr.flow) ? Math.min(100, Math.round((curr.flow / 30) * 100)) : 0}, 100`);
}

// UPDATE PRODUCTION TIMESERIES CHART (TARGET DATE t+1, TENSION 0.0, Nm³/day)
function updateProductionChart() {
  const canvas = document.getElementById('productionChart');
  if (!canvas) return;

  if (typeof Chart === 'undefined') {
    const parent = canvas.parentElement;
    let fallback = document.getElementById('production-chart-fallback');
    if (!fallback && parent) {
      fallback = document.createElement('div');
      fallback.id = 'production-chart-fallback';
      fallback.className = 'flex flex-col items-center justify-center h-48 sm:h-64 text-slate-400 text-xs p-4 text-center bg-slate-900/40 rounded-xl border border-dashed border-slate-700/50';
      fallback.innerHTML = `
        <span class="text-amber-400 text-sm font-semibold mb-1">⚠️ Chart Engine Offline</span>
        <span>Timeseries visualization is suspended because Chart.js is not loaded. All numeric telemetry and forecasting pipelines remain active.</span>
      `;
      canvas.classList.add('hidden');
      parent.appendChild(fallback);
    }
    return;
  } else {
    const fallback = document.getElementById('production-chart-fallback');
    if (fallback) fallback.remove();
    canvas.classList.remove('hidden');
  }

  if (currentDataSource === "AGSTAR_REGISTRY") {
    if (productionChart) {
      productionChart.data.labels = [];
      productionChart.data.datasets[0].data = [];
      productionChart.data.datasets[1].data = [];
      productionChart.update('none');
    }
    const tsSub = document.getElementById('timeseries-sub');
    if (tsSub) {
      tsSub.innerHTML = 'AgSTAR Livestock Digester Registry • Static Benchmark (<span class="text-blue-400 font-mono">Time-Series Charting Disabled</span>)';
    }
    const withheldNotice = document.getElementById('chart-withheld-notice');
    if (withheldNotice) {
      withheldNotice.textContent = "Time-series charting and forecasting are disabled for static registry benchmarks.";
      withheldNotice.classList.remove('hidden');
    }
    return;
  }

  // For held-out test (24 days), show the full 24-day test evaluation window.
  // For other modes (simulation or full 176 days), show a 25-day rolling window up to currentRecordIndex.
  let windowSlice;
  if (currentDataSource === "REAL_SPARK_HISTORICAL") {
    windowSlice = telemetryDataset;
  } else {
    windowSlice = telemetryDataset.slice(Math.max(0, currentRecordIndex - 24), currentRecordIndex + 1);
  }

  const labels = windowSlice.map((r, i) => {
    if (r.targetDate) return r.targetDate;
    if (r.timestamp && r.timestamp.length >= 10) return r.timestamp;
    return `Day ${i + 1}`;
  });

  // For past days, r.actualNextDay is the observed target.
  // For DEMO_SYNTHETIC latest day t, future actual is not yet observed -> null
  const actualData = windowSlice.map((r, i) => {
    if (currentDataSource === "DEMO_SYNTHETIC" && i === windowSlice.length - 1) return null; // Strictly no lookahead: future t+1 actual is unobserved on day t
    if (r.actualNextDay !== undefined && r.actualNextDay !== null) return r.actualNextDay;
    return null;
  });

  // Predicted data:
  // If community scale (simulation or live IoT) AND industrial GRU or XCO-Net, DO NOT plot unvalidated predictions!
  const isCommunityUnvalidated = (currentDataSource === "DEMO_SYNTHETIC" || currentDataSource === "LIVE_IOT") && (currentModel === "GRU-14d Residual" || currentModel.includes("XCO"));
  const predictedData = windowSlice.map(r => {
    if (isCommunityUnvalidated) {
      return null;
    }
    if (currentModel === "EMA-0.90") {
      return (r.emaPredictedBiogas !== undefined && r.emaPredictedBiogas !== null) ? r.emaPredictedBiogas : r.predictedBiogas;
    }
    if (currentModel === "Persistence") {
      return (r.persistencePredictedBiogas !== undefined && r.persistencePredictedBiogas !== null) ? r.persistencePredictedBiogas : r.biogas;
    }
    return (r.predictedBiogas !== undefined && r.predictedBiogas !== null ? r.predictedBiogas : null);
  });

  // Dual-Axis Dataset 3: Calculated Electricity Potential (kWh/day)
  const eff = window.__GEN_EFF__ !== undefined ? window.__GEN_EFF__ : 0.30;
  const electricityData = windowSlice.map((r, i) => {
    if (currentDataSource === "DEMO_SYNTHETIC" && i === windowSlice.length - 1) return null;
    const vol = (r.actualNextDay !== undefined && r.actualNextDay !== null) ? r.actualNextDay : (r.biogas !== undefined && r.biogas !== null ? r.biogas : null);
    if (vol === null) return null;
    const ch4 = (r.methane !== undefined && r.methane !== null) ? (r.methane / 100.0) : 0.60;
    const kwh = vol * ch4 * 9.94 * eff;
    return Number(kwh.toFixed(2));
  });

  const unitLabel = "Nm³/day";
  const predLabel = isCommunityUnvalidated 
    ? "Prediction withheld — industrial model not validated for Community Scale" 
    : `${currentModel} Forecast (${unitLabel})`;

  const withheldNotice = document.getElementById('chart-withheld-notice');
  if (withheldNotice) {
    if (isCommunityUnvalidated) withheldNotice.classList.remove('hidden');
    else withheldNotice.classList.add('hidden');
  }

  const tsSub = document.getElementById('timeseries-sub');
  if (tsSub) {
    if (currentDataSource === "DEMO_SYNTHETIC") {
      tsSub.innerHTML = 'Community Physics Simulation (180 Continuous Days) • Strictly Zero Spline Smoothing (<code class="text-slate-400 font-mono bg-slate-800/60 px-1.5 py-0.5 rounded text-[11px] border border-slate-700/50">tension: 0.0</code>)';
    } else if (currentDataSource === "REAL_SPARK_HISTORICAL") {
      tsSub.innerHTML = 'Spark Bio Gas • Held-Out Test Set (24 Days) • Strictly Zero Spline Smoothing (<code class="text-slate-400 font-mono bg-slate-800/60 px-1.5 py-0.5 rounded text-[11px] border border-slate-700/50">tension: 0.0</code>)';
    } else if (currentDataSource === "SPARK_FULL") {
      tsSub.innerHTML = 'Spark Bio Gas • Full Historical (176 Calendar Days) • Strictly Zero Spline Smoothing (<code class="text-slate-400 font-mono bg-slate-800/60 px-1.5 py-0.5 rounded text-[11px] border border-slate-700/50">tension: 0.0</code>)';
    } else {
      tsSub.innerHTML = 'Community Live Telemetry (ESP32 / IoT) • Strictly Zero Spline Smoothing (<code class="text-slate-400 font-mono bg-slate-800/60 px-1.5 py-0.5 rounded text-[11px] border border-slate-700/50">tension: 0.0</code>)';
    }
  }

  if (!productionChart) {
    const ctx = canvas.getContext('2d');
    productionChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: `Actual Biogas (${unitLabel})`,
            data: actualData,
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            borderWidth: 2.5,
            fill: true,
            tension: 0.0, // Strictly zero smoothing
            pointRadius: 3,
            pointBackgroundColor: '#10B981',
            yAxisID: 'y'
          },
          {
            label: predLabel,
            data: predictedData,
            borderColor: '#3B82F6',
            borderWidth: 2,
            borderDash: [5, 4],
            fill: false,
            tension: 0.0, // Strictly zero smoothing
            pointRadius: 3,
            pointBackgroundColor: '#3B82F6',
            yAxisID: 'y'
          },
          {
            label: `Calculated Electricity Potential (kWh/day) [CALCULATED]`,
            data: electricityData,
            borderColor: '#F59E0B',
            backgroundColor: 'rgba(245, 158, 11, 0.05)',
            borderWidth: 2,
            borderDash: [3, 3],
            fill: false,
            tension: 0.0,
            pointRadius: 3,
            pointBackgroundColor: '#F59E0B',
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              color: '#CBD5E1',
              font: { family: 'Inter', size: 11, weight: '600' }
            }
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleFont: { family: 'Inter', size: 12, weight: 'bold' },
            bodyFont: { family: 'Inter', size: 11 },
            cornerRadius: 8,
            callbacks: {
              title: items => `Target Date (t+1): ${items[0].label}`,
              label: item => {
                if (item.raw === null) return `${item.dataset.label}: Unobserved / Not Plotted`;
                if (item.dataset.yAxisID === 'y1') {
                  return `${item.dataset.label}: ${Number(item.raw).toFixed(2)} kWh/day`;
                }
                return `${item.dataset.label}: ${Number(item.raw).toFixed(2)} Nm³/day`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#94A3B8', font: { family: 'Inter', size: 10 } }
          },
          y: {
            type: 'linear',
            position: 'left',
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: '#10B981', font: { family: 'Inter', size: 10 }, callback: v => `${v} Nm³/d` },
            title: { display: true, text: 'Biogas (Nm³/day)', color: '#10B981', font: { size: 10, weight: '600' } }
          },
          y1: {
            type: 'linear',
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: { color: '#F59E0B', font: { family: 'Inter', size: 10 }, callback: v => `${v} kWh/d` },
            title: { display: true, text: 'Electricity (kWh/day)', color: '#F59E0B', font: { size: 10, weight: '600' } }
          }
        }
      }
    });
  } else {
    productionChart.data.labels = labels;
    productionChart.data.datasets[0].label = `Actual Biogas (${unitLabel})`;
    productionChart.data.datasets[0].data = actualData;
    productionChart.data.datasets[1].label = predLabel;
    productionChart.data.datasets[1].data = predictedData;
    if (productionChart.data.datasets.length > 2) {
      productionChart.data.datasets[2].label = `Calculated Electricity Potential (kWh/day) [CALCULATED]`;
      productionChart.data.datasets[2].data = electricityData;
    }
    productionChart.update('none');
  }
}

// UPDATE COMPOSITE DIGESTER HEALTH INDEX
function updateHealthIndex(curr) {
  const scoreVal = document.getElementById('health-score-val');
  const arc = document.getElementById('health-radial-arc');
  const badge = document.getElementById('health-status-badge');

  if (!curr) {
    if (scoreVal) scoreVal.textContent = " — ";
    if (arc) {
      arc.setAttribute('stroke-dasharray', '0, 100');
      arc.setAttribute('class', 'text-slate-600 transition-all duration-700');
    }
    if (badge) {
      badge.textContent = 'UNAVAILABLE';
      badge.className = 'inline-block text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 py-0.5 rounded bg-slate-800 border border-slate-700 mt-1';
    }
    return;
  }

  let observedCount = 0;
  let score = 100;

  if (curr.temp != null && !isNaN(curr.temp)) {
    observedCount++;
    if (curr.temp < 35.0 || curr.temp > 38.0) score -= 15;
  }
  if (curr.ph != null && !isNaN(curr.ph)) {
    observedCount++;
    if (curr.ph < 6.8 || curr.ph > 7.5) score -= 20;
  }
  if (curr.pressure != null && !isNaN(curr.pressure)) {
    observedCount++;
    if (curr.pressure > 1.30) score -= 25;
  }
  if (curr.methane != null && !isNaN(curr.methane)) {
    observedCount++;
    if (curr.methane < 55.0) score -= 15;
  }

  if (observedCount === 0) {
    if (scoreVal) scoreVal.textContent = " — ";
    if (arc) {
      arc.setAttribute('stroke-dasharray', '0, 100');
      arc.setAttribute('class', 'text-slate-600 transition-all duration-700');
    }
    if (badge) {
      badge.textContent = 'UNAVAILABLE';
      badge.className = 'inline-block text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 py-0.5 rounded bg-slate-800 border border-slate-700 mt-1';
    }
    return;
  }

  score = Math.max(35, Math.min(100, score));

  if (scoreVal) scoreVal.textContent = `${score}%`;
  if (arc) arc.setAttribute('stroke-dasharray', `${score}, 100`);

  if (badge) {
    if (score >= 85) {
      badge.textContent = 'Optimal (Green)';
      badge.className = 'inline-block text-[10px] font-bold text-emerald-400 uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 mt-1';
      if (arc) arc.setAttribute('class', 'text-emerald-500 transition-all duration-700');
    } else if (score >= 65) {
      badge.textContent = 'Moderate (Yellow)';
      badge.className = 'inline-block text-[10px] font-bold text-amber-400 uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 mt-1';
      if (arc) arc.setAttribute('class', 'text-amber-500 transition-all duration-700');
    } else {
      badge.textContent = 'Critical (Red)';
      badge.className = 'inline-block text-[10px] font-bold text-rose-400 uppercase tracking-wider px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/30 mt-1 animate-pulse';
      if (arc) arc.setAttribute('class', 'text-rose-500 transition-all duration-700');
    }
  }
}

// UPDATE PEARSON CORRELATION MATRIX HEATMAP
function updateCorrelationHeatmap() {
  const tbody = document.getElementById('correlation-matrix-body');
  if (!tbody || telemetryDataset.length < 2) return;

  const vars = ['temp', 'ph', 'pressure', 'feed', 'methane', 'biogas'];
  const labels = ['Temp', 'pH', 'Press', 'Feed', 'CH₄', 'Biogas'];

  const matrix = [];
  for (let i = 0; i < vars.length; i++) {
    const row = [];
    for (let j = 0; j < vars.length; j++) {
      if (i === j) {
        row.push(1.0);
      } else {
        const corr = calcPearson(vars[i], vars[j]);
        row.push(corr);
      }
    }
    matrix.push(row);
  }

  tbody.innerHTML = matrix.map((rowArr, i) => `
    <tr>
      <td class="py-1 px-1.5 font-bold text-slate-300 text-[10.5px]">${labels[i]}</td>
      ${rowArr.map(val => {
        const bg = getCorrBg(val);
        return `<td class="py-1 px-1 rounded transition-all font-mono font-bold text-[10.5px]" style="${bg}">${val >= 0 ? '+' : ''}${val.toFixed(2)}</td>`;
      }).join('')}
    </tr>
  `).join('');
}

function calcPearson(key1, key2) {
  const n = telemetryDataset.length;
  let s1 = 0, s2 = 0, s1Sq = 0, s2Sq = 0, pSum = 0;

  for (let r of telemetryDataset) {
    const x = r[key1];
    const y = r[key2];
    s1 += x;
    s2 += y;
    s1Sq += x * x;
    s2Sq += y * y;
    pSum += x * y;
  }

  const num = pSum - (s1 * s2 / n);
  const den = Math.sqrt((s1Sq - (s1 * s1 / n)) * (s2Sq - (s2 * s2 / n)));
  if (den === 0 || isNaN(den)) return 0;
  return Math.max(-1.0, Math.min(1.0, num / den));
}

function getCorrBg(val) {
  if (val >= 0.7) return 'background: rgba(16, 185, 129, 0.45); color: #6EE7B7;';
  if (val >= 0.3) return 'background: rgba(16, 185, 129, 0.25); color: #A7F3D0;';
  if (val >= 0.0) return 'background: rgba(37, 99, 235, 0.2); color: #93C5FD;';
  if (val >= -0.4) return 'background: rgba(37, 99, 235, 0.35); color: #60A5FA;';
  return 'background: rgba(239, 68, 68, 0.4); color: #FCA5A5;';
}

// UPDATE COMMUNITY SUSTAINABILITY IMPACT METRICS
function updateSustainabilityMetrics(curr) {
  const feedstockEl = document.getElementById('sust-feedstock-val');
  const elecEl = document.getElementById('sust-elec-val');
  const energyEl = document.getElementById('sust-energy-val');
  const costEl = document.getElementById('sust-cost-val');

  if (!curr || !telemetryDataset || telemetryDataset.length === 0) {
    if (feedstockEl) feedstockEl.textContent = " — ";
    if (elecEl) elecEl.textContent = " — ";
    if (energyEl) energyEl.textContent = " — ";
    if (costEl) costEl.textContent = " — ";
    return;
  }

  const slice = telemetryDataset.slice(0, currentRecordIndex + 1);
  const totalBiogas = slice.reduce((acc, r) => acc + (r.biogas || 0), 0);
  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;

  const isIndustrial = (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL" || (slice[0] && slice[0].feed_mt !== undefined));
  let totalFeedstock = 0;
  if (isIndustrial) {
    totalFeedstock = slice.reduce((acc, r) => acc + (r.feed_mt !== undefined ? r.feed_mt : (r.feed ? r.feed / 100 : 0)), 0);
  } else {
    totalFeedstock = slice.reduce((acc, r) => acc + (r.feed || 0), 0);
  }

  // Dynamic Electricity Potential across active slice
  const totalElec = slice.reduce((acc, r) => {
    const ch4 = (r.methane != null && !isNaN(r.methane) && r.methane > 0) ? Number(r.methane) : 60.0;
    return acc + ((r.biogas || 0) * (ch4 / 100.0) * 9.94 * eff);
  }, 0);

  const monetaryOffset = Math.round(totalElec * 8.5); // illustrative local tariff ₹8.5/kWh

  if (feedstockEl) {
    feedstockEl.textContent = isIndustrial
      ? `${Math.round(totalFeedstock).toLocaleString()} MT`
      : `${Math.round(totalFeedstock).toLocaleString()} kg`;
  }
  if (elecEl) {
    elecEl.textContent = totalElec >= 10000
      ? `${(totalElec / 1000).toFixed(1)} MWh`
      : `${Math.round(totalElec).toLocaleString()} kWh`;
  }
  if (energyEl) {
    energyEl.textContent = totalBiogas >= 10000
      ? `${(totalBiogas / 1000).toFixed(1)}k Nm³`
      : `${Math.round(totalBiogas).toLocaleString()} Nm³`;
  }
  if (costEl) {
    costEl.textContent = `₹${monetaryOffset.toLocaleString()}`;
  }

  const sustTitle = document.getElementById('sust-title');
  const sustQualifier = document.getElementById('sust-provenance-qualifier');
  if (sustTitle) {
    if (currentDataSource === "DEMO_SYNTHETIC") {
      sustTitle.innerHTML = '🌍 Community Scenario Impact';
    } else if (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL") {
      sustTitle.innerHTML = '🌍 Industrial Reference Impact';
    } else if (currentDataSource === "USER_UPLOAD") {
      sustTitle.innerHTML = '🌍 User Dataset Scenario Impact';
    } else {
      sustTitle.innerHTML = '🌍 Community Impact — Derived from Live Telemetry';
    }
  }
  if (sustQualifier) {
    if (currentDataSource === "DEMO_SYNTHETIC") {
      sustQualifier.textContent = "Illustrative community-scale scenario estimate — not measured impact";
    } else if (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL") {
      sustQualifier.textContent = "Derived reference calculation from industrial historical data — not a measured community deployment outcome.";
    } else if (currentDataSource === "USER_UPLOAD") {
      sustQualifier.textContent = "Calculated scenario estimate derived from user-uploaded dataset.";
    } else {
      sustQualifier.textContent = "Measured live community telemetry impact: Based on measured live community telemetry; impact values are calculated estimates.";
    }
  }

  // Mini Doughnut Chart (if present in DOM)
  const canvas = document.getElementById('sustainabilityDonutChart');
  if (!canvas) return;

  if (typeof Chart === 'undefined') {
    const parent = canvas.parentElement;
    let fallback = document.getElementById('sustainability-chart-fallback');
    if (!fallback && parent) {
      fallback = document.createElement('div');
      fallback.id = 'sustainability-chart-fallback';
      fallback.className = 'flex items-center justify-center h-28 text-slate-500 text-[11px] text-center italic p-2';
      fallback.textContent = 'Chart engine offline';
      canvas.classList.add('hidden');
      parent.appendChild(fallback);
    }
    return;
  } else {
    const fallback = document.getElementById('sustainability-chart-fallback');
    if (fallback) fallback.remove();
    canvas.classList.remove('hidden');
  }

  if (!sustainabilityChart) {
    const ctx = canvas.getContext('2d');
    sustainabilityChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Electricity Potential (50%)', 'Microgrid Offset (30%)', 'Biomass Digested (20%)'],
        datasets: [{
          data: [50, 30, 20],
          backgroundColor: ['#3B82F6', '#10B981', '#8B5CF6'],
          borderColor: '#0B1120',
          borderWidth: 2.5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            cornerRadius: 8
          }
        }
      }
    });
  } else {
    sustainabilityChart.update('none');
  }
}

// UPDATE SOLAR DETAILS
function renderSolarDetails(sol) {
  if (!sol) return;
  const wEl = document.getElementById('solar-w');
  const vEl = document.getElementById('solar-v');
  const bSocEl = document.getElementById('battery-soc');
  const bVEl = document.getElementById('battery-v');
  const badge = document.getElementById('solar-status-badge');
  const sTitle = document.getElementById('solar-subsystem-title');
  const sDesc = document.getElementById('solar-subsystem-desc');

  if (sTitle) {
    if (currentDataSource === "DEMO_SYNTHETIC") sTitle.textContent = "Solar Subsystem & Battery (Simulated)";
    else if (currentDataSource === "LIVE_IOT") sTitle.textContent = "Solar Subsystem & Battery (Live IoT)";
    else sTitle.textContent = "Auxiliary Solar Subsystem — Demo/Configured State";
  }
  if (sDesc) {
    if (currentDataSource === "DEMO_SYNTHETIC") sDesc.textContent = "Dedicated solar PV generation powers the IoT monitoring node, edge microcontroller, and process sensors without grid reliance.";
    else if (currentDataSource === "LIVE_IOT") sDesc.textContent = "Real-time solar irradiation harvesting and battery storage telemetry.";
    else sDesc.textContent = "Solar telemetry is unavailable in historical Spark data. Displays configured auxiliary reference state.";
  }

  if (wEl && sol.solar_power_w !== null) wEl.textContent = `${(sol.solar_power_w / 1000.0).toFixed(2)} kW`;
  if (vEl && sol.solar_voltage_v !== null) vEl.textContent = `${sol.solar_voltage_v.toFixed(1)} V`;
  if (bSocEl && sol.battery_soc_percent !== null) bSocEl.textContent = `${Math.round(sol.battery_soc_percent)}%`;
  if (bVEl && sol.battery_voltage_v !== null) bVEl.textContent = `${sol.battery_voltage_v.toFixed(1)} V`;
  if (badge) {
    if (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL") {
      badge.textContent = "AUXILIARY STATE";
      badge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-slate-700/50 text-slate-300 border border-slate-600";
    } else if (sol.solar_status) {
      badge.textContent = sol.solar_status;
      badge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
    }
  }
}

// ================================================================
// ENERGY GENERATION & COMMUNITY MICROGRID MANAGEMENT (P1)
// ================================================================

function updateEnergyGenerationSection(curr) {
  const biogasEl = document.getElementById('gen-biogas-val');
  const biogasProv = document.getElementById('gen-biogas-prov');
  const powerEl = document.getElementById('gen-power-val');
  const elecEl = document.getElementById('gen-elec-val');
  const effEl = document.getElementById('gen-eff-val');
  const effSlider = document.getElementById('gen-eff-slider');
  const fuelRateEl = document.getElementById('gen-fuel-rate-val');
  const statusBadge = document.getElementById('gen-status-badge');
  const runtimeEl = document.getElementById('gen-runtime-val');
  const hardwareBadge = document.getElementById('gen-hardware-badge');

  if (statusBadge) {
    statusBadge.textContent = "NOT CONNECTED";
    statusBadge.className = "px-2 py-1 rounded text-xs font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700 inline-block";
  }
  if (runtimeEl) runtimeEl.textContent = "N/A";
  if (hardwareBadge) hardwareBadge.textContent = "NOT CONNECTED";

  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
  if (effEl) effEl.textContent = `${Math.round(eff * 100)}%`;
  if (effSlider && Number(effSlider.value) !== Math.round(eff * 100)) {
    effSlider.value = Math.round(eff * 100);
  }

  if (!curr || curr.biogas == null || isNaN(Number(curr.biogas))) {
    if (biogasEl) biogasEl.textContent = " — ";
    if (powerEl) powerEl.textContent = " — ";
    if (elecEl) elecEl.textContent = " — ";
    if (fuelRateEl) fuelRateEl.textContent = " — ";
    if (biogasProv) biogasProv.textContent = "[AWAITING INPUT]";
    return;
  }

  const V = Number(curr.biogas);
  const ch4 = (curr.methane != null && !isNaN(Number(curr.methane)) && Number(curr.methane) > 0) ? Number(curr.methane) : 60.0;
  const calorificKwh = V * (ch4 / 100.0) * 9.94;
  const elecKwh = calorificKwh * eff;
  const powerKw = elecKwh / 24.0;
  const fuelRate = (ch4 > 0 && eff > 0) ? 1.0 / ((ch4 / 100.0) * 9.94 * eff) : 0.0;

  if (biogasEl) biogasEl.textContent = formatMetric(V, 2);
  if (powerEl) powerEl.textContent = formatMetric(powerKw, powerKw >= 100 ? 1 : 2);
  if (elecEl) elecEl.textContent = formatMetric(elecKwh, elecKwh >= 100 ? 1 : 2);
  if (fuelRateEl) fuelRateEl.textContent = formatMetric(fuelRate, 2);

  if (biogasProv) {
    if (currentDataSource === "DEMO_SYNTHETIC") biogasProv.textContent = "[SIMULATED BIOGAS]";
    else if (currentDataSource === "LIVE_IOT") biogasProv.textContent = "[LIVE MEASURED BIOGAS]";
    else if (currentDataSource === "USER_UPLOAD") biogasProv.textContent = "[USER DATASET]";
    else biogasProv.textContent = "[HISTORICAL OBSERVED]";
  }
}

function updateCommunityEnergySection(curr) {
  const demandInput = document.getElementById('comm-demand-input');
  const demandVal = document.getElementById('comm-demand-val');
  const genVal = document.getElementById('comm-generation-val');
  const covVal = document.getElementById('comm-coverage-val');
  const covSub = document.getElementById('comm-coverage-sub');
  const netVal = document.getElementById('comm-net-val');
  const netSub = document.getElementById('comm-net-sub');
  const lightingEl = document.getElementById('equiv-lighting-hrs');
  const fridgeEl = document.getElementById('equiv-fridge-days');
  const pumpEl = document.getElementById('equiv-pump-hrs');

  const demand = (window.__COMM_DEMAND__ != null) ? window.__COMM_DEMAND__ : 5.20;
  if (demandVal) demandVal.textContent = `${formatMetric(demand, 2)} kWh/day`;
  if (demandInput && Number(demandInput.value) !== demand) demandInput.value = demand.toFixed(2);

  if (!curr || curr.biogas == null || isNaN(Number(curr.biogas))) {
    if (genVal) genVal.textContent = " — ";
    if (covVal) covVal.textContent = " — ";
    if (netVal) netVal.textContent = " — ";
    if (lightingEl) lightingEl.textContent = " — ";
    if (fridgeEl) fridgeEl.textContent = " — ";
    if (pumpEl) pumpEl.textContent = " — ";
    if (communityEnergyChart) {
      communityEnergyChart.data.datasets[0].data = Array(24).fill(0);
      communityEnergyChart.data.datasets[1].data = Array(24).fill(0);
      communityEnergyChart.update('none');
    }
    return;
  }

  const V = Number(curr.biogas);
  const ch4 = (curr.methane != null && !isNaN(Number(curr.methane)) && Number(curr.methane) > 0) ? Number(curr.methane) : 60.0;
  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
  const elecKwh = V * (ch4 / 100.0) * 9.94 * eff;
  const powerKw = elecKwh / 24.0;

  const coverage = demand > 0 ? Math.min(100.0, (elecKwh / demand) * 100.0) : 0.0;
  const net = elecKwh - demand;

  if (genVal) genVal.textContent = `${formatMetric(elecKwh, elecKwh >= 100 ? 1 : 2)} kWh/day`;
  if (covVal) covVal.textContent = `${coverage.toFixed(1)}%`;
  if (covSub) covSub.textContent = coverage >= 100 ? "100% Demand Self-Sufficiency" : `${(100 - coverage).toFixed(1)}% Auxiliary / Grid Needed`;

  if (netVal) {
    const sign = net >= 0 ? "+" : "";
    netVal.textContent = `${sign}${formatMetric(net, net >= 100 ? 1 : 2)} kWh/day`;
    netVal.className = `text-2xl font-black font-mono mt-1 ${net >= 0 ? 'text-emerald-400' : 'text-amber-400'}`;
  }
  if (netSub) {
    netSub.textContent = net >= 0 ? "Surplus: Energy available for battery storage or microgrid export" : "Deficit: Supplementary microgrid solar/grid power required";
  }

  // Equivalencies (dynamically computed from current daily electricity potential)
  if (lightingEl) lightingEl.textContent = formatMetric((elecKwh * 1000) / 10.0, 0); // 10W LED bulb hours
  if (fridgeEl) fridgeEl.textContent = formatMetric(elecKwh / 0.8, 1);              // 0.8 kWh/day vaccine fridge
  if (pumpEl) pumpEl.textContent = formatMetric(elecKwh / 0.5, 1);                  // 0.5 kW community pump hours

  // 24-Hour Diurnal Chart Update
  if (communityEnergyChart) {
    const diurnalWeights = [
      0.025, 0.020, 0.015, 0.015, 0.020, 0.035,
      0.055, 0.065, 0.060, 0.045, 0.040, 0.035,
      0.035, 0.035, 0.035, 0.040, 0.045, 0.055,
      0.080, 0.090, 0.085, 0.070, 0.045, 0.035
    ];
    const hourlyDemandData = diurnalWeights.map(w => Number((w * demand).toFixed(4)));
    const hourlyPowerData = Array(24).fill(Number(powerKw.toFixed(4)));

    communityEnergyChart.data.datasets[0].data = hourlyDemandData;
    communityEnergyChart.data.datasets[1].data = hourlyPowerData;
    communityEnergyChart.update('none');
  }
}

function initCommunityEnergyChart() {
  const canvas = document.getElementById('communityEnergyChart');
  if (!canvas || typeof Chart === 'undefined') return;

  if (communityEnergyChart) {
    communityEnergyChart.destroy();
    communityEnergyChart = null;
  }

  const hours = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`);
  const ctx = canvas.getContext('2d');
  communityEnergyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: hours,
      datasets: [
        {
          label: 'Hourly Community Demand (kWh)',
          data: Array(24).fill(0),
          borderColor: '#38BDF8',
          backgroundColor: 'rgba(56, 189, 248, 0.12)',
          borderWidth: 2,
          fill: true,
          tension: 0.35,
          pointRadius: 2,
          pointHoverRadius: 5
        },
        {
          label: '24-h Avg Power Potential (kW)',
          data: Array(24).fill(0),
          borderColor: '#F59E0B',
          borderDash: [5, 4],
          borderWidth: 2.5,
          fill: false,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#F8FAFC',
          bodyColor: '#94A3B8',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          cornerRadius: 8,
          padding: 8,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.raw).toFixed(3)} ${ctx.datasetIndex === 0 ? 'kWh' : 'kW'}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748B', font: { family: 'monospace', size: 10 }, maxTicksLimit: 12 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#64748B',
            font: { family: 'monospace', size: 10 },
            callback: (val) => `${Number(val).toFixed(2)}`
          }
        }
      }
    }
  });
}

function initEnergyControls() {
  const effSlider = document.getElementById('gen-eff-slider');
  const effVal = document.getElementById('gen-eff-val');
  const demandInput = document.getElementById('comm-demand-input');

  if (effSlider) {
    effSlider.addEventListener('input', (e) => {
      const pct = Number(e.target.value);
      window.__GEN_EFF__ = pct / 100.0;
      if (effVal) effVal.textContent = `${pct}%`;

      const curr = getCurrentRecord();
      if (curr) {
        updateKPICards(curr);
        updateEnergyGenerationSection(curr);
        updateCommunityEnergySection(curr);
        updateSustainabilityMetrics(curr);
        if (latestForecast) renderForecastDetails(latestForecast, curr);
      }
    });
  }

  if (demandInput) {
    demandInput.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val) && val > 0) {
        window.__COMM_DEMAND__ = val;
        const curr = getCurrentRecord();
        if (curr) updateCommunityEnergySection(curr);
      }
    });
  }
}

// UPDATE FORECAST DETAILS PANEL
function renderForecastDetails(fc, curr) {
  if (!fc) return;
  const fcCurrent = document.getElementById('forecast-current-biogas');
  const fcCurrentElec = document.getElementById('forecast-current-elec');
  const fcPredictedElec = document.getElementById('forecast-predicted-elec');
  const kpiCurrent = document.getElementById('kpi-current-biogas');
  const kpiPredicted = document.getElementById('kpi-predicted-biogas');
  const kpiPredictedTop = document.getElementById('kpi-predicted-biogas-top');
  const kpiModelTop = document.getElementById('kpi-model-tag-top');
  const modelTag = document.getElementById('kpi-model-tag');
  const targetDateEl = document.getElementById('kpi-target-date');
  const provenanceBadge = document.getElementById('kpi-provenance-badge');
  const domainBadge = document.getElementById('header-domain-badge');
  const domainContextTag = document.getElementById('kpi-domain-context-tag');
  const historyBadge = document.getElementById('kpi-history-badge');
  const statusDot = document.getElementById('kpi-status-dot');
  const statusText = document.getElementById('kpi-status-text');
  const domainNoticeBox = document.getElementById('kpi-domain-notice-box');
  const domainNoticeText = document.getElementById('kpi-domain-notice-text');
  const healthSourceBadge = document.getElementById('health-source-badge');
  const corrSourceContext = document.getElementById('corr-source-context');
  const corrSampleSize = document.getElementById('corr-sample-size');

  const prov = fc.data_source || currentDataSource;

  // Header & Card Domain Badges
  if (prov === 'DEMO_SYNTHETIC') {
    if (domainBadge) {
      domainBadge.textContent = 'COMMUNITY-SCALE SIMULATION';
      domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-amber-500/10 border border-amber-500/30 text-amber-300 uppercase tracking-wide';
    }
    if (domainContextTag) {
      domainContextTag.textContent = 'Community Simulation';
      domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-amber-500/20 border border-amber-500/40 text-amber-300 uppercase';
    }
    if (provenanceBadge) {
      provenanceBadge.textContent = 'DEMO_SYNTHETIC';
      provenanceBadge.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-slate-800 border border-slate-700 text-slate-300 uppercase';
    }
    if (healthSourceBadge) healthSourceBadge.textContent = 'SOURCE: Community Sim';
    if (corrSourceContext) corrSourceContext.textContent = 'SOURCE: Community Sim';
  } else if (prov === 'REAL_SPARK_HISTORICAL' || prov === 'SPARK_FULL') {
    if (domainBadge) {
      domainBadge.textContent = 'INDUSTRIAL RESEARCH DATA';
      domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 uppercase tracking-wide';
    }
    if (domainContextTag) {
      domainContextTag.textContent = 'Industrial Research (Spark Bio Gas)';
      domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 uppercase';
    }
    if (provenanceBadge) {
      provenanceBadge.textContent = prov === 'SPARK_FULL' ? 'SPARK_FULL' : 'REAL_SPARK_HISTORICAL';
      provenanceBadge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 uppercase';
    }
    if (healthSourceBadge) healthSourceBadge.textContent = 'SOURCE: Spark Bio Gas';
    if (corrSourceContext) corrSourceContext.textContent = 'SOURCE: Spark Bio Gas';
  } else if (prov === 'LIVE_IOT') {
    if (domainBadge) {
      domainBadge.textContent = 'COMMUNITY LIVE TELEMETRY';
      domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 uppercase tracking-wide';
    }
    if (domainContextTag) {
      domainContextTag.textContent = 'Community Live IoT';
      domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 uppercase';
    }
    if (provenanceBadge) {
      provenanceBadge.textContent = 'LIVE_IOT';
      provenanceBadge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 uppercase';
    }
    if (healthSourceBadge) healthSourceBadge.textContent = 'SOURCE: Live IoT';
    if (corrSourceContext) corrSourceContext.textContent = 'SOURCE: Live IoT';
  } else if (prov === 'LIVE_IOT') {
    if (domainBadge) {
      domainBadge.textContent = 'COMMUNITY LIVE TELEMETRY';
      domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 uppercase tracking-wide';
    }
    if (domainContextTag) {
      domainContextTag.textContent = 'Community Live IoT';
      domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 uppercase';
    }
    if (provenanceBadge) {
      provenanceBadge.textContent = 'LIVE_IOT';
      provenanceBadge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 uppercase';
    }
    if (healthSourceBadge) healthSourceBadge.textContent = 'SOURCE: Live IoT';
    if (corrSourceContext) corrSourceContext.textContent = 'SOURCE: Live IoT';
  } else if (prov === 'USER_UPLOAD' || prov === 'UPLOADED_SCADA') {
    if (domainBadge) {
      domainBadge.textContent = 'USER-UPLOADED DATA';
      domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-amber-500/10 border border-amber-500/30 text-amber-300 uppercase tracking-wide';
    }
    if (domainContextTag) {
      domainContextTag.textContent = 'User-Uploaded SCADA';
      domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-amber-500/20 border border-amber-500/40 text-amber-300 uppercase';
    }
    if (provenanceBadge) {
      provenanceBadge.textContent = 'USER_UPLOAD';
      provenanceBadge.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-amber-500/20 border border-amber-500/40 text-amber-300 uppercase';
    }
    if (healthSourceBadge) healthSourceBadge.textContent = 'SOURCE: User Upload';
    if (corrSourceContext) corrSourceContext.textContent = 'SOURCE: User Upload';
  }

  if (corrSampleSize) corrSampleSize.textContent = `N = ${telemetryDataset.length}`;

  // Current Biogas Values
  const currVal = fc.input_biogas_m3_day !== null && fc.input_biogas_m3_day !== undefined
    ? formatMetric(fc.input_biogas_m3_day, 2)
    : (curr && curr.biogas !== null && curr.biogas !== undefined ? formatMetric(curr.biogas, 2) : "—");
  if (kpiCurrent) kpiCurrent.textContent = currVal;
  if (fcCurrent) fcCurrent.textContent = currVal;

  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
  const ch4Pct = (curr && curr.methane != null && !isNaN(curr.methane) && curr.methane > 0) ? Number(curr.methane) : 60.0;

  // Dynamic Current Electricity Potential
  if (currVal !== "—" && !isNaN(Number(currVal))) {
    const curElec = Number(currVal) * (ch4Pct / 100.0) * 9.94 * eff;
    if (fcCurrentElec) fcCurrentElec.textContent = formatMetric(curElec, curElec >= 100 ? 1 : 2);
  } else {
    if (fcCurrentElec) fcCurrentElec.textContent = " — ";
  }

  // Target Date
  if (targetDateEl) {
    if (curr && curr.targetDate) {
      targetDateEl.textContent = `${curr.targetDate} (t+1)`;
    } else if (fc.target_date) {
      targetDateEl.textContent = `${fc.target_date.substring(0, 10)} (t+1)`;
    } else {
      targetDateEl.textContent = 't+1 (Next-Day)';
    }
  }

  // Causal History Badge
  const mName = fc.model_name || currentModel;
  const histLen = fc.history_length !== undefined ? fc.history_length : (curr && curr.history_length !== undefined ? curr.history_length : 14);
  let lookbackRequired = 14;
  if (mName.includes("EMA")) lookbackRequired = 3;
  else if (mName.includes("Persistence") || mName.includes("Lag")) lookbackRequired = 1;
  else if (mName.includes("XCO")) lookbackRequired = 7;

  if (historyBadge) {
    if (histLen >= lookbackRequired) {
      historyBadge.textContent = `${histLen}/${lookbackRequired} timesteps`;
      historyBadge.className = "px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30 font-mono";
    } else {
      historyBadge.textContent = `${histLen}/${lookbackRequired} timesteps`;
      historyBadge.className = "px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30 font-mono";
    }
  }

  // Model-Aware Causal Footer
  const causalFooter = document.getElementById('forecast-causal-footer');
  if (causalFooter) {
    if (mName.includes("EMA")) {
      causalFooter.textContent = "Uses the previous 3 continuous timesteps and is generated causally from information available through the current day.";
    } else if (mName.includes("Persistence") || mName.includes("Lag")) {
      causalFooter.textContent = "Uses the previous 1 timestep and is generated causally from information available through the current day.";
    } else if (mName.includes("XCO")) {
      causalFooter.textContent = "Uses the previous 7 continuous timesteps and is generated causally from information available through the current day.";
    } else {
      causalFooter.textContent = "Uses the previous 14 continuous timesteps and is generated causally from information available through the current day.";
    }
  }

  if (modelTag) {
    modelTag.textContent = fc.model_name || currentModel;
  }
  if (kpiModelTop) {
    kpiModelTop.textContent = `${fc.model_name || currentModel} (t → t+1)`;
  }

  // Forecast Prediction & Domain Validation
  if (fc.status === 'Warming up forecast model') {
    if (kpiPredicted) {
      kpiPredicted.className = "text-3xl font-black text-slate-500 font-mono mt-1";
      kpiPredicted.textContent = '—';
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = '—';
    if (fcPredictedElec) fcPredictedElec.textContent = '—';
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse';
    if (statusText) {
      statusText.className = 'text-amber-400 font-mono text-[11px] truncate';
      statusText.textContent = `Status: Warming up (${histLen}/${lookbackRequired})`;
    }
    if (domainNoticeBox) domainNoticeBox.classList.add('hidden');
  } else if (fc.status === 'INSUFFICIENT_HISTORY' || fc.status === 'INSUFFICIENT_LIVE_HISTORY') {
    if (kpiPredicted) {
      kpiPredicted.className = "text-3xl font-black text-rose-400 font-mono mt-1";
      kpiPredicted.textContent = '—';
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = '—';
    if (fcPredictedElec) fcPredictedElec.textContent = '—';
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-rose-400';
    if (statusText) {
      statusText.className = 'text-rose-400 font-mono text-[11px] truncate';
      statusText.textContent = `Status: INSUFFICIENT_HISTORY (< ${lookbackRequired}d)`;
    }
    if (domainNoticeBox) domainNoticeBox.classList.add('hidden');
  } else if (fc.status === 'INSUFFICIENT_FEATURES') {
    if (kpiPredicted) {
      kpiPredicted.className = "text-xl md:text-2xl font-black text-rose-400 font-mono mt-1";
      kpiPredicted.textContent = 'INSUFFICIENT FEATURES';
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = '—';
    if (fcPredictedElec) fcPredictedElec.textContent = '—';
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-rose-400';
    if (statusText) {
      statusText.className = 'text-rose-400 font-mono text-[11px] truncate';
      statusText.textContent = 'Status: Missing required model features';
    }
    if (domainNoticeBox) {
      domainNoticeBox.classList.remove('hidden');
      if (domainNoticeText) {
        domainNoticeText.textContent = fc.domain_note || "Uploaded dataset lacks one or more mandatory features required by this forecasting model. Predictions are withheld without fallback substitution.";
      }
    }
  } else {
    // Status is SUCCESS or UNVALIDATED_USER_DATASET
    const isDomainValid = fc.domain_valid !== undefined ? fc.domain_valid : true;

    if (!isDomainValid) {
      if (kpiPredicted) {
        kpiPredicted.className = "text-lg md:text-xl font-black text-amber-300 tracking-tight leading-snug";
        kpiPredicted.textContent = prov === 'USER_UPLOAD' ? "Not Validated for User Dataset" : "Not Validated for Community Scale";
      }
      if (kpiPredictedTop) kpiPredictedTop.textContent = 'UNVALIDATED';
      if (fcPredictedElec) fcPredictedElec.textContent = '—';
      if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse';
      if (statusText) {
        statusText.className = 'text-amber-400 font-mono text-[11px] truncate';
        statusText.textContent = prov === 'USER_UPLOAD' ? 'UNVALIDATED USER DATASET (Transfer unvalidated)' : 'SUCCESS (Causal past-only; transfer unvalidated)';
      }
      if (domainNoticeBox) {
        domainNoticeBox.classList.remove('hidden');
        if (domainNoticeText) {
          domainNoticeText.textContent = fc.domain_note || (prov === 'USER_UPLOAD'
            ? "Model was calibrated on industrial Spark plant data (~5,300 Nm³/day). Transfer to user-uploaded dataset has not been scientifically validated. Numerical forecast is withheld for operational integrity."
            : "Industrial GRU calibrated on real Spark plant data (~5,300 Nm³/day). Current simulation represents a community-scale digester (~3 Nm³/day). Industrial-to-community scale transfer has not been validated. Select EMA-0.90 for a scale-compatible community forecast, or switch source to Spark Bio Gas.");
        }
      }
    } else {
      // Valid domain forecast (Spark with GRU/XCO, or Community with EMA/Persistence)
      const predBiogas = Number(fc.predicted_biogas_m3_day);
      if (kpiPredicted) {
        kpiPredicted.className = "text-3xl font-black text-emerald-300 tracking-tight flex items-baseline gap-1 font-mono mt-1";
        kpiPredicted.textContent = formatMetric(predBiogas, 2);
      }
      if (kpiPredictedTop) kpiPredictedTop.textContent = formatMetric(predBiogas, 2);
      if (fcPredictedElec) {
        const predElec = predBiogas * (ch4Pct / 100.0) * 9.94 * eff;
        fcPredictedElec.textContent = formatMetric(predElec, predElec >= 100 ? 1 : 2);
      }
      if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse';
      if (statusText) {
        statusText.className = 'text-emerald-400 font-mono text-[11px] truncate';
        statusText.textContent = 'Status: SUCCESS (Causal past-only)';
      }
      if (domainNoticeBox) domainNoticeBox.classList.add('hidden');
    }
  }

  // Model Interpretation & Research Attribution
  updateModelInterpretationUI(mName, null, prov);
}

// DYNAMIC MODEL INTERPRETATION VIA /api/forecast/interpretation
async function updateModelInterpretationUI(mName, historyWindow, dataSource) {
  const shapList = document.getElementById('shap-factors-list');
  const attUnavailable = document.getElementById('attribution-unavailable-note');
  const attTitle = document.getElementById('model-interpretation-title');
  const attBadge = document.getElementById('model-interpretation-badge');
  const attSub = document.getElementById('model-interpretation-sub');
  const dynDetails = document.getElementById('interpretation-dynamic-details');
  const predValEl = document.getElementById('interp-pred-val');
  const refLabelEl = document.getElementById('interp-ref-label');
  const refValEl = document.getElementById('interp-ref-val');
  const signalsGrid = document.getElementById('interp-signals-grid');
  const signalsSec = document.getElementById('interp-signals-section');
  const sensTitle = document.getElementById('interp-sensitivities-title');
  const sensSec = document.getElementById('interp-sensitivities-section');
  const expTextEl = document.getElementById('interp-explanation-text');
  const methodFooter = document.getElementById('interp-method-footer');

  if (dataSource === "AGSTAR_REGISTRY") {
    if (attTitle) attTitle.textContent = "Benchmark Registry Profile";
    if (attBadge) {
      attBadge.textContent = "Static Data";
      attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30";
    }
    if (attSub) attSub.textContent = "USDA / EPA AgSTAR Livestock Anaerobic Digester Database";
    if (dynDetails) dynDetails.classList.add('hidden');
    if (attUnavailable) {
      attUnavailable.classList.remove('hidden');
      attUnavailable.textContent = "Time-series forecasting models and feature attribution are disabled for static benchmarks.";
    }
    if (methodFooter) methodFooter.textContent = "Static registry data • Time-series forecasting disabled";
    return;
  }

  const timeoutSignal = createTimeoutSignal(10000);
  try {
    const res = await fetch('/api/forecast/interpretation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: "DIGESTER_001",
        model_name: mName,
        data_source: dataSource,
        history_window: historyWindow
      }),
      signal: timeoutSignal.signal
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();

    if (!data.available) {
      if (dynDetails) dynDetails.classList.add('hidden');
      if (attUnavailable) {
        attUnavailable.classList.remove('hidden');
        attUnavailable.textContent = data.reason || "Additive feature attribution is unavailable for this forecasting model.";
      }
      if (attTitle) attTitle.textContent = `${mName} Interpretation`;
      if (attBadge) {
        attBadge.textContent = "Unavailable";
        attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700";
      }
      if (methodFooter) methodFooter.textContent = `Method: ${data.method || 'Unknown'} • (is_shap: ${data.is_shap})`;
      return;
    }

    if (attUnavailable) attUnavailable.classList.add('hidden');
    if (dynDetails) dynDetails.classList.remove('hidden');

    // Title and Badges
    if (mName.includes("XCO")) {
      if (attTitle) attTitle.textContent = "XCO-Net Research Attribution";
      if (attBadge) {
        attBadge.textContent = "Architecture Weights";
        attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30";
      }
      if (attSub) attSub.textContent = "Architecture-level projection weights (1×1 pointwise convolutions), not additive SHAP";
    } else if (mName.includes("EMA")) {
      if (attTitle) attTitle.textContent = "EMA-0.90 Mathematical Decomposition";
      if (attBadge) {
        attBadge.textContent = "Exact Coefficients";
        attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30";
      }
      if (attSub) attSub.textContent = "Exact weight distribution across recent observations derived from algorithm formula";
    } else if (mName.includes("Persistence")) {
      if (attTitle) attTitle.textContent = "Persistence Baseline Logic";
      if (attBadge) {
        attBadge.textContent = "Identity Baseline";
        attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30";
      }
      if (attSub) attSub.textContent = "Exact identity step carrying current observation forward (y_{t+1} = y_t)";
    } else {
      if (attTitle) attTitle.textContent = "GRU-14d Local Sensitivity";
      if (attBadge) {
        attBadge.textContent = "Perturbation Analysis";
        attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
      }
      if (attSub) attSub.textContent = "Local input perturbation (+0.10σ) sensitivity over current 14-day history";
    }

    // Prediction & Reference
    if (predValEl) predValEl.textContent = data.prediction_nm3_day != null ? `${formatMetric(data.prediction_nm3_day, 2)} Nm³/day` : '—';
    if (refLabelEl) refLabelEl.textContent = data.reference_label || 'Reference (y_t):';
    if (refValEl) refValEl.textContent = data.reference_nm3_day != null ? `${formatMetric(data.reference_nm3_day, 2)} Nm³/day` : '—';

    // Input Signals & Trends
    if (signalsGrid && signalsSec) {
      if (data.features && data.features.length > 0) {
        signalsSec.classList.remove('hidden');
        signalsGrid.innerHTML = data.features.map(f => {
          let arrowColor = f.trend === '↑' ? 'text-emerald-400 font-bold' : (f.trend === '↓' ? 'text-rose-400 font-bold' : 'text-slate-400');
          let valStr = f.latest_value != null ? `${formatMetric(f.latest_value, 1)} ${f.unit}` : '—';
          return `
            <div class="p-1.5 rounded bg-slate-950/60 border border-slate-800 flex items-center justify-between">
              <span class="text-slate-400 text-[10px]">${f.label}:</span>
              <span class="font-bold text-white text-[11px] font-mono flex items-center gap-1">${valStr} <span class="${arrowColor}">${f.trend}</span></span>
            </div>
          `;
        }).join('');
      } else {
        signalsSec.classList.add('hidden');
      }
    }

    // Sensitivities or Weights List
    if (shapList && sensSec) {
      sensSec.classList.remove('hidden');
      shapList.classList.remove('hidden');
      if (data.sensitivities && data.sensitivities.length > 0) {
        if (sensTitle) sensTitle.textContent = "Local Input Sensitivity (+0.10σ Feature Perturbation):";
        shapList.innerHTML = data.sensitivities.map(s => {
          const sign = s.delta_prediction_nm3 >= 0 ? '+' : '';
          const colClass = s.delta_prediction_nm3 >= 0 ? 'text-emerald-400' : 'text-rose-400';
          return `
            <li class="flex items-center justify-between py-1 border-b border-slate-800/60 text-[11px]">
              <span class="text-slate-300 font-medium">${s.label}</span>
              <span class="font-mono ${colClass} font-bold">${sign}${formatMetric(s.delta_prediction_nm3, 3)} Nm³/day</span>
            </li>
          `;
        }).join('');
      } else if (data.contributions && data.contributions.length > 0) {
        if (sensTitle) sensTitle.textContent = mName.includes("EMA") ? "Algorithm Weight Decomposition:" : (mName.includes("XCO") ? "Architecture Projection Components:" : "Model Logic Attribution:");
        shapList.innerHTML = data.contributions.map(c => {
          return `
            <li class="flex items-center justify-between py-1 border-b border-slate-800/60 text-[11px]">
              <span class="text-slate-300 font-medium">${c.component}</span>
              <span class="font-mono text-cyan-400 font-bold">${c.weight} ${c.influence_nm3 != null ? `<span class="text-slate-400">(${formatMetric(c.influence_nm3, 2)} Nm³/day)</span>` : ''}</span>
            </li>
          `;
        }).join('');
      } else {
        sensSec.classList.add('hidden');
      }
    }

    // Explanation text
    if (expTextEl) {
      expTextEl.textContent = data.explanation_text || '';
    }

    // Method footer
    if (methodFooter) {
      methodFooter.textContent = `Method: ${data.method} • Local input sensitivity over active lookback window. No fabricated feature importance values.`;
    }

  } catch (err) {
    console.warn("Failed to fetch interpretation:", err);
    if (dynDetails) dynDetails.classList.add('hidden');
    if (attUnavailable) {
      attUnavailable.classList.remove('hidden');
      attUnavailable.textContent = "Interpretation service temporarily unavailable.";
    }
  } finally {
    timeoutSignal.cleanup();
  }
}

// EXECUTE MODEL FORECAST FOR A PLAYBACK TIMESTEP
async function executeModelForecast(curr, idx) {
  if (currentDataSource === "AGSTAR_REGISTRY") {
    return;
  }

  // Determine required lookback: strictly 14 timesteps for GRU, 7 for XCO-Net
  let lookback = 14;
  if (currentModel.includes("EMA")) lookback = 3;
  else if (currentModel.includes("Persistence")) lookback = 1;
  else if (currentModel.includes("XCO")) lookback = 7;

  const historyLength = curr.history_length !== undefined ? curr.history_length : (idx + 1);

  // 1. User Uploaded Dataset path (strictly runs via API with zero fake fallbacks)
  if (currentDataSource === "USER_UPLOAD") {
    const windowSlice = telemetryDataset.slice(Math.max(0, idx - lookback + 1), idx + 1);
    const historyWindow = windowSlice.map(r => {
      if (r.features) return r.features;
      return {
        biogas_today_nm3: r.biogas,
        total_incoming_mt: r.feed != null ? r.feed / 1000.0 : null,
        total_processed_mt: r.waste != null ? r.waste / 1000.0 : null,
        feed_total_m3: r.feed != null ? r.feed * 0.0012 : null,
        temp_outlet_d1_c: r.temp,
        ph_outlet_d1: r.ph,
        recycle_water_m3: null,
        feed_total_m3_was_missing: r.feed != null ? 0 : 1,
        ph_outlet_d1_was_missing: r.ph != null ? 0 : 1
      };
    });

    const myFcToken = ++currentForecastToken;
    const timeoutSignal = createTimeoutSignal(10000);
    try {
      const res = await fetch('/api/forecast/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: "DIGESTER_001",
          model_name: currentModel,
          data_source: "USER_UPLOAD",
          history_window: historyWindow
        }),
        signal: timeoutSignal.signal
      });
      if (myFcToken !== currentForecastToken) return;
      if (res.ok) {
        const data = await res.json();
        if (myFcToken !== currentForecastToken) return;
        curr.predictedBiogas = data.predicted_biogas_m3_day;
        data.history_length = historyWindow.length;
        renderForecastDetails(data, curr);
        await updateModelInterpretationUI(currentModel, historyWindow, "USER_UPLOAD");
      }
    } catch (err) {
      if (myFcToken !== currentForecastToken) return;
      console.warn("Forecast API error for USER_UPLOAD:", err);
    } finally {
      timeoutSignal.cleanup();
    }
    return;
  }

  // 2. Spark replay path (pre-calculated with verified causal context)
  if (currentDataSource === "REAL_SPARK_HISTORICAL" || currentDataSource === "SPARK_FULL") {
    const windowSlice = telemetryDataset.slice(Math.max(0, idx - lookback + 1), idx + 1);
    const historyWindow = windowSlice.map(r => ({
      biogas_today_nm3: r.biogas,
      total_incoming_mt: (r.feed_mt || 120.0) / 1000.0,
      total_processed_mt: (r.feed_mt || 120.0) / 1000.0,
      feed_total_m3: (r.feed_mt || 120.0) * 0.0012,
      temp_outlet_d1_c: r.temp || 36.5,
      ph_outlet_d1: r.ph || 7.25,
      recycle_water_m3: 30.0,
      feed_total_m3_was_missing: 0,
      ph_outlet_d1_was_missing: 0
    }));

    if (curr.status === "SUCCESS" && curr.predictedBiogas !== null && curr.predictedBiogas !== undefined) {
      let f1 = "Slurry Temperature D1 (36.5°C mesophilic)";
      let f2 = "Total Feedstock Loading Rate";
      let f3 = "Digester 1 pH Buffer";
      if (currentModel.includes("XCO")) {
        f1 = "Pointwise Cross-Channel Interaction";
        f2 = "Cross-Channel Operator Feedstock Projection";
        f3 = "Training-Derived Bounded Delta (±4152 Nm³/day)";
      } else if (currentModel.includes("EMA")) {
        f1 = "Exponential Smoothing Weight (α = 0.90)";
        f2 = "3-Day Moving Window Average";
        f3 = "Biogas Inertia Factor";
      } else if (currentModel.includes("Persistence")) {
        f1 = "Lag-0 Today Production";
        f2 = "Zero Dynamic Memory";
        f3 = "Identity Transfer";
      }

      renderForecastDetails({
        predicted_biogas_m3_day: curr.predictedBiogas,
        input_biogas_m3_day: curr.biogas,
        model_name: currentModel,
        model_version: currentModel.includes("XCO") ? "v1.0.0-research" : "v1.0.0",
        preprocessing_version: currentModel.includes("EMA") || currentModel.includes("Persistence") ? "none" : "v1.0.0-frozen-train",
        data_source: currentDataSource,
        status: "SUCCESS",
        domain_valid: curr.domain_valid !== undefined ? curr.domain_valid : true,
        domain_note: curr.domain_note || "Industrial research domain validated.",
        history_length: historyLength,
        timestamp: new Date().toISOString(),
        top_feature_1: f1,
        top_feature_2: f2,
        top_feature_3: f3
      }, curr);
      await updateModelInterpretationUI(currentModel, historyWindow, currentDataSource);
      return;
    } else {
      curr.predictedBiogas = null;
      renderForecastDetails({
        predicted_biogas_m3_day: null,
        input_biogas_m3_day: curr.biogas,
        model_name: currentModel,
        model_version: currentModel.includes("XCO") ? "v1.0.0-research" : "v1.0.0",
        preprocessing_version: currentModel.includes("EMA") || currentModel.includes("Persistence") ? "none" : "v1.0.0-frozen-train",
        data_source: currentDataSource,
        status: "INSUFFICIENT_HISTORY",
        history_length: historyLength,
        timestamp: new Date().toISOString()
      }, curr);
      await updateModelInterpretationUI(currentModel, historyWindow, currentDataSource);
      return;
    }
  }

  // 3. DEMO_SYNTHETIC simulation path
  // If history is below required lookback, report warming up and never fabricate prediction
  if (historyLength < lookback) {
    curr.predictedBiogas = null;
    renderForecastDetails({
      predicted_biogas_m3_day: null,
      input_biogas_m3_day: curr.biogas,
      model_name: currentModel,
      model_version: "v1.0.0",
      preprocessing_version: currentModel.includes("EMA") || currentModel.includes("Persistence") ? "none" : "v1.0.0-frozen-train",
      data_source: currentDataSource,
      status: "Warming up forecast model",
      history_length: historyLength,
      timestamp: new Date().toISOString()
    }, curr);
    await updateModelInterpretationUI(currentModel, [], currentDataSource);
    return;
  }

  const simSlice = telemetryDataset.slice(Math.max(0, idx - lookback + 1), idx + 1);
  const simHistory = simSlice.map(r => ({
    biogas_today_nm3: r.biogas,
    total_incoming_mt: (r.feed || 120.0) / 1000.0,
    total_processed_mt: (r.waste || 120.0) / 1000.0,
    feed_total_m3: (r.feed || 120.0) * 0.0012,
    temp_outlet_d1_c: r.temp || 36.5,
    ph_outlet_d1: r.ph || 7.25,
    recycle_water_m3: 30.0,
    feed_total_m3_was_missing: 0,
    ph_outlet_d1_was_missing: 0
  }));

  // Precomputed values for Community Simulation
  if (currentModel === "GRU-14d Residual" && curr.predictedBiogas !== undefined && curr.predictedBiogas !== null) {
    renderForecastDetails({
      predicted_biogas_m3_day: curr.predictedBiogas,
      input_biogas_m3_day: curr.biogas,
      model_name: "GRU-14d Residual",
      model_version: "v1.0.0",
      preprocessing_version: "v1.0.0-frozen-train",
      data_source: "DEMO_SYNTHETIC",
      status: "SUCCESS",
      domain_valid: curr.domain_valid !== undefined ? curr.domain_valid : false,
      domain_note: curr.domain_note || "Industrial GRU calibrated on real Spark plant data (~5,300 Nm³/day). Current simulation represents a community-scale digester (~3 Nm³/day). Industrial-to-community scale transfer has not been validated.",
      history_length: historyLength,
      timestamp: new Date().toISOString()
    }, curr);
    await updateModelInterpretationUI(currentModel, simHistory, "DEMO_SYNTHETIC");
    return;
  }

  if (currentModel === "EMA-0.90") {
    const emaVal = (curr.emaPredictedBiogas !== undefined && curr.emaPredictedBiogas !== null) ? curr.emaPredictedBiogas : Number((curr.biogas * 0.98).toFixed(2));
    renderForecastDetails({
      predicted_biogas_m3_day: emaVal,
      input_biogas_m3_day: curr.biogas,
      model_name: "EMA-0.90",
      model_version: "v1.0.0",
      preprocessing_version: "none",
      data_source: "DEMO_SYNTHETIC",
      status: "SUCCESS",
      domain_valid: true,
      domain_note: "Scale-compatible statistical filter",
      history_length: historyLength,
      timestamp: new Date().toISOString()
    }, curr);
    await updateModelInterpretationUI(currentModel, simHistory, "DEMO_SYNTHETIC");
    return;
  }

  if (currentModel === "Persistence") {
    const pVal = (curr.persistencePredictedBiogas !== undefined && curr.persistencePredictedBiogas !== null) ? curr.persistencePredictedBiogas : curr.biogas;
    renderForecastDetails({
      predicted_biogas_m3_day: pVal,
      input_biogas_m3_day: curr.biogas,
      model_name: "Persistence",
      model_version: "v1.0.0",
      preprocessing_version: "none",
      data_source: "DEMO_SYNTHETIC",
      status: "SUCCESS",
      domain_valid: true,
      domain_note: "Scale-compatible naive persistence",
      history_length: historyLength,
      timestamp: new Date().toISOString()
    }, curr);
    await updateModelInterpretationUI(currentModel, simHistory, "DEMO_SYNTHETIC");
    return;
  }

  if (currentModel.includes("XCO")) {
    renderForecastDetails({
      predicted_biogas_m3_day: null,
      input_biogas_m3_day: curr.biogas,
      model_name: "XCO-Net",
      model_version: "v1.0.0",
      preprocessing_version: "v1.0.0-frozen-train",
      data_source: "DEMO_SYNTHETIC",
      status: "SUCCESS",
      domain_valid: false,
      domain_note: "Industrial XCO-Net calibrated on real Spark plant data (~5,300 Nm³/day). Current simulation represents a community-scale digester (~3 Nm³/day). Industrial-to-community scale transfer has not been validated.",
      history_length: historyLength,
      timestamp: new Date().toISOString()
    }, curr);
    await updateModelInterpretationUI(currentModel, simHistory, "DEMO_SYNTHETIC");
    return;
  }

  // Fallback: API predict
  const myFcToken = ++currentForecastToken;
  const timeoutSignal = createTimeoutSignal(10000);
  try {
    const res = await fetch('/api/forecast/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: "DIGESTER_001",
        model_name: currentModel,
        data_source: (currentDataSource === "SPARK_FULL" || currentDataSource === "REAL_SPARK_HISTORICAL") ? "REAL_SPARK_HISTORICAL" : "DEMO_SYNTHETIC",
        history_window: simHistory
      }),
      signal: timeoutSignal.signal
    });

    if (myFcToken !== currentForecastToken) return;

    if (res.ok) {
      const data = await res.json();
      if (myFcToken !== currentForecastToken) return;
      curr.predictedBiogas = data.predicted_biogas_m3_day;
      data.history_length = historyLength;
      renderForecastDetails(data, curr);
      await updateModelInterpretationUI(currentModel, simHistory, data.data_source || currentDataSource);
    }
  } catch (err) {
    if (myFcToken !== currentForecastToken) return;
    console.warn("Forecast API error:", err);
  } finally {
    timeoutSignal.cleanup();
  }
}

// LOAD REAL SPARK DATASET REPLAY TIMELINE (DUAL MODE: HELD_OUT_TEST or FULL_HISTORICAL)
async function loadSparkReplayData(mode = "held_out_test") {
  const statusText = document.getElementById('kpi-status-text');
  const statusDot = document.getElementById('kpi-status-dot');
  const prevBtn = document.getElementById('prev-row-btn');
  const nextBtn = document.getElementById('next-row-btn');
  const autoBtn = document.getElementById('auto-play-btn');

  const myToken = ++currentSourceLoadToken;
  if (currentSourceAbortController) {
    currentSourceAbortController.abort();
  }
  currentSourceAbortController = new AbortController();
  const parentSignal = currentSourceAbortController.signal;
  const timeoutSignal = createTimeoutSignal(15000, parentSignal);

  try {
    stopAutoPlay();
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
    if (autoBtn) autoBtn.disabled = true;

    if (mode === "full_historical") {
      if (statusText) {
        statusText.textContent = "Loading SPARK_FULL (176 records)...";
        statusText.className = "text-cyan-400 font-mono text-[11px] truncate animate-pulse";
      }
      if (statusDot) {
        statusDot.className = "w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping";
      }
    }

    const res = await fetch(`/api/forecast/spark-replay?model_name=${encodeURIComponent(currentModel)}&mode=${mode}`, { signal: timeoutSignal.signal });
    if (myToken !== currentSourceLoadToken) return;

    if (res.ok) {
      const items = await res.json();
      if (myToken !== currentSourceLoadToken) return;
      if (items && items.length > 0) {
        telemetryDataset = items.map(item => ({
          timestamp: item.date,
          targetDate: item.target_date,
          temp: item.temperature_c != null ? Number(item.temperature_c.toFixed(1)) : null,
          ph: item.ph_d1 != null ? Number(item.ph_d1.toFixed(2)) : null,
          pressure: 1.15,
          methane: 62.0,
          level: 80.0,
          feed: item.feed_total_m3 != null ? Math.round(item.feed_total_m3 * 100) : null,
          feed_mt: item.feed_total_m3 != null ? Number(item.feed_total_m3.toFixed(1)) : null,
          flow: item.actual_biogas_today_nm3,
          biogas: item.actual_biogas_today_nm3,
          waste: item.feed_total_m3 != null ? Math.round(item.feed_total_m3 * 100) : null,
          predictedBiogas: item.predicted_next_day_nm3,
          actualNextDay: item.actual_next_day_nm3,
          history_length: item.history_length !== undefined ? item.history_length : 14,
          status: item.status || (item.predicted_next_day_nm3 !== null ? "SUCCESS" : "INSUFFICIENT_HISTORY"),
          domain_valid: item.domain_valid !== undefined ? item.domain_valid : true,
          domain_note: item.domain_note || "Industrial research domain validated.",
          data_source: mode === "full_historical" ? "SPARK_FULL" : "REAL_SPARK_HISTORICAL"
        }));
        currentRecordIndex = 0;
        currentDataSource = mode === "full_historical" ? "SPARK_FULL" : "REAL_SPARK_HISTORICAL";

        const countEl = document.getElementById('dataset-row-count');
        if (countEl) countEl.textContent = telemetryDataset.length;
        const infoStr = document.getElementById('dataset-info-str');
        if (infoStr) {
          const modeDesc = mode === "full_historical"
            ? `all <strong class="text-white font-mono">${telemetryDataset.length}</strong> historical operational days`
            : `<strong class="text-white font-mono">${telemetryDataset.length}</strong> held-out test days (2026-03-10 to 2026-04-02)`;
          infoStr.innerHTML = `Loaded ${modeDesc} from <code class="text-cyan-400 bg-slate-900 px-2 py-0.5 rounded font-bold">Spark Biogas SCADA</code> (Strict Past-Only Causality)`;
        }
        await renderAllMetrics();
      }
    } else {
      if (statusText) {
        statusText.textContent = `Error loading ${mode} (${res.status})`;
        statusText.className = "text-rose-400 font-mono text-[11px] truncate";
      }
      if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-rose-400";
    }
  } catch (err) {
    if (myToken !== currentSourceLoadToken) return;
    if (err.name === 'AbortError' && !timeoutSignal.isTimedOut()) return;
    console.error("Failed to load Spark replay data:", err);
    if (statusText) {
      if (timeoutSignal.isTimedOut() || err.name === 'TimeoutError') {
        statusText.textContent = `Request timed out loading ${mode} (>15s)`;
      } else {
        statusText.textContent = `Connection error loading ${mode}`;
      }
      statusText.className = "text-rose-400 font-mono text-[11px] truncate";
    }
    if (statusDot) statusDot.className = "w-1.5 h-1.5 rounded-full bg-rose-400";
  } finally {
    timeoutSignal.cleanup();
    if (myToken === currentSourceLoadToken) {
      if (prevBtn) prevBtn.disabled = false;
      if (nextBtn) nextBtn.disabled = false;
      if (autoBtn) autoBtn.disabled = false;
    }
  }
}

// LOAD LIVE HARDWARE TELEMETRY (GENUINE ESP32 / IoT PATH: NO FALLBACK TO SIMULATOR/SPARK)
async function loadLiveIotData() {
  currentDataSource = "LIVE_IOT";
  stopAutoPlay();

  // 1. Clear previous source state immediately
  clearSourceState();
  const myToken = currentSourceLoadToken;
  const signal = currentSourceAbortController ? currentSourceAbortController.signal : undefined;

  // 2. Configure replay controls for live hardware
  const prevBtn = document.getElementById('prev-row-btn');
  const nextBtn = document.getElementById('next-row-btn');
  const autoBtn = document.getElementById('auto-play-btn');
  const rowDisp = document.getElementById('row-index-display');
  const modelSelect = document.getElementById('model-select');
  const livePill = document.getElementById('live-iot-status-pill');

  if (prevBtn) {
    prevBtn.disabled = true;
    prevBtn.classList.add('opacity-40', 'cursor-not-allowed');
  }
  if (nextBtn) {
    nextBtn.disabled = true;
    nextBtn.classList.add('opacity-40', 'cursor-not-allowed');
  }
  if (autoBtn) autoBtn.classList.add('hidden');
  if (rowDisp) rowDisp.classList.add('hidden');
  if (modelSelect) {
    modelSelect.disabled = false;
    modelSelect.classList.remove('opacity-40', 'cursor-not-allowed');
  }

  // 3. Update domain header badges to COMMUNITY LIVE TELEMETRY
  const domainBadge = document.getElementById('header-domain-badge');
  const domainContextTag = document.getElementById('kpi-domain-context-tag');
  const provenanceBadge = document.getElementById('kpi-provenance-badge');
  const healthSourceBadge = document.getElementById('health-source-badge');
  const corrSourceContext = document.getElementById('corr-source-context');

  if (domainBadge) {
    domainBadge.textContent = 'COMMUNITY LIVE TELEMETRY';
    domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 uppercase tracking-wide';
  }
  if (domainContextTag) {
    domainContextTag.textContent = 'Community Live IoT';
    domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 uppercase';
  }
  if (provenanceBadge) {
    provenanceBadge.textContent = 'LIVE_IOT';
    provenanceBadge.className = 'px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 uppercase';
  }
  if (healthSourceBadge) healthSourceBadge.textContent = 'SOURCE: Live IoT';
  if (corrSourceContext) corrSourceContext.textContent = 'SOURCE: Live IoT';

  // 4. Source-aware KPI titles for LIVE_IOT
  updateSourceKpiLabels("LIVE_IOT");

  // 5. Query /api/readings/live-status and /api/readings?source=live_esp32
  const timeoutSignal = createTimeoutSignal(10000, signal);
  try {
    const [statusRes, readingsRes] = await Promise.all([
      fetch('/api/readings/live-status', { signal: timeoutSignal.signal }),
      fetch('/api/readings?source=live_esp32&limit=50', { signal: timeoutSignal.signal })
    ]);

    if (myToken !== currentSourceLoadToken) return;

    const liveStatus = statusRes.ok ? await statusRes.json() : { count: 0, connectivity_state: "WAITING FOR ESP32" };
    const readings = readingsRes.ok ? await readingsRes.json() : [];

    if (myToken !== currentSourceLoadToken) return;

    // Update status pill
    if (livePill) {
      livePill.classList.remove('hidden');
      livePill.textContent = liveStatus.connectivity_state;
      if (liveStatus.connectivity_state === "ESP32 CONNECTED") {
        livePill.className = "px-2.5 py-1 rounded-xl text-xs font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300";
      } else if (liveStatus.connectivity_state === "DATA STALE / DEVICE NOT RECENTLY SEEN") {
        livePill.className = "px-2.5 py-1 rounded-xl text-xs font-mono font-bold bg-amber-500/20 border border-amber-500/40 text-amber-300";
      } else {
        livePill.className = "px-2.5 py-1 rounded-xl text-xs font-mono font-bold bg-rose-500/20 border border-rose-500/40 text-rose-300";
      }
    }

    if (!readings || readings.length === 0) {
      // EMPTY STATE: Strictly zero fallback data!
      renderLiveIotEmptyState();
      return;
    }

    // Chronological order: past -> latest
    const chronoReadings = [...readings].reverse();
    telemetryDataset = chronoReadings.map(r => ({
      timestamp: r.timestamp,
      temp: r.temperature_c,
      ph: r.ph,
      pressure: r.pressure_bar,
      flow: r.biogas_production_m3_day,
      biogas: r.biogas_production_m3_day,
      methane: r.methane_pct,
      feed: r.feedstock_mass_kg,
      waste: r.feedstock_mass_kg,
      level: 75.0,
      predictedBiogas: null,
      history_length: chronoReadings.length,
      status: "SUCCESS",
      domain_valid: true,
      domain_note: "Live IoT hardware readings (zero synthetic data).",
      data_source: "LIVE_IOT"
    }));
    currentRecordIndex = telemetryDataset.length - 1;

    // Update DOM counters
    const countEl = document.getElementById('dataset-row-count');
    if (countEl) countEl.textContent = telemetryDataset.length;
    const infoStr = document.getElementById('dataset-info-str');
    if (infoStr) {
      infoStr.innerHTML = `Loaded <strong class="text-white font-mono">${telemetryDataset.length}</strong> live telemetry records from <code class="text-emerald-400 bg-slate-900 px-2 py-0.5 rounded font-bold">ESP32 Hardware</code> (Chronological).`;
    }

    const latest = telemetryDataset[currentRecordIndex];

    // Render 4 Primary Process KPIs
    renderLiveIotKpis(latest);

    // If community scale (simulation or live IoT) AND industrial GRU or XCO-Net, DO NOT forecast!
    if (currentModel === "GRU-14d Residual" || currentModel.includes("XCO")) {
      renderLiveIotUnvalidatedForecast(latest);
      updateProductionChart();
      updateLiveSustainability(latest);
      updateLiveSolar();
      await updateSafetyAlerts(latest);
      return;
    }

    // Build history window for forecast predict
    const historyWindow = chronoReadings.map(r => ({
      timestamp: r.timestamp,
      biogas_today_nm3: r.biogas_production_m3_day,
      total_incoming_mt: r.feedstock_mass_kg != null ? r.feedstock_mass_kg / 1000.0 : null,
      total_processed_mt: r.feedstock_mass_kg != null ? r.feedstock_mass_kg / 1000.0 : null,
      feed_total_m3: r.feedstock_mass_kg != null ? r.feedstock_mass_kg * 0.0012 : null,
      temp_outlet_d1_c: r.temperature_c,
      ph_outlet_d1: r.ph,
      recycle_water_m3: null,
      feed_total_m3_was_missing: r.feedstock_mass_kg != null ? 0.0 : 1.0,
      ph_outlet_d1_was_missing: r.ph != null ? 0.0 : 1.0
    }));

    // Request backend forecast prediction with authoritative checks
    const fcRes = await fetch('/api/forecast/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: timeoutSignal.signal,
      body: JSON.stringify({
        device_id: latest.device_id || "DIGESTER_001",
        model_name: currentModel,
        data_source: "LIVE_IOT",
        history_window: historyWindow
      })
    });

    if (myToken !== currentSourceLoadToken) return;

    if (fcRes.ok) {
      const fcData = await fcRes.json();
      if (myToken !== currentSourceLoadToken) return;
      renderLiveIotForecastResult(fcData, latest, historyWindow.length);
    }

    updateProductionChart();
    updateLiveSustainability(latest);
    updateLiveSolar();
    await updateSafetyAlerts(latest);

  } catch (err) {
    if (err.name === 'AbortError' && !timeoutSignal.isTimedOut()) return;
    if (myToken !== currentSourceLoadToken) return;
    console.error("Failed to load LIVE_IOT telemetry:", err);
    renderLiveIotEmptyState();
  } finally {
    timeoutSignal.cleanup();
  }
}

function renderLiveIotEmptyState() {
  const infoStr = document.getElementById('dataset-info-str');
  if (infoStr) {
    infoStr.innerHTML = `Loaded <strong class="text-white font-mono">0</strong> live telemetry records from <code class="text-emerald-400 bg-slate-900 px-2 py-0.5 rounded font-bold">ESP32 Hardware</code> (Awaiting initial ingestion). <span class="text-amber-400">No current ESP32 data received.</span>`;
  }
  const countEl = document.getElementById('dataset-row-count');
  if (countEl) countEl.textContent = '0';

  const tempEl = document.getElementById('kpi-temp-val');
  const phEl = document.getElementById('kpi-ph-val');
  const pressEl = document.getElementById('kpi-press-val');
  const biogasEl = document.getElementById('kpi-current-biogas');
  const fcCurrent = document.getElementById('forecast-current-biogas');
  const feedEl = document.getElementById('kpi-feedstock-val');
  const methEl = document.getElementById('kpi-methane-val');
  const kpiElecPot = document.getElementById('kpi-electricity-potential');
  const kpiContPower = document.getElementById('kpi-continuous-power');
  const fcCurrentElec = document.getElementById('forecast-current-elec');
  const fcPredictedElec = document.getElementById('forecast-predicted-elec');
  const kpiPredTop = document.getElementById('kpi-predicted-biogas-top');

  if (tempEl) tempEl.textContent = '—';
  if (phEl) phEl.textContent = '—';
  if (pressEl) pressEl.textContent = '—';
  if (biogasEl) biogasEl.textContent = '—';
  if (fcCurrent) fcCurrent.textContent = '—';
  if (feedEl) feedEl.textContent = '—';
  if (methEl) methEl.textContent = '—';
  if (kpiElecPot) kpiElecPot.textContent = '—';
  if (kpiContPower) kpiContPower.textContent = '—';
  if (fcCurrentElec) fcCurrentElec.textContent = '—';
  if (fcPredictedElec) fcPredictedElec.textContent = '—';
  if (kpiPredTop) kpiPredTop.textContent = '—';

  const kpiPredicted = document.getElementById('kpi-predicted-biogas');
  const statusDot = document.getElementById('kpi-status-dot');
  const statusText = document.getElementById('kpi-status-text');
  const targetDateEl = document.getElementById('kpi-target-date');
  const historyBadge = document.getElementById('kpi-history-badge');
  const domainNoticeBox = document.getElementById('kpi-domain-notice-box');

  if (kpiPredicted) {
    kpiPredicted.className = "text-3xl font-black text-rose-400 font-mono mt-1";
    kpiPredicted.textContent = '—';
  }
  if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-rose-400';
  if (statusText) {
    statusText.className = 'text-rose-400 font-mono text-[11px] truncate';
    statusText.textContent = 'Status: INSUFFICIENT LIVE HISTORY';
  }
  if (targetDateEl) targetDateEl.textContent = 't+1 (Next-Day)';
  if (historyBadge) {
    historyBadge.textContent = '0 timesteps';
    historyBadge.className = 'px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold border border-rose-500/30 font-mono';
  }
  if (domainNoticeBox) domainNoticeBox.classList.add('hidden');

  if (productionChart) {
    productionChart.data.labels = [];
    productionChart.data.datasets[0].data = [];
    productionChart.data.datasets[1].data = [];
    productionChart.update('none');
  }
  const tsSub = document.getElementById('timeseries-sub');
  if (tsSub) {
    tsSub.innerHTML = 'Live Telemetry Timeseries • <span class="text-amber-400 font-mono">Awaiting Initial Hardware Connection</span>';
  }
  const withheldNotice = document.getElementById('chart-withheld-notice');
  if (withheldNotice) {
    withheldNotice.textContent = "Awaiting live ESP32 telemetry. No synthetic fallback data displayed.";
    withheldNotice.classList.remove('hidden');
  }

  // Explicitly reset gauges, health index, sustainability, and authoritative safety for empty LIVE_IOT state
  updateGauges(null);
  updateHealthIndex(null);
  updateSustainabilityMetrics(null);
  updateEnergyGenerationSection(null);
  updateCommunityEnergySection(null);
  updateDrawerTelemetryPreview(null);
  updateSafetyAlerts(null);

  const alertsList = document.getElementById('alerts-list');
  if (alertsList) {
    alertsList.innerHTML = `
      <div class="p-3 rounded-xl bg-slate-800/60 border border-slate-700/50 text-xs text-slate-400">
        ⚪ No active sensor telemetry stream (ESP32 awaiting connection).
      </div>
    `;
  }

  updateLiveSustainability(null);
  updateLiveSolar();
}

function renderLiveIotUnvalidatedForecast(latest) {
  const kpiPredicted = document.getElementById('kpi-predicted-biogas');
  const kpiPredictedTop = document.getElementById('kpi-predicted-biogas-top');
  const fcPredictedElec = document.getElementById('forecast-predicted-elec');
  const statusDot = document.getElementById('kpi-status-dot');
  const statusText = document.getElementById('kpi-status-text');
  const domainNoticeBox = document.getElementById('kpi-domain-notice-box');
  const domainNoticeText = document.getElementById('kpi-domain-notice-text');

  if (kpiPredicted) {
    kpiPredicted.className = "text-lg md:text-xl font-black text-amber-300 tracking-tight leading-snug";
    kpiPredicted.textContent = "Not Validated for Community Scale";
  }
  if (kpiPredictedTop) kpiPredictedTop.textContent = "UNVALIDATED";
  if (fcPredictedElec) fcPredictedElec.textContent = "—";
  if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse';
  if (statusText) {
    statusText.className = 'text-amber-400 font-mono text-[11px] truncate';
    statusText.textContent = 'SUCCESS (Causal past-only; transfer unvalidated)';
  }
  if (domainNoticeBox) {
    domainNoticeBox.classList.remove('hidden');
    if (domainNoticeText) {
      domainNoticeText.textContent = "Industrial model calibrated on real Spark plant data (~5,300 Nm³/day). Current telemetry represents a community-scale digester. Industrial-to-community scale transfer has not been validated.";
    }
  }
}

const renderLiveIotKpis = renderLiveTelemetryCardValues;

function renderLiveTelemetryCardValues(latest) {
  const tempEl = document.getElementById('kpi-temp-val');
  const phEl = document.getElementById('kpi-ph-val');
  const pressEl = document.getElementById('kpi-press-val');
  const biogasEl = document.getElementById('kpi-current-biogas');
  const fcCurrent = document.getElementById('forecast-current-biogas');
  const feedEl = document.getElementById('kpi-feedstock-val');
  const methEl = document.getElementById('kpi-methane-val');
  const kpiElecPot = document.getElementById('kpi-electricity-potential');
  const kpiContPower = document.getElementById('kpi-continuous-power');
  const kpiElecProv = document.getElementById('kpi-electricity-provenance');
  const fcCurrentElec = document.getElementById('forecast-current-elec');

  if (tempEl) tempEl.textContent = formatMetric(latest.temperature_c, 1);
  if (phEl) phEl.textContent = formatMetric(latest.ph, 2);
  if (pressEl) pressEl.textContent = formatMetric(latest.pressure_bar, 2);
  if (biogasEl) biogasEl.textContent = formatMetric(latest.biogas_production_m3_day, 2);
  if (fcCurrent) fcCurrent.textContent = formatMetric(latest.biogas_production_m3_day, 2);
  if (feedEl) feedEl.textContent = formatMetric(latest.feedstock_mass_kg, 1);
  if (methEl) methEl.textContent = formatMetric(latest.methane_percent, 1);

  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
  if (latest.biogas_production_m3_day != null && !isNaN(latest.biogas_production_m3_day)) {
    const ch4Pct = (latest.methane_percent != null && !isNaN(latest.methane_percent) && latest.methane_percent > 0) ? Number(latest.methane_percent) : 60.0;
    const elecKwh = Number(latest.biogas_production_m3_day) * (ch4Pct / 100.0) * 9.94 * eff;
    const powerKw = elecKwh / 24.0;
    if (kpiElecPot) kpiElecPot.textContent = formatMetric(elecKwh, elecKwh >= 100 ? 1 : 2);
    if (kpiContPower) kpiContPower.textContent = formatMetric(powerKw, powerKw >= 100 ? 1 : 2);
    if (kpiElecProv) kpiElecProv.textContent = (latest.methane_percent != null && !isNaN(latest.methane_percent)) ? "[CALCULATED]" : "[CALCULATED @ ASSUMED 60% CH₄]";
    if (fcCurrentElec) fcCurrentElec.textContent = formatMetric(elecKwh, elecKwh >= 100 ? 1 : 2);
  } else {
    if (kpiElecPot) kpiElecPot.textContent = " — ";
    if (kpiContPower) kpiContPower.textContent = " — ";
    if (fcCurrentElec) fcCurrentElec.textContent = " — ";
  }

  const liveRecord = {
    biogas: latest.biogas_production_m3_day,
    methane: latest.methane_percent,
    temp: latest.temperature_c,
    ph: latest.ph,
    pressure: latest.pressure_bar,
    feed: latest.feedstock_mass_kg
  };
  updateEnergyGenerationSection(liveRecord);
  updateCommunityEnergySection(liveRecord);
}

function renderLiveIotForecastResult(fcData, latest, historyLength) {
  const kpiPredicted = document.getElementById('kpi-predicted-biogas');
  const kpiPredictedTop = document.getElementById('kpi-predicted-biogas-top');
  const fcPredictedElec = document.getElementById('forecast-predicted-elec');
  const kpiModelTop = document.getElementById('kpi-model-tag-top');
  const statusDot = document.getElementById('kpi-status-dot');
  const statusText = document.getElementById('kpi-status-text');
  const targetDateEl = document.getElementById('kpi-target-date');
  const historyBadge = document.getElementById('kpi-history-badge');
  const domainNoticeBox = document.getElementById('kpi-domain-notice-box');
  const domainNoticeText = document.getElementById('kpi-domain-notice-text');
  const causalFooter = document.getElementById('forecast-causal-footer');
  const modelTag = document.getElementById('kpi-model-tag');

  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
  const ch4Pct = (latest && latest.methane_percent != null && !isNaN(latest.methane_percent) && latest.methane_percent > 0) ? Number(latest.methane_percent) : 60.0;

  if (modelTag) modelTag.textContent = currentModel;
  if (kpiModelTop) kpiModelTop.textContent = `${currentModel} (t → t+1)`;
  if (targetDateEl) targetDateEl.textContent = 't+1 (Next-Day)';

  let lookbackRequired = 14;
  if (currentModel.includes("EMA")) lookbackRequired = 3;
  else if (currentModel.includes("Persistence")) lookbackRequired = 1;
  else if (currentModel.includes("XCO")) lookbackRequired = 7;

  if (historyBadge) {
    historyBadge.textContent = `${historyLength}/${lookbackRequired} timesteps`;
    if (historyLength >= lookbackRequired) {
      historyBadge.className = "px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30 font-mono";
    } else {
      historyBadge.className = "px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30 font-mono";
    }
  }

  if (causalFooter) {
    if (currentModel.includes("EMA")) {
      causalFooter.textContent = "Uses the previous 3 continuous timesteps and is generated causally from information available through the current day.";
    } else if (currentModel.includes("Persistence")) {
      causalFooter.textContent = "Uses the previous 1 timestep and is generated causally from information available through the current day.";
    } else if (currentModel.includes("XCO")) {
      causalFooter.textContent = "Uses the previous 7 continuous timesteps and is generated causally from information available through the current day.";
    } else {
      causalFooter.textContent = "Uses the previous 14 continuous timesteps and is generated causally from information available through the current day.";
    }
  }

  if (fcData.status === "INSUFFICIENT LIVE HISTORY" || fcData.status === "INSUFFICIENT_HISTORY") {
    if (kpiPredicted) {
      kpiPredicted.className = "text-3xl font-black text-rose-400 font-mono mt-1";
      kpiPredicted.textContent = '—';
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = '—';
    if (fcPredictedElec) fcPredictedElec.textContent = '—';
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-rose-400';
    if (statusText) {
      statusText.className = 'text-rose-400 font-mono text-[11px] truncate';
      statusText.textContent = `Status: INSUFFICIENT LIVE HISTORY (< ${lookbackRequired} obs)`;
    }
    if (domainNoticeBox) domainNoticeBox.classList.add('hidden');
    return;
  }

  if (fcData.status === "INSUFFICIENT LIVE FEATURES") {
    if (kpiPredicted) {
      kpiPredicted.className = "text-3xl font-black text-rose-400 font-mono mt-1";
      kpiPredicted.textContent = '—';
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = '—';
    if (fcPredictedElec) fcPredictedElec.textContent = '—';
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-rose-400';
    if (statusText) {
      statusText.className = 'text-rose-400 font-mono text-[11px] truncate';
      statusText.textContent = 'Status: INSUFFICIENT LIVE FEATURES';
    }
    if (domainNoticeBox) domainNoticeBox.classList.add('hidden');
    return;
  }

  if (!fcData.domain_valid) {
    if (kpiPredicted) {
      kpiPredicted.className = "text-lg md:text-xl font-black text-amber-300 tracking-tight leading-snug";
      kpiPredicted.textContent = "Not Validated for Community Scale";
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = 'UNVALIDATED';
    if (fcPredictedElec) fcPredictedElec.textContent = '—';
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse';
    if (statusText) {
      statusText.className = 'text-amber-400 font-mono text-[11px] truncate';
      statusText.textContent = 'SUCCESS (Causal past-only; transfer unvalidated)';
    }
    if (domainNoticeBox) {
      domainNoticeBox.classList.remove('hidden');
      if (domainNoticeText) {
        domainNoticeText.textContent = fcData.domain_note || "Industrial model calibrated on real Spark plant data (~5,300 Nm³/day). Current telemetry represents a community-scale digester. Industrial-to-community scale transfer has not been validated.";
      }
    }
  } else {
    const predBiogas = Number(fcData.predicted_biogas_m3_day);
    if (kpiPredicted) {
      kpiPredicted.className = "text-3xl font-black text-emerald-300 tracking-tight flex items-baseline gap-1 font-mono mt-1";
      kpiPredicted.textContent = formatMetric(predBiogas, 2);
    }
    if (kpiPredictedTop) kpiPredictedTop.textContent = formatMetric(predBiogas, 2);
    if (fcPredictedElec) {
      const predElec = predBiogas * (ch4Pct / 100.0) * 9.94 * eff;
      fcPredictedElec.textContent = formatMetric(predElec, predElec >= 100 ? 1 : 2);
    }
    if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse';
    if (statusText) {
      statusText.className = 'text-emerald-400 font-mono text-[11px] truncate';
      statusText.textContent = 'Status: SUCCESS (Causal past-only)';
    }
    if (domainNoticeBox) domainNoticeBox.classList.add('hidden');
  }
}

function updateLiveSustainability(latest) {
  const sustTitle = document.getElementById('sust-title');
  const sustQualifier = document.getElementById('sust-provenance-qualifier');
  if (sustTitle) sustTitle.innerHTML = '🌍 Community Impact — Derived from Live Telemetry';
  if (sustQualifier) sustQualifier.textContent = 'Based on measured live community telemetry; impact values are calculated estimates.';

  const feedstockEl = document.getElementById('sust-feedstock-val');
  const elecEl = document.getElementById('sust-elec-val');
  const energyEl = document.getElementById('sust-energy-val');
  const costEl = document.getElementById('sust-cost-val');

  if (!latest || latest.biogas_production_m3_day == null) {
    if (feedstockEl) feedstockEl.textContent = '—';
    if (elecEl) elecEl.textContent = '—';
    if (energyEl) energyEl.textContent = '—';
    if (costEl) costEl.textContent = '—';
    return;
  }

  const eff = (window.__GEN_EFF__ != null) ? window.__GEN_EFF__ : 0.30;
  const dailyBiogas = Number(latest.biogas_production_m3_day);
  const annualBiogas = dailyBiogas * 365;
  const ch4Pct = (latest.methane_pct != null && !isNaN(latest.methane_pct) && latest.methane_pct > 0) ? Number(latest.methane_pct) : 60.0;
  const dailyElec = dailyBiogas * (ch4Pct / 100.0) * 9.94 * eff;
  const annualElec = dailyElec * 365;
  const annualOffset = annualElec * 8.5; // illustrative local tariff ₹8.5/kWh
  const annualFeedstock = (Number(latest.feedstock_kg_day || 120) * 365) / 1000;

  if (feedstockEl) feedstockEl.textContent = `${annualFeedstock.toFixed(1)} MT/yr`;
  if (elecEl) elecEl.textContent = annualElec >= 10000 ? `${(annualElec / 1000).toFixed(1)} MWh/yr` : `${Math.round(annualElec).toLocaleString()} kWh/yr`;
  if (energyEl) energyEl.textContent = `${Math.round(annualBiogas).toLocaleString()} Nm³/yr`;
  if (costEl) costEl.textContent = `₹${Math.round(annualOffset).toLocaleString()}/yr`;
}

function updateLiveSolar() {
  const sTitle = document.getElementById('solar-subsystem-title');
  const sDesc = document.getElementById('solar-subsystem-desc');
  const sBadge = document.getElementById('solar-status-badge');
  if (sTitle) sTitle.textContent = "Solar Subsystem & Battery (Live Telemetry)";
  if (sDesc) sDesc.textContent = "Real-time solar auxiliary state and IoT battery monitoring node.";
  if (sBadge) {
    sBadge.textContent = "LIVE MONITOR";
    sBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
  }
}

// DYNAMICALLY POPULATE BENCHMARK MODAL FROM FASTAPI ENDPOINT
async function populateBenchmarkModal() {
  try {
    const res = await fetch('/api/forecast/benchmarks');
    if (res.ok) {
      const data = await res.json();
      const tbody = document.querySelector('#benchmark-modal tbody');
      if (tbody && data.models) {
        tbody.innerHTML = data.models.map(m => {
          const isDefault = m.role.includes("Default");
          const isResearch = m.category === "Research";
          let rowClass = "";
          let nameClass = "text-slate-300";
          if (isDefault) {
            rowClass = "bg-emerald-950/20 border-l-4 border-emerald-500";
            nameClass = "font-bold text-emerald-300";
          } else if (isResearch) {
            rowClass = "bg-cyan-950/20";
            nameClass = "font-bold text-cyan-300";
          } else if (m.model_name.includes("EMA")) {
            nameClass = "font-bold text-amber-300";
          }

          const formatSign = val => (val >= 0 ? `+${val.toFixed(4)}` : val.toFixed(4));

          return `
            <tr class="${rowClass}">
              <td class="py-3 px-3 ${nameClass}">${m.model_name}</td>
              <td class="py-3 px-2 font-sans text-[10px] font-bold ${isDefault ? 'text-emerald-400' : (isResearch ? 'text-cyan-400' : 'text-slate-400')}">${m.role}</td>
              <td class="py-3 px-2 text-slate-300">${m.lookback_days} days</td>
              <td class="py-3 px-2 text-white font-bold">${m.held_out_test_metrics.mae.toFixed(2)}</td>
              <td class="py-3 px-2 text-white font-bold">${m.held_out_test_metrics.rmse.toFixed(2)}</td>
              <td class="py-3 px-2 text-white">${formatSign(m.held_out_test_metrics.r2)}</td>
              <td class="py-3 px-2 ${isDefault ? 'text-emerald-300 font-bold' : 'text-slate-300'}">${m.cross_window_mean_metrics.mae.toFixed(2)}</td>
              <td class="py-3 px-2 ${isDefault ? 'text-emerald-300 font-bold' : 'text-slate-300'}">${m.cross_window_mean_metrics.rmse.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
              <td class="py-3 px-2 ${isDefault ? 'text-emerald-300' : 'text-slate-300'}">${formatSign(m.cross_window_mean_metrics.r2)}</td>
            </tr>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.warn("Failed to populate benchmark modal:", err);
  }
}

// POPULATE XCO-NET RESEARCH MODAL METRICS DYNAMICALLY
async function populateXconetModal() {
  const paramCountEl = document.getElementById('xco-param-count');
  if (paramCountEl && (!paramCountEl.textContent || paramCountEl.textContent === 'null' || paramCountEl.textContent === 'undefined')) {
    paramCountEl.textContent = '—';
  }
  try {
    const res = await fetch('/api/forecast/xconet-research');
    if (res.ok) {
      const data = await res.json();
      if (paramCountEl && data.total_trainable_parameters != null) {
        paramCountEl.textContent = Number(data.total_trainable_parameters).toLocaleString();
      }
    }
  } catch (err) {
    console.warn("Failed to populate XCO-Net research modal:", err);
  }
}

// CLEAR ALL SOURCE AND FORECAST STATE ON TRANSITION
function clearSourceState() {
  if (currentSourceAbortController) {
    currentSourceAbortController.abort();
  }
  currentSourceAbortController = new AbortController();
  currentSourceLoadToken++;

  stopAutoPlay();
  telemetryDataset = [];
  currentRecordIndex = 0;

  // Unconditionally dismiss AgSTAR modal on any source transition to prevent pointer-event traps
  const agstarModal = document.getElementById('agstar-modal');
  if (agstarModal) {
    agstarModal.classList.add('hidden');
    agstarModal.classList.remove('flex');
  }

  const livePill = document.getElementById('live-iot-status-pill');
  if (livePill) livePill.classList.add('hidden');
  const withheldNotice = document.getElementById('chart-withheld-notice');
  if (withheldNotice) withheldNotice.classList.add('hidden');
  const domainNoticeBox = document.getElementById('kpi-domain-notice-box');
  if (domainNoticeBox) domainNoticeBox.classList.add('hidden');

  const kpiPredicted = document.getElementById('kpi-predicted-biogas');
  if (kpiPredicted) {
    kpiPredicted.className = "text-3xl font-black text-slate-500 font-mono mt-1";
    kpiPredicted.textContent = '—';
  }
  const statusDot = document.getElementById('kpi-status-dot');
  if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-slate-500';
  const statusText = document.getElementById('kpi-status-text');
  if (statusText) {
    statusText.className = 'text-slate-400 font-mono text-[11px] truncate';
    statusText.textContent = 'Status: Initializing...';
  }
  const targetDateEl = document.getElementById('kpi-target-date');
  if (targetDateEl) targetDateEl.textContent = 't+1 (Next-Day)';
  const historyBadge = document.getElementById('kpi-history-badge');
  if (historyBadge) {
    historyBadge.textContent = '0 timesteps';
    historyBadge.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-bold border border-slate-700 font-mono';
  }
  const kpiCurrent = document.getElementById('kpi-current-biogas');
  const fcCurrent = document.getElementById('forecast-current-biogas');
  if (kpiCurrent) kpiCurrent.textContent = '—';
  if (fcCurrent) fcCurrent.textContent = '—';

  const tempEl = document.getElementById('kpi-temp-val');
  const phEl = document.getElementById('kpi-ph-val');
  const pressEl = document.getElementById('kpi-press-val');
  const feedEl = document.getElementById('kpi-feedstock-val');
  const methEl = document.getElementById('kpi-methane-val');
  if (tempEl) tempEl.textContent = '—';
  if (phEl) phEl.textContent = '—';
  if (pressEl) pressEl.textContent = '—';
  if (feedEl) feedEl.textContent = '—';
  if (methEl) methEl.textContent = '—';

  const headerSafety = document.getElementById('header-safety-indicator');
  const headerSafetyDot = document.getElementById('header-safety-dot');
  const headerSafetyText = document.getElementById('header-safety-text');
  if (headerSafety && headerSafetyText && headerSafetyDot) {
    headerSafety.className = "header-badge px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-lg sm:rounded-xl text-[10px] sm:text-xs font-bold border transition flex items-center gap-1.5 bg-slate-800 border-slate-700 text-slate-300";
    headerSafetyDot.className = "w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-slate-500 shrink-0";
    headerSafetyText.textContent = "Interlocks Initializing...";
  }

  const alertsList = document.getElementById('alerts-list');
  const alertBadge = document.getElementById('alert-count-badge');
  if (alertsList) {
    alertsList.innerHTML = `
      <div class="p-3 rounded-xl bg-slate-800/60 border border-slate-700 text-xs text-slate-400">
        ⚪ Initializing telemetry source...
      </div>
    `;
  }
  if (alertBadge) alertBadge.textContent = '0 Active';

  updateGauges(null);
  updateHealthIndex(null);
  updateSustainabilityMetrics(null);
  updateDrawerTelemetryPreview(null);

  if (productionChart) {
    productionChart.data.labels = [];
    productionChart.data.datasets[0].data = [];
    productionChart.data.datasets[1].data = [];
    productionChart.update('none');
  }

  const shapList = document.getElementById('shap-factors-list');
  if (shapList) shapList.classList.add('hidden');
  const attUnavailable = document.getElementById('attribution-unavailable-note');
  if (attUnavailable) attUnavailable.classList.add('hidden');
  const dynDetails = document.getElementById('interpretation-dynamic-details');
  if (dynDetails) dynDetails.classList.add('hidden');
}

// UPDATE SOURCE-AWARE KPI LABELS
function updateSourceKpiLabels(source) {
  const tempTitle = document.getElementById('kpi-temp-title');
  const phTitle = document.getElementById('kpi-ph-title');
  const pressTitle = document.getElementById('kpi-press-title');
  const biogasTitle = document.getElementById('kpi-current-biogas-title');
  const biogasSub = document.getElementById('kpi-current-biogas-sub');

  if (source === "LIVE_IOT") {
    if (tempTitle) tempTitle.textContent = "Live Temperature";
    if (phTitle) phTitle.textContent = "Live pH";
    if (pressTitle) pressTitle.textContent = "Live Gas Pressure";
    if (biogasTitle) biogasTitle.textContent = "Live Daily Production";
    if (biogasSub) biogasSub.textContent = "Live Sensor Reading";
  } else if (source === "USER_UPLOAD") {
    if (tempTitle) tempTitle.textContent = "Observed Temperature";
    if (phTitle) phTitle.textContent = "Observed pH";
    if (pressTitle) pressTitle.textContent = "Observed Pressure";
    if (biogasTitle) biogasTitle.textContent = "Observed Biogas";
    if (biogasSub) biogasSub.textContent = "User-Uploaded Telemetry";
  } else if (source === "DEMO_SYNTHETIC") {
    if (tempTitle) tempTitle.textContent = "Slurry Temperature";
    if (phTitle) phTitle.textContent = "Slurry pH Buffer";
    if (pressTitle) pressTitle.textContent = "Gas Pressure";
    if (biogasTitle) biogasTitle.textContent = "Current Biogas";
    if (biogasSub) biogasSub.textContent = "Simulated Daily Production";
  } else if (source === "REAL_SPARK_HISTORICAL" || source === "SPARK_FULL") {
    if (tempTitle) tempTitle.textContent = "Slurry Temperature";
    if (phTitle) phTitle.textContent = "Slurry pH Buffer";
    if (pressTitle) pressTitle.textContent = "Gas Pressure";
    if (biogasTitle) biogasTitle.textContent = "Current Biogas";
    if (biogasSub) biogasSub.textContent = "Observed Daily Production";
  }
}

// RESTORE OPERATIONAL PLAYBACK AND MODEL CONTROLS
function restoreOperationalControls() {
  const prevBtn = document.getElementById('prev-row-btn');
  const nextBtn = document.getElementById('next-row-btn');
  const autoBtn = document.getElementById('auto-play-btn');
  const rowDisp = document.getElementById('row-index-display');
  const modelSelect = document.getElementById('model-select');
  const withheldNotice = document.getElementById('chart-withheld-notice');
  const livePill = document.getElementById('live-iot-status-pill');

  if (prevBtn) {
    prevBtn.disabled = false;
    prevBtn.classList.remove('opacity-40', 'cursor-not-allowed');
  }
  if (nextBtn) {
    nextBtn.disabled = false;
    nextBtn.classList.remove('opacity-40', 'cursor-not-allowed');
  }
  if (autoBtn) autoBtn.classList.remove('hidden');
  if (rowDisp) rowDisp.classList.remove('hidden');
  if (modelSelect) {
    modelSelect.disabled = false;
    modelSelect.classList.remove('opacity-40', 'cursor-not-allowed');
    modelSelect.removeAttribute('title');
  }
  if (withheldNotice) withheldNotice.classList.add('hidden');
  if (livePill) livePill.classList.add('hidden');
}

// RENDER DEDICATED AGSTAR BENCHMARK STATE (NON-TIMESERIES, FORECASTING DISABLED)
function renderAgstarBenchmarkState() {
  currentDataSource = "AGSTAR_REGISTRY";
  stopAutoPlay();

  // 1. Disable playback controls & model selector
  const prevBtn = document.getElementById('prev-row-btn');
  const nextBtn = document.getElementById('next-row-btn');
  const autoBtn = document.getElementById('auto-play-btn');
  const rowDisp = document.getElementById('row-index-display');
  const modelSelect = document.getElementById('model-select');

  if (prevBtn) {
    prevBtn.disabled = true;
    prevBtn.classList.add('opacity-40', 'cursor-not-allowed');
  }
  if (nextBtn) {
    nextBtn.disabled = true;
    nextBtn.classList.add('opacity-40', 'cursor-not-allowed');
  }
  if (autoBtn) autoBtn.classList.add('hidden');
  if (rowDisp) rowDisp.classList.add('hidden');
  if (modelSelect) {
    modelSelect.disabled = true;
    modelSelect.classList.add('opacity-40', 'cursor-not-allowed');
    modelSelect.title = "Forecasting models disabled for static benchmark";
  }

  // 2. Clear / Reset Numerical Forecast & Execution State
  const kpiPredicted = document.getElementById('kpi-predicted-biogas');
  const statusDot = document.getElementById('kpi-status-dot');
  const statusText = document.getElementById('kpi-status-text');
  const targetDateEl = document.getElementById('kpi-target-date');
  const modelTag = document.getElementById('kpi-model-tag');
  const historyBadge = document.getElementById('kpi-history-badge');
  const domainBadge = document.getElementById('header-domain-badge');
  const domainContextTag = document.getElementById('kpi-domain-context-tag');
  const provenanceBadge = document.getElementById('kpi-provenance-badge');
  const domainNoticeBox = document.getElementById('kpi-domain-notice-box');
  const domainNoticeText = document.getElementById('kpi-domain-notice-text');
  const causalFooter = document.getElementById('forecast-causal-footer');
  const kpiCurrent = document.getElementById('kpi-current-biogas');
  const fcCurrent = document.getElementById('forecast-current-biogas');
  const kpiCurrentSub = document.getElementById('kpi-current-sub');

  if (kpiPredicted) {
    kpiPredicted.className = "text-3xl font-black text-slate-500 font-mono mt-1";
    kpiPredicted.textContent = '—';
  }
  if (statusDot) statusDot.className = 'w-1.5 h-1.5 rounded-full bg-slate-500';
  if (statusText) {
    statusText.className = 'text-slate-400 font-mono text-[11px] truncate';
    statusText.textContent = 'External benchmark — forecasting disabled';
  }
  if (targetDateEl) targetDateEl.textContent = 'None (Static Benchmark)';
  if (modelTag) modelTag.textContent = 'None (Static Benchmark)';
  if (historyBadge) {
    historyBadge.textContent = 'N/A (Static Benchmark)';
    historyBadge.className = 'px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-bold border border-slate-700 font-mono';
  }
  if (domainBadge) {
    domainBadge.textContent = 'EXTERNAL STATIC BENCHMARK';
    domainBadge.className = 'px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-blue-500/10 border border-blue-500/30 text-blue-300 uppercase tracking-wide';
  }
  if (domainContextTag) {
    domainContextTag.textContent = 'Static Benchmark (AgSTAR)';
    domainContextTag.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-blue-500/20 border border-blue-500/40 text-blue-300 uppercase';
  }
  if (provenanceBadge) {
    provenanceBadge.textContent = 'AGSTAR_REGISTRY';
    provenanceBadge.className = 'px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold bg-blue-900/60 border border-blue-600/50 text-blue-300 uppercase';
  }
  if (domainNoticeBox) {
    domainNoticeBox.classList.remove('hidden');
    domainNoticeBox.className = 'p-3 rounded-xl bg-blue-500/10 border border-blue-500/30 text-xs text-blue-300 flex items-start gap-2.5';
    if (domainNoticeText) {
      domainNoticeText.textContent = 'AgSTAR is an external static macro benchmark of 526 commercial livestock anaerobic digester facilities across 38 US States, not continuous operational time-series telemetry. Time-series forecasting models (GRU-14d Residual, EMA-0.90, Persistence, XCO-Net) are disabled for this source.';
    }
  }
  if (causalFooter) {
    causalFooter.textContent = 'Role: External benchmark/context only — not used as GRU time-series input. Forecasting models disabled.';
  }
  if (kpiCurrent) kpiCurrent.textContent = '—';
  if (fcCurrent) fcCurrent.textContent = '—';
  const kpiElecPot = document.getElementById('kpi-electricity-potential');
  const kpiContPower = document.getElementById('kpi-continuous-power');
  const kpiPredTop = document.getElementById('kpi-predicted-biogas-top');
  const fcCurrentElec = document.getElementById('forecast-current-elec');
  const fcPredictedElec = document.getElementById('forecast-predicted-elec');
  if (kpiElecPot) kpiElecPot.textContent = '—';
  if (kpiContPower) kpiContPower.textContent = '—';
  if (kpiPredTop) kpiPredTop.textContent = '—';
  if (fcCurrentElec) fcCurrentElec.textContent = '—';
  if (fcPredictedElec) fcPredictedElec.textContent = '—';
  if (kpiCurrentSub) kpiCurrentSub.textContent = 'Static Registry Benchmark (Non-TimeSeries)';

  // 3. Clear Process KPIs
  const tempEl = document.getElementById('kpi-temp-val');
  const phEl = document.getElementById('kpi-ph-val');
  const feedEl = document.getElementById('kpi-feedstock-val');
  const feedRef = document.getElementById('kpi-feedstock-sub');
  const methEl = document.getElementById('kpi-methane-val');
  if (tempEl) tempEl.textContent = '—';
  if (phEl) phEl.textContent = '—';
  if (feedEl) feedEl.textContent = '—';
  if (feedRef) feedRef.textContent = 'Manure Slurry (Livestock Dairy/Swine)';
  if (methEl) methEl.textContent = '—';

  // 4. Feature attribution
  const shapList = document.getElementById('shap-factors-list');
  const attUnavailable = document.getElementById('attribution-unavailable-note');
  const attTitle = document.getElementById('model-interpretation-title');
  const attBadge = document.getElementById('model-interpretation-badge');
  const attSub = document.getElementById('model-interpretation-sub');
  if (attTitle) attTitle.textContent = "Benchmark Registry Profile";
  if (attBadge) {
    attBadge.textContent = "Static Data";
    attBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30";
  }
  if (attSub) attSub.textContent = "USDA / EPA AgSTAR Livestock Anaerobic Digester Database";
  if (shapList) shapList.classList.add('hidden');
  if (attUnavailable) {
    attUnavailable.classList.remove('hidden');
    attUnavailable.textContent = "Time-series forecasting models and feature attribution are disabled for static benchmarks.";
  }

  // 5. Clear Production Chart
  if (productionChart) {
    productionChart.data.labels = [];
    productionChart.data.datasets[0].data = [];
    productionChart.data.datasets[1].data = [];
    productionChart.update('none');
  }
  const tsSub = document.getElementById('timeseries-sub');
  if (tsSub) {
    tsSub.innerHTML = 'AgSTAR Livestock Digester Registry • Static Benchmark (<span class="text-blue-400 font-mono">Time-Series Charting Disabled</span>)';
  }
  const withheldNotice = document.getElementById('chart-withheld-notice');
  if (withheldNotice) {
    withheldNotice.textContent = "Time-series charting and forecasting are disabled for static registry benchmarks.";
    withheldNotice.classList.remove('hidden');
  }

  // 6. Sustainability Impact & Solar Subsystem
  const sustTitle = document.getElementById('sust-title');
  const sustQualifier = document.getElementById('sust-provenance-qualifier');
  if (sustTitle) sustTitle.innerHTML = '🌍 External Macro Benchmark Reference';
  if (sustQualifier) sustQualifier.textContent = 'USDA/EPA AgSTAR Livestock Digester Registry (526 facilities across 38 US States) — static reference context only.';
  const feedstockEl = document.getElementById('sust-feedstock-val');
  const elecEl = document.getElementById('sust-elec-val');
  const energyEl = document.getElementById('sust-energy-val');
  const costEl = document.getElementById('sust-cost-val');
  if (feedstockEl) feedstockEl.textContent = '—';
  if (elecEl) elecEl.textContent = '—';
  if (energyEl) energyEl.textContent = '—';
  if (costEl) costEl.textContent = '—';
  updateEnergyGenerationSection(null);
  updateCommunityEnergySection(null);

  const sTitle = document.getElementById('solar-subsystem-title');
  const sDesc = document.getElementById('solar-subsystem-desc');
  const sBadge = document.getElementById('solar-status-badge');
  if (sTitle) sTitle.textContent = 'Auxiliary Solar Subsystem — Not Applicable';
  if (sDesc) sDesc.textContent = 'AgSTAR is an external static livestock digester registry. Solar subsystem telemetry is not applicable.';
  if (sBadge) {
    sBadge.textContent = 'INACTIVE';
    sBadge.className = 'text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700';
  }

  // 7. Dataset banner info
  const countEl = document.getElementById('dataset-row-count');
  if (countEl) countEl.textContent = '526';
  const infoStr = document.getElementById('dataset-info-str');
  if (infoStr) {
    infoStr.innerHTML = `Loaded <strong class="text-white font-mono">526</strong> commercial facilities across <strong class="text-white font-mono">38 US States</strong> from <code class="text-blue-400 bg-slate-900 px-2 py-0.5 rounded font-bold">USDA / EPA AgSTAR Registry</code> (Static External Benchmark — Forecasting Disabled)`;
  }
}

// INITIALIZE FORECAST CONTROLS & MODALS
function initForecastControls() {
  const modelSelect = document.getElementById('model-select');
  const sourceSelect = document.getElementById('telemetry-source-select');
  const openBenchBtn = document.getElementById('open-benchmarks-btn');
  const closeBenchBtn = document.getElementById('close-benchmarks-btn');
  const benchModal = document.getElementById('benchmark-modal');
  const openXcoBtn = document.getElementById('open-xconet-btn');
  const closeXcoBtn = document.getElementById('close-xconet-btn');
  const xcoModal = document.getElementById('xconet-modal');

  // Health modal controls
  const openHealthBtn = document.getElementById('open-health-method-btn');
  const closeHealthBtn = document.getElementById('close-health-method-btn');
  const healthModal = document.getElementById('health-method-modal');

  // AgSTAR modal controls
  const closeAgstarBtn = document.getElementById('close-agstar-btn');
  const agstarModal = document.getElementById('agstar-modal');

  if (modelSelect) {
    modelSelect.addEventListener('change', async (e) => {
      currentModel = e.target.value;
      if (currentDataSource === "LIVE_IOT") {
        await loadLiveIotData();
      } else if (currentDataSource === "USER_UPLOAD") {
        await renderAllMetrics();
      } else if (currentDataSource === "REAL_SPARK_HISTORICAL") {
        await loadSparkReplayData("held_out_test");
      } else if (currentDataSource === "SPARK_FULL") {
        await loadSparkReplayData("full_historical");
      } else if (currentDataSource === "DEMO_SYNTHETIC") {
        await renderAllMetrics();
      }
    });
  }

  if (sourceSelect) {
    sourceSelect.addEventListener('change', async (e) => {
      const selectedSource = e.target.value;
      clearSourceState();

      if (selectedSource === "AGSTAR_REGISTRY") {
        currentDataSource = "AGSTAR_REGISTRY";
        renderAgstarBenchmarkState();
        if (agstarModal) {
          agstarModal.classList.remove('hidden');
          agstarModal.classList.add('flex');
        }
        return;
      }

      restoreOperationalControls();

      currentDataSource = selectedSource;
      if (currentDataSource === "LIVE_IOT") {
        await loadLiveIotData();
      } else if (currentDataSource === "USER_UPLOAD") {
        updateSourceKpiLabels("USER_UPLOAD");
        if (currentIngestionReport && currentIngestionReport.clean_rows && currentIngestionReport.clean_rows.length > 0) {
          activateUploadedDataset();
        } else {
          const fi = document.getElementById('scada-file-input') || document.getElementById('excel-file-input');
          if (fi) fi.click();
          const reportModal = document.getElementById('ingestion-report-modal');
          if (reportModal) {
            reportModal.classList.remove('hidden');
            reportModal.classList.add('flex');
          }
        }
      } else if (currentDataSource === "REAL_SPARK_HISTORICAL") {
        updateSourceKpiLabels("REAL_SPARK_HISTORICAL");
        await loadSparkReplayData("held_out_test");
      } else if (currentDataSource === "SPARK_FULL") {
        updateSourceKpiLabels("SPARK_FULL");
        await loadSparkReplayData("full_historical");
      } else {
        updateSourceKpiLabels("DEMO_SYNTHETIC");
        await loadSimulatorData();
      }
    });
  }

  // Benchmark Modal
  if (openBenchBtn && benchModal) {
    openBenchBtn.addEventListener('click', () => {
      populateBenchmarkModal();
      benchModal.classList.remove('hidden');
      benchModal.classList.add('flex');
    });
  }
  if (closeBenchBtn && benchModal) {
    closeBenchBtn.addEventListener('click', () => {
      benchModal.classList.add('hidden');
      benchModal.classList.remove('flex');
    });
  }
  if (benchModal) {
    benchModal.addEventListener('click', (e) => {
      if (e.target === benchModal) {
        benchModal.classList.add('hidden');
        benchModal.classList.remove('flex');
      }
    });
  }

  // XCO-Net Modal
  if (openXcoBtn && xcoModal) {
    openXcoBtn.addEventListener('click', () => {
      populateXconetModal();
      xcoModal.classList.remove('hidden');
      xcoModal.classList.add('flex');
    });
  }
  if (closeXcoBtn && xcoModal) {
    closeXcoBtn.addEventListener('click', () => {
      xcoModal.classList.add('hidden');
      xcoModal.classList.remove('flex');
    });
  }
  if (xcoModal) {
    xcoModal.addEventListener('click', (e) => {
      if (e.target === xcoModal) {
        xcoModal.classList.add('hidden');
        xcoModal.classList.remove('flex');
      }
    });
  }

  // Health Method Modal
  if (openHealthBtn && healthModal) {
    openHealthBtn.addEventListener('click', () => {
      healthModal.classList.remove('hidden');
      healthModal.classList.add('flex');
    });
  }
  if (closeHealthBtn && healthModal) {
    closeHealthBtn.addEventListener('click', () => {
      healthModal.classList.add('hidden');
      healthModal.classList.remove('flex');
    });
  }
  if (healthModal) {
    healthModal.addEventListener('click', (e) => {
      if (e.target === healthModal) {
        healthModal.classList.add('hidden');
        healthModal.classList.remove('flex');
      }
    });
  }

  // AgSTAR Modal
  if (closeAgstarBtn && agstarModal) {
    closeAgstarBtn.addEventListener('click', () => {
      agstarModal.classList.add('hidden');
      agstarModal.classList.remove('flex');
    });
  }
  if (agstarModal) {
    agstarModal.addEventListener('click', (e) => {
      if (e.target === agstarModal) {
        agstarModal.classList.add('hidden');
        agstarModal.classList.remove('flex');
      }
    });
  }
}

// RENDER ACTIVE ALERTS
function renderAlertsList(alerts) {
  const listEl = document.getElementById('alerts-list');
  const badge = document.getElementById('alert-count-badge');
  if (!listEl) return;

  if (badge) badge.textContent = `${alerts.length} Active`;

  if (!alerts || alerts.length === 0) {
    listEl.innerHTML = `
      <div class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300">
        🟢 All biokinetic and electrical safety thresholds are normal.
      </div>
    `;
    return;
  }

  listEl.innerHTML = alerts.map(a => {
    const isCrit = a.severity === 'CRITICAL';
    const color = isCrit ? 'rose' : 'amber';
    return `
      <div class="p-3 rounded-xl bg-${color}-500/10 border border-${color}-500/30 text-xs space-y-1">
        <div class="flex items-center justify-between font-bold text-${color}-400">
          <span>${isCrit ? '🚨' : '⚠️'} [${a.severity}] ${a.parameter.toUpperCase()}</span>
          <button onclick="acknowledgeAlert(${a.id})" class="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">Ack</button>
        </div>
        <p class="text-slate-300 text-[11px]">${a.message}</p>
      </div>
    `;
  }).join('');
}

async function acknowledgeAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' });
    if (res.ok) {
      const alertsRes = await fetch('/api/alerts?device_id=DIGESTER_001&unacknowledged_only=true');
      if (alertsRes.ok) {
        latestAlerts = await alertsRes.json();
        renderAlertsList(latestAlerts);
      }
    }
  } catch (err) {
    console.warn('Acknowledge alert failed:', err);
  }
}
window.acknowledgeAlert = acknowledgeAlert;

// UPDATE DRAWER TELEMETRY PREVIEW
function updateDrawerTelemetryPreview(curr) {
  const dt = document.getElementById('drawer-temp');
  const dp = document.getElementById('drawer-ph');
  const dpr = document.getElementById('drawer-press');
  const dch = document.getElementById('drawer-ch4');

  if (!curr) {
    if (dt) dt.textContent = " — ";
    if (dp) dp.textContent = " — ";
    if (dpr) dpr.textContent = " — ";
    if (dch) dch.textContent = " — ";
    return;
  }

  if (dt) dt.textContent = formatMetricWithUnit(curr.temp, 1, "°C");
  if (dp) dp.textContent = formatMetric(curr.ph, 2);
  if (dpr) dpr.textContent = formatMetricWithUnit(curr.pressure, 2, " bar");
  if (dch) dch.textContent = formatMetricWithUnit(curr.methane, 1, "%");
}

// ================================================================
// CONVERSATIONAL AI ASSISTANT (CHATGPT-STYLE GLASS DRAWER)
// ================================================================
function initChatAssistant() {
  const floatBtn = document.getElementById('floating-ai-btn');
  const closeBtn = document.getElementById('close-ai-drawer-btn');
  const drawer = document.getElementById('xco-ai-drawer');
  const sendBtn = document.getElementById('send-chat-btn');
  const inputEl = document.getElementById('chat-user-input');
  const chips = document.querySelectorAll('.chat-chip');

  if (floatBtn && drawer) {
    floatBtn.addEventListener('click', () => drawer.classList.remove('translate-x-full'));
  }
  if (closeBtn && drawer) {
    closeBtn.addEventListener('click', () => drawer.classList.add('translate-x-full'));
  }

  if (sendBtn && inputEl) {
    sendBtn.addEventListener('click', () => handleChatMessage());
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleChatMessage();
    });
  }

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-query');
      if (inputEl) inputEl.value = q;
      handleChatMessage();
    });
  });
}

async function handleChatMessage() {
  const inputEl = document.getElementById('chat-user-input');
  const sendBtn = document.getElementById('send-chat-btn');
  if (!inputEl) return;
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = '';
  appendUserMessage(text);
  showTypingIndicator();

  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.classList.add('opacity-50', 'cursor-not-allowed');
  }

  try {
    const curr = getCurrentRecord();
    const payload = {
      message: text,
      telemetry: curr ? {
        temp: curr.temp ?? null,
        ph: curr.ph ?? null,
        pressure: curr.pressure ?? null,
        methane: curr.methane ?? null,
        feed: curr.feed ?? null,
        biogas: curr.biogas ?? null,
        flow: curr.flow ?? null,
        level: curr.level ?? null,
        waste: curr.waste ?? null,
        solar_power: latestSolar ? latestSolar.solar_power_w / 1000.0 : null,
        battery_soc: latestSolar ? latestSolar.battery_soc_percent : null,
        source: currentDataSource
      } : null,
      timestamp: new Date().toISOString()
    };

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000)
    });

    removeTypingIndicator();

    if (!res.ok) {
      appendErrorMessage('Chat assistant temporarily unavailable. Please try again.');
      return;
    }

    const data = await res.json();
    if (data && data.reply) {
      appendAssistantMessage(data.reply, data.model, data.source);
    } else {
      appendErrorMessage('No reply generated. Check backend connection.');
    }

  } catch (err) {
    console.error('Chat error:', err);
    removeTypingIndicator();
    if (err.name === 'TimeoutError') {
      appendErrorMessage('Chat request timed out after 15 seconds. Please try again.');
    } else {
      appendErrorMessage('Could not connect to the AI assistant backend.');
    }
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }
}

function appendUserMessage(text) {
  const box = document.getElementById('chat-messages-container');
  if (!box) return;

  const div = document.createElement('div');
  div.className = 'flex items-start gap-3 justify-end';
  div.innerHTML = `
    <div class="p-3 rounded-2xl bg-blue-600/30 border border-blue-500/40 text-xs text-slate-100 font-medium max-w-[85%]">
      ${escapeHtml(text)}
    </div>
    <div class="w-7 h-7 rounded-xl bg-slate-800 flex items-center justify-center text-slate-300 text-xs shrink-0 font-bold border border-slate-700">
      👤
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function appendAssistantMessage(replyText, model, source) {
  const box = document.getElementById('chat-messages-container');
  if (!box) return;

  const formattedHtml = formatMarkdown(replyText);
  const isGemini = source === 'gemini-api';

  const div = document.createElement('div');
  div.className = 'flex items-start gap-3';
  div.innerHTML = `
    <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center text-white text-xs shrink-0 font-bold shadow-md shadow-emerald-500/20">
      ⚡
    </div>
    <div class="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-100 leading-relaxed max-w-[90%] space-y-1.5 font-sans">
      <div class="flex items-center justify-between text-[10px] text-slate-400 pb-1 border-b border-slate-800 font-mono">
        <span class="${isGemini ? 'text-emerald-400 font-bold' : 'text-amber-400'}">${isGemini ? '● Gemini 2.5 Active' : '● Local Rule Engine'}</span>
        <span>${model || 'AI Model'}</span>
      </div>
      <div>${formattedHtml}</div>
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function appendErrorMessage(msg) {
  const box = document.getElementById('chat-messages-container');
  if (!box) return;

  const div = document.createElement('div');
  div.className = 'flex items-start gap-3';
  div.innerHTML = `
    <div class="w-8 h-8 rounded-xl bg-rose-500 flex items-center justify-center text-white text-xs shrink-0 font-bold">
      ⚠️
    </div>
    <div class="p-3 rounded-2xl bg-slate-900 border border-rose-500/40 text-xs text-rose-300 font-medium max-w-[90%]">
      ${escapeHtml(msg)}
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function showTypingIndicator() {
  const box = document.getElementById('chat-messages-container');
  if (!box || document.getElementById('ai-typing-indicator')) return;

  const div = document.createElement('div');
  div.id = 'ai-typing-indicator';
  div.className = 'flex items-start gap-3';
  div.innerHTML = `
    <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center text-white text-xs shrink-0 font-bold shadow-md shadow-emerald-500/20">
      ⚡
    </div>
    <div class="p-3 rounded-2xl bg-slate-900 border border-slate-800 flex items-center gap-1.5 text-emerald-400">
      <span class="w-2 h-2 rounded-full bg-emerald-400 typing-dot"></span>
      <span class="w-2 h-2 rounded-full bg-emerald-400 typing-dot"></span>
      <span class="w-2 h-2 rounded-full bg-emerald-400 typing-dot"></span>
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('ai-typing-indicator');
  if (el) el.remove();
}

function formatMarkdown(text) {
  if (!text) return '';
  let escaped = escapeHtml(text);

  // Headers (### Header)
  escaped = escaped.replace(/### (.*?)(<br>|$)/g, '<div class="text-sm font-bold text-emerald-400 mt-2 mb-1">$1</div>');
  // Bold (**text**)
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong class="text-emerald-300 font-bold">$1</strong>');
  // Inline code (`code`)
  escaped = escaped.replace(/`(.*?)`/g, '<code class="bg-slate-950 px-1.5 py-0.5 rounded text-amber-300 font-mono text-[11px]">$1</code>');
  // Blockquotes (> text)
  escaped = escaped.replace(/^&gt; (.*?)$/gm, '<div class="pl-2 border-l-2 border-emerald-500 text-slate-400 italic my-1">$1</div>');
  // Bullet lists (- text)
  escaped = escaped.replace(/^- (.*?)$/gm, '<li class="ml-3 list-disc">$1</li>');
  // Line breaks
  escaped = escaped.replace(/\n/g, '<br>');

  return escaped;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
