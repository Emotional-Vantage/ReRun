import os
import re
import io
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Literal

class PDFValidationError(ValueError):
    """Raised when PDF fails format, size, page count, or text extractability validation."""
    pass

def validate_pdf_bytes(pdf_bytes: bytes) -> dict:
    if not pdf_bytes:
        raise PDFValidationError("No PDF data provided.")
        
    if not pdf_bytes.startswith(b"%PDF-"):
        raise PDFValidationError("Uploaded file is not a valid PDF (missing '%PDF-' header).")
        
    max_size = 25 * 1024 * 1024
    if len(pdf_bytes) > max_size:
        raise PDFValidationError(f"PDF exceeds size limit of 25 MB (got {len(pdf_bytes) / (1024*1024):.1f} MB).")
        
    page_count = 0
    extracted_text = ""
    try:
        import pymupdf
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            page_count = len(doc)
            if page_count > 60:
                raise PDFValidationError(f"PDF exceeds maximum page limit of 60 pages (got {page_count} pages).")
            for page in doc:
                txt = page.get_text() or ""
                extracted_text += txt + "\n"
    except PDFValidationError:
        raise
    except Exception:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            if page_count > 60:
                raise PDFValidationError(f"PDF exceeds maximum page limit of 60 pages (got {page_count} pages).")
            for page in reader.pages:
                txt = page.extract_text() or ""
                extracted_text += txt + "\n"
        except PDFValidationError:
            raise
        except Exception as e:
            raise PDFValidationError(f"Failed to parse PDF document: {e}")
            
    clean_text = "".join(extracted_text.split())
    if len(clean_text) < 50:
        raise PDFValidationError(
            "PDF contains no extractable text. Scanned or image-only documents are not supported; "
            "please upload a PDF with digital text."
        )
        
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
    return {
        "sha256": sha256_hash,
        "page_count": page_count,
        "text_length": len(clean_text)
    }

def normalize_text(text: str) -> str:
    """Normalizes text for substring search, resolving ligatures, dashes, quotes, and whitespace."""
    if not text:
        return ""
    t = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    t = t.replace("–", "-").replace("—", "-").replace("−", "-")
    t = t.replace("“", '"').replace("”", '"').replace("„", '"').replace("‟", '"')
    t = t.replace("‘", "'").replace("’", "'").replace("‚", "'").replace("‛", "'")
    t = " ".join(t.split())
    return t

def verify_quote(full_text: str, quote: str, tables: Optional[List[Dict[str, Any]]] = None) -> bool:
    """
    Verifies that quote is a verbatim substring of paper text or extracted markdown tables.
    Rejects hallucinated quotes.
    """
    if not quote or not quote.strip() or not full_text:
        return False

    norm_quote = normalize_text(quote).lower()
    norm_full = normalize_text(full_text).lower()

    if norm_quote in norm_full:
        return True

    if tables:
        for tbl in tables:
            md_text = tbl.get("markdown", "")
            if md_text:
                norm_tbl = normalize_text(md_text).lower()
                if norm_quote in norm_tbl:
                    return True
            rows = tbl.get("rows", [])
            for r in rows:
                row_str = normalize_text(" ".join(str(cell) for cell in r)).lower()
                if norm_quote in row_str:
                    return True

    return False

def _clean_header_footer(blocks: list, page_height: float, page_num: int) -> list:
    cleaned = []
    header_threshold = page_height * 0.07
    footer_threshold = page_height * 0.93

    header_patterns = [
        re.compile(r"arxiv:\d+\.\d+", re.I),
        re.compile(r"proceedings of", re.I),
        re.compile(r"preprint\.?\s*under review", re.I),
        re.compile(r"conference on", re.I),
        re.compile(r"published as a conference paper", re.I),
    ]

    for b in blocks:
        if b[6] != 0:
            continue
        text = b[4].strip()
        if not text:
            continue

        y0, y1 = b[1], b[3]

        if y1 <= header_threshold:
            if any(p.search(text) for p in header_patterns) or len(text) < 30:
                continue

        if y0 >= footer_threshold:
            if text.isdigit() or text.lower() == str(page_num) or len(text) < 15:
                continue

        cleaned.append(b)

    return cleaned

def _sort_blocks_layout_aware(blocks: list, page_width: float, page_height: float) -> list:
    if not blocks:
        return []

    mid_x = page_width / 2.0

    left_cnt = sum(1 for b in blocks if b[2] <= mid_x + 30 and b[0] < mid_x - 30)
    right_cnt = sum(1 for b in blocks if b[0] >= mid_x - 30 and b[2] > mid_x + 30)
    is_two_col = (left_cnt >= 2 and right_cnt >= 2)

    if not is_two_col:
        return sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

    def get_sort_key(b):
        x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
        if x0 < mid_x - 60 and x1 > mid_x + 60:
            band = 0 if y0 < page_height * 0.35 else 3
            return (band, round(y0, 1), round(x0, 1))
        elif x1 <= mid_x + 25:
            return (1, round(y0, 1), round(x0, 1))
        elif x0 >= mid_x - 25:
            return (2, round(y0, 1), round(x0, 1))
        else:
            center = (x0 + x1) / 2.0
            col = 1 if center < mid_x else 2
            return (col, round(y0, 1), round(x0, 1))

    return sorted(blocks, key=get_sort_key)

