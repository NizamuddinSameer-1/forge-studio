// ==========================================================================
// INTERACTIVE CANVAS CROPPER & ASPECT RATIO MANAGER (v2.1)
// CapCut-style: dimmed cut-away regions, center/edge snapping with guides,
// anchored 8-handle resize, preset auto-center, live exact-export badge.
// ==========================================================================

const EXPORT_CANVASES = {
  '9:16': { '1080p': [1080, 1920], '720p': [720, 1280] },
  '4:5': { '1080p': [1080, 1350], '720p': [720, 900] },
  '1:1': { '1080p': [1080, 1080], '720p': [720, 720] },
  '4:3': { '1080p': [1440, 1080], '720p': [960, 720] },
  '16:9': { '1080p': [1920, 1080], '720p': [1280, 720] },
};

function resolveExportCanvas(cw, ch, res) {
  if (res === 'source') return [Math.max(2, cw - (cw % 2)), Math.max(2, ch - (ch % 2))];
  if (res !== '1080p' && res !== '720p') res = '1080p';
  const r = cw / Math.max(1, ch);
  let bucket;
  if (r < 0.65) bucket = '9:16';
  else if (r < 0.90) bucket = '4:5';
  else if (r < 1.15) bucket = '1:1';
  else if (r < 1.50) bucket = '4:3';
  else bucket = '16:9';
  return EXPORT_CANVASES[bucket][res];
}

class CanvasCropper {
  constructor(container, videoElement) {
    this.container = container;
    this.video = videoElement;

    this.cropBox = document.getElementById('cropBox');
    this.cropBadge = document.getElementById('cropBadge');
    this.ratioCards = document.querySelectorAll('.ratio-card');

    this.inputW = document.getElementById('cropWidthInput');
    this.inputH = document.getElementById('cropHeightInput');
    this.inputX = document.getElementById('cropXInput');
    this.inputY = document.getElementById('cropYInput');

    this.btnCenter = document.getElementById('btnCenterCrop');
    this.btnReset = document.getElementById('btnResetCrop');

    this.exportBtns = document.querySelectorAll('#exportResolution .export-size-btn');
    this.exportPreview = document.getElementById('cropExportPreview');

    this.currentRatioMode = 'free';
    this.ratioValue = null;

    // Crop box in container pixel space: { x, y, w, h }
    this.box = { x: 0, y: 0, w: 100, h: 100 };

    this.isDragging = false;
    this.isResizing = false;
    this.activeHandle = null;
    this.dragStart = { x: 0, y: 0, boxX: 0, boxY: 0, boxW: 0, boxH: 0 };
    this.snapThreshold = 8;

    // Dimmed cut-away regions + center snap guides (built here so the HTML
    // stays lean).
    this.dims = {};
    ['top', 'bottom', 'left', 'right'].forEach((k) => {
      const el = document.createElement('div');
      el.className = 'crop-dim';
      el.style.display = 'none';
      container.appendChild(el);
      this.dims[k] = el;
    });
    this.guideV = document.createElement('div');
    this.guideV.className = 'crop-guide v';
    this.guideH = document.createElement('div');
    this.guideH.className = 'crop-guide h';
    container.appendChild(this.guideV);
    container.appendChild(this.guideH);

    this.initEvents();
  }

