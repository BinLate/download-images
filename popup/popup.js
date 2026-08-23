/**
 * Image Collector & Downloader Pro - Popup Controller Logic
 * Quét DOM tab hiện tại, quản lý bộ lọc kích thước, multi-select và tải xuống tuần tự.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    allImages: [],
    filteredImages: [],
    selectedUrls: new Set(),
    activePreset: 'all',
    activeFormat: 'ALL',
    minWidth: null,
    maxWidth: null,
    minHeight: null,
    maxHeight: null,
    searchQuery: '',
    sortOrder: 'default',
    isDownloading: false,
    cancelRequested: false,
    currentPreviewItem: null
  };

  // DOM Elements
  const el = {
    totalBadge: document.getElementById('total-count-badge'),
    btnRefresh: document.getElementById('btn-refresh'),
    searchInput: document.getElementById('search-input'),
    btnClearSearch: document.getElementById('btn-clear-search'),
    sortSelect: document.getElementById('sort-select'),
    presetChips: document.querySelectorAll('.chip[data-preset]'),
    formatChips: document.querySelectorAll('.format-chip[data-format]'),
    minWidthInput: document.getElementById('min-width'),
    maxWidthInput: document.getElementById('max-width'),
    minHeightInput: document.getElementById('min-height'),
    maxHeightInput: document.getElementById('max-height'),
    btnResetFilters: document.getElementById('btn-reset-filters'),
    checkboxSelectAll: document.getElementById('checkbox-select-all'),
    btnInvertSelection: document.getElementById('btn-invert-selection'),
    selectionCounter: document.getElementById('selection-counter'),
    filteredCount: document.getElementById('filtered-count'),
    imageGrid: document.getElementById('image-grid'),
    loadingState: document.getElementById('loading-state'),
    emptyState: document.getElementById('empty-state'),
    btnEmptyReset: document.getElementById('btn-empty-reset'),
    progressContainer: document.getElementById('progress-container'),
    progressStatusText: document.getElementById('progress-status-text'),
    progressPercentage: document.getElementById('progress-percentage'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    downloadDelaySelect: document.getElementById('download-delay'),
    btnDownloadSelected: document.getElementById('btn-download-selected'),
    downloadBtnText: document.getElementById('download-btn-text'),
    btnCancelDownload: document.getElementById('btn-cancel-download'),
    previewModal: document.getElementById('preview-modal'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    modalPreviewImg: document.getElementById('modal-preview-img'),
    modalImageTitle: document.getElementById('modal-image-title'),
    modalImageDimensions: document.getElementById('modal-image-dimensions'),
    modalFormat: document.getElementById('modal-format'),
    modalSource: document.getElementById('modal-source'),
    modalUrl: document.getElementById('modal-url'),
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
    await scanActiveTabImages();
  }

  async function scanActiveTabImages() {
    setLoading(true);
    state.allImages = [];
    state.selectedUrls.clear();

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) {
        throw new Error('Không tìm thấy tab hiện tại');
      }

      // Check if URL is restricted (e.g. chrome://, edge://, about:)
      if (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('chrome-extension://') || tab.url.startsWith('view-source:')) {
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

      if (results && results.length > 0) {
        const aggregatedMap = new Map();

        // Ghép kết quả từ tất cả các frames
        for (const frameResult of results) {
          if (Array.isArray(frameResult.result)) {
            for (const img of frameResult.result) {
              if (img && img.url) {
                if (!aggregatedMap.has(img.url)) {
                  aggregatedMap.set(img.url, img);
                } else {
                  const curr = aggregatedMap.get(img.url);
                  if (img.width > curr.width) curr.width = img.width;
                  if (img.height > curr.height) curr.height = img.height;
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

  function measureUnresolvedImages(images) {
    images.forEach(img => {
      if ((!img.width || !img.height) && img.url && !img.url.startsWith('data:image/svg+xml')) {
        const tempImg = new Image();
        tempImg.onload = () => {
          if (tempImg.naturalWidth && tempImg.naturalHeight) {
            img.width = tempImg.naturalWidth;
            img.height = tempImg.naturalHeight;
            // Update badge on card if rendered
            const cardBadge = document.querySelector(`.img-card[data-url="${CSS.escape(img.url)}"] .card-dim-badge`);
            if (cardBadge) {
              cardBadge.textContent = `${img.width} × ${img.height}`;
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

      // 3. Preset Filter
      if (state.activePreset === 'small') {
        if (w > 200 || h > 200) return false;
      } else if (state.activePreset === 'medium') {
        if ((w < 200 && h < 200) || (w > 800 && h > 800)) return false;
      } else if (state.activePreset === 'large') {
        if (w < 800 && h < 800) return false;
      } else if (state.activePreset === 'hd') {
        if (w < 1920 && h < 1080) return false;
      }

      // 4. Custom Dimension Filter
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
    el.downloadBtnText.textContent = `Tải xuống (${selectedCount} ảnh)`;
    el.btnDownloadSelected.disabled = selectedCount === 0 || state.isDownloading;

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

    state.filteredImages.forEach(item => {
      const isSelected = state.selectedUrls.has(item.url);
      const card = document.createElement('div');
      card.className = `img-card ${isSelected ? 'selected' : ''}`;
      card.dataset.url = item.url;

      const dimText = (item.width > 0 && item.height > 0) ? `${item.width} × ${item.height}` : 'Tự động';

      card.innerHTML = `
        <div class="card-checkbox">
          <label class="custom-checkbox" onclick="event.stopPropagation()">
            <input type="checkbox" ${isSelected ? 'checked' : ''} class="item-checkbox">
            <span class="checkmark"></span>
          </label>
        </div>
        <span class="card-dim-badge">${dimText}</span>
        <div class="img-card-thumb">
          <img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.alt || '')}" loading="lazy" onerror="this.src='../icons/icon48.png'">
        </div>
        <span class="card-format-badge">${item.format}</span>
        <div class="card-actions-hover" onclick="event.stopPropagation()">
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
        openPreviewModal(item);
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
  // Sequential Download Engine
  // =========================================================================
  async function startSequentialDownload() {
    const targetImages = state.filteredImages.filter(img => state.selectedUrls.has(img.url));
    if (targetImages.length === 0) {
      showToast('Vui lòng chọn ít nhất một ảnh để tải xuống');
      return;
    }

    const delayMs = parseInt(el.downloadDelaySelect.value, 10) || 300;
    state.isDownloading = true;
    state.cancelRequested = false;

    // UI Updates
    el.progressContainer.classList.remove('hidden');
    el.btnCancelDownload.classList.remove('hidden');
    el.btnDownloadSelected.disabled = true;
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
      const filename = getSanitizedFilename(item, i + 1);
      const currentIdx = i + 1;
      const total = targetImages.length;
      const percent = Math.round((currentIdx / total) * 100);

      // Update progress
      el.progressStatusText.textContent = `Đang tải ${currentIdx}/${total}: ${filename}`;
      el.progressPercentage.textContent = `${percent}%`;
      el.progressBarFill.style.width = `${percent}%`;

      try {
        await executeDownload(item.url, filename);
        successCount++;
      } catch (err) {
        console.error('Download error:', item.url, err);
        failCount++;
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

    if (!state.cancelRequested) {
      el.progressStatusText.textContent = `Hoàn tất! Tải thành công ${successCount} ảnh ${failCount > 0 ? `(${failCount} lỗi)` : ''}`;
      el.progressBarFill.style.width = '100%';
      showToast(`Đã tải thành công ${successCount} ảnh về thư mục Downloads`);
    }

    setTimeout(() => {
      if (!state.isDownloading) {
        el.progressContainer.classList.add('hidden');
      }
    }, 4000);
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
        saveAs: false // Uses browser default downloads folder directly
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
    const filename = getSanitizedFilename(item, 1);
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
  // Preview Modal
  // =========================================================================
  function openPreviewModal(item) {
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
  }

  // =========================================================================
  // UI Event Listeners
  // =========================================================================
  function setupEventListeners() {
    // Refresh Button
    el.btnRefresh.addEventListener('click', scanActiveTabImages);

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

      el.presetChips.forEach(c => c.classList.toggle('active', c.dataset.preset === 'all'));
      el.formatChips.forEach(c => c.classList.toggle('active', c.dataset.format === 'ALL'));

      applyFilters();
      render();
    };

    el.btnResetFilters.addEventListener('click', resetFilters);
    el.btnEmptyReset.addEventListener('click', resetFilters);

    // Select All Checkbox
    el.checkboxSelectAll.addEventListener('change', (e) => {
      if (e.target.checked) {
        selectAllFiltered();
      } else {
        deselectAllFiltered();
      }
    });

    // Invert Selection
    el.btnInvertSelection.addEventListener('click', invertSelectionFiltered);

    // Download Button
    el.btnDownloadSelected.addEventListener('click', startSequentialDownload);

    // Cancel Download Button
    el.btnCancelDownload.addEventListener('click', () => {
      state.cancelRequested = true;
    });

    // Modal Events
    el.btnCloseModal.addEventListener('click', closePreviewModal);
    el.previewModal.addEventListener('click', (e) => {
      if (e.target === el.previewModal) closePreviewModal();
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
      if (e.key === 'Escape' && !el.previewModal.classList.contains('hidden')) {
        closePreviewModal();
      }
    });
  }

  // =========================================================================
  // Helpers
  // =========================================================================
  function setLoading(isLoading) {
    if (isLoading) {
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