def _extract_tables(page, page_num: int) -> List[Dict[str, Any]]:
    tables = []
    try:
        tabs = page.find_tables().tables
    except Exception:
        return tables

    for t_idx, tab in enumerate(tabs):
        try:
            raw_rows = tab.extract()
            if not raw_rows or len(raw_rows) < 2:
                continue

            clean_rows = []
            for r in raw_rows:
                row_cells = [("" if cell is None else str(cell).replace("\n", " ").strip()) for cell in r]
                if any(row_cells):
                    clean_rows.append(row_cells)

            if len(clean_rows) < 2:
                continue

            max_cols = max(len(r) for r in clean_rows)
            padded = [r + [""] * (max_cols - len(r)) for r in clean_rows]

            headers = padded[0]
            data_rows = padded[1:]

            table_id = f"[p{page_num}:T{t_idx + 1}]"
            md_lines = [
                f"{table_id}",
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * max_cols) + " |"
            ]
            for r in data_rows:
                md_lines.append("| " + " | ".join(r) + " |")

            tables.append({
                "id": table_id,
                "page": page_num,
                "markdown": "\n".join(md_lines),
                "headers": headers,
                "rows": data_rows
            })
        except Exception:
            continue

    return tables

METRIC_SCORING_PATTERNS = [
    r"\baccuracy\b", r"\bf1\b", r"\bbleu\b", r"\bauc\b", r"\berror\s*rate\b", r"\btest\s*accuracy\b",
    r"\bresults\b", r"\btable\b", r"\bbenchmark\b", r"\bsota\b", r"\bstate-of-the-art\b", r"\bperformance\b",
    r"\bevaluation\b", r"\bscore\b", r"\btest\s*error\b", r"\bmetric\b", r"\bprecision\b", r"\brecall\b"
]

HYPERPARAM_SCORING_PATTERNS = [
    r"\bhyperparameter[s]?\b", r"\blearning\s*rate\b", r"\bbatch\s*size\b", r"\boptimizer\b",
    r"\bweight\s*decay\b", r"\bdropout\b", r"\bepoch[s]?\b", r"\biteration[s]?\b", r"\bseed[s]?\b",
    r"\bimplementation\s*details\b", r"\btraining\s*details\b", r"\bexperimental\s*setup\b",
    r"\bappendix\b", r"\badam\b", r"\bsgd\b", r"\bmomentum\b", r"\blr\b"
]

def score_page(text: str, tables: List[Dict[str, Any]], page_num: int) -> float:
    text_lower = text.lower()
    score = 0.0

    if page_num == 1:
        score += 15.0
    elif page_num == 2:
        score += 5.0

    score += len(tables) * 5.0

    for p in METRIC_SCORING_PATTERNS:
        matches = len(re.findall(p, text_lower))
        score += min(matches, 5) * 2.5

    for p in HYPERPARAM_SCORING_PATTERNS:
        matches = len(re.findall(p, text_lower))
        score += min(matches, 5) * 2.0

    return round(score, 2)

def cap_prompt_text(pages: List[Dict[str, Any]], max_chars: int = 60_000) -> str:
    if not pages:
        return ""

    sorted_by_score = sorted(pages, key=lambda p: (p["n"] == 1, p["score"]), reverse=True)

    selected_pages = []
    current_len = 0

    for p in sorted_by_score:
        page_content_len = len(p["page_marked_text"])
        if current_len + page_content_len <= max_chars or p["n"] == 1:
            selected_pages.append(p)
            current_len += page_content_len
        elif not selected_pages:
            selected_pages.append(p)
            break

    selected_pages.sort(key=lambda p: p["n"])

    out_chunks = []
    for p in selected_pages:
        header = f"=== Page {p['n']} (Relevance Score: {p['score']}) ==="
        out_chunks.append(header)
        out_chunks.append(p["page_marked_text"])

    return "\n\n".join(out_chunks)

