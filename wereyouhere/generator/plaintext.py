# https://linux-and-mac-hacks.blogspot.co.uk/2013/04/use-grep-and-regular-expressions-to.html
_URL_REGEX = r'\b(https?|ftp|file)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]*[-A-Za-z0-9+&@#/%=~_|]'

def extract_from_path(path: str) -> str:
    # -n to output line numbers so we could restore context
    # -I to ignore binaries
    return  rf"""grep --color=never -Eo -I -r -n --exclude="*.html~" --exclude="*.html" --exclude-dir=".git" '{_URL_REGEX}' {path}"""
