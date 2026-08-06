#!/usr/bin/env python3
"""Validate md2view v3 view-spec semantic contracts."""
from collections import defaultdict

from semantic_contract import derive_source_units, validate_semantic_model


ALLOWED_DIAGRAM_KINDS = {
    'architecture',
    'flow',
    'matrix',
    'argument',
}
DYNAMIC_RELATIONS = {'calls', 'triggers', 'produces', 'transitionsTo', 'returns'}
STRUCTURAL_RELATIONS = {'contains', 'partOf', 'layerOf', 'instanceOf'}
ARGUMENT_RELATIONS = {'supportsClaim', 'contradicts', 'mitigates'}
DEPENDENCY_RELATIONS = {'dependsOn', 'enables', 'constrains', 'provides'}
CONNECTION_RELATIONS = {'connectsTo', 'exchangesWith', 'peersWith'}
OBSERVATION_RELATIONS = {'observes', 'reports', 'alerts'}
ALLOWED_RELATION_KINDS = (
    STRUCTURAL_RELATIONS
    | DYNAMIC_RELATIONS
    | DEPENDENCY_RELATIONS
    | CONNECTION_RELATIONS
    | OBSERVATION_RELATIONS
    | ARGUMENT_RELATIONS
)
ALLOWED_FACT_KINDS = {
    'evidence', 'constraint', 'risk', 'exception', 'metric', 'checkpoint',
    'decision',
}
ALLOWED_STATE_KINDS = {'start', 'intermediate', 'terminal', 'persistent'}
ENTITY_FIELDS = {
    'id',
    'type',
    'stateKind',
    'emphasis',
    'boundary',
    'label',
    'detail',
    'multiplicity',
    'sourceBlockIds',
    'sourceUnitId',
}
SPEC_FIELDS = {'schemaVersion', 'page', 'views'}
PAGE_FIELDS = {'title', 'audience', 'readerTask', 'centralClaim', 'narrative'}
CLAIM_FIELDS = {'text', 'sourceBlockIds'}
NARRATIVE_FIELDS = {'viewId', 'role', 'transition'}
VIEW_FIELDS = {
    'id', 'title', 'question', 'centralClaim', 'narrativeRole', 'diagramKind',
    'diagramRationale', 'entities', 'relations', 'facts', 'composition',
}
RELATION_FIELDS = {
    'id', 'subjectId', 'objectId', 'kind', 'emphasis', 'label',
    'sourceBlockIds', 'sourceUnitId',
}
FACT_FIELDS = {
    'id', 'kind', 'scope', 'label', 'value', 'values', 'sourceBlockIds',
    'sourceUnitId',
}
SCOPE_FIELDS = {'kind', 'targetIds'}
COMPOSITION_FIELDS = {'rootRegionId', 'readingPath', 'focalIds', 'regions'}
READING_PATH_FIELDS = {'kind', 'sequence'}
REGION_FIELDS = {
    'id', 'primitive', 'role', 'axis', 'parentId', 'ownerEntityId',
    'entityIds', 'childRegionIds', 'targetRegionIds',
}
COMPARISON_VALUE_FIELDS = {'targetId', 'value'}


def _reject_unknown_fields(problems, value, allowed, label):
    if not isinstance(value, dict):
        return
    unknown = sorted(set(value) - allowed)
    if unknown:
        problems.append(f'{label} 未知字段: {", ".join(unknown)}')


def _require_str(problem, value, label):
    if not str(value or '').strip():
        problem.append(f'{label} 不能为空')


def _require_list(problem, value, label):
    if not isinstance(value, list):
        problem.append(f'{label} 必须是数组')
        return []
    return value


def _require_block_refs(problem, refs, label):
    if (
        not isinstance(refs, list)
        or not refs
        or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
    ):
        problem.append(f'{label} 必须是非空 sourceBlockIds 数组')
        return
    duplicates = sorted({ref for ref in refs if refs.count(ref) > 1})
    if duplicates:
        problem.append(f'{label} 不得重复: ' + ', '.join(duplicates))


def _validate_page(spec, view_ids, problems):
    page = spec.get('page')
    if not isinstance(page, dict):
        problems.append('page 必须是对象')
        return
    _reject_unknown_fields(problems, page, PAGE_FIELDS, 'page')
    _require_str(problems, page.get('title'), 'page.title')
    _require_str(problems, page.get('audience'), 'page.audience')
    _require_str(problems, page.get('readerTask'), 'page.readerTask')
    central_claim = page.get('centralClaim')
    if not isinstance(central_claim, dict):
        problems.append('page.centralClaim 必须是对象')
    else:
        _reject_unknown_fields(problems, central_claim, CLAIM_FIELDS, 'page.centralClaim')
        _require_str(problems, central_claim.get('text'), 'page.centralClaim.text')
        _require_block_refs(problems, central_claim.get('sourceBlockIds'), 'page.centralClaim.sourceBlockIds')
    narrative = _require_list(problems, page.get('narrative'), 'page.narrative')
    for index, item in enumerate(narrative, 1):
        if not isinstance(item, dict):
            problems.append(f'page.narrative[{index}] 必须是对象')
            continue
        _reject_unknown_fields(
            problems,
            item,
            NARRATIVE_FIELDS,
            f'page.narrative[{index}]',
        )
        _require_str(problems, item.get('viewId'), f'page.narrative[{index}].viewId')
        role = item.get('role')
        if role is not None:
            _require_str(problems, role, f'page.narrative[{index}].role')
        view_id = item.get('viewId')
        if view_id and view_id not in view_ids:
            problems.append(f'page.narrative[{index}].viewId 不存在: {view_id}')


