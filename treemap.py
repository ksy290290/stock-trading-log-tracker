"""Minimal squarified-treemap layout (Bruls, Huizing, van Wijk 2000),
implemented from scratch to avoid an extra dependency for one small feature.

Used by the 히트맵 tab to lay out a two-level treemap: sectors sized by
total market cap, and within each sector, individual stocks sized by their
own market cap.
"""


def _row_ratio(row, side):
    """Worst (largest) aspect ratio produced by laying `row` along `side`."""
    if not row or side <= 0:
        return float("inf")
    total = sum(row)
    if total <= 0:
        return float("inf")
    row_max = max(row)
    row_min = min(row)
    side_sq = side * side
    total_sq = total * total
    return max((side_sq * row_max) / total_sq, total_sq / (side_sq * row_min))


def squarify(sizes, x, y, w, h):
    """Lay out `sizes` (already scaled so sum(sizes) == w*h) into rectangles
    filling (x, y, w, h). Returns a list of (x, y, w, h) in the same order
    as `sizes`. Best results when `sizes` is sorted descending."""
    sizes = list(sizes)
    rects = [None] * len(sizes)
    indices = list(range(len(sizes)))
    x, y, w, h = float(x), float(y), float(w), float(h)

    while indices:
        side = min(w, h)
        row = [sizes[indices[0]]]
        row_idx = [indices[0]]
        i = 1
        while i < len(indices):
            candidate = row + [sizes[indices[i]]]
            if _row_ratio(candidate, side) <= _row_ratio(row, side):
                row = candidate
                row_idx.append(indices[i])
                i += 1
            else:
                break

        row_total = sum(row)
        if w >= h:
            row_w = row_total / h if h > 0 else 0
            ry = y
            for idx, size in zip(row_idx, row):
                rh = size / row_w if row_w > 0 else 0
                rects[idx] = (x, ry, row_w, rh)
                ry += rh
            x += row_w
            w -= row_w
        else:
            row_h = row_total / w if w > 0 else 0
            rx = x
            for idx, size in zip(row_idx, row):
                rw = size / row_h if row_h > 0 else 0
                rects[idx] = (rx, y, rw, row_h)
                rx += rw
            y += row_h
            h -= row_h

        indices = indices[len(row_idx):]

    return rects


def normalize_sizes(sizes, w, h):
    total = sum(sizes)
    if total <= 0:
        return [0 for _ in sizes]
    area = w * h
    return [s / total * area for s in sizes]


def layout_grouped(items, key_size, key_group, canvas_w, canvas_h, header_h=20, gap=2):
    """Two-level treemap: group items by key_group(item), size sector blocks
    by the sum of key_size(item) within each group, then squarify each
    group's items inside its block (below a header strip of `header_h`).

    Returns (sector_rects, item_rects):
      sector_rects: list of {"name", "x","y","w","h","total"} for each group
      item_rects:   list of (item, x, y, w, h) for each item, header-relative
                    coordinates already applied (i.e. ready to render as-is)
    Groups and items within a group are sorted by size descending.
    """
    groups = {}
    for item in items:
        groups.setdefault(key_group(item), []).append(item)

    group_names = sorted(groups.keys(), key=lambda g: sum(key_size(i) for i in groups[g]), reverse=True)
    group_totals = [sum(key_size(i) for i in groups[g]) for g in group_names]

    areas = normalize_sizes(group_totals, canvas_w, canvas_h)
    group_boxes = squarify(areas, 0, 0, canvas_w, canvas_h)

    sector_rects = []
    item_rects = []
    for name, total, (gx, gy, gw, gh) in zip(group_names, group_totals, group_boxes):
        gx += gap / 2
        gy += gap / 2
        gw = max(gw - gap, 0)
        gh = max(gh - gap, 0)
        sector_rects.append({"name": name, "x": gx, "y": gy, "w": gw, "h": gh, "total": total})

        inner_header = min(header_h, gh * 0.4) if gh > 0 else 0
        inner_y = gy + inner_header
        inner_h = max(gh - inner_header, 0)

        members = sorted(groups[name], key=key_size, reverse=True)
        sizes = [max(key_size(m), 1) for m in members]
        member_areas = normalize_sizes(sizes, gw, inner_h)
        member_boxes = squarify(member_areas, gx, inner_y, gw, inner_h)
        for item, (ix, iy, iw, ih) in zip(members, member_boxes):
            item_rects.append((item, ix, iy, iw, ih))

    return sector_rects, item_rects
