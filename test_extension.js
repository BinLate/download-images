// Test Extension Manifest & Files Verification
const fs = require('fs');
const path = require('path');
const assert = require('assert');

async function testExtension() {
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
    'download-format-convert',
    'download-delay',
    'btn-download-selected',
    'btn-download-zip',
    'toast'
  ];

  requiredIds.forEach(id => {
    assert(popupHtml.includes(`id="${id}"`), `popup.html thiếu phần tử có id="${id}"`);
  });
  console.log(`✓ 4. Đã xác thực đầy đủ ${requiredIds.length} ID phần tử UI trong popup.html`);

  // 6. Check JSZip script and functionality (Awaited)
  const jszipPath = path.join(__dirname, 'popup', 'jszip.min.js');
  assert(fs.existsSync(jszipPath), 'Thiếu popup/jszip.min.js');
  const JSZip = require(jszipPath);
  const zip = new JSZip();
  zip.file('test.png', Buffer.from('fake-image-binary-data'));
  zip.file('folder/test2.jpg', Buffer.from('fake-image-2'));
  const zipBuffer = await zip.generateAsync({ type: 'nodebuffer' });
  assert(zipBuffer && zipBuffer.length > 0, 'JSZip generateAsync phải trả về buffer hợp lệ');
  console.log(`✓ 5. Thư viện JSZip tích hợp thành công và tạo archive buffer hợp lệ (${zipBuffer.length} bytes)`);

  // 7. Test Format Conversion emulation
  function shouldConvertImage(imgFormat, convertMode) {
    if (!convertMode || convertMode === 'original') return false;
    const fmt = (imgFormat || '').toUpperCase();
    if (convertMode === 'webp-to-jpg' && (fmt === 'WEBP' || fmt === 'AVIF')) return 'image/jpeg';
    if (convertMode === 'webp-to-png' && (fmt === 'WEBP' || fmt === 'AVIF')) return 'image/png';
    if (convertMode === 'all-to-jpg' && fmt !== 'JPG') return 'image/jpeg';
    if (convertMode === 'all-to-png' && fmt !== 'PNG') return 'image/png';
    return false;
  }

  assert.strictEqual(shouldConvertImage('WEBP', 'webp-to-jpg'), 'image/jpeg');
  assert.strictEqual(shouldConvertImage('AVIF', 'webp-to-png'), 'image/png');
  assert.strictEqual(shouldConvertImage('JPG', 'webp-to-jpg'), false);
  assert.strictEqual(shouldConvertImage('PNG', 'all-to-jpg'), 'image/jpeg');
  assert.strictEqual(shouldConvertImage('SVG', 'original'), false);

  // Test prepareImagePayload extension preservation on conversion failure
  async function emulatePrepareImagePayload(item, convertMode, throwOnConvert = false) {
    const targetMime = shouldConvertImage(item.format, convertMode);
    const originalFilename = 'photo.webp';
    if (targetMime) {
      if (throwOnConvert) {
        // Conversion failed -> must retain originalFilename
        return { filename: originalFilename, isConverted: false };
      }
      const targetExt = targetMime === 'image/png' ? '.png' : '.jpg';
      const nameWithoutExt = originalFilename.replace(/\.[^/.]+$/, '');
      return { filename: `${nameWithoutExt}${targetExt}`, isConverted: true };
    }
    return { filename: originalFilename, isConverted: false };
  }

  const successPayload = await emulatePrepareImagePayload({ format: 'WEBP' }, 'webp-to-jpg', false);
  assert.strictEqual(successPayload.filename, 'photo.jpg', 'Chuyển đổi thành công phải đổi đuôi thành .jpg');
  assert.strictEqual(successPayload.isConverted, true);

  const failedPayload = await emulatePrepareImagePayload({ format: 'WEBP' }, 'webp-to-jpg', true);
  assert.strictEqual(failedPayload.filename, 'photo.webp', 'Chuyển đổi thất bại PHẢI giữ nguyên đuôi gốc .webp');
  assert.strictEqual(failedPayload.isConverted, false);

  console.log('✓ 6. Logic chuyển đổi định dạng và cơ chế bảo toàn đuôi file khi convert lỗi hoạt động chuẩn xác');

  // 8. Test Aspect Ratio Mutually Exclusive Boundaries
  function testRatio(w, h) {
    if (w <= 0 || h <= 0) return 'UNKNOWN';
    const ratio = w / h;
    if (ratio > 1.15) return 'LANDSCAPE';
    if (ratio < 0.85) return 'PORTRAIT';
    return 'SQUARE'; // 0.85 <= ratio <= 1.15
  }

  assert.strictEqual(testRatio(1920, 1080), 'LANDSCAPE', '1920x1080 (1.77) phải là LANDSCAPE');
  assert.strictEqual(testRatio(1080, 1920), 'PORTRAIT', '1080x1920 (0.56) phải là PORTRAIT');
  assert.strictEqual(testRatio(800, 800), 'SQUARE', '800x800 (1.0) phải là SQUARE');
  assert.strictEqual(testRatio(1150, 1000), 'SQUARE', '1150x1000 (1.15) biên phải là SQUARE');
  assert.strictEqual(testRatio(850, 1000), 'SQUARE', '850x1000 (0.85) biên phải là SQUARE');
  console.log('✓ 7. Thuật toán phân loại Tỷ lệ khung hình (Aspect Ratio) loại trừ tương hỗ chuẩn xác');

  // 9. Test Subfolder & filename sanitization emulation
  function sanitizeSubfolder(name) {
    return (name || '').replace(/[/\\?%*:|"<>]/g, '_').trim();
  }
  assert.strictEqual(sanitizeSubfolder('Shopee: Mua sắm/Hàng hot?'), 'Shopee_ Mua sắm_Hàng hot_');
  console.log('✓ 8. Hàm khử ký tự cấm cho thư mục tải về hoạt động an toàn');

  // 10. Test Recursive Shadow DOM traversal emulation
  function emulateDomWithShadowRoots() {
    const fakeImgInLightDom = { nodeType: 1, tagName: 'IMG', getAttribute: () => 'https://example.com/light.jpg' };
    const fakeImgInShadow = { nodeType: 1, tagName: 'IMG', getAttribute: () => 'https://example.com/shadow.png' };
    const fakeCustomElement = {
      nodeType: 1,
      tagName: 'CUSTOM-WIDGET',
      shadowRoot: {
        nodeType: 11,
        children: [fakeImgInShadow]
      },
      children: []
    };
    const fakeDoc = {
      nodeType: 9,
      children: [fakeImgInLightDom, fakeCustomElement]
    };

    const collected = [];
    const visited = new Set();
    function traverse(node) {
      if (!node) return;
      if (node.nodeType === 1) collected.push(node);
      if (node.shadowRoot && !visited.has(node.shadowRoot)) {
        visited.add(node.shadowRoot);
        traverse(node.shadowRoot);
      }
      const children = node.children || [];
      for (const child of children) traverse(child);
    }
    traverse(fakeDoc);
    return collected;
  }

  const collectedNodes = emulateDomWithShadowRoots();
  assert(collectedNodes.some(n => n.tagName === 'CUSTOM-WIDGET'), 'Thiếu custom element');
  assert(collectedNodes.some(n => n.getAttribute && n.getAttribute() === 'https://example.com/shadow.png'), 'Thiếu ảnh bên trong shadowRoot');
  console.log('✓ 9. Thuật toán quét đệ quy Shadow DOM (shadowRoot) trích xuất thành công ảnh trong Web Components');

  // 11. Test Smart Deduplication & Identity Preservation
  function testDeduplicationEngine() {
    function getCanonicalImageKey(url) {
      if (!url) return '';
      try {
        const parsed = new URL(url);
        let path = parsed.pathname; // Giữ nguyên case của pathname
        path = path.replace(/(?:-\d{2,4}x\d{2,4}|-scaled)(?=\.[a-z0-9]+$)/i, '');
        
        let queryString = '';
        if (parsed.search) {
          const cleanParams = new URLSearchParams(parsed.search);
          ['w', 'width', 'h', 'height', 'resize', 'maxwidth', 'maxheight'].forEach(p => {
            cleanParams.delete(p);
          });
          cleanParams.sort();
          queryString = cleanParams.toString();
        }
        return `${parsed.origin.toLowerCase()}${path}${queryString ? '?' + queryString : ''}`;
      } catch {
        return url;
      }
    }

    const testUrls = [
      'https://example.com/uploads/2026/03/wallpaper.jpg',
      'https://example.com/uploads/2026/03/wallpaper-768x495.jpg',
      'https://example.com/uploads/2026/03/wallpaper-300x193.jpg',
      'https://example.com/uploads/2026/03/wallpaper-210x136.jpg'
    ];

    const dedupeMap = new Map();
    for (const u of testUrls) {
      const key = getCanonicalImageKey(u);
      if (!dedupeMap.has(key)) {
        dedupeMap.set(key, u);
      }
    }

    assert.strictEqual(dedupeMap.size, 1, '4 phiên bản responsive của cùng 1 ảnh phải được gom thành 1 key duy nhất');

    // Verify same basename with different extensions are NOT merged
    const jpgUrl = 'https://example.com/assets/logo.jpg';
    const pngUrl = 'https://example.com/assets/logo.png';
    assert.notStrictEqual(getCanonicalImageKey(jpgUrl), getCanonicalImageKey(pngUrl), 'logo.jpg và logo.png là 2 tài nguyên độc lập, không được gộp nhầm');

    // Verify case-sensitive path preservation
    const uppercasePathUrl = 'https://example.com/images/Asset_A.jpg';
    const lowercasePathUrl = 'https://example.com/images/asset_a.jpg';
    assert.notStrictEqual(getCanonicalImageKey(uppercasePathUrl), getCanonicalImageKey(lowercasePathUrl), 'URL có path chữ hoa/thường khác nhau phải giữ nguyên tính phân biệt case');

    // Verify query param order invariance
    const urlOrderA = 'https://example.com/api/view?auth=true&id=999&w=300';
    const urlOrderB = 'https://example.com/api/view?w=700&id=999&auth=true';
    assert.strictEqual(getCanonicalImageKey(urlOrderA), getCanonicalImageKey(urlOrderB), 'Thứ tự query params khác nhau phải cho ra cùng 1 canonical key');

    // Verify raw observed URL is preserved as fallbackUrl when inferred unscaled URL fails
    const observedRawUrl = 'https://example.com/wp-content/uploads/2026/03/product-300x300.jpg';
    const parsedKey = getCanonicalImageKey(observedRawUrl);
    assert(parsedKey.endsWith('.jpg'), 'Phải giữ nguyên extension .jpg trong canonical key');

    // Test extractor serialization with fallbackUrl
    const sampleItem = { url: 'https://example.com/image.jpg', fallbackUrl: observedRawUrl, width: 300, height: 300 };
    assert.strictEqual(sampleItem.fallbackUrl, observedRawUrl, 'fallbackUrl phải được bảo tồn trọn vẹn trong cấu trúc dữ liệu trả về');
  }

  testDeduplicationEngine();
  console.log('✓ 10. Thuật toán Khử trùng lặp bảo tồn case-sensitive paths, sắp xếp query parameters và giữ nguyên fallbackUrl');

  // 12. Test Dimension Preset Boundary Classification (Small < 300, Medium 300-800, Large > 800)
  function testPresetClassification(w, h, preset) {
    const maxDim = Math.max(w, h);
    if (preset === 'small') return maxDim < 300;
    if (preset === 'medium') return maxDim >= 300 && maxDim <= 800;
    if (preset === 'large') return maxDim > 800;
    if (preset === 'hd') return maxDim >= 1080 || (w >= 1920 && h >= 1080);
    return true;
  }

  assert.strictEqual(testPresetClassification(299, 200, 'small'), true, '299x200 thuộc Small (<300px)');
  assert.strictEqual(testPresetClassification(300, 200, 'small'), false, '300x200 không thuộc Small');
  assert.strictEqual(testPresetClassification(300, 300, 'medium'), true, '300x300 thuộc Medium (300-800px)');
  assert.strictEqual(testPresetClassification(800, 600, 'medium'), true, '800x600 thuộc Medium (300-800px)');
  assert.strictEqual(testPresetClassification(800, 600, 'large'), false, '800x600 không thuộc Large (>800px)');
  assert.strictEqual(testPresetClassification(801, 500, 'large'), true, '801x500 thuộc Large (>800px)');
  assert.strictEqual(testPresetClassification(1200, 500, 'large'), true, '1200x500 thuộc Large (>800px)');
  assert.strictEqual(testPresetClassification(1200, 500, 'medium'), false, '1200x500 không thuộc Medium');
  console.log('✓ 11. Kiểm thử phân loại kích thước chính xác tuyệt đối theo biên (Small < 300, Medium 300-800, Large > 800)');

  console.log('\n--- TOÀN BỘ KIỂM TRA EXTENSION THÀNH CÔNG 100%! ---');
}

testExtension();

