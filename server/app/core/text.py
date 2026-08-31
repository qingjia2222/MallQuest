def plain_text(value: str) -> str:
    """Keep chat output readable in clients that do not render Markdown."""
    return (value or "").replace("*", "")
