// Test Extension Manifest & Files Verification
const fs = require('fs');
const path = require('path');

function testExtension() {
  console.log('--- Bắt đầu kiểm tra Chrome Extension ---');

  // 1. Check manifest.json
  const manifestPath = path.join(__dirname, 'manifest.json');
  if (!fs.existsSync(manifestPath)) {
    throw new Error('Thiếu manifest.json');
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  console.log('✓ Manifest Version:', manifest.manifest_version);
  console.log('✓ Name:', manifest.name);
  console.log('✓ Permissions:', manifest.permissions.join(', '));
  console.log('✓ Host Permissions:', manifest.host_permissions.join(', '));

  // 2. Check files referenced in manifest
  const popupHtml = path.join(__dirname, manifest.action.default_popup);
  if (!fs.existsSync(popupHtml)) throw new Error('Thiếu popup.html');
  console.log('✓ Popup HTML tồn tại:', manifest.action.default_popup);

  for (const [size, iconPath] of Object.entries(manifest.icons)) {
    const fullIconPath = path.join(__dirname, iconPath);
    if (!fs.existsSync(fullIconPath)) throw new Error(`Thiếu icon ${size}: ${iconPath}`);
    console.log(`✓ Icon ${size}x${size} tồn tại:`, iconPath);
  }

  // 3. Check extractor script
  const extractorPath = path.join(__dirname, 'scripts', 'extractor.js');
  if (!fs.existsSync(extractorPath)) throw new Error('Thiếu scripts/extractor.js');
  console.log('✓ Script extractor.js tồn tại');

  // 4. Check popup.css & popup.js
  const popupCss = path.join(__dirname, 'popup', 'popup.css');
  const popupJs = path.join(__dirname, 'popup', 'popup.js');
  if (!fs.existsSync(popupCss)) throw new Error('Thiếu popup/popup.css');
  if (!fs.existsSync(popupJs)) throw new Error('Thiếu popup/popup.js');
  console.log('✓ Popup CSS & JS tồn tại');

  console.log('--- Toàn bộ kiểm tra cấu trúc extension thành công 100%! ---');
}

testExtension();
