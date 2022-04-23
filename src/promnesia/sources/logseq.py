import os.path

def logseq_replacer(path: str, root: str) -> str:
    if not path.startswith("editor://") or not path.endswith('.md'):
        return path
        
    graph = os.path.basename(root)
    page_name = os.path.basename(path).split('.')[0]
    
    uri = f"logseq://graph/{graph}?page={page_name}"

    return uri