def _validate_sources(blocks, spec, problems):
    block_ids = {
        block.get('id')
        for block in blocks
        if isinstance(block, dict) and block.get('id')
    }
    source_units = derive_source_units(blocks)
    sourced_items = []
    page = spec.get('page') or {}
    if isinstance(page.get('centralClaim'), dict):
        sourced_items.append(('page.centralClaim', page['centralClaim']))
    for view in spec.get('views', []):
        if not isinstance(view, dict):
            continue
        view_id = view.get('id') or '<unknown-view>'
        if isinstance(view.get('centralClaim'), dict):
            sourced_items.append((f'{view_id}.centralClaim', view['centralClaim']))
        for collection_name in ('entities', 'relations', 'facts'):
            for index, item in enumerate(view.get(collection_name, []), 1):
                if isinstance(item, dict):
                    item_id = item.get('id') or index
                    sourced_items.append((f'{view_id}.{collection_name}[{item_id}]', item))

    for label, item in sourced_items:
        refs = item.get('sourceBlockIds')
        if not isinstance(refs, list):
            continue
        for block_id in refs:
            if block_id not in block_ids:
                problems.append(f'{label}.sourceBlockId 不存在: {block_id}')
        source_unit_id = item.get('sourceUnitId')
        if not source_unit_id:
            continue
        unit = source_units.get(source_unit_id)
        if unit is None:
            problems.append(f'{label}.sourceUnitId 不存在: {source_unit_id}')
        elif unit['blockId'] not in refs:
            problems.append(
                f'{label}.sourceUnitId {source_unit_id} 的父块 '
                f'{unit["blockId"]} 未列入 sourceBlockIds'
            )


def _build_region_index(regions, problems):
    region_index = {}
    children = defaultdict(list)
    for index, region in enumerate(regions, 1):
        if not isinstance(region, dict):
            problems.append(f'composition.regions[{index}] 必须是对象')
            continue
        _reject_unknown_fields(
            problems,
            region,
            REGION_FIELDS,
            f'composition.regions[{index}]',
        )
        region_id = region.get('id')
        if not str(region_id or '').strip():
            problems.append(f'composition.regions[{index}].id 不能为空')
            continue
        if region_id in region_index:
            problems.append(f'composition.regions 重复 id: {region_id}')
            continue
        region_index[region_id] = region
        parent_id = region.get('parentId')
        if parent_id:
            children[parent_id].append(region_id)
    return region_index, children


