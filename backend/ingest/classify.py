import re

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".txt",
}

_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Finance", ["financ", "corporate finance", " cf_", "(cf_", "value investing", "pricing strategies"]),
    ("Strategy", ["strategic", "strategy"]),
    ("Marketing", ["marketing", "mktg", "pricing", "platformization", "entertainment"]),
    ("Economics", ["economic", "microeconomics", "macroeconomics", " me_", "(me_", "mep_"]),
    (
        "Operations",
        ["operations", "supply chain", "logistics", "optimization", "optimisation", "experimentation"],
    ),
    ("Public Policy", ["policy", "government", "public private", "partnerships and coalitions"]),
    (
        "Organisational Behaviour",
        ["organi", "human resource", "hrm", "interpersonal", "talent", "power and politics", "ethics"],
    ),
    (
        "Technology",
        ["information technology", "machine learning", "data visualization", "regression methods",
         "internet-enabled", "streams, algorithms"],
    ),
]


def classify_category(course_name: str) -> str:
    lowered = course_name.lower()
    for category, keywords in _CATEGORY_RULES:
        if any(kw in lowered for kw in keywords):
            return category
    return "General Reading"


def classify_material_type(relative_path: str, filename: str) -> str:
    path_lower = relative_path.lower()
    name_lower = filename.lower()
    ext = _extension(filename)

    if "case material" in path_lower or "case stud" in path_lower:
        return "case_study"
    if re.search(r"\bcase[\s\-]", name_lower) or re.search(r"^\d+\s*case\b", name_lower):
        return "case_study"
    if "quiz" in path_lower or "quiz" in name_lower:
        return "assessment"
    if "outline" in path_lower or "outline" in name_lower or "syllabus" in name_lower:
        return "general"
    if ext in {".pptx", ".ppt"}:
        return "lecture_notes"
    if ext in {".xlsx", ".xls", ".csv"}:
        return "dataset"
    if ext in {".pdf", ".docx", ".doc", ".txt"}:
        return "textbook"
    return "general"


def extract_course_code(course_folder_name: str) -> str | None:
    match = re.search(r"\(([A-Za-z0-9\-&]+)_T\d\)", course_folder_name)
    if match:
        return match.group(1)
    return None


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""
