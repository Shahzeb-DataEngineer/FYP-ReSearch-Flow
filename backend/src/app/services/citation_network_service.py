import logging
import re
from typing import List, Dict, Any, Set, Tuple, Optional
import requests
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .openalex_client import get_openalex_headers, is_key_not_activated

OPENALEX_BASE_URL = "https://api.openalex.org"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
SS_HEADERS = {"User-Agent": "ReSearch-Flow/1.0"}
SS_FIELDS = "paperId,title,authors,year,citationCount,venue"


def _is_semantic_scholar_id(paper_id: str) -> bool:
    """Check if a paper ID looks like a Semantic Scholar ID (40-char hex string)."""
    return bool(re.match(r'^[0-9a-f]{40}$', str(paper_id).strip()))


# ──────────────────────────────────────────────
# API Fetchers
# ──────────────────────────────────────────────

def fetch_semantic_scholar_references(paper_id: str) -> Optional[Dict[str, Any]]:
    """Fetch paper details and its OUTGOING references from Semantic Scholar."""
    try:
        url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{paper_id}"
        params = {
            "fields": f"{SS_FIELDS},references.paperId,references.title,references.year,references.citationCount,references.authors,references.venue"
        }
        resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.warning(f"Failed to fetch S2 references for {paper_id}: {e}")
        return None


