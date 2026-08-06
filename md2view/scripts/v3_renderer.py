#!/usr/bin/env python3
"""Deterministic HTML renderers for md2view v3 diagram families."""
from html import escape

from v3_contract import DYNAMIC_RELATIONS


def _attr(value):
    return escape(str(value), quote=True)


def _source_attr(item):
    return ' '.join(str(block_id) for block_id in item.get('sourceBlockIds', []))


def _source_unit_attr(item):
    return (
        f' data-source-unit="{_attr(item["sourceUnitId"])}"'
        if item.get('sourceUnitId') else ''
    )


def _render_entity(entity, *, owner=False):
    classes = ['mv-entity']
    if owner:
        classes.append('mv-region-owner')
    emphasis = entity.get('emphasis', 'secondary')
    optional_attrs = ''.join(
        f' data-{name}="{_attr(entity[field])}"'
        for name, field in (
            ('boundary', 'boundary'),
            ('multiplicity', 'multiplicity'),
            ('state-kind', 'stateKind'),
        )
        if entity.get(field) is not None
    )
    return (
        f'<article class="{" ".join(classes)}" '
        f'data-entity-id="{_attr(entity["id"])}" '
        f'data-entity-type="{_attr(entity.get("type", "entity"))}" '
        f'data-emphasis="{_attr(emphasis)}"{optional_attrs} '
        f'data-source-blocks="{_attr(_source_attr(entity))}">'
        f'<h3>{escape(str(entity.get("label", "")))}</h3>'
        f'<p>{escape(str(entity.get("detail", "")))}</p>'
        '</article>'
    )


def _render_fact(fact):
    scope = fact.get('scope') or {}
    targets = ' '.join(str(target) for target in scope.get('targetIds', []))
    source_unit_attr = _source_unit_attr(fact)
    if 'value' in fact:
        value_html = f'<span>{escape(str(fact.get("value", "")))}</span>'
    else:
        value_html = ''.join(
            '<span class="mv-fact-comparison" '
            f'data-target-id="{_attr(item.get("targetId", ""))}">'
            f'{escape(str(item.get("value", "")))}</span>'
            for item in fact.get('values', [])
        )
    return (
        '<aside class="mv-fact" '
        f'data-fact-id="{_attr(fact["id"])}" '
        f'data-fact-kind="{_attr(fact.get("kind", "evidence"))}" '
        f'data-scope-kind="{_attr(scope.get("kind", "view"))}" '
        f'data-target-ids="{_attr(targets)}" '
        f'data-source-blocks="{_attr(_source_attr(fact))}"{source_unit_attr}>'
        f'<strong>{escape(str(fact.get("label", "")))}</strong>'
        f'{value_html}</aside>'
    )


def _render_region(region_id, regions, entities, facts_by_entity, facts_by_region):
    region = regions[region_id]
    owner_id = region.get('ownerEntityId')
    owner_attr = (
        f' data-owner-entity-id="{_attr(owner_id)}"'
        if owner_id else ''
    )
    target_attr = ' '.join(str(target) for target in region.get('targetRegionIds', []))
    has_secondary_content = bool(
        region.get('entityIds')
        or region.get('childRegionIds')
        or facts_by_region.get(region_id)
        or (owner_id and facts_by_entity.get(owner_id))
    )
    region_columns = max(
        1,
        len(region.get('entityIds', [])) + len(region.get('childRegionIds', [])),
    )
    contents = []
    if owner_id:
        contents.append(_render_entity(entities[owner_id], owner=True))
        contents.extend(_render_fact(fact) for fact in facts_by_entity.get(owner_id, []))
    if region.get('primitive') == 'crosscut':
        target_labels = []
        for target_region_id in region.get('targetRegionIds', []):
            target_region = regions.get(target_region_id, {})
            target_owner_id = target_region.get('ownerEntityId')
            target_labels.append(
                entities.get(target_owner_id, {}).get('label') or target_region_id
            )
        contents.append(
            '<p class="mv-crosscut-targets">'
            '<strong>作用于</strong> '
            + escape(' · '.join(str(label) for label in target_labels))
            + '</p>'
        )
    for entity_id in region.get('entityIds', []):
        contents.append(_render_entity(entities[entity_id]))
        contents.extend(_render_fact(fact) for fact in facts_by_entity.get(entity_id, []))
    contents.extend(_render_fact(fact) for fact in facts_by_region.get(region_id, []))
    contents.extend(
        _render_region(
            child_id,
            regions,
            entities,
            facts_by_entity,
            facts_by_region,
        )
        for child_id in region.get('childRegionIds', [])
    )
    return (
        f'<div class="mv-region mv-region--{_attr(region["primitive"])}" '
        f'data-region-id="{_attr(region_id)}" '
        f'data-primitive="{_attr(region["primitive"])}" '
        f'data-role="{_attr(region.get("role", "main"))}" '
        f'data-axis="{_attr(region.get("axis", "none"))}" '
        f'data-region-columns="{region_columns}" '
        f'data-has-content="{str(has_secondary_content).lower()}" '
        f'data-target-region-ids="{_attr(target_attr)}" '
        f'style="--mv-region-columns:{region_columns}"{owner_attr}>'
        + ''.join(contents)
        + '</div>'
    )


