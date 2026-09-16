// ==========================================================================
// TEXT OVERLAY & TYPOGRAPHY MANAGER (v2.2)
// Multi-line captions, per-layer timing, draggable — basis-aware so layers
// stay put when the crop is confirmed and the stage re-frames.
// ==========================================================================

class TextOverlayManager {
  constructor(container, videoElement, getBasis) {
    this.container = container;
    this.video = videoElement;
    this.getBasis = getBasis || (() => ({
      w: container.clientWidth, h: container.clientHeight,
      scale: 1, offX: 0, offY: 0,
      visX: 0, visY: 0, visW: container.clientWidth, visH: container.clientHeight,
    }));

    this.stageLayer = document.getElementById('textStageLayer');
    this.btnAdd = document.getElementById('btnAddTextLayer');
    this.layerEditor = document.getElementById('textLayerEditor');
    this.layersList = document.getElementById('textLayersList');

    this.inputText = document.getElementById('textInputContent');
    this.selectFont = document.getElementById('textFontFamily');
    this.inputSize = document.getElementById('textFontSize');
    this.inputColor = document.getElementById('textColorPicker');
    this.hexColor = document.getElementById('textColorHex');
    this.inputStroke = document.getElementById('textStrokePicker');
    this.hexStroke = document.getElementById('textStrokeHex');
    this.inputStrokeWidth = document.getElementById('textStrokeWidth');

    this.toggleBg = document.getElementById('textBgToggle');
    this.ctrlBg = document.getElementById('textBgControls');
    this.inputBgColor = document.getElementById('textBgColor');
    this.inputBgOpacity = document.getElementById('textBgOpacity');

    this.inputStart = document.getElementById('textStartInput');
    this.inputEnd = document.getElementById('textEndInput');

    this.btnAlignTop = document.getElementById('btnAlignTextTop');
    this.btnAlignCenter = document.getElementById('btnAlignTextCenter');
    this.btnAlignBottom = document.getElementById('btnAlignTextBottom');
    this.btnDelete = document.getElementById('btnDeleteTextLayer');

    this.layers = [];
    this.activeLayerId = null;
    this.layerCounter = 1;

    this.initEvents();
  }

