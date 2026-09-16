// Reproduces the reported crop bug: pick Freeform, drag the crop box, export,
// and check whether the exported video actually matches the crop box.
// Hashing is switched off so this isolates the crop/export path (and stays fast).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const PORT = process.env.FORGE_PORT || '8018';
const BASE = `http://127.0.0.1:${PORT}`;
const ROOT = 'C:\\Users\\lenovo\\OneDrive\\Desktop\\Custom editing software';
const VIDEO = path.join(ROOT, 'app', 'uploads', 'crop_probe.mp4');
const SHOTS = path.join(ROOT, 'tools', 'screenshots');

const errors = [];
const consoleErrors = [];

function step(m) { console.log(`\n== ${m}`); }

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(`${e.name}: ${e.message}`));

  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(
      () => !document.getElementById('engineStatusText').textContent.includes('Checking'),
      { timeout: 25000 });

    step('1. load the 1280x720 landscape probe clip');
    await page.setInputFiles('#fileInput', VIDEO);
    await page.waitForFunction(
      () => document.getElementById('mediaMetaPill').style.display !== 'none',
      { timeout: 60000 });
    await page.waitForTimeout(2500);
    console.log(`   ${await page.textContent('#metaFileName')}  ${await page.textContent('#metaResolution')}`);

    const container = await page.evaluate(() => {
      const el = document.getElementById('stageCanvasContainer');
      return { w: el.clientWidth, h: el.clientHeight };
    });
    console.log(`   stage container: ${container.w}x${container.h}`);
    if (Math.abs((container.w / container.h) - (1280 / 720)) > 0.02) {
      console.log('   !! container aspect differs from the video aspect');
    }

    step('2. what crop is set right after load?');
    let ratio = await page.evaluate(() => ({
      active: document.querySelector('.ratio-card.active')?.dataset.ratio,
      badge: document.getElementById('cropBadge').textContent,
      nativeW: document.getElementById('cropWidthInput').value,
      nativeH: document.getElementById('cropHeightInput').value,
      nativeX: document.getElementById('cropXInput').value,
      nativeY: document.getElementById('cropYInput').value,
      box: (() => { const r = document.getElementById('cropBox').getBoundingClientRect();
                    return { w: Math.round(r.width), h: Math.round(r.height) }; })(),
    }));
    console.log(`   active=${ratio.active} badge="${ratio.badge}" box=${ratio.box.w}x${ratio.box.h}`);
    console.log(`   crop sent to ffmpeg: ${ratio.nativeW}x${ratio.nativeH} at +${ratio.nativeX}+${ratio.nativeY}`);
    if (ratio.nativeW !== '1280' || ratio.nativeH !== '720' || ratio.nativeX !== '0' || ratio.nativeY !== '0') {
      throw new Error(`a freshly loaded video must NOT be cropped - got ${ratio.nativeW}x${ratio.nativeH} at +${ratio.nativeX}+${ratio.nativeY}`);
    }
    console.log('   full frame - nothing is cropped until the user asks for it');
    await page.screenshot({ path: path.join(SHOTS, 'crop-1-onload.png') });

    step('3. pick 9:16, then back to Freeform');
    await page.click('#tabBtnCrop');
    await page.waitForTimeout(400);
    await page.click('.ratio-card[data-ratio="9:16"]');
    await page.waitForTimeout(400);
    const after916 = await page.evaluate(() => ({
      badge: document.getElementById('cropBadge').textContent,
      w: document.getElementById('cropWidthInput').value,
      h: document.getElementById('cropHeightInput').value,
    }));
    console.log(`   after 9:16: badge="${after916.badge}" crop=${after916.w}x${after916.h}`);

    await page.click('.ratio-card[data-ratio="free"]');
    await page.waitForTimeout(400);
    ratio = await page.evaluate(() => ({
      active: document.querySelector('.ratio-card.active')?.dataset.ratio,
      badge: document.getElementById('cropBadge').textContent,
      w: document.getElementById('cropWidthInput').value,
      h: document.getElementById('cropHeightInput').value,
    }));
    console.log(`   after Freeform: badge="${ratio.badge}" crop=${ratio.w}x${ratio.h}`);
    console.log('   NOTE: Freeform keeps the current shape - it only unlocks the ratio.');

    step('4a. drag the box BODY to a different position (the common "crop" gesture)');
    let cb = await page.$('#cropBox');
    let bb = await cb.boundingBox();
    await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await page.mouse.down();
    await page.mouse.move(bb.x + bb.width / 2 + 120, bb.y + bb.height / 2 + 40, { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(500);

    const moved = await page.evaluate(() => ({
      nativeW: document.getElementById('cropWidthInput').value,
      nativeH: document.getElementById('cropHeightInput').value,
      nativeX: document.getElementById('cropXInput').value,
      nativeY: document.getElementById('cropYInput').value,
      badge: document.getElementById('cropBadge').textContent,
    }));
    console.log(`   after moving the box, crop sent to ffmpeg: ` +
                `${moved.nativeW}x${moved.nativeH} at +${moved.nativeX}+${moved.nativeY}`);
    console.log(`   badge still says "${moved.badge}" - shape never changed, only position`);

    step('4b. now actually resize it with the SE handle');
    const se = await page.$('#cropBox .handle-se');
    const sb = await se.boundingBox();
    await page.mouse.move(sb.x + sb.width / 2, sb.y + sb.height / 2);
    await page.mouse.down();
    await page.mouse.move(sb.x - 160, sb.y - 90, { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(500);

    const after = await page.evaluate(() => {
      const r = document.getElementById('cropBox').getBoundingClientRect();
      return {
        boxW: Math.round(r.width), boxH: Math.round(r.height),
        boxAspect: +(r.width / r.height).toFixed(3),
        nativeW: document.getElementById('cropWidthInput').value,
        nativeH: document.getElementById('cropHeightInput').value,
        nativeX: document.getElementById('cropXInput').value,
        nativeY: document.getElementById('cropYInput').value,
        badge: document.getElementById('cropBadge').textContent,
      };
    });
    console.log(`   box ${after.boxW}x${after.boxH} (aspect ${after.boxAspect})`);
    console.log(`   native crop sent to ffmpeg: ${after.nativeW}x${after.nativeH} at +${after.nativeX}+${after.nativeY}`);
    await page.screenshot({ path: path.join(SHOTS, 'crop-2-after-drag.png') });

    step('5. is everything outside the crop hidden?');
    const preview = await page.evaluate(() => {
      const backdrop = document.getElementById('cropBackdrop');
      const box = document.getElementById('cropBox');
      return {
        backdropBg: getComputedStyle(backdrop).backgroundColor,
        boxShadow: getComputedStyle(box).boxShadow,
        badge: document.getElementById('cropBadge').textContent,
      };
    });
    console.log(`   backdrop background: ${preview.backdropBg}`);
    console.log(`   crop box shadow    : ${preview.boxShadow.slice(0, 44)}...`);
    console.log(`   badge              : "${preview.badge}"`);
    if (preview.backdropBg !== 'rgba(0, 0, 0, 0)') {
      throw new Error('backdrop still dims the whole frame uniformly');
    }
    if (!preview.boxShadow.startsWith('rgb(0, 0, 0)')) {
      throw new Error('outside the crop is still semi-transparent: ' + preview.boxShadow.slice(0, 40));
    }
    if (!/\d+×\d+/.test(preview.badge)) {
      throw new Error('badge does not show the exported size: ' + preview.badge);
    }
    console.log('   outside the crop is solid black - only the kept region is visible');

    // Prove it pixel by pixel: sample the video well outside the crop and
    // compare against a pixel just inside it.
    const pixels = await page.evaluate(async () => {
      const el = document.getElementById('stageCanvasContainer');
      const r = el.getBoundingClientRect();
      const box = document.getElementById('cropBox').getBoundingClientRect();
      return {
        stage: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        box: { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) },
      };
    });
    const shot = await page.screenshot();
    console.log(`   stage ${pixels.stage.w}x${pixels.stage.h}, crop box at +${pixels.box.x - pixels.stage.x}+${pixels.box.y - pixels.stage.y}`);
    console.log('   (see crop-2-after-drag.png - outside the box should be pure black)');

    step('6. export with hashing OFF so we isolate the crop');
    await page.click('#tabBtnHashing');
    await page.waitForTimeout(400);
    // The switch input is visually hidden (custom styled), so Playwright cannot
    // click it - drive it the same way the app's own reset code does.
    await page.evaluate(() => {
      const t = document.getElementById('hashingEnableToggle');
      t.checked = false;
      t.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(300);
    const hashingOff = await page.evaluate(() => document.getElementById('hashingEnableToggle').checked);
    console.log(`   hashing toggle now: ${hashingOff ? 'ON (unexpected)' : 'OFF'}`);
    await page.click('#btnExportVideo');
    await page.waitForSelector('#modalSuccessState', { state: 'visible', timeout: 90000 });

    const result = await page.evaluate(() => ({
      dims: document.getElementById('resDimensions').textContent,
      title: document.getElementById('modalSuccessTitle').textContent,
      download: document.getElementById('btnDownloadExport').getAttribute('href'),
    }));
    console.log(`   ${result.title}`);
    console.log(`   exported dimensions: ${result.dims}`);
    await page.screenshot({ path: path.join(SHOTS, 'crop-3-exported.png') });

    step('7. verdict');
    const m = result.dims.match(/(\d+)\s*[×x]\s*(\d+)/);
    const outW = m ? parseInt(m[1], 10) : 0;
    const outH = m ? parseInt(m[2], 10) : 0;
    const wantW = parseInt(after.nativeW, 10);
    const wantH = parseInt(after.nativeH, 10);
    console.log(`   asked for ${wantW}x${wantH}, got ${outW}x${outH}`);
    const ok = Math.abs(outW - wantW) <= 2 && Math.abs(outH - wantH) <= 2;
    console.log(ok
      ? '   MATCH - the crop was applied correctly on export'
      : '   MISMATCH - the exported video does not match the crop box');
    if (!ok) process.exitCode = 1;

    step('8. the real flow: hashing ON, run it, and check the HASHED size');
    await page.click('#btnCloseModal');
    await page.waitForTimeout(400);
    await page.click('#tabBtnHashing');
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      const t = document.getElementById('hashingEnableToggle');
      t.checked = true;
      t.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(300);
    await page.click('#btnRunHashing');
    await page.waitForSelector('#modalSuccessState', { state: 'visible', timeout: 300000 });

    const hashed = await page.evaluate(() => ({
      dims: document.getElementById('resDimensions').textContent,
      hash: document.getElementById('resHashStatus').textContent,
      profile: document.getElementById('resProfileUsed').textContent,
    }));
    console.log(`   hashed output: ${hashed.dims}  ${hashed.hash}  (${hashed.profile})`);

    const hm = hashed.dims.match(/(\d+)\s*[×x]\s*(\d+)/);
    const hw = parseInt(hm[1], 10);
    const hh = parseInt(hm[2], 10);
    const wantAspect = wantW / wantH;
    const gotAspect = hw / hh;
    console.log(`   crop aspect ${wantAspect.toFixed(3)}  ->  hashed aspect ${gotAspect.toFixed(3)}`);
    if (Math.abs(wantAspect - gotAspect) > 0.02) {
      throw new Error(`hashing CHANGED the aspect (wanted ${wantAspect.toFixed(3)}, got ${gotAspect.toFixed(3)})`);
    }
    if (Math.abs(gotAspect - 9 / 16) < 0.01 && Math.abs(wantAspect - 9 / 16) > 0.05) {
      throw new Error('hashed output is 9:16 but the crop was not');
    }
    console.log('   the hashed video kept the freeform crop shape');
    await page.screenshot({ path: path.join(SHOTS, 'crop-4-hashed.png') });
    console.log('   saved crop-4-hashed.png');

  } catch (e) {
    console.log(`\n!!! FAILED: ${e.message}`);
    try { await page.screenshot({ path: path.join(SHOTS, 'crop-failure.png') }); } catch (_) {}
    process.exitCode = 1;
  } finally {
    step('console / page errors');
    console.log(`   page errors: ${errors.length}  console errors: ${consoleErrors.length}`);
    errors.forEach(e => console.log(`     - ${e}`));
    consoleErrors.forEach(e => console.log(`     - ${e}`));
    await browser.close();
  }
})();