def _render_architecture(view):
    entities = {entity['id']: entity for entity in view.get('entities', [])}
    regions = {
        region['id']: region
        for region in view.get('composition', {}).get('regions', [])
    }
    root_id = view['composition']['rootRegionId']
    facts_by_entity = {}
    facts_by_region = {}
    facts_by_relation = {}
    view_facts = []
    for fact in view.get('facts', []):
        scope = fact.get('scope') or {}
        targets = scope.get('targetIds', [])
        if scope.get('kind') == 'entity':
            for target in targets:
                facts_by_entity.setdefault(target, []).append(fact)
        elif scope.get('kind') == 'region':
            for target in targets:
                facts_by_region.setdefault(target, []).append(fact)
        elif scope.get('kind') == 'relation':
            for target in targets:
                facts_by_relation.setdefault(target, []).append(fact)
        else:
            view_facts.append(fact)
    structural_kinds = {'contains', 'partOf', 'layerOf', 'instanceOf'}
    for relation in view.get('relations', []):
        if relation.get('kind') not in structural_kinds:
            continue
        relation_facts = facts_by_relation.get(relation.get('id'), [])
        if relation_facts:
            facts_by_entity.setdefault(relation['objectId'], []).extend(relation_facts)
    visual_by_kind = {
        'dependsOn': 'adjacency',
        'enables': 'adjacency',
        'constrains': 'adjacency',
        'provides': 'adjacency',
        'connectsTo': 'port',
        'exchangesWith': 'port',
        'peersWith': 'port',
        'observes': 'crosscut',
        'reports': 'crosscut',
        'alerts': 'crosscut',
        'calls': 'local-connector',
        'triggers': 'local-connector',
        'produces': 'local-connector',
        'transitionsTo': 'local-connector',
        'returns': 'local-connector',
    }
    structural_markers = ''.join(
        '<span class="mv-relation" '
        f'data-relation-id="{_attr(relation["id"])}" '
        f'data-subject="{_attr(relation["subjectId"])}" '
        f'data-object="{_attr(relation["objectId"])}" '
        f'data-kind="{_attr(relation["kind"])}" '
        f'data-source-blocks="{_attr(_source_attr(relation))}"'
        f'{_source_unit_attr(relation)} '
        'data-visual="containment" hidden>'
        f'{escape(str(entities[relation["subjectId"]].get("label", "")))} '
        f'{escape(str(relation.get("label") or relation["kind"]))} '
        f'{escape(str(entities[relation["objectId"]].get("label", "")))}'
        '</span>'
        for relation in view.get('relations', [])
        if relation.get('kind') in structural_kinds
    )
    visible_relations = []
    for relation in view.get('relations', []):
        if relation.get('kind') in structural_kinds:
            continue
        visual = visual_by_kind.get(relation.get('kind'), 'adjacency')
        subject = entities[relation['subjectId']]
        obj = entities[relation['objectId']]
        label = relation.get('label') or relation['kind']
        arrow = '<span aria-hidden="true">→</span>' if visual == 'local-connector' else '<span aria-hidden="true">—</span>'
        attached_facts = ''.join(
            _render_fact(fact)
            for fact in facts_by_relation.get(relation['id'], [])
        )
        visible_relations.append(
            '<li class="mv-architecture-relation" '
            f'data-relation-id="{_attr(relation["id"])}" '
            f'data-subject="{_attr(relation["subjectId"])}" '
            f'data-object="{_attr(relation["objectId"])}" '
            f'data-kind="{_attr(relation["kind"])}" '
            f'data-visual="{_attr(visual)}" '
            f'data-source-blocks="{_attr(_source_attr(relation))}"'
            f'{_source_unit_attr(relation)}>'
            f'<strong>{escape(str(subject.get("label", "")))}</strong>{arrow}'
            f'<em>{escape(str(label))}</em>{arrow}'
            f'<strong>{escape(str(obj.get("label", "")))}</strong>'
            f'{attached_facts}</li>'
        )
    relation_index = ''
    if visible_relations:
        relation_index = (
            '<ul class="mv-architecture-relations" aria-label="架构关系">'
            + ''.join(visible_relations)
            + '</ul>'
        )
    root = _render_region(
        root_id,
        regions,
        entities,
        facts_by_entity,
        facts_by_region,
    )
    trailing_facts = ''.join(
        _render_fact(fact)
        for fact in view_facts
    )
    if trailing_facts:
        trailing_facts = f'<div class="mv-view-facts">{trailing_facts}</div>'
    return root + structural_markers + relation_index + trailing_facts


