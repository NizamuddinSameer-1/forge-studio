// ==========================================================================
// INTERACTIVE CANVAS CROPPER & ASPECT RATIO MANAGER (v2.3)
// Confirm Crop applies the crop to the stage. Canvas Aspect control applies
// a ratio (9:16 etc.) to the whole canvas, Fill (crop) or Fit (blur bars).
// ==========================================================================

const EXPORT_CANVASES = {
  '9:16': { '1080p': [1080, 1920], '720p': [720, 1280] },
  '4:5': { '1080p': [1080, 1350], '720p': [720, 900] },
  '1:1': { '1080p': [1080, 1080], '720p': [720, 720] },
  '4:3': { '1080p': [1440, 1080], '720p': [960, 720] },
  '16:9': { '1080p': [1920, 1080], '720p': [1280, 720] },
};
const ASPECTS = { '9:16': [9, 16], '4:5': [4, 5], '1:1': [1, 1], '4:3': [4, 3], '16:9': [16, 9] };

function evenFloor(v) { v = Math.max(2, Math.round(v)); return v - (v % 2); }

function resolveExportCanvas(cw, ch, res, aspect) {
  res = (res === '720p' || res === 'source') ? res : '1080p';
  if (res === 'source') {
    if (ASPECTS[aspect]) {
      const [rw, rh] = ASPECTS[aspect];
      const r2 = rw / rh;
      if (cw / Math.max(1, ch) > r2) return [evenFloor(cw), evenFloor(cw / r2)];
      return [evenFloor(ch * r2), evenFloor(ch)];
    }
    return [evenFloor(cw), evenFloor(ch)];
  }
  if (ASPECTS[aspect]) return EXPORT_CANVASES[aspect][res];
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
    this.fitBtns = document.querySelectorAll('#canvasFit .mode-btn');

    this.currentRatioMode = 'free';
    this.ratioValue = null;

    // Canvas & export state
    this.exportAspect = 'auto';   // 'auto' | '9:16' | '4:5' | '1:1' | '4:3' | '16:9'
    this.exportFit = 'cover';     // 'cover' (Fill/crop) | 'contain' (Fit/blur bars)

    this.box = { x: 0, y: 0, w: 100, h: 100 };

    // Confirm-crop ("applied") state
    this.applied = false;
    this.appliedBox = null;
    this.appliedFull = null;
    this.appliedScale = 1;
    this.onModeChange = null;

    this.isDragging = false;
    this.isResizing = false;
    this.activeHandle = null;
    this.dragStart = { x: 0, y: 0, boxX: 0, boxY: 0, boxW: 0, boxH: 0 };
    this.snapThreshold = 8;

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

    this.fitBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        this.fitBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.exportFit = btn.dataset.fit;
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

  /** The export/canvas config sent to the backend for the final render. */
  getExportConfig() {
    return {
      resolution: this.getExportResolution(),
      aspect: this.exportAspect,
      fit: this.exportFit,
    };
  }

  getBasis() {
    if (this.applied && this.appliedBox && this.appliedFull) {
      return {
        w: this.appliedFull.w,
        h: this.appliedFull.h,
        scale: this.appliedScale || 1,
        offX: this.appliedBox.x * (this.appliedScale || 1),
        offY: this.appliedBox.y * (this.appliedScale || 1),
        visX: this.appliedBox.x,
        visY: this.appliedBox.y,
        visW: this.appliedBox.w,
        visH: this.appliedBox.h,
      };
    }
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    return { w, h, scale: 1, offX: 0, offY: 0, visX: 0, visY: 0, visW: w, visH: h };
  }

  // -------------------------------------------------------------------------
  // Confirm crop: the cut-away area is removed from the stage for real.
  // -------------------------------------------------------------------------
  confirmCrop() {
    if (!this.video.videoWidth || this.applied) return;
    this.appliedBox = { ...this.box };
    this.appliedFull = { w: this.container.clientWidth, h: this.container.clientHeight };
    this.applied = true;
    this.cropBox.style.display = 'none';
    Object.values(this.dims).forEach(d => { d.style.display = 'none'; });
    this.hideGuides();
    if (this.onModeChange) this.onModeChange(true);
    this.updateBadge();
  }

  editCrop() {
    if (!this.applied) return;
    this.applied = false;
    this.appliedScale = 1;
    this.container.classList.remove('applied');
    this.cropBox.style.display = 'block';
    Object.values(this.dims).forEach(d => { d.style.display = 'block'; });
    if (this.onModeChange) this.onModeChange(false);
    this.updateDOM();
  }

  layoutApplied(maxW, maxH) {
    const b = this.appliedBox;
    const full = this.appliedFull;
    if (!b || !full) return;

    const aspect = b.w / b.h;
    let w = maxW;
    let h = w / aspect;
    if (h > maxH) { h = maxH; w = h * aspect; }
    w = Math.max(40, Math.round(w));
    h = Math.max(40, Math.round(h));

    this.container.style.width = `${w}px`;
    this.container.style.height = `${h}px`;
    this.container.style.overflow = 'hidden';
    this.container.classList.add('applied');

    const scale = w / b.w;
    this.appliedScale = scale;

    this.video.style.width = `${Math.round(full.w * scale)}px`;
    this.video.style.height = `${Math.round(full.h * scale)}px`;

    const t = `translate(${-b.x * scale}px, ${-b.y * scale}px)`;
    this.video.style.transformOrigin = 'top left';
    this.video.style.transform = t;
    ['maskStageLayer', 'textStageLayer'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.style.transformOrigin = 'top left';
        el.style.transform = t;
      }
    });
  }

  clearAppliedLayout() {
    this.container.classList.remove('applied');
    this.container.style.overflow = '';
    this.video.style.transform = '';
    ['maskStageLayer', 'textStageLayer'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.style.transform = '';
    });
  }

  setRatio(mode) {
    this.currentRatioMode = mode;
    const map = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9, '4:3': 4 / 3 };
    this.ratioValue = map[mode] || null;
    // The chosen preset IS the canvas aspect for the final render.
    this.exportAspect = mode === 'free' ? 'auto' : mode;

    if (this.applied) {
      // Changing ratio in applied view: jump back to editing with the new box.
      this.editCrop();
    }
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
    this.applied = false;
    this.appliedBox = null;
    this.appliedFull = null;
    this.appliedScale = 1;
    this.exportAspect = 'auto';
    this.clearAppliedLayout();
    this.cropBox.style.display = 'block';
    Object.values(this.dims).forEach(d => { d.style.display = 'block'; });
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
    if (this.applied) this.editCrop();
    this.currentRatioMode = 'free';
    this.ratioValue = null;
    this.exportAspect = 'auto';
    this.ratioCards.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'free'));
    this.box = { x: 0, y: 0, w: this.container.clientWidth, h: this.container.clientHeight };
    this.updateDOM();
    this.updateInputs();
  }

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
    if (this.applied) { this.updateBadge(); return; }
    this.cropBox.style.left = `${this.box.x}px`;
    this.cropBox.style.top = `${this.box.y}px`;
    this.cropBox.style.width = `${this.box.w}px`;
    this.cropBox.style.height = `${this.box.h}px`;

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
    const [w, h] = resolveExportCanvas(c.width, c.height, this.getExportResolution(), this.exportAspect);
    return { width: w, height: h };
  }

  updateBadge() {
    const c = this.getNativeCoords();
    if (!c) {
      this.cropBadge.textContent = this.ratioLabel();
      if (this.exportPreview) this.exportPreview.textContent = '—';
      return;
    }
    const [ew, eh] = resolveExportCanvas(c.width, c.height, this.getExportResolution(), this.exportAspect);
    const fitTag = this.exportFit === 'contain' ? ' · fit' : '';
    this.cropBadge.innerHTML =
      `${this.ratioLabel()} · ${c.width}×${c.height} → <span class="export-dims">${ew}×${eh}</span>${fitTag}`;
    if (this.exportPreview) {
      const aspectTxt = this.exportAspect === 'auto' ? 'auto aspect' : this.exportAspect;
      this.exportPreview.textContent = `${ew} × ${eh} · ${aspectTxt}${fitTag}`;
    }
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
    const basis = this.getBasis();
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    const scaleX = basis.w / nw;
    const scaleY = basis.h / nh;

    this.box.w = (parseInt(this.inputW.value) || 100) * scaleX;
    this.box.h = (parseInt(this.inputH.value) || 100) * scaleY;
    this.box.x = (parseInt(this.inputX.value) || 0) * scaleX;
    this.box.y = (parseInt(this.inputY.value) || 0) * scaleY;

    this.currentRatioMode = 'free';
    this.ratioValue = null;
    this.ratioCards.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'free'));
    if (this.applied) this.editCrop();
    this.updateDOM();
  }

  /**
   * Exact pixel crop coordinates in native video space for FFmpeg crop=w:h:x:y.
   * Works in both editing and applied (confirmed) mode.
   */
  getNativeCoords() {
    const nw = this.video.videoWidth;
    const nh = this.video.videoHeight;
    const basis = this.getBasis();

    if (!nw || !nh || !basis.w || !basis.h) return null;

    const scaleX = nw / basis.w;
    const scaleY = nh / basis.h;
    const box = (this.applied && this.appliedBox) ? this.appliedBox : this.box;

    let x = Math.round(box.x * scaleX);
    let y = Math.round(box.y * scaleY);
    let width = Math.round(box.w * scaleX);
    let height = Math.round(box.h * scaleY);

    width = Math.max(2, width - (width % 2));
    height = Math.max(2, height - (height % 2));
    x = Math.max(0, Math.min(nw - width, x - (x % 2)));
    y = Math.max(0, Math.min(nh - height, y - (y % 2)));

    return { enabled: true, x, y, width, height };
  }
}

window.CanvasCropper = CanvasCropper;