def _validate_region_tree(view, problems):
    composition = view.get('composition')
    if not isinstance(composition, dict):
        problems.append(f'{view["id"]}.composition 必须是对象')
        return {}, {}, {}
    _reject_unknown_fields(
        problems,
        composition,
        COMPOSITION_FIELDS,
        f'{view["id"]}.composition',
    )

    root_id = composition.get('rootRegionId')
    _require_str(problems, root_id, f'{view["id"]}.composition.rootRegionId')
    regions = composition.get('regions')
    if not isinstance(regions, list) or not regions:
        problems.append(f'{view["id"]}.composition.regions 必须是非空数组')
        return {}, {}, {}

    region_index, children = _build_region_index(regions, problems)
    if root_id and root_id not in region_index:
        problems.append(f'{view["id"]}.composition.rootRegionId 不存在: {root_id}')
        return region_index, {}, {}

    root = region_index.get(root_id)
    if root and root.get('parentId') not in (None, ''):
        problems.append(f'{view["id"]}.composition.rootRegionId 必须没有 parentId')

    allowed_primitives = {'container', 'band', 'axis', 'sequence', 'radial', 'stack', 'crosscut', 'inset'}
    entity_index = {
        entity.get('id'): entity
        for entity in view.get('entities', [])
        if isinstance(entity, dict) and entity.get('id')
    }
    has_dynamic_relation = any(
        relation.get('kind') in DYNAMIC_RELATIONS
        for relation in view.get('relations', [])
        if isinstance(relation, dict)
    )
    region_lists = {}
    for region_id, region in region_index.items():
        for field in ('entityIds', 'childRegionIds', 'targetRegionIds'):
            raw_items = region.get(field)
            if not isinstance(raw_items, list):
                problems.append(
                    f'{view["id"]}.composition.regions[{region_id}].{field} 必须是数组'
                )
                items = []
            else:
                items = [
                    item for item in raw_items
                    if isinstance(item, str) and item.strip()
                ]
                if len(items) != len(raw_items):
                    problems.append(
                        f'{view["id"]}.composition.regions[{region_id}].{field} '
                        '只能包含非空 id'
                    )
                duplicates = sorted({
                    item for item in items if items.count(item) > 1
                })
                if duplicates:
                    problems.append(
                        f'{view["id"]}.composition.regions[{region_id}].{field} '
                        '不得重复: ' + ', '.join(duplicates)
                    )
            region_lists[(region_id, field)] = items

    for region_id, region in region_index.items():
        primitive = region.get('primitive')
        if primitive not in allowed_primitives:
            problems.append(f'{view["id"]}.composition.regions[{region_id}].primitive 非法: {primitive}')
        if region.get('role') not in {'main', 'support', 'crosscut', 'inset', 'context'}:
            problems.append(
                f'{view["id"]}.composition.regions[{region_id}].role 非法: '
                f'{region.get("role")}'
            )
        if region.get('axis') not in {'horizontal', 'vertical', 'none'}:
            problems.append(
                f'{view["id"]}.composition.regions[{region_id}].axis 非法: '
                f'{region.get("axis")}'
            )
        parent_id = region.get('parentId')
        if parent_id and parent_id not in region_index:
            problems.append(f'{view["id"]}.composition.regions[{region_id}].parentId 不存在: {parent_id}')
        for child_id in region_lists[(region_id, 'childRegionIds')]:
            if child_id not in region_index:
                problems.append(f'{view["id"]}.composition.regions[{region_id}].childRegionIds 不存在: {child_id}')
            elif region_index[child_id].get('parentId') != region_id:
                problems.append(f'{view["id"]}.composition.regions[{region_id}] 与 childRegionIds[{child_id}] 不一致')
        if (
            parent_id in region_index
            and region_id not in region_lists.get((parent_id, 'childRegionIds'), [])
        ):
            problems.append(
                f'{view["id"]}.composition.regions[{region_id}] parentId '
                '与父 region.childRegionIds 不一致'
            )
        direct_entity_ids = [
            entity_id
            for entity_id in [
                region.get('ownerEntityId'),
                *region_lists[(region_id, 'entityIds')],
            ]
            if entity_id
        ]
        if primitive == 'stack':
            invalid_stack_entities = [
                entity_id
                for entity_id in direct_entity_ids
                if entity_index.get(entity_id, {}).get('multiplicity') != 'many'
            ]
            if not direct_entity_ids or invalid_stack_entities:
                problems.append(
                    f'{view["id"]}.composition.regions[{region_id}] stack '
                    '只能承载 multiplicity=many 的实体'
                )
        if primitive == 'crosscut':
            targets = region_lists[(region_id, 'targetRegionIds')]
            if not targets:
                problems.append(
                    f'{view["id"]}.composition.regions[{region_id}] crosscut '
                    '必须声明 targetRegionIds'
                )
            for target_id in targets:
                if target_id not in region_index:
                    problems.append(
                        f'{view["id"]}.composition.regions[{region_id}] crosscut '
                        f'targetRegionIds 不存在: {target_id}'
                    )
        if primitive == 'inset' and not parent_id:
            problems.append(
                f'{view["id"]}.composition.regions[{region_id}] inset 必须有 parentId'
            )
        if primitive == 'sequence' and view.get('diagramKind') != 'flow':
            if region.get('role') != 'inset' or not has_dynamic_relation:
                problems.append(
                    f'{view["id"]}.composition.regions[{region_id}] sequence '
                    '只允许用于 flow 主图或含动态关系的 inset'
                )

    reachable = set()
    if root_id in region_index:
        stack = [root_id]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(children.get(current, []))
    missing = sorted(set(region_index) - reachable)
    if missing:
        problems.append(f'{view["id"]}.composition 存在不可达 region: {", ".join(missing)}')

    entity_regions = defaultdict(list)
    for region_id, region in region_index.items():
        owner = region.get('ownerEntityId')
        if owner:
            entity_regions[owner].append(region_id)
        for entity_id in region_lists[(region_id, 'entityIds')]:
            entity_regions[entity_id].append(region_id)

    reading_path = composition.get('readingPath')
    if not isinstance(reading_path, dict):
        problems.append(f'{view["id"]}.composition.readingPath 必须是对象')
    else:
        _reject_unknown_fields(
            problems,
            reading_path,
            READING_PATH_FIELDS,
            f'{view["id"]}.composition.readingPath',
        )
        if reading_path.get('kind') not in {'left-right', 'top-down', 'center-out', 'cyclic', 'scan'}:
            problems.append(
                f'{view["id"]}.composition.readingPath.kind 非法: '
                f'{reading_path.get("kind")}'
            )
        sequence = reading_path.get('sequence')
        if not isinstance(sequence, list):
            problems.append(f'{view["id"]}.composition.readingPath.sequence 必须是数组')
        else:
            valid_sequence = [
                item for item in sequence
                if isinstance(item, str) and item.strip()
            ]
            if len(valid_sequence) != len(sequence):
                problems.append(
                    f'{view["id"]}.composition.readingPath.sequence '
                    '只能包含非空 entity id'
                )
            duplicate_sequence = sorted({
                item for item in valid_sequence
                if valid_sequence.count(item) > 1
            })
            if duplicate_sequence:
                problems.append(
                    f'{view["id"]}.composition.readingPath.sequence '
                    '不得重复实体: ' + ', '.join(duplicate_sequence)
                )
            unknown_sequence = sorted(set(valid_sequence) - set(entity_regions))
            if unknown_sequence:
                problems.append(
                    f'{view["id"]}.composition.readingPath.sequence 引用不存在实体: '
                    + ', '.join(unknown_sequence)
                )

    focal_ids = composition.get('focalIds')
    if not isinstance(focal_ids, list) or not focal_ids:
        problems.append(f'{view["id"]}.composition.focalIds 必须是非空数组')
    else:
        valid_focal_ids = [
            item for item in focal_ids
            if isinstance(item, str) and item.strip()
        ]
        if len(valid_focal_ids) != len(focal_ids):
            problems.append(
                f'{view["id"]}.composition.focalIds 只能包含非空 id'
            )
        duplicate_focal_ids = sorted({
            item for item in valid_focal_ids
            if valid_focal_ids.count(item) > 1
        })
        if duplicate_focal_ids:
            problems.append(
                f'{view["id"]}.composition.focalIds 不得重复: '
                + ', '.join(duplicate_focal_ids)
            )
        known_focal_ids = {
            *entity_regions.keys(),
            *(fact.get('id') for fact in view.get('facts', []) if fact.get('id')),
        }
        missing_focal_ids = sorted(set(valid_focal_ids) - known_focal_ids)
        if missing_focal_ids:
            problems.append(
                f'{view["id"]}.composition.focalIds 引用不存在对象: '
                + ', '.join(missing_focal_ids)
            )

    for entity in view.get('entities', []):
        entity_id = entity.get('id')
        if not entity_id:
            problems.append(f'{view["id"]}.entities 缺少 id')
            continue
        placements = entity_regions.get(entity_id, [])
        if not placements:
            problems.append(f'{view["id"]}.entities[{entity_id}] 没有 region 归属')
        elif len(placements) > 1:
            problems.append(f'{view["id"]}.entities[{entity_id}] 重复出现在多个 region: {", ".join(placements)}')

    ancestors = {}
    for region_id in region_index:
        chain = []
        current = region_id
        seen = set()
        while current and current not in seen:
            seen.add(current)
            chain.append(current)
            current = region_index[current].get('parentId')
        ancestors[region_id] = chain
    return region_index, entity_regions, ancestors


