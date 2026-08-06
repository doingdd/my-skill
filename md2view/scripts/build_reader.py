#!/usr/bin/env python3
"""Build a reader candidate and promote it only after browser validation."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from assemble_split import main as assemble_reader


DESKTOP_VIEWPORTS = '1440,1280,1024,768'


def promote_candidate(candidate_path, final_path, validator):
    candidate_path = os.fspath(candidate_path)
    final_path = os.fspath(final_path)
    validator(candidate_path)
    os.replace(candidate_path, final_path)


def run_browser_gate(candidate_path, shots_dir):
    script_path = Path(__file__).with_name('shot.js')
    command = [
        'node',
        str(script_path),
        os.fspath(candidate_path),
        os.fspath(shots_dir),
        f'--viewports={DESKTOP_VIEWPORTS}',
    ]
    subprocess.run(command, check=True)


def build_reader(
    blocks_path,
    fragments_dir,
    views_path,
    final_path,
    shots_dir,
    *,
    assembler=assemble_reader,
    validator=None,
):
    """Assemble to a sibling temp file; expose it only after the browser gate passes."""
    final = Path(final_path)
    final.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f'.{final.stem}.',
        suffix='.candidate.html',
        dir=final.parent,
        delete=False,
    ) as handle:
        candidate = Path(handle.name)

    try:
        assembler(
            os.fspath(blocks_path),
            os.fspath(fragments_dir),
            os.fspath(views_path),
            os.fspath(candidate),
        )
        gate = validator or (lambda path: run_browser_gate(path, shots_dir))
        promote_candidate(candidate, final, gate)
    finally:
        if candidate.exists():
            candidate.unlink()
    print(f'reader promoted -> {final} (browser gate: {DESKTOP_VIEWPORTS})')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='组装候选 reader，并仅在桌面浏览器门禁通过后原子替换最终文件。',
    )
    parser.add_argument('blocks')
    parser.add_argument('fragments')
    parser.add_argument('views')
    parser.add_argument('output')
    parser.add_argument(
        '--shots-dir',
        help='截图与失败诊断目录；默认是输出文件旁的 shots/',
    )
    args = parser.parse_args(argv)
    output = Path(args.output)
    shots = Path(args.shots_dir) if args.shots_dir else output.parent / 'shots'
    build_reader(args.blocks, args.fragments, args.views, output, shots)


if __name__ == '__main__':
    main()


__all__ = ['DESKTOP_VIEWPORTS', 'build_reader', 'promote_candidate', 'run_browser_gate']
