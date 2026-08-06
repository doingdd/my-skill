#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from assemble_v3 import main as assemble_v3
from coverage import measure
from v3_contract import validate_v3_spec


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'fixtures' / 'v3' / 'family-smoke'


class FamilySmokeFixtureTests(unittest.TestCase):
    def load_fixture(self):
        blocks = json.loads((FIXTURE_ROOT / 'blocks.json').read_text(encoding='utf-8'))
        spec = json.loads((FIXTURE_ROOT / 'view-spec.json').read_text(encoding='utf-8'))
        return blocks, spec

    def test_family_smoke_fixture_satisfies_v3_contract(self):
        blocks, spec = self.load_fixture()

        validate_v3_spec(blocks, spec)

        self.assertEqual(
            ['flow', 'matrix', 'argument'],
            [view['diagramKind'] for view in spec['views']],
        )

    def test_family_smoke_candidate_contains_family_specific_dom(self):
        blocks, spec = self.load_fixture()
        validate_v3_spec(blocks, spec)

        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / 'family-smoke.candidate.html'
            assemble_v3(
                FIXTURE_ROOT / 'blocks.json',
                FIXTURE_ROOT / 'view-spec.json',
                candidate,
            )
            html = candidate.read_text(encoding='utf-8')

        self.assertIn('data-diagram-kind="flow"', html)
        self.assertIn('class="mv-flow-sequence"', html)
        self.assertIn('data-relation-id="submit-to-review"', html)
        self.assertIn('data-directed="true"', html)
        self.assertIn('data-diagram-kind="matrix"', html)
        self.assertIn('<table class="mv-matrix">', html)
        self.assertIn('data-fact-id="route-dependency"', html)
        self.assertIn('data-source-unit="b003:r001"', html)
        self.assertIn('data-diagram-kind="argument"', html)
        self.assertIn('class="mv-argument-evidence-main"', html)
        self.assertIn('class="mv-argument-link"', html)
        self.assertIn('data-relation-id="supports-direct"', html)
        self.assertNotIn('unsupported_diagram_kind', html)

    def test_family_smoke_candidate_preserves_all_source_mappings(self):
        blocks, spec = self.load_fixture()
        validate_v3_spec(blocks, spec)

        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / 'family-smoke.candidate.html'
            assemble_v3(
                FIXTURE_ROOT / 'blocks.json',
                FIXTURE_ROOT / 'view-spec.json',
                candidate,
            )
            html = candidate.read_text(encoding='utf-8')
            coverage = measure(blocks, candidate)

        for view in spec['views']:
            for entity in view['entities']:
                self.assertIn(f'data-entity-id="{entity["id"]}"', html)
                self.assertIn(f'data-source-blocks="{" ".join(entity["sourceBlockIds"])}"', html)
            for relation in view['relations']:
                self.assertIn(f'data-relation-id="{relation["id"]}"', html)
                self.assertIn(f'data-source-blocks="{" ".join(relation["sourceBlockIds"])}"', html)
            for fact in view['facts']:
                self.assertIn(f'data-fact-id="{fact["id"]}"', html)
                self.assertIn(f'data-source-blocks="{" ".join(fact["sourceBlockIds"])}"', html)

        self.assertEqual(100.0, coverage['source_map_coverage'])
        self.assertEqual(100.0, coverage['source_unit_coverage'])


if __name__ == '__main__':
    unittest.main()