  initEvents() {
    this.ratioCards.forEach((card) => {
      card.addEventListener('click', () => {
        this.ratioCards.forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        this.setRatio(card.dataset.ratio);
      });
    });

    this.exportBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        this.exportBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.updateBadge();
      });
    });

    this.cropBox.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('handle')) return;
      this.isDragging = true;
      this.dragStart = {
        x: e.clientX, y: e.clientY,
        boxX: this.box.x, boxY: this.box.y,
        boxW: this.box.w, boxH: this.box.h,
      };
      this.cropBox.setPointerCapture(e.pointerId);
      e.stopPropagation();
    });

    this.cropBox.querySelectorAll('.handle').forEach((handle) => {
      handle.addEventListener('pointerdown', (e) => {
        this.isResizing = true;
        this.activeHandle = handle.dataset.handle;
        this.dragStart = {
          x: e.clientX, y: e.clientY,
          boxX: this.box.x, boxY: this.box.y,
          boxW: this.box.w, boxH: this.box.h,
        };
        handle.setPointerCapture(e.pointerId);
        e.stopPropagation();
      });
    });

    window.addEventListener('pointermove', (e) => {
      if (this.isDragging) this.onDrag(e);
      else if (this.isResizing) this.onResize(e);
    });

    window.addEventListener('pointerup', () => {
      if (this.isDragging || this.isResizing) {
        this.isDragging = false;
        this.isResizing = false;
        this.activeHandle = null;
        this.hideGuides();
        this.updateInputs();
      }
    });

    [this.inputW, this.inputH, this.inputX, this.inputY].forEach((inp) => {
      inp.addEventListener('change', () => this.onManualInputChange());
    });

    if (this.btnCenter) this.btnCenter.addEventListener('click', () => this.centerCrop());
    if (this.btnReset) this.btnReset.addEventListener('click', () => this.resetToFull());
  }

  getExportResolution() {
    const active = document.querySelector('#exportResolution .export-size-btn.active');
    return active ? active.dataset.res : '1080p';
  }

  setRatio(mode) {
    this.currentRatioMode = mode;
    const map = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9, '4:3': 4 / 3 };
    this.ratioValue = map[mode] || null;

    // CapCut behavior: picking a preset drops in the largest centered box of
    // that ratio, ready to drag.
    if (this.ratioValue) {
      this.fitRatioCentered();
    }
    this.updateDOM();
    this.updateInputs();
  }

  fitRatioCentered() {
    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;
    let w = maxW * 0.92;
    let h = w / this.ratioValue;
    if (h > maxH * 0.92) {
      h = maxH * 0.92;
      w = h * this.ratioValue;
    }
    this.box.w = Math.max(30, w);
    this.box.h = Math.max(30, h);
    this.box.x = (maxW - this.box.w) / 2;
    this.box.y = (maxH - this.box.h) / 2;
  }

  onVideoLoaded() {
    if (this.container.clientWidth <= 0 || this.container.clientHeight <= 0) return;
    this.cropBox.style.display = 'block';
    Object.values(this.dims).forEach(d => { d.style.display = 'block'; });
    // Start on the full frame: never silently crop a video the user just loaded.
    this.resetToFull();
  }

  centerCrop() {
    if (this.ratioValue) this.fitRatioCentered();
    else {
      const maxW = this.container.clientWidth;
      const maxH = this.container.clientHeight;
      this.box.w = maxW * 0.8;
      this.box.h = maxH * 0.8;
      this.box.x = (maxW - this.box.w) / 2;
      this.box.y = (maxH - this.box.h) / 2;
    }
    this.updateDOM();
    this.updateInputs();
  }

  resetToFull() {
    this.currentRatioMode = 'free';
    this.ratioValue = null;
    this.ratioCards.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'free'));
    this.box = { x: 0, y: 0, w: this.container.clientWidth, h: this.container.clientHeight };
    this.updateDOM();
    this.updateInputs();
  }

  // Snap helpers: edges (0 / max) and center, threshold in container px.
  snapAxis(pos, size, max) {
    const targets = [0, (max - size) / 2, max - size];
    for (const t of targets) {
      if (Math.abs(pos - t) <= this.snapThreshold) return { pos: t, snapped: t === (max - size) / 2 ? 'center' : 'edge' };
    }
    return { pos, snapped: null };
  }

  onDrag(e) {
    const dx = e.clientX - this.dragStart.x;
    const dy = e.clientY - this.dragStart.y;
    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;

    let newX = this.dragStart.boxX + dx;
    let newY = this.dragStart.boxY + dy;

    const sx = this.snapAxis(newX, this.box.w, maxW);
    const sy = this.snapAxis(newY, this.box.h, maxH);
    newX = sx.pos;
    newY = sy.pos;

    this.guideV.style.display = sx.snapped === 'center' ? 'block' : 'none';
    this.guideV.style.left = `${maxW / 2}px`;
    this.guideH.style.display = sy.snapped === 'center' ? 'block' : 'none';
    this.guideH.style.top = `${maxH / 2}px`;

    this.box.x = Math.max(0, Math.min(maxW - this.box.w, newX));
    this.box.y = Math.max(0, Math.min(maxH - this.box.h, newY));
    this.updateDOM();
  }

  onResize(e) {
    const dx = e.clientX - this.dragStart.x;
    const dy = e.clientY - this.dragStart.y;
    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;

    const { boxX, boxY, boxW, boxH } = this.dragStart;
    const h = this.activeHandle;

    // Anchored resize: the opposite corner/edge stays put (CapCut feel).
    let newX = boxX, newY = boxY, newW = boxW, newH = boxH;

    if (h.includes('e')) newW = boxW + dx;
    if (h.includes('w')) { newW = boxW - dx; newX = boxX + dx; }
    if (h.includes('s')) newH = boxH + dy;
    if (h.includes('n')) { newH = boxH - dy; newY = boxY + dy; }

    if (this.ratioValue) {
      if (h === 'e' || h === 'w') {
        newH = newW / this.ratioValue;
        newY = boxY + (boxH - newH) / 2;
      } else if (h === 'n' || h === 's') {
        newW = newH * this.ratioValue;
        newX = boxX + (boxW - newW) / 2;
      } else {
        if (Math.abs(dx) > Math.abs(dy)) {
          newH = newW / this.ratioValue;
          if (h.includes('n')) newY = boxY + boxH - newH;
        } else {
          newW = newH * this.ratioValue;
          if (h.includes('w')) newX = boxX + boxW - newW;
        }
      }
    }

    if (newW < 20 || newH < 20) return;
    if (newX < 0) { newW += newX; newX = 0; }
    if (newY < 0) { newH += newY; newY = 0; }
    if (newX + newW > maxW) newW = maxW - newX;
    if (newY + newH > maxH) newH = maxH - newY;

    this.box = { x: newX, y: newY, w: newW, h: newH };
    this.updateDOM();
  }

  hideGuides() {
    this.guideV.style.display = 'none';
    this.guideH.style.display = 'none';
  }

  updateDOM() {
    this.cropBox.style.left = `${this.box.x}px`;
    this.cropBox.style.top = `${this.box.y}px`;
    this.cropBox.style.width = `${this.box.w}px`;
    this.cropBox.style.height = `${this.box.h}px`;

    // Dimmed cut-away: exactly what will be cropped off.
    const cw = this.container.clientWidth;
    const ch = this.container.clientHeight;
    Object.assign(this.dims.top.style, { left: '0px', top: '0px', width: `${cw}px`, height: `${this.box.y}px` });
    Object.assign(this.dims.bottom.style, { left: '0px', top: `${this.box.y + this.box.h}px`, width: `${cw}px`, height: `${Math.max(0, ch - this.box.y - this.box.h)}px` });
    Object.assign(this.dims.left.style, { left: '0px', top: `${this.box.y}px`, width: `${this.box.x}px`, height: `${this.box.h}px` });
    Object.assign(this.dims.right.style, { left: `${this.box.x + this.box.w}px`, top: `${this.box.y}px`, width: `${Math.max(0, cw - this.box.x - this.box.w)}px`, height: `${this.box.h}px` });

    this.updateBadge();
  }

  ratioLabel() {
    return this.currentRatioMode === 'free' ? 'Custom' : this.currentRatioMode;
  }

  getExportCanvas() {
    const c = this.getNativeCoords();
    if (!c) return null;
    const [w, h] = resolveExportCanvas(c.width, c.height, this.getExportResolution());
    return { width: w, height: h };
  }

  /**
   * Show BOTH the crop size and the exact export canvas, so the size on the
   * badge is the size the downloaded file will have. No more surprise rescale.
   */
  updateBadge() {
    const c = this.getNativeCoords();
    if (!c) {
      this.cropBadge.textContent = this.ratioLabel();
      if (this.exportPreview) this.exportPreview.textContent = '—';
      return;
    }
    const [ew, eh] = resolveExportCanvas(c.width, c.height, this.getExportResolution());
    this.cropBadge.innerHTML =
      `${this.ratioLabel()} · ${c.width}×${c.height} → <span class="export-dims">${ew}×${eh}</span>`;
    if (this.exportPreview) this.exportPreview.textContent = `${ew} × ${eh}`;
  }

  updateInputs() {
    const c = this.getNativeCoords();
    if (!c) return;
    this.inputW.value = c.width;
    this.inputH.value = c.height;
    this.inputX.value = c.x;
    this.inputY.value = c.y;
  }

  onManualInputChange() {
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    const scaleX = this.container.clientWidth / nw;
    const scaleY = this.container.clientHeight / nh;

    this.box.w = (parseInt(this.inputW.value) || 100) * scaleX;
    this.box.h = (parseInt(this.inputH.value) || 100) * scaleY;
    this.box.x = (parseInt(this.inputX.value) || 0) * scaleX;
    this.box.y = (parseInt(this.inputY.value) || 0) * scaleY;

    this.currentRatioMode = 'free';
    this.ratioValue = null;
    this.ratioCards.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'free'));
    this.updateDOM();
  }

  /**
   * Exact pixel crop coordinates in native video space for FFmpeg crop=w:h:x:y
   */
  getNativeCoords() {
    const nw = this.video.videoWidth;
    const nh = this.video.videoHeight;
    const cw = this.container.clientWidth;
    const ch = this.container.clientHeight;

    if (!nw || !nh || !cw || !ch) return null;

    const scaleX = nw / cw;
    const scaleY = nh / ch;

    let x = Math.round(this.box.x * scaleX);
    let y = Math.round(this.box.y * scaleY);
    let width = Math.round(this.box.w * scaleX);
    let height = Math.round(this.box.h * scaleY);

    width = Math.max(2, width - (width % 2));
    height = Math.max(2, height - (height % 2));
    x = Math.max(0, Math.min(nw - width, x - (x % 2)));
    y = Math.max(0, Math.min(nh - height, y - (y % 2)));

    return { enabled: true, x, y, width, height };
  }
}

window.CanvasCropper = CanvasCropper;
