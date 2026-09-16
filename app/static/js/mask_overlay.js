// ==========================================================================
// MASK MANAGER (v2.2) - unlimited blur / pixelate boxes
// Basis-aware: renders & converts correctly while the crop is applied too.
// ==========================================================================

class MaskOverlayManager {
  constructor(container, videoElement, getBasis) {
    this.container = container;
    this.video = videoElement;
    this.getBasis = getBasis || (() => ({
      w: container.clientWidth, h: container.clientHeight,
      scale: 1, offX: 0, offY: 0,
      visX: 0, visY: 0, visW: container.clientWidth, visH: container.clientHeight,
    }));
    this.stageLayer = document.getElementById('maskStageLayer');

    this.editor = document.getElementById('maskEditor');
    this.layersList = document.getElementById('maskLayersList');
    this.btnAdd = document.getElementById('btnAddMask');
    this.btnDelete = document.getElementById('btnDeleteMask');
    this.modeBtns = document.querySelectorAll('#maskMode .mode-btn');
    this.sliderBlur = document.getElementById('sliderMaskBlur');
    this.valBlur = document.getElementById('valMaskBlur');
    this.inputW = document.getElementById('maskWidthInput');
    this.inputH = document.getElementById('maskHeightInput');
    this.inputX = document.getElementById('maskXInput');
    this.inputY = document.getElementById('maskYInput');
    this.btnTR = document.getElementById('btnMaskTopRight');
    this.btnBR = document.getElementById('btnMaskBottomRight');
    this.btnTL = document.getElementById('btnMaskTopLeft');
    this.btnBL = document.getElementById('btnMaskBottomLeft');

    this.masks = [];
    this.activeId = null;
    this.counter = 1;

    this.initEvents();
  }

  get enabled() {
    return this.masks.length > 0;
  }

