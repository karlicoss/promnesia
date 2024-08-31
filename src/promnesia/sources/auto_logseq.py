import os.path
import urllib.parse


def logseq_replacer(path: str, root: str) -> str:
    if not path.startswith("editor://") or not (path.endswith((".md", ".org"))):
        return path

    graph = os.path.basename(root)  # noqa: PTH119
    page_name = os.path.basename(path).rsplit('.', 1)[0]  # noqa: PTH119
    encoded_page_name = urllib.parse.quote(page_name)

    uri = f"logseq://graph/{graph}?page={encoded_page_name}"

    return uri
