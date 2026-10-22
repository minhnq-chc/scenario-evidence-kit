"""Copy a freshly built UI into the Python package for wheel distribution."""

import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'frontend/dist'
target = root / 'src/scenario_evidence/web'
if not (source / 'index.html').is_file():
    raise SystemExit('Run npm ci && npm run build in frontend first.')
# Only replace build products underneath this project's package.
if target.exists():
    if not target.resolve().is_relative_to((root / 'src/scenario_evidence').resolve()):
        raise SystemExit('Unexpected build target')
    shutil.rmtree(target)
shutil.copytree(source, target)
notices = []
for package in ('react', 'react-dom', 'scheduler'):
    license_file = root / 'frontend/node_modules' / package / 'LICENSE'
    if not license_file.is_file():
        raise SystemExit(f'Missing upstream notice: {package}')
    notices.append(package + '\n' + license_file.read_text(encoding='utf-8'))
(target / 'assets/THIRD_PARTY_LICENSES.txt').write_text('\n\n'.join(notices), encoding='utf-8')
print('Web assets included in Python package.')
