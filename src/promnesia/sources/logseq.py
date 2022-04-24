import os.path

def logseq_replacer(path: str, root: str) -> str:
    if not path.startswith("editor://") or not (path.endswith('.md') or path.endswith('.org')):
        return path
        
    graph = os.path.basename(root)
    page_name = os.path.basename(path).rsplit('.', 1)[0]
    
    uri = f"logseq://graph/{graph}?page={page_name}"

    return uri
