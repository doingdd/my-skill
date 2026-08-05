#!/usr/bin/env python3
import os
import tempfile
import unittest

import coverage
from assemble_split import validate_fragment


SOURCE_IDS = {'b001', 'b002', 'b003'}


def view_with_fact():
    return {
        'id': 'v-test',
        'facts': [
            {
                'id': 'f1',
                'label': '条件',
                'value': '只有明确需求才进入重组',
                'sourceBlockIds': ['b002'],
            },
        ],
        'elements': [
            {
                'id': 'n1',
                'label': '入口',
                'detail': '先判断触发条件',
                'sourceBlockIds': ['b001'],
            },
            {
                'id': 'n2',
                'label': '输出',
                'detail': '生成右栏视图',
                'sourceBlockIds': ['b003'],
            },
        ],
        'relations': [{'from': 'n1', 'to': 'n2'}],
    }


def valid_fragment():
    return """
    <section data-flow data-layout="timeline">
      <div class="mv-node" data-node-id="n1" data-source-blocks="b001">
        <span class="mv-node-title">入口</span>
      </div>
      <div class="mv-fact" data-fact-id="f1" data-source-blocks="b002">
        <span class="mv-fact-label">条件</span>
        <span class="mv-fact-value">只有明确需求才进入重组</span>
      </div>
      <div class="mv-node" data-node-id="n2" data-source-blocks="b003">
        <span class="mv-node-title">输出</span>
      </div>
      <span class="mv-edge" data-from="n1" data-to="n2" hidden></span>
    </section>
    """


