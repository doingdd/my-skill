#!/usr/bin/env python3
"""Build a reader candidate and promote it only after browser validation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from assemble_split import main as assemble_reader
from assemble_v3 import main as assemble_reader_v3
from visual_verdict import validate_visual_verdict


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
    visual_verdict_path=None,
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
        if validator is None:
            def gate(path):
                run_browser_gate(path, shots_dir)
                if visual_verdict_path:
                    validate_visual_verdict(visual_verdict_path, candidate_path=path)
        else:
            gate = validator
        promote_candidate(candidate, final, gate)
    finally:
        if candidate.exists():
            candidate.unlink()
    print(f'reader promoted -> {final} (browser gate: {DESKTOP_VIEWPORTS})')


def build_reader_v3(
    blocks_path,
    spec_path,
    final_path,
    shots_dir,
    *,
    visual_verdict_path=None,
    producer_id=None,
    assembler=assemble_reader_v3,
    browser_validator=None,
):
    """Compile v3 and promote only after browser and independent visual gates."""
    if not visual_verdict_path:
        raise ValueError('v3 晋升必须提供 visual-verdict.json')
    if not str(producer_id or '').strip():
        raise ValueError('v3 晋升必须由编排器提供 producer_id')
    final = Path(final_path)
    final.parent.mkdir(parents=True, exist_ok=True)
    with open(spec_path, encoding='utf-8') as handle:
        spec = json.load(handle)
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
            os.fspath(spec_path),
            os.fspath(candidate),
        )

        def gate(path):
            browser_gate = browser_validator or (
                lambda candidate_path: run_browser_gate(candidate_path, shots_dir)
            )
            browser_gate(path)
            validate_visual_verdict(
                visual_verdict_path,
                candidate_path=path,
                candidate_ref=f'{final.stem}.candidate.html',
                producer_id=producer_id,
                require_digest=True,
                spec=spec,
            )

        promote_candidate(candidate, final, gate)
    finally:
        if candidate.exists():
            candidate.unlink()
    print(
        f'reader v3 promoted -> {final} '
        f'(browser gate: {DESKTOP_VIEWPORTS}; visual verdict: PASS)'
    )


def main(argv=None):
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == 'v3':
        parser = argparse.ArgumentParser(
            description='Compile a v3 view-spec and promote it after all gates pass.',
        )
        parser.add_argument('blocks')
        parser.add_argument('spec')
        parser.add_argument('output')
        parser.add_argument('--shots-dir')
        parser.add_argument('--visual-verdict', required=True)
        parser.add_argument('--producer-id', required=True)
        args = parser.parse_args(raw_args[1:])
        output = Path(args.output)
        shots = Path(args.shots_dir) if args.shots_dir else output.parent / 'shots'
        build_reader_v3(
            args.blocks,
            args.spec,
            output,
            shots,
            visual_verdict_path=args.visual_verdict,
            producer_id=args.producer_id,
        )
        return

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
    parser.add_argument(
        '--visual-verdict',
        help='可选的 visual-verdict.json；提供后会作为晋升强门禁',
    )
    args = parser.parse_args(raw_args)
    output = Path(args.output)
    shots = Path(args.shots_dir) if args.shots_dir else output.parent / 'shots'
    build_reader(
        args.blocks,
        args.fragments,
        args.views,
        output,
        shots,
        visual_verdict_path=args.visual_verdict,
    )


if __name__ == '__main__':
    main()


__all__ = [
    'DESKTOP_VIEWPORTS',
    'build_reader',
    'build_reader_v3',
    'promote_candidate',
    'run_browser_gate',
]
