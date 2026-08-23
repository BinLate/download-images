/**
 * Image Extractor Script for Chrome Extension
 * Quét thông minh & khử trùng lặp toàn diện hình ảnh trên trang web hiện tại:
 * - Khử trùng lặp ảnh responsive (srcset, picture/source, lazy-load)
 * - Tự động chọn ảnh độ phân giải cao nhất (Master / Original resolution)
 * - Trích xuất ảnh trong Light DOM, recursive open Shadow DOM, CSS backgrounds, SVG, canvas, video poster...
 */

(function () {
  'use strict';

  function normalizeUrl(url) {
    if (!url || typeof url !== 'string') return null;
    const trimmed = url.trim();
    if (!trimmed || trimmed.startsWith('javascript:') || trimmed.startsWith('mailto:') || trimmed.startsWith('about:')) {
      return null;
    }
    try {
      const parsed = new URL(trimmed, document.baseURI || window.location.href);
      // Giữ nguyên hash/query nếu cần thiết, nhưng xóa tracking queries thông dụng
      const searchParams = parsed.searchParams;
      ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', '_ga', '_gl'].forEach(p => {
        searchParams.delete(p);
      });
      return parsed.href;
    } catch {
      return null;
    }
  }

  function detectFormat(url) {
    if (!url) return 'OTHER';
    if (url.startsWith('data:image/svg+xml')) return 'SVG';
    if (url.startsWith('data:image/png')) return 'PNG';
    if (url.startsWith('data:image/jpeg') || url.startsWith('data:image/jpg')) return 'JPG';
    if (url.startsWith('data:image/webp')) return 'WEBP';
    if (url.startsWith('data:image/gif')) return 'GIF';
    if (url.startsWith('data:image/avif')) return 'AVIF';
    if (url.startsWith('data:image/')) return 'DATA-URI';

    try {
      const pathname = new URL(url).pathname.toLowerCase();
      if (pathname.endsWith('.jpg') || pathname.endsWith('.jpeg')) return 'JPG';
      if (pathname.endsWith('.png')) return 'PNG';
      if (pathname.endsWith('.webp')) return 'WEBP';
      if (pathname.endsWith('.svg')) return 'SVG';
      if (pathname.endsWith('.gif')) return 'GIF';
      if (pathname.endsWith('.avif')) return 'AVIF';
      if (pathname.endsWith('.bmp')) return 'BMP';
      if (pathname.endsWith('.ico')) return 'ICO';
    } catch {
      // Ignore URL parsing errors
    }

    return 'IMAGE';
  }

  /**
   * Phân tích chuỗi srcset và trả về danh sách candidates kèm độ rộng/density
   */
  function parseSrcsetDetailed(srcsetStr) {
    if (!srcsetStr || typeof srcsetStr !== 'string') return [];
    const candidates = [];
    const parts = srcsetStr.split(',');
    for (const part of parts) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      const tokens = trimmed.split(/\s+/);
      const url = normalizeUrl(tokens[0]);
      if (!url) continue;

      let width = 0;
      let density = 1;

      if (tokens.length > 1) {
        const desc = tokens[1].toLowerCase();
        if (desc.endsWith('w')) {
          width = parseInt(desc.slice(0, -1), 10) || 0;
        } else if (desc.endsWith('x')) {
          density = parseFloat(desc.slice(0, -1)) || 1;
        }
      }

      candidates.push({ url, width, density });
    }
    return candidates;
  }

  function extractUrlsFromBgStyle(bgStyle) {
    if (!bgStyle || bgStyle === 'none') return [];
    const urls = [];
    const regex = /url\((?:['"]?)(.*?)(?:['"]?)\)/gi;
    let match;
    while ((match = regex.exec(bgStyle)) !== null) {
      const u = match[1];
      if (u && !u.startsWith('data:image/svg+xml;base64,PHN2Zy')) {
        const norm = normalizeUrl(u);
        if (norm) urls.push(norm);
      }
    }
    return urls;
  }

  /**
   * Tìm URL gốc không bị resize từ link WordPress/CDN thumbnail
   * Ví dụ: image-768x495.jpg -> image.jpg
   */
  function getOriginalUnscaledUrl(url) {
    if (!url || typeof url !== 'string') return url;
    try {
      const parsed = new URL(url);
      // Khử suffix WordPress: -1024x768.jpg, -768x495.jpg, -300x193.jpg, -scaled.jpg
      const wpRegex = /^(.+?)(?:-\d{2,4}x\d{2,4}|-scaled)(\.[a-zA-Z0-9]+)$/i;
      const match = parsed.pathname.match(wpRegex);
      if (match) {
        const newPathname = match[1] + match[2];
        const unscaled = new URL(parsed.href);
        unscaled.pathname = newPathname;
        return unscaled.href;
      }
      // Khử query params resize CDN thông dụng: ?resize=..., ?w=..., ?width=...
      if (parsed.searchParams.has('resize') || parsed.searchParams.has('w') || parsed.searchParams.has('width') || parsed.searchParams.has('fit')) {
        const clean = new URL(parsed.href);
        clean.searchParams.delete('resize');
        clean.searchParams.delete('w');
        clean.searchParams.delete('width');
        clean.searchParams.delete('h');
        clean.searchParams.delete('height');
        clean.searchParams.delete('fit');
        clean.searchParams.delete('crop');
        return clean.href;
      }
    } catch {
      // Ignore URL parsing errors
    }
    return url;
  }

  /**
   * Tạo khóa nhận diện canonical base cho ảnh để gom nhóm các phiên bản WebP/JPG/Thumbnails của cùng 1 ảnh
   */
  function getCanonicalImageKey(url) {
    if (!url || typeof url !== 'string') return '';
    if (url.startsWith('data:')) return url;
    try {
      const parsed = new URL(url);
      let path = parsed.pathname.toLowerCase();
      // Bỏ đuôi kích thước -WxH hoặc -scaled
      path = path.replace(/(?:-\d{2,4}x\d{2,4}|-scaled)(?=\.[a-z0-9]+$)/i, '');
      // Bỏ phần mở rộng đuôi file để match giữa .webp và .jpg/.png của cùng 1 gốc
      path = path.replace(/\.(?:jpg|jpeg|png|webp|avif|gif)$/i, '');
      return `${parsed.origin}${path}`;
    } catch {
      return url.toLowerCase();
    }
  }

  function extractAllImages() {
    const rawImagesMap = new Map(); // Canonical Key -> Best Image Object
    const processedElements = new Set();
    const consumedAnchorHrefs = new Set();

    function addCandidateImage(item) {
      if (!item || !item.url) return;
      const cleanUrl = normalizeUrl(item.url);
      if (!cleanUrl) return;

      // Không nạp ảnh 1x1 tracking pixel hoặc placeholder rỗng
      if (item.width === 1 && item.height === 1) return;
      if (cleanUrl.startsWith('data:image/gif;base64,R0lGODlhAQABA')) return;

      const canonicalKey = getCanonicalImageKey(cleanUrl);
      const width = Number(item.width) || 0;
      const height = Number(item.height) || 0;
      const alt = item.alt ? item.alt.trim().slice(0, 150) : '';
      const format = detectFormat(cleanUrl);
      const source = item.source || 'img';

      const existing = rawImagesMap.get(canonicalKey);
      if (!existing) {
        rawImagesMap.set(canonicalKey, {
          url: cleanUrl,
          canonicalKey: canonicalKey,
          width: width,
          height: height,
          alt: alt,
          format: format,
          source: source,
          priority: item.priority || 1
        });
      } else {
        // Nếu tìm thấy phiên bản tốt hơn (độ phân giải cao hơn, ảnh gốc unscaled, hoặc link href gốc)
        const isHigherRes = (width * height) > (existing.width * existing.height);
        const isBetterPriority = (item.priority || 1) > (existing.priority || 1);
        const isUnscaledOriginal = cleanUrl === getOriginalUnscaledUrl(cleanUrl) && existing.url !== getOriginalUnscaledUrl(existing.url);
        
        // Ưu tiên định dạng gốc JPG/PNG hoặc ảnh có kích thước đo được lớn hơn
        if (isHigherRes || isBetterPriority || isUnscaledOriginal) {
          existing.url = cleanUrl;
          if (width > 0) existing.width = width;
          if (height > 0) existing.height = height;
          if (!existing.alt && alt) existing.alt = alt;
          existing.format = format;
          existing.source = source;
          existing.priority = Math.max(existing.priority || 1, item.priority || 1);
        } else {
          // Bổ sung thông tin kích thước/alt nếu bản cũ chưa có
          if ((!existing.width || existing.width === 0) && width > 0) existing.width = width;
          if ((!existing.height || existing.height === 0) && height > 0) existing.height = height;
          if (!existing.alt && alt) existing.alt = alt;
        }
      }
    }

    // Helper function to recursively collect all elements across Light DOM and Shadow DOM
    function getAllDomNodes(root = document) {
      const collected = [];
      const visitedRoots = new Set();

      function traverse(node) {
        if (!node) return;

        if (node.nodeType === 1) { // Node.ELEMENT_NODE
          collected.push(node);

          // Recursively traverse open Shadow DOM if present
          if (node.shadowRoot && !visitedRoots.has(node.shadowRoot)) {
            visitedRoots.add(node.shadowRoot);
            traverse(node.shadowRoot);
          }
        }

        const children = node.children || node.childNodes;
        if (children) {
          for (let i = 0; i < children.length; i++) {
            const child = children[i];
            if (child.nodeType === 1) {
              traverse(child);
            }
          }
        }
      }

      traverse(root);
      return collected;
    }

    const allElements = getAllDomNodes(document);
    const imageExtRegex = /\.(?:jpg|jpeg|png|webp|gif|svg|avif|bmp|ico)(?:\?.*)?$/i;

    // Phase 1: Xử lý các khối <picture> trước để chọn ra 1 ảnh master duy nhất cho mỗi khối <picture>
    allElements.forEach((el) => {
      const tagName = (el.tagName || '').toLowerCase();
      if (tagName === 'picture') {
        processedElements.add(el);
        const imgChild = el.querySelector('img');
        if (imgChild) processedElements.add(imgChild);

        let bestUrl = null;
        let maxWidth = 0;
        let alt = '';
        let naturalW = 0;
        let naturalH = 0;

        if (imgChild) {
          alt = imgChild.alt || imgChild.getAttribute('aria-label') || imgChild.title || '';
          naturalW = imgChild.naturalWidth || imgChild.width || imgChild.clientWidth || 0;
          naturalH = imgChild.naturalHeight || imgChild.height || imgChild.clientHeight || 0;
          bestUrl = imgChild.currentSrc || imgChild.src || imgChild.getAttribute('src');
          maxWidth = naturalW;
        }

        // Duyệt các thẻ <source> trong <picture>
        const sources = el.querySelectorAll('source');
        sources.forEach(srcEl => {
          processedElements.add(srcEl);
          const srcset = srcEl.getAttribute('srcset');
          if (srcset) {
            const parsed = parseSrcsetDetailed(srcset);
            for (const cand of parsed) {
              if (cand.width > maxWidth || !bestUrl) {
                maxWidth = cand.width;
                bestUrl = cand.url;
              }
            }
          }
        });

        // Kiểm tra xem thẻ cha có phải là thẻ <a href="...image"> không
        const parentAnchor = el.closest('a');
        if (parentAnchor) {
          const href = parentAnchor.getAttribute('href');
          if (href && imageExtRegex.test(href)) {
            const normHref = normalizeUrl(href);
            if (normHref) {
              bestUrl = normHref;
              consumedAnchorHrefs.add(normHref);
            }
          }
        }

        if (bestUrl) {
          addCandidateImage({
            url: getOriginalUnscaledUrl(bestUrl),
            width: naturalW || maxWidth,
            height: naturalH,
            alt: alt,
            source: 'picture',
            priority: 4
          });
        }
      }
    });

    // Phase 2: Xử lý toàn bộ các phần tử còn lại
    allElements.forEach((el) => {
      if (processedElements.has(el)) return;
      const tagName = (el.tagName || '').toLowerCase();
      if (tagName === 'script' || tagName === 'style' || tagName === 'noscript') return;

      // 1. Thẻ <img>
      if (tagName === 'img') {
        processedElements.add(el);
        const naturalWidth = el.naturalWidth || el.width || el.clientWidth || 0;
        const naturalHeight = el.naturalHeight || el.height || el.clientHeight || 0;
        const alt = el.alt || el.getAttribute('aria-label') || el.title || '';

        let candidateUrls = [];

        // 1.1 Thẻ cha <a href="...image"> (Lightbox/Full-size Link)
        const parentAnchor = el.closest('a');
        if (parentAnchor) {
          const href = parentAnchor.getAttribute('href');
          if (href && imageExtRegex.test(href)) {
            const normHref = normalizeUrl(href);
            if (normHref) {
              candidateUrls.push({ url: normHref, width: naturalWidth * 2, priority: 5 });
              consumedAnchorHrefs.add(normHref);
            }
          }
        }

        // 1.2 Thuộc tính lazy-load độ phân giải cao
        const lazyAttrs = [
          'data-zoom-image', 'data-high-res-src', 'data-full-image',
          'data-original', 'data-src', 'data-lazy-src', 'data-url',
          'data-bsrjs', 'data-orig-file'
        ];
        for (const attr of lazyAttrs) {
          const lazySrc = el.getAttribute(attr);
          if (lazySrc) {
            const norm = normalizeUrl(lazySrc);
            if (norm) candidateUrls.push({ url: norm, width: naturalWidth, priority: 3 });
          }
        }

        // 1.3 Thuộc tính srcset
        const srcset = el.getAttribute('srcset') || el.getAttribute('data-srcset');
        if (srcset) {
          const parsed = parseSrcsetDetailed(srcset);
          parsed.forEach(c => candidateUrls.push({ url: c.url, width: c.width || naturalWidth, priority: 2 }));
        }

        // 1.4 Thuộc tính src & currentSrc
        const src = el.currentSrc || el.src || el.getAttribute('src');
        if (src) {
          const norm = normalizeUrl(src);
          if (norm) candidateUrls.push({ url: norm, width: naturalWidth, priority: 1 });
        }

        // Chọn URL chất lượng cao nhất cho <img> này
        if (candidateUrls.length > 0) {
          // Sắp xếp theo ưu tiên và độ rộng
          candidateUrls.sort((a, b) => (b.priority - a.priority) || (b.width - a.width));
          const best = candidateUrls[0];
          addCandidateImage({
            url: getOriginalUnscaledUrl(best.url),
            width: naturalWidth || best.width,
            height: naturalHeight,
            alt: alt,
            source: 'img',
            priority: best.priority
          });
        }
      }

      // 2. CSS background-image (kèm ::before & ::after pseudo-elements)
      try {
        const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
        const w = Math.round(rect.width || 0);
        const h = Math.round(rect.height || 0);

        // Main element background
        const style = window.getComputedStyle(el);
        const bgImage = style ? style.backgroundImage : null;
        if (bgImage && bgImage !== 'none') {
          const urls = extractUrlsFromBgStyle(bgImage);
          urls.forEach(u => addCandidateImage({ url: getOriginalUnscaledUrl(u), width: w, height: h, alt: '', source: 'background', priority: 1 }));
        }

        // ::before pseudo-element
        const beforeStyle = window.getComputedStyle(el, '::before');
        const beforeBg = beforeStyle ? beforeStyle.backgroundImage : null;
        if (beforeBg && beforeBg !== 'none') {
          const urls = extractUrlsFromBgStyle(beforeBg);
          urls.forEach(u => addCandidateImage({ url: getOriginalUnscaledUrl(u), width: w, height: h, alt: '', source: 'bg-before', priority: 1 }));
        }

        // ::after pseudo-element
        const afterStyle = window.getComputedStyle(el, '::after');
        const afterBg = afterStyle ? afterStyle.backgroundImage : null;
        if (afterBg && afterBg !== 'none') {
          const urls = extractUrlsFromBgStyle(afterBg);
          urls.forEach(u => addCandidateImage({ url: getOriginalUnscaledUrl(u), width: w, height: h, alt: '', source: 'bg-after', priority: 1 }));
        }
      } catch {
        // Skip un-computable elements
      }

      // 3. Thẻ <input type="image">
      if (tagName === 'input' && el.type === 'image') {
        const src = el.getAttribute('src');
        if (src) {
          const w = el.naturalWidth || el.width || el.clientWidth || 0;
          const h = el.naturalHeight || el.height || el.clientHeight || 0;
          addCandidateImage({ url: src, width: w, height: h, alt: el.alt || 'Input Image', source: 'input-image', priority: 2 });
        }
      }

      // 4. Thẻ <video poster="...">
      if (tagName === 'video') {
        const poster = el.getAttribute('poster');
        if (poster) {
          const w = el.videoWidth || el.clientWidth || 0;
          const h = el.videoHeight || el.clientHeight || 0;
          addCandidateImage({ url: poster, width: w, height: h, alt: 'Video Poster', source: 'video-poster', priority: 2 });
        }
      }

      // 5. Thẻ <a href="..."> liên kết trực tiếp tới file ảnh độc lập (chưa bị tiêu thụ bởi <img> bên trong)
      if (tagName === 'a') {
        const href = el.getAttribute('href');
        if (href && imageExtRegex.test(href)) {
          const normHref = normalizeUrl(href);
          if (normHref && !consumedAnchorHrefs.has(normHref)) {
            addCandidateImage({
              url: getOriginalUnscaledUrl(normHref),
              width: 0,
              height: 0,
              alt: el.textContent ? el.textContent.trim().slice(0, 80) : 'Link Image',
              source: 'anchor-link',
              priority: 2
            });
          }
        }
      }

      // 6. Thẻ <canvas>
      if (tagName === 'canvas') {
        try {
          if (el.width > 30 && el.height > 30) {
            const dataUrl = el.toDataURL('image/png');
            addCandidateImage({ url: dataUrl, width: el.width, height: el.height, alt: 'Canvas Image', source: 'canvas', priority: 1 });
          }
        } catch {
          // Tainted canvas security error
        }
      }

      // 7. Inline <svg> tags
      if (tagName === 'svg') {
        try {
          const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
          const w = Math.round(rect.width || 0);
          const h = Math.round(rect.height || 0);
          if (w >= 32 && h >= 32) {
            const serializer = new XMLSerializer();
            let svgStr = serializer.serializeToString(el);
            if (!svgStr.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
              svgStr = svgStr.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
            }
            const svgDataUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);
            addCandidateImage({ url: svgDataUrl, width: w, height: h, alt: 'SVG Vector', source: 'svg-inline', priority: 1 });
          }
        } catch {
          // Ignore serialization issues
        }
      }
    });

    // Phase 3: Quét thẻ <meta> OpenGraph / Twitter Card & <link> trên Document (chỉ thêm nếu chưa có trong bài viết)
    try {
      const metaElements = document.querySelectorAll('meta[property*="image"], meta[name*="image"], meta[itemprop="image"]');
      metaElements.forEach((meta) => {
        const content = meta.getAttribute('content');
        if (content) {
          addCandidateImage({
            url: getOriginalUnscaledUrl(content),
            width: 0,
            height: 0,
            alt: meta.getAttribute('property') || meta.getAttribute('name') || 'Meta Image',
            source: 'meta-tag',
            priority: 1
          });
        }
      });

      const linkIcons = document.querySelectorAll('link[rel*="icon"], link[rel="image_src"], link[rel*="apple-touch-icon"]');
      linkIcons.forEach((link) => {
        const href = link.getAttribute('href');
        if (href) {
          addCandidateImage({
            url: href,
            width: 0,
            height: 0,
            alt: link.getAttribute('rel') || 'Link Icon',
            source: 'link-tag',
            priority: 1
          });
        }
      });
    } catch {
      // Ignore head query errors
    }

    // Trả về danh sách ảnh đã được khử trùng lặp và làm sạch hoàn toàn
    return Array.from(rawImagesMap.values()).map(item => ({
      url: item.url,
      width: item.width,
      height: item.height,
      alt: item.alt,
      format: item.format,
      source: item.source
    }));
  }

  // Cho phép gọi trực tiếp hoặc trả về kết quả cho executeScript
  return extractAllImages();
})();
