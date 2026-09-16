// Drives the real Forge Studio UI in Chromium: loads the page, watches for
// JS errors, uploads a video, runs the hashing step, and screenshots the result.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const PORT = process.env.FORGE_PORT || '8015';
const BASE = `http://127.0.0.1:${PORT}`;
const ROOT = 'C:\\Users\\lenovo\\OneDrive\\Desktop\\Custom editing software';
const VIDEO = path.join(ROOT, 'app', 'uploads', 'test_sample.mp4');
const SHOTS = path.join(ROOT, 'tools', 'screenshots');

const errors = [];
const consoleErrors = [];
const failedRequests = [];

function step(msg) {
  console.log(`\n== ${msg}`);
}

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });

  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  page.on('pageerror', (e) => errors.push(`${e.name}: ${e.message}`));
  page.on('requestfailed', (r) => {
    const u = r.url();
    if (!u.startsWith('data:')) failedRequests.push(`${r.method()} ${u} - ${r.failure()?.errorText}`);
  });

  try {
    step('1. load the studio');
    // Wait on domcontentloaded, not 'load': the page pulls a Google Fonts
    // stylesheet, and if that request stalls the window load event never fires
    // even though the studio itself is fully working.
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(
      () => !document.getElementById('engineStatusText').textContent.includes('Checking'),
      { timeout: 25000 });
    await page.waitForTimeout(800);

    const title = await page.title();
    console.log(`   title: ${title}`);

    step('1b. storage panel rendered');
    const storage = await page.evaluate(() => ({
      uploadsTotal: document.getElementById('storageUploadsTotal').textContent,
      outputsTotal: document.getElementById('storageOutputsTotal').textContent,
      uploadRows: document.querySelectorAll('#storageUploadsList .storage-row').length,
      outputRows: document.querySelectorAll('#storageOutputsList .storage-row').length,
      delButtons: document.querySelectorAll('.storage-del').length,
      clearOutputs: !!document.getElementById('btnClearOutputs'),
      clearUploads: !!document.getElementById('btnClearUploads'),
    }));
    console.log(`   uploads ${storage.uploadsTotal} across ${storage.uploadRows} file(s)`);
    console.log(`   outputs ${storage.outputsTotal} across ${storage.outputRows} file(s)`);
    console.log(`   ${storage.delButtons} per-file delete buttons, bulk buttons: ` +
                `${storage.clearOutputs && storage.clearUploads ? 'yes' : 'MISSING'}`);
    if (storage.uploadRows === 0) throw new Error('storage panel listed no uploads');
    if (!storage.clearOutputs || !storage.clearUploads) throw new Error('bulk clear buttons missing');
    if (storage.delButtons !== storage.uploadRows + storage.outputRows) {
      throw new Error('not every storage row has a delete button');
    }

    step('2. engine status after boot');
    const engineText = await page.textContent('#engineStatusText');
    const engineOk = await page.evaluate(() =>
      document.getElementById('engineStatus').classList.contains('is-ok'));
    console.log(`   status: ${engineText}`);
    console.log(`   engine ok class: ${engineOk}`);

    step('3. profile grid rendered from /api/profiles');
    const cards = await page.$$eval('.profile-card', els =>
      els.map(e => e.dataset.profile));
    console.log(`   ${cards.length} profiles: ${cards.join(', ')}`);
    const activeCard = await page.$$eval('.profile-card.active',
      els => els.map(e => e.dataset.profile));
    console.log(`   active: ${activeCard.join(', ')}`);

    step('3b. stage 1.5 (AI pass) status is reported honestly');
    const ml = await page.evaluate(() => ({
      visible: document.getElementById('mlStatus').style.display !== 'none',
      badge: document.getElementById('mlStatusBadge').textContent,
      text: document.getElementById('mlStatusText').textContent.trim(),
      off: document.getElementById('mlStatus').classList.contains('is-off'),
    }));
    console.log(`   visible=${ml.visible} badge=${ml.badge} flagged-off=${ml.off}`);
    console.log(`   ${ml.text}`);
    if (!ml.visible) throw new Error('Stage 1.5 status should be visible');

    const mlMarked = await page.$$eval('.profile-card .profile-uses-ml',
      els => els.length);
    const mlSkipped = await page.$$eval('.profile-card.ml-skipped',
      els => els.map(e => e.dataset.profile));
    console.log(`   profiles marked as wanting AI: ${mlMarked}`);
    console.log(`   profiles flagged as skipping it: ${mlSkipped.join(', ') || 'none'}`);

    step('4. hash button state before a video is loaded');
    let disabled = await page.isDisabled('#btnRunHashing');
    let label = await page.textContent('#btnRunHashingLabel');
    console.log(`   disabled=${disabled} label="${label}"`);
    if (!disabled) throw new Error('hash button should be disabled with no video');

    step('5. upload a video through the real file input');
    await page.setInputFiles('#fileInput', VIDEO);
    await page.waitForFunction(
      () => document.getElementById('mediaMetaPill').style.display !== 'none',
      { timeout: 60000 });
    await page.waitForTimeout(2500);
    const metaName = await page.textContent('#metaFileName');
    const metaRes = await page.textContent('#metaResolution');
    console.log(`   loaded: ${metaName}  ${metaRes}`);

    step('6. hash button state after loading');
    disabled = await page.isDisabled('#btnRunHashing');
    label = await page.textContent('#btnRunHashingLabel');
    console.log(`   disabled=${disabled} label="${label}"`);
    if (disabled) throw new Error('hash button should be enabled once a video is loaded');

    step('7. open the Anti-Detection tab and screenshot');
    await page.click('#tabBtnHashing');
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SHOTS, '1-hashing-tab.png') });
    console.log('   saved 1-hashing-tab.png');

    step('8. click Run Content Hashing');
    await page.click('#btnRunHashing');
    await page.waitForSelector('#modalProcessingState', { state: 'visible', timeout: 20000 });
    console.log('   modal opened');

    // Watch the stage label + progress bar move while the job runs.
    const seenStages = new Set();
    const seenProgress = [];
    const deadline = Date.now() + 240000;
    while (Date.now() < deadline) {
      const st = await page.evaluate(() => ({
        stage: document.getElementById('modalStageLabel').textContent,
        elapsed: document.getElementById('modalElapsed').textContent,
        width: document.getElementById('exportProgressBar').style.width,
        indeterminate: document.getElementById('exportProgressBar').classList.contains('indeterminate'),
        done: document.getElementById('modalSuccessState').style.display !== 'none',
      }));
      if (!seenStages.has(st.stage)) {
        seenStages.add(st.stage);
        console.log(`   [${st.elapsed}] stage: ${st.stage}  bar=${st.width || '(indeterminate)'}`);
      }
      if (!st.indeterminate && st.width) seenProgress.push(st.width);
      if (st.done) break;
      await page.waitForTimeout(700);
    }

    step('9. progress bar actually moved');
    const distinct = [...new Set(seenProgress)];
    console.log(`   distinct widths seen: ${distinct.length ? distinct.slice(0, 8).join(', ') : 'NONE'}`);
    if (distinct.length < 3) throw new Error('progress bar did not advance - it is still decorative');

    step('10. result state');
    const res = await page.evaluate(() => ({
      hash: document.getElementById('resHashStatus').textContent,
      profile: document.getElementById('resProfileUsed').textContent,
      dims: document.getElementById('resDimensions').textContent,
      dur: document.getElementById('resDuration').textContent,
      size: document.getElementById('resFileSize').textContent,
      title: document.getElementById('modalSuccessTitle').textContent,
      videoSrc: document.getElementById('modalOutputVideo').getAttribute('src'),
      download: document.getElementById('btnDownloadExport').getAttribute('href'),
    }));
    console.log(`   ${res.title}`);
    console.log(`   hashing=${res.hash} profile=${res.profile} ${res.dims} ${res.dur} ${res.size}`);
    console.log(`   preview=${res.videoSrc}`);
    console.log(`   download=${res.download}`);
    await page.screenshot({ path: path.join(SHOTS, '2-hash-complete.png') });
    console.log('   saved 2-hash-complete.png');

    step('11. close modal, check the result card in the sidebar');
    await page.click('#btnCloseModal');
    await page.waitForTimeout(500);
    const card = await page.evaluate(() => ({
      visible: document.getElementById('hashResultCard').style.display !== 'none',
      stale: document.getElementById('hashResultCard').classList.contains('is-stale'),
      profile: document.getElementById('hashResProfile').textContent,
      badge: document.getElementById('hashResultBadge').textContent,
      exportLabel: document.getElementById('btnExportLabel').textContent,
    }));
    console.log(`   card visible=${card.visible} stale=${card.stale} badge=${card.badge}`);
    console.log(`   profile=${card.profile} export button="${card.exportLabel}"`);
    if (!card.visible) throw new Error('hash result card should be visible after hashing');
    if (card.stale) throw new Error('hash result card should not be stale immediately after hashing');

    const inView = await page.evaluate(() => {
      const el = document.getElementById('hashResultCard');
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top), bottom: Math.round(r.bottom),
               vh: window.innerHeight,
               fullyVisible: r.top >= 0 && r.bottom <= window.innerHeight + 4 && r.height > 0 };
    });
    console.log(`   card rect top=${inView.top} bottom=${inView.bottom} viewportH=${inView.vh}`);
    if (!inView.fullyVisible) {
      throw new Error('result card is off-screen - the user cannot see it after hashing');
    }
    console.log('   card is fully on screen');
    await page.screenshot({ path: path.join(SHOTS, '3-result-card.png') });
    console.log('   saved 3-result-card.png');

    step('12. change an edit -> card must go stale');
    await page.click('#tabBtnColor');
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      const s = document.getElementById('sliderBrightness');
      s.value = '0.2';
      s.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await page.waitForTimeout(400);
    await page.click('#tabBtnHashing');
    await page.waitForTimeout(400);
    const stale = await page.evaluate(() => ({
      stale: document.getElementById('hashResultCard').classList.contains('is-stale'),
      note: document.getElementById('hashStaleNote').style.display !== 'none',
      exportLabel: document.getElementById('btnExportLabel').textContent,
    }));
    console.log(`   stale=${stale.stale} note shown=${stale.note} export="${stale.exportLabel}"`);
    if (!stale.stale) throw new Error('changing an edit should mark the hash stale');
    await page.screenshot({ path: path.join(SHOTS, '4-stale-warning.png') });
    console.log('   saved 4-stale-warning.png');

    step('13. export is refused while stale');
    await page.click('#btnExportVideo');
    await page.waitForTimeout(1500);
    // Read the NEWEST toast - older ones linger for 4s and would give a false pass.
    const toast = await page.evaluate(() => {
      const all = document.querySelectorAll('.toast');
      const t = all[all.length - 1];
      return t ? t.textContent.trim() : null;
    });
    console.log(`   toast: ${toast}`);
    if (!toast || !/hashing again|run content hashing/i.test(toast)) {
      throw new Error('expected a "run Content Hashing again" warning, got: ' + toast);
    }

    step('14. restore the edit and export for real');
    await page.click('#tabBtnColor');
    await page.evaluate(() => {
      const s = document.getElementById('sliderBrightness');
      s.value = '0';
      s.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await page.click('#btnExportVideo');
    await page.waitForSelector('#modalSuccessState', { state: 'visible', timeout: 60000 });
    const exportRes = await page.evaluate(() => ({
      title: document.getElementById('modalSuccessTitle').textContent,
      download: document.getElementById('btnDownloadExport').getAttribute('href'),
    }));
    console.log(`   ${exportRes.title}`);
    console.log(`   download=${exportRes.download}`);
    await page.screenshot({ path: path.join(SHOTS, '5-export.png') });
    console.log('   saved 5-export.png');

  } catch (e) {
    console.log(`\n!!! FAILED: ${e.message}`);
    try {
      await page.screenshot({ path: path.join(SHOTS, 'failure.png') });
      console.log('   saved failure.png');
    } catch (_) {}
    process.exitCode = 1;
  } finally {
    step('console / page errors');
    console.log(`   page errors   : ${errors.length}`);
    errors.forEach(e => console.log(`     - ${e}`));
    console.log(`   console errors: ${consoleErrors.length}`);
    consoleErrors.forEach(e => console.log(`     - ${e}`));
    console.log(`   failed requests: ${failedRequests.length}`);
    failedRequests.forEach(e => console.log(`     - ${e}`));
    if (errors.length) process.exitCode = 1;
    await browser.close();
  }
})();
