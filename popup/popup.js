/**
 * Image Collector & Downloader Pro - Popup Controller Logic
 * Quét DOM tab hiện tại, quản lý bộ lọc kích thước, tỷ lệ khung hình,
 * cuộn sâu (deep scroll), multi-select, thư mục con và tải xuống tuần tự.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    allImages: [],
    filteredImages: [],
    selectedUrls: new Set(),
    activePreset: 'all',
    activeRatio: 'ALL',
    activeFormat: 'ALL',
    minWidth: null,
    maxWidth: null,
    minHeight: null,
    maxHeight: null,
    searchQuery: '',
    sortOrder: 'default',
    downloadFolder: '',
    isDownloading: false,
    cancelRequested: false,
    currentPreviewIndex: -1,
    currentPreviewItem: null
  };

  // DOM Elements
  const el = {
    totalBadge: document.getElementById('total-count-badge'),
    btnDeepScroll: document.getElementById('btn-deep-scroll'),
    btnRefresh: document.getElementById('btn-refresh'),
    searchInput: document.getElementById('search-input'),
    btnClearSearch: document.getElementById('btn-clear-search'),
    sortSelect: document.getElementById('sort-select'),
    presetChips: document.querySelectorAll('.chip[data-preset]'),
    ratioChips: document.querySelectorAll('.ratio-chip[data-ratio]'),
    formatChips: document.querySelectorAll('.format-chip[data-format]'),
    minWidthInput: document.getElementById('min-width'),
    maxWidthInput: document.getElementById('max-width'),
    minHeightInput: document.getElementById('min-height'),
    maxHeightInput: document.getElementById('max-height'),
    btnResetFilters: document.getElementById('btn-reset-filters'),
    checkboxSelectAll: document.getElementById('checkbox-select-all'),
    btnInvertSelection: document.getElementById('btn-invert-selection'),
    btnCopyUrls: document.getElementById('btn-copy-urls'),
    btnExportTxt: document.getElementById('btn-export-txt'),
    selectionCounter: document.getElementById('selection-counter'),
    filteredCount: document.getElementById('filtered-count'),
    imageGrid: document.getElementById('image-grid'),
    loadingState: document.getElementById('loading-state'),
    loadingTitle: document.getElementById('loading-title'),
    loadingDesc: document.getElementById('loading-desc'),
    emptyState: document.getElementById('empty-state'),
    btnEmptyReset: document.getElementById('btn-empty-reset'),
    progressContainer: document.getElementById('progress-container'),
    progressStatusText: document.getElementById('progress-status-text'),
    progressPercentage: document.getElementById('progress-percentage'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    downloadFolderInput: document.getElementById('download-folder'),
    downloadFormatConvert: document.getElementById('download-format-convert'),
    downloadDelaySelect: document.getElementById('download-delay'),
    btnDownloadZip: document.getElementById('btn-download-zip'),
    zipBtnText: document.getElementById('zip-btn-text'),
    btnDownloadSelected: document.getElementById('btn-download-selected'),
    downloadBtnText: document.getElementById('download-btn-text'),
    btnCancelDownload: document.getElementById('btn-cancel-download'),
    previewModal: document.getElementById('preview-modal'),
    btnPrevModal: document.getElementById('btn-prev-modal'),
    btnNextModal: document.getElementById('btn-next-modal'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    modalPreviewImg: document.getElementById('modal-preview-img'),
    modalImageTitle: document.getElementById('modal-image-title'),
    modalImageDimensions: document.getElementById('modal-image-dimensions'),
    modalFormat: document.getElementById('modal-format'),
    modalSource: document.getElementById('modal-source'),
    modalUrl: document.getElementById('modal-url'),
    modalBtnOpenTab: document.getElementById('modal-btn-open-tab'),
    modalBtnCopyUrl: document.getElementById('modal-btn-copy-url'),
    modalBtnDownload: document.getElementById('modal-btn-download'),
    toast: document.getElementById('toast')
  };

  // =========================================================================
  // Initialization & Data Fetching
  // =========================================================================
  init();

  async function init() {
    setupEventListeners();
    await loadPreferences();
    await scanActiveTabImages();
  }

  async function loadPreferences() {
    try {
      if (chrome.storage && chrome.storage.local) {
        const data = await chrome.storage.local.get(['downloadFolder', 'downloadDelay', 'downloadFormatConvert']);
        if (data.downloadFolder && el.downloadFolderInput) {
          el.downloadFolderInput.value = data.downloadFolder;
          state.downloadFolder = data.downloadFolder;
        }
        if (data.downloadDelay && el.downloadDelaySelect) {
          el.downloadDelaySelect.value = data.downloadDelay;
        }
        if (data.downloadFormatConvert && el.downloadFormatConvert) {
          el.downloadFormatConvert.value = data.downloadFormatConvert;
        }
      }
    } catch {
      // Ignore storage errors
    }
  }

  async function scanActiveTabImages() {
    setLoading(true, 'Đang quét hình ảnh trên trang...', 'Vui lòng chờ trong giây lát');
    state.allImages = [];
    state.selectedUrls.clear();

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        throw new Error('Không tìm thấy tab hiện tại');
      }

      // Default folder suggestion based on tab title if input is empty
      if (!el.downloadFolderInput.value && tab.title) {
        const cleanTitle = tab.title.replace(/[/\\?%*:|"<>]/g, '_').trim().slice(0, 30);
        if (cleanTitle) {
          el.downloadFolderInput.placeholder = cleanTitle;
        }
      }

      // Check if URL is restricted
      if (tab.url && (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('chrome-extension://') || tab.url.startsWith('view-source:') || tab.url.startsWith('about:'))) {
        showToast('Không thể quét ảnh trên trang hệ thống trình duyệt');
        setLoading(false);
        render();
        return;
      }

      // Inject extractor script
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id, allFrames: true },
        files: ['scripts/extractor.js']
      });

  function getCanonicalKey(url) {
    if (!url || typeof url !== 'string') return '';
    if (url.startsWith('data:')) return url;
    try {
      const parsed = new URL(url);
      let path = parsed.pathname.toLowerCase();
      path = path.replace(/(?:-\d{2,4}x\d{2,4}|-scaled)(?=\.[a-z0-9]+$)/i, '');
      path = path.replace(/\.(?:jpg|jpeg|png|webp|avif|gif)$/i, '');
      
      // Giữ lại các query param định danh, loại bỏ params resize/crop/format
      let queryString = '';
      if (parsed.search) {
        const cleanParams = new URLSearchParams(parsed.search);
        ['w', 'width', 'h', 'height', 'resize', 'fit', 'crop', 'size', 'maxwidth', 'maxheight', 'quality', 'q', 'format', 'auto'].forEach(p => {
          cleanParams.delete(p);
        });
        queryString = cleanParams.toString();
      }
      return `${parsed.origin}${path}${queryString ? '?' + queryString : ''}`;
    } catch {
      return url.toLowerCase();
    }
  }

      if (results && results.length > 0) {
        const aggregatedMap = new Map();

        // Ghép và khử trùng lặp thông minh từ tất cả các frames
        for (const frameResult of results) {
          if (Array.isArray(frameResult.result)) {
            for (const img of frameResult.result) {
              if (img && img.url) {
                const key = getCanonicalKey(img.url);
                if (!aggregatedMap.has(key)) {
                  aggregatedMap.set(key, { ...img });
                } else {
                  const curr = aggregatedMap.get(key);
                  const isNewHigherRes = ((img.width || 0) * (img.height || 0)) > ((curr.width || 0) * (curr.height || 0));
                  if (isNewHigherRes) {
                    curr.url = img.url;
                    curr.width = img.width;
                    curr.height = img.height;
                    curr.format = img.format;
                  } else {
                    if ((!curr.width || curr.width === 0) && img.width > 0) curr.width = img.width;
                    if ((!curr.height || curr.height === 0) && img.height > 0) curr.height = img.height;
                  }
                  if (!curr.alt && img.alt) curr.alt = img.alt;
                }
              }
            }
          }
        }

        state.allImages = Array.from(aggregatedMap.values());
      }

      // Preload / Measure background & unresolved images in popup context
      measureUnresolvedImages(state.allImages);

    } catch (err) {
      console.error('Lỗi khi quét ảnh:', err);
      showToast('Không thể quét ảnh: ' + (err.message || 'Lỗi trang'));
    } finally {
      setLoading(false);
      applyFilters();
      // Auto select all initially by default
      selectAllFiltered();
      render();
    }
  }

  // Deep Auto-Scroll Scan
  async function runDeepScrollAndScan() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        showToast('Không tìm thấy tab đang mở');
        return;
      }

      setLoading(true, 'Đang tự động cuộn trang để kích hoạt Lazy-load...', 'Hệ thống đang cuộn toàn bộ trang web');

      // Inject smooth auto-scroll routine into webpage
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: async () => {
          const step = 450;
          const delay = 120;
          const maxSteps = 45;
          let count = 0;

          while (count < maxSteps) {
            const prevScrollY = window.scrollY;
            window.scrollBy(0, step);
            count++;
            await new Promise(r => setTimeout(r, delay));
            const currentScrollY = window.scrollY;
            const maxY = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
            // Dừng sớm nếu đã chạm đáy trang
            if (currentScrollY + window.innerHeight >= maxY - 20 && currentScrollY === prevScrollY) {
              break;
            }
          }

          // Return back to top
          window.scrollTo({ top: 0, behavior: 'smooth' });
          await new Promise(r => setTimeout(r, 250));
        }
      });

      // Now scan images
      await scanActiveTabImages();
      showToast('Đã hoàn tất cuộn sâu và cập nhật danh sách ảnh!');
    } catch (err) {
      console.error('Deep scroll error:', err);
      showToast('Lỗi khi cuộn trang: ' + (err.message || 'Không thành công'));
      setLoading(false);
      render();
    }
  }

  function measureUnresolvedImages(images) {
    let reFilterNeeded = false;
    let measureTimer;

    images.forEach(img => {
      if ((!img.width || !img.height) && img.url && !img.url.startsWith('data:image/svg+xml')) {
        const tempImg = new Image();
        tempImg.onload = () => {
          if (tempImg.naturalWidth && tempImg.naturalHeight) {
            img.width = tempImg.naturalWidth;
            img.height = tempImg.naturalHeight;
            // Update badge on card if already rendered
            const cardBadge = document.querySelector(`.img-card[data-url="${CSS.escape(img.url)}"] .card-dim-badge`);
            if (cardBadge) {
              cardBadge.textContent = `${img.width} × ${img.height}`;
            }

            // Debounce re-filter if dimension/ratio filters are active
            if (state.minWidth || state.maxWidth || state.minHeight || state.maxHeight || state.activePreset !== 'all' || state.activeRatio !== 'ALL') {
              reFilterNeeded = true;
              clearTimeout(measureTimer);
              measureTimer = setTimeout(() => {
                if (reFilterNeeded) {
                  applyFilters();
                  render();
                }
              }, 300);
            }
          }
        };
        tempImg.src = img.url;
      }
    });
  }

  // =========================================================================
  // Filtering & Sorting Logic
  // =========================================================================
  function applyFilters() {
    const q = state.searchQuery.toLowerCase().trim();
    const minW = state.minWidth !== null ? state.minWidth : -Infinity;
    const maxW = state.maxWidth !== null ? state.maxWidth : Infinity;
    const minH = state.minHeight !== null ? state.minHeight : -Infinity;
    const maxH = state.maxHeight !== null ? state.maxHeight : Infinity;

    state.filteredImages = state.allImages.filter(img => {
      const w = img.width || 0;
      const h = img.height || 0;

      // 1. Search Query Filter
      if (q) {
        const urlMatch = img.url.toLowerCase().includes(q);
        const altMatch = img.alt ? img.alt.toLowerCase().includes(q) : false;
        const formatMatch = img.format.toLowerCase().includes(q);
        if (!urlMatch && !altMatch && !formatMatch) return false;
      }

      // 2. Format Filter
      if (state.activeFormat !== 'ALL') {
        if (state.activeFormat === 'OTHER') {
          if (['JPG', 'PNG', 'WEBP', 'SVG', 'GIF'].includes(img.format)) return false;
        } else if (img.format !== state.activeFormat) {
          return false;
        }
      }

      // 3. Preset Filter (Normalized by maximum dimension for mutually exclusive classification)
      const maxDim = Math.max(w, h);
      if (state.activePreset === 'small') {
        if (maxDim >= 300) return false;
      } else if (state.activePreset === 'medium') {
        if (maxDim < 300 || maxDim > 800) return false;
      } else if (state.activePreset === 'large') {
        if (maxDim <= 800) return false;
      } else if (state.activePreset === 'hd') {
        if (maxDim < 1080 && (w < 1920 && h < 1080)) return false;
      }

      // 4. Aspect Ratio Filter
      if (state.activeRatio !== 'ALL' && w > 0 && h > 0) {
        const ratio = w / h;
        if (state.activeRatio === 'LANDSCAPE' && ratio < 1.15) return false;
        if (state.activeRatio === 'PORTRAIT' && ratio > 0.87) return false;
        if (state.activeRatio === 'SQUARE' && (ratio < 0.85 || ratio > 1.18)) return false;
      }

      // 5. Custom Dimension Filter
      if (state.minWidth !== null && w < minW) return false;
      if (state.maxWidth !== null && w > maxW) return false;
      if (state.minHeight !== null && h < minH) return false;
      if (state.maxHeight !== null && h > maxH) return false;

      return true;
    });

    // Apply Sorting
    sortFilteredImages();
  }

  function sortFilteredImages() {
    switch (state.sortOrder) {
      case 'size-desc':
        state.filteredImages.sort((a, b) => (b.width * b.height) - (a.width * a.height));
        break;
      case 'size-asc':
        state.filteredImages.sort((a, b) => (a.width * a.height) - (b.width * b.height));
        break;
      case 'width-desc':
        state.filteredImages.sort((a, b) => b.width - a.width);
        break;
      case 'height-desc':
        state.filteredImages.sort((a, b) => b.height - a.height);
        break;
      case 'name-asc':
        state.filteredImages.sort((a, b) => getFilenameFromUrl(a.url).localeCompare(getFilenameFromUrl(b.url)));
        break;
      default:
        // Default extraction order
        break;
    }
  }

  // =========================================================================
  // Rendering
  // =========================================================================
  function render() {
    el.totalBadge.textContent = `${state.allImages.length} ảnh`;
    el.filteredCount.textContent = state.filteredImages.length;

    // Update Selection Counter
    const selectedCount = getVisibleSelectedCount();
    el.selectionCounter.innerHTML = `Đã chọn: <strong>${selectedCount}</strong> / <span>${state.filteredImages.length}</span>`;
    el.downloadBtnText.textContent = `Tải xuống (${selectedCount})`;
    el.btnDownloadSelected.disabled = selectedCount === 0 || state.isDownloading;
    if (el.btnDownloadZip) {
      el.btnDownloadZip.disabled = selectedCount === 0 || state.isDownloading;
      if (el.zipBtnText) {
        el.zipBtnText.textContent = selectedCount > 0 ? `Tải ZIP (${selectedCount})` : 'Tải ZIP';
      }
    }

    // Update Select All Checkbox
    if (state.filteredImages.length === 0) {
      el.checkboxSelectAll.checked = false;
      el.checkboxSelectAll.indeterminate = false;
    } else if (selectedCount === state.filteredImages.length) {
      el.checkboxSelectAll.checked = true;
      el.checkboxSelectAll.indeterminate = false;
    } else if (selectedCount > 0) {
      el.checkboxSelectAll.checked = false;
      el.checkboxSelectAll.indeterminate = true;
    } else {
      el.checkboxSelectAll.checked = false;
      el.checkboxSelectAll.indeterminate = false;
    }

    // Toggle Empty State
    if (state.filteredImages.length === 0 && state.allImages.length > 0) {
      el.emptyState.classList.remove('hidden');
      el.imageGrid.classList.add('hidden');
    } else if (state.allImages.length === 0) {
      el.emptyState.classList.remove('hidden');
      el.imageGrid.classList.add('hidden');
      el.emptyState.querySelector('.state-title').textContent = 'Không tìm thấy hình ảnh nào trên trang';
      el.emptyState.querySelector('.state-desc').textContent = 'Trang này có thể không chứa ảnh hoặc đang chặn truy xuất DOM';
    } else {
      el.emptyState.classList.add('hidden');
      el.imageGrid.classList.remove('hidden');
      renderGridItems();
    }
  }

  function renderGridItems() {
    el.imageGrid.innerHTML = '';
    const fragment = document.createDocumentFragment();

    state.filteredImages.forEach((item, index) => {
      const isSelected = state.selectedUrls.has(item.url);
      const card = document.createElement('div');
      card.className = `img-card ${isSelected ? 'selected' : ''}`;
      card.dataset.url = item.url;

      const dimText = (item.width > 0 && item.height > 0) ? `${item.width} × ${item.height}` : 'Tự động';

      card.innerHTML = `
        <div class="card-checkbox">
          <label class="custom-checkbox">
            <input type="checkbox" ${isSelected ? 'checked' : ''} class="item-checkbox">
          </label>
        </div>
        <span class="card-dim-badge">${dimText}</span>
        <div class="img-card-thumb">
          <img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.alt || '')}" loading="lazy">
        </div>
        <span class="card-format-badge">${item.format}</span>
        <div class="card-actions-hover">
          <button class="btn-card-action btn-preview" title="Xem chi tiết">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
          </button>
          <button class="btn-card-action btn-download-single" title="Tải ảnh này">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </button>
        </div>
      `;

      // Prevent card selection toggle when clicking checkbox label or action buttons
      const chkLabel = card.querySelector('.custom-checkbox');
      if (chkLabel) {
        chkLabel.addEventListener('click', (e) => e.stopPropagation());
      }
      const actionsHover = card.querySelector('.card-actions-hover');
      if (actionsHover) {
        actionsHover.addEventListener('click', (e) => e.stopPropagation());
      }

      // Safe fallback image on error (CSP compliant without inline onerror)
      const thumbImg = card.querySelector('.img-card-thumb img');
      if (thumbImg) {
        thumbImg.addEventListener('error', () => {
          thumbImg.src = '../icons/icon48.png';
        }, { once: true });
      }

      // Click card to toggle selection
      card.addEventListener('click', () => {
        toggleItemSelection(item.url);
      });

      // Checkbox click
      const checkbox = card.querySelector('.item-checkbox');
      checkbox.addEventListener('change', () => {
        toggleItemSelection(item.url, checkbox.checked);
      });

      // Preview button click
      const btnPreview = card.querySelector('.btn-preview');
      btnPreview.addEventListener('click', () => {
        openPreviewModal(item, index);
      });

      // Single download button click
      const btnSingleDl = card.querySelector('.btn-download-single');
      btnSingleDl.addEventListener('click', () => {
        downloadSingleFile(item);
      });

      fragment.appendChild(card);
    });

    el.imageGrid.appendChild(fragment);
  }

  // =========================================================================
  // Selection Handlers
  // =========================================================================
  function getVisibleSelectedCount() {
    let count = 0;
    state.filteredImages.forEach(img => {
      if (state.selectedUrls.has(img.url)) count++;
    });
    return count;
  }

  function toggleItemSelection(url, forceState = null) {
    if (forceState !== null) {
      if (forceState) state.selectedUrls.add(url);
      else state.selectedUrls.delete(url);
    } else {
      if (state.selectedUrls.has(url)) state.selectedUrls.delete(url);
      else state.selectedUrls.add(url);
    }
    render();
  }

  function selectAllFiltered() {
    state.filteredImages.forEach(img => state.selectedUrls.add(img.url));
    render();
  }

  function deselectAllFiltered() {
    state.filteredImages.forEach(img => state.selectedUrls.delete(img.url));
    render();
  }

  function invertSelectionFiltered() {
    state.filteredImages.forEach(img => {
      if (state.selectedUrls.has(img.url)) state.selectedUrls.delete(img.url);
      else state.selectedUrls.add(img.url);
    });
    render();
  }

  // =========================================================================
  // Export & Copy URLs Logic
  // =========================================================================
  function getSelectedOrAllUrls() {
    const selected = state.filteredImages.filter(img => state.selectedUrls.has(img.url));
    const target = selected.length > 0 ? selected : state.filteredImages;
    return target.map(img => img.url);
  }

  function copySelectedUrls() {
    const urls = getSelectedOrAllUrls();
    if (urls.length === 0) {
      showToast('Không có link ảnh nào để sao chép');
      return;
    }

    navigator.clipboard.writeText(urls.join('\n'))
      .then(() => {
        showToast(`Đã sao chép ${urls.length} link ảnh vào clipboard!`);
      })
      .catch(() => {
        showToast('Không thể sao chép vào clipboard');
      });
  }

  function exportSelectedUrlsTxt() {
    const urls = getSelectedOrAllUrls();
    if (urls.length === 0) {
      showToast('Không có link ảnh nào để xuất');
      return;
    }

    const content = urls.join('\r\n');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const blobUrl = URL.createObjectURL(blob);
    const dateStr = new Date().toISOString().slice(0, 10);
    const filename = `image_links_${dateStr}.txt`;

    chrome.downloads.download({
      url: blobUrl,
      filename: filename,
      saveAs: true
    }, () => {
      showToast(`Đã xuất danh sách ${urls.length} link ảnh`);
    });
  }

  // =========================================================================
  // Image Conversion & Payload Preparation Helpers
  // =========================================================================
  function shouldConvertImage(imgFormat, convertMode) {
    if (!convertMode || convertMode === 'original') return false;
    const fmt = (imgFormat || '').toUpperCase();
    if (convertMode === 'webp-to-jpg' && (fmt === 'WEBP' || fmt === 'AVIF')) return 'image/jpeg';
    if (convertMode === 'webp-to-png' && (fmt === 'WEBP' || fmt === 'AVIF')) return 'image/png';
    if (convertMode === 'all-to-jpg' && fmt !== 'JPG') return 'image/jpeg';
    if (convertMode === 'all-to-png' && fmt !== 'PNG') return 'image/png';
    return false;
  }

  async function convertImageToBlob(url, targetMimeType = 'image/jpeg', quality = 0.92) {
    const sourceBlob = await fetchImageAsBlob(url);
    const objectUrl = URL.createObjectURL(sourceBlob);
    try {
      return await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          try {
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth || img.width || 300;
            canvas.height = img.naturalHeight || img.height || 300;
            const ctx = canvas.getContext('2d');
            if (targetMimeType === 'image/jpeg') {
              ctx.fillStyle = '#ffffff';
              ctx.fillRect(0, 0, canvas.width, canvas.height);
            }
            ctx.drawImage(img, 0, 0);
            canvas.toBlob((blob) => {
              if (blob) {
                resolve(blob);
              } else {
                reject(new Error('Canvas toBlob trả về null'));
              }
            }, targetMimeType, quality);
          } catch (err) {
            reject(err);
          }
        };
        img.onerror = () => reject(new Error('Không thể tải ảnh vào Canvas để chuyển đổi'));
        img.src = objectUrl;
      });
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  }

  async function fetchImageAsBlob(url) {
    if (url.startsWith('data:image/svg+xml;charset=utf-8,')) {
      const svgContent = decodeURIComponent(url.replace('data:image/svg+xml;charset=utf-8,', ''));
      return new Blob([svgContent], { type: 'image/svg+xml' });
    }
    if (url.startsWith('data:')) {
      const res = await fetch(url);
      return await res.blob();
    }
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    return await response.blob();
  }

  async function prepareImagePayload(item, index = 1, convertMode = 'original') {
    const targetMime = shouldConvertImage(item.format, convertMode);
    let filename = getSanitizedFilename(item, index);

    if (targetMime) {
      const targetExt = targetMime === 'image/png' ? '.png' : '.jpg';
      const nameWithoutExt = filename.replace(/\.[^/.]+$/, '');
      filename = `${nameWithoutExt}${targetExt}`;

      try {
        const convertedBlob = await convertImageToBlob(item.url, targetMime, 0.92);
        return { blob: convertedBlob, filename, isConverted: true };
      } catch (e) {
        console.warn('Chuyển đổi ảnh thất bại, dùng file gốc:', item.url, e);
      }
    }

    const blob = await fetchImageAsBlob(item.url);
    return { blob, filename, isConverted: false };
  }

  // =========================================================================
  // Sequential Download Engine
  // =========================================================================
  async function startSequentialDownload() {
    const targetImages = state.filteredImages.filter(img => state.selectedUrls.has(img.url));
    if (targetImages.length === 0) {
      showToast('Vui lòng chọn ít nhất một ảnh để tải xuống');
      return;
    }

    const delayMs = parseInt(el.downloadDelaySelect.value, 10) || 300;
    const convertMode = el.downloadFormatConvert ? el.downloadFormatConvert.value : 'original';
    const subfolder = getSanitizedSubfolder();
    state.isDownloading = true;
    state.cancelRequested = false;

    // Save preferences
    if (chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({
        downloadFolder: el.downloadFolderInput.value.trim(),
        downloadDelay: el.downloadDelaySelect.value,
        downloadFormatConvert: convertMode
      });
    }

    // UI Updates
    el.progressContainer.classList.remove('hidden');
    el.btnCancelDownload.classList.remove('hidden');
    el.btnDownloadSelected.disabled = true;
    if (el.btnDownloadZip) el.btnDownloadZip.disabled = true;
    el.progressBarFill.style.width = '0%';
    el.progressPercentage.textContent = '0%';

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < targetImages.length; i++) {
      if (state.cancelRequested) {
        showToast('Đã dừng tiến trình tải xuống');
        break;
      }

      const item = targetImages[i];
      const currentIdx = i + 1;
      const total = targetImages.length;
      const percent = Math.round((currentIdx / total) * 100);

      // Update progress
      el.progressStatusText.textContent = `Đang tải ${currentIdx}/${total}: ${getFilenameFromUrl(item.url)}`;
      el.progressPercentage.textContent = `${percent}%`;
      el.progressBarFill.style.width = `${percent}%`;

      try {
        const payload = await prepareImagePayload(item, currentIdx, convertMode);
        let finalFilename = payload.filename;
        if (subfolder) {
          finalFilename = `${subfolder}/${finalFilename}`;
        }

        if (payload.blob) {
          const blobUrl = URL.createObjectURL(payload.blob);
          await executeDownload(blobUrl, finalFilename);
          setTimeout(() => URL.revokeObjectURL(blobUrl), 15000);
        } else {
          await executeDownload(item.url, finalFilename);
        }
        successCount++;
      } catch (err) {
        console.error('Download error:', item.url, err);
        // Fallback to original url download if payload preparation errored
        try {
          let fallbackName = getSanitizedFilename(item, currentIdx);
          if (subfolder) fallbackName = `${subfolder}/${fallbackName}`;
          await executeDownload(item.url, fallbackName);
          successCount++;
        } catch (fbErr) {
          console.error('Fallback download failed:', item.url, fbErr);
          failCount++;
        }
      }

      // Delay between sequential downloads to prevent browser freezing
      if (i < targetImages.length - 1 && delayMs > 0 && !state.cancelRequested) {
        await new Promise(r => setTimeout(r, delayMs));
      }
    }

    // Finished
    state.isDownloading = false;
    el.btnCancelDownload.classList.add('hidden');
    el.btnDownloadSelected.disabled = false;
    if (el.btnDownloadZip) el.btnDownloadZip.disabled = false;

    if (!state.cancelRequested) {
      el.progressStatusText.textContent = `Hoàn tất! Tải thành công ${successCount} ảnh ${failCount > 0 ? `(${failCount} lỗi)` : ''}`;
      el.progressBarFill.style.width = '100%';
      const destText = subfolder ? `thư mục Downloads/${subfolder}` : 'thư mục Downloads';
      showToast(`Đã tải thành công ${successCount} ảnh về ${destText}`);
    }

    setTimeout(() => {
      if (!state.isDownloading) {
        el.progressContainer.classList.add('hidden');
      }
    }, 4000);
  }

  // =========================================================================
  // ZIP Archive Download Engine (JSZip)
  // =========================================================================
  async function startZipDownload() {
    if (typeof JSZip === 'undefined') {
      showToast('Lỗi: Thư viện JSZip chưa được tải');
      return;
    }

    const targetImages = state.filteredImages.filter(img => state.selectedUrls.has(img.url));
    if (targetImages.length === 0) {
      showToast('Vui lòng chọn ít nhất một ảnh để tải ZIP');
      return;
    }

    const convertMode = el.downloadFormatConvert ? el.downloadFormatConvert.value : 'original';
    const subfolder = getSanitizedSubfolder();
    state.isDownloading = true;
    state.cancelRequested = false;

    // Save preferences
    if (chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({
        downloadFolder: el.downloadFolderInput.value.trim(),
        downloadDelay: el.downloadDelaySelect.value,
        downloadFormatConvert: convertMode
      });
    }

    // UI Updates
    el.progressContainer.classList.remove('hidden');
    el.btnCancelDownload.classList.remove('hidden');
    el.btnDownloadSelected.disabled = true;
    if (el.btnDownloadZip) el.btnDownloadZip.disabled = true;
    el.progressBarFill.style.width = '0%';
    el.progressPercentage.textContent = '0%';
    el.progressStatusText.textContent = 'Đang thu thập và nén ảnh vào file ZIP...';

    const zip = new JSZip();
    const usedNames = new Set();
    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < targetImages.length; i++) {
      if (state.cancelRequested) {
        showToast('Đã dừng tiến trình nén file ZIP');
        break;
      }

      const item = targetImages[i];
      const currentIdx = i + 1;
      const total = targetImages.length;
      const percent = Math.round((currentIdx / total) * 80); // 0-80% for fetching

      el.progressStatusText.textContent = `Đang tải & nén ${currentIdx}/${total}: ${getFilenameFromUrl(item.url)}`;
      el.progressPercentage.textContent = `${percent}%`;
      el.progressBarFill.style.width = `${percent}%`;

      try {
        const payload = await prepareImagePayload(item, currentIdx, convertMode);
        let zipItemName = payload.filename;

        // Ensure unique filename in zip
        if (usedNames.has(zipItemName)) {
          const parts = zipItemName.split('.');
          const ext = parts.length > 1 ? '.' + parts.pop() : '';
          zipItemName = `${parts.join('.')}_${currentIdx}${ext}`;
        }
        usedNames.add(zipItemName);

        zip.file(zipItemName, payload.blob);
        successCount++;
      } catch (err) {
        console.error('ZIP pack error:', item.url, err);
        failCount++;
      }
    }

    if (state.cancelRequested || successCount === 0) {
      state.isDownloading = false;
      el.btnCancelDownload.classList.add('hidden');
      el.btnDownloadSelected.disabled = false;
      if (el.btnDownloadZip) el.btnDownloadZip.disabled = false;
      if (successCount === 0 && !state.cancelRequested) {
        showToast('Không thể tải dữ liệu ảnh nào để tạo file ZIP');
      }
      setTimeout(() => {
        if (!state.isDownloading) el.progressContainer.classList.add('hidden');
      }, 3000);
      return;
    }

    // Generate ZIP file
    el.progressStatusText.textContent = 'Đang đóng gói file ZIP (DEFLATE)...';
    try {
      const zipBlob = await zip.generateAsync(
        {
          type: 'blob',
          compression: 'DEFLATE',
          compressionOptions: { level: 6 }
        },
        (metadata) => {
          const packPercent = 80 + Math.round((metadata.percent / 100) * 20);
          el.progressPercentage.textContent = `${packPercent}%`;
          el.progressBarFill.style.width = `${packPercent}%`;
        }
      );

      const zipUrl = URL.createObjectURL(zipBlob);
      const dateStr = new Date().toISOString().slice(0, 10);
      const timeStr = new Date().toTimeString().slice(0, 5).replace(':', '');
      let zipName = subfolder ? `${subfolder}_${dateStr}_${timeStr}.zip` : `images_${dateStr}_${timeStr}.zip`;
      if (subfolder) {
        zipName = `${subfolder}/${zipName}`;
      }

      await executeDownload(zipUrl, zipName);
      setTimeout(() => URL.revokeObjectURL(zipUrl), 30000);

      el.progressStatusText.textContent = `Hoàn tất! Đã nén thành công ${successCount} ảnh (${(zipBlob.size / 1024 / 1024).toFixed(2)} MB)`;
      el.progressBarFill.style.width = '100%';
      el.progressPercentage.textContent = '100%';
      showToast(`Đã xuất file ZIP (${successCount} ảnh) thành công!`);
    } catch (zipErr) {
      console.error('ZIP generation error:', zipErr);
      showToast('Lỗi khi đóng gói file ZIP: ' + (zipErr.message || 'Thất bại'));
    } finally {
      state.isDownloading = false;
      el.btnCancelDownload.classList.add('hidden');
      el.btnDownloadSelected.disabled = false;
      if (el.btnDownloadZip) el.btnDownloadZip.disabled = false;

      setTimeout(() => {
        if (!state.isDownloading) {
          el.progressContainer.classList.add('hidden');
        }
      }, 4000);
    }
  }

  function getSanitizedSubfolder() {
    const raw = el.downloadFolderInput.value.trim() || el.downloadFolderInput.placeholder.trim();
    if (!raw) return '';
    return raw.replace(/[/\\?%*:|"<>]/g, '_').trim();
  }

  function executeDownload(url, filename) {
    return new Promise((resolve, reject) => {
      // Check if it is a data URL SVG or large data URL
      if (url.startsWith('data:image/svg+xml;charset=utf-8,')) {
        try {
          const svgContent = decodeURIComponent(url.replace('data:image/svg+xml;charset=utf-8,', ''));
          const blob = new Blob([svgContent], { type: 'image/svg+xml' });
          const blobUrl = URL.createObjectURL(blob);
          chrome.downloads.download({
            url: blobUrl,
            filename: filename,
            conflictAction: 'uniquify',
            saveAs: false
          }, (downloadId) => {
            if (chrome.runtime.lastError || !downloadId) {
              reject(chrome.runtime.lastError || new Error('Download failed'));
            } else {
              resolve(downloadId);
            }
          });
          return;
        } catch {
          // Fallback to normal download
        }
      }

      chrome.downloads.download({
        url: url,
        filename: filename,
        conflictAction: 'uniquify',
        saveAs: false
      }, (downloadId) => {
        if (chrome.runtime.lastError || !downloadId) {
          reject(chrome.runtime.lastError || new Error('Download failed'));
        } else {
          resolve(downloadId);
        }
      });
    });
  }

  async function downloadSingleFile(item) {
    let filename = getSanitizedFilename(item, 1);
    const subfolder = getSanitizedSubfolder();
    if (subfolder) {
      filename = `${subfolder}/${filename}`;
    }
    showToast(`Đang tải: ${filename}`);
    try {
      await executeDownload(item.url, filename);
      showToast(`Đã tải xong: ${filename}`);
    } catch (err) {
      showToast('Lỗi khi tải ảnh: ' + (err.message || 'Thất bại'));
    }
  }

  function getSanitizedFilename(item, index = 1) {
    let name = getFilenameFromUrl(item.url);
    const ext = getExtensionForFormat(item.format);

    if (!name || name === 'image' || name.length < 3) {
      name = `image_${String(index).padStart(3, '0')}${ext}`;
    } else {
      // Ensure file has an extension
      if (!name.includes('.')) {
        name = `${name}${ext}`;
      }
    }

    // Clean special characters invalid in file systems
    name = name.replace(/[/\\?%*:|"<>]/g, '_').trim();
    if (name.length > 100) {
      const parts = name.split('.');
      const fileExt = parts.length > 1 ? '.' + parts.pop() : ext;
      name = parts.join('.').slice(0, 80) + fileExt;
    }
    return name;
  }

  function getFilenameFromUrl(url) {
    if (!url) return 'image';
    if (url.startsWith('data:')) return 'image_data';

    try {
      const parsed = new URL(url);
      
      // Check query params for common filename keys (file, filename, name, img, image)
      const queryName = parsed.searchParams.get('file') || parsed.searchParams.get('filename') || parsed.searchParams.get('name') || parsed.searchParams.get('img');
      if (queryName) {
        let cleanQueryName = decodeURIComponent(queryName).split('?')[0].split('#')[0].trim();
        if (cleanQueryName && cleanQueryName.length > 2) {
          return cleanQueryName;
        }
      }

      const pathname = parsed.pathname;
      const segments = pathname.split('/').filter(Boolean);
      if (segments.length > 0) {
        let last = decodeURIComponent(segments[segments.length - 1]);
        // Remove hash / query params if any in filename
        last = last.split('?')[0].split('#')[0];
        if (last) return last;
      }
    } catch {
      // Ignore URL parse error
    }
    return 'image';
  }

  function getExtensionForFormat(format) {
    switch (format) {
      case 'JPG': return '.jpg';
      case 'PNG': return '.png';
      case 'WEBP': return '.webp';
      case 'SVG': return '.svg';
      case 'GIF': return '.gif';
      case 'AVIF': return '.avif';
      case 'BMP': return '.bmp';
      case 'ICO': return '.ico';
      default: return '.jpg';
    }
  }

  // =========================================================================
  // Preview Modal & Navigation
  // =========================================================================
  function openPreviewModal(item, index = -1) {
    if (index === -1) {
      index = state.filteredImages.findIndex(i => i.url === item.url);
    }
    state.currentPreviewIndex = index;
    state.currentPreviewItem = item;

    el.modalPreviewImg.src = item.url;
    el.modalImageTitle.textContent = item.alt || getFilenameFromUrl(item.url) || 'Chi tiết hình ảnh';
    el.modalImageDimensions.textContent = (item.width > 0 && item.height > 0) ? `${item.width} × ${item.height} px` : 'Đang tải kích thước';
    el.modalFormat.textContent = item.format;
    el.modalSource.textContent = item.source || 'img';
    el.modalUrl.textContent = item.url;
    el.modalUrl.href = item.url;
    el.previewModal.classList.remove('hidden');
  }

  function closePreviewModal() {
    el.previewModal.classList.add('hidden');
    state.currentPreviewItem = null;
    state.currentPreviewIndex = -1;
  }

  function navigateModal(direction) {
    if (state.filteredImages.length === 0 || state.currentPreviewIndex === -1) return;
    let newIndex = state.currentPreviewIndex + direction;
    if (newIndex < 0) newIndex = state.filteredImages.length - 1;
    if (newIndex >= state.filteredImages.length) newIndex = 0;
    openPreviewModal(state.filteredImages[newIndex], newIndex);
  }

  // =========================================================================
  // UI Event Listeners
  // =========================================================================
  function setupEventListeners() {
    // Refresh Button & Deep Scroll Button
    el.btnRefresh.addEventListener('click', scanActiveTabImages);
    el.btnDeepScroll.addEventListener('click', runDeepScrollAndScan);

    // Search Input with Debounce
    let searchTimer;
    el.searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value;
      if (state.searchQuery) {
        el.btnClearSearch.classList.remove('hidden');
      } else {
        el.btnClearSearch.classList.add('hidden');
      }
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        applyFilters();
        render();
      }, 200);
    });

    el.btnClearSearch.addEventListener('click', () => {
      el.searchInput.value = '';
      state.searchQuery = '';
      el.btnClearSearch.classList.add('hidden');
      applyFilters();
      render();
    });

    // Sort Dropdown
    el.sortSelect.addEventListener('change', (e) => {
      state.sortOrder = e.target.value;
      sortFilteredImages();
      render();
    });

    // Preset Dimension Chips
    el.presetChips.forEach(chip => {
      chip.addEventListener('click', () => {
        el.presetChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.activePreset = chip.dataset.preset;

        // Clear custom dimension inputs if preset is chosen
        if (state.activePreset !== 'custom') {
          el.minWidthInput.value = '';
          el.maxWidthInput.value = '';
          el.minHeightInput.value = '';
          el.maxHeightInput.value = '';
          state.minWidth = null;
          state.maxWidth = null;
          state.minHeight = null;
          state.maxHeight = null;
        }

        applyFilters();
        render();
      });
    });

    // Ratio Chips
    el.ratioChips.forEach(chip => {
      chip.addEventListener('click', () => {
        el.ratioChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.activeRatio = chip.dataset.ratio;
        applyFilters();
        render();
      });
    });

    // Format Chips
    el.formatChips.forEach(chip => {
      chip.addEventListener('click', () => {
        el.formatChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.activeFormat = chip.dataset.format;
        applyFilters();
        render();
      });
    });

    // Custom Dimension Inputs
    const onDimInputChange = () => {
      state.minWidth = el.minWidthInput.value ? parseInt(el.minWidthInput.value, 10) : null;
      state.maxWidth = el.maxWidthInput.value ? parseInt(el.maxWidthInput.value, 10) : null;
      state.minHeight = el.minHeightInput.value ? parseInt(el.minHeightInput.value, 10) : null;
      state.maxHeight = el.maxHeightInput.value ? parseInt(el.maxHeightInput.value, 10) : null;

      // Deactivate presets if custom dimensions entered
      if (state.minWidth || state.maxWidth || state.minHeight || state.maxHeight) {
        el.presetChips.forEach(c => c.classList.remove('active'));
        state.activePreset = 'custom';
      }

      applyFilters();
      render();
    };

    el.minWidthInput.addEventListener('input', onDimInputChange);
    el.maxWidthInput.addEventListener('input', onDimInputChange);
    el.minHeightInput.addEventListener('input', onDimInputChange);
    el.maxHeightInput.addEventListener('input', onDimInputChange);

    // Reset Filters Button
    const resetFilters = () => {
      el.minWidthInput.value = '';
      el.maxWidthInput.value = '';
      el.minHeightInput.value = '';
      el.maxHeightInput.value = '';
      el.searchInput.value = '';
      el.btnClearSearch.classList.add('hidden');
      state.minWidth = null;
      state.maxWidth = null;
      state.minHeight = null;
      state.maxHeight = null;
      state.searchQuery = '';
      state.activeFormat = 'ALL';
      state.activePreset = 'all';
      state.activeRatio = 'ALL';

      el.presetChips.forEach(c => c.classList.toggle('active', c.dataset.preset === 'all'));
      el.ratioChips.forEach(c => c.classList.toggle('active', c.dataset.ratio === 'ALL'));
      el.formatChips.forEach(c => c.classList.toggle('active', c.dataset.format === 'ALL'));

      applyFilters();
      render();
    };

    el.btnResetFilters.addEventListener('click', resetFilters);
    el.btnEmptyReset.addEventListener('click', resetFilters);

    // Select All Checkbox & Invert
    el.checkboxSelectAll.addEventListener('change', (e) => {
      if (e.target.checked) {
        selectAllFiltered();
      } else {
        deselectAllFiltered();
      }
    });

    el.btnInvertSelection.addEventListener('click', invertSelectionFiltered);

    // Export and Copy URLs
    el.btnCopyUrls.addEventListener('click', copySelectedUrls);
    el.btnExportTxt.addEventListener('click', exportSelectedUrlsTxt);

    // Download Buttons (Sequential & ZIP)
    el.btnDownloadSelected.addEventListener('click', startSequentialDownload);
    if (el.btnDownloadZip) {
      el.btnDownloadZip.addEventListener('click', startZipDownload);
    }
    if (el.downloadFormatConvert) {
      el.downloadFormatConvert.addEventListener('change', (e) => {
        if (chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ downloadFormatConvert: e.target.value });
        }
      });
    }

    // Cancel Download Button
    el.btnCancelDownload.addEventListener('click', () => {
      state.cancelRequested = true;
    });

    // Modal Events & Navigation
    el.btnCloseModal.addEventListener('click', closePreviewModal);
    el.btnPrevModal.addEventListener('click', (e) => {
      e.stopPropagation();
      navigateModal(-1);
    });
    el.btnNextModal.addEventListener('click', (e) => {
      e.stopPropagation();
      navigateModal(1);
    });

    el.previewModal.addEventListener('click', (e) => {
      if (e.target === el.previewModal) closePreviewModal();
    });

    el.modalBtnOpenTab.addEventListener('click', () => {
      if (state.currentPreviewItem && state.currentPreviewItem.url) {
        chrome.tabs.create({ url: state.currentPreviewItem.url });
      }
    });

    el.modalBtnCopyUrl.addEventListener('click', () => {
      if (state.currentPreviewItem) {
        navigator.clipboard.writeText(state.currentPreviewItem.url);
        showToast('Đã sao chép URL vào clipboard');
      }
    });

    el.modalBtnDownload.addEventListener('click', () => {
      if (state.currentPreviewItem) {
        downloadSingleFile(state.currentPreviewItem);
      }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (!el.previewModal.classList.contains('hidden')) {
        if (e.key === 'Escape') {
          closePreviewModal();
        } else if (e.key === 'ArrowLeft') {
          navigateModal(-1);
        } else if (e.key === 'ArrowRight') {
          navigateModal(1);
        }
      }
    });
  }

  // =========================================================================
  // Helpers
  // =========================================================================
  function setLoading(isLoading, title = 'Đang quét hình ảnh trên trang...', desc = 'Vui lòng chờ trong giây lát') {
    if (isLoading) {
      el.loadingTitle.textContent = title;
      el.loadingDesc.textContent = desc;
      el.loadingState.classList.remove('hidden');
      el.emptyState.classList.add('hidden');
      el.imageGrid.classList.add('hidden');
    } else {
      el.loadingState.classList.add('hidden');
    }
  }

  let toastTimer;
  function showToast(msg) {
    el.toast.textContent = msg;
    el.toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.toast.classList.add('hidden');
    }, 2800);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[m]);
  }
});

