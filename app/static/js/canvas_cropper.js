// ==========================================================================
// INTERACTIVE CANVAS CROPPER & ASPECT RATIO MANAGER
// ==========================================================================

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

    // Current aspect ratio mode ('9:16', '1:1', '4:5', '16:9', '4:3', 'free').
    // Start on the whole frame: never silently crop a video the user just
    // loaded. Picking 9:16 (or any preset) is one click away.
    this.currentRatioMode = 'free';
    this.ratioValue = null;

    // Crop box in container pixel space: { x, y, w, h }
    this.box = { x: 0, y: 0, w: 100, h: 100 };

    this.isDragging = false;
    this.isResizing = false;
    this.activeHandle = null;
    this.dragStart = { x: 0, y: 0, boxX: 0, boxY: 0, boxW: 0, boxH: 0 };

    this.initEvents();
  }

  initEvents() {
    // Ratio buttons
    this.ratioCards.forEach((card) => {
      card.addEventListener('click', () => {
        this.ratioCards.forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        this.setRatio(card.dataset.ratio);
      });
    });

    // Handle drag on the crop box body
    this.cropBox.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('handle')) return; // handled by handle
      this.isDragging = true;
      this.dragStart = {
        x: e.clientX,
        y: e.clientY,
        boxX: this.box.x,
        boxY: this.box.y,
        boxW: this.box.w,
        boxH: this.box.h,
      };
      this.cropBox.setPointerCapture(e.pointerId);
      e.stopPropagation();
    });

    // Handles
    const handles = this.cropBox.querySelectorAll('.handle');
    handles.forEach((handle) => {
      handle.addEventListener('pointerdown', (e) => {
        this.isResizing = true;
        this.activeHandle = handle.dataset.handle;
        this.dragStart = {
          x: e.clientX,
          y: e.clientY,
          boxX: this.box.x,
          boxY: this.box.y,
          boxW: this.box.w,
          boxH: this.box.h,
        };
        handle.setPointerCapture(e.pointerId);
        e.stopPropagation();
      });
    });

    // Window pointer move and up
    window.addEventListener('pointermove', (e) => {
      if (this.isDragging) {
        this.onDrag(e);
      } else if (this.isResizing) {
        this.onResize(e);
      }
    });

    window.addEventListener('pointerup', (e) => {
      if (this.isDragging || this.isResizing) {
        this.isDragging = false;
        this.isResizing = false;
        this.activeHandle = null;
        this.updateInputs();
      }
    });

    // Direct input adjustments
    [this.inputW, this.inputH, this.inputX, this.inputY].forEach((inp) => {
      inp.addEventListener('change', () => this.onManualInputChange());
    });

    if (this.btnCenter) {
      this.btnCenter.addEventListener('click', () => this.centerCrop());
    }
    if (this.btnReset) {
      this.btnReset.addEventListener('click', () => this.resetToFull());
    }
  }

  setRatio(mode) {
    this.currentRatioMode = mode;

    if (mode === 'free') {
      this.ratioValue = null;
    } else if (mode === '9:16') {
      this.ratioValue = 9 / 16;
    } else if (mode === '1:1') {
      this.ratioValue = 1 / 1;
    } else if (mode === '4:5') {
      this.ratioValue = 4 / 5;
    } else if (mode === '16:9') {
      this.ratioValue = 16 / 9;
    } else if (mode === '4:3') {
      this.ratioValue = 4 / 3;
    }

    if (this.ratioValue) {
      this.applyRatioToCurrentBox();
    }
    this.updateDOM();
    this.updateInputs();
  }

  onVideoLoaded() {
    const containerW = this.container.clientWidth;
    const containerH = this.container.clientHeight;

    if (containerW <= 0 || containerH <= 0) return;

    // Start on the full frame so nothing is cropped until the user asks for it.
    this.resetToFull();
  }

  applyRatioToCurrentBox() {
    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;

    if (!this.ratioValue) return;

    let targetW = this.box.w;
    let targetH = targetW / this.ratioValue;

    if (targetH > maxH) {
      targetH = maxH * 0.9;
      targetW = targetH * this.ratioValue;
    }
    if (targetW > maxW) {
      targetW = maxW * 0.9;
      targetH = targetW / this.ratioValue;
    }

    this.box.w = Math.max(30, targetW);
    this.box.h = Math.max(30, targetH);

    // Keep within bounds
    if (this.box.x + this.box.w > maxW) this.box.x = maxW - this.box.w;
    if (this.box.y + this.box.h > maxH) this.box.y = maxH - this.box.h;
    if (this.box.x < 0) this.box.x = 0;
    if (this.box.y < 0) this.box.y = 0;
  }

  centerCrop() {
    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;

    if (this.ratioValue) {
      // Find largest rectangle that fits
      let w = maxW * 0.85;
      let h = w / this.ratioValue;
      if (h > maxH * 0.95) {
        h = maxH * 0.95;
        w = h * this.ratioValue;
      }
      this.box.w = Math.min(maxW, w);
      this.box.h = Math.min(maxH, h);
    } else {
      this.box.w = maxW * 0.8;
      this.box.h = maxH * 0.8;
    }

    this.box.x = (maxW - this.box.w) / 2;
    this.box.y = (maxH - this.box.h) / 2;

    this.updateDOM();
    this.updateInputs();
  }

  resetToFull() {
    this.currentRatioMode = 'free';
    this.ratioValue = null;
    this.ratioCards.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'free'));

    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;
    this.box = { x: 0, y: 0, w: maxW, h: maxH };

    this.updateDOM();
    this.updateInputs();
  }

  onDrag(e) {
    const dx = e.clientX - this.dragStart.x;
    const dy = e.clientY - this.dragStart.y;

    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;

    let newX = this.dragStart.boxX + dx;
    let newY = this.dragStart.boxY + dy;

    // Bounds check
    newX = Math.max(0, Math.min(maxW - this.box.w, newX));
    newY = Math.max(0, Math.min(maxH - this.box.h, newY));

    this.box.x = newX;
    this.box.y = newY;

    this.updateDOM();
  }

  onResize(e) {
    const dx = e.clientX - this.dragStart.x;
    const dy = e.clientY - this.dragStart.y;

    const maxW = this.container.clientWidth;
    const maxH = this.container.clientHeight;

    let { boxX, boxY, boxW, boxH } = this.dragStart;
    let newX = boxX;
    let newY = boxY;
    let newW = boxW;
    let newH = boxH;

    const h = this.activeHandle;

    if (h.includes('e')) newW = boxW + dx;
    if (h.includes('s')) newH = boxH + dy;
    if (h.includes('w')) {
      newW = boxW - dx;
      newX = boxX + dx;
    }
    if (h.includes('n')) {
      newH = boxH - dy;
      newY = boxY + dy;
    }

    // Apply aspect ratio lock if active
    if (this.ratioValue) {
      if (h === 'e' || h === 'w') {
        newH = newW / this.ratioValue;
        newY = boxY + (boxH - newH) / 2;
      } else if (h === 'n' || h === 's') {
        newW = newH * this.ratioValue;
        newX = boxX + (boxW - newW) / 2;
      } else {
        // Corner handles: use dominant axis
        if (Math.abs(dx) > Math.abs(dy)) {
          newH = newW / this.ratioValue;
          if (h.includes('n')) newY = boxY + boxH - newH;
        } else {
          newW = newH * this.ratioValue;
          if (h.includes('w')) newX = boxX + boxW - newW;
        }
      }
    }

    // Min bounds
    if (newW < 20 || newH < 20) return;

    // Max bounds check
    if (newX < 0) {
      newW += newX;
      newX = 0;
    }
    if (newY < 0) {
      newH += newY;
      newY = 0;
    }
    if (newX + newW > maxW) newW = maxW - newX;
    if (newY + newH > maxH) newH = maxH - newY;

    this.box = { x: newX, y: newY, w: newW, h: newH };
    this.updateDOM();
  }

  updateDOM() {
    this.cropBox.style.left = `${this.box.x}px`;
    this.cropBox.style.top = `${this.box.y}px`;
    this.cropBox.style.width = `${this.box.w}px`;
    this.cropBox.style.height = `${this.box.h}px`;
    this.updateBadge();
  }

  ratioLabel() {
    return this.currentRatioMode === 'free' ? 'Custom' : this.currentRatioMode;
  }

  /**
   * Show the size that will actually be exported, not just the ratio name.
   * Choosing "Freeform" does not reshape the box - it only unlocks the ratio -
   * so without this the badge could read "Custom" while the crop was still 9:16.
   */
  updateBadge() {
    const c = this.getNativeCoords();
    this.cropBadge.textContent = c
      ? `${this.ratioLabel()} · ${c.width}×${c.height}`
      : this.ratioLabel();
  }

  updateInputs() {
    const nativeCoords = this.getNativeCoords();
    if (!nativeCoords) return;

    this.inputW.value = nativeCoords.width;
    this.inputH.value = nativeCoords.height;
    this.inputX.value = nativeCoords.x;
    this.inputY.value = nativeCoords.y;
  }

  onManualInputChange() {
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    const scaleX = this.container.clientWidth / nw;
    const scaleY = this.container.clientHeight / nh;

    const nativeW = parseInt(this.inputW.value) || 100;
    const nativeH = parseInt(this.inputH.value) || 100;
    const nativeX = parseInt(this.inputX.value) || 0;
    const nativeY = parseInt(this.inputY.value) || 0;

    this.box.x = nativeX * scaleX;
    this.box.y = nativeY * scaleY;
    this.box.w = nativeW * scaleX;
    this.box.h = nativeH * scaleY;

    this.currentRatioMode = 'free';
    this.ratioValue = null;
    this.ratioCards.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'free'));

    this.updateDOM();
  }

  /**
   * Returns exact pixel crop coordinates in native video space
   * Suitable for FFmpeg crop=w:h:x:y
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

    // Ensure even dimensions
    width = Math.max(2, width - (width % 2));
    height = Math.max(2, height - (height % 2));
    x = Math.max(0, Math.min(nw - width, x - (x % 2)));
    y = Math.max(0, Math.min(nh - height, y - (y % 2)));

    return {
      enabled: true,
      x,
      y,
      width,
      height,
    };
  }
}

window.CanvasCropper = CanvasCropper;
