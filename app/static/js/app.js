// ==========================================================================
// MASTER APP CONTROLLER - FORGE STUDIO (v2.3)
// Flow: import -> crop (Confirm Crop cuts the rest) -> colour -> anti-detect
// on the cropped clip at its own size -> hashed clip AUTO-REPLACES the studio
// clip -> pick canvas aspect (Fill/Fit) -> masks & text -> export.
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  const video = document.getElementById('mainVideo');
  const stageCanvasContainer = document.getElementById('stageCanvasContainer');
  const stageEmptyState = document.getElementById('stageEmptyState');
  const mediaMetaPill = document.getElementById('mediaMetaPill');

  // Sub-managers (masks & text share the cropper's coordinate basis so they
  // stay glued to the content when the crop is confirmed and the stage
  // re-frames to the cropped view)
  const colorGrading = new ColorGradingManager(video);
  const canvasCropper = new CanvasCropper(stageCanvasContainer, video);
  const maskOverlay = new MaskOverlayManager(stageCanvasContainer, video, () => canvasCropper.getBasis());
  const textOverlay = new TextOverlayManager(stageCanvasContainer, video, () => canvasCropper.getBasis());
  const timeline = new TimelineManager(video);

  // App State
  const state = {
    currentFile: null,
    meta: null,
    hashingProfile: 'BALANCED',
    hashingEnabled: true,
    engineAvailable: false,
    mlRunnable: false,
    hashResult: null,
    hashedPayload: null,
    pendingSignature: null,
    jobId: null,
    logCount: 0,
    pollTimer: null,
    modalMinimized: false,
    clipIsHashed: false,   // true right after the hashed clip auto-replaces the source
  };

  const PROFILE_BADGES = {
    BALANCED: { label: 'DEFAULT', cls: 'badge-rec' },
    SAFE: { label: 'LOW', cls: '' },
    AGGRESSIVE: { label: 'HIGH', cls: 'badge-high' },
    AIMIMIC: { label: 'AI STYLE', cls: 'badge-high' },
    TOON: { label: 'ANIME', cls: '' },
    MAXIMUM: { label: 'NUCLEAR', cls: 'badge-max' },
  };

  // --------------------------------------------------------------------------
  // Tab Navigation
  // --------------------------------------------------------------------------
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.tab;
      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add('active');

      if (targetId === 'tab-hashing') refreshStaleState();
    });
  });

  // --------------------------------------------------------------------------
  // Ingestion: File Upload & Dropzone
  // --------------------------------------------------------------------------
  const dropzone = document.getElementById('fileDropzone');
  const fileInput = document.getElementById('fileInput');
  const btnEmptyBrowse = document.getElementById('btnEmptyBrowse');

  dropzone.addEventListener('click', () => fileInput.click());
  btnEmptyBrowse.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      uploadFile(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });

  async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    showToast(`Uploading ${file.name}...`);
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');

      loadVideoIntoStudio(data);
      loadStorage();
      showToast('Video loaded successfully!', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // --------------------------------------------------------------------------
  // Ingestion: Social Media URL Downloader (yt-dlp)
  // --------------------------------------------------------------------------
  const inputVideoUrl = document.getElementById('inputVideoUrl');
  const btnFetchUrl = document.getElementById('btnFetchUrl');
  const btnEmptyUrl = document.getElementById('btnEmptyUrl');
  const urlLoading = document.getElementById('urlLoadingIndicator');

  btnEmptyUrl.addEventListener('click', () => {
    document.getElementById('tabBtnSource').click();
    inputVideoUrl.focus();
  });

  btnFetchUrl.addEventListener('click', () => fetchUrlVideo());
  inputVideoUrl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') fetchUrlVideo();
  });

  async function fetchUrlVideo() {
    const url = inputVideoUrl.value.trim();
    if (!url) {
      showToast('Please paste a valid video URL.', 'error');
      return;
    }

    urlLoading.style.display = 'flex';
    btnFetchUrl.disabled = true;

    try {
      const res = await fetch('/api/fetch-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to download video');

      loadVideoIntoStudio(data);
      inputVideoUrl.value = '';
      loadStorage();
      showToast('Video downloaded and loaded!', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      urlLoading.style.display = 'none';
      btnFetchUrl.disabled = false;
    }
  }

  // --------------------------------------------------------------------------
  // Load Video Setup
  // --------------------------------------------------------------------------
  function loadVideoIntoStudio(meta) {
    state.currentFile = meta.filename;
    state.meta = meta;
    state.clipIsHashed = Boolean(meta.clipIsHashed);

    // A new source invalidates anything hashed from the previous one.
    resetHashState();

    stageEmptyState.style.display = 'none';
    stageCanvasContainer.style.display = 'block';
    mediaMetaPill.style.display = 'flex';

    document.getElementById('metaFileName').textContent = meta.filename.split('_').slice(1).join('_') || meta.filename;
    document.getElementById('metaResolution').textContent = `${meta.width}×${meta.height}`;
    document.getElementById('metaDuration').textContent = timeline.formatTime(meta.duration);
    document.getElementById('metaFps').textContent = `${meta.fps} fps`;

    video.src = meta.url;
    video.load();

    video.onloadedmetadata = () => {
      adjustStageSize(meta.width, meta.height);
      canvasCropper.onVideoLoaded();
      timeline.onVideoLoaded(meta.duration);
    };

    updateHashButton();
  }

  function adjustStageSize(nativeW, nativeH) {
    const viewportBox = document.getElementById('viewportBox');
    const maxW = viewportBox.clientWidth - 40;
    const maxH = viewportBox.clientHeight - 40;

    if (canvasCropper.applied) {
      // Confirmed crop: the stage IS the crop window.
      canvasCropper.layoutApplied(maxW, maxH);
      return;
    }

    canvasCropper.clearAppliedLayout();

    let targetW = maxW;
    let targetH = targetW * (nativeH / nativeW);

    if (targetH > maxH) {
      targetH = maxH;
      targetW = targetH * (nativeW / nativeH);
    }

    stageCanvasContainer.style.width = `${Math.round(targetW)}px`;
    stageCanvasContainer.style.height = `${Math.round(targetH)}px`;
    video.style.width = `${Math.round(targetW)}px`;
    video.style.height = `${Math.round(targetH)}px`;
  }

  window.addEventListener('resize', () => {
    if (state.meta) {
      adjustStageSize(state.meta.width, state.meta.height);
      canvasCropper.updateDOM();
      maskOverlay.updateAllDOM();
      textOverlay.refreshAllDOM();
    }
  });

  // --------------------------------------------------------------------------
  // Confirm Crop wiring: apply the crop to the stage / jump back to editing
  // --------------------------------------------------------------------------
  const btnConfirmCrop = document.getElementById('btnConfirmCrop');
  const btnEditCrop = document.getElementById('btnEditCrop');
  const cropModeHint = document.getElementById('cropModeHint');

  canvasCropper.onModeChange = (applied) => {
    if (state.meta) adjustStageSize(state.meta.width, state.meta.height);
    maskOverlay.updateAllDOM();
    textOverlay.refreshAllDOM();
    if (btnConfirmCrop) btnConfirmCrop.style.display = applied ? 'none' : '';
    if (btnEditCrop) btnEditCrop.style.display = applied ? '' : 'none';
    if (cropModeHint) {
      cropModeHint.textContent = applied
        ? 'Crop applied — this frame is exactly what the pipeline works with. Hit Edit Crop to adjust.'
        : 'Drag the box over the frame — the dimmed area gets cut away — then hit Confirm Crop to see the real result.';
    }
  };

  if (btnConfirmCrop) {
    btnConfirmCrop.addEventListener('click', () => {
      canvasCropper.confirmCrop();
      refreshStaleState();
    });
  }
  if (btnEditCrop) {
    btnEditCrop.addEventListener('click', () => {
      canvasCropper.editCrop();
      refreshStaleState();
    });
  }

  // --------------------------------------------------------------------------
  // Content Hashing Configuration
  // --------------------------------------------------------------------------
  const profileGrid = document.getElementById('profileGrid');
  const hashingToggle = document.getElementById('hashingEnableToggle');
  const hashingControlsWrap = document.getElementById('hashingControlsWrap');
  const engineStatus = document.getElementById('engineStatus');
  const engineStatusText = document.getElementById('engineStatusText');
  const mlStatus = document.getElementById('mlStatus');
  const mlStatusBadge = document.getElementById('mlStatusBadge');
  const mlStatusText = document.getElementById('mlStatusText');
  const btnRunHashing = document.getElementById('btnRunHashing');
  const btnRunHashingLabel = document.getElementById('btnRunHashingLabel');
  const hashHint = document.getElementById('hashHint');

  async function loadEngineConfig() {
    try {
      const res = await fetch('/api/profiles');
      const data = await res.json();

      state.mlRunnable = Boolean(data.ml_stage && data.ml_stage.runnable);
      renderMlStatus(data.ml_stage, data.ml_profiles || []);
      renderProfiles(data.profiles || []);

      state.engineAvailable = Boolean(data.engine && data.engine.available);
      if (state.engineAvailable) {
        engineStatus.classList.add('is-ok');
        engineStatus.classList.remove('is-bad');
        engineStatusText.textContent = `Hash engine ready — ${(data.profiles || []).length} profiles loaded.`;
      } else {
        engineStatus.classList.add('is-bad');
        engineStatus.classList.remove('is-ok');
        const reason = (data.engine && data.engine.error) || 'v7_pipeline failed to import';
        engineStatusText.textContent = `Hash engine unavailable: ${reason}. Run: pip install -r requirements.txt`;
      }
    } catch (err) {
      state.engineAvailable = false;
      engineStatus.classList.add('is-bad');
      engineStatusText.textContent = `Could not reach the hash engine: ${err.message}`;
    }
    updateHashButton();
  }

  function renderMlStatus(ml, mlProfileNames) {
    if (!ml) return;
    mlStatus.style.display = 'flex';
    mlStatus.classList.toggle('is-on', ml.runnable);
    mlStatus.classList.toggle('is-off', !ml.runnable);

    if (ml.runnable) {
      mlStatusBadge.textContent = ml.device.toUpperCase();
      mlStatusText.textContent =
        `The CLIP adversarial pass will run on ${ml.device}.` +
        (ml.device === 'cpu' ? ' On CPU this is slow — expect a long hash.' : '');
      return;
    }

    mlStatusBadge.textContent = 'SKIPPED';
    const list = mlProfileNames.length ? mlProfileNames.join(', ') : 'none';
    mlStatusText.textContent =
      `Unavailable here (${ml.reason}). ${list} still hash, but without the AI pass — ` +
      `use Colab for that.`;
  }

  function renderProfiles(profiles) {
    if (!profiles.length) return;
    profileGrid.innerHTML = '';

    profiles.forEach((prof) => {
      const badge = PROFILE_BADGES[prof.name] || { label: 'CUSTOM', cls: '' };
      const usesMl = Boolean(prof.uses_ml);
      const mlSkipped = usesMl && !state.mlRunnable;

      const card = document.createElement('div');
      card.className = [
        'profile-card',
        prof.name === state.hashingProfile ? 'active' : '',
        mlSkipped ? 'ml-skipped' : '',
      ].filter(Boolean).join(' ');
      card.dataset.profile = prof.name;
      card.title = mlSkipped
        ? 'This profile requests the Stage 1.5 AI pass, which is unavailable in this interpreter.'
        : '';
      card.innerHTML = `
        <div class="profile-badge-row">
          <span class="profile-name">${prof.name}${usesMl ? '<span class="profile-uses-ml">AI</span>' : ''}</span>
          <span class="badge ${badge.cls}">${badge.label}</span>
        </div>
        <p class="profile-info">${prof.description || 'Custom V7 content hashing profile.'}</p>
      `;
      card.addEventListener('click', () => {
        profileGrid.querySelectorAll('.profile-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        state.hashingProfile = card.dataset.profile;
        refreshStaleState();
      });
      profileGrid.appendChild(card);
    });
  }

  hashingToggle.addEventListener('change', () => {
    state.hashingEnabled = hashingToggle.checked;
    state.clipIsHashed = false;
    hashingControlsWrap.classList.toggle('disabled-wrap', !state.hashingEnabled);
    updateHashButton();
    refreshStaleState();
  });

  function updateHashButton() {
    const ready = Boolean(state.currentFile) && state.engineAvailable && state.hashingEnabled;
    btnRunHashing.disabled = !ready;
    btnRunHashing.classList.toggle('is-ready', ready && !state.hashResult);

    if (!state.currentFile) {
      btnRunHashingLabel.textContent = 'Run Content Hashing';
      hashHint.textContent = 'Load a video first, then run the hashing pass here.';
    } else if (!state.engineAvailable) {
      btnRunHashingLabel.textContent = 'Hash Engine Unavailable';
      hashHint.textContent = 'Install the missing packages, then restart the studio.';
    } else if (!state.hashingEnabled && state.clipIsHashed) {
      btnRunHashingLabel.textContent = 'Already Anti-Detected';
      hashHint.textContent = 'This clip is already hashed. Add masks/text, pick your canvas aspect, then Export. (Flip the switch on to hash again.)';
    } else if (!state.hashingEnabled) {
      btnRunHashingLabel.textContent = 'Hashing Disabled';
      hashHint.textContent = 'Turn the switch above back on to hash this video.';
    } else {
      btnRunHashingLabel.textContent = state.hashResult ? 'Re-run Content Hashing' : 'Run Content Hashing';
      hashHint.textContent = 'Runs on your cropped clip exactly as framed. The hashed clip then replaces your working clip automatically.';
    }
  }

  // --------------------------------------------------------------------------
  // Edit payload + staleness tracking
  // --------------------------------------------------------------------------
  function buildPayload(phase = 'export') {
    const trim = timeline.getTrimRange();
    const crop = canvasCropper.getNativeCoords();
    const color = colorGrading.getState();
    const masks = maskOverlay.getNativeMasks(crop);
    const textLayers = textOverlay.getNativeLayers(crop);

    const seedVal = document.getElementById('hashingSeedInput').value.trim();
    const seed = seedVal ? parseInt(seedVal, 10) : null;
    const pad = document.getElementById('hashingPadToggle').checked;

    // Hash phase: keep the cropped clip's OWN dimensions — anti-detection on
    // the clip as framed, never forced into an aspect bucket. The canvas
    // aspect + Fill/Fit choice is applied at the final export render.
    const exportCfg = phase === 'hash'
      ? { resolution: 'source', aspect: 'auto', fit: 'cover' }
      : canvasCropper.getExportConfig();

    return {
      filename: state.currentFile,
      trim_start: trim.start,
      trim_end: trim.end,
      crop: crop,
      color_grade: color,
      masks: masks,
      text_layers: textLayers,
      hashing: {
        enabled: state.hashingEnabled,
        profile: state.hashingProfile,
        seed: seed,
        pad: pad,
      },
      export: exportCfg,
    };
  }

  function currentSignature() {
    // Canvas aspect / fit / size are packaging choices applied at the final
    // render — they must not invalidate a hash of the same edits.
    const p = buildPayload('export');
    delete p.export;
    return JSON.stringify(p);
  }

  function refreshStaleState() {
    const card = document.getElementById('hashResultCard');
    const note = document.getElementById('hashStaleNote');
    if (!state.hashResult) {
      card.style.display = 'none';
      return;
    }

    const stale = state.hashedPayload !== currentSignature();
    card.style.display = 'block';
    card.classList.toggle('is-stale', stale);
    note.style.display = stale ? 'block' : 'none';
    updateExportLabel(stale);
  }

  function updateExportLabel(stale) {
    const label = document.getElementById('btnExportLabel');
    if (!state.hashResult) {
      label.textContent = 'Export Video';
    } else if (stale) {
      label.textContent = 'Re-hash to Export';
    } else {
      label.textContent = 'Export Video';
    }
  }

  function resetHashState() {
    state.hashResult = null;
    state.hashedPayload = null;
    state.pendingSignature = null;
    document.getElementById('hashResultCard').style.display = 'none';
    document.getElementById('btnDownloadHash').removeAttribute('href');
    updateExportLabel(false);
    updateHashButton();
  }

  // Any edit to the settings invalidates the stored hash, so keep the note live.
  const controlsPanel = document.getElementById('controlsPanel');
  controlsPanel.addEventListener('input', refreshStaleState);
  controlsPanel.addEventListener('change', refreshStaleState);
  // Canvas drags (crop/mask/text) and canvas/export clicks don't emit
  // input/change events - catch them so the stale badge updates instantly.
  stageCanvasContainer.addEventListener('pointerup', refreshStaleState);
  const exportResEl = document.getElementById('exportResolution');
  if (exportResEl) exportResEl.addEventListener('click', refreshStaleState);
  const canvasFitEl = document.getElementById('canvasFit');
  if (canvasFitEl) canvasFitEl.addEventListener('click', refreshStaleState);

  // --------------------------------------------------------------------------
  // The hashing step (with exact 3-stage stepper) + auto-replace of the clip
  // --------------------------------------------------------------------------
  const exportModal = document.getElementById('exportModal');
  const modalProcessing = document.getElementById('modalProcessingState');
  const modalSuccess = document.getElementById('modalSuccessState');
  const terminalLog = document.getElementById('terminalLog');
  const modalProgressStep = document.getElementById('modalProgressStep');
  const modalStageLabel = document.getElementById('modalStageLabel');
  const modalElapsed = document.getElementById('modalElapsed');
  const exportProgressBar = document.getElementById('exportProgressBar');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const btnMinimizeModal = document.getElementById('btnMinimizeModal');
  const hashStepper = document.getElementById('hashStepper');

  function setProgress(pct) {
    if (typeof pct === 'number' && pct > 0) {
      exportProgressBar.classList.remove('indeterminate');
      exportProgressBar.style.width = `${pct}%`;
    } else {
      exportProgressBar.classList.add('indeterminate');
      exportProgressBar.style.width = '';
    }
  }

  function updateStepper(step) {
    if (!hashStepper || !step) return;
    hashStepper.querySelectorAll('.hash-step').forEach((el) => {
      const n = parseInt(el.dataset.step, 10);
      el.classList.toggle('done', step.current > n || step.label === 'Complete');
      el.classList.toggle('active', step.current === n && step.label !== 'Complete');
      if (step.label === 'Complete') el.classList.remove('active');
    });
  }

  function resetStepper() {
    if (!hashStepper) return;
    hashStepper.querySelectorAll('.hash-step').forEach((el) => {
      el.classList.remove('done', 'active');
    });
  }

  btnRunHashing.addEventListener('click', () => runHashing());
  btnCloseModal.addEventListener('click', () => {
    exportModal.style.display = 'none';
    revealHashCard();
  });

  function revealHashCard() {
    if (!state.hashResult) return;
    const card = document.getElementById('hashResultCard');
    if (card.style.display === 'none') return;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  btnMinimizeModal.addEventListener('click', () => {
    state.modalMinimized = true;
    exportModal.style.display = 'none';
    showToast('Hashing continues in the background.');
  });

  document.getElementById('btnPreviewHash').addEventListener('click', () => {
    if (!state.hashResult) return;
    showSuccessModal(state.hashResult, 'Hashed Preview', 'This is the hashed file. Export it when you are happy.');
  });

  function openProcessingModal(title, subtitle) {
    exportModal.style.display = 'flex';
    modalProcessing.style.display = 'flex';
    modalSuccess.style.display = 'none';
    state.modalMinimized = false;
    document.getElementById('modalProcessingTitle').textContent = title;
    modalProgressStep.textContent = subtitle;
    modalStageLabel.textContent = 'Queued';
    modalElapsed.textContent = '0.0s';
    setProgress(null);
    resetStepper();
    terminalLog.innerHTML = '';
  }

  async function runHashing() {
    if (!state.currentFile) {
      showToast('Load a video first.', 'error');
      return;
    }
    if (!state.engineAvailable) {
      showToast('Hash engine unavailable — run: pip install -r requirements.txt', 'error');
      return;
    }

    video.pause();
    timeline.setPlaying(false);

    openProcessingModal('Hashing Your Video', 'Starting the v7 hashing engine...');
    btnRunHashing.classList.add('is-running');
    btnRunHashingLabel.textContent = 'Hashing...';

    // Hash phase payload: cropped clip at its OWN size, no aspect forcing.
    const payload = buildPayload('hash');

    try {
      const res = await fetch('/api/hash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not start the hashing job.');

      state.jobId = data.job_id;
      state.logCount = 0;
      state.pendingSignature = currentSignature();
      appendLog(`[INIT] Job ${data.job_id} started — profile ${payload.hashing.profile}`, 'info');
      startPolling();
    } catch (err) {
      endHashingUi();
      exportModal.style.display = 'none';
      showToast(err.message, 'error');
    }
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = setInterval(pollJob, 800);
    pollJob();
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function pollJob() {
    if (!state.jobId) return;
    try {
      const res = await fetch(`/api/hash/${state.jobId}?since=${state.logCount}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lost track of the hashing job.');

      (data.logs || []).forEach(line => appendLog(line, logClass(line)));
      state.logCount = data.log_total;

      modalStageLabel.textContent = data.stage || 'Working...';
      modalElapsed.textContent = `${data.elapsed.toFixed(1)}s`;
      modalProgressStep.textContent = data.stage || 'Working...';
      setProgress(data.progress);
      updateStepper(data.step);

      if (data.status === 'done') {
        stopPolling();
        onHashComplete(data.result);
      } else if (data.status === 'error') {
        stopPolling();
        onHashFailed(data.error);
      }
    } catch (err) {
      stopPolling();
      onHashFailed(err.message);
    }
  }

  function logClass(line) {
    if (line.startsWith('[ERR]') || line.includes('[ERR]')) return 'error';
    if (line.startsWith('[!]')) return 'warn';
    if (line.startsWith('[OK]') || line.includes('[SUCCESS]') || line.startsWith('[STAGE')) return 'ok';
    return 'info';
  }

  function appendLog(line, cls) {
    const div = document.createElement('div');
    div.className = `log-line ${cls}`;
    div.textContent = line;
    terminalLog.appendChild(div);
    while (terminalLog.childElementCount > 300) {
      terminalLog.removeChild(terminalLog.firstElementChild);
    }
    terminalLog.scrollTop = terminalLog.scrollHeight;
  }

  function onHashComplete(result) {
    endHashingUi();
    if (!result) {
      onHashFailed('The pipeline finished without producing a file.');
      return;
    }

    state.hashResult = result;
    state.hashedPayload = state.pendingSignature || currentSignature();

    document.getElementById('hashResProfile').textContent = result.profile_used;
    document.getElementById('hashResDims').textContent = `${result.width} × ${result.height}`;
    document.getElementById('hashResDuration').textContent = `${result.duration}s`;
    document.getElementById('hashResSize').textContent = `${result.size_mb} MB`;
    document.getElementById('hashResultBadge').textContent = result.hash_changed ? 'CHANGED' : 'SAME';

    document.getElementById('btnDownloadHash').href = result.download_url;
    document.getElementById('btnDownloadHash').setAttribute('download', result.file_name);

    refreshStaleState();
    updateHashButton();
    loadStorage();

    showSuccessModal(
      result,
      'Hashing Complete',
      result.hash_changed
        ? 'Anti-detected clip is now loaded in the studio — keep editing or export.'
        : 'Hashing finished, but the file hash did not change — try a stronger profile.'
    );
    showToast('Content hashing complete!', 'success');

    // Auto-replace: the anti-detected clip becomes the studio's working clip.
    autoAdopt(result);
  }

  /**
   * Swap the studio's working clip to the freshly hashed file, so the user
   * keeps editing (canvas aspect, masks, text) on the ANTI-DETECTED clip and
   * exports from it — no manual download/re-upload.
   */
  async function autoAdopt(result) {
    try {
      const res = await fetch('/api/adopt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: result.file_name }),
      });
      const meta = await res.json();
      if (!res.ok) throw new Error(meta.detail || 'adopt failed');

      meta.clipIsHashed = true;
      loadVideoIntoStudio(meta);

      // Fresh edits on the new clip.
      colorGrading.reset();
      maskOverlay.clearAll();
      while (textOverlay.layers.length > 0) {
        textOverlay.activeLayerId = textOverlay.layers[0].id;
        textOverlay.deleteActive();
      }

      // This clip is already anti-detected — skip re-hashing by default.
      state.clipIsHashed = true;
      state.hashingEnabled = false;
      hashingToggle.checked = false;
      hashingControlsWrap.classList.add('disabled-wrap');
      updateHashButton();
      loadStorage();
      showToast('Anti-detected clip loaded into the studio — pick your canvas aspect, add masks/text, then Export.', 'success');
    } catch (e) {
      // Fallback: keep the old clip; the hashed file is still in the result card.
      showToast(`Hashed file is ready in the result card (auto-load failed: ${e.message})`, 'error');
    }
  }

  function onHashFailed(message) {
    endHashingUi();
    exportModal.style.display = 'none';
    showToast(`Hashing failed: ${message}`, 'error');
  }

  function endHashingUi() {
    state.jobId = null;
    btnRunHashing.classList.remove('is-running');
    updateHashButton();
  }

  // --------------------------------------------------------------------------
  // Export
  // --------------------------------------------------------------------------
  const btnExport = document.getElementById('btnExportVideo');
  btnExport.addEventListener('click', () => startExport());

  async function startExport() {
    if (!state.currentFile) {
      showToast('Please load a video first before exporting!', 'error');
      return;
    }

    video.pause();
    timeline.setPlaying(false);

    if (state.hashingEnabled && !state.clipIsHashed && state.hashedPayload !== currentSignature()) {
      showToast('Your edits changed since hashing — run Content Hashing again.', 'error');
      document.getElementById('tabBtnHashing').click();
      btnRunHashing.classList.add('is-ready');
      return;
    }

    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload('export')),
      });
      const data = await res.json();

      if (res.status === 409) {
        showToast('Run Content Hashing first, then export.', 'error');
        document.getElementById('tabBtnHashing').click();
        return;
      }
      if (!res.ok) throw new Error(data.detail || 'Export failed.');

      showSuccessModal(
        data,
        'Export Complete!',
        data.reused
          ? 'This is your hashed video, ready for upload.'
          : 'Your video is rendered and ready for upload.'
      );
      showToast('Video exported!', 'success');
    } catch (err) {
      showToast(`Export Error: ${err.message}`, 'error');
    }
  }

  function showSuccessModal(result, title, subtitle) {
    exportModal.style.display = 'flex';
    modalProcessing.style.display = 'none';
    modalSuccess.style.display = 'flex';

    document.getElementById('modalSuccessTitle').textContent = title;
    document.getElementById('modalSuccessSubtitle').textContent = subtitle;

    document.getElementById('resHashStatus').textContent = result.hash_changed ? 'CHANGED' : 'SAME';
    document.getElementById('resProfileUsed').textContent = result.profile_used;
    document.getElementById('resDimensions').textContent = `${result.width} × ${result.height}`;
    document.getElementById('resDuration').textContent = `${result.duration}s`;
    document.getElementById('resFileSize').textContent = `${result.size_mb} MB`;

    const outVideo = document.getElementById('modalOutputVideo');
    outVideo.src = result.stream_url;
    outVideo.load();

    const btnDownload = document.getElementById('btnDownloadExport');
    btnDownload.href = result.download_url;
    btnDownload.setAttribute('download', result.file_name);
  }

  // --------------------------------------------------------------------------
  // Reset All Button
  // --------------------------------------------------------------------------
  const btnResetAll = document.getElementById('btnResetAll');
  btnResetAll.addEventListener('click', () => {
    if (!confirm('Reset all edits, crop, color grading, masks, and text overlays?')) return;
    colorGrading.reset();
    canvasCropper.resetToFull();
    maskOverlay.clearAll();
    document.querySelectorAll('#exportResolution .export-size-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.res === '1080p');
    });
    document.querySelectorAll('#canvasFit .mode-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.fit === 'cover');
    });
    canvasCropper.exportFit = 'cover';
    canvasCropper.updateBadge();
    while (textOverlay.layers.length > 0) {
      textOverlay.activeLayerId = textOverlay.layers[0].id;
      textOverlay.deleteActive();
    }
    if (state.meta) {
      timeline.inPoint = 0;
      timeline.outPoint = state.meta.duration;
      timeline.updateDOM();
    }
    refreshStaleState();
    showToast('All parameters reset to defaults.');
  });

  // --------------------------------------------------------------------------
  // Storage
  // --------------------------------------------------------------------------
  const storageUploadsList = document.getElementById('storageUploadsList');
  const storageOutputsList = document.getElementById('storageOutputsList');
  const storageUploadsTotal = document.getElementById('storageUploadsTotal');
  const storageOutputsTotal = document.getElementById('storageOutputsTotal');
  const storageUploadsCount = document.getElementById('storageUploadsCount');
  const storageOutputsCount = document.getElementById('storageOutputsCount');

  document.getElementById('btnStorageRefresh').addEventListener('click', loadStorage);

  async function loadStorage() {
    try {
      const res = await fetch('/api/storage');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not read storage.');

      const inUse = new Set(data.in_use || []);
      storageUploadsTotal.textContent = `${data.uploads_total_mb} MB`;
      storageOutputsTotal.textContent = `${data.outputs_total_mb} MB`;
      storageUploadsCount.textContent = `(${(data.uploads || []).length})`;
      storageOutputsCount.textContent = `(${(data.outputs || []).length})`;

      renderStorageList(storageUploadsList, data.uploads || [], 'uploads', inUse);
      renderStorageList(storageOutputsList, data.outputs || [], 'outputs', inUse);
    } catch (err) {
      showToast(`Storage: ${err.message}`, 'error');
    }
  }

  function renderStorageList(container, items, kind, inUse) {
    container.innerHTML = '';
    if (!items.length) {
      container.innerHTML = '<div class="storage-empty">Nothing yet.</div>';
      return;
    }

    items.forEach((item) => {
      const used = kind === 'outputs' && inUse.has(item.name);
      const row = document.createElement('div');
      row.className = `storage-row${used ? ' is-in-use' : ''}`;
      row.innerHTML = `
        <span class="name" title="${item.name}">${item.name}</span>
        ${used ? '<span class="in-use-tag">IN USE</span>' : ''}
        <span class="size">${item.size_mb} MB</span>
        <button class="storage-del" title="Delete this file">&times;</button>
      `;
      row.querySelector('.storage-del').addEventListener('click', () => {
        deleteStorageItem(kind, item.name, item.size_mb, used);
      });
      container.appendChild(row);
    });
  }

  async function deleteStorageItem(kind, name, sizeMb, inUse) {
    const extra = inUse
      ? '\n\nThis file backs your current hashed result. Deleting it means you must\nre-hash before you can export.'
      : '';
    if (!confirm(`Delete this file permanently?\n\n${name}  (${sizeMb} MB)${extra}`)) return;

    try {
      const res = await fetch(`/api/storage/${kind}/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Delete failed.');

      showToast(`Deleted ${name} — freed ${data.freed_mb} MB`, 'success');
      if (inUse) resetHashState();
      if (kind === 'uploads' && name === state.currentFile) clearLoadedVideo();
      loadStorage();
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'error');
    }
  }

  async function clearStorage(kind, label, total) {
    const loadedNote = kind === 'uploads'
      ? '\n\nThis includes the video currently loaded in the studio.'
      : '';
    if (!confirm(
      `Delete ALL ${label} permanently?\n\n` +
      `Every file in the ${label} folder will be removed (${total}).${loadedNote}\n\n` +
      `This cannot be undone.`
    )) return;

    try {
      const res = await fetch('/api/storage/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, older_than_hours: 0 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Clear failed.');

      showToast(`Removed ${data.deleted_count} file(s) — freed ${data.freed_mb} MB`, 'success');
      if (kind === 'outputs') resetHashState();
      if (kind === 'uploads' || (data.deleted || []).includes(state.currentFile)) {
        clearLoadedVideo();
      }
      loadStorage();
    } catch (err) {
      showToast(`Clear failed: ${err.message}`, 'error');
    }
  }

  document.getElementById('btnClearOutputs')
    .addEventListener('click', () => clearStorage('outputs', 'outputs', storageOutputsTotal.textContent));
  document.getElementById('btnClearUploads')
    .addEventListener('click', () => clearStorage('uploads', 'uploads', storageUploadsTotal.textContent));

  function clearLoadedVideo() {
    state.currentFile = null;
    state.meta = null;
    state.clipIsHashed = false;
    video.pause();
    video.removeAttribute('src');
    video.load();
    stageEmptyState.style.display = 'flex';
    stageCanvasContainer.style.display = 'none';
    mediaMetaPill.style.display = 'none';
    resetHashState();
    updateHashButton();
  }

  // --------------------------------------------------------------------------
  // Toast Helper
  // --------------------------------------------------------------------------
  function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'toast-error' : ''}`;
    toast.innerHTML = `
      <span>${type === 'error' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️'}</span>
      <span>${msg}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Boot
  loadEngineConfig();
  updateHashButton();
  loadStorage();
});
