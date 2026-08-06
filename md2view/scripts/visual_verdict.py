#!/usr/bin/env python3
"""Validate independent visual-semantic verdicts for md2view candidate readers."""
import argparse
import hashlib
import json
import os
from pathlib import Path


ALLOWED_VIEW_VERDICTS = {'PASS', 'REJECT', 'UNCERTAIN'}


def load_visual_verdict(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _require_string(problem, value, label):
    if not isinstance(value, str) or not value.strip():
        problem.append(f'{label} 必须是非空字符串')


def _require_bool(problem, value, label):
    if not isinstance(value, bool):
        problem.append(f'{label} 必须是布尔值')


def _validate_blind_readback(problem, readback, view_id):
    if not isinstance(readback, dict):
        problem.append(f'{view_id}.blindReadback 必须是对象')
        return
    _require_string(problem, readback.get('centralClaimParaphrase'), f'{view_id}.blindReadback.centralClaimParaphrase')
    _require_string(problem, readback.get('dominantRelation'), f'{view_id}.blindReadback.dominantRelation')
    focal = readback.get('firstFocalLabels')
    if not isinstance(focal, list) or not focal or any(not isinstance(item, str) or not item.strip() for item in focal):
        problem.append(f'{view_id}.blindReadback.firstFocalLabels 必须是非空字符串数组')
    attachments = readback.get('factAttachments')
    if not isinstance(attachments, list):
        problem.append(f'{view_id}.blindReadback.factAttachments 必须是数组')
    else:
        for index, attachment in enumerate(attachments, 1):
            if not isinstance(attachment, dict):
                problem.append(f'{view_id}.blindReadback.factAttachments[{index}] 必须是对象')
                continue
            _require_string(problem, attachment.get('factLabel'), f'{view_id}.blindReadback.factAttachments[{index}].factLabel')
            _require_string(
                problem,
                attachment.get('attachedToLabel'),
                f'{view_id}.blindReadback.factAttachments[{index}].attachedToLabel',
            )
    _require_string(
        problem,
        readback.get('lowerMisreadAlternative'),
        f'{view_id}.blindReadback.lowerMisreadAlternative',
    )


def _validate_comparison(problem, comparison, view_id):
    if not isinstance(comparison, dict):
        problem.append(f'{view_id}.comparison 必须是对象')
        return
    _require_bool(problem, comparison.get('claimMatches'), f'{view_id}.comparison.claimMatches')
    _require_bool(problem, comparison.get('focalMatches'), f'{view_id}.comparison.focalMatches')
    if comparison.get('claimMatches') is not True:
        problem.append(f'{view_id}.comparison.claimMatches 必须为 true')
    if comparison.get('focalMatches') is not True:
        problem.append(f'{view_id}.comparison.focalMatches 必须为 true')
    relation_matches = comparison.get('primaryRelationMatches')
    if not isinstance(relation_matches, list):
        problem.append(f'{view_id}.comparison.primaryRelationMatches 必须是数组')
    else:
        for index, item in enumerate(relation_matches, 1):
            if not isinstance(item, dict):
                problem.append(f'{view_id}.comparison.primaryRelationMatches[{index}] 必须是对象')
                continue
            _require_string(
                problem,
                item.get('relationId'),
                f'{view_id}.comparison.primaryRelationMatches[{index}].relationId',
            )
            _require_bool(
                problem,
                item.get('matches'),
                f'{view_id}.comparison.primaryRelationMatches[{index}].matches',
            )
            if item.get('matches') is not True:
                problem.append(
                    f'{view_id}.comparison.primaryRelationMatches '
                    f'{item.get("relationId") or index} 必须为 true'
                )
    fact_matches = comparison.get('factScopeMatches')
    if not isinstance(fact_matches, list):
        problem.append(f'{view_id}.comparison.factScopeMatches 必须是数组')
    else:
        for index, item in enumerate(fact_matches, 1):
            if not isinstance(item, dict):
                problem.append(f'{view_id}.comparison.factScopeMatches[{index}] 必须是对象')
                continue
            _require_string(
                problem,
                item.get('factId'),
                f'{view_id}.comparison.factScopeMatches[{index}].factId',
            )
            _require_bool(
                problem,
                item.get('matches'),
                f'{view_id}.comparison.factScopeMatches[{index}].matches',
            )
            if item.get('matches') is not True:
                problem.append(
                    f'{view_id}.comparison.factScopeMatches '
                    f'{item.get("factId") or index} 必须为 true'
                )


def validate_visual_verdict(
    verdict,
    *,
    candidate_path=None,
    candidate_ref=None,
    producer_id=None,
    require_digest=False,
    spec=None,
):
    """Validate a visual verdict payload or a JSON file path.

    Returns the parsed payload on success, otherwise raises ValueError.
    """
    if isinstance(verdict, (str, os.PathLike)):
        verdict = load_visual_verdict(verdict)

    problems = []
    if not isinstance(verdict, dict):
        raise ValueError('visual-verdict 必须是对象')

    if verdict.get('schemaVersion') != 1:
        problems.append('schemaVersion 必须是 1')

    candidate = verdict.get('candidate')
    if candidate_path is not None or candidate_ref is not None:
        expected_name = Path(candidate_ref or candidate_path).name
        if not isinstance(candidate, str) or Path(candidate).name != expected_name:
            problems.append(f'candidate 必须匹配 {expected_name}')
    if require_digest:
        digest = verdict.get('candidateSha256')
        if not isinstance(digest, str) or len(digest) != 64:
            problems.append('candidateSha256 必须是 64 位十六进制字符串')
        elif candidate_path is None or not Path(candidate_path).is_file():
            problems.append('candidateSha256 校验需要可读候选文件')
        else:
            actual_digest = hashlib.sha256(Path(candidate_path).read_bytes()).hexdigest()
            if digest.lower() != actual_digest:
                problems.append('candidateSha256 与候选文件不匹配')

    reviewer = verdict.get('reviewer')
    if not isinstance(reviewer, dict):
        problems.append('reviewer 必须是对象')
    else:
        _require_string(problems, reviewer.get('mode'), 'reviewer.mode')
        _require_bool(problems, reviewer.get('independentFromProducer'), 'reviewer.independentFromProducer')
        if reviewer.get('independentFromProducer') is not True:
            problems.append('reviewer.independentFromProducer 必须为 true')
        if producer_id is not None:
            reviewer_id = reviewer.get('id')
            _require_string(problems, reviewer_id, 'reviewer.id')
            if reviewer_id == producer_id:
                problems.append('reviewer 与 producer 必须独立')

    views = verdict.get('views')
    if not isinstance(views, list) or not views:
        problems.append('views 必须是非空数组')
        views = []

    for index, view in enumerate(views, 1):
        view_label = f'views[{index}]'
        if not isinstance(view, dict):
            problems.append(f'{view_label} 必须是对象')
            continue
        _require_string(problems, view.get('viewId'), f'{view_label}.viewId')
        _validate_blind_readback(problems, view.get('blindReadback'), view_label)
        _validate_comparison(problems, view.get('comparison'), view_label)
        verdict_state = view.get('verdict')
        if verdict_state not in ALLOWED_VIEW_VERDICTS:
            problems.append(f'{view_label}.verdict 必须是 PASS / REJECT / UNCERTAIN')
        elif verdict_state != 'PASS':
            problems.append(f'{view_label}.verdict 必须为 PASS')

    if spec is not None:
        expected_view_ids = {
            view.get('id')
            for view in spec.get('views', [])
            if isinstance(view, dict) and view.get('id')
        }
        actual_view_ids = {
            view.get('viewId')
            for view in views
            if isinstance(view, dict) and view.get('viewId')
        }
        missing_views = sorted(expected_view_ids - actual_view_ids)
        extra_views = sorted(actual_view_ids - expected_view_ids)
        if missing_views:
            problems.append(f'未覆盖 view: {", ".join(missing_views)}')
        if extra_views:
            problems.append(f'引用 spec 外 view: {", ".join(extra_views)}')
        verdict_views = {
            view.get('viewId'): view
            for view in views
            if isinstance(view, dict) and view.get('viewId')
        }
        for spec_view in spec.get('views', []):
            if not isinstance(spec_view, dict) or not spec_view.get('id'):
                continue
            view_id = spec_view['id']
            verdict_view = verdict_views.get(view_id)
            if verdict_view is None:
                continue
            comparison = verdict_view.get('comparison')
            if not isinstance(comparison, dict):
                continue
            expected_relations = {
                relation.get('id')
                for relation in spec_view.get('relations', [])
                if isinstance(relation, dict)
                and relation.get('id')
                and relation.get('emphasis') == 'primary'
            }
            actual_relations = {
                item.get('relationId')
                for item in comparison.get('primaryRelationMatches', [])
                if isinstance(item, dict) and item.get('relationId')
            }
            missing_relations = sorted(expected_relations - actual_relations)
            extra_relations = sorted(actual_relations - expected_relations)
            if missing_relations:
                problems.append(
                    f'{view_id} 未核对 primary relation: '
                    + ', '.join(missing_relations)
                )
            if extra_relations:
                problems.append(
                    f'{view_id} 核对了非 primary relation: '
                    + ', '.join(extra_relations)
                )

            expected_facts = {
                fact.get('id')
                for fact in spec_view.get('facts', [])
                if isinstance(fact, dict) and fact.get('id')
            }
            actual_facts = {
                item.get('factId')
                for item in comparison.get('factScopeMatches', [])
                if isinstance(item, dict) and item.get('factId')
            }
            missing_facts = sorted(expected_facts - actual_facts)
            extra_facts = sorted(actual_facts - expected_facts)
            if missing_facts:
                problems.append(
                    f'{view_id} 未核对 fact scope: ' + ', '.join(missing_facts)
                )
            if extra_facts:
                problems.append(
                    f'{view_id} 核对了 spec 外 fact: ' + ', '.join(extra_facts)
                )

    if verdict.get('verdict') != 'PASS':
        problems.append('verdict 必须为 PASS')

    if problems:
        raise ValueError('visual-verdict 合同失败:\n- ' + '\n- '.join(problems))
    return verdict


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate a md2view visual-verdict.json file.')
    parser.add_argument('verdict')
    parser.add_argument(
        '--candidate',
        help='候选 HTML 路径；若提供，candidate 字段必须与之同名',
    )
    args = parser.parse_args(argv)
    validate_visual_verdict(args.verdict, candidate_path=args.candidate)
    print(f'visual-verdict ok: {args.verdict}')


if __name__ == '__main__':
    main()


__all__ = ['load_visual_verdict', 'validate_visual_verdict', 'main']
