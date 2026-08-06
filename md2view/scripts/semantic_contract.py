#!/usr/bin/env python3
"""Derive and validate source-level semantic units for md2view models."""
import re


TABLE_ROW = 'table-row'
CHECK_ITEM = 'check-item'


def _table_cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _is_table_separator(line):
    cells = _table_cells(line)
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells)


def source_units_for_block(block):
    """Return stable row/item anchors without changing the parent block id."""
    block_id = block['id']
    raw = block.get('raw', '')
    if block.get('type') == 'table':
        lines = [line for line in raw.splitlines() if '|' in line and not _is_table_separator(line)]
        rows = lines[1:] if lines else []
        units = []
        for index, line in enumerate(rows, 1):
            cells = _table_cells(line)
            if not cells or not any(cells):
                continue
            units.append({
                'id': f'{block_id}:r{index:03d}',
                'kind': TABLE_ROW,
                'key': cells[0] or f'第 {index} 行',
                'raw': line.strip(),
            })
        return units
    if block.get('type') == 'list':
        units = []
        for line in raw.splitlines():
            match = re.match(r'^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]\s+(.+?)\s*$', line)
            if not match:
                continue
            index = len(units) + 1
            units.append({
                'id': f'{block_id}:i{index:03d}',
                'kind': CHECK_ITEM,
                'key': match.group(2),
                'raw': line.strip(),
                'checked': match.group(1).lower() == 'x',
            })
        return units
    return []


def derive_source_units(blocks):
    return {
        unit['id']: {**unit, 'blockId': block['id']}
        for block in blocks
        for unit in source_units_for_block(block)
    }


def is_decision_table(block):
    if block.get('type') != 'table':
        return False
    first_line = next((line for line in block.get('raw', '').splitlines() if '|' in line), '')
    cells = _table_cells(first_line)
    if not cells:
        return False
    heading = re.sub(r'[\s*_`：:（）()]', '', cells[0]).lower()
    markers = ('维度', '指标', '标准', '对比项', '比较项', 'dimension', 'criterion', 'criteria', 'metric')
    return any(marker in heading for marker in markers)


def _view_entities(view):
    model_entities = view.get('entities', view.get('elements', []))
    return [*model_entities, *view.get('facts', [])]


def _norm_semantic_text(value):
    return re.sub(r'[\W_]+', '', str(value or ''), flags=re.UNICODE).lower()


def _entity_text(entity):
    scalar_text = [
        str(entity.get(field, ''))
        for field in ('label', 'detail', 'value')
    ]
    comparison_text = [
        str(item.get('value', ''))
        for item in entity.get('values', [])
        if isinstance(item, dict)
    ]
    return _norm_semantic_text(' '.join([*scalar_text, *comparison_text]))


def validate_semantic_model(blocks, plan):
    """Reject models that collapse atomic decision rows into summary elements."""
    units = derive_source_units(blocks)
    decision_block_ids = {block['id'] for block in blocks if is_decision_table(block)}
    required = {
        unit_id: unit
        for unit_id, unit in units.items()
        if unit['kind'] == CHECK_ITEM or unit['blockId'] in decision_block_ids
    }
    supplied = set()
    problems = []

    for view in plan.get('views', []):
        entities = _view_entities(view)
        for entity in entities:
            source_unit_id = entity.get('sourceUnitId')
            if source_unit_id:
                if source_unit_id not in units:
                    problems.append(f'sourceUnitId 不存在: {source_unit_id}')
                    continue
                parent_block_id = units[source_unit_id]['blockId']
                if parent_block_id not in entity.get('sourceBlockIds', []):
                    problems.append(
                        f"{source_unit_id} 的父块 {parent_block_id} 未出现在 "
                        f"{entity.get('id', 'entity')}.sourceBlockIds"
                    )
                    continue
                unit = units[source_unit_id]
                entity_text = _entity_text(entity)
                key = _norm_semantic_text(unit['key'])
                if key and key not in entity_text:
                    problems.append(
                        f"{source_unit_id} 未在 {entity.get('id', 'entity')} 中呈现源单位 key: "
                        f"{unit['key']}"
                    )
                    continue
                if unit['kind'] == TABLE_ROW:
                    missing_cells = [
                        cell
                        for cell in _table_cells(unit['raw'])[1:]
                        if _norm_semantic_text(cell) and _norm_semantic_text(cell) not in entity_text
                    ]
                    if missing_cells:
                        problems.append(
                            f"{source_unit_id} 未在 {entity.get('id', 'entity')} 中呈现表格单元格: "
                            f"{missing_cells[0]}"
                        )
                        continue
                supplied.add(source_unit_id)
        concept = view.get('diagramKind', view.get('concept', ''))
        if str(concept).lower() != 'matrix':
            continue
        referenced_blocks = {
            block_id
            for entity in entities
            for block_id in entity.get('sourceBlockIds', [])
        }
        required.update({
            unit_id: unit
            for unit_id, unit in units.items()
            if unit['kind'] == TABLE_ROW and unit['blockId'] in referenced_blocks
        })

    missing = [unit for unit_id, unit in required.items() if unit_id not in supplied]
    if missing:
        labels = '、'.join(f"{unit['id']}({unit['key']})" for unit in missing)
        problems.append(f'缺少 {len(missing)} 个原子语义单元: {labels}')
    if problems:
        raise ValueError('views.json 语义原子合同失败:\n- ' + '\n- '.join(problems))


__all__ = [
    'CHECK_ITEM',
    'TABLE_ROW',
    'derive_source_units',
    'is_decision_table',
    'source_units_for_block',
    'validate_semantic_model',
]
