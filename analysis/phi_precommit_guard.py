#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pre-commit guard: refuse the commit if patient data or credentials are staged.

Why this exists, and why a .gitignore is not enough.

A .gitignore only blocks paths that match a pattern someone thought of in
advance. The companion repository in this series had its firewall patched three
separate times, each time after a file turned out to be untracked-but-addable —
one `git add .` away from being published. A pattern list is a memory of past
mistakes, not a guard against the next one.

This guard reads what is actually staged and looks for the *shape* of the data
rather than the *name* of the file. It refuses the commit rather than warning,
because a warning during a busy day is a warning that gets scrolled past.

Install:
    python analysis/phi_precommit_guard.py --install

Bypass is deliberately not provided. If a legitimate string trips it, quote the
finding and decide in the open, rather than adding a flag that will one day be
used in a hurry.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

# Shapes, not names. Each is a class of identifier that must never be published.
BLOCKING = [
    ('national identifier (TW)', re.compile(rb'\b[A-Z][12]\d{8}\b')),
    ('mobile number (TW)', re.compile(rb'\b09\d{2}-?\d{3}-?\d{3}\b')),
    ('mobile number (+886)', re.compile(rb'\+?886-?9\d{8}\b')),
    ('landline (TW)', re.compile(rb'\b0[2-8]-?\d{3,4}-?\d{4}\b')),
    ('record composite key', re.compile(rb'\b\d{4,8}[A-Z]\d{15,}\b')),
    ('API key / token', re.compile(
        rb'\b(sk-ant-|sk-proj-|AIza|ghp_|github_pat_|xoxb-)[A-Za-z0-9_\-]{10,}')),
    ('absolute user path', re.compile(rb'C:\\Users\\[A-Za-z0-9_]+')),
    # A *path*, not the word. Narrowed 2026-09-25: the first version matched the
    # bare name, so it refused a file whose Chinese comments explain the rule -
    # documentation of a protection has to be able to name what it protects.
    # A separator on either side is what makes it a path rather than prose.
    ('path into clinical storage', re.compile(
        rb'[\\/](?:Patient_Records|VR6AI4_Consolidated|VR6AI4_Workspace)'
        rb'|(?:Patient_Records|VR6AI4_Consolidated|VR6AI4_Workspace)[\\/]')),
]

HOOK = """#!/bin/sh
# Installed by analysis/phi_precommit_guard.py — do not edit by hand.
exec python "$(git rev-parse --show-toplevel)/analysis/phi_precommit_guard.py"
"""


def install() -> int:
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                         capture_output=True).stdout.decode().strip()
    if not top:
        print('not inside a git repository')
        return 1
    path = os.path.join(top, '.git', 'hooks', 'pre-commit')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(HOOK)
    os.chmod(path, 0o755)
    print(f'installed: {path}')
    print('Every commit in this repository is now scanned before it is recorded.')
    return 0


def main() -> int:
    if '--install' in sys.argv:
        return install()

    staged = subprocess.run(['git', 'diff', '--cached', '--name-only', '-z'],
                            capture_output=True).stdout.decode().split('\x00')
    staged = [f for f in staged if f]
    findings = []
    for path in staged:
        # This file carries the patterns themselves, so it matches its own rules.
        # The exemption is exactly one path and is stated here rather than made
        # configurable: a general "skip" mechanism is the thing that eventually
        # gets pointed at the file that actually matters.
        if path == 'analysis/phi_precommit_guard.py':
            continue
        blob = subprocess.run(['git', 'show', f':{path}'], capture_output=True).stdout
        if b'\x00' in blob[:4096]:          # binary
            continue
        for label, pat in BLOCKING:
            hits = pat.findall(blob)
            if hits:
                findings.append((path, label, len(hits)))

    if not findings:
        print(f'PHI guard: {len(staged)} staged file(s) clean')
        return 0

    print('')
    print('COMMIT REFUSED — staged content matches a protected pattern.')
    print('')
    for path, label, n in findings:
        print(f'  {path}')
        print(f'      {label} x{n}')
    print('')
    print('Nothing has been committed. Remove the content, or if the match is a')
    print('false positive, say so explicitly in the commit message after')
    print('narrowing the pattern in analysis/phi_precommit_guard.py.')
    print('')
    return 1


if __name__ == '__main__':
    sys.exit(main())
