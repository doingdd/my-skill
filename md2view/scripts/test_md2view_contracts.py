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
    def test_rejects_fragment_css_overriding_shared_visual_classes(self):
        fragment = (
            '<style>.mv-edge-layer{clip-path:inset(100%)}</style>' +
            valid_fragment()
        )

        with self.assertRaisesRegex(ValueError, '不得重定义共享 \.mv- 视觉类'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_inline_style_on_fragment_elements(self):
        fragment = valid_fragment().replace(
            'class="mv-fact"',
            'class="mv-fact" style="opacity:0"',
        )

        with self.assertRaisesRegex(ValueError, '不得使用 inline style'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_allows_safe_view_prefixed_layout_css(self):
        fragment = (
            '<style>.v-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}</style>' +
            valid_fragment().replace(
                'data-flow data-layout="timeline"',
                'class="v-test-grid" data-flow data-layout="timeline"',
            )
        )

        validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_view_css_that_can_hide_or_clip_content(self):
        fragment = '<style>.v-test-grid{clip-path:inset(100%)}</style>' + valid_fragment()

        with self.assertRaisesRegex(ValueError, '不得隐藏、裁剪或覆盖语义内容'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_unscoped_member_in_selector_list(self):
        fragment = '<style>body, .v-test-grid{display:grid}</style>' + valid_fragment()

        with self.assertRaisesRegex(ValueError, 'selector 必须使用'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_non_layout_property_even_when_view_scoped(self):
        fragment = '<style>.v-test-grid{color:transparent}</style>' + valid_fragment()

        with self.assertRaisesRegex(ValueError, '仅允许安全布局属性'):
            validate_fragment(fragment, view_with_fact(), SOURCE_IDS)

    def test_rejects_matrix_concept_rendered_as_lanes(self):
        view = view_with_fact()
        view['concept'] = 'matrix'

        with self.assertRaisesRegex(ValueError, 'concept=matrix 必须使用 data-layout=matrix'):
            validate_fragment(valid_fragment(), view, SOURCE_IDS)

    def test_rejects_visible_flow_relations_in_matrix(self):
        view = view_with_fact()
        view['concept'] = 'matrix'
        fragment = valid_fragment().replace('data-layout="timeline"', 'data-layout="matrix"')

        with self.assertRaisesRegex(ValueError, 'concept=matrix 不得声明流程关系'):
            validate_fragment(fragment, view, SOURCE_IDS)

    def test_rejects_relation_label_that_differs_from_model(self):
        view = view_with_fact()
        view['relations'][0]['label'] = '校验'

        with self.assertRaisesRegex(ValueError, 'n1→n2 的 data-label 与 views\.json 不一致'):
            validate_fragment(valid_fragment(), view, SOURCE_IDS)

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

    def test_rejects_fragment_that_drops_model_source_unit(self):
        view = view_with_fact()
        view['facts'][0]['sourceUnitId'] = 'b002:i001'

        with self.assertRaisesRegex(
            ValueError,
            'f1 的 data-source-unit 与 views\.json 不一致',
        ):
            validate_fragment(valid_fragment(), view, SOURCE_IDS)

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
    def test_distinguishes_optional_table_rows_from_required_atomic_units(self):
        blocks = [{
            'id': 'b001',
            'type': 'table',
            'raw': (
                '| 名称 | 说明 |\n'
                '| --- | --- |\n'
                '| SDK | 普通查阅资料 |'
            ),
        }]
        html = """
        <main>
          <div class="src-block" data-block-id="b001">完整表格原文</div>
          <section data-flow data-layout="vertical">
            <div class="mv-node" data-node-id="n1" data-source-blocks="b001">SDK</div>
          </section>
        </main>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'reader.html')
            with open(html_path, 'w') as f:
                f.write(html)

            result = coverage.measure(blocks, html_path)

        self.assertEqual(result['source_unit_measured'], 1)
        self.assertEqual(result['source_unit_mapped'], 0)
        self.assertEqual(result['required_source_unit_measured'], 0)
        self.assertEqual(result['required_source_unit_mapped'], 0)

    def test_matrix_escalates_referenced_table_rows_to_required_atomic_units(self):
        blocks = [{
            'id': 'b001',
            'type': 'table',
            'raw': (
                '| 名称 | 说明 |\n'
                '| --- | --- |\n'
                '| SDK | 普通查阅资料 |'
            ),
        }]
        html = """
        <main>
          <div class="src-block" data-block-id="b001">完整表格原文</div>
          <section data-flow data-layout="matrix">
            <div class="mv-fact" data-fact-id="f1" data-source-blocks="b001">SDK</div>
          </section>
        </main>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'reader.html')
            with open(html_path, 'w') as f:
                f.write(html)

            result = coverage.measure(blocks, html_path)

        self.assertEqual(result['required_source_unit_measured'], 1)
        self.assertEqual(result['required_source_unit_mapped'], 0)
        self.assertEqual(result['required_source_unit_coverage'], 0.0)
        self.assertEqual(result['unmapped_required_source_unit_ids'], ['b001:r001'])

    def test_reports_atomic_table_row_coverage(self):
        blocks = [{
            'id': 'b001',
            'type': 'table',
            'raw': (
                '| 维度 | A | B |\n'
                '| --- | --- | --- |\n'
                '| 页面依赖 | 官网主页 | 登录入口 |\n'
                '| 失败定位 | 混合定位 | 聚焦登录页 |\n'
                '| 单测范围 | 全站导航 | 登录导航 |'
            ),
        }]
        html = """
        <main>
          <div class="src-block" data-block-id="b001">完整表格原文</div>
          <section data-flow data-layout="matrix">
            <div class="mv-fact" data-fact-id="f1" data-source-blocks="b001"
                 data-source-unit="b001:r001">页面依赖</div>
          </section>
        </main>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'reader.html')
            with open(html_path, 'w') as f:
                f.write(html)

            result = coverage.measure(blocks, html_path)

        self.assertEqual(result['source_unit_measured'], 3)
        self.assertEqual(result['source_unit_mapped'], 1)
        self.assertEqual(result['source_unit_coverage'], 33.3)
        self.assertEqual(result['unmapped_unit_ids'], ['b001:r002', 'b001:r003'])
        self.assertEqual(result['required_source_unit_measured'], 3)
        self.assertEqual(result['required_source_unit_mapped'], 1)

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