def _render_flow(view):
    entities = {entity['id']: entity for entity in view.get('entities', [])}
    sequence = view['composition']['readingPath']['sequence']
    dynamic_relations = {
        (relation['subjectId'], relation['objectId']): relation
        for relation in view.get('relations', [])
        if relation.get('kind') in DYNAMIC_RELATIONS
    }
    facts_by_entity = {}
    facts_by_relation = {}
    trailing_facts = []
    for fact in view.get('facts', []):
        scope = fact.get('scope') or {}
        if scope.get('kind') == 'entity':
            for target in scope.get('targetIds', []):
                facts_by_entity.setdefault(target, []).append(fact)
        elif scope.get('kind') == 'relation':
            for target in scope.get('targetIds', []):
                facts_by_relation.setdefault(target, []).append(fact)
        else:
            trailing_facts.append(fact)
    parts = []
    for index, entity_id in enumerate(sequence):
        entity_facts = ''.join(
            _render_fact(fact)
            for fact in facts_by_entity.get(entity_id, [])
        )
        parts.append(
            '<div class="mv-flow-step">'
            + _render_entity(entities[entity_id])
            + entity_facts
            + '</div>'
        )
        if index >= len(sequence) - 1:
            continue
        next_id = sequence[index + 1]
        relation = dynamic_relations.get((entity_id, next_id))
        if relation is None:
            continue
        relation_label = relation.get('label') or relation['kind']
        relation_facts = ''.join(
            _render_fact(fact)
            for fact in facts_by_relation.get(relation['id'], [])
        )
        parts.append(
            '<div class="mv-connector" '
            f'data-relation-id="{_attr(relation["id"])}" '
            f'data-subject="{_attr(entity_id)}" '
            f'data-object="{_attr(next_id)}" '
            f'data-kind="{_attr(relation["kind"])}" '
            f'data-source-blocks="{_attr(_source_attr(relation))}"'
            f'{_source_unit_attr(relation)} '
            'data-directed="true" role="img" '
            f'aria-label="{_attr(relation_label)}">'
            '<span aria-hidden="true">→</span>'
            f'<small>{escape(str(relation_label))}</small>'
            f'{relation_facts}'
            '</div>'
        )
    relation_markers = ''.join(
        '<span class="mv-relation" '
        f'data-relation-id="{_attr(relation["id"])}" '
        f'data-subject="{_attr(relation["subjectId"])}" '
        f'data-object="{_attr(relation["objectId"])}" '
        f'data-kind="{_attr(relation["kind"])}" '
        f'data-source-blocks="{_attr(_source_attr(relation))}"'
        f'{_source_unit_attr(relation)} hidden>'
        f'{escape(str(entities[relation["subjectId"]].get("label", "")))} '
        f'{escape(str(relation.get("label") or relation["kind"]))} '
        f'{escape(str(entities[relation["objectId"]].get("label", "")))}'
        '</span>'
        for relation in view.get('relations', [])
        if relation.get('kind') not in DYNAMIC_RELATIONS
    )
    trailing_html = ''.join(_render_fact(fact) for fact in trailing_facts)
    if trailing_html:
        trailing_html = f'<div class="mv-view-facts">{trailing_html}</div>'
    return (
        '<div class="mv-flow-sequence">'
        + ''.join(parts)
        + '</div>'
        + relation_markers
        + trailing_html
    )


