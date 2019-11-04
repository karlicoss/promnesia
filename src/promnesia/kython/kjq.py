"""
Some combinators for jq
"""

def pipe(*queries):
    return ' | '.join(queries)

def jdel(q):
    return f'del({q})'

def jq_del_all(*keys, split_by=10):
    parts = []
    # TODO shit. looks like query might be too long for jq...
    for q in range(0, len(keys), split_by):
        kk = keys[q: q + split_by]
        parts.append(jdel('.. | ({})'.format(', '.join('.' + k + '?' for k in kk))))
    return pipe(*parts)
