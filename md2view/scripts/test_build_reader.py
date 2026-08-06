#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from assemble_split import cli as assemble_cli, main as assemble_candidate
from build_reader import build_reader, promote_candidate


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


if __name__ == '__main__':
    unittest.main()