def _validate_relations(view, entity_regions, ancestors, problems):
    entities = {entity['id'] for entity in view.get('entities', []) if entity.get('id')}
    relations = view.get('relations', [])
    relation_ids = set()
    for index, relation in enumerate(relations, 1):
        if not isinstance(relation, dict):
            problems.append(f'{view["id"]}.relations[{index}] 必须是对象')
            continue
        _reject_unknown_fields(
            problems,
            relation,
            RELATION_FIELDS,
            f'{view["id"]}.relations[{index}]',
        )
        rel_id = relation.get('id') or f'<relation-{index}>'
        _require_str(problems, relation.get('id'), f'{view["id"]}.relations[{index}].id')
        if relation.get('id'):
            if rel_id in relation_ids:
                problems.append(f'{view["id"]}.relations 重复 id: {rel_id}')
            relation_ids.add(rel_id)
        subject = relation.get('subjectId')
        obj = relation.get('objectId')
        kind = relation.get('kind')
        _require_str(problems, subject, f'{view["id"]}.relations[{rel_id}].subjectId')
        _require_str(problems, obj, f'{view["id"]}.relations[{rel_id}].objectId')
        _require_str(problems, kind, f'{view["id"]}.relations[{rel_id}].kind')
        _require_str(problems, relation.get('emphasis'), f'{view["id"]}.relations[{rel_id}].emphasis')
        _require_block_refs(
            problems,
            relation.get('sourceBlockIds'),
            f'{view["id"]}.relations[{rel_id}].sourceBlockIds',
        )
        if subject and subject not in entities:
            problems.append(f'{view["id"]}.relations[{rel_id}].subjectId 不存在: {subject}')
        if obj and obj not in entities:
            problems.append(f'{view["id"]}.relations[{rel_id}].objectId 不存在: {obj}')
        if kind and kind not in ALLOWED_RELATION_KINDS:
            problems.append(
                f'{view["id"]}.relation {rel_id}.kind 非法: {kind}'
            )
        if relation.get('emphasis') not in {'primary', 'secondary', 'context'}:
            problems.append(
                f'{view["id"]}.relations[{rel_id}].emphasis 非法: '
                f'{relation.get("emphasis")}'
            )
        if kind in STRUCTURAL_RELATIONS:
            subject_regions = entity_regions.get(subject, [])
            object_regions = entity_regions.get(obj, [])
            # contains: parent -> child; partOf/layerOf/instanceOf: child -> parent.
            parent_regions, child_regions = (
                (subject_regions, object_regions)
                if kind == 'contains'
                else (object_regions, subject_regions)
            )
            spatially_proven = False
            if parent_regions and child_regions:
                parent_region = parent_regions[0]
                child_region = child_regions[0]
                spatially_proven = (
                    parent_region != child_region
                    and parent_region in ancestors.get(child_region, [])
                )
            if not spatially_proven:
                problems.append(
                    f'{view["id"]}.relations[{rel_id}] {kind} 关系必须通过 region 嵌套表达'
                )


