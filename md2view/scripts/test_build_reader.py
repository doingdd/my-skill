#!/usr/bin/env python3
"""build_reader v4 对抗测试:验证不过不产出;产出必须自包含、双栏锚点齐备。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_reader
from test_verify_anchors import GOOD, make_blocks


class TestBuildReader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.blocks_path = os.path.join(self.tmp, 'blocks.json')
        with open(self.blocks_path, 'w', encoding='utf-8') as f:
            json.dump(make_blocks(), f, ensure_ascii=False)
        self.fragment_path = os.path.join(self.tmp, 'right-pane.html')
        self.out_path = os.path.join(self.tmp, 'reader.html')

    def write_fragment(self, text):
        with open(self.fragment_path, 'w', encoding='utf-8') as f:
            f.write(text)

    def test_good_fragment_builds(self):
        self.write_fragment(GOOD)
        rc = build_reader.main([self.blocks_path, self.fragment_path, self.out_path])
        self.assertEqual(rc, 0)
        with open(self.out_path, encoding='utf-8') as f:
            doc = f.read()
        self.assertIn('data-block="b001"', doc)      # 左栏源块锚点
        self.assertIn('data-sources="b003"', doc)    # 右栏溯源锚点
        self.assertIn('执行内核选型', doc)           # 标题来自首个标题块
        self.assertIn('paneL', doc) and self.assertIn('paneR', doc)
        self.assertNotIn('http://', doc.replace('http://www.w3.org', ''))  # 自包含

    def test_bad_fragment_writes_nothing(self):
        self.write_fragment(GOOD.replace('35 个质量 skill', '999 个质量 skill'))
        rc = build_reader.main([self.blocks_path, self.fragment_path, self.out_path])
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self.out_path))

    def test_atomic_no_tmp_left(self):
        self.write_fragment(GOOD)
        build_reader.main([self.blocks_path, self.fragment_path, self.out_path])
        self.assertFalse(os.path.exists(self.out_path + '.tmp'))

    def test_title_override(self):
        self.write_fragment(GOOD)
        build_reader.main([self.blocks_path, self.fragment_path, self.out_path,
                           '--title', '自定义标题'])
        with open(self.out_path, encoding='utf-8') as f:
            doc = f.read()
        self.assertIn('<title>自定义标题 · 双栏</title>', doc)


if __name__ == '__main__':
    unittest.main()