def extract_paper(pdf_path: str, max_chars: int = 60_000) -> Dict[str, Any]:
    import pymupdf

    pages = []
    all_tables = []
    all_marked_lines = []
    full_prose_parts = []
    page_scores = {}

    with pymupdf.open(pdf_path) as doc:
        total_pages = len(doc)
        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            w = page.rect.width
            h = page.rect.height

            raw_blocks = page.get_text("blocks")
            clean_blocks = _clean_header_footer(raw_blocks, h, page_num)
            sorted_blocks = _sort_blocks_layout_aware(clean_blocks, w, h)

            page_tables = _extract_tables(page, page_num)
            all_tables.extend(page_tables)

            page_lines = []
            marked_page_lines = []
            for b in sorted_blocks:
                b_text = b[4]
                for line in b_text.splitlines():
                    clean_line = line.strip()
                    if clean_line:
                        page_lines.append(clean_line)

            for line_idx, line in enumerate(page_lines):
                marker = f"[p{page_num}:L{line_idx + 1}] {line}"
                marked_page_lines.append(marker)
                all_marked_lines.append(marker)

            for t in page_tables:
                marked_page_lines.append(t["markdown"])
                all_marked_lines.append(t["markdown"])

            page_text = "\n".join(page_lines)
            full_prose_parts.append(page_text)

            score = score_page(page_text, page_tables, page_num)
            page_scores[page_num] = score

            pages.append({
                "n": page_num,
                "lines": page_lines,
                "text": page_text,
                "tables": page_tables,
                "score": score,
                "page_marked_text": "\n".join(marked_page_lines)
            })

    full_text = "\n".join(full_prose_parts)
    marked_text = "\n".join(all_marked_lines)
    selected_prompt = cap_prompt_text(pages, max_chars=max_chars)

    return {
        "pages": pages,
        "tables": all_tables,
        "marked_text": marked_text,
        "full_text": full_text,
        "selected_prompt_text": selected_prompt,
        "total_pages": total_pages,
        "page_scores": page_scores
    }

def extract_text(pdf_path: str) -> Dict[str, Any]:
    try:
        return extract_paper(pdf_path)
    except Exception as e:
        return {
            "pages": [],
            "tables": [],
            "marked_text": "",
            "full_text": f"Error extracting PDF text: {e}",
            "selected_prompt_text": ""
        }

DEFAULT_HYPERPARAM_ALIASES: Dict[str, List[str]] = {
    "learning_rate": ["learning_rate", "lr", "base_lr", "init_lr", "learning_rate_init", "lr_rate", "eta"],
    "batch_size": ["batch_size", "batchsize", "bs", "train_batch_size", "batch_sz", "b_size"],
    "epochs": ["epochs", "num_epochs", "max_epochs", "total_epochs", "n_epochs", "epoch", "num_epoch"],
    "weight_decay": ["weight_decay", "wd", "w_decay"],
    "seed": ["seed", "random_seed", "manual_seed"],
    "optimizer": ["optimizer", "opt", "optim"],
    "momentum": ["momentum", "mom"],
    "dropout": ["dropout", "drop_rate", "p_dropout", "dropout_rate"],
    "hidden_dim": ["hidden_dim", "hidden_size", "n_hidden", "d_model", "hidden_units", "n_embd"],
    "num_layers": ["num_layers", "n_layers", "n_layer", "layers", "depth"]
}

def extract_repo_config_keys(workspace_path: Optional[str]) -> Set[str]:
    if not workspace_path or not os.path.exists(workspace_path):
        return set()

    keys: Set[str] = set()
    ws = Path(workspace_path)

    for yml in list(ws.rglob("*.yaml")) + list(ws.rglob("*.yml")):
        try:
            import yaml
            content = yml.read_text(encoding="utf-8", errors="ignore")
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                for k in data.keys():
                    keys.add(str(k).lower())
        except Exception:
            pass

    for jf in ws.rglob("*.json"):
        if "package" in jf.name or "results" in jf.name:
            continue
        try:
            import json
            data = json.loads(jf.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, dict):
                for k in data.keys():
                    keys.add(str(k).lower())
        except Exception:
            pass

    for py_file in ws.rglob("*.py"):
        try:
            import ast
            code = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = getattr(node, "func", None)
                    if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                raw_opt = arg.value
                                clean_opt = raw_opt.lstrip("-").replace("-", "_").lower()
                                if clean_opt:
                                    keys.add(clean_opt)
        except Exception:
            pass

    return keys

def resolve_setting_key(
    paper_key: str,
    repo_workspace: Optional[str] = None,
    candidate_keys: Optional[List[str]] = None
) -> Tuple[Optional[str], str]:
    clean_key = paper_key.strip().lower().replace(" ", "_").replace("-", "_")
    available_repo_keys = extract_repo_config_keys(repo_workspace) if repo_workspace else set()

    alias_list = DEFAULT_HYPERPARAM_ALIASES.get(clean_key, [clean_key])
    for alias in alias_list:
        if alias in available_repo_keys:
            return (alias, "validated_in_repo")

    if candidate_keys:
        for cand in candidate_keys:
            cand_clean = cand.strip().lower().replace(" ", "_").replace("-", "_")
            if cand_clean in available_repo_keys:
                return (cand_clean, "validated_in_repo_from_candidate")

    if not available_repo_keys:
        return (alias_list[0], "alias_default")

    return (None, f"Setting '{paper_key}' not found in repo config or argument definitions")