def _validate_facts(view, entities, problems):
    entity_ids = {entity['id'] for entity in entities if entity.get('id')}
    relation_ids = {
        relation.get('id')
        for relation in view.get('relations', [])
        if isinstance(relation, dict) and relation.get('id')
    }
    region_ids = {
        region.get('id')
        for region in (view.get('composition') or {}).get('regions', [])
        if isinstance(region, dict) and region.get('id')
    }
    fact_ids = set()
    for index, fact in enumerate(view.get('facts', []), 1):
        if not isinstance(fact, dict):
            problems.append(f'{view["id"]}.facts[{index}] 必须是对象')
            continue
        _reject_unknown_fields(
            problems,
            fact,
            FACT_FIELDS,
            f'{view["id"]}.facts[{index}]',
        )
        _require_str(problems, fact.get('id'), f'{view["id"]}.facts[{index}].id')
        if fact.get('id'):
            if fact['id'] in fact_ids:
                problems.append(f'{view["id"]}.facts 重复 id: {fact["id"]}')
            fact_ids.add(fact['id'])
        _require_str(problems, fact.get('kind'), f'{view["id"]}.facts[{index}].kind')
        _require_str(problems, fact.get('label'), f'{view["id"]}.facts[{index}].label')
        _require_block_refs(problems, fact.get('sourceBlockIds'), f'{view["id"]}.facts[{index}].sourceBlockIds')
        fact_id = fact.get('id') or index
        if fact.get('kind') and fact.get('kind') not in ALLOWED_FACT_KINDS:
            problems.append(
                f'{view["id"]}.facts[{fact_id}].kind 非法: {fact.get("kind")}'
            )
        scope = fact.get('scope')
        if not isinstance(scope, dict):
            problems.append(f'{view["id"]}.facts[{fact_id}].scope 必须是对象')
        else:
            _reject_unknown_fields(
                problems,
                scope,
                SCOPE_FIELDS,
                f'{view["id"]}.facts[{fact_id}].scope',
            )
            scope_kind = scope.get('kind')
            targets = scope.get('targetIds')
            allowed_scope_kinds = {'entity', 'relation', 'region', 'view'}
            if scope_kind not in allowed_scope_kinds:
                problems.append(
                    f'{view["id"]}.facts[{fact_id}].scope.kind 非法: {scope_kind}'
                )
            if not isinstance(targets, list) or not targets:
                problems.append(
                    f'{view["id"]}.facts[{fact_id}].scope.targetIds 必须是非空数组'
                )
                targets = []
            elif len(targets) != 1:
                problems.append(
                    f'{view["id"]}.facts[{fact_id}].scope.targetIds '
                    '必须恰有一个目标；共享事实应挂到共同 region 或 view'
                )
            valid_targets = {
                'entity': entity_ids,
                'relation': relation_ids,
                'region': region_ids,
                'view': {view['id']},
            }.get(scope_kind, set())
            missing_targets = sorted(set(targets) - valid_targets)
            if missing_targets:
                problems.append(
                    f'{view["id"]}.facts[{fact_id}] scope target 不存在: '
                    + ', '.join(missing_targets)
                )
        has_scalar = 'value' in fact
        values = fact.get('values')
        if has_scalar == (values is not None):
            problems.append(
                f'{view["id"]}.facts[{fact_id}] 必须且只能声明 value 或 values'
            )
        if values is not None:
            if not isinstance(values, list) or not values:
                problems.append(f'{view["id"]}.facts[{index}].values 必须是非空数组')
            else:
                seen_targets = set()
                for value_index, item in enumerate(values, 1):
                    if not isinstance(item, dict):
                        problems.append(f'{view["id"]}.facts[{index}].values[{value_index}] 必须是对象')
                        continue
                    _reject_unknown_fields(
                        problems,
                        item,
                        COMPARISON_VALUE_FIELDS,
                        f'{view["id"]}.facts[{fact_id}].values[{value_index}]',
                    )
                    target_id = item.get('targetId')
                    _require_str(problems, target_id, f'{view["id"]}.facts[{index}].values[{value_index}].targetId')
                    _require_str(problems, item.get('value'), f'{view["id"]}.facts[{index}].values[{value_index}].value')
                    if target_id:
                        if target_id not in entity_ids:
                            problems.append(f'{view["id"]}.facts[{index}].values[{value_index}].targetId 不存在: {target_id}')
                        elif target_id in seen_targets:
                            problems.append(f'{view["id"]}.facts[{index}].values[{value_index}].targetId 重复: {target_id}')
                        seen_targets.add(target_id)


