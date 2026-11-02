"""Scan tracked/current submission files and reachable Git blobs without printing secrets.

This is a bounded signature/configured-secret check, not a credential audit service.
No raw file content, matches, or local configuration is emitted.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
config = dotenv_values(ROOT/'.env')
secrets = [v.encode() for k, v in config.items() if v and len(v) >= 16 and any(s in k for s in ('KEY', 'SECRET', 'PASSWORD', 'DATABASE_URL'))]
patterns = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'\bAKIA[0-9A-Z]{16}\b'), re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(rb'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{20,}\b')]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def suspect(data):
    return any(value in data for value in secrets) or any(p.search(data) for p in patterns)


files = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
findings, checked = [], 0
for file in filter(None, files):
    path = ROOT/file
    if path.is_file():
        checked += 1
        if suspect(path.read_bytes()): findings.append({'scope': 'worktree', 'file': file})
objects = git('rev-list', '--objects', '--all').decode().splitlines()
proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
blobs = 0
for entry in objects:
    oid = entry.split(' ', 1)[0]
    proc.stdin.write((oid+'\n').encode()); proc.stdin.flush()
    header = proc.stdout.readline().split()
    size = int(header[2])
    data = proc.stdout.read(size); proc.stdout.read(1)
    if header[1] == b'blob':
        blobs += 1
        if suspect(data): findings.append({'scope': 'history', 'object': oid})
proc.stdin.close(); proc.wait(timeout=10)
report = {'scanBaseCommit': git('rev-parse', 'HEAD').decode().strip(),
    'worktreeFiles': checked, 'reachableHistoryBlobs': blobs, 'findings': findings,
    'checks': 'configured long secret values; private-key headers; AWS/GitHub/JWT signatures',
    'limitations': 'Does not detect every provider, old rotated secret, entropy-only credential, ignored local file, or unreachable Git object.'}
out = ROOT/'evidence'/'security'
out.mkdir(parents=True, exist_ok=True)
(out/'secret-scan.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(bool(findings))
