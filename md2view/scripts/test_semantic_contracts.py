#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from assemble_split import main as assemble_reader
from semantic_contract import validate_semantic_model
from parse_blocks import parse_blocks


class StructuredSemanticContractTests(unittest.TestCase):
    def test_assembler_runs_semantic_contract_before_writing_reader(self):
        blocks = self.matrix_blocks()
        plan = {'views': [{
            'id': 'v1',
            'concept': 'matrix',
            'elements': [],
            'facts': [{
                'id': 'f-summary',
                'label': '结论',
                'value': 'B 更稳',
                'sourceBlockIds': ['b001'],
            }],
            'relations': [],
        }]}
        fragment = (
            '<section class="view" id="v1">'
            '<div data-flow data-layout="matrix">'
            '<article class="mv-fact" data-fact-id="f-summary" '
            'data-source-blocks="b001">B 更稳</article>'
            '</div></section>'
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'fragments').mkdir()
            (root / 'blocks.json').write_text(json.dumps(blocks), encoding='utf-8')
            (root / 'views.json').write_text(json.dumps(plan), encoding='utf-8')
            (root / 'fragments' / 'v1.html').write_text(fragment, encoding='utf-8')
            output = root / 'reader.candidate.html'

            with self.assertRaisesRegex(ValueError, '缺少 3 个原子语义单元'):
                assemble_reader(
                    str(root / 'blocks.json'),
                    str(root / 'fragments'),
                    str(root / 'views.json'),
                    str(output),
                )
            self.assertFalse(output.exists())

    def test_parser_emits_stable_source_units_for_rows_and_check_items(self):
        blocks = parse_blocks(
            '| 维度 | A | B |\n'
            '| --- | --- | --- |\n'
            '| 依赖 | 主页 | 登录页 |\n\n'
            '- [ ] 登录成功检查保持不变。\n'
            '- [x] 相关导航单测通过。'
        )

        self.assertEqual(
            [unit['id'] for unit in blocks[0]['sourceUnits']],
            ['b000:r001'],
        )
        self.assertEqual(
            [unit['id'] for unit in blocks[1]['sourceUnits']],
            ['b001:i001', 'b001:i002'],
        )

    def test_parser_emits_source_units_for_ordered_check_items(self):
        blocks = parse_blocks(
            '1. [ ] 首项验收保持可见。\n'
            '2) [x] 次项验收保持可见。'
        )

        self.assertEqual(
            [unit['id'] for unit in blocks[0]['sourceUnits']],
            ['b000:i001', 'b000:i002'],
        )

    def matrix_blocks(self):
        return [{
            'id': 'b001',
            'type': 'table',
            'raw': (
                '| 维度 | 方案 A | 方案 B |\n'
                '| --- | --- | --- |\n'
                '| 单次导航步骤 | 主页、等待、点击 | 一次直达 |\n'
                '| 页面依赖 | 官网主页、页头选择器 | 登录入口 |\n'
                '| 失败定位 | 混合定位 | 聚焦登录页 |'
            ),
        }]

    def test_rejects_matrix_when_one_fact_collapses_all_table_rows(self):
        blocks = self.matrix_blocks()
        plan = {'views': [{
            'id': 'v1',
            'concept': 'matrix',
            'elements': [],
            'facts': [{
                'id': 'f-summary',
                'label': '比较结论',
                'value': 'B 更短、更稳、更清晰',
                'sourceBlockIds': ['b001'],
            }],
            'relations': [],
        }]}

        with self.assertRaisesRegex(
            ValueError,
            '缺少 3 个原子语义单元.*单次导航步骤.*页面依赖.*失败定位',
        ):
            validate_semantic_model(blocks, plan)

    def test_decision_table_header_still_requires_rows_when_concept_is_mislabeled(self):
        plan = {'views': [{
            'id': 'v1',
            'concept': 'flow',
            'elements': [],
            'facts': [{
                'id': 'f-summary',
                'label': '比较结论',
                'value': 'B 更稳定',
                'sourceBlockIds': ['b001'],
            }],
            'relations': [],
        }]}

        with self.assertRaisesRegex(ValueError, '缺少 3 个原子语义单元'):
            validate_semantic_model(self.matrix_blocks(), plan)

    def test_accepts_matrix_when_each_decision_row_has_its_own_source_unit(self):
        plan = {'views': [{
            'id': 'v1',
            'concept': 'matrix',
            'elements': [],
            'facts': [
                {
                    'id': 'f-nav',
                    'label': '单次导航步骤',
                    'value': 'A 主页、等待、点击；B 一次直达',
                    'sourceBlockIds': ['b001'],
                    'sourceUnitId': 'b001:r001',
                },
                {
                    'id': 'f-dependency',
                    'label': '页面依赖',
                    'value': 'A 官网主页、页头选择器；B 登录入口',
                    'sourceBlockIds': ['b001'],
                    'sourceUnitId': 'b001:r002',
                },
                {
                    'id': 'f-debug',
                    'label': '失败定位',
                    'value': 'A 混合定位；B 聚焦登录页',
                    'sourceBlockIds': ['b001'],
                    'sourceUnitId': 'b001:r003',
                },
            ],
            'relations': [],
        }]}

        validate_semantic_model(self.matrix_blocks(), plan)

    def test_rejects_matrix_row_that_names_dimension_but_drops_a_cell(self):
        plan = {'views': [{
            'id': 'v1',
            'concept': 'matrix',
            'elements': [],
            'facts': [
                {
                    'id': 'f-nav',
                    'label': '单次导航步骤',
                    'value': 'B 一次直达',
                    'sourceBlockIds': ['b001'],
                    'sourceUnitId': 'b001:r001',
                },
                {
                    'id': 'f-dependency',
                    'label': '页面依赖',
                    'value': 'A 官网主页、页头选择器；B 登录入口',
                    'sourceBlockIds': ['b001'],
                    'sourceUnitId': 'b001:r002',
                },
                {
                    'id': 'f-debug',
                    'label': '失败定位',
                    'value': 'A 混合定位；B 聚焦登录页',
                    'sourceBlockIds': ['b001'],
                    'sourceUnitId': 'b001:r003',
                },
            ],
            'relations': [],
        }]}

        with self.assertRaisesRegex(
            ValueError,
            'b001:r001 未在 f-nav 中呈现表格单元格: 主页、等待、点击',
        ):
            validate_semantic_model(self.matrix_blocks(), plan)

    def test_rejects_source_unit_id_used_as_a_token_without_showing_its_key(self):
        facts = []
        for index, unit_id in enumerate(('b001:r001', 'b001:r002', 'b001:r003'), 1):
            facts.append({
                'id': f'f{index}',
                'label': f'结论 {index}',
                'value': 'B 更好',
                'sourceBlockIds': ['b001'],
                'sourceUnitId': unit_id,
            })
        plan = {'views': [{
            'id': 'v1',
            'concept': 'matrix',
            'elements': [],
            'facts': facts,
            'relations': [],
        }]}

        with self.assertRaisesRegex(
            ValueError,
            'b001:r001 未在 f1 中呈现源单位 key: 单次导航步骤',
        ):
            validate_semantic_model(self.matrix_blocks(), plan)

    def test_rejects_checklist_when_acceptance_items_are_merged(self):
        blocks = [{
            'id': 'b002',
            'type': 'list',
            'raw': (
                '- [ ] ontest 首次进入和失败重试都访问 /login.html。\n'
                '- [ ] prod 首次进入和失败重试都访问 /login.html。\n'
                '- [ ] 二维码、短信、密码登录的重试路径一致。\n'
                '- [ ] 重试过程不再访问官网主页。\n'
                '- [ ] 登录成功检查保持不变。\n'
                '- [ ] 登出行为保持不变。\n'
                '- [ ] 相关导航单测通过。'
            ),
        }]
        plan = {'views': [{
            'id': 'v1',
            'concept': 'flow',
            'elements': [],
            'facts': [
                {
                    'id': 'f-env',
                    'label': '环境验收',
                    'value': 'ontest 与 prod 都直达登录页',
                    'sourceBlockIds': ['b002'],
                },
                {
                    'id': 'f-retry',
                    'label': '重试验收',
                    'value': '三种登录方式路径一致',
                    'sourceBlockIds': ['b002'],
                },
            ],
            'relations': [],
        }]}

        with self.assertRaisesRegex(
            ValueError,
            '缺少 7 个原子语义单元.*登录成功检查保持不变.*登出行为保持不变.*相关导航单测通过',
        ):
            validate_semantic_model(blocks, plan)

    def test_accepts_check_item_split_across_fact_label_and_value(self):
        blocks = [{
            'id': 'b002',
            'type': 'list',
            'raw': '- [ ] 登录成功检查保持不变。',
        }]
        plan = {'views': [{
            'id': 'v1',
            'concept': 'pipeline',
            'elements': [],
            'facts': [{
                'id': 'f-check',
                'label': '登录成功检查',
                'value': '保持不变。',
                'sourceBlockIds': ['b002'],
                'sourceUnitId': 'b002:i001',
            }],
            'relations': [],
        }]}

        validate_semantic_model(blocks, plan)

    def test_rejects_unknown_source_unit_id(self):
        blocks = [{'id': 'b001', 'type': 'paragraph', 'raw': '普通段落'}]
        plan = {'views': [{
            'id': 'v1',
            'concept': 'flow',
            'elements': [{
                'id': 'e1',
                'label': '伪锚点',
                'detail': '不能自造原子语义 id',
                'sourceBlockIds': ['b001'],
                'sourceUnitId': 'b001:i999',
            }],
            'facts': [],
            'relations': [],
        }]}

        with self.assertRaisesRegex(ValueError, 'sourceUnitId 不存在: b001:i999'):
            validate_semantic_model(blocks, plan)

    def test_rejects_source_unit_without_its_parent_block_mapping(self):
        blocks = [
            {
                'id': 'b001',
                'type': 'list',
                'raw': '- [ ] 登录成功检查保持不变。',
            },
            {'id': 'b002', 'type': 'paragraph', 'raw': '别的来源'},
        ]
        plan = {'views': [{
            'id': 'v1',
            'concept': 'flow',
            'elements': [],
            'facts': [{
                'id': 'f1',
                'label': '登录检查',
                'value': '保持不变',
                'sourceBlockIds': ['b002'],
                'sourceUnitId': 'b001:i001',
            }],
            'relations': [],
        }]}

        with self.assertRaisesRegex(
            ValueError,
            'b001:i001 的父块 b001 未出现在 f1.sourceBlockIds',
        ):
            validate_semantic_model(blocks, plan)


if __name__ == '__main__':
    unittest.main()