def fetch_semantic_scholar_citations(paper_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch papers that CITE a given paper (incoming citations)."""
    try:
        url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{paper_id}/citations"
        params = {
            "fields": SS_FIELDS,
            "limit": limit
        }
        resp = requests.get(url, params=params, headers=SS_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return [item.get("citingPaper", {}) for item in data.get("data", []) if item.get("citingPaper", {}).get("paperId")]
    except Exception as e:
        logging.warning(f"Failed to fetch S2 citations for {paper_id}: {e}")
        return []


def fetch_work_details(work_id: str) -> Optional[Dict[str, Any]]:
    """Fetch detailed information about a specific work from OpenAlex."""
    try:
        if work_id.startswith("https://openalex.org/"):
            work_id = work_id.replace("https://openalex.org/", "")
        url = f"{OPENALEX_BASE_URL}/works/{work_id}"
        headers = get_openalex_headers()
        resp = requests.get(url, headers=headers, timeout=10)
        if headers and is_key_not_activated(resp):
            logging.warning(
                "OpenAlex API key not activated yet (key_not_activated); "
                "retrying without a key"
            )
            resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.warning(f"Failed to fetch work {work_id}: {e}")
        return None


def fetch_openalex_cited_by(work_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch papers that cite a given OpenAlex work (incoming citations)."""
    try:
        if work_id.startswith("https://openalex.org/"):
            work_id = work_id.replace("https://openalex.org/", "")
        url = f"{OPENALEX_BASE_URL}/works"
        params = {"filter": f"cites:{work_id}", "per_page": limit}
        headers = get_openalex_headers()
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if headers and is_key_not_activated(resp):
            logging.warning(
                "OpenAlex API key not activated yet (key_not_activated); "
                "retrying without a key"
            )
            resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        logging.warning(f"Failed to fetch OpenAlex cited-by for {work_id}: {e}")
        return []


# ──────────────────────────────────────────────
# Graph Metrics
# ──────────────────────────────────────────────

def _enrich_graph_with_metrics(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    """Computes Influence Score, PageRank, and Citation Velocity for graph nodes."""
    current_year = datetime.now().year

    # 1. Citation Velocity
    for node in nodes:
        node["inDegree"] = 0
        node["pageRankScore"] = 1.0 / max(1, len(nodes))
        year = node.get("year")
        cites = node.get("citationCount", 0)
        if year and isinstance(year, int) and year <= current_year:
            age = max(1, current_year - year)
            node["citationVelocity"] = round(cites / age, 2)
        else:
            node["citationVelocity"] = 0.0

    # 2. In-Degree & Influence Score
    in_degrees = defaultdict(int)
    out_degrees = defaultdict(int)
    for edge in edges:
        in_degrees[edge["target"]] += 1
        out_degrees[edge["source"]] += 1

    max_in_degree = max(in_degrees.values()) if in_degrees else 1

    for node in nodes:
        nid = node["id"]
        node["inDegree"] = in_degrees[nid]
        node["influenceScore"] = round(in_degrees[nid] / max_in_degree, 4) if max_in_degree > 0 else 0.0

    # 3. PageRank (10 iterations)
    d = 0.85
    num_nodes = len(nodes)
    if num_nodes == 0:
        return

    node_map = {n["id"]: n for n in nodes}
    incoming_edges = defaultdict(list)
    for edge in edges:
        incoming_edges[edge["target"]].append(edge["source"])

    for _ in range(10):
        new_pr = {}
        for node in nodes:
            nid = node["id"]
            pr_sum = 0.0
            for source_id in incoming_edges[nid]:
                if source_id in node_map:
                    source_out = out_degrees[source_id]
                    if source_out > 0:
                        pr_sum += node_map[source_id]["pageRankScore"] / source_out
            new_pr[nid] = ((1.0 - d) / num_nodes) + d * pr_sum

        for nid, score in new_pr.items():
            node_map[nid]["pageRankScore"] = score

    # Normalize PageRank to 0-1 range
    pr_scores = [n["pageRankScore"] for n in nodes]
    max_pr = max(pr_scores) if pr_scores else 1.0
    for node in nodes:
        node["pageRankScore"] = round(node["pageRankScore"] / max_pr, 4) if max_pr > 0 else 0.0


# ──────────────────────────────────────────────
# Helper: extract author names
# ──────────────────────────────────────────────

def _extract_authors(authors_raw):
    """Normalize author list from various formats."""
    if not authors_raw:
        return []
    if isinstance(authors_raw[0], dict):
        return [a.get("name", "Unknown") for a in authors_raw[:3]]
    return list(authors_raw[:3])


# ──────────────────────────────────────────────
# Semantic Scholar Network Builder
# ──────────────────────────────────────────────

def _fetch_paper_neighbourhood(paper_id: str) -> Dict[str, Any]:
    """Fetch both references AND citations for one paper concurrently."""
    with ThreadPoolExecutor(max_workers=2) as inner_pool:
        refs_future = inner_pool.submit(fetch_semantic_scholar_references, paper_id)
        cites_future = inner_pool.submit(fetch_semantic_scholar_citations, paper_id, 8)
        
        refs_data = refs_future.result()
        citations = cites_future.result()
    
    return {
        "paper_id": paper_id,
        "references": (refs_data.get("references") or []) if refs_data else [],
        "citations": citations
    }


def _build_network_semantic_scholar(papers: List[Dict[str, Any]], max_depth: int = 1, max_nodes: int = 80) -> Dict[str, Any]:
    """Build bidirectional citation network using Semantic Scholar API with concurrent fetching."""
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    visited: Set[str] = set()
    root_ids: Set[str] = set()

    # Step 1: Add root papers
    for paper in papers:
        paper_id = paper.get("paperId") or paper.get("id")
        if not paper_id or paper_id in visited:
            continue
        if len(nodes) >= max_nodes:
            break

        visited.add(paper_id)
        root_ids.add(paper_id)
        nodes[paper_id] = {
            "id": paper_id,
            "label": (paper.get("title") or "Unknown Title")[:100],
            "title": paper.get("title", "Unknown Title"),
            "year": paper.get("year"),
            "citationCount": paper.get("citationCount", 0),
            "authors": _extract_authors(paper.get("authors", [])),
            "venue": paper.get("venue", "N/A"),
            "isRoot": True,
            "isBridge": False
        }

    # Step 2: Fetch references AND citations concurrently
    if max_depth >= 1:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_fetch_paper_neighbourhood, pid): pid
                for pid in list(root_ids)
            }
            for future in as_completed(futures):
                pid = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    logging.warning(f"Error fetching neighbourhood for {pid}: {e}")
                    continue

                if len(nodes) >= max_nodes:
                    break

                # Process REFERENCES (outgoing: root → reference)
                for ref in result["references"][:8]:
                    ref_id = ref.get("paperId")
                    if not ref_id:
                        continue
                    edges.append({"source": pid, "target": ref_id, "type": "cites"})
                    if ref_id not in visited and len(nodes) < max_nodes:
                        visited.add(ref_id)
                        nodes[ref_id] = {
                            "id": ref_id,
                            "label": (ref.get("title") or "Unknown Title")[:100],
                            "title": ref.get("title", "Unknown Title"),
                            "year": ref.get("year"),
                            "citationCount": ref.get("citationCount", 0),
                            "authors": _extract_authors(ref.get("authors", [])),
                            "venue": ref.get("venue", "N/A"),
                            "isRoot": False,
                            "isBridge": False
                        }

                # Process CITATIONS (incoming: citing_paper → root)
                for citing in result["citations"][:8]:
                    citing_id = citing.get("paperId")
                    if not citing_id:
                        continue
                    edges.append({"source": citing_id, "target": pid, "type": "cited_by"})
                    if citing_id not in visited and len(nodes) < max_nodes:
                        visited.add(citing_id)
                        nodes[citing_id] = {
                            "id": citing_id,
                            "label": (citing.get("title") or "Unknown Title")[:100],
                            "title": citing.get("title", "Unknown Title"),
                            "year": citing.get("year"),
                            "citationCount": citing.get("citationCount", 0),
                            "authors": _extract_authors(citing.get("authors", [])),
                            "venue": citing.get("venue", "N/A"),
                            "isRoot": False,
                            "isBridge": False
                        }

    # Step 3: Bridge paper discovery
    # A bridge paper is a non-root node that connects to 2+ different root papers
    node_root_connections: Dict[str, Set[str]] = defaultdict(set)
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in root_ids and tgt not in root_ids:
            node_root_connections[tgt].add(src)
        if tgt in root_ids and src not in root_ids:
            node_root_connections[src].add(tgt)

    bridge_count = 0
    for nid, connected_roots in node_root_connections.items():
        if len(connected_roots) >= 2 and nid in nodes:
            nodes[nid]["isBridge"] = True
            bridge_count += 1

    # Step 4: Filter & deduplicate
    valid_node_ids = set(nodes.keys())
    edges = [e for e in edges if e["source"] in valid_node_ids and e["target"] in valid_node_ids]

    seen_edges = set()
    unique_edges = []
    for edge in edges:
        edge_key = (edge["source"], edge["target"])
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            unique_edges.append(edge)

    nodes_list = list(nodes.values())
    _enrich_graph_with_metrics(nodes_list, unique_edges)

    logging.info(f"S2 citation network: {len(nodes_list)} nodes, {len(unique_edges)} edges, {bridge_count} bridges")

    return {
        "nodes": nodes_list,
        "edges": unique_edges,
        "stats": {
            "totalNodes": len(nodes_list),
            "totalEdges": len(unique_edges),
            "rootNodes": sum(1 for n in nodes_list if n.get("isRoot")),
            "citationNodes": sum(1 for n in nodes_list if not n.get("isRoot") and not n.get("isBridge")),
            "bridgeNodes": bridge_count,
            "bidirectional": True
        }
    }


