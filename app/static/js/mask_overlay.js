// ==========================================================================
// INTERACTIVE BLUR MASK OVERLAY CONTROLLER
// ==========================================================================

class MaskOverlayManager {
  constructor(container, videoElement) {
    this.container = container;
    this.video = videoElement;

    this.maskBox = document.getElementById('maskBox');
    this.toggle = document.getElementById('maskEnableToggle');
    this.controlsWrap = document.getElementById('maskControlsWrap');

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

    this.enabled = false;
    this.blurRadius = 20;

    // Mask in container pixel space
    this.box = { x: 30, y: 30, w: 160, h: 70 };

    this.isDragging = false;
    this.isResizing = false;
    this.dragStart = { x: 0, y: 0, boxX: 0, boxY: 0, boxW: 0, boxH: 0 };

    this.initEvents();
  }

  initEvents() {
    // Toggle switch
    this.toggle.addEventListener('change', () => {
      this.enabled = this.toggle.checked;
      this.maskBox.style.display = this.enabled ? 'block' : 'none';
      this.controlsWrap.classList.toggle('disabled-wrap', !this.enabled);
      if (this.enabled) {
        this.updateDOM();
        this.updateInputs();
      }
    });

    // Blur slider
    this.sliderBlur.addEventListener('input', (e) => {
      this.blurRadius = parseInt(e.target.value);
      this.valBlur.textContent = `${this.blurRadius} px`;
      this.maskBox.style.backdropFilter = `blur(${this.blurRadius}px)`;
      this.maskBox.style.webkitBackdropFilter = `blur(${this.blurRadius}px)`;
    });

    // Dragging mask box
    this.maskBox.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('mask-handle-se')) return;
      this.isDragging = true;
      this.dragStart = {
        x: e.clientX,
        y: e.clientY,
        boxX: this.box.x,
        boxY: this.box.y,
        boxW: this.box.w,
        boxH: this.box.h,
      };
      this.maskBox.setPointerCapture(e.pointerId);
      e.stopPropagation();
    });

    // Resizing mask box
    const handle = this.maskBox.querySelector('.mask-handle-se');
    if (handle) {
      handle.addEventListener('pointerdown', (e) => {
        this.isResizing = true;
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
    }

    window.addEventListener('pointermove', (e) => {
      if (this.isDragging) {
        this.onDrag(e);
      } else if (this.isResizing) {
        this.onResize(e);
      }
    });

    window.addEventListener('pointerup', () => {
      if (this.isDragging || this.isResizing) {
        this.isDragging = false;
        this.isResizing = false;
        this.updateInputs();
      }
    });

    // Inputs change
    [this.inputW, this.inputH, this.inputX, this.inputY].forEach((inp) => {
      inp.addEventListener('change', () => this.onManualInputChange());
    });

    // Preset positions
    if (this.btnTR) this.btnTR.addEventListener('click', () => this.setPosition('tr'));
    if (this.btnBR) this.btnBR.addEventListener('click', () => this.setPosition('br'));
    if (this.btnTL) this.btnTL.addEventListener('click', () => this.setPosition('tl'));
    if (this.btnBL) this.btnBL.addEventListener('click', () => this.setPosition('bl'));
  }

  setPosition(pos) {
    const cw = this.container.clientWidth;
    const ch = this.container.clientHeight;
    const pad = 20;

    if (pos === 'tr') {
      this.box.x = cw - this.box.w - pad;
      this.box.y = pad;
    } else if (pos === 'br') {
      this.box.x = cw - this.box.w - pad;
      this.box.y = ch - this.box.h - pad;
    } else if (pos === 'tl') {
      this.box.x = pad;
      this.box.y = pad;
    } else if (pos === 'bl') {
      this.box.x = pad;
      this.box.y = ch - this.box.h - pad;
    }

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

    let newW = Math.max(20, Math.min(maxW - this.box.x, this.dragStart.boxW + dx));
    let newH = Math.max(20, Math.min(maxH - this.box.y, this.dragStart.boxH + dy));

    this.box.w = newW;
    this.box.h = newH;
    this.updateDOM();
  }

  updateDOM() {
    this.maskBox.style.left = `${this.box.x}px`;
    this.maskBox.style.top = `${this.box.y}px`;
    this.maskBox.style.width = `${this.box.w}px`;
    this.maskBox.style.height = `${this.box.h}px`;
    this.maskBox.style.backdropFilter = `blur(${this.blurRadius}px)`;
    this.maskBox.style.webkitBackdropFilter = `blur(${this.blurRadius}px)`;
  }

  updateInputs() {
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    const cw = this.container.clientWidth || 1;
    const ch = this.container.clientHeight || 1;

    const scaleX = nw / cw;
    const scaleY = nh / ch;

    this.inputW.value = Math.round(this.box.w * scaleX);
    this.inputH.value = Math.round(this.box.h * scaleY);
    this.inputX.value = Math.round(this.box.x * scaleX);
    this.inputY.value = Math.round(this.box.y * scaleY);
  }

  onManualInputChange() {
    const nw = this.video.videoWidth || 1080;
    const nh = this.video.videoHeight || 1920;
    const cw = this.container.clientWidth || 1;
    const ch = this.container.clientHeight || 1;

    const scaleX = cw / nw;
    const scaleY = ch / nh;

    this.box.w = (parseInt(this.inputW.value) || 100) * scaleX;
    this.box.h = (parseInt(this.inputH.value) || 50) * scaleY;
    this.box.x = (parseInt(this.inputX.value) || 0) * scaleX;
    this.box.y = (parseInt(this.inputY.value) || 0) * scaleY;

    this.updateDOM();
  }

  /**
   * Returns mask coordinates relative to the cropped frame for FFmpeg
   */
  getNativeCoords(cropNative) {
    if (!this.enabled) return { enabled: false };

    const nw = this.video.videoWidth;
    const nh = this.video.videoHeight;
    const cw = this.container.clientWidth;
    const ch = this.container.clientHeight;

    if (!nw || !nh || !cw || !ch) return { enabled: false };

    const scaleX = nw / cw;
    const scaleY = nh / ch;

    const absMaskX = Math.round(this.box.x * scaleX);
    const absMaskY = Math.round(this.box.y * scaleY);
    const absMaskW = Math.round(this.box.w * scaleX);
    const absMaskH = Math.round(this.box.h * scaleY);

    // Calculate relative coordinates to crop area
    const cropX = cropNative ? cropNative.x : 0;
    const cropY = cropNative ? cropNative.y : 0;
    const cropW = cropNative ? cropNative.width : nw;
    const cropH = cropNative ? cropNative.height : nh;

    let relX = absMaskX - cropX;
    let relY = absMaskY - cropY;
    let relW = absMaskW;
    let relH = absMaskH;

    // Clamp inside crop frame
    relW = Math.max(4, Math.min(cropW, relW));
    relH = Math.max(4, Math.min(cropH, relH));
    relW = relW - (relW % 2);
    relH = relH - (relH % 2);

    relX = Math.max(0, Math.min(cropW - relW, relX));
    relY = Math.max(0, Math.min(cropH - relH, relY));

    return {
      enabled: true,
      x: relX,
      y: relY,
      width: relW,
      height: relH,
      blur: this.blurRadius,
    };
  }
}

window.MaskOverlayManager = MaskOverlayManager;
