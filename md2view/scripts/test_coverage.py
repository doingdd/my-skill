#!/usr/bin/env python3
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import coverage


class SourceMapParserV3Tests(unittest.TestCase):
    def test_v3_entities_and_facts_count_as_semantic_elements(self):
        html = """
        <main>
          <section data-v3-view="v1" data-diagram-kind="architecture">
            <div class="mv-node mv-entity" data-entity-id="system"
                 data-source-blocks="b001">系统</div>
            <div class="mv-fact mv-fact-chip" data-fact-id="f1"
                 data-source-blocks="b002">约束</div>
          </section>
        </main>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "reader.html")
            with open(html_path, "w") as f:
                f.write(html)

            source_map = coverage.html_source_map(html_path)

        self.assertEqual(source_map.nodes, 1)
        self.assertEqual(source_map.facts, 1)
        self.assertEqual(source_map.source_ids, {"b001", "b002"})

    def test_v3_matrix_marks_table_rows_as_required_units_without_double_counting(self):
        blocks = [{
            "id": "b001",
            "type": "table",
            "raw": (
                "| 名称 | 说明 |\n"
                "| --- | --- |\n"
                "| 页面依赖 | 官网主页 |\n"
                "| 失败定位 | 混合定位 |"
            ),
        }]
        html = """
        <main>
          <section data-v3-view="v1" data-diagram-kind="matrix">
            <table>
              <tbody>
                <tr data-source-blocks="b001" data-source-unit="b001:r001">
                  <th>页面依赖</th><td>官网主页</td>
                </tr>
                <tr data-source-blocks="b001">
                  <th>失败定位</th><td>混合定位</td>
                </tr>
              </tbody>
            </table>
          </section>
        </main>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "reader.html")
            with open(html_path, "w") as f:
                f.write(html)

            result = coverage.measure(blocks, html_path)

        self.assertEqual(result["source_map_mapped"], 1)
        self.assertEqual(result["source_unit_mapped"], 1)
        self.assertEqual(result["required_source_unit_measured"], 2)
        self.assertEqual(result["required_source_unit_mapped"], 1)
        self.assertEqual(result["unmapped_required_source_unit_ids"], ["b001:r002"])


if __name__ == "__main__":
    unittest.main()