def _validate_flow(view, problems):
    view_id = view['id']
    dynamic_relations = [
        relation
        for relation in view.get('relations', [])
        if relation.get('kind') in DYNAMIC_RELATIONS
    ]
    if not dynamic_relations:
        problems.append(f'{view_id}.flow 至少需要一条动态关系')

    has_terminal = any(
        entity.get('stateKind') in {'terminal', 'persistent'}
        for entity in view.get('entities', [])
    )
    reading_path = (view.get('composition') or {}).get('readingPath') or {}
    sequence = reading_path.get('sequence') or []
    if not sequence:
        problems.append(f'{view_id}.flow readingPath.sequence 必须声明非空主路径')
    dynamic_pairs = {
        (relation.get('subjectId'), relation.get('objectId'))
        for relation in dynamic_relations
    }
    for subject, obj in zip(sequence, sequence[1:]):
        if (subject, obj) not in dynamic_pairs:
            problems.append(
                f'{view_id}.flow readingPath {subject} -> {obj} 缺少动态关系'
            )

    if sequence:
        adjacency = defaultdict(set)
        for relation in dynamic_relations:
            adjacency[relation.get('subjectId')].add(relation.get('objectId'))
        reachable = set()
        pending = [sequence[0]]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(adjacency.get(current, set()) - reachable)
        entity_ids = {
            entity.get('id')
            for entity in view.get('entities', [])
            if entity.get('id')
        }
        unreachable = sorted(entity_ids - reachable)
        if unreachable:
            problems.append(
                f'{view_id}.flow 存在从 readingPath 起点不可达的实体: '
                + ', '.join(unreachable)
            )
    has_closed_cycle = (
        reading_path.get('kind') == 'cyclic'
        and len(sequence) >= 2
        and any(
            relation.get('subjectId') == sequence[-1]
            and relation.get('objectId') == sequence[0]
            for relation in dynamic_relations
        )
    )
    if not has_terminal and not has_closed_cycle:
        problems.append(f'{view_id}.flow 必须显式声明 terminal 或闭合循环')


def _validate_matrix(view, problems):
    view_id = view['id']
    non_option_ids = sorted({
        entity.get('id')
        for entity in view.get('entities', [])
        if entity.get('id') and entity.get('type') != 'option'
    })
    if non_option_ids:
        problems.append(
            f'{view_id}.matrix 只接受 option entity: '
            + ', '.join(non_option_ids)
        )
    option_ids = {
        entity.get('id')
        for entity in view.get('entities', [])
        if entity.get('type') == 'option' and entity.get('id')
    }
    if len(option_ids) < 2:
        problems.append(f'{view_id}.matrix 至少需要两个 option entity')
    comparison_facts = [
        fact for fact in view.get('facts', [])
        if isinstance(fact.get('values'), list)
    ]
    if not comparison_facts:
        problems.append(f'{view_id}.matrix 至少需要一个共同维度比较 fact')
    for fact in comparison_facts:
        scope = fact.get('scope') or {}
        if (
            scope.get('kind') != 'view'
            or scope.get('targetIds') != [view_id]
        ):
            problems.append(
                f'{view_id}.matrix 比较 fact {fact.get("id", "?")} '
                '必须 scope 到当前 view'
            )
        covered = {
            item.get('targetId')
            for item in fact.get('values', [])
            if isinstance(item, dict) and item.get('targetId')
        }
        missing = sorted(option_ids - covered)
        extra = sorted(covered - option_ids)
        if missing:
            problems.append(
                f'{view_id}.matrix 比较 fact {fact.get("id", "?")} '
                f'未覆盖 option: {", ".join(missing)}'
            )
        if extra:
            problems.append(
                f'{view_id}.matrix 比较 fact {fact.get("id", "?")} '
                f'引用非 option: {", ".join(extra)}'
            )


def _validate_argument(view, problems):
    view_id = view['id']
    claim_ids = {
        entity.get('id')
        for entity in view.get('entities', [])
        if entity.get('type') == 'claim' and entity.get('id')
    }
    evidence_ids = {
        entity.get('id')
        for entity in view.get('entities', [])
        if entity.get('type') in {'evidence', 'counterevidence'} and entity.get('id')
    }
    if not claim_ids or not evidence_ids:
        problems.append(f'{view_id}.argument 必须同时包含 claim 与 evidence/counterevidence')
    argument_relations = [
        relation
        for relation in view.get('relations', [])
        if relation.get('kind') in ARGUMENT_RELATIONS
    ]
    if not argument_relations:
        problems.append(f'{view_id}.argument 至少需要一条论证关系')
    for relation in argument_relations:
        relation_id = relation.get('id', '?')
        subject = relation.get('subjectId')
        obj = relation.get('objectId')
        kind = relation.get('kind')
        if kind in {'supportsClaim', 'contradicts'}:
            valid = subject in evidence_ids and obj in claim_ids
        else:
            valid = (
                (subject in evidence_ids and obj in claim_ids)
                or (subject in claim_ids and obj in evidence_ids)
            )
        if not valid:
            problems.append(
                f'{view_id}.argument relation {relation_id} 必须指向 claim '
                '并连接 evidence/counterevidence'
            )

    composition = view.get('composition') or {}
    main_sequences = [
        region.get('id', '?')
        for region in composition.get('regions', [])
        if region.get('role') == 'main' and region.get('primitive') == 'sequence'
    ]
    if main_sequences:
        problems.append(
            f'{view_id}.argument 论证关系不得编码为执行顺序: '
            + ', '.join(main_sequences)
        )
    focal_ids = set(composition.get('focalIds') or [])
    if claim_ids and not (claim_ids & focal_ids):
        problems.append(f'{view_id}.argument 中心 claim 必须为 focalIds 焦点')


