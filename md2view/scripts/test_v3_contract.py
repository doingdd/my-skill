#!/usr/bin/env python3
import copy
import unittest
from unittest.mock import patch

from v3_contract import validate_v3_spec
from v3_renderer import render_v3_view


def architecture_spec():
    return {
        'schemaVersion': 3,
        'page': {
            'title': '执行内核',
            'audience': '技术决策者',
            'readerTask': '理解职责边界',
            'centralClaim': {
                'text': '执行内核以分层方式承载职责。',
                'sourceBlockIds': ['b001'],
            },
            'narrative': [{'viewId': 'v1', 'role': 'orientation'}],
        },
        'views': [{
            'id': 'v1',
            'title': '总体架构',
            'question': '系统由哪些职责边界构成？',
            'centralClaim': {
                'text': '编排层在执行内核边界内组织任务。',
                'sourceBlockIds': ['b001'],
            },
            'narrativeRole': 'orientation',
            'diagramKind': 'architecture',
            'diagramRationale': '主问题是包含与职责边界。',
            'entities': [
                {
                    'id': 'kernel',
                    'type': 'system',
                    'emphasis': 'primary',
                    'label': '执行内核',
                    'detail': '承载分层执行职责',
                    'multiplicity': 'one',
                    'sourceBlockIds': ['b001'],
                },
                {
                    'id': 'orchestration',
                    'type': 'layer',
                    'emphasis': 'secondary',
                    'label': '编排层',
                    'detail': '组织任务与状态',
                    'multiplicity': 'one',
                    'sourceBlockIds': ['b001'],
                },
            ],
            'relations': [{
                'id': 'contains-layer',
                'subjectId': 'kernel',
                'objectId': 'orchestration',
                'kind': 'contains',
                'emphasis': 'primary',
                'sourceBlockIds': ['b001'],
            }],
            'facts': [],
            'composition': {
                'rootRegionId': 'main',
                'readingPath': {'kind': 'top-down', 'sequence': ['kernel', 'orchestration']},
                'focalIds': ['kernel'],
                'regions': [
                    {
                        'id': 'main',
                        'primitive': 'container',
                        'role': 'main',
                        'axis': 'vertical',
                        'parentId': None,
                        'ownerEntityId': 'kernel',
                        'entityIds': [],
                        'childRegionIds': ['orchestration-band'],
                        'targetRegionIds': [],
                    },
                    {
                        'id': 'orchestration-band',
                        'primitive': 'band',
                        'role': 'main',
                        'axis': 'horizontal',
                        'parentId': 'main',
                        'ownerEntityId': 'orchestration',
                        'entityIds': [],
                        'childRegionIds': [],
                        'targetRegionIds': [],
                    },
                ],
            },
        }],
    }


def flow_spec():
    spec = architecture_spec()
    view = spec['views'][0]
    view.update({
        'title': '发布流程',
        'question': '发布怎样从请求推进到完成？',
        'centralClaim': {
            'text': '通过审核的请求才会进入已发布状态。',
            'sourceBlockIds': ['b001'],
        },
        'diagramKind': 'flow',
        'diagramRationale': '主问题是状态如何定向推进。',
        'entities': [
            {
                'id': 'requested',
                'type': 'state',
                'stateKind': 'start',
                'emphasis': 'primary',
                'label': '待发布',
                'detail': '请求已建立',
                'multiplicity': 'one',
                'sourceBlockIds': ['b001'],
            },
            {
                'id': 'published',
                'type': 'state',
                'stateKind': 'terminal',
                'emphasis': 'secondary',
                'label': '已发布',
                'detail': '产物可访问',
                'multiplicity': 'one',
                'sourceBlockIds': ['b001'],
            },
        ],
        'relations': [{
            'id': 'publish',
            'subjectId': 'requested',
            'objectId': 'published',
            'kind': 'transitionsTo',
            'emphasis': 'primary',
            'sourceBlockIds': ['b001'],
        }],
        'composition': {
            'rootRegionId': 'main',
            'readingPath': {'kind': 'left-right', 'sequence': ['requested', 'published']},
            'focalIds': ['requested'],
            'regions': [{
                'id': 'main',
                'primitive': 'sequence',
                'role': 'main',
                'axis': 'horizontal',
                'parentId': None,
                'entityIds': ['requested', 'published'],
                'childRegionIds': [],
                'targetRegionIds': [],
            }],
        },
    })
    return spec