def _render_matrix(view):
    options = [
        entity
        for entity in view.get('entities', [])
        if entity.get('type') == 'option'
    ]
    header_cells = ''.join(
        '<th scope="col" '
        f'data-entity-id="{_attr(option["id"])}" '
        f'data-emphasis="{_attr(option.get("emphasis", "secondary"))}" '
        f'data-source-blocks="{_attr(_source_attr(option))}">'
        f'<strong>{escape(str(option.get("label", "")))}</strong>'
        f'<small>{escape(str(option.get("detail", "")))}</small>'
        '</th>'
        for option in options
    )
    rows = []
    for fact in view.get('facts', []):
        if not isinstance(fact.get('values'), list):
            continue
        values = {
            item['targetId']: item.get('value', '')
            for item in fact['values']
        }
        source_unit_attr = (
            f' data-source-unit="{_attr(fact["sourceUnitId"])}"'
            if fact.get('sourceUnitId') else ''
        )
        scope = fact.get('scope') or {}
        target_ids = ' '.join(str(target) for target in scope.get('targetIds', []))
        value_cells = ''.join(
            f'<td data-target-id="{_attr(option["id"])}">'
            f'{escape(str(values.get(option["id"], "")))}</td>'
            for option in options
        )
        rows.append(
            f'<tr data-fact-id="{_attr(fact["id"])}" '
            f'data-scope-kind="{_attr(scope.get("kind", "view"))}" '
            f'data-target-ids="{_attr(target_ids)}" '
            f'data-source-blocks="{_attr(_source_attr(fact))}"{source_unit_attr}>'
            f'<th scope="row">{escape(str(fact.get("label", "")))}</th>'
            f'{value_cells}</tr>'
        )
    scalar_facts = ''.join(
        _render_fact(fact)
        for fact in view.get('facts', [])
        if not isinstance(fact.get('values'), list)
    )
    table = (
        '<table class="mv-matrix">'
        '<thead><tr><th scope="col">比较维度</th>'
        f'{header_cells}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
    )
    if scalar_facts:
        scalar_facts = f'<div class="mv-view-facts">{scalar_facts}</div>'
    return table + scalar_facts


def _render_argument_entity(entity, role):
    return (
        '<article class="mv-argument-item mv-entity" '
        f'data-argument-role="{_attr(role)}" '
        f'data-entity-id="{_attr(entity["id"])}" '
        f'data-entity-type="{_attr(entity.get("type", "entity"))}" '
        f'data-emphasis="{_attr(entity.get("emphasis", "secondary"))}" '
        f'data-source-blocks="{_attr(_source_attr(entity))}">'
        f'<h3>{escape(str(entity.get("label", "")))}</h3>'
        f'<p>{escape(str(entity.get("detail", "")))}</p>'
        '</article>'
    )


