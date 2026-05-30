import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "build", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "our", "that", "the", "to", "we",
    "with", "you", "your",
}

SKILL_ALIASES = {
    "amazon web services": "aws",
    "aws": "aws",
    "ci cd": "ci/cd",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "continuous integration": "ci/cd",
    "docker": "docker",
    "fast api": "fastapi",
    "fastapi": "fastapi",
    "gen ai": "generative ai",
    "generative ai": "generative ai",
    "go lang": "golang",
    "golang": "golang",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "large language models": "llm",
    "llms": "llm",
    "llm": "llm",
    "machine learning": "machine learning",
    "ml": "machine learning",
    "natural language processing": "nlp",
    "nlp": "nlp",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "py": "python",
    "python": "python",
    "retrieval augmented generation": "rag",
    "rag": "rag",
    "react.js": "react",
    "reactjs": "react",
    "react": "react",
    "semantic search": "semantic search",
    "sql": "sql",
    "typescript": "typescript",
    "vector database": "vector database",
}

ATS_KEYWORDS = {
    *SKILL_ALIASES.keys(),
    *SKILL_ALIASES.values(),
    "agile", "ansible", "api", "argocd", "azure", "bash", "cka", "ckad",
    "cloud", "cloudwatch", "crossplane", "devops", "devsecops", "django",
    "eks", "elk", "flask", "gcp", "git", "github actions", "gitlab", "gitops",
    "grafana", "helm", "incident management", "java", "javascript", "jenkins",
    "jira", "kafka", "kubebuilder", "lambda", "linux", "microservices", "mqtt",
    "mongodb", "mysql", "nats", "node.js", "numpy", "oidc", "operator sdk",
    "pandas", "prometheus", "pytorch", "rancher", "rbac", "redis", "rest api",
    "scikit-learn", "spark", "splunk", "spring boot", "terraform",
    "typescript", "vpc",
}

CONCEPT_GROUPS = {
    "automation": {"automation", "ci/cd", "github actions", "jenkins", "gitops"},
    "cloud": {"aws", "azure", "gcp", "cloud", "eks", "vpc", "lambda", "cloudwatch"},
    "containers": {"docker", "kubernetes", "helm", "argocd", "rancher", "rbac"},
    "data": {"sql", "postgresql", "mysql", "mongodb", "redis", "spark", "pandas"},
    "observability": {"prometheus", "grafana", "splunk", "elk", "cloudwatch"},
    "platform": {"terraform", "ansible", "crossplane", "linux", "kubernetes", "helm"},
    "search-ai": {"machine learning", "nlp", "llm", "rag", "semantic search", "vector database"},
}


def clean(value: str) -> str:
    value = value.lower().replace("_", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_skill(value: str) -> str:
    normalized = clean(value)
    return SKILL_ALIASES.get(normalized, normalized)


def extract_ats_keywords(value: str) -> list[str]:
    lowered = clean(value)
    found = {
        normalize_skill(keyword)
        for keyword in ATS_KEYWORDS
        if re.search(rf"(?<![\w+#.-]){re.escape(keyword)}(?![\w+#.-])", lowered)
    }
    return sorted(found)


def semantic_similarity(left: str, right: str) -> float:
    left_terms = _semantic_terms(left)
    right_terms = _semantic_terms(right)
    if not left_terms or not right_terms:
        return 0.0
    overlap = sum(min(left_terms[term], right_terms[term]) for term in left_terms.keys() & right_terms.keys())
    left_norm = math.sqrt(sum(value * value for value in left_terms.values()))
    right_norm = math.sqrt(sum(value * value for value in right_terms.values()))
    return overlap / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _semantic_terms(value: str) -> Counter[str]:
    terms = Counter(tokenize(value))
    keywords = extract_ats_keywords(value)
    terms.update(f"skill:{keyword}" for keyword in keywords)
    for concept, members in CONCEPT_GROUPS.items():
        matched = sum(1 for keyword in keywords if keyword in members)
        if matched:
            terms[f"concept:{concept}"] += matched * 2
    return terms


def tokenize(value: str) -> list[str]:
    return [
        token for token in TOKEN_RE.findall(clean(value))
        if token not in STOP_WORDS and len(token) > 1
    ]


def jaccard(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    if not documents:
        return []
    query_tokens = tokenize(query)
    tokenized = [tokenize(document) for document in documents]
    avg_length = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
    document_frequency = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))

    scores = []
    for tokens in tokenized:
        frequencies = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = frequencies[token]
            if not frequency:
                continue
            frequency_in_docs = document_frequency[token]
            inverse_frequency = math.log(
                1 + (len(documents) - frequency_in_docs + 0.5) /
                (frequency_in_docs + 0.5)
            )
            length_adjustment = frequency + 1.2 * (
                1 - 0.75 + 0.75 * len(tokens) / max(avg_length, 1)
            )
            score += inverse_frequency * frequency * 2.2 / length_adjustment
        scores.append(score)

    maximum = max(scores, default=0)
    return [score / maximum if maximum else 0.0 for score in scores]
