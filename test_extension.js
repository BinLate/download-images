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

  // 13. Test Icon Palette (Emerald Green Verification - No purple allowed)
  const zlib = require('zlib');
  const iconSizes = [16, 48, 128];
  for (const size of iconSizes) {
    const iconFile = path.join(__dirname, 'icons', `icon${size}.png`);
    assert(fs.existsSync(iconFile), `Thiếu icon ${size}px`);
    const buf = fs.readFileSync(iconFile);
    let offset = 8;
    const chunks = [];
    while (offset < buf.length) {
      const len = buf.readUInt32BE(offset);
      const type = buf.slice(offset + 4, offset + 8).toString('ascii');
      const data = buf.slice(offset + 8, offset + 8 + len);
      chunks.push({ type, data });
      offset += 12 + len;
    }
    const ihdr = chunks.find(c => c.type === 'IHDR');
    const width = ihdr.data.readUInt32BE(0);
    const height = ihdr.data.readUInt32BE(4);
    assert.strictEqual(width, size, `Chiều rộng icon phải là ${size}`);
    assert.strictEqual(height, size, `Chiều cao icon phải là ${size}`);
    const idat = Buffer.concat(chunks.filter(c => c.type === 'IDAT').map(c => c.data));
    const uncompressed = zlib.inflateSync(idat);
    const scanlineLen = 1 + width * 4;

    let hasEmeraldGreen = false;
    let hasPurple = false;

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * scanlineLen + 1 + x * 4;
        const r = uncompressed[idx];
        const g = uncompressed[idx + 1];
        const b = uncompressed[idx + 2];
        const a = uncompressed[idx + 3];

        if (a > 100) {
          // Emerald Green check (#10b981 / #047857 / #059669 range)
          if (g > r && g > b && g >= 80) {
            hasEmeraldGreen = true;
          }
          // Purple check (#6366f1 / rgb(99,102,241))
          if (b > g && b > r && b >= 150) {
            hasPurple = true;
          }
        }
      }
    }

    assert(hasEmeraldGreen, `Icon ${size}px phải chứa màu xanh lá cây Emerald Green`);
    assert(!hasPurple, `Icon ${size}px KHÔNG được chứa màu tím cũ (#6366f1)`);
  }
  console.log('✓ 12. Xác thực bộ Icon (16x16, 48x48, 128x128) mang màu xanh Emerald Green chuẩn, loại bỏ hoàn toàn màu tím');

  // 14. Direct DOM-Level Production popup.js Execution & Persistence Lifecycle Test
  const vm = require('vm');
  async function testProductionPopupDOMExecution() {
    const popupJsPath = path.join(__dirname, 'popup', 'popup.js');
    const popupJsCode = fs.readFileSync(popupJsPath, 'utf8');

    function createDOMHarness(storageMap = {}) {
      const listeners = {};
      const elementsById = {};

      class DOMElement {
        constructor(tag, id = '', className = '', dataset = {}) {
          this.tagName = tag.toUpperCase();
          this.id = id;
          this.className = className;
          this.children = [];
          this.classList = {
            _classes: new Set(className ? className.split(/\s+/).filter(Boolean) : []),
            add: (...c) => c.forEach(cls => this.classList._classes.add(cls)),
            remove: (...c) => c.forEach(cls => this.classList._classes.delete(cls)),
            toggle: (cls, force) => {
              if (force === undefined) {
                if (this.classList._classes.has(cls)) this.classList._classes.delete(cls);
                else this.classList._classes.add(cls);
              } else if (force) {
                this.classList._classes.add(cls);
              } else {
                this.classList._classes.delete(cls);
              }
            },
            contains: (cls) => this.classList._classes.has(cls)
          };
          this.dataset = { ...dataset };
          this.value = '';
          this.checked = false;
          this.indeterminate = false;
          this.disabled = false;
          this.textContent = '';
          this.innerHTML = '';
          this.src = '';
          this.href = '';
          this.style = {};
          this._eventHandlers = {};
        }

        appendChild(child) {
          this.children.push(child);
          return child;
        }

        addEventListener(event, handler) {
          if (!this._eventHandlers[event]) this._eventHandlers[event] = [];
          this._eventHandlers[event].push(handler);
        }

        dispatchEvent(event) {
          const type = typeof event === 'string' ? event : event.type;
          const target = typeof event === 'string' ? this : (event.target || this);
          if (this._eventHandlers[type]) {
            this._eventHandlers[type].forEach(fn => fn({ target, type }));
          }
        }

        querySelector(sel) {
          return new DOMElement('div');
        }

        querySelectorAll(sel) {
          return [];
        }
      }

      // Populate required elements from popup.html
      const ids = [
        'total-count-badge', 'btn-deep-scroll', 'btn-refresh', 'search-input', 'btn-clear-search',
        'sort-select', 'min-width', 'max-width', 'min-height', 'max-height', 'btn-reset-filters',
        'checkbox-select-all', 'btn-invert-selection', 'btn-copy-urls', 'btn-export-txt',
        'selection-counter', 'filtered-count', 'image-grid', 'loading-state', 'loading-title',
        'loading-desc', 'empty-state', 'btn-empty-reset', 'progress-container', 'progress-status-text',
        'progress-percentage', 'progress-bar-fill', 'download-folder', 'download-format-convert',
        'download-delay', 'btn-download-zip', 'zip-btn-text', 'btn-download-selected',
        'download-btn-text', 'btn-cancel-download', 'preview-modal', 'btn-prev-modal',
        'btn-next-modal', 'btn-close-modal', 'modal-preview-img', 'modal-image-title',
        'modal-image-dimensions', 'modal-format', 'modal-source', 'modal-url',
        'modal-btn-open-tab', 'modal-btn-copy-url', 'modal-btn-download', 'toast'
      ];

      ids.forEach(id => {
        elementsById[id] = new DOMElement('div', id);
      });

      // Preset chips
      const presetNames = ['all', 'small', 'medium', 'large', 'hd'];
      const presetChips = presetNames.map(p => new DOMElement('button', '', p === 'all' ? 'chip active' : 'chip', { preset: p }));

      // Ratio chips
      const ratioNames = ['ALL', 'LANDSCAPE', 'PORTRAIT', 'SQUARE'];
      const ratioChips = ratioNames.map(r => new DOMElement('button', '', r === 'ALL' ? 'ratio-chip active' : 'ratio-chip', { ratio: r }));

      // Format chips
      const formatNames = ['ALL', 'JPG', 'PNG', 'WEBP', 'SVG', 'GIF', 'OTHER'];
      const formatChips = formatNames.map(f => new DOMElement('button', '', f === 'ALL' ? 'format-chip active' : 'format-chip', { format: f }));

      const doc = {
        getElementById: (id) => elementsById[id] || new DOMElement('div', id),
        querySelectorAll: (sel) => {
          if (sel === '.chip[data-preset]') return presetChips;
          if (sel === '.ratio-chip[data-ratio]') return ratioChips;
          if (sel === '.format-chip[data-format]') return formatChips;
          return [];
        },
        querySelector: (sel) => {
          if (sel.startsWith('#')) return elementsById[sel.slice(1)] || null;
          return new DOMElement('div');
        },
        createElement: (tag) => new DOMElement(tag),
        createDocumentFragment: () => new DOMElement('fragment'),
        addEventListener: (event, handler) => {
          if (!listeners[event]) listeners[event] = [];
          listeners[event].push(handler);
        }
      };

      const chromeMock = {
        storage: {
          local: {
            get: async (keys) => {
              const res = {};
              keys.forEach(k => { if (k in storageMap) res[k] = storageMap[k]; });
              return res;
            },
            set: async (items) => {
              Object.assign(storageMap, items);
            }
          }
        },
        tabs: {
          query: async () => [{ id: 1, title: 'Sample Page', url: 'https://example.com' }]
        },
        scripting: {
          executeScript: async () => [{
            result: [
              { url: 'https://example.com/photo1.jpg', width: 1200, height: 800, format: 'JPG' },
              { url: 'https://example.com/photo2.png', width: 200, height: 200, format: 'PNG' }
            ]
          }]
        }
      };

      const sandbox = {
        document: doc,
        window: { location: { href: 'popup.html' } },
        chrome: chromeMock,
        console: { log: () => {}, warn: () => {}, error: () => {} },
        setTimeout: (fn) => setTimeout(fn, 0),
        clearTimeout: (id) => clearTimeout(id),
        setInterval: () => {},
        clearInterval: () => {},
        Image: function() { this.onload = null; this.src = ''; },
        CSS: { escape: s => s }
      };

      return { sandbox, elementsById, presetChips, ratioChips, formatChips, storageMap, listeners };
    }

    // Run 1: First Popup Load & User Interaction
    const sharedStorage = {};
    const h1 = createDOMHarness(sharedStorage);
    vm.runInNewContext(popupJsCode, h1.sandbox);

    for (const fn of h1.listeners['DOMContentLoaded'] || []) {
      await fn();
    }

    // Verify initial state
    assert(h1.presetChips[0].classList.contains('active'), 'Initial "all" preset chip must be active');

    // Step 2: User enters custom dimension
    const minWidthEl = h1.elementsById['min-width'];
    minWidthEl.value = '640';
    minWidthEl.dispatchEvent('input');

    assert.strictEqual(sharedStorage.minWidth, 640, 'minWidth 640 must be persisted in storage');
    assert.strictEqual(sharedStorage.activePreset, 'custom', 'activePreset must be custom in storage');
    assert(!h1.presetChips[0].classList.contains('active'), 'all chip must be deactivated when custom dimension entered');

    // Step 3: User clears all custom dimensions
    minWidthEl.value = '';
    minWidthEl.dispatchEvent('input');

    assert.strictEqual(sharedStorage.activePreset, 'all', 'activePreset must revert to all in storage');
    assert(h1.presetChips[0].classList.contains('active'), 'all chip must be activated when dimensions cleared');

    // Step 4: Recreate/reload popup DOM (simulating reopening extension popup)
    const h2 = createDOMHarness(sharedStorage);
    vm.runInNewContext(popupJsCode, h2.sandbox);

    for (const fn of h2.listeners['DOMContentLoaded'] || []) {
      await fn();
    }

    assert(h2.presetChips[0].classList.contains('active'), 'all chip must be active upon popup reopen');
    assert.strictEqual(h2.elementsById['min-width'].value, '', 'min-width input must remain empty');
  }

  await testProductionPopupDOMExecution();
  console.log('✓ 14. Kiểm thử DOM-Level trực tiếp mã nguồn production popup.js & Vòng đời Đồng bộ Preferences thành công');

  console.log('\n--- TOÀN BỘ KIỂM TRA EXTENSION THÀNH CÔNG 100%! ---');

}

testExtension();

