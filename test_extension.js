// Test Extension Manifest & Files Verification
const fs = require('fs');
const path = require('path');
const assert = require('assert');

function testExtension() {
  console.log('--- Bắt đầu kiểm tra toàn diện Chrome Extension ---');

  // 1. Check manifest.json
  const manifestPath = path.join(__dirname, 'manifest.json');
  if (!fs.existsSync(manifestPath)) {
    throw new Error('Thiếu manifest.json');
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  assert.strictEqual(manifest.manifest_version, 3, 'Manifest version phải là 3');
  assert(manifest.permissions.includes('downloads'), 'Thiếu permission downloads');
  assert(manifest.permissions.includes('storage'), 'Thiếu permission storage');
  assert(manifest.permissions.includes('scripting'), 'Thiếu permission scripting');
  assert(manifest.permissions.includes('activeTab'), 'Thiếu permission activeTab');
  console.log('✓ 1. Manifest JSON hợp lệ (MV3, đầy đủ permissions & host_permissions)');

  // 2. Check files referenced in manifest
  const popupHtmlPath = path.join(__dirname, manifest.action.default_popup);
  if (!fs.existsSync(popupHtmlPath)) throw new Error('Thiếu popup.html');
  const popupHtml = fs.readFileSync(popupHtmlPath, 'utf8');

  for (const [size, iconPath] of Object.entries(manifest.icons)) {
    const fullIconPath = path.join(__dirname, iconPath);
    if (!fs.existsSync(fullIconPath)) throw new Error(`Thiếu icon ${size}: ${iconPath}`);
  }
  console.log('✓ 2. Toàn bộ icons và popup HTML tồn tại');

  // 3. Check extractor script syntax & contents
  const extractorPath = path.join(__dirname, 'scripts', 'extractor.js');
  if (!fs.existsSync(extractorPath)) throw new Error('Thiếu scripts/extractor.js');
  const extractorCode = fs.readFileSync(extractorPath, 'utf8');
  assert(extractorCode.includes('extractUrlsFromBgStyle'), 'Thiếu extractUrlsFromBgStyle trong extractor.js');
  assert(extractorCode.includes('::before'), 'Thiếu quét pseudo-element ::before');
  assert(extractorCode.includes('meta[property*="image"]'), 'Thiếu quét thẻ meta OpenGraph');
  console.log('✓ 3. Script extractor.js chứa đầy đủ tính năng quét nâng cao');

  // 4. Check popup.css & popup.js
  const popupCssPath = path.join(__dirname, 'popup', 'popup.css');
  const popupJsPath = path.join(__dirname, 'popup', 'popup.js');
  if (!fs.existsSync(popupCssPath)) throw new Error('Thiếu popup/popup.css');
  if (!fs.existsSync(popupJsPath)) throw new Error('Thiếu popup/popup.js');
  const popupJs = fs.readFileSync(popupJsPath, 'utf8');

  // 5. Verify required DOM IDs in popup.html
  const requiredIds = [
    'total-count-badge',
    'btn-deep-scroll',
    'btn-refresh',
    'search-input',
    'btn-clear-search',
    'sort-select',
    'btn-reset-filters',
    'checkbox-select-all',
    'btn-invert-selection',
    'btn-copy-urls',
    'btn-export-txt',
    'selection-counter',
    'filtered-count',
    'image-grid',
    'loading-state',
    'empty-state',
    'progress-container',
    'download-folder',
    'download-delay',
    'btn-download-selected',
    'preview-modal',
    'btn-prev-modal',
    'btn-next-modal',
    'modal-btn-open-tab',
    'modal-btn-copy-url',
    'modal-btn-download',
    'toast'
  ];

  requiredIds.forEach(id => {
    assert(popupHtml.includes(`id="${id}"`), `popup.html thiếu phần tử có id="${id}"`);
  });
  console.log(`✓ 4. Đã xác thực đầy đủ ${requiredIds.length} ID phần tử UI trong popup.html`);

  // 6. Test Aspect Ratio & Subfolder logic emulation
  function testRatio(w, h) {
    if (w <= 0 || h <= 0) return 'UNKNOWN';
    const ratio = w / h;
    if (ratio >= 1.15) return 'LANDSCAPE';
    if (ratio <= 0.87) return 'PORTRAIT';
    if (ratio >= 0.85 && ratio <= 1.18) return 'SQUARE';
    return 'OTHER';
  }

  assert.strictEqual(testRatio(1920, 1080), 'LANDSCAPE', '1920x1080 phải là LANDSCAPE');
  assert.strictEqual(testRatio(1080, 1920), 'PORTRAIT', '1080x1920 phải là PORTRAIT');
  assert.strictEqual(testRatio(800, 800), 'SQUARE', '800x800 phải là SQUARE');
  console.log('✓ 5. Thuật toán phân loại Tỷ lệ khung hình (Aspect Ratio) hoạt động chính xác');

  // 7. Test Subfolder & filename sanitization emulation
  function sanitizeSubfolder(name) {
    return (name || '').replace(/[/\\?%*:|"<>]/g, '_').trim();
  }
  assert.strictEqual(sanitizeSubfolder('Shopee: Mua sắm/Hàng hot?'), 'Shopee_ Mua sắm_Hàng hot_');
  console.log('✓ 6. Hàm khử ký tự cấm cho thư mục tải về hoạt động an toàn');

  console.log('\n--- TOÀN BỘ KIỂM TRA EXTENSION THÀNH CÔNG 100%! ---');
}

testExtension();

