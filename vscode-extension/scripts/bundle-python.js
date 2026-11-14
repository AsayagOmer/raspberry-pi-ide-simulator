// Copies the Python backend (src/core, src/pi5sim) and the license into the extension before packaging.
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..', '..');
const ext = path.join(__dirname, '..');
const out = path.join(ext, 'python');

fs.rmSync(out, { recursive: true, force: true });
for (const pkg of ['core', 'pi5sim']) {
  fs.cpSync(path.join(root, 'src', pkg), path.join(out, pkg), {
    recursive: true,
    filter: (p) => !p.includes('__pycache__'),
  });
}
fs.copyFileSync(path.join(root, 'requirements.txt'), path.join(out, 'requirements.txt'));
fs.copyFileSync(path.join(root, 'LICENSE.md'), path.join(ext, 'LICENSE.md'));
console.log('Bundled Python backend into', out);