def matrix_spec():
    spec = architecture_spec()
    view = spec['views'][0]
    view.update({
        'title': '路由方案对比',
        'question': '哪条登录路由更直接、更稳定？',
        'centralClaim': {
            'text': '直达登录页面的方案依赖更少。',
            'sourceBlockIds': ['b001'],
        },
        'diagramKind': 'matrix',
        'diagramRationale': '主问题是两个方案沿共同维度的比较。',
        'entities': [
            {
                'id': 'route-a',
                'type': 'option',
                'emphasis': 'secondary',
                'label': '主页路由',
                'detail': '先访问主页再进入登录',
                'multiplicity': 'one',
                'sourceBlockIds': ['b001'],
            },
            {
                'id': 'route-b',
                'type': 'option',
                'emphasis': 'primary',
                'label': '直达路由',
                'detail': '直接访问登录入口',
                'multiplicity': 'one',
                'sourceBlockIds': ['b001'],
            },
        ],
        'relations': [],
        'facts': [{
            'id': 'dependency',
            'kind': 'decision',
            'scope': {'kind': 'view', 'targetIds': ['v1']},
            'label': '页面依赖',
            'values': [
                {'targetId': 'route-a', 'value': '主页、页头选择器'},
                {'targetId': 'route-b', 'value': '登录入口'},
            ],
            'sourceBlockIds': ['b001'],
            'sourceUnitId': 'b001:r001',
        }],
        'composition': {
            'rootRegionId': 'comparison',
            'readingPath': {'kind': 'scan', 'sequence': []},
            'focalIds': ['route-b'],
            'regions': [{
                'id': 'comparison',
                'primitive': 'axis',
                'role': 'main',
                'axis': 'horizontal',
                'parentId': None,
                'entityIds': ['route-a', 'route-b'],
                'childRegionIds': [],
                'targetRegionIds': [],
            }],
        },
    })
    return spec


def argument_spec():
    spec = architecture_spec()
    view = spec['views'][0]
    view.update({
        'title': '为什么选择直达路由',
        'question': '哪些证据支持直达路由？',
        'centralClaim': {
            'text': '直达路由的不稳定依赖更少。',
            'sourceBlockIds': ['b001'],
        },
        'diagramKind': 'argument',
        'diagramRationale': '主问题是证据如何支持结论。',
        'entities': [
            {
                'id': 'claim',
                'type': 'claim',
                'emphasis': 'primary',
                'label': '选择直达路由',
                'detail': '将变动范围限定在登录页',
                'multiplicity': 'one',
                'sourceBlockIds': ['b001'],
            },
            {
                'id': 'evidence',
                'type': 'evidence',
                'emphasis': 'secondary',
                'label': '依赖数量',
                'detail': '不再依赖主页和页头选择器',
                'multiplicity': 'one',
                'sourceBlockIds': ['b001'],
            },
        ],
        'relations': [{
            'id': 'supports',
            'subjectId': 'evidence',
            'objectId': 'claim',
            'kind': 'supportsClaim',
            'emphasis': 'primary',
            'sourceBlockIds': ['b001'],
        }],
        'facts': [],
        'composition': {
            'rootRegionId': 'case',
            'readingPath': {'kind': 'center-out', 'sequence': ['claim', 'evidence']},
            'focalIds': ['claim'],
            'regions': [{
                'id': 'case',
                'primitive': 'radial',
                'role': 'main',
                'axis': 'none',
                'parentId': None,
                'entityIds': ['claim', 'evidence'],
                'childRegionIds': [],
                'targetRegionIds': [],
            }],
        },
    })
    return spec