def _render_argument(view):
    entities = {entity['id']: entity for entity in view.get('entities', [])}
    claims = [
        entity for entity in view.get('entities', [])
        if entity.get('type') == 'claim'
    ]
    evidence = [
        entity for entity in view.get('entities', [])
        if entity.get('type') in {'evidence', 'counterevidence'}
    ]
    relation_by_subject = {
        relation['subjectId']: relation
        for relation in view.get('relations', [])
        if relation.get('kind') in {'supportsClaim', 'contradicts', 'mitigates'}
    }
    facts_by_entity = {}
    facts_by_relation = {}
    trailing_facts = []
    for fact in view.get('facts', []):
        scope = fact.get('scope') or {}
        if scope.get('kind') == 'entity':
            for target in scope.get('targetIds', []):
                facts_by_entity.setdefault(target, []).append(fact)
        elif scope.get('kind') == 'relation':
            for target in scope.get('targetIds', []):
                facts_by_relation.setdefault(target, []).append(fact)
        else:
            trailing_facts.append(fact)
    evidence_items = []
    for entity in evidence:
        relation = relation_by_subject.get(entity['id'])
        entity_facts = ''.join(
            _render_fact(fact)
            for fact in facts_by_entity.get(entity['id'], [])
        )
        badge = ''
        if relation:
            relation_facts = ''.join(
                _render_fact(fact)
                for fact in facts_by_relation.get(relation['id'], [])
            )
            badge = (
                '<div class="mv-argument-link"><span class="mv-argument-relation" '
                f'data-relation-id="{_attr(relation["id"])}" '
                f'data-subject="{_attr(relation["subjectId"])}" '
                f'data-object="{_attr(relation["objectId"])}" '
                f'data-kind="{_attr(relation["kind"])}" '
                f'data-source-blocks="{_attr(_source_attr(relation))}"'
                f'{_source_unit_attr(relation)}>'
                f'{escape(str(relation.get("label") or relation["kind"]))}</span>'
                f'{relation_facts}'
                '</div>'
            )
        evidence_items.append(
            '<div class="mv-argument-evidence">'
            + '<div class="mv-argument-evidence-main">'
            + _render_argument_entity(entity, entity.get('type', 'evidence'))
            + entity_facts
            + '</div>'
            + badge
            + '</div>'
        )
    claim_html = ''.join(
        _render_argument_entity(entity, 'claim')
        + ''.join(_render_fact(fact) for fact in facts_by_entity.get(entity['id'], []))
        for entity in claims
    )
    unplaced = [
        entity for entity_id, entity in entities.items()
        if entity_id not in {item['id'] for item in claims + evidence}
    ]
    context_html = ''.join(
        _render_argument_entity(entity, 'context')
        + ''.join(_render_fact(fact) for fact in facts_by_entity.get(entity['id'], []))
        for entity in unplaced
    )
    trailing_html = ''.join(_render_fact(fact) for fact in trailing_facts)
    if trailing_html:
        trailing_html = f'<div class="mv-view-facts">{trailing_html}</div>'
    return (
        '<div class="mv-argument">'
        f'<div class="mv-argument-claim">{claim_html}</div>'
        f'<div class="mv-argument-evidence-list">{"".join(evidence_items)}</div>'
        f'{context_html}'
        '</div>'
        f'{trailing_html}'
    )


def render_v3_view(view):
    """Render one validated v3 view without accepting free-form HTML or CSS."""
    kind = view.get('diagramKind')
    renderers = {
        'architecture': _render_architecture,
        'flow': _render_flow,
        'matrix': _render_matrix,
        'argument': _render_argument,
    }
    renderer = renderers.get(kind)
    if renderer is None:
        raise ValueError(f'unsupported_diagram_kind: {kind}')
    claim = view.get('centralClaim', {})
    body = renderer(view)
    composition = view.get('composition') or {}
    reading_path = composition.get('readingPath') or {}
    focal_ids = ' '.join(str(item) for item in composition.get('focalIds', []))
    return (
        f'<section class="view mv-view mv-view--{_attr(kind)}" '
        f'id="{_attr(view["id"])}" data-v3-view '
        f'data-diagram-kind="{_attr(kind)}" '
        f'data-reading-kind="{_attr(reading_path.get("kind", "scan"))}" '
        f'data-focal-ids="{_attr(focal_ids)}">'
        '<header class="mv-view-header">'
        f'<p class="mv-view-question">{escape(str(view.get("question", "")))}</p>'
        f'<h2>{escape(str(view.get("title", "")))}</h2>'
        f'<p class="mv-view-claim" data-source-blocks="{_attr(_source_attr(claim))}">'
        f'{escape(str(claim.get("text", "")))}</p>'
        '</header>'
        f'<div class="mv-diagram mv-diagram--{_attr(kind)}">{body}</div>'
        '</section>'
    )


__all__ = ['render_v3_view']
