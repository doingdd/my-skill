#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from assemble_v3 import V3_JS, main as assemble_v3
from test_v3_contract import architecture_spec


class AssembleV3Tests(unittest.TestCase):
    def test_tablet_dual_pane_uses_the_same_minimum_widths_as_css(self):
        self.assertIn('(max-width:767px)', V3_JS)
        self.assertIn('300/width*100', V3_JS)
        self.assertIn('(width-390)/width*100', V3_JS)

    def test_compiles_view_spec_directly_into_dual_pane_candidate(self):
        blocks = [{
            'id': 'b001',
            'type': 'paragraph',
            'raw': '执行内核分层承载职责。',
        }]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            blocks_path = root / 'blocks.json'
            spec_path = root / 'view-spec.json'
            candidate = root / 'reader.candidate.html'
            blocks_path.write_text(json.dumps(blocks, ensure_ascii=False), encoding='utf-8')
            spec_path.write_text(
                json.dumps(architecture_spec(), ensure_ascii=False),
                encoding='utf-8',
            )

            assemble_v3(blocks_path, spec_path, candidate)

            html = candidate.read_text(encoding='utf-8')
            self.assertIn('data-block-id="b001"', html)
            self.assertIn('data-v3-view', html)
            self.assertIn('data-diagram-kind="architecture"', html)
            self.assertIn('data-md2view-separator', html)
            self.assertNotIn('fragments/', html)


if __name__ == '__main__':
    unittest.main()
