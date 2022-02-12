def obsidian_replacer(p: str) -> str:
    if not p.startswith("editor://") or not p.endswith('.md'):
        return p
    
    path = p.split('/', 2)[-1]
    
    uri = f"obsidian://{path}"
    return uri