# ──────────────────────────────────────────────
# OpenAlex Network Builder
# ──────────────────────────────────────────────

def _fetch_openalex_neighbourhood(paper_id: str) -> Dict[str, Any]:
    """Fetch both references AND cited-by for one OpenAlex paper concurrently."""
    with ThreadPoolExecutor(max_workers=2) as inner_pool:
        work_future = inner_pool.submit(fetch_work_details, paper_id)
        cited_future = inner_pool.submit(fetch_openalex_cited_by, paper_id, 8)
        
        work = work_future.result()
        cited_by = cited_future.result()
    
    return {"paper_id": paper_id, "work": work, "cited_by": cited_by}


def _parse_openalex_node(work: Dict[str, Any], is_root: bool = False) -> Dict[str, Any]:
    """Parse an OpenAlex work into a graph node."""
    oa_id = work.get("id", "").replace("https://openalex.org/", "")
    return {
        "id": oa_id,
        "label": work.get("display_name", "Unknown Title")[:100],
        "title": work.get("display_name", "Unknown Title"),
        "year": work.get("publication_year"),
        "citationCount": work.get("cited_by_count", 0),
        "authors": [
            (a.get("author") or {}).get("display_name", "Unknown")
            for a in (work.get("authorships") or [])[:3]
        ],
        "venue": ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "N/A"),
        "isRoot": is_root,
        "isBridge": False
    }