def _validate_view(view, problems):
    view_id = view.get('id') or '<unknown-view>'
    _reject_unknown_fields(problems, view, VIEW_FIELDS, view_id)
    _require_str(problems, view.get('id'), 'view.id')
    _require_str(problems, view.get('title'), f'{view_id}.title')
    _require_str(problems, view.get('question'), f'{view_id}.question')
    _require_str(problems, view.get('narrativeRole'), f'{view_id}.narrativeRole')
    _require_str(problems, view.get('diagramKind'), f'{view_id}.diagramKind')
    _require_str(problems, view.get('diagramRationale'), f'{view_id}.diagramRationale')

    claim = view.get('centralClaim')
    if not isinstance(claim, dict):
        problems.append(f'{view_id}.centralClaim 必须是对象')
    else:
        _reject_unknown_fields(
            problems,
            claim,
            CLAIM_FIELDS,
            f'{view_id}.centralClaim',
        )
        _require_str(problems, claim.get('text'), f'{view_id}.centralClaim.text')
        _require_block_refs(problems, claim.get('sourceBlockIds'), f'{view_id}.centralClaim.sourceBlockIds')

    kind = view.get('diagramKind')
    if kind not in ALLOWED_DIAGRAM_KINDS:
        problems.append(f'{view_id}.diagramKind unsupported_diagram_kind: {kind}')

    raw_entities = view.get('entities', [])
    if not isinstance(raw_entities, list):
        problems.append(f'{view_id}.entities 必须是数组')
        raw_entities = []
    else:
        seen_entities = set()
        for index, entity in enumerate(raw_entities, 1):
            if not isinstance(entity, dict):
                problems.append(f'{view_id}.entities[{index}] 必须是对象')
                continue
            entity_id = entity.get('id')
            _require_str(problems, entity_id, f'{view_id}.entities[{index}].id')
            if entity_id:
                if entity_id in seen_entities:
                    problems.append(f'{view_id}.entities 重复 id: {entity_id}')
                seen_entities.add(entity_id)
            _require_str(problems, entity.get('label'), f'{view_id}.entities[{index}].label')
            _require_str(problems, entity.get('detail'), f'{view_id}.entities[{index}].detail')
            _require_str(problems, entity.get('type'), f'{view_id}.entities[{index}].type')
            _require_str(problems, entity.get('emphasis'), f'{view_id}.entities[{index}].emphasis')
            _require_str(problems, entity.get('multiplicity'), f'{view_id}.entities[{index}].multiplicity')
            _require_block_refs(problems, entity.get('sourceBlockIds'), f'{view_id}.entities[{index}].sourceBlockIds')
            unknown_fields = sorted(set(entity) - ENTITY_FIELDS)
            if unknown_fields:
                problems.append(
                    f'{view_id}.entities[{entity_id or index}] 未知字段: '
                    + ', '.join(unknown_fields)
                )
            if entity.get('emphasis') not in {'primary', 'secondary', 'context'}:
                problems.append(
                    f'{view_id}.entities[{entity_id or index}].emphasis 非法: '
                    f'{entity.get("emphasis")}'
                )
            if entity.get('multiplicity') not in {'one', 'many', 'optional'}:
                problems.append(
                    f'{view_id}.entities[{entity_id or index}].multiplicity 非法: '
                    f'{entity.get("multiplicity")}'
                )
            if entity.get('boundary') not in {None, 'internal', 'external'}:
                problems.append(
                    f'{view_id}.entities[{entity_id or index}].boundary 非法: '
                    f'{entity.get("boundary")}'
                )
            if entity.get('stateKind') not in {None, *ALLOWED_STATE_KINDS}:
                problems.append(
                    f'{view_id}.entities[{entity_id or index}].stateKind 非法: '
                    f'{entity.get("stateKind")}'
                )

    raw_relations = view.get('relations', [])
    if not isinstance(raw_relations, list):
        problems.append(f'{view_id}.relations 必须是数组')
        raw_relations = []
    else:
        for index, relation in enumerate(raw_relations, 1):
            if not isinstance(relation, dict):
                problems.append(f'{view_id}.relations[{index}] 必须是对象')

    raw_facts = view.get('facts', [])
    if not isinstance(raw_facts, list):
        problems.append(f'{view_id}.facts 必须是数组')
        raw_facts = []
    else:
        for index, fact in enumerate(raw_facts, 1):
            if not isinstance(fact, dict):
                problems.append(f'{view_id}.facts[{index}] 必须是对象')

    composition = view.get('composition')
    if not isinstance(composition, dict):
        problems.append(f'{view_id}.composition 必须是对象')
        composition = {}

    # All downstream validators operate on a non-mutating, type-safe view.
    # Shape errors above remain contract errors instead of leaking AttributeError.
    safe_view = dict(view)
    safe_view['entities'] = [item for item in raw_entities if isinstance(item, dict)]
    safe_view['relations'] = [item for item in raw_relations if isinstance(item, dict)]
    safe_view['facts'] = [item for item in raw_facts if isinstance(item, dict)]
    safe_view['composition'] = composition
    entities = safe_view['entities']

    primary_entities = [
        entity.get('id')
        for entity in entities
        if isinstance(entity, dict) and entity.get('emphasis') == 'primary'
    ]
    if len(primary_entities) != 1:
        problems.append(
            f'{view_id}.entities 必须恰有一个 emphasis=primary，'
            f'实际 {len(primary_entities)}'
        )

    region_index, entity_regions, ancestors = _validate_region_tree(safe_view, problems)
    _validate_relations(safe_view, entity_regions, ancestors, problems)
    _validate_facts(safe_view, entities, problems)

    if kind == 'architecture':
        if not region_index:
            problems.append(f'{view_id}.composition 必须提供 region tree')
        has_architecture_relation = any(
            rel.get('kind') in STRUCTURAL_RELATIONS | DEPENDENCY_RELATIONS
            for rel in safe_view.get('relations', [])
            if isinstance(rel, dict)
        )
        has_semantic_region_owner = any(
            region.get('ownerEntityId')
            for region in (safe_view.get('composition') or {}).get('regions', [])
            if isinstance(region, dict)
        )
        if not has_architecture_relation and not has_semantic_region_owner:
            problems.append(
                f'{view_id}.architecture 至少需要结构/依赖关系或有语义 owner 的 region'
            )
        incompatible_primary = [
            relation.get('kind')
            for relation in safe_view.get('relations', [])
            if isinstance(relation, dict)
            and relation.get('emphasis') == 'primary'
            and relation.get('kind') not in (
                STRUCTURAL_RELATIONS
                | DEPENDENCY_RELATIONS
                | CONNECTION_RELATIONS
                | OBSERVATION_RELATIONS
            )
        ]
        if incompatible_primary:
            problems.append(
                f'{view_id}.architecture primary relation 不兼容: '
                + ', '.join(str(item) for item in incompatible_primary)
            )
        incompatible_relations = [
            relation.get('kind')
            for relation in safe_view.get('relations', [])
            if isinstance(relation, dict)
            and relation.get('kind') in ARGUMENT_RELATIONS
        ]
        if incompatible_relations:
            problems.append(
                f'{view_id}.architecture relation 不兼容: '
                + ', '.join(str(item) for item in incompatible_relations)
            )
    elif kind == 'flow':
        _validate_flow(safe_view, problems)
        incompatible_relations = [
            relation.get('kind')
            for relation in safe_view.get('relations', [])
            if isinstance(relation, dict)
            and relation.get('kind') not in DYNAMIC_RELATIONS
        ]
        if incompatible_relations:
            problems.append(
                f'{view_id}.flow relation 不兼容: '
                + ', '.join(str(item) for item in incompatible_relations)
            )
    elif kind == 'matrix':
        _validate_matrix(safe_view, problems)
        if safe_view.get('relations'):
            problems.append(
                f'{view_id}.matrix 不接受 relation；共同维度必须编码为 fact.values'
            )
    elif kind == 'argument':
        _validate_argument(safe_view, problems)
        incompatible_relations = [
            relation.get('kind')
            for relation in safe_view.get('relations', [])
            if isinstance(relation, dict)
            and relation.get('kind') not in ARGUMENT_RELATIONS
        ]
        if incompatible_relations:
            problems.append(
                f'{view_id}.argument relation 不兼容: '
                + ', '.join(str(item) for item in incompatible_relations)
            )


