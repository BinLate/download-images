/**
 * Image Extractor Script for Chrome Extension
 * Quét toàn bộ hình ảnh trên trang web hiện tại: <img>, <picture>, background-image (kèm pseudo-elements),
 * meta tags (og:image, twitter:image), link tags, video poster, a[href], input[type=image], svg, canvas...
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
      return new URL(trimmed, document.baseURI || window.location.href).href;
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

  function parseSrcset(srcsetStr) {
    if (!srcsetStr) return [];
    const urls = [];
    const candidates = srcsetStr.split(',');
    for (const cand of candidates) {
      const parts = cand.trim().split(/\s+/);
      if (parts[0]) {
        const fullUrl = normalizeUrl(parts[0]);
        if (fullUrl) urls.push(fullUrl);
      }
    }
    return urls;
  }

  function extractUrlsFromBgStyle(bgStyle) {
    if (!bgStyle || bgStyle === 'none') return [];
    const urls = [];
    const regex = /url\((?:['"]?)(.*?)(?:['"]?)\)/gi;
    let match;
    while ((match = regex.exec(bgStyle)) !== null) {
      const u = match[1];
      if (u && !u.startsWith('data:image/svg+xml;base64,PHN2Zy')) {
        urls.push(u);
      }
    }
    return urls;
  }

  function extractAllImages() {
    const imagesMap = new Map();

    function addImage(url, width = 0, height = 0, alt = '', source = 'img') {
      const cleanUrl = normalizeUrl(url);
      if (!cleanUrl) return;

      const existing = imagesMap.get(cleanUrl);
      if (existing) {
        // Cập nhật nếu tìm thấy kích thước lớn hơn hoặc thông tin chi tiết hơn
        if ((!existing.width || existing.width === 0) && width > 0) {
          existing.width = width;
        }
        if ((!existing.height || existing.height === 0) && height > 0) {
          existing.height = height;
        }
        if (!existing.alt && alt) {
          existing.alt = alt;
        }
      } else {
        imagesMap.set(cleanUrl, {
          url: cleanUrl,
          width: Number(width) || 0,
          height: Number(height) || 0,
          alt: alt ? alt.trim().slice(0, 150) : '',
          format: detectFormat(cleanUrl),
          source: source
        });
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

    // Process all elements in Light DOM & Shadow DOM
    allElements.forEach((el) => {
      const tagName = (el.tagName || '').toLowerCase();
      if (tagName === 'script' || tagName === 'style' || tagName === 'noscript') return;

      // 1. Thẻ <img>
      if (tagName === 'img') {
        const src = el.currentSrc || el.src || el.getAttribute('src');
        const naturalWidth = el.naturalWidth || el.width || el.clientWidth || 0;
        const naturalHeight = el.naturalHeight || el.height || el.clientHeight || 0;
        const alt = el.alt || el.getAttribute('aria-label') || el.title || '';

        if (src) {
          addImage(src, naturalWidth, naturalHeight, alt, 'img');
        }

        // Check lazy-load attributes
        const lazyAttrs = ['data-src', 'data-original', 'data-url', 'data-lazy-src', 'data-high-res-src', 'data-srcset'];
        for (const attr of lazyAttrs) {
          const lazySrc = el.getAttribute(attr);
          if (lazySrc) {
            if (attr === 'data-srcset') {
              const parsed = parseSrcset(lazySrc);
              parsed.forEach(u => addImage(u, naturalWidth, naturalHeight, alt, 'img-lazy-srcset'));
            } else {
              addImage(lazySrc, naturalWidth, naturalHeight, alt, 'img-lazy');
            }
          }
        }

        // Check srcset
        const srcset = el.getAttribute('srcset');
        if (srcset) {
          const srcsetUrls = parseSrcset(srcset);
          srcsetUrls.forEach(u => addImage(u, naturalWidth, naturalHeight, alt, 'srcset'));
        }
      }

      // 2. Thẻ <picture> & <source>
      if (tagName === 'source' && el.parentElement && el.parentElement.tagName.toLowerCase() === 'picture') {
        const srcset = el.getAttribute('srcset');
        if (srcset) {
          const srcsetUrls = parseSrcset(srcset);
          srcsetUrls.forEach(u => addImage(u, 0, 0, '', 'picture-source'));
        }
      }

      // 3. CSS background-image (kèm ::before & ::after pseudo-elements)
      try {
        const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
        const w = Math.round(rect.width || 0);
        const h = Math.round(rect.height || 0);

        // Main element background
        const style = window.getComputedStyle(el);
        const bgImage = style ? style.backgroundImage : null;
        if (bgImage && bgImage !== 'none') {
          const urls = extractUrlsFromBgStyle(bgImage);
          urls.forEach(u => addImage(u, w, h, '', 'background'));
        }

        // ::before pseudo-element
        const beforeStyle = window.getComputedStyle(el, '::before');
        const beforeBg = beforeStyle ? beforeStyle.backgroundImage : null;
        if (beforeBg && beforeBg !== 'none') {
          const urls = extractUrlsFromBgStyle(beforeBg);
          urls.forEach(u => addImage(u, w, h, '', 'bg-before'));
        }

        // ::after pseudo-element
        const afterStyle = window.getComputedStyle(el, '::after');
        const afterBg = afterStyle ? afterStyle.backgroundImage : null;
        if (afterBg && afterBg !== 'none') {
          const urls = extractUrlsFromBgStyle(afterBg);
          urls.forEach(u => addImage(u, w, h, '', 'bg-after'));
        }
      } catch {
        // Skip un-computable elements
      }

      // 4. Thẻ <input type="image">
      if (tagName === 'input' && el.type === 'image') {
        const src = el.getAttribute('src');
        if (src) {
          const w = el.naturalWidth || el.width || el.clientWidth || 0;
          const h = el.naturalHeight || el.height || el.clientHeight || 0;
          addImage(src, w, h, el.alt || 'Input Image', 'input-image');
        }
      }

      // 5. Thẻ <video poster="...">
      if (tagName === 'video') {
        const poster = el.getAttribute('poster');
        if (poster) {
          const w = el.videoWidth || el.clientWidth || 0;
          const h = el.videoHeight || el.clientHeight || 0;
          addImage(poster, w, h, 'Video Poster', 'video-poster');
        }
      }

      // 6. Thẻ <a href="..."> liên kết trực tiếp tới file ảnh
      if (tagName === 'a') {
        const href = el.getAttribute('href');
        if (href && imageExtRegex.test(href)) {
          addImage(href, 0, 0, el.textContent || 'Link Image', 'anchor-link');
        }
      }

      // 7. Thẻ <canvas>
      if (tagName === 'canvas') {
        try {
          if (el.width > 30 && el.height > 30) {
            const dataUrl = el.toDataURL('image/png');
            addImage(dataUrl, el.width, el.height, 'Canvas Image', 'canvas');
          }
        } catch {
          // Tainted canvas security error
        }
      }

      // 8. Inline <svg> tags
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
            addImage(svgDataUrl, w, h, 'SVG Vector', 'svg-inline');
          }
        } catch {
          // Ignore serialization issues
        }
      }
    });

    // 9. Quét thẻ <meta> OpenGraph / Twitter Card & <link> trên Document
    try {
      const metaElements = document.querySelectorAll('meta[property*="image"], meta[name*="image"], meta[itemprop="image"]');
      metaElements.forEach((meta) => {
        const content = meta.getAttribute('content');
        if (content) {
          addImage(content, 0, 0, meta.getAttribute('property') || meta.getAttribute('name') || 'Meta Image', 'meta-tag');
        }
      });

      const linkIcons = document.querySelectorAll('link[rel*="icon"], link[rel="image_src"], link[rel*="apple-touch-icon"]');
      linkIcons.forEach((link) => {
        const href = link.getAttribute('href');
        if (href) {
          addImage(href, 0, 0, link.getAttribute('rel') || 'Link Icon', 'link-tag');
        }
      });
    } catch {
      // Ignore head query errors
    }

    return Array.from(imagesMap.values());
  }

  // Cho phép gọi trực tiếp hoặc trả về kết quả cho executeScript
  return extractAllImages();
})();

