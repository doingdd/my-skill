#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from visual_verdict import validate_visual_verdict


class VisualVerdictTests(unittest.TestCase):
    def test_accepts_pass_verdict(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'mode': 'vision-agent',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构，不是八步流程',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [{
                        'factLabel': '边界',
                        'attachedToLabel': '编排层',
                    }],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [{'relationId': 'rel1', 'matches': True}],
                    'focalMatches': True,
                    'factScopeMatches': [{'factId': 'f1', 'matches': True}],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }

        self.assertEqual(validate_visual_verdict(verdict, candidate_path='reader.candidate.html')['verdict'], 'PASS')

    def test_rejects_non_independent_reviewer(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'mode': 'vision-agent',
                'independentFromProducer': False,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }

        with self.assertRaisesRegex(ValueError, 'independentFromProducer'):
            validate_visual_verdict(verdict, candidate_path='reader.candidate.html')

    def test_rejects_candidate_mismatch(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'other.candidate.html',
            'reviewer': {
                'mode': 'human',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }

        with self.assertRaisesRegex(ValueError, 'candidate 必须匹配 reader\\.candidate\\.html'):
            validate_visual_verdict(verdict, candidate_path='reader.candidate.html')

    def test_rejects_uncertain_view(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'mode': 'human',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'UNCERTAIN',
            }],
            'verdict': 'PASS',
        }

        with self.assertRaisesRegex(ValueError, 'views\\[1\\]\\.verdict 必须为 PASS'):
            validate_visual_verdict(verdict, candidate_path='reader.candidate.html')

    def test_rejects_pass_label_when_semantic_comparison_is_false(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'mode': 'human',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是八步流程',
                    'dominantRelation': 'sequence',
                    'firstFocalLabels': ['消费方'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': '分层架构',
                },
                'comparison': {
                    'claimMatches': False,
                    'primaryRelationMatches': [
                        {'relationId': 'contains-layer', 'matches': False},
                    ],
                    'focalMatches': False,
                    'factScopeMatches': [
                        {'factId': 'boundary', 'matches': False},
                    ],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }

        with self.assertRaisesRegex(
            ValueError,
            '(?s)claimMatches 必须为 true.*focalMatches 必须为 true.*contains-layer.*boundary',
        ):
            validate_visual_verdict(verdict, candidate_path='reader.candidate.html')

    def test_rejects_verdict_missing_primary_relations_and_facts_from_spec(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'mode': 'human',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }
        spec = {
            'views': [{
                'id': 'v1',
                'relations': [
                    {'id': 'contains-layer', 'emphasis': 'primary'},
                    {'id': 'context-only', 'emphasis': 'context'},
                ],
                'facts': [{'id': 'boundary'}],
            }],
        }

        with self.assertRaisesRegex(
            ValueError,
            '(?s)未核对 primary relation: contains-layer.*未核对 fact scope: boundary',
        ):
            validate_visual_verdict(
                verdict,
                candidate_path='reader.candidate.html',
                spec=spec,
            )

    def test_rejects_reviewer_identity_equal_to_recorded_producer(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'id': 'model-a',
                'mode': 'vision-agent',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }

        with self.assertRaisesRegex(ValueError, 'reviewer 与 producer 必须独立'):
            validate_visual_verdict(
                verdict,
                candidate_path='reader.candidate.html',
                producer_id='model-a',
            )

    def test_rejects_verdict_bound_to_stale_candidate_digest(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'candidateSha256': '0' * 64,
            'reviewer': {
                'id': 'reviewer-b',
                'mode': 'vision-agent',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / 'reader.candidate.html'
            candidate.write_text('current candidate', encoding='utf-8')

            with self.assertRaisesRegex(ValueError, 'candidateSha256 与候选文件不匹配'):
                validate_visual_verdict(
                    verdict,
                    candidate_path=candidate,
                    producer_id='producer-a',
                    require_digest=True,
                )

    def test_rejects_verdict_that_does_not_cover_every_spec_view(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'id': 'reviewer-b',
                'mode': 'human',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }
        spec = {'views': [{'id': 'v1'}, {'id': 'v2'}]}

        with self.assertRaisesRegex(ValueError, '未覆盖 view: v2'):
            validate_visual_verdict(
                verdict,
                candidate_path='reader.candidate.html',
                producer_id='producer-a',
                spec=spec,
            )


class VisualVerdictCliTests(unittest.TestCase):
    def test_cli_accepts_json_file(self):
        verdict = {
            'schemaVersion': 1,
            'candidate': 'reader.candidate.html',
            'reviewer': {
                'mode': 'vision-agent',
                'independentFromProducer': True,
            },
            'views': [{
                'viewId': 'v1',
                'blindReadback': {
                    'centralClaimParaphrase': '这是分层架构',
                    'dominantRelation': 'containment',
                    'firstFocalLabels': ['执行内核'],
                    'factAttachments': [],
                    'lowerMisreadAlternative': 'none',
                },
                'comparison': {
                    'claimMatches': True,
                    'primaryRelationMatches': [],
                    'focalMatches': True,
                    'factScopeMatches': [],
                },
                'verdict': 'PASS',
            }],
            'verdict': 'PASS',
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / 'visual-verdict.json'
            path.write_text(json.dumps(verdict, ensure_ascii=False), encoding='utf-8')

            validate_visual_verdict(path, candidate_path=root / 'reader.candidate.html')


if __name__ == '__main__':
    unittest.main()
