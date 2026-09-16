// ==========================================================================
// COLOR GRADING & SHARPENING CONTROLLER
// ==========================================================================

class ColorGradingManager {
  constructor(videoElement) {
    this.video = videoElement;
    this.state = {
      sharpen: 0.0,      // 0.0 to 2.5
      brightness: 0.0,   // -0.5 to 0.5 (maps to 50% to 150%)
      contrast: 1.0,     // 0.5 to 1.8
      saturation: 1.0,   // 0.0 to 2.0
      temperature: 0.0,  // -0.4 to 0.4 (cool to warm)
    };

    this.initUI();
  }

  initUI() {
    this.sliderSharpen = document.getElementById('sliderSharpen');
    this.sliderBrightness = document.getElementById('sliderBrightness');
    this.sliderContrast = document.getElementById('sliderContrast');
    this.sliderSaturation = document.getElementById('sliderSaturation');
    this.sliderTemperature = document.getElementById('sliderTemperature');

    this.valSharpen = document.getElementById('valSharpen');
    this.valBrightness = document.getElementById('valBrightness');
    this.valContrast = document.getElementById('valContrast');
    this.valSaturation = document.getElementById('valSaturation');
    this.valTemperature = document.getElementById('valTemperature');

    this.btnReset = document.getElementById('btnResetColorGrading');

    // Attach listeners
    this.sliderSharpen.addEventListener('input', (e) => {
      this.state.sharpen = parseFloat(e.target.value);
      this.valSharpen.textContent = this.state.sharpen.toFixed(2);
      this.applyPreviewFilters();
    });

    this.sliderBrightness.addEventListener('input', (e) => {
      this.state.brightness = parseFloat(e.target.value);
      const pct = Math.round(this.state.brightness * 100);
      this.valBrightness.textContent = (pct > 0 ? `+${pct}%` : `${pct}%`);
      this.applyPreviewFilters();
    });

    this.sliderContrast.addEventListener('input', (e) => {
      this.state.contrast = parseFloat(e.target.value);
      this.valContrast.textContent = this.state.contrast.toFixed(2);
      this.applyPreviewFilters();
    });

    this.sliderSaturation.addEventListener('input', (e) => {
      this.state.saturation = parseFloat(e.target.value);
      this.valSaturation.textContent = this.state.saturation.toFixed(2);
      this.applyPreviewFilters();
    });

    this.sliderTemperature.addEventListener('input', (e) => {
      this.state.temperature = parseFloat(e.target.value);
      const tempVal = Math.round(this.state.temperature * 100);
      this.valTemperature.textContent = tempVal > 0 ? `+${tempVal} (Warm)` : tempVal < 0 ? `${tempVal} (Cool)` : '0';
      this.applyPreviewFilters();
    });

    if (this.btnReset) {
      this.btnReset.addEventListener('click', () => this.reset());
    }
  }

  applyPreviewFilters() {
    if (!this.video) return;

    // CSS filter values:
    // Brightness: 1.0 + brightness
    const b = Math.max(0.2, 1.0 + this.state.brightness);
    const c = this.state.contrast;
    const s = this.state.saturation;

    // Temperature simulation:
    // Warm: subtle sepia + hue-rotate
    let sepia = 0;
    let hueRotate = 0;
    if (this.state.temperature > 0) {
      sepia = this.state.temperature * 0.4;
      hueRotate = -this.state.temperature * 15;
    } else if (this.state.temperature < 0) {
      sepia = Math.abs(this.state.temperature) * 0.2;
      hueRotate = Math.abs(this.state.temperature) * 25; // shifts toward blue/cyan
    }

    let filterStr = `brightness(${b}) contrast(${c}) saturate(${s})`;
    if (sepia > 0) {
      filterStr += ` sepia(${sepia}) hue-rotate(${hueRotate}deg)`;
    }

    // Sharpening simulation via contrast / clarity edge punch
    if (this.state.sharpen > 0) {
      const extraContrast = 1 + (this.state.sharpen * 0.08);
      filterStr += ` contrast(${extraContrast})`;
    }

    this.video.style.filter = filterStr;
  }

  reset() {
    this.state = {
      sharpen: 0.0,
      brightness: 0.0,
      contrast: 1.0,
      saturation: 1.0,
      temperature: 0.0,
    };

    this.sliderSharpen.value = 0.0;
    this.sliderBrightness.value = 0.0;
    this.sliderContrast.value = 1.0;
    this.sliderSaturation.value = 1.0;
    this.sliderTemperature.value = 0.0;

    this.valSharpen.textContent = '0.00';
    this.valBrightness.textContent = '0%';
    this.valContrast.textContent = '1.00';
    this.valSaturation.textContent = '1.00';
    this.valTemperature.textContent = '0';

    this.applyPreviewFilters();
  }

  getState() {
    return { ...this.state };
  }
}

window.ColorGradingManager = ColorGradingManager;
