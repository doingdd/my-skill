#!/usr/bin/env python3
"""verify_anchors 对抗测试:合法概括必须通过,伪造/换词/吞行必须被拒绝。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_anchors import verify_fragment, has_lexical_anchor


def make_blocks():
    return [
        {'id': 'b000', 'type': 'heading', 'depth': 1, 'raw': '# 执行内核选型'},
        {'id': 'b001', 'type': 'paragraph',
         'raw': '主执行内核选 Pi,固定 0.82.x 版本,35 个质量 skill 零改造可用。'},
        {'id': 'b002', 'type': 'table',
         'raw': '| 决策项 | 结论 |\n|---|---|\n| 主执行内核 | Pi(SDK 进程内嵌入) |\n| 知识检索 | 不引入向量索引,用 agentic 检索 |',
         'sourceUnits': [
             {'id': 'b002:r001', 'kind': 'table-row', 'key': '主执行内核',
              'raw': '| 主执行内核 | Pi(SDK 进程内嵌入) |'},
             {'id': 'b002:r002', 'kind': 'table-row', 'key': '知识检索',
              'raw': '| 知识检索 | 不引入向量索引,用 agentic 检索 |'},
         ]},
        {'id': 'b003', 'type': 'list',
         'raw': '- 确定性管线为骨架,只在关节嵌 agent\n- 工具产数字,agent 做判断'},
    ]


GOOD = '''
<header class="mv-page-head" data-sources="b000 b001">
  <div class="mv-kicker">技术设计</div>
  <h1>执行内核选型</h1>
  <p class="mv-lead">主执行内核选 Pi,固定 0.82.x;35 个质量 skill 零改造可用。</p>
</header>
<section class="mv-view" id="v-decision">
  <header class="mv-view-head"><h2>结论</h2></header>
  <table class="mv-table" data-sources="b002">
    <tr><td class="k">主执行内核</td><td>Pi(SDK 进程内嵌入)</td></tr>
    <tr><td class="k">知识检索</td><td>不引入向量索引,用 agentic 检索</td></tr>
  </table>
  <ul class="mv-list" data-sources="b003">
    <li>确定性管线为骨架,只在关节嵌 agent</li>
    <li>工具产数字,agent 做判断</li>
  </ul>
</section>
'''


class TestLexicalAnchor(unittest.TestCase):
    def test_shared_terms_pass(self):
        self.assertTrue(has_lexical_anchor('主执行内核选 Pi', '内核层为 pi-agent-core,主执行内核固定'))

    def test_latin_token_passes(self):
        self.assertTrue(has_lexical_anchor('选用 Pi 内核', 'the Pi SDK is embedded'))

    def test_complete_reword_fails(self):
        self.assertFalse(has_lexical_anchor('它们都很高兴', '主执行内核固定版本'))


class TestVerifyFragment(unittest.TestCase):
    def check(self, fragment, blocks=None):
        return verify_fragment(blocks or make_blocks(), fragment)

    def test_good_fragment_passes(self):
        errors, warnings, stats = self.check(GOOD)
        self.assertEqual(errors, [])
        self.assertEqual(stats['covered'], 4)  # b000(标题被 page-head 引用)+ b001 b002 b003

    def test_fabricated_number_rejected(self):
        bad = GOOD.replace('35 个质量 skill 零改造可用', '99.9% 的 skill 可用')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('99.9%' in e for e in errors), errors)

    def test_complete_reword_rejected(self):
        # 元素的全部可见正文都被换成与来源无关的话,只剩 id 宣称有来源 → 拒绝
        bad = GOOD.replace(
            '<ul class="mv-list" data-sources="b003">',
            '<div class="mv-callout" data-sources="b001"><span class="mv-co-body">'
            '这些东西都挺好的,没啥问题。</span></div><ul class="mv-list" data-sources="b003">')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('词锚' in e for e in errors), errors)

    def test_uncovered_block_rejected(self):
        bad = GOOD.replace('data-sources="b003"', 'data-sources="b001"')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('b003' in e and '未被' in e for e in errors), errors)

    def test_unknown_block_rejected(self):
        bad = GOOD.replace('data-sources="b003"', 'data-sources="b999"')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('b999' in e for e in errors), errors)

    def test_swallowed_table_row_rejected(self):
        bad = GOOD.replace(
            '<tr><td class="k">知识检索</td><td>不引入向量索引,用 agentic 检索</td></tr>', '')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('b002:r002' in e for e in errors), errors)

    def test_heading_needs_no_coverage(self):
        blocks = make_blocks()
        fragment = GOOD  # b000 标题未被右栏引用也合法(page-head 引了,但去掉也行)
        errors, _, _ = self.check(fragment, blocks)
        self.assertEqual(errors, [])

    def test_script_rejected(self):
        bad = GOOD + '<section class="mv-view"><script>alert(1)</script></section>'
        errors, _, _ = self.check(bad)
        self.assertTrue(any('<script>' in e or 'script' in e for e in errors), errors)

    def test_external_resource_rejected(self):
        bad = GOOD.replace('<table', '<link rel="stylesheet" href="https://evil.example/x.css"><table')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('外部资源' in e for e in errors), errors)

    def test_hidden_text_trick_rejected(self):
        bad = GOOD.replace('<ul class="mv-list"',
                           '<span style="display:none">垫字</span><ul class="mv-list"')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('隐藏' in e for e in errors), errors)

    def test_empty_sourced_element_rejected(self):
        bad = GOOD.replace('<div class="mv-kicker">技术设计</div>',
                           '<div class="mv-kicker">技术设计</div><span data-sources="b001">  </span>')
        errors, _, _ = self.check(bad)
        self.assertTrue(any('空元素' in e for e in errors), errors)

    def test_diagram_dangling_edge_rejected(self):
        fragment = GOOD + '''
        <section class="mv-view"><figure class="mv-diagram" data-diagram>
          <div class="mv-node" data-node="a" data-sources="b001">主执行内核</div>
          <i class="mv-edge" data-from="a" data-to="ghost" data-label="调用"></i>
        </figure></section>'''
        errors, _, _ = self.check(fragment)
        self.assertTrue(any('ghost' in e for e in errors), errors)

    def test_diagram_duplicate_node_rejected(self):
        fragment = GOOD + '''
        <section class="mv-view"><figure class="mv-diagram" data-diagram>
          <div class="mv-node" data-node="a" data-sources="b001">主执行内核</div>
          <div class="mv-node" data-node="a" data-sources="b001">主执行内核副本</div>
        </figure></section>'''
        errors, _, _ = self.check(fragment)
        self.assertTrue(any('重复 data-node' in e for e in errors), errors)

    def test_edge_inside_mv_edge_text_not_visible(self):
        # mv-edge 的 data-label 不计入可见文本,不能用来垫锚点
        fragment = GOOD + '''
        <section class="mv-view"><figure class="mv-diagram" data-diagram>
          <div class="mv-node" data-node="a" data-sources="b001">主执行内核</div>
          <i class="mv-edge" data-from="a" data-to="a" data-label="不存在于来源的词汇甲乙丙"></i>
        </figure></section>'''
        errors, _, _ = self.check(fragment)
        self.assertEqual(errors, [])

    def test_data_unit_precise_claim(self):
        fragment = GOOD.replace(
            '<table class="mv-table" data-sources="b002">',
            '<table class="mv-table" data-sources="b002"><tbody data-unit="b002:r001" data-sources="b002">')
        # data-unit 元素包含该行内容,精确认领合法
        errors, _, _ = self.check(fragment)
        self.assertEqual(errors, [])

    def test_details_drawer_counts_as_covered_but_warns(self):
        # 明细收进 <details> 抽屉是合法投影(可寻址),但只进抽屉要给出提醒
        fragment = GOOD.replace(
            '<ul class="mv-list" data-sources="b003">',
            '<details class="mv-drawer"><summary>设计原则</summary>'
            '<ul class="mv-list" data-sources="b003">')
        fragment = fragment.replace('</ul>\n</section>', '</ul></details>\n</section>')
        errors, warnings, stats = self.check(fragment)
        self.assertEqual(errors, [])
        self.assertEqual(stats['covered'], 4)
        self.assertTrue(any('抽屉' in w and 'b003' in w for w in warnings), warnings)


if __name__ == '__main__':
    unittest.main()