  initEvents() {
    this.btnAdd.addEventListener('click', () => this.addLayer());

    this.inputText.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.text = e.target.value;
      this.updateStageElement(layer);
      this.renderLayersList();
    });

    this.selectFont.addEventListener('change', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.font_family = e.target.value;
      this.updateStageElement(layer);
    });

    this.inputSize.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.font_size = parseInt(e.target.value) || 36;
      this.updateStageElement(layer);
    });

    this.inputColor.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.color = e.target.value;
      this.hexColor.textContent = e.target.value.toUpperCase();
      this.updateStageElement(layer);
    });

    this.inputStroke.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.stroke_color = e.target.value;
      this.hexStroke.textContent = e.target.value.toUpperCase();
      this.updateStageElement(layer);
    });

    this.inputStrokeWidth.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.stroke_width = parseInt(e.target.value) || 0;
      this.updateStageElement(layer);
    });

    this.toggleBg.addEventListener('change', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.bg_enabled = e.target.checked;
      this.ctrlBg.style.display = layer.bg_enabled ? 'block' : 'none';
      this.updateStageElement(layer);
    });

    this.inputBgColor.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.bg_color = e.target.value;
      this.updateStageElement(layer);
    });

    this.inputBgOpacity.addEventListener('input', (e) => {
      const layer = this.getActiveLayer();
      if (!layer) return;
      layer.bg_opacity = parseFloat(e.target.value) || 0.7;
      this.updateStageElement(layer);
    });

    const bindTiming = (input, key) => {
      if (!input) return;
      input.addEventListener('input', (e) => {
        const layer = this.getActiveLayer();
        if (!layer) return;
        const v = e.target.value.trim();
        layer[key] = v === '' ? null : Math.max(0, parseFloat(v) || 0);
        this.renderLayersList();
      });
    };
    bindTiming(this.inputStart, 'start');
    bindTiming(this.inputEnd, 'end');

    this.btnAlignTop.addEventListener('click', () => this.alignActive('top'));
    this.btnAlignCenter.addEventListener('click', () => this.alignActive('center'));
    this.btnAlignBottom.addEventListener('click', () => this.alignActive('bottom'));

    this.btnDelete.addEventListener('click', () => this.deleteActive());
  }

  addLayer(presetText = 'HOOK TITLE HERE') {
    const id = `layer_${this.layerCounter++}`;
    const b = this.getBasis();

    const newLayer = {
      id,
      text: presetText,
      x: Math.round(b.visX + b.visW * 0.1),
      y: Math.round(b.visY + b.visH * 0.15),
      font_family: 'Impact',
      font_size: 32,
      color: '#FFFFFF',
      stroke_color: '#000000',
      stroke_width: 3,
      bg_enabled: false,
      bg_color: '#000000',
      bg_opacity: 0.7,
      start: null,
      end: null,
    };

    this.layers.push(newLayer);
    this.createStageElement(newLayer);
    this.selectLayer(id);
    this.renderLayersList();
  }

  createStageElement(layer) {
    const el = document.createElement('div');
    el.className = 'text-stage-item';
    el.id = `stage_${layer.id}`;
    el.dataset.layerId = layer.id;

    let isDragging = false;
    let startX = 0, startY = 0;
    let initX = 0, initY = 0;

    el.addEventListener('pointerdown', (e) => {
      this.selectLayer(layer.id);
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      initX = layer.x;
      initY = layer.y;
      el.setPointerCapture(e.pointerId);
      e.stopPropagation();
    });

    el.addEventListener('pointermove', (e) => {
      if (!isDragging) return;
      const b = this.getBasis();
      const sc = b.scale || 1;
      const dx = (e.clientX - startX) / sc;
      const dy = (e.clientY - startY) / sc;

      const modelW = el.offsetWidth / sc;
      const modelH = el.offsetHeight / sc;

      layer.x = Math.max(b.visX, Math.min(b.visX + b.visW - modelW, initX + dx));
      layer.y = Math.max(b.visY, Math.min(b.visY + b.visH - modelH, initY + dy));

      el.style.left = `${layer.x * sc - b.offX}px`;
      el.style.top = `${layer.y * sc - b.offY}px`;
    });

    el.addEventListener('pointerup', () => {
      isDragging = false;
    });

    this.stageLayer.appendChild(el);
    this.updateStageElement(layer);
  }

  updateStageElement(layer) {
    const el = document.getElementById(`stage_${layer.id}`);
    if (!el) return;

    const b = this.getBasis();
    const sc = b.scale || 1;

    el.textContent = layer.text;
    el.style.left = `${layer.x * sc - b.offX}px`;
    el.style.top = `${layer.y * sc - b.offY}px`;
    el.style.fontFamily = layer.font_family;
    el.style.fontSize = `${layer.font_size * sc}px`;
    el.style.color = layer.color;
    el.style.whiteSpace = 'pre-line';  // multi-line captions preview

    if (layer.stroke_width > 0) {
      el.style.webkitTextStroke = `${layer.stroke_width * sc}px ${layer.stroke_color}`;
    } else {
      el.style.webkitTextStroke = 'none';
    }

    if (layer.bg_enabled) {
      const hex = layer.bg_color.replace('#', '');
      const r = parseInt(hex.substring(0, 2), 16) || 0;
      const g = parseInt(hex.substring(2, 4), 16) || 0;
      const bch = parseInt(hex.substring(4, 6), 16) || 0;
      el.style.backgroundColor = `rgba(${r}, ${g}, ${bch}, ${layer.bg_opacity})`;
      el.style.borderRadius = '4px';
      el.style.padding = '4px 10px';
    } else {
      el.style.backgroundColor = 'transparent';
      el.style.padding = '2px 4px';
    }
  }

  refreshAllDOM() {
    this.layers.forEach((layer) => this.updateStageElement(layer));
  }

  selectLayer(id) {
    this.activeLayerId = id;

    this.stageLayer.querySelectorAll('.text-stage-item').forEach((el) => {
      el.classList.toggle('selected', el.dataset.layerId === id);
    });

    const layer = this.getActiveLayer();
    if (!layer) {
      this.layerEditor.style.display = 'none';
      return;
    }

    this.layerEditor.style.display = 'block';
    this.inputText.value = layer.text;
    this.selectFont.value = layer.font_family;
    this.inputSize.value = layer.font_size;
    this.inputColor.value = layer.color;
    this.hexColor.textContent = layer.color.toUpperCase();
    this.inputStroke.value = layer.stroke_color;
    this.hexStroke.textContent = layer.stroke_color.toUpperCase();
    this.inputStrokeWidth.value = layer.stroke_width;

    this.toggleBg.checked = layer.bg_enabled;
    this.ctrlBg.style.display = layer.bg_enabled ? 'block' : 'none';
    this.inputBgColor.value = layer.bg_color;
    this.inputBgOpacity.value = layer.bg_opacity;

    if (this.inputStart) this.inputStart.value = layer.start ?? '';
    if (this.inputEnd) this.inputEnd.value = layer.end ?? '';

    this.renderLayersList();
  }

  alignActive(pos) {
    const layer = this.getActiveLayer();
    if (!layer) return;

    const b = this.getBasis();
    const el = document.getElementById(`stage_${layer.id}`);
    const sc = b.scale || 1;
    const elW = el ? el.offsetWidth / sc : 100;
    const elH = el ? el.offsetHeight / sc : 40;

    layer.x = Math.max(b.visX, Math.round(b.visX + (b.visW - elW) / 2));

    if (pos === 'top') {
      layer.y = Math.round(b.visY + b.visH * 0.1);
    } else if (pos === 'center') {
      layer.y = Math.round(b.visY + (b.visH - elH) / 2);
    } else if (pos === 'bottom') {
      layer.y = Math.round(b.visY + b.visH * 0.82);
    }

    this.updateStageElement(layer);
  }

  deleteActive() {
    if (!this.activeLayerId) return;
    const id = this.activeLayerId;

    const stageEl = document.getElementById(`stage_${id}`);
    if (stageEl) stageEl.remove();

    this.layers = this.layers.filter(l => l.id !== id);
    this.activeLayerId = this.layers.length > 0 ? this.layers[this.layers.length - 1].id : null;

    if (this.activeLayerId) {
      this.selectLayer(this.activeLayerId);
    } else {
      this.layerEditor.style.display = 'none';
    }
    this.renderLayersList();
  }

  getActiveLayer() {
    return this.layers.find(l => l.id === this.activeLayerId);
  }

  renderLayersList() {
    if (this.layers.length === 0) {
      this.layersList.innerHTML = '<div class="empty-layers-msg">No text layers yet. Click "+ Add Text" above.</div>';
      return;
    }

    this.layersList.innerHTML = '';
    this.layers.forEach((layer) => {
      const timing = (layer.start !== null || layer.end !== null)
        ? ` ⏱ ${layer.start ?? 0}s→${layer.end ?? 'end'}s`
        : '';
      const item = document.createElement('div');
      item.className = `text-layer-item ${layer.id === this.activeLayerId ? 'active' : ''}`;
      item.innerHTML = `
        <span class="layer-item-title">${(layer.text || '(Empty text)').split('\n')[0]}${timing}</span>
        <span class="badge">${layer.font_family}</span>
      `;
      item.addEventListener('click', () => this.selectLayer(layer.id));
      this.layersList.appendChild(item);
    });
  }

  /**
   * Text layers translated into native crop coordinates for FFmpeg,
   * including per-layer start/end timing (seconds, null = whole clip).
   */
  getNativeLayers(cropNative) {
    const nw = this.video.videoWidth;
    const nh = this.video.videoHeight;
    const b = this.getBasis();

    if (!nw || !nh || !b.w || !b.h) return [];

    const scaleX = nw / b.w;
    const scaleY = nh / b.h;

    const cropX = cropNative ? cropNative.x : 0;
    const cropY = cropNative ? cropNative.y : 0;

    return this.layers.map((layer) => {
      const nativeFontSize = Math.round(layer.font_size * scaleY);
      const nativeX = Math.round(layer.x * scaleX);
      const nativeY = Math.round(layer.y * scaleY);

      const relX = Math.max(0, nativeX - cropX);
      const relY = Math.max(0, nativeY - cropY);

      return {
        id: layer.id,
        text: layer.text,
        x: relX,
        y: relY,
        font_family: layer.font_family,
        font_size: Math.max(12, nativeFontSize),
        color: layer.color,
        stroke_color: layer.stroke_color,
        stroke_width: Math.round(layer.stroke_width * scaleY),
        bg_enabled: layer.bg_enabled,
        bg_color: layer.bg_color,
        bg_opacity: layer.bg_opacity,
        start: layer.start ?? null,
        end: layer.end ?? null,
      };
    });
  }
}

window.TextOverlayManager = TextOverlayManager;
