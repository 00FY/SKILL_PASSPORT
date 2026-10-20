"""
Sample source files for the demo personas' "Defend Your Code" questions.

Demo passports have no real repository to clone, so these stand in for files from their linked repos.
They go through the same picker, sandbox and question builder as real code.
"""

PRIYA_FILES = {
    "repo_url": "https://github.com/priya/api-service",
    "commit": "4f2c9a1d7e3b8c0a5f6e2d1b9a8c7e6f5d4c3b2a",
    "files": {
        "app/utils/pagination.py": '''
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def paginate(items: list[int], page: int, size: int = DEFAULT_PAGE_SIZE) -> dict:
    """Slices a result set and reports whether more pages exist."""
    if page < 1:
        page = 1
    size = max(1, min(size, MAX_PAGE_SIZE))
    start = (page - 1) * size
    chunk = items[start:start + size]
    return {
        "page": page,
        "count": len(chunk),
        "has_next": start + size < len(items),
    }
''',
        "app/utils/text.py": '''
def slugify(title: str) -> str:
    """URL slug: lowercase words joined by single dashes."""
    cleaned = []
    for ch in title.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    if not slug:
        return "untitled"
    return slug[:40]


def parse_query(query: str) -> dict:
    """Parses 'a=1&b=2' into a dict; later keys win, blanks are skipped."""
    params = {}
    for part in query.split("&"):
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            params[key] = value.strip()
    return params
''',
        "app/services/orders.py": '''
STATUS_FLOW = {"pending": "paid", "paid": "shipped", "shipped": "delivered"}


def next_status(status: str, cancelled: bool = False) -> str:
    """Moves an order one step along its lifecycle."""
    if cancelled:
        if status in ("shipped", "delivered"):
            return status
        return "cancelled"
    if status not in STATUS_FLOW:
        return status
    nxt = STATUS_FLOW[status]
    return nxt


def order_total(prices: list[float], discount_pct: int) -> float:
    """Sum of line prices after a percentage discount, never below zero."""
    subtotal = 0.0
    for price in prices:
        if price > 0:
            subtotal += price
    if discount_pct > 50:
        discount_pct = 50
    total = subtotal * (100 - discount_pct) / 100
    return round(max(total, 0.0), 2)
''',
    },
}

JORDAN_FILES = {
    "repo_url": "https://github.com/jordan/task-manager",
    "commit": "9b1e4c7a2d5f8e0b3c6a9d2e5f8b1c4a7d0e3f6b",
    "files": {
        "tasks/stats.py": '''
def count_done(statuses: list[str]) -> int:
    """How many tasks are finished."""
    done = 0
    for status in statuses:
        if status == "done":
            done += 1
        elif status == "archived":
            done += 1
    if done > len(statuses):
        done = len(statuses)
    return done


def priority_label(score: int) -> str:
    """Maps a 0-10 urgency score to a label."""
    if score >= 8:
        label = "urgent"
    elif score >= 5:
        label = "high"
    elif score >= 2:
        label = "normal"
    else:
        label = "low"
    return label
''',
        "tasks/text_tools.py": '''
def word_counts(text: str) -> dict:
    """Counts words in a task description, ignoring case."""
    counts = {}
    for word in text.lower().split():
        word = word.strip(".,!?")
        if not word:
            continue
        counts[word] = counts.get(word, 0) + 1
    return counts


def short_title(title: str, limit: int = 10) -> str:
    """Shortens long titles for the task list."""
    title = title.strip()
    if len(title) <= limit:
        return title
    cut = title[:limit]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut + "..."
''',
    },
}

DEMO_DEFEND_FILES = {"priya": PRIYA_FILES, "jordan": JORDAN_FILES}
