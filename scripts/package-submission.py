"""Package only Git-visible source/evidence; ignored credentials/dumps stay out."""
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
manifest_path = 'evidence/submission-manifest.json'
files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
files = sorted(set(f for f in files if f and f != manifest_path and (ROOT/f).is_file()))
assert all(not Path(f).is_absolute() and '..' not in Path(f).parts for f in files)
assert not any(f == '.env' or f.startswith(('.local/', '.venv/', 'frontend/node_modules/')) or f.endswith('.dump') for f in files)
entries = [{'path': f, 'sha256': hashlib.sha256((ROOT/f).read_bytes()).hexdigest()} for f in files]
(ROOT/manifest_path).write_text(json.dumps({'files': entries, 'excluded': 'ignored files, Git internals and this self-referential manifest'}, indent=2), encoding='utf-8')
output = (ROOT/'.local'/'tripsync-phase4-submission.zip').resolve()
assert output.is_relative_to((ROOT/'.local').resolve())
output.parent.mkdir(exist_ok=True)
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for file in files+[manifest_path]: archive.write(ROOT/file, file)
print('Packaged', len(files)+1, 'files; SHA256', hashlib.sha256(output.read_bytes()).hexdigest())