def _build_network_openalex(papers: List[Dict[str, Any]], max_depth: int = 1, max_nodes: int = 80) -> Dict[str, Any]:
    """Build bidirectional citation network using OpenAlex API with concurrent fetching."""
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    visited: Set[str] = set()
    root_ids: Set[str] = set()

    # Step 1: Add root papers
    for paper in papers:
        paper_id = paper.get("paperId") or paper.get("id")
        if not paper_id or paper_id in visited:
            continue
        visited.add(paper_id)
        root_ids.add(paper_id)
        nodes[paper_id] = {
            "id": paper_id,
            "label": (paper.get("title") or "Unknown Title")[:100],
            "title": paper.get("title", "Unknown Title"),
            "year": paper.get("year"),
            "citationCount": paper.get("citationCount", 0),
            "authors": paper.get("authors", [])[:3],
            "venue": paper.get("venue", "N/A"),
            "isRoot": True,
            "isBridge": False
        }

    # Step 2: Concurrent fetching
    if max_depth >= 1:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_fetch_openalex_neighbourhood, pid): pid
                for pid in list(root_ids)
            }
            for future in as_completed(futures):
                pid = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    logging.warning(f"Error fetching OA neighbourhood for {pid}: {e}")
                    continue

                work = result["work"]
                if not work:
                    continue

                # REFERENCES (outgoing)
                for ref_id_raw in (work.get("referenced_works") or [])[:10]:
                    ref_id = ref_id_raw.replace("https://openalex.org/", "") if ref_id_raw.startswith("https://") else ref_id_raw
                    if len(nodes) >= max_nodes:
                        break
                    edges.append({"source": pid, "target": ref_id, "type": "cites"})
                    if ref_id not in visited:
                        ref_work = fetch_work_details(ref_id)
                        if ref_work:
                            visited.add(ref_id)
                            nodes[ref_id] = _parse_openalex_node(ref_work, is_root=False)

                # CITATIONS (incoming)
                for citing_work in result["cited_by"]:
                    citing_id = citing_work.get("id", "").replace("https://openalex.org/", "")
                    if not citing_id or len(nodes) >= max_nodes:
                        break
                    edges.append({"source": citing_id, "target": pid, "type": "cited_by"})
                    if citing_id not in visited:
                        visited.add(citing_id)
                        nodes[citing_id] = _parse_openalex_node(citing_work, is_root=False)

    # Step 3: Bridge discovery
    node_root_connections: Dict[str, Set[str]] = defaultdict(set)
    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in root_ids and tgt not in root_ids:
            node_root_connections[tgt].add(src)
        if tgt in root_ids and src not in root_ids:
            node_root_connections[src].add(tgt)

    bridge_count = 0
    for nid, connected_roots in node_root_connections.items():
        if len(connected_roots) >= 2 and nid in nodes:
            nodes[nid]["isBridge"] = True
            bridge_count += 1

    # Step 4: Filter & deduplicate
    valid_node_ids = set(nodes.keys())
    edges = [e for e in edges if e["source"] in valid_node_ids and e["target"] in valid_node_ids]

    seen_edges = set()
    unique_edges = []
    for edge in edges:
        edge_key = (edge["source"], edge["target"])
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            unique_edges.append(edge)

    nodes_list = list(nodes.values())
    _enrich_graph_with_metrics(nodes_list, unique_edges)

    logging.info(f"OpenAlex citation network: {len(nodes_list)} nodes, {len(unique_edges)} edges, {bridge_count} bridges")

    return {
        "nodes": nodes_list,
        "edges": unique_edges,
        "stats": {
            "totalNodes": len(nodes_list),
            "totalEdges": len(unique_edges),
            "rootNodes": sum(1 for n in nodes_list if n.get("isRoot")),
            "citationNodes": sum(1 for n in nodes_list if not n.get("isRoot") and not n.get("isBridge")),
            "bridgeNodes": bridge_count,
            "bidirectional": True
        }
    }


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def build_citation_network(paper_ids: List[str], max_depth: int = 1, max_nodes: int = 80) -> Dict[str, Any]:
    """Build a citation network graph from a list of paper IDs (OpenAlex)."""
    logging.info(f"Building citation network for {len(paper_ids)} papers, depth={max_depth}, max_nodes={max_nodes}")
    papers = [{"id": pid} for pid in paper_ids]
    return _build_network_openalex(papers, max_depth, max_nodes)


def build_citation_network_from_papers(papers: List[Dict[str, Any]], max_depth: int = 1, max_nodes: int = 80) -> Dict[str, Any]:
    """
    Build an interconnected citation network from search results.
    Auto-detects whether papers are from Semantic Scholar or OpenAlex.
    """
    logging.info(f"Building citation network from {len(papers)} papers, depth={max_depth}, max_nodes={max_nodes}")

    sample_ids = [p.get("paperId") or p.get("id", "") for p in papers[:3]]
    use_semantic_scholar = any(_is_semantic_scholar_id(pid) for pid in sample_ids if pid)

    if use_semantic_scholar:
        logging.info("Detected Semantic Scholar IDs — using S2 API")
        return _build_network_semantic_scholar(papers, max_depth, max_nodes)
    else:
        logging.info("Using OpenAlex API")
        return _build_network_openalex(papers, max_depth, max_nodes)