def validate_v3_spec(blocks, spec):
    """Reject incomplete v3 intent before any renderer is invoked."""
    problems = []
    if not isinstance(spec, dict):
        raise ValueError('view-spec.json v3 合同失败:\n- 根节点必须是对象')
    _reject_unknown_fields(problems, spec, SPEC_FIELDS, 'view-spec')
    if spec.get('schemaVersion') != 3:
        problems.append('schemaVersion 必须为 3')

    raw_views = spec.get('views')
    if not isinstance(raw_views, list) or not raw_views:
        problems.append('views 必须是非空数组')
        views = []
    else:
        views = raw_views

    view_ids = {
        view.get('id')
        for view in views
        if isinstance(view, dict) and view.get('id')
    }
    _validate_page(spec, view_ids, problems)

    seen_ids = set()
    for view in views:
        if not isinstance(view, dict):
            problems.append('views 中每个视图都必须是对象')
            continue
        view_id = view.get('id')
        if not str(view_id or '').strip():
            problems.append('view.id 不能为空')
            continue
        if view_id in seen_ids:
            problems.append(f'views 重复 id: {view_id}')
        seen_ids.add(view_id)
        _validate_view(view, problems)

    safe_spec = dict(spec)
    safe_spec['views'] = views
    safe_spec['page'] = spec.get('page') if isinstance(spec.get('page'), dict) else {}
    _validate_sources(blocks, safe_spec, problems)

    if problems:
        raise ValueError('view-spec.json v3 合同失败:\n- ' + '\n- '.join(problems))
    validate_semantic_model(blocks, spec)


__all__ = [
    'ARGUMENT_RELATIONS',
    'ALLOWED_RELATION_KINDS',
    'CONNECTION_RELATIONS',
    'DEPENDENCY_RELATIONS',
    'DYNAMIC_RELATIONS',
    'OBSERVATION_RELATIONS',
    'STRUCTURAL_RELATIONS',
    'validate_v3_spec',
]
