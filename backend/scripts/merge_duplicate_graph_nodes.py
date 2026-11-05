"""One-time cleanup: merge GraphNode rows that are really the same concept.

Before the dedup-key fix in graph/builder.py, a concept extracted from one
document as "concept" and from another as "framework" (or raced by two
concurrent /graph/build calls) could end up as two separate GraphNode rows
with the identical label — rendering as overlapping duplicate dots with no
edge between them. This merges each such group into a single survivor node,
repoints every edge onto it, and drops the duplicates.

Run once from backend/: .venv/bin/python scripts/merge_duplicate_graph_nodes.py
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from db.models import GraphEdge, GraphNode
from db.session import SessionLocal

MERGED_TYPE_GROUPS = {"concept": "concept_or_framework", "framework": "concept_or_framework"}


def group_key(node: GraphNode) -> tuple[str, str]:
    return (MERGED_TYPE_GROUPS.get(node.node_type, node.node_type), node.label.strip().lower())


def main() -> None:
    db = SessionLocal()
    try:
        nodes = db.execute(select(GraphNode)).scalars().all()
        groups: dict[tuple[str, str], list[GraphNode]] = defaultdict(list)
        for node in nodes:
            groups[group_key(node)].append(node)

        edges = db.execute(select(GraphEdge)).scalars().all()
        degree: dict[str, int] = defaultdict(int)
        for edge in edges:
            degree[edge.source_id] += 1
            degree[edge.target_id] += 1

        merged_groups = 0
        nodes_removed = 0
        edges_repointed = 0
        edges_deduped = 0

        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda n: (-degree.get(n.id, 0), n.created_at))
            survivor, duplicates = members[0], members[1:]
            dup_ids = {d.id for d in duplicates}
            merged_groups += 1

            for edge in edges:
                changed = False
                if edge.source_id in dup_ids:
                    edge.source_id = survivor.id
                    changed = True
                if edge.target_id in dup_ids:
                    edge.target_id = survivor.id
                    changed = True
                if changed:
                    edges_repointed += 1

            # Repointing can create self-loops (an edge between two
            # duplicates in the same group) and exact-duplicate edges (same
            # source, target, relation) touching the survivor — drop both.
            seen: set[tuple[str, str, str]] = set()
            for edge in list(edges):
                if edge.source_id != survivor.id and edge.target_id != survivor.id:
                    continue
                if edge.source_id == edge.target_id:
                    db.delete(edge)
                    edges.remove(edge)
                    edges_deduped += 1
                    continue
                triple = (edge.source_id, edge.target_id, edge.relation)
                if triple in seen:
                    db.delete(edge)
                    edges.remove(edge)
                    edges_deduped += 1
                else:
                    seen.add(triple)

            for dup in duplicates:
                db.delete(dup)
                nodes_removed += 1

        db.commit()
        print(f"merged groups: {merged_groups}")
        print(f"nodes removed: {nodes_removed}")
        print(f"edges repointed: {edges_repointed}")
        print(f"duplicate edges dropped: {edges_deduped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
