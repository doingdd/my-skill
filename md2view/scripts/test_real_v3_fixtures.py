#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from assemble_v3 import main as assemble_v3
from coverage import measure
from v3_contract import STRUCTURAL_RELATIONS, validate_v3_spec


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / 'fixtures' / 'v3'


def load_fixture(name):
    root = FIXTURE_ROOT / name
    return (
        root,
        json.loads((root / 'blocks.json').read_text(encoding='utf-8')),
        json.loads((root / 'view-spec.json').read_text(encoding='utf-8')),
    )


class RealV3FixtureTests(unittest.TestCase):
    def compile_fixture(self, name, output_root):
        root, blocks, spec = load_fixture(name)
        validate_v3_spec(blocks, spec)
        candidate = output_root / f'{name}.candidate.html'
        assemble_v3(root / 'blocks.json', root / 'view-spec.json', candidate)
        return blocks, spec, candidate, candidate.read_text(encoding='utf-8')

    def assert_complete_semantic_dom(self, spec, html):
        for view in spec['views']:
            for entity in view['entities']:
                self.assertIn(f'data-entity-id="{entity["id"]}"', html)
            for relation in view['relations']:
                relation_marker = f'data-relation-id="{relation["id"]}"'
                self.assertIn(relation_marker, html)
                relation_index = html.index(relation_marker)
                tag_start = html.rfind('<', 0, relation_index)
                tag_end = html.find('>', relation_index)
                relation_tag = html[tag_start:tag_end]
                self.assertIn('data-source-blocks=', relation_tag)
                if relation['kind'] in STRUCTURAL_RELATIONS:
                    self.assertNotIn(
                        f'class="mv-connector" {relation_marker}',
                        html,
                    )
            for fact in view['facts']:
                self.assertIn(f'data-fact-id="{fact["id"]}"', html)

    def test_two_real_architectures_compile_to_distinct_spatial_grammars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            eight_blocks, eight_spec, eight_candidate, eight_html = self.compile_fixture(
                'eight-layer-stack', output_root,
            )
            deployment_blocks, deployment_spec, deployment_candidate, deployment_html = self.compile_fixture(
                'deployment-containers', output_root,
            )

            self.assert_complete_semantic_dom(eight_spec, eight_html)
            self.assert_complete_semantic_dom(deployment_spec, deployment_html)

            self.assertIn('data-region-id="observability-crosscut"', eight_html)
            self.assertIn('data-primitive="crosscut"', eight_html)
            self.assertIn('data-reading-kind="top-down"', eight_html)
            self.assertNotIn('class="mv-flow-sequence"', eight_html)

            self.assertIn('data-region-id="deployment-landscape"', deployment_html)
            self.assertIn('data-axis="horizontal"', deployment_html)
            self.assertIn('data-region-columns="3"', deployment_html)
            self.assertIn('data-region-id="cluster-boundary"', deployment_html)
            self.assertIn('data-region-id="sandbox-boundary"', deployment_html)
            cluster_start = deployment_html.index('data-region-id="cluster-boundary"')
            sandbox_start = deployment_html.index('data-region-id="sandbox-boundary"')
            external_start = deployment_html.index('data-region-id="external-boundary"')
            self.assertLess(cluster_start, sandbox_start)
            self.assertLess(sandbox_start, external_start)
            self.assertNotIn('data-primitive="crosscut"', deployment_html)

            eight_coverage = measure(eight_blocks, eight_candidate)
            deployment_coverage = measure(deployment_blocks, deployment_candidate)
            self.assertEqual(eight_coverage['source_map_coverage'], 100.0)
            self.assertEqual(deployment_coverage['source_map_coverage'], 100.0)
            self.assertEqual(
                deployment_coverage['source_unit_coverage'],
                100.0,
            )


if __name__ == '__main__':
    unittest.main()
