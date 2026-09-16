// ==========================================================================
// COLOR GRADING CONTROLLER (v2.1) - full CapCut-style adjust suite
// Live preview maps each control to the closest CSS equivalent; the export
// render uses the matching FFmpeg filters 1:1 (see editor_engine.py).
// ==========================================================================

class ColorGradingManager {
  constructor(videoElement) {
    this.video = videoElement;
    this.defaults = {
      brightness: 0, exposure: 0, contrast: 1, saturation: 1,
      highlights: 0, shadows: 0, temperature: 0, tint: 0,
      sharpen: 0, fade: 0, vignette: 0, grain: 0,
    };
    this.state = { ...this.defaults };

    this.fxVignette = document.getElementById('fxVignette');
    this.fxGrain = document.getElementById('fxGrain');

    this.controls = [
      { key: 'brightness', slider: 'sliderBrightness', val: 'valBrightness', fmt: v => `${Math.round(v * 100)}%` },
      { key: 'exposure', slider: 'sliderExposure', val: 'valExposure', fmt: v => v.toFixed(2) },
      { key: 'contrast', slider: 'sliderContrast', val: 'valContrast', fmt: v => v.toFixed(2) },
      { key: 'saturation', slider: 'sliderSaturation', val: 'valSaturation', fmt: v => v.toFixed(2) },
      { key: 'highlights', slider: 'sliderHighlights', val: 'valHighlights', fmt: v => v.toFixed(2) },
      { key: 'shadows', slider: 'sliderShadows', val: 'valShadows', fmt: v => v.toFixed(2) },
      { key: 'temperature', slider: 'sliderTemperature', val: 'valTemperature', fmt: v => (v > 0 ? `+${Math.round(v * 100)} (Warm)` : v < 0 ? `${Math.round(v * 100)} (Cool)` : '0') },
      { key: 'tint', slider: 'sliderTint', val: 'valTint', fmt: v => v.toFixed(2) },
      { key: 'sharpen', slider: 'sliderSharpen', val: 'valSharpen', fmt: v => v.toFixed(2) },
      { key: 'fade', slider: 'sliderFade', val: 'valFade', fmt: v => v.toFixed(2) },
      { key: 'vignette', slider: 'sliderVignette', val: 'valVignette', fmt: v => v.toFixed(2) },
      { key: 'grain', slider: 'sliderGrain', val: 'valGrain', fmt: v => v.toFixed(2) },
    ];

    this.initUI();
  }

  initUI() {
    this.controls.forEach((c) => {
      const slider = document.getElementById(c.slider);
      const valEl = document.getElementById(c.val);
      if (!slider) return;
      c._slider = slider;
      c._val = valEl;
      slider.addEventListener('input', (e) => {
        this.state[c.key] = parseFloat(e.target.value);
        if (valEl) valEl.textContent = c.fmt(this.state[c.key]);
        this.applyPreviewFilters();
      });
    });

    const btnReset = document.getElementById('btnResetColorGrading');
    if (btnReset) btnReset.addEventListener('click', () => this.reset());
  }

  applyPreviewFilters() {
    if (!this.video) return;
    const s = this.state;

    // Luminance stack: brightness + exposure + shadows lift + highlights
    let brightness = 1 + s.brightness + s.exposure * 0.35 + s.shadows * 0.08 - Math.max(0, s.highlights) * 0.04;
    let contrast = s.contrast * (1 + s.highlights * 0.08) * (1 - s.fade * 0.12);
    let saturate = s.saturation * (1 - s.fade * 0.15);

    let filterStr = `brightness(${Math.max(0.2, brightness.toFixed(3))}) contrast(${Math.max(0.2, contrast.toFixed(3))}) saturate(${Math.max(0, saturate.toFixed(3))})`;

    // Temperature: warm = sepia + slight hue shift; cool = hue toward cyan.
    let hue = 0;
    let sepia = 0;
    if (s.temperature > 0) {
      sepia = s.temperature * 0.4;
      hue = -s.temperature * 15;
    } else if (s.temperature < 0) {
      sepia = Math.abs(s.temperature) * 0.2;
      hue = Math.abs(s.temperature) * 25;
    }
    // Tint (green <-> magenta): approximate with a small counter hue-rotate.
    hue += -s.tint * 10;

    if (sepia > 0 || hue !== 0) filterStr += ` sepia(${sepia.toFixed(3)}) hue-rotate(${hue.toFixed(1)}deg)`;

    // Sharpen: crisp edges read as a slight local contrast bump in preview.
    if (s.sharpen > 0) filterStr += ` contrast(${(1 + s.sharpen * 0.08).toFixed(3)})`;

    this.video.style.filter = filterStr;

    // Vignette + grain preview via stage overlays.
    if (this.fxVignette) this.fxVignette.style.opacity = (s.vignette * 0.85).toFixed(2);
    if (this.fxGrain) this.fxGrain.style.opacity = (s.grain * 0.4).toFixed(2);
  }

  reset() {
    this.state = { ...this.defaults };
    this.controls.forEach((c) => {
      if (c._slider) c._slider.value = this.defaults[c.key];
      if (c._val) c._val.textContent = c.fmt(this.defaults[c.key]);
    });
    this.applyPreviewFilters();
  }

  getState() {
    return { ...this.state };
  }
}

window.ColorGradingManager = ColorGradingManager;