class FragmentContractFactTests(unittest.TestCase):
    def test_accepts_fragment_when_all_declared_facts_are_present(self):
        validate_fragment(valid_fragment(), view_with_fact(), SOURCE_IDS)

    def test_rejects_fragment_when_declared_fact_is_missing(self):
        fragment = valid_fragment().replace(
            '<div class="mv-fact" data-fact-id="f1" data-source-blocks="b002">',
            '<div class="mv-fact-missing" data-fact-id="f1" data-source-blocks="b002">',
        )

        with self.assertRaisesRegex(ValueError, '缺少 views\\.json facts: f1'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_fact_without_id(self):
        fragment = valid_fragment().replace(' data-fact-id="f1"', '')

        with self.assertRaisesRegex(ValueError, 'mv-fact 缺少 data-fact-id'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_fact_without_source_mapping(self):
        fragment = valid_fragment().replace(' data-source-blocks="b002"', '', 1)

        with self.assertRaisesRegex(ValueError, 'f1 缺少 data-source-blocks'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_fact_with_unknown_source_mapping(self):
        fragment = valid_fragment().replace('data-source-blocks="b002"', 'data-source-blocks="b999"')

        with self.assertRaisesRegex(ValueError, 'data-source-blocks 引用了不存在的源块: b999'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_node_source_mapping_that_differs_from_model(self):
        fragment = valid_fragment().replace('data-source-blocks="b001"', 'data-source-blocks="b002"')

        with self.assertRaisesRegex(ValueError, 'n1 的 data-source-blocks 与 views\.json 不一致'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_fact_source_mapping_that_differs_from_model(self):
        fragment = valid_fragment().replace('data-source-blocks="b002"', 'data-source-blocks="b003"')

        with self.assertRaisesRegex(ValueError, 'f1 的 data-source-blocks 与 views\.json 不一致'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_element_scoped_fact(self):
        view = view_with_fact()
        view['facts'] = []
        view['elements'][0]['facts'] = [{
            'id': 'f1',
            'label': '条件',
            'value': '只有明确需求才进入重组',
            'sourceBlockIds': ['b002'],
        }]

        with self.assertRaisesRegex(ValueError, 'element\.facts；请移到 view\.facts'):
            validate_fragment(valid_fragment(), view, SOURCE_IDS)

    def test_rejects_fact_outside_flow(self):
        fragment = """
        <div class="mv-fact" data-fact-id="f1" data-source-blocks="b002">
          <span class="mv-fact-label">条件</span>
        </div>
        """

        with self.assertRaisesRegex(ValueError, 'mv-fact 必须位于 data-flow 内'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_fragment_without_semantic_flow_scope(self):
        fragment = '<section class="view"><p>只有视觉文本，没有语义作用域</p></section>'

        with self.assertRaisesRegex(ValueError, 'fragment v2 缺少 data-flow 语义作用域'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_node_dom_order_that_differs_from_model(self):
        fragment = valid_fragment().replace(
            '<div class="mv-node" data-node-id="n1" data-source-blocks="b001">\n'
            '        <span class="mv-node-title">入口</span>\n'
            '      </div>',
            '',
        ).replace(
            '<div class="mv-node" data-node-id="n2" data-source-blocks="b003">',
            '<div class="mv-node" data-node-id="n2" data-source-blocks="b003">',
        ).replace(
            '      <span class="mv-edge" data-from="n1" data-to="n2" hidden></span>',
            '      <div class="mv-node" data-node-id="n1" data-source-blocks="b001">\n'
            '        <span class="mv-node-title">入口</span>\n'
            '      </div>\n'
            '      <span class="mv-edge" data-from="n1" data-to="n2" hidden></span>',
        )

        with self.assertRaisesRegex(ValueError, '节点 DOM 阅读顺序与 views\.json 不一致'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_fact_dom_order_that_differs_from_model(self):
        view = view_with_fact()
        view['facts'].append({
            'id': 'f2',
            'label': '边界',
            'value': '输出必须可追溯',
            'sourceBlockIds': ['b003'],
        })
        fragment = valid_fragment().replace(
            '<div class="mv-fact" data-fact-id="f1" data-source-blocks="b002">',
            '<div class="mv-fact" data-fact-id="f2" data-source-blocks="b003">\n'
            '        <span class="mv-fact-label">边界</span>\n'
            '        <span class="mv-fact-value">输出必须可追溯</span>\n'
            '      </div>\n'
            '      <div class="mv-fact" data-fact-id="f1" data-source-blocks="b002">',
        )

        with self.assertRaisesRegex(ValueError, 'facts DOM 阅读顺序与 views\.json 不一致'):
            validate_fragment(fragment, view, SOURCE_IDS)


class SourceMapCoverageTests(unittest.TestCase):
    def test_source_map_coverage_uses_right_pane_mappings_not_left_pane_text(self):
        blocks = [
            {'id': 'h001', 'type': 'heading', 'raw': '# 标题'},
            {'id': 'b001', 'type': 'paragraph', 'raw': 'Alpha source text is fully present.'},
            {'id': 'b002', 'type': 'paragraph', 'raw': 'Beta source text is also fully present.'},
        ]
        html = """
        <main>
          <article class="source">
            <div class="src-block" data-block-id="b001">Alpha source text is fully present.</div>
            <div class="src-block" data-block-id="b002">Beta source text is also fully present.</div>
          </article>
          <article class="projection">
            <section data-flow data-layout="timeline">
              <div class="mv-node" data-node-id="n1" data-source-blocks="b001">Alpha</div>
              <div class="mv-fact" data-fact-id="f1" data-source-blocks="b001">Only alpha</div>
            </section>
          </article>
        </main>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'reader.html')
            with open(html_path, 'w') as f:
                f.write(html)

            result = coverage.measure(blocks, html_path)

        self.assertEqual(result['block_coverage'], 100.0)
        self.assertEqual(result['source_map_measured'], 2)
        self.assertEqual(result['source_map_mapped'], 1)
        self.assertEqual(result['source_map_coverage'], 50.0)
        self.assertEqual(result['nodes'], 1)
        self.assertEqual(result['facts'], 1)
        self.assertEqual(result['unmapped_ids'], ['b002'])


if __name__ == '__main__':
    unittest.main()
