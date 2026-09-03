#!/usr/bin/env python3
"""parse_blocks 回归:块类型、稳定 id、rule 识别、sourceUnit 提取。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parse_blocks import parse_blocks


class TestParseBlocks(unittest.TestCase):
    def test_types_and_ids(self):
        blocks = parse_blocks('# 标题\n\n正文一段。\n\n---\n\n| a | b |\n|---|---|\n| r1 | 42 |\n\n- [x] 已完成项\n- [ ] 未完成项\n')
        types = [b['type'] for b in blocks]
        self.assertEqual(types, ['heading', 'paragraph', 'rule', 'table', 'list'])
        self.assertEqual([b['id'] for b in blocks], ['b000', 'b001', 'b002', 'b003', 'b004'])

    def test_table_units(self):
        blocks = parse_blocks('| h1 | h2 |\n|---|---|\n| a | 1 |\n| b | 2 |\n')
        units = blocks[0]['sourceUnits']
        self.assertEqual([u['id'] for u in units], ['b000:r001', 'b000:r002'])
        self.assertEqual(units[0]['key'], 'a')

    def test_checkitem_units(self):
        blocks = parse_blocks('- [x] 做了\n- [ ] 没做\n')
        units = blocks[0]['sourceUnits']
        self.assertEqual(len(units), 2)
        self.assertTrue(units[0]['checked'])
        self.assertFalse(units[1]['checked'])

    def test_code_fence_not_split(self):
        blocks = parse_blocks('前文。\n\n```python\n# 注释\nprint(1)\n```\n\n后文。\n')
        self.assertEqual([b['type'] for b in blocks], ['paragraph', 'code', 'paragraph'])


if __name__ == '__main__':
    unittest.main()
