// ==========================================================================
// TIMELINE & PRECISION TRIMMER MANAGER
// ==========================================================================

class TimelineManager {
  constructor(videoElement) {
    this.video = videoElement;

    // DOM Elements
    this.btnPlayPause = document.getElementById('btnPlayPause');
    this.playIcon = document.getElementById('playIcon');
    this.pauseIcon = document.getElementById('pauseIcon');
    this.btnStepBack = document.getElementById('btnStepBack');
    this.btnStepForward = document.getElementById('btnStepForward');

    this.timeCurrent = document.getElementById('timeCurrent');
    this.timeTotal = document.getElementById('timeTotal');

    this.trackWrap = document.getElementById('timelineTrackWrap');
    this.track = document.getElementById('timelineTrack');
    this.dimLeft = document.getElementById('trimDimLeft');
    this.dimRight = document.getElementById('trimDimRight');
    this.activeRegion = document.getElementById('trimActiveRegion');

    this.handleLeft = document.getElementById('trimHandleLeft');
    this.handleRight = document.getElementById('trimHandleRight');
    this.tagIn = document.getElementById('inPointTag');
    this.tagOut = document.getElementById('outPointTag');

    this.playhead = document.getElementById('timelinePlayhead');

    this.btnSetIn = document.getElementById('btnSetInPoint');
    this.btnSetOut = document.getElementById('btnSetOutPoint');
    this.btnResetTrim = document.getElementById('btnResetTrim');

    // Trim state in seconds
    this.duration = 0.0;
    this.inPoint = 0.0;
    this.outPoint = 0.0;

    this.isDraggingIn = false;
    this.isDraggingOut = false;
    this.isScrubbing = false;

    this.initEvents();
  }

  initEvents() {
    // Play/Pause
    this.btnPlayPause.addEventListener('click', () => this.togglePlay());
    this.btnStepBack.addEventListener('click', () => this.step(-1));
    this.btnStepForward.addEventListener('click', () => this.step(1));

    // Spacebar hotkey
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        this.togglePlay();
      }
    });

    // Video timeupdate
    this.video.addEventListener('timeupdate', () => this.onTimeUpdate());
    this.video.addEventListener('ended', () => {
      this.video.currentTime = this.inPoint;
      this.setPlaying(false);
    });

    // Left In Handle Drag
    this.handleLeft.addEventListener('pointerdown', (e) => {
      this.isDraggingIn = true;
      this.handleLeft.setPointerCapture(e.pointerId);
      e.stopPropagation();
    });

    // Right Out Handle Drag
    this.handleRight.addEventListener('pointerdown', (e) => {
      this.isDraggingOut = true;
      this.handleRight.setPointerCapture(e.pointerId);
      e.stopPropagation();
    });

    // Track click / scrubber drag
    this.track.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('trim-handle') || e.target.closest('.trim-handle')) return;
      this.isScrubbing = true;
      this.seekToClientX(e.clientX);
      this.track.setPointerCapture(e.pointerId);
    });

    window.addEventListener('pointermove', (e) => {
      if (this.isDraggingIn) {
        const t = this.clientToTime(e.clientX);
        this.inPoint = Math.max(0, Math.min(this.outPoint - 0.2, t));
        this.video.currentTime = this.inPoint;
        this.updateDOM();
      } else if (this.isDraggingOut) {
        const t = this.clientToTime(e.clientX);
        this.outPoint = Math.max(this.inPoint + 0.2, Math.min(this.duration, t));
        this.video.currentTime = this.outPoint;
        this.updateDOM();
      } else if (this.isScrubbing) {
        this.seekToClientX(e.clientX);
      }
    });

    window.addEventListener('pointerup', () => {
      this.isDraggingIn = false;
      this.isDraggingOut = false;
      this.isScrubbing = false;
    });

    // Quick set buttons
    if (this.btnSetIn) {
      this.btnSetIn.addEventListener('click', () => {
        this.inPoint = Math.max(0, Math.min(this.outPoint - 0.2, this.video.currentTime));
        this.updateDOM();
      });
    }

    if (this.btnSetOut) {
      this.btnSetOut.addEventListener('click', () => {
        this.outPoint = Math.max(this.inPoint + 0.2, Math.min(this.duration, this.video.currentTime));
        this.updateDOM();
      });
    }

    if (this.btnResetTrim) {
      this.btnResetTrim.addEventListener('click', () => {
        this.inPoint = 0.0;
        this.outPoint = this.duration;
        this.updateDOM();
      });
    }
  }

  onVideoLoaded(duration) {
    this.duration = duration || this.video.duration || 1.0;
    this.inPoint = 0.0;
    this.outPoint = this.duration;
    this.timeTotal.textContent = this.formatTime(this.duration);
    this.updateDOM();
  }

  togglePlay() {
    if (this.video.paused) {
      if (this.video.currentTime < this.inPoint || this.video.currentTime >= this.outPoint) {
        this.video.currentTime = this.inPoint;
      }
      this.video.play();
      this.setPlaying(true);
    } else {
      this.video.pause();
      this.setPlaying(false);
    }
  }

  setPlaying(isPlaying) {
    this.playIcon.style.display = isPlaying ? 'none' : 'block';
    this.pauseIcon.style.display = isPlaying ? 'block' : 'none';
  }

  step(seconds) {
    this.video.currentTime = Math.max(0, Math.min(this.duration, this.video.currentTime + seconds));
  }

  onTimeUpdate() {
    const cur = this.video.currentTime;
    this.timeCurrent.textContent = this.formatTime(cur);

    // Loop within trim bounds if playing
    if (!this.video.paused) {
      if (cur >= this.outPoint) {
        this.video.currentTime = this.inPoint;
      }
    }

    // Update playhead
    if (this.duration > 0) {
      const pct = (cur / this.duration) * 100;
      this.playhead.style.left = `${Math.min(100, Math.max(0, pct))}%`;
    }
  }

  seekToClientX(clientX) {
    const t = this.clientToTime(clientX);
    this.video.currentTime = t;
    this.onTimeUpdate();
  }

  clientToTime(clientX) {
    const rect = this.track.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return pct * this.duration;
  }

  updateDOM() {
    if (this.duration <= 0) return;

    const inPct = (this.inPoint / this.duration) * 100;
    const outPct = (this.outPoint / this.duration) * 100;

    // Dimmed regions
    this.dimLeft.style.width = `${inPct}%`;
    this.dimRight.style.width = `${100 - outPct}%`;

    // Active highlighted region
    this.activeRegion.style.left = `${inPct}%`;
    this.activeRegion.style.width = `${outPct - inPct}%`;

    // Tags
    this.tagIn.textContent = `IN: ${this.inPoint.toFixed(1)}s`;
    this.tagOut.textContent = `OUT: ${this.outPoint.toFixed(1)}s`;
  }

  formatTime(sec) {
    if (isNaN(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(2);
    return `${m.toString().padStart(2, '0')}:${s.padStart(5, '0')}`;
  }

  getTrimRange() {
    return {
      start: parseFloat(this.inPoint.toFixed(3)),
      end: parseFloat(this.outPoint.toFixed(3)),
    };
  }
}

window.TimelineManager = TimelineManager;
