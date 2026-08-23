/**
 * Image Extractor Script for Chrome Extension
 * Quét toàn bộ hình ảnh trên trang web hiện tại: <img>, <picture>, background-image, svg, video poster, link ảnh...
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

    // 1. Quét thẻ <img>
    const imgElements = document.querySelectorAll('img');
    imgElements.forEach((img) => {
      const src = img.currentSrc || img.src || img.getAttribute('src');
      const naturalWidth = img.naturalWidth || img.width || img.clientWidth || 0;
      const naturalHeight = img.naturalHeight || img.height || img.clientHeight || 0;
      const alt = img.alt || img.getAttribute('aria-label') || img.title || '';

      if (src) {
        addImage(src, naturalWidth, naturalHeight, alt, 'img');
      }

      // Check lazy-load attributes
      const lazyAttrs = ['data-src', 'data-original', 'data-url', 'data-lazy-src', 'data-high-res-src'];
      for (const attr of lazyAttrs) {
        const lazySrc = img.getAttribute(attr);
        if (lazySrc) {
          addImage(lazySrc, naturalWidth, naturalHeight, alt, 'img-lazy');
        }
      }

      // Check srcset
      const srcset = img.getAttribute('srcset');
      if (srcset) {
        const srcsetUrls = parseSrcset(srcset);
        srcsetUrls.forEach(u => addImage(u, 0, 0, alt, 'srcset'));
      }
    });

    // 2. Quét thẻ <picture> & <source>
    const sourceElements = document.querySelectorAll('picture source');
    sourceElements.forEach((source) => {
      const srcset = source.getAttribute('srcset');
      if (srcset) {
        const srcsetUrls = parseSrcset(srcset);
        srcsetUrls.forEach(u => addImage(u, 0, 0, '', 'picture-source'));
      }
    });

    // 3. Quét CSS background-image từ tất cả phần tử DOM
    const allElements = document.querySelectorAll('*');
    const bgUrlRegex = /url\((?:['"]?)(.*?)(?:['"]?)\)/gi;

    allElements.forEach((el) => {
      // Bỏ qua thẻ script, style
      const tagName = el.tagName.toLowerCase();
      if (tagName === 'script' || tagName === 'style' || tagName === 'noscript') return;

      try {
        const style = window.getComputedStyle(el);
        const bgImage = style.backgroundImage;
        if (bgImage && bgImage !== 'none') {
          let match;
          while ((match = bgUrlRegex.exec(bgImage)) !== null) {
            const url = match[1];
            if (url && !url.startsWith('data:image/svg+xml;base64,PHN2Zy')) { // bỏ qua một số data svg placeholder rác
              const rect = el.getBoundingClientRect();
              const w = Math.round(rect.width);
              const h = Math.round(rect.height);
              addImage(url, w, h, '', 'background');
            }
          }
        }
      } catch {
        // Skip un-computable elements
      }
    });

    // 4. Quét thẻ <video poster="...">
    const videoElements = document.querySelectorAll('video[poster]');
    videoElements.forEach((video) => {
      const poster = video.getAttribute('poster');
      if (poster) {
        const w = video.videoWidth || video.clientWidth || 0;
        const h = video.videoHeight || video.clientHeight || 0;
        addImage(poster, w, h, 'Video Poster', 'video-poster');
      }
    });

    // 5. Quét thẻ <a href="..."> liên kết trực tiếp tới file ảnh
    const anchorElements = document.querySelectorAll('a[href]');
    const imageExtRegex = /\.(?:jpg|jpeg|png|webp|gif|svg|avif|bmp|ico)(?:\?.*)?$/i;
    anchorElements.forEach((a) => {
      const href = a.getAttribute('href');
      if (href && imageExtRegex.test(href)) {
        addImage(href, 0, 0, a.textContent || 'Link Image', 'anchor-link');
      }
    });

    // 6. Quét thẻ <canvas>
    const canvasElements = document.querySelectorAll('canvas');
    canvasElements.forEach((canvas) => {
      try {
        if (canvas.width > 30 && canvas.height > 30) {
          const dataUrl = canvas.toDataURL('image/png');
          addImage(dataUrl, canvas.width, canvas.height, 'Canvas Image', 'canvas');
        }
      } catch {
        // Tainted canvas security error
      }
    });

    // 7. Inline <svg> tags (nếu có kích thước đủ lớn > 32px)
    const svgElements = document.querySelectorAll('svg');
    svgElements.forEach((svg) => {
      try {
        const rect = svg.getBoundingClientRect();
        const w = Math.round(rect.width);
        const h = Math.round(rect.height);
        if (w >= 32 && h >= 32) {
          const serializer = new XMLSerializer();
          let svgStr = serializer.serializeToString(svg);
          if (!svgStr.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
            svgStr = svgStr.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
          }
          const svgDataUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);
          addImage(svgDataUrl, w, h, 'SVG Vector', 'svg-inline');
        }
      } catch {
        // Ignore serialization issues
      }
    });

    return Array.from(imagesMap.values());
  }

  // Cho phép gọi trực tiếp hoặc trả về kết quả cho executeScript
  return extractAllImages();
})();
