#!/usr/bin/env python3
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import build_reader as build_reader_module
from assemble_split import cli as assemble_cli, main as assemble_candidate
from build_reader import build_reader, build_reader_v3, promote_candidate


class AtomicReaderPromotionTests(unittest.TestCase):
    def test_direct_assembler_api_cannot_overwrite_final_reader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            final = Path(tmpdir) / 'reader.html'
            final.write_text('known good reader', encoding='utf-8')

            with self.assertRaisesRegex(ValueError, r'candidate\.html'):
                assemble_candidate(
                    'missing-blocks.json',
                    'missing-fragments',
                    'missing-views.json',
                    str(final),
                )

            self.assertEqual(final.read_text(encoding='utf-8'), 'known good reader')

    def test_direct_assembler_cli_cannot_overwrite_final_reader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            final = Path(tmpdir) / 'reader.html'
            final.write_text('known good reader', encoding='utf-8')

            with self.assertRaisesRegex(SystemExit, r'candidate\.html'):
                assemble_cli([
                    'missing-blocks.json',
                    'missing-fragments',
                    'missing-views.json',
                    str(final),
                ])

            self.assertEqual(final.read_text(encoding='utf-8'), 'known good reader')

    def test_build_failure_never_exposes_candidate_as_final_reader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            final = root / 'reader.html'
            final.write_text('known good reader', encoding='utf-8')

            def fake_assembler(_blocks, _fragments, _views, candidate):
                Path(candidate).write_text('unchecked reader', encoding='utf-8')

            def reject(_candidate):
                raise RuntimeError('desktop browser gate failed')

            with self.assertRaisesRegex(RuntimeError, 'desktop browser gate failed'):
                build_reader(
                    root / 'blocks.json',
                    root / 'fragments',
                    root / 'views.json',
                    final,
                    root / 'shots',
                    assembler=fake_assembler,
                    validator=reject,
                )

            self.assertEqual(final.read_text(encoding='utf-8'), 'known good reader')
            self.assertFalse(list(root.glob('.*.candidate.html')))

    def test_successful_browser_validation_atomically_replaces_reader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate = root / '.reader.candidate.html'
            final = root / 'reader.html'
            candidate.write_text('new reader', encoding='utf-8')
            final.write_text('old reader', encoding='utf-8')

            promote_candidate(candidate, final, lambda _candidate: None)

            self.assertEqual(final.read_text(encoding='utf-8'), 'new reader')
            self.assertFalse(candidate.exists())

    def test_failed_browser_validation_keeps_previous_reader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidate = root / '.reader.candidate.html'
            final = root / 'reader.html'
            candidate.write_text('bad candidate', encoding='utf-8')
            final.write_text('known good reader', encoding='utf-8')

            def reject(_candidate):
                raise RuntimeError('browser gate failed')

            with self.assertRaisesRegex(RuntimeError, 'browser gate failed'):
                promote_candidate(candidate, final, reject)

            self.assertEqual(final.read_text(encoding='utf-8'), 'known good reader')
            self.assertEqual(candidate.read_text(encoding='utf-8'), 'bad candidate')

    def test_visual_verdict_gate_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            final = root / 'reader.html'
            final.write_text('known good reader', encoding='utf-8')
            verdict = root / 'visual-verdict.json'
            verdict.write_text(
                '{"schemaVersion":1,"candidate":"reader.candidate.html","reviewer":{"mode":"human","independentFromProducer":true},"views":[{"viewId":"v1","blindReadback":{"centralClaimParaphrase":"这是分层架构","dominantRelation":"containment","firstFocalLabels":["执行内核"],"factAttachments":[],"lowerMisreadAlternative":"none"},"comparison":{"claimMatches":true,"primaryRelationMatches":[],"focalMatches":true,"factScopeMatches":[]},"verdict":"REJECT"}],"verdict":"PASS"}',
                encoding='utf-8',
            )

            def fake_assembler(_blocks, _fragments, _views, candidate):
                Path(candidate).write_text('unchecked reader', encoding='utf-8')

            original_gate = build_reader_module.run_browser_gate
            build_reader_module.run_browser_gate = lambda candidate, shots: None
            try:
                with self.assertRaisesRegex(ValueError, 'visual-verdict 合同失败'):
                    build_reader(
                        root / 'blocks.json',
                        root / 'fragments',
                        root / 'views.json',
                        final,
                        root / 'shots',
                        assembler=fake_assembler,
                        visual_verdict_path=verdict,
                    )
            finally:
                build_reader_module.run_browser_gate = original_gate

            self.assertEqual(final.read_text(encoding='utf-8'), 'known good reader')

    def test_v3_build_requires_visual_verdict_even_when_browser_gate_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            final = root / 'reader.html'
            final.write_text('known good reader', encoding='utf-8')

            def fake_assembler(_blocks, _spec, candidate):
                Path(candidate).write_text('unchecked v3 reader', encoding='utf-8')

            with self.assertRaisesRegex(ValueError, 'v3 晋升必须提供 visual-verdict'):
                build_reader_v3(
                    root / 'blocks.json',
                    root / 'view-spec.json',
                    final,
                    root / 'shots',
                    assembler=fake_assembler,
                    browser_validator=lambda _candidate: None,
                )

            self.assertEqual(final.read_text(encoding='utf-8'), 'known good reader')
            self.assertFalse(list(root.glob('.*.candidate.html')))

    def test_v3_build_requires_recorded_producer_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            verdict = root / 'visual-verdict.json'
            verdict.write_text('{}', encoding='utf-8')

            with self.assertRaisesRegex(ValueError, 'producer_id'):
                build_reader_v3(
                    root / 'blocks.json',
                    root / 'view-spec.json',
                    root / 'reader.html',
                    root / 'shots',
                    visual_verdict_path=verdict,
                )

    def test_v3_build_promotes_only_digest_bound_independent_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            final = root / 'reader.html'
            final.write_text('old reader', encoding='utf-8')
            candidate_body = 'checked v3 reader'
            spec = {'schemaVersion': 3, 'views': [{'id': 'v1'}]}
            spec_path = root / 'view-spec.json'
            spec_path.write_text(json.dumps(spec), encoding='utf-8')
            verdict = {
                'schemaVersion': 1,
                'candidate': 'reader.candidate.html',
                'candidateSha256': hashlib.sha256(candidate_body.encode()).hexdigest(),
                'reviewer': {
                    'id': 'reviewer-b',
                    'mode': 'vision-agent',
                    'independentFromProducer': True,
                },
                'views': [{
                    'viewId': 'v1',
                    'blindReadback': {
                        'centralClaimParaphrase': '这是分层架构',
                        'dominantRelation': 'containment',
                        'firstFocalLabels': ['执行内核'],
                        'factAttachments': [],
                        'lowerMisreadAlternative': 'none',
                    },
                    'comparison': {
                        'claimMatches': True,
                        'primaryRelationMatches': [],
                        'focalMatches': True,
                        'factScopeMatches': [],
                    },
                    'verdict': 'PASS',
                }],
                'verdict': 'PASS',
            }
            verdict_path = root / 'visual-verdict.json'
            verdict_path.write_text(json.dumps(verdict, ensure_ascii=False), encoding='utf-8')

            def fake_assembler(_blocks, _spec, candidate):
                Path(candidate).write_text(candidate_body, encoding='utf-8')

            build_reader_v3(
                root / 'blocks.json',
                spec_path,
                final,
                root / 'shots',
                visual_verdict_path=verdict_path,
                producer_id='producer-a',
                assembler=fake_assembler,
                browser_validator=lambda _candidate: None,
            )

            self.assertEqual(final.read_text(encoding='utf-8'), candidate_body)

    def test_v3_cli_routes_to_v3_pipeline_without_fragments_argument(self):
        captured = {}

        def fake_build(blocks, spec, output, shots, **kwargs):
            captured.update({
                'blocks': blocks,
                'spec': spec,
                'output': output,
                'shots': shots,
                **kwargs,
            })

        original = build_reader_module.build_reader_v3
        build_reader_module.build_reader_v3 = fake_build
        try:
            build_reader_module.main([
                'v3',
                'blocks.json',
                'view-spec.json',
                'reader.html',
                '--visual-verdict',
                'visual-verdict.json',
                '--producer-id',
                'model-a',
            ])
        finally:
            build_reader_module.build_reader_v3 = original

        self.assertEqual(captured['blocks'], 'blocks.json')
        self.assertEqual(captured['spec'], 'view-spec.json')
        self.assertEqual(captured['output'], Path('reader.html'))
        self.assertEqual(captured['visual_verdict_path'], 'visual-verdict.json')
        self.assertEqual(captured['producer_id'], 'model-a')


if __name__ == '__main__':
    unittest.main()