  initEvents() {
    this.btnAdd.addEventListener('click', () => this.addMask());
    this.btnDelete.addEventListener('click', () => this.deleteActive());

    this.modeBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const m = this.getActive();
        if (!m) return;
        m.mode = btn.dataset.mode;
        this.modeBtns.forEach(b => b.classList.toggle('active', b === btn));
        this.updateBoxDOM(m);
        this.renderList();
      });
    });

    this.sliderBlur.addEventListener('input', (e) => {
      const m = this.getActive();
      if (!m) return;
      m.blur = parseInt(e.target.value);
      this.valBlur.textContent = `${m.blur} px`;
      this.updateBoxDOM(m);
    });

    [this.inputW, this.inputH, this.inputX, this.inputY].forEach((inp) => {
      inp.addEventListener('change', () => this.onManualInput());
    });

    if (this.btnTR) this.btnTR.addEventListener('click', () => this.setPosition('tr'));
    if (this.btnBR) this.btnBR.addEventListener('click', () => this.setPosition('br'));
    if (this.btnTL) this.btnTL.addEventListener('click', () => this.setPosition('tl'));
    if (this.btnBL) this.btnBL.addEventListener('click', () => this.setPosition('bl'));
  }

  addMask() {
    const b = this.getBasis();
    const mask = {
      id: `mask_${this.counter++}`,
      x: Math.round(b.visX + b.visW * 0.32),
      y: Math.round(b.visY + b.visH * 0.06),
      w: Math.round(b.visW * 0.36),
      h: Math.max(28, Math.round(b.visH * 0.07)),
      blur: 20,
      mode: 'blur',
      enabled: true,
    };
    mask.el = this.createBoxElement(mask);
    this.masks.push(mask);
    this.selectMask(mask.id);
    this.renderList();
  }

  createBoxElement(mask) {
    const el = document.createElement('div');
    el.className = 'mask-box';
    el.dataset.maskId = mask.id;

    const tag = document.createElement('div');
    tag.className = 'mask-box-tag';
    el.appendChild(tag);

    ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].forEach((h) => {
      const hd = document.createElement('div');
      hd.className = 'mask-handle';
      hd.dataset.handle = h;
      el.appendChild(hd);
      hd.addEventListener('pointerdown', (e) => this.startResize(e, mask, h));
    });

    el.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('mask-handle')) return;
      this.selectMask(mask.id);
      this.startDrag(e, mask);
    });

    this.stageLayer.appendChild(el);
    this.updateBoxDOM(mask);
    return el;
  }

  startDrag(e, mask) {
    e.stopPropagation();
    const b = this.getBasis();
    const sc = b.scale || 1;
    const start = { x: e.clientX, y: e.clientY, boxX: mask.x, boxY: mask.y };
    const move = (ev) => {
      mask.x = Math.max(b.visX, Math.min(b.visX + b.visW - mask.w, start.boxX + (ev.clientX - start.x) / sc));
      mask.y = Math.max(b.visY, Math.min(b.visY + b.visH - mask.h, start.boxY + (ev.clientY - start.y) / sc));
      this.updateBoxDOM(mask);
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      this.updateInputs();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  startResize(e, mask, handle) {
    e.stopPropagation();
    const b = this.getBasis();
    const sc = b.scale || 1;
    const start = { x: e.clientX, y: e.clientY, boxX: mask.x, boxY: mask.y, boxW: mask.w, boxH: mask.h };
    const move = (ev) => {
      const dx = (ev.clientX - start.x) / sc;
      const dy = (ev.clientY - start.y) / sc;

      let { boxX: x, boxY: y, boxW: w, boxH: h } = start;
      if (handle.includes('e')) w = start.boxW + dx;
      if (handle.includes('s')) h = start.boxH + dy;
      if (handle.includes('w')) { w = start.boxW - dx; x = start.boxX + dx; }
      if (handle.includes('n')) { h = start.boxH - dy; y = start.boxY + dy; }

      if (w < 20 || h < 20) return;
      if (x < b.visX) { w -= (b.visX - x); x = b.visX; }
      if (y < b.visY) { h -= (b.visY - y); y = b.visY; }
      if (x + w > b.visX + b.visW) w = b.visX + b.visW - x;
      if (y + h > b.visY + b.visH) h = b.visY + b.visH - y;

      mask.x = x; mask.y = y; mask.w = w; mask.h = h;
      this.updateBoxDOM(mask);
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      this.updateInputs();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  updateBoxDOM(mask) {
    const el = mask.el;
    if (!el) return;
    const b = this.getBasis();
    const sc = b.scale || 1;
    el.style.left = `${mask.x * sc - b.offX}px`;
    el.style.top = `${mask.y * sc - b.offY}px`;
    el.style.width = `${mask.w * sc}px`;
    el.style.height = `${mask.h * sc}px`;
    el.style.backdropFilter = `blur(${Math.max(1, mask.blur * sc)}px)`;
    el.style.webkitBackdropFilter = `blur(${Math.max(1, mask.blur * sc)}px)`;
    el.classList.toggle('pixelate', mask.mode === 'pixelate');
    el.classList.toggle('selected', mask.id === this.activeId);
    const tag = el.querySelector('.mask-box-tag');
    if (tag) tag.textContent = mask.mode === 'pixelate' ? 'PIXELATE' : 'BLUR';
  }

  updateAllDOM() {
    this.masks.forEach((m) => this.updateBoxDOM(m));
  }

  selectMask(id) {
    this.activeId = id;
    this.masks.forEach((m) => this.updateBoxDOM(m));
    const m = this.getActive();
    this.editor.style.display = m ? 'flex' : 'none';
    if (!m) return;

    this.sliderBlur.value = m.blur;
    this.valBlur.textContent = `${m.blur} px`;
    this.modeBtns.forEach(b => b.classList.toggle('active', b.dataset.mode === m.mode));
    this.updateInputs();
    this.renderList();
  }

  getActive() {
    return this.masks.find((m) => m.id === this.activeId) || null;
  }

  deleteActive() {
    if (!this.activeId) return;
    const m = this.getActive();
    if (m && m.el) m.el.remove();
    this.masks = this.masks.filter((x) => x.id !== this.activeId);
    this.activeId = this.masks.length ? this.masks[this.masks.length - 1].id : null;
    if (this.activeId) this.selectMask(this.activeId);
    else this.editor.style.display = 'none';
    this.renderList();
  }

  clearAll() {
    this.masks.forEach((m) => m.el && m.el.remove());
    this.masks = [];
    this.activeId = null;
    this.editor.style.display = 'none';
    this.renderList();
  }

  setPosition(pos) {
    const m = this.getActive();
    if (!m) return;
    const b = this.getBasis();
    const pad = 20;
    if (pos === 'tr') { m.x = b.visX + b.visW - m.w - pad; m.y = b.visY + pad; }
    else if (pos === 'br') { m.x = b.visX + b.visW - m.w - pad; m.y = b.visY + b.visH - m.h - pad; }
    else if (pos === 'tl') { m.x = b.visX + pad; m.y = b.visY + pad; }
    else if (pos === 'bl') { m.x = b.visX + pad; m.y = b.visY + b.visH - m.h - pad; }
    this.updateBoxDOM(m);
    this.updateInputs();
  }

  updateInputs() {
    const m = this.getActive();
    if (!m) return;
    const b = this.getBasis();
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    this.inputW.value = Math.round(m.w * (nw / b.w));
    this.inputH.value = Math.round(m.h * (nh / b.h));
    this.inputX.value = Math.round(m.x * (nw / b.w));
    this.inputY.value = Math.round(m.y * (nh / b.h));
  }

  onManualInput() {
    const m = this.getActive();
    if (!m) return;
    const b = this.getBasis();
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    const scaleX = b.w / nw;
    const scaleY = b.h / nh;
    m.w = (parseInt(this.inputW.value) || 100) * scaleX;
    m.h = (parseInt(this.inputH.value) || 50) * scaleY;
    m.x = (parseInt(this.inputX.value) || 0) * scaleX;
    m.y = (parseInt(this.inputY.value) || 0) * scaleY;
    this.updateBoxDOM(m);
  }

  renderList() {
    if (!this.masks.length) {
      this.layersList.innerHTML = '<div class="empty-layers-msg">No masks yet. Click "+ Add Mask".</div>';
      return;
    }
    this.layersList.innerHTML = '';
    this.masks.forEach((m, i) => {
      const item = document.createElement('div');
      item.className = `mask-item ${m.id === this.activeId ? 'active' : ''}`;
      item.innerHTML = `
        <span class="mask-item-title">${m.mode === 'pixelate' ? '▦' : '🌫'} Mask ${i + 1}</span>
        <span class="badge">${m.mode === 'pixelate' ? 'PIXELATE' : 'BLUR'} ${m.blur}px</span>
      `;
      item.addEventListener('click', () => this.selectMask(m.id));
      this.layersList.appendChild(item);
    });
  }

  /**
   * All masks translated to native video coords, relative to the crop area
   * (the backend scales them again into the export canvas).
   */
  getNativeMasks(cropNative) {
    const nw = this.video.videoWidth;
    const nh = this.video.videoHeight;
    const b = this.getBasis();
    if (!nw || !nh || !b.w || !b.h) return [];

    const scaleX = nw / b.w;
    const scaleY = nh / b.h;
    const cropX = cropNative ? cropNative.x : 0;
    const cropY = cropNative ? cropNative.y : 0;
    const cropW = cropNative ? cropNative.width : nw;
    const cropH = cropNative ? cropNative.height : nh;

    return this.masks.map((m) => {
      let relX = Math.round(m.x * scaleX) - cropX;
      let relY = Math.round(m.y * scaleY) - cropY;
      let relW = Math.round(m.w * scaleX);
      let relH = Math.round(m.h * scaleY);

      relW = Math.max(4, Math.min(cropW, relW));
      relH = Math.max(4, Math.min(cropH, relH));
      relW -= relW % 2;
      relH -= relH % 2;
      relX = Math.max(0, Math.min(cropW - relW, relX));
      relY = Math.max(0, Math.min(cropH - relH, relY));

      return {
        id: m.id,
        enabled: true,
        x: relX,
        y: relY,
        width: relW,
        height: relH,
        blur: m.blur,
        mode: m.mode,
      };
    });
  }
}

window.MaskOverlayManager = MaskOverlayManager;