class ViewSpecV3ContractTests(unittest.TestCase):
    def test_rejects_view_without_question_and_central_claim(self):
        blocks = [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}]
        spec = {
            'schemaVersion': 3,
            'page': {
                'title': '执行内核',
                'audience': '技术决策者',
                'readerTask': '理解职责边界',
                'centralClaim': {
                    'text': '执行内核以分层方式承载职责。',
                    'sourceBlockIds': ['b001'],
                },
                'narrative': [{'viewId': 'v1', 'role': 'orientation'}],
            },
            'views': [{
                'id': 'v1',
                'title': '总体架构',
                'diagramKind': 'architecture',
                'entities': [],
                'relations': [],
                'facts': [],
                'composition': {},
            }],
        }

        with self.assertRaisesRegex(
            ValueError,
            r'(?s)v1\.question.*v1\.centralClaim',
        ):
            validate_v3_spec(blocks, spec)

    def test_architecture_renders_structure_as_regions_without_flow_arrows(self):
        spec = architecture_spec()
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])

        self.assertIn('data-diagram-kind="architecture"', html)
        self.assertIn('data-region-id="orchestration-band"', html)
        self.assertIn('data-has-content="false"', html)
        self.assertIn('data-owner-entity-id="orchestration"', html)
        self.assertIn('data-kind="contains"', html)
        self.assertIn('data-source-blocks="b001"', html)
        self.assertIn('执行内核 contains 编排层', html)
        self.assertNotIn('mv-edge', html)

    def test_architecture_rejects_contains_relation_without_spatial_ownership(self):
        spec = copy.deepcopy(architecture_spec())
        spec['views'][0]['composition'] = {
            'rootRegionId': 'main',
            'readingPath': {'kind': 'scan', 'sequence': []},
            'focalIds': ['kernel'],
            'regions': [{
                'id': 'main',
                'primitive': 'container',
                'role': 'main',
                'axis': 'vertical',
                'parentId': None,
                'entityIds': ['kernel', 'orchestration'],
                'childRegionIds': [],
                'targetRegionIds': [],
            }],
        }

        with self.assertRaisesRegex(ValueError, 'contains.*嵌套'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_duplicate_child_region_before_renderer_duplicates_dom(self):
        spec = architecture_spec()
        spec['views'][0]['composition']['regions'][0]['childRegionIds'] = [
            'orchestration-band',
            'orchestration-band',
        ]

        with self.assertRaisesRegex(
            ValueError,
            r'regions\[main\]\.childRegionIds 不得重复: orchestration-band',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_architecture_accepts_dependency_without_inventing_contains(self):
        spec = copy.deepcopy(architecture_spec())
        spec['views'][0]['relations'] = [{
            'id': 'depends-on-layer',
            'subjectId': 'orchestration',
            'objectId': 'kernel',
            'kind': 'dependsOn',
            'emphasis': 'primary',
            'label': '依赖执行能力',
            'sourceBlockIds': ['b001'],
        }]

        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '编排层依赖执行内核。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])
        self.assertIn('data-kind="dependsOn"', html)
        self.assertNotIn('data-kind="contains"', html)

    def test_flow_requires_dynamic_relation_and_terminal_or_cycle(self):
        spec = flow_spec()
        spec['views'][0]['relations'][0]['kind'] = 'dependsOn'
        spec['views'][0]['entities'][1]['stateKind'] = 'intermediate'

        with self.assertRaisesRegex(ValueError, '(?s)动态关系.*terminal 或闭合循环'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
                spec,
            )

    def test_flow_rejects_reading_path_gap(self):
        spec = flow_spec()
        view = spec['views'][0]
        view['entities'].insert(1, {
            'id': 'reviewed',
            'type': 'state',
            'stateKind': 'intermediate',
            'emphasis': 'secondary',
            'label': '已审核',
            'detail': '请求已通过审核',
            'multiplicity': 'one',
            'sourceBlockIds': ['b001'],
        })
        view['composition']['regions'][0]['entityIds'].insert(1, 'reviewed')
        view['composition']['readingPath']['sequence'] = [
            'requested', 'reviewed', 'published',
        ]

        with self.assertRaisesRegex(
            ValueError,
            r'flow readingPath requested -> reviewed 缺少动态关系',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
                spec,
            )

    def test_flow_rejects_duplicate_entity_in_reading_path(self):
        spec = flow_spec()
        view = spec['views'][0]
        view['composition']['readingPath'] = {
            'kind': 'cyclic',
            'sequence': ['requested', 'published', 'requested'],
        }
        view['relations'].append({
            'id': 'retry-loop',
            'subjectId': 'published',
            'objectId': 'requested',
            'kind': 'transitionsTo',
            'emphasis': 'secondary',
            'label': '重试',
            'sourceBlockIds': ['b001'],
        })

        with self.assertRaisesRegex(
            ValueError,
            r'readingPath\.sequence 不得重复实体: requested',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布失败后重试。'}],
                spec,
            )

    def test_flow_rejects_relation_opposite_to_reading_path(self):
        spec = flow_spec()
        relation = spec['views'][0]['relations'][0]
        relation['subjectId'], relation['objectId'] = (
            relation['objectId'], relation['subjectId'],
        )

        with self.assertRaisesRegex(
            ValueError,
            r'flow readingPath requested -> published 缺少动态关系',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
                spec,
            )

    def test_flow_rejects_reading_path_gap_without_dynamic_relation(self):
        spec = flow_spec()
        spec['views'][0]['entities'].insert(1, {
            'id': 'approved',
            'type': 'state',
            'stateKind': 'intermediate',
            'emphasis': 'secondary',
            'label': '已审核',
            'detail': '请求通过发布检查',
            'multiplicity': 'one',
            'sourceBlockIds': ['b001'],
        })
        spec['views'][0]['composition']['readingPath']['sequence'] = [
            'requested',
            'approved',
            'published',
        ]
        spec['views'][0]['composition']['regions'][0]['entityIds'] = [
            'requested',
            'approved',
            'published',
        ]
        spec['views'][0]['relations'][0].update({
            'subjectId': 'approved',
            'objectId': 'published',
        })

        with self.assertRaisesRegex(ValueError, 'readingPath.*requested -> approved.*动态关系'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
                spec,
            )

    def test_flow_renders_only_dynamic_relations_as_directed_connectors(self):
        spec = flow_spec()
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])

        self.assertIn('data-diagram-kind="flow"', html)
        self.assertIn('class="mv-flow-sequence"', html)
        self.assertIn('class="mv-connector"', html)
        self.assertIn('data-kind="transitionsTo"', html)
        self.assertIn('data-directed="true"', html)
        self.assertNotIn('data-kind="contains"', html)

    def test_flow_renders_cycle_relation_as_directed_connector_with_its_fact(self):
        spec = flow_spec()
        view = spec['views'][0]
        view['composition']['readingPath']['kind'] = 'cyclic'
        view['relations'].append({
            'id': 'retry-loop',
            'subjectId': 'published',
            'objectId': 'requested',
            'kind': 'transitionsTo',
            'emphasis': 'secondary',
            'label': '重新发布',
            'sourceBlockIds': ['b001'],
        })
        view['facts'].append({
            'id': 'retry-condition',
            'kind': 'exception',
            'scope': {'kind': 'relation', 'targetIds': ['retry-loop']},
            'label': '重试条件',
            'value': '发布结果不满足验收条件',
            'sourceBlockIds': ['b001'],
        })
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '发布失败后重新进入待发布状态。'}],
            spec,
        )

        html = render_v3_view(view)

        self.assertIn('class="mv-flow-secondary-relations"', html)
        self.assertIn('data-flow-relation-role="cycle"', html)
        self.assertIn(
            'class="mv-connector mv-connector--auxiliary" data-relation-id="retry-loop"',
            html,
        )
        self.assertIn('data-visual-direction="reverse"', html)
        self.assertIn('data-directed="true"', html)
        loop_start = html.index('data-relation-id="retry-loop"')
        loop_end = html.find('</li>', loop_start)
        self.assertIn('data-fact-id="retry-condition"', html[loop_start:loop_end])

    def test_flow_rejects_non_dynamic_relation_instead_of_hiding_it(self):
        spec = flow_spec()
        spec['views'][0]['relations'].append({
            'id': 'runtime-dependency',
            'subjectId': 'published',
            'objectId': 'requested',
            'kind': 'dependsOn',
            'emphasis': 'secondary',
            'label': '依赖发布配置',
            'sourceBlockIds': ['b001'],
        })

        with self.assertRaisesRegex(ValueError, 'flow relation 不兼容.*dependsOn'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程依赖发布配置。'}],
                spec,
            )

    def test_flow_renders_branch_entities_and_their_directed_relation(self):
        spec = flow_spec()
        view = spec['views'][0]
        view['entities'].append({
            'id': 'failed',
            'type': 'state',
            'stateKind': 'terminal',
            'emphasis': 'secondary',
            'label': '发布失败',
            'detail': '检查失败后的终态',
            'multiplicity': 'one',
            'sourceBlockIds': ['b001'],
        })
        view['relations'].append({
            'id': 'publish-failed',
            'subjectId': 'requested',
            'objectId': 'failed',
            'kind': 'transitionsTo',
            'emphasis': 'primary',
            'label': '检查失败',
            'sourceBlockIds': ['b001'],
        })
        view['facts'].append({
            'id': 'failure-reason',
            'kind': 'exception',
            'scope': {'kind': 'entity', 'targetIds': ['failed']},
            'label': '失败原因',
            'value': '发布检查未通过',
            'sourceBlockIds': ['b001'],
        })
        view['composition']['regions'][0]['entityIds'].append('failed')
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '发布检查失败会进入失败终态。'}],
            spec,
        )

        html = render_v3_view(view)

        self.assertIn('class="mv-flow-branches"', html)
        self.assertIn('data-entity-id="failed"', html)
        self.assertIn('data-relation-id="publish-failed"', html)
        self.assertIn('data-fact-id="failure-reason"', html)
        self.assertIn('data-declared-entity-ids="requested published failed"', html)
        self.assertIn('data-declared-relation-ids="publish publish-failed"', html)
        self.assertIn('data-declared-fact-ids="failure-reason"', html)

    def test_flow_rejects_entities_unreachable_from_the_reading_start(self):
        spec = flow_spec()
        view = spec['views'][0]
        view['entities'].append({
            'id': 'orphan',
            'type': 'state',
            'stateKind': 'terminal',
            'emphasis': 'secondary',
            'label': '孤立状态',
            'detail': '没有动态关系可以到达',
            'multiplicity': 'one',
            'sourceBlockIds': ['b001'],
        })
        view['composition']['regions'][0]['entityIds'].append('orphan')

        with self.assertRaisesRegex(ValueError, 'flow 存在从 readingPath 起点不可达的实体: orphan'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
                spec,
            )

    def test_matrix_requires_every_comparison_fact_to_cover_all_options(self):
        spec = matrix_spec()
        spec['views'][0]['facts'][0]['values'].pop()

        with self.assertRaisesRegex(ValueError, '比较 fact dependency.*route-b'):
            validate_v3_spec(
                [{
                    'id': 'b001',
                    'type': 'table',
                    'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
                }],
                spec,
            )

    def test_matrix_renders_shared_dimensions_as_a_real_table(self):
        spec = matrix_spec()
        blocks = [{
            'id': 'b001',
            'type': 'table',
            'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
        }]
        validate_v3_spec(blocks, spec)

        html = render_v3_view(spec['views'][0])

        self.assertIn('data-diagram-kind="matrix"', html)
        self.assertIn('<table class="mv-matrix">', html)
        self.assertIn('<th scope="col" data-entity-id="route-a"', html)
        self.assertIn('data-fact-id="dependency"', html)
        self.assertIn('主页、页头选择器', html)
        self.assertNotIn('mv-connector', html)

    def test_matrix_rejects_comparison_fact_scoped_to_one_option(self):
        spec = matrix_spec()
        fact = spec['views'][0]['facts'][0]
        fact['scope'] = {'kind': 'entity', 'targetIds': ['route-a']}
        fact.pop('sourceUnitId')

        with self.assertRaisesRegex(
            ValueError,
            r'matrix 比较 fact dependency 必须 scope 到当前 view',
        ):
            validate_v3_spec(
                [{
                    'id': 'b001',
                    'type': 'table',
                    'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
                }],
                spec,
            )

    def test_matrix_rejects_relations_instead_of_dropping_them(self):
        spec = matrix_spec()
        spec['views'][0]['relations'].append({
            'id': 'option-dependency',
            'subjectId': 'route-a',
            'objectId': 'route-b',
            'kind': 'dependsOn',
            'emphasis': 'secondary',
            'label': '依赖',
            'sourceBlockIds': ['b001'],
        })

        with self.assertRaisesRegex(ValueError, 'matrix 不接受 relation'):
            validate_v3_spec(
                [{
                    'id': 'b001',
                    'type': 'table',
                    'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
                }],
                spec,
            )

    def test_matrix_rejects_non_option_entity_instead_of_dropping_it(self):
        spec = matrix_spec()
        view = spec['views'][0]
        view['entities'].append({
            'id': 'comparison-context',
            'type': 'context',
            'emphasis': 'secondary',
            'label': '比较背景',
            'detail': '不属于任何被比较方案',
            'multiplicity': 'one',
            'sourceBlockIds': ['b001'],
        })
        view['composition']['regions'][0]['entityIds'].append('comparison-context')

        with self.assertRaisesRegex(
            ValueError,
            r'matrix 只接受 option entity: comparison-context',
        ):
            validate_v3_spec(
                [{
                    'id': 'b001',
                    'type': 'table',
                    'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
                }],
                spec,
            )

    def test_argument_rejects_support_relation_encoded_as_execution_sequence(self):
        spec = argument_spec()
        composition = spec['views'][0]['composition']
        composition['regions'][0]['primitive'] = 'sequence'
        composition['readingPath'] = {
            'kind': 'left-right',
            'sequence': ['evidence', 'claim'],
        }

        with self.assertRaisesRegex(ValueError, 'argument.*执行顺序'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '直达路由依赖更少。'}],
                spec,
            )

    def test_argument_rejects_support_relation_that_does_not_target_claim(self):
        spec = argument_spec()
        view = spec['views'][0]
        view['entities'].append({
            'id': 'evidence-2',
            'type': 'evidence',
            'emphasis': 'secondary',
            'label': '另一条证据',
            'detail': '只与第一条证据相关',
            'multiplicity': 'one',
            'sourceBlockIds': ['b001'],
        })
        view['composition']['regions'][0]['entityIds'].append('evidence-2')
        view['relations'][0]['objectId'] = 'evidence-2'

        with self.assertRaisesRegex(
            ValueError,
            r'argument relation supports 必须指向 claim',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '直达路由依赖更少。'}],
                spec,
            )

    def test_argument_renders_claim_centered_evidence_without_flow_connectors(self):
        spec = argument_spec()
        spec['views'][0]['facts'] = [
            {
                'id': 'evidence-detail',
                'kind': 'evidence',
                'scope': {'kind': 'entity', 'targetIds': ['evidence']},
                'label': '依赖差异',
                'value': '少依赖主页与页头选择器',
                'sourceBlockIds': ['b001'],
            },
            {
                'id': 'support-strength',
                'kind': 'evidence',
                'scope': {'kind': 'relation', 'targetIds': ['supports']},
                'label': '证据强度',
                'value': '直接支持结论',
                'sourceBlockIds': ['b001'],
            },
        ]
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '直达路由依赖更少。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])

        self.assertIn('data-diagram-kind="argument"', html)
        self.assertIn('class="mv-argument"', html)
        self.assertIn('data-argument-role="claim"', html)
        self.assertIn('data-argument-role="evidence"', html)
        self.assertIn('class="mv-argument-relation"', html)
        self.assertIn('class="mv-argument-connector" data-direction="to-claim"', html)
        self.assertIn('data-kind="supportsClaim"', html)
        self.assertIn('data-source-blocks="b001"', html)
        self.assertIn('data-fact-id="evidence-detail"', html)
        self.assertIn('data-fact-id="support-strength"', html)
        self.assertIn('class="mv-argument-evidence-main"', html)
        self.assertIn('class="mv-argument-link"', html)
        self.assertLess(
            html.index('class="mv-argument-evidence-main"'),
            html.index('data-fact-id="evidence-detail"'),
        )
        self.assertLess(
            html.index('class="mv-argument-link"'),
            html.index('data-relation-id="supports"'),
        )
        self.assertLess(
            html.index('class="mv-argument-link"'),
            html.index('class="mv-argument-evidence-main"'),
        )
        self.assertGreater(
            html.index('data-fact-id="support-strength"'),
            html.index('data-relation-id="supports"'),
        )
        self.assertNotIn('mv-connector', html)

    def test_argument_preserves_multiple_relations_from_one_evidence(self):
        spec = argument_spec()
        view = spec['views'][0]
        view['relations'].append({
            'id': 'mitigates-risk',
            'subjectId': 'evidence',
            'objectId': 'claim',
            'kind': 'mitigates',
            'emphasis': 'secondary',
            'label': '缓解风险',
            'sourceBlockIds': ['b001'],
        })
        view['facts'].append({
            'id': 'mitigation-detail',
            'kind': 'evidence',
            'scope': {'kind': 'relation', 'targetIds': ['mitigates-risk']},
            'label': '缓解方式',
            'value': '缩小变动面',
            'sourceBlockIds': ['b001'],
        })
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '直达路由依赖更少。'}],
            spec,
        )

        html = render_v3_view(view)

        self.assertIn('data-relation-id="supports"', html)
        self.assertIn('data-relation-id="mitigates-risk"', html)
        self.assertIn('data-fact-id="mitigation-detail"', html)

    def test_argument_rejects_non_argument_relation_instead_of_dropping_it(self):
        spec = argument_spec()
        spec['views'][0]['relations'].append({
            'id': 'runtime-dependency',
            'subjectId': 'evidence',
            'objectId': 'claim',
            'kind': 'dependsOn',
            'emphasis': 'secondary',
            'label': '依赖',
            'sourceBlockIds': ['b001'],
        })

        with self.assertRaisesRegex(ValueError, 'argument relation 不兼容.*dependsOn'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '直达路由依赖更少。'}],
                spec,
            )

    def test_malformed_collections_fail_as_contract_errors(self):
        blocks = [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}]
        for field in ('entities', 'relations', 'facts'):
            spec = flow_spec()
            spec['views'][0][field] = 'not-an-array'
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    ValueError,
                    rf'v1\.{field} 必须是数组',
                ):
                    validate_v3_spec(blocks, spec)

    def test_null_views_fail_as_a_contract_error(self):
        spec = architecture_spec()
        spec['views'] = None

        with self.assertRaisesRegex(ValueError, 'views 必须是非空数组'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核。'}],
                spec,
            )

    def test_rejects_source_block_reference_that_is_not_in_authoritative_blocks(self):
        spec = architecture_spec()
        spec['views'][0]['entities'][1]['sourceBlockIds'] = ['b999']

        with self.assertRaisesRegex(ValueError, 'sourceBlockId 不存在: b999'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_duplicate_source_block_reference_like_schema(self):
        spec = architecture_spec()
        spec['page']['centralClaim']['sourceBlockIds'] = ['b001', 'b001']

        with self.assertRaisesRegex(
            ValueError,
            r'page\.centralClaim\.sourceBlockIds 不得重复: b001',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_duplicate_focal_id_like_schema(self):
        spec = architecture_spec()
        spec['views'][0]['composition']['focalIds'] = ['kernel', 'kernel']

        with self.assertRaisesRegex(
            ValueError,
            r'composition\.focalIds 不得重复: kernel',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_freeform_visual_style_in_semantic_spec(self):
        spec = architecture_spec()
        spec['views'][0]['entities'][0]['style'] = {
            'color': '#ff0000',
            'position': 'absolute',
        }

        with self.assertRaisesRegex(ValueError, 'entities\\[kernel\\].*未知字段: style'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_unknown_relation_kind_before_rendering(self):
        spec = architecture_spec()
        spec['views'][0]['relations'][0]['kind'] = 'relatedTo'

        with self.assertRaisesRegex(ValueError, 'relation.*kind 非法: relatedTo'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_architecture_rejects_dynamic_relation_as_primary_grammar(self):
        spec = architecture_spec()
        spec['views'][0]['relations'][0].update({
            'kind': 'calls',
            'label': '调用',
            'emphasis': 'primary',
        })

        with self.assertRaisesRegex(ValueError, 'architecture.*primary.*calls'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核调用编排层。'}],
                spec,
            )

    def test_architecture_rejects_layer_of_without_spatial_nesting(self):
        spec = architecture_spec()
        view = spec['views'][0]
        view['relations'][0].update({
            'kind': 'layerOf',
            'subjectId': 'orchestration',
            'objectId': 'kernel',
        })
        view['composition'] = {
            'rootRegionId': 'main',
            'readingPath': {'kind': 'scan', 'sequence': []},
            'focalIds': ['kernel'],
            'regions': [{
                'id': 'main',
                'primitive': 'axis',
                'role': 'main',
                'axis': 'horizontal',
                'parentId': None,
                'entityIds': ['kernel', 'orchestration'],
                'childRegionIds': [],
                'targetRegionIds': [],
            }],
        }

        with self.assertRaisesRegex(
            ValueError,
            r'layerOf 关系必须通过 region 嵌套表达',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '编排层属于执行内核。'}],
                spec,
            )

    def test_rejects_invalid_fact_and_state_vocabularies(self):
        spec = flow_spec()
        spec['views'][0]['entities'][0]['stateKind'] = 'done-ish'
        spec['views'][0]['facts'] = [{
            'id': 'note',
            'kind': 'decoration',
            'scope': {'kind': 'view', 'targetIds': ['v1']},
            'label': '说明',
            'value': '任意样式提示',
            'sourceBlockIds': ['b001'],
        }]

        with self.assertRaisesRegex(
            ValueError,
            '(?s)stateKind 非法: done-ish.*facts\\[note\\]\\.kind 非法: decoration',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '发布流程。'}],
                spec,
            )

    def test_rejects_region_parent_child_mismatch(self):
        spec = architecture_spec()
        spec['views'][0]['composition']['regions'][0]['childRegionIds'] = []

        with self.assertRaisesRegex(ValueError, 'parentId.*childRegionIds.*不一致'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_region_primitives_that_contradict_their_semantics(self):
        cases = []

        stack_spec = architecture_spec()
        stack_spec['views'][0]['composition']['regions'][0]['primitive'] = 'stack'
        cases.append((stack_spec, 'stack.*multiplicity=many'))

        crosscut_spec = architecture_spec()
        crosscut_spec['views'][0]['composition']['regions'][1]['primitive'] = 'crosscut'
        cases.append((crosscut_spec, 'crosscut.*targetRegionIds'))

        sequence_spec = architecture_spec()
        sequence_spec['views'][0]['composition']['regions'][0]['primitive'] = 'sequence'
        cases.append((sequence_spec, 'sequence.*flow'))

        blocks = [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}]
        for spec, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_v3_spec(blocks, spec)

    def test_rejects_fact_scope_that_cannot_attach_to_a_real_target(self):
        spec = architecture_spec()
        spec['views'][0]['facts'] = [{
            'id': 'boundary',
            'kind': 'constraint',
            'scope': {'kind': 'entity', 'targetIds': ['missing-layer']},
            'label': '边界',
            'value': '只组织任务，不直接执行工具',
            'sourceBlockIds': ['b001'],
        }]

        with self.assertRaisesRegex(ValueError, 'facts\\[boundary\\].*scope target 不存在'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_rejects_multi_target_fact_scope_instead_of_duplicating_fact_dom(self):
        spec = architecture_spec()
        spec['views'][0]['facts'] = [{
            'id': 'shared-boundary',
            'kind': 'constraint',
            'scope': {
                'kind': 'entity',
                'targetIds': ['kernel', 'orchestration'],
            },
            'label': '共同边界',
            'value': '两个实体共同受此约束',
            'sourceBlockIds': ['b001'],
        }]

        with self.assertRaisesRegex(
            ValueError,
            r'facts\[shared-boundary\]\.scope\.targetIds 必须恰有一个目标',
        ):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_architecture_places_entity_fact_inside_its_semantic_region(self):
        spec = architecture_spec()
        spec['views'][0]['facts'] = [{
            'id': 'boundary',
            'kind': 'constraint',
            'scope': {'kind': 'entity', 'targetIds': ['orchestration']},
            'label': '边界',
            'value': '只组织任务，不直接执行工具',
            'sourceBlockIds': ['b001'],
        }]
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])

        owner_index = html.index('data-owner-entity-id="orchestration"')
        fact_index = html.index('data-fact-id="boundary"')
        self.assertGreater(fact_index, owner_index)
        self.assertIn('data-scope-kind="entity"', html)
        self.assertIn('data-target-ids="orchestration"', html)

    def test_matrix_preserves_every_cell_of_referenced_source_row(self):
        spec = matrix_spec()
        spec['views'][0]['facts'][0]['values'][0]['value'] = '额外导航依赖'
        blocks = [{
            'id': 'b001',
            'type': 'table',
            'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
        }]

        with self.assertRaisesRegex(ValueError, 'b001:r001.*表格单元格: 主页'):
            validate_v3_spec(blocks, spec)

    def test_unimplemented_family_fails_at_contract_boundary(self):
        spec = architecture_spec()
        spec['views'][0]['diagramKind'] = 'topology'

        with self.assertRaisesRegex(ValueError, 'unsupported_diagram_kind: topology'):
            validate_v3_spec(
                [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
                spec,
            )

    def test_renderer_rejects_any_declared_semantic_id_missing_from_dom(self):
        spec = matrix_spec()
        view = spec['views'][0]
        validate_v3_spec(
            [{
                'id': 'b001',
                'type': 'table',
                'raw': '| 维度 | A | B |\n| --- | --- | --- |\n| 页面依赖 | 主页 | 登录入口 |',
            }],
            spec,
        )

        with patch('v3_renderer._render_matrix', return_value='<table></table>'):
            with self.assertRaisesRegex(
                ValueError,
                'rendered_semantic_set_mismatch.*entity.*route-a',
            ):
                render_v3_view(view)

    def test_architecture_encodes_dependency_as_adjacency_not_execution_arrow(self):
        spec = architecture_spec()
        spec['views'][0]['relations'].append({
            'id': 'provides-api',
            'subjectId': 'kernel',
            'objectId': 'orchestration',
            'kind': 'provides',
            'emphasis': 'secondary',
            'label': '提供执行接口',
            'sourceBlockIds': ['b001'],
        })
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '执行内核分层承载职责。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])

        self.assertIn('class="mv-architecture-relation"', html)
        self.assertIn('data-visual="adjacency"', html)
        self.assertIn('提供执行接口', html)
        self.assertNotIn('class="mv-connector"', html)

    def test_architecture_attaches_relation_fact_to_relation_encoding(self):
        spec = architecture_spec()
        spec['views'][0]['relations'].append({
            'id': 'provides-api',
            'subjectId': 'kernel',
            'objectId': 'orchestration',
            'kind': 'provides',
            'emphasis': 'secondary',
            'label': '提供执行接口',
            'sourceBlockIds': ['b001'],
        })
        spec['views'][0]['facts'] = [{
            'id': 'api-constraint',
            'kind': 'constraint',
            'scope': {'kind': 'relation', 'targetIds': ['provides-api']},
            'label': '接口约束',
            'value': '只暴露任务操作',
            'sourceBlockIds': ['b001'],
        }]
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '只暴露任务操作。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])
        relation_start = html.index('data-relation-id="provides-api"')
        relation_end = html.index('</li>', relation_start)
        fact_start = html.index('data-fact-id="api-constraint"')
        self.assertLess(relation_start, fact_start)
        self.assertLess(fact_start, relation_end)

    def test_flow_attaches_relation_fact_to_its_connector(self):
        spec = flow_spec()
        spec['views'][0]['facts'] = [{
            'id': 'approval-guard',
            'kind': 'constraint',
            'scope': {'kind': 'relation', 'targetIds': ['publish']},
            'label': '前置条件',
            'value': '审核通过',
            'sourceBlockIds': ['b001'],
        }]
        validate_v3_spec(
            [{'id': 'b001', 'type': 'paragraph', 'raw': '发布前必须审核通过。'}],
            spec,
        )

        html = render_v3_view(spec['views'][0])

        connector_index = html.index('data-relation-id="publish"')
        fact_index = html.index('data-fact-id="approval-guard"')
        self.assertGreater(fact_index, connector_index)
        self.assertIn('data-scope-kind="relation"', html)


if __name__ == '__main__':
    unittest.main()
