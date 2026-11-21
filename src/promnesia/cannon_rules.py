"""
Generic rule-based URL canonification system.

This module provides a framework for learning and applying URL canonification rules
from examples. Instead of hardcoding site-specific rules, rules can be:

1. Learned automatically from input/output URL pairs
2. Defined declaratively in configuration files
3. Extended by users without modifying source code

Background & Prior Art
----------------------

URL canonification (or normalization) is the process of converting URLs to a
standard, consistent format. This is essential for:
- Deduplication: recognizing that different URLs point to the same content
- History tracking: grouping visits to the same page
- Link analysis: understanding relationships between pages

Traditional approaches to URL canonification rely on hardcoded rules for specific
domains (e.g., "remove 'utm_*' parameters", "convert m.youtube.com to youtube.com").
This has limitations:
- Requires manual maintenance as websites change
- Cannot easily adapt to new sites
- Difficult for users to customize

This module takes a more generic approach inspired by techniques from:

1. **Anti-unification** (Plotkin, 1970): Finding the least general generalization
   of multiple examples. Given URLs that should canonify to the same result, we
   find the minimal pattern that captures all of them.

2. **Program synthesis by example** (Gulwani, 2011): Learning programs from
   input/output examples. We treat URL canonification as a string transformation
   program that can be inferred from examples.

3. **URL pattern mining** (used in web crawling): Identifying patterns in URLs
   to understand site structure. We use similar techniques to recognize which
   parts of URLs are meaningful vs. tracking/session parameters.

The implementation uses:
- LCS (Longest Common Subsequence) for aligning input/output URL tokens
- Pattern templates with named variables for generalizing specific values
- Rule priority ordering for handling overlapping patterns

Usage Examples
--------------

Basic rule application:
    >>> rules = get_default_rules()
    >>> rules.apply('youtu.be/abc123')
    'youtube.com/watch?v=abc123'

Learning from examples:
    >>> rules = RuleSet()
    >>> rules.learn([
    ...     ('https://m.youtube.com/watch?v=abc', 'youtube.com/watch?v=abc'),
    ...     ('https://mobile.twitter.com/user', 'twitter.com/user'),
    ... ])
    >>> rules.apply('m.youtube.com/watch?v=xyz')
    'youtube.com/watch?v=xyz'

Saving/loading rules:
    >>> rules.save('my_rules.json')
    >>> loaded_rules = RuleSet()
    >>> loaded_rules.load('my_rules.json')

Custom rule definition:
    >>> rule = CanonifyRule(
    ...     input_pattern=URLPattern('example.com/article/{id}'),
    ...     output_pattern=URLPattern('example.com/a/{id}'),
    ...     description='Shorten article URLs',
    ... )
    >>> rules.add_rule(rule)

Key Classes
-----------
- URLPattern: A URL template with placeholders (e.g., '{subdomain}.youtube.com/{path}')
- CanonifyRule: A transformation from input pattern to output pattern
- QueryParamRule: Specifies query parameter handling for a domain
- RuleSet: A collection of rules that can be applied to canonify URLs
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit


@dataclass
class PatternVar:
    """A variable in a pattern that can match URL components."""

    name: str
    pattern: str = r'[^/&?#]+'  # default: match any non-delimiter chars

    def to_regex(self) -> str:
        return f'(?P<{self.name}>{self.pattern})'

    def __str__(self) -> str:
        return f'{{{self.name}}}'


@dataclass
class URLPattern:
    """
    A pattern for matching and transforming URLs.

    Patterns can contain:
    - Literal strings that must match exactly
    - Variables like {domain}, {path}, {id} that capture URL components
    - Optional segments like [/optional]

    Example patterns:
    - '{subdomain}.youtube.com/watch?v={video_id}'
    - 'twitter.com/{user}/status/{tweet_id}'
    """

    template: str
    variables: dict[str, PatternVar] = field(default_factory=dict)

    def __post_init__(self):
        # Auto-detect variables from template
        var_pattern = re.compile(r'\{(\w+)(?::([^}]+))?\}')
        for match in var_pattern.finditer(self.template):
            name = match.group(1)
            pattern = match.group(2) or r'[^/&?#]+'
            if name not in self.variables:
                self.variables[name] = PatternVar(name, pattern)

    def to_regex(self) -> re.Pattern[str]:
        """Convert pattern to a compiled regex."""
        regex = re.escape(self.template)
        for name, var in self.variables.items():
            # Replace escaped placeholder with regex group
            escaped_placeholder = re.escape(f'{{{name}}}')
            regex = regex.replace(escaped_placeholder, var.to_regex())

            # Also handle patterns with explicit regex like {name:pattern}
            escaped_with_pattern = re.escape(f'{{{name}:{var.pattern}}}')
            regex = regex.replace(escaped_with_pattern, var.to_regex())
        return re.compile(regex)

    def match(self, url: str) -> dict[str, str] | None:
        """Try to match URL against this pattern, returning captured variables."""
        m = self.to_regex().fullmatch(url)
        if m:
            return m.groupdict()
        return None

    def substitute(self, variables: dict[str, str]) -> str:
        """Substitute variables into the template."""
        result = self.template
        for name, value in variables.items():
            result = result.replace(f'{{{name}}}', value)
            # Also handle patterns with explicit regex
            var = self.variables.get(name)
            if var:
                result = result.replace(f'{{{name}:{var.pattern}}}', value)
        return result


@dataclass
class CanonifyRule:
    """
    A rule for transforming URLs to their canonical form.

    A rule consists of:
    - input_pattern: Pattern to match input URLs
    - output_pattern: Pattern to generate canonical URLs
    - priority: Higher priority rules are tried first (default: 0)
    - domain_hint: Optional domain to restrict when rule applies
    """

    input_pattern: URLPattern
    output_pattern: URLPattern
    priority: int = 0
    domain_hint: str | None = None
    description: str = ''

    def apply(self, url: str) -> str | None:
        """
        Try to apply this rule to canonify a URL.

        Returns the canonical URL if the rule matches, None otherwise.
        """
        match = self.input_pattern.match(url)
        if match is None:
            return None
        return self.output_pattern.substitute(match)

    def to_dict(self) -> dict[str, Any]:
        """Serialize rule to a dictionary."""
        return {
            'input': self.input_pattern.template,
            'output': self.output_pattern.template,
            'priority': self.priority,
            'domain_hint': self.domain_hint,
            'description': self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonifyRule:
        """Deserialize rule from a dictionary."""
        return cls(
            input_pattern=URLPattern(data['input']),
            output_pattern=URLPattern(data['output']),
            priority=data.get('priority', 0),
            domain_hint=data.get('domain_hint'),
            description=data.get('description', ''),
        )


# Default query params to remove (tracking, analytics, etc.)
default_qremove = {
    'utm_source',
    'utm_campaign',
    'utm_content',
    'utm_medium',
    'utm_term',
    'utm_umg_et',
    'usg',
    'hl',
    'vl',
    'utf8',
    'ref',
    'source',
    'fbclid',
    'gclid',
}


@dataclass
class QueryParamRule:
    """
    Rule for handling query parameters during canonification.

    Specifies which query parameters to keep, remove, or reorder for a domain.
    """

    domain: str
    keep: list[str] = field(default_factory=list)  # params to keep (in order)
    remove: set[str] = field(default_factory=set)  # params to explicitly remove
    keep_all: bool = False  # if True, keep all params not in remove

    def filter_params(self, params: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Filter and order query parameters according to this rule."""
        if self.keep_all:
            # Keep all except those in remove set
            return [(k, v) for k, v in params if k not in self.remove]

        # Build order map from keep list
        keep_order = {k: i for i, k in enumerate(self.keep)}
        default_qkeep = ['id', 't', 'p']  # common params to keep
        for i, k in enumerate(default_qkeep):
            if k not in keep_order:
                keep_order[k] = len(self.keep) + i

        # Filter and sort
        filtered = []
        for k, v in params:
            if k in keep_order:
                filtered.append((keep_order[k], k, v))
            elif k not in self.remove and k not in default_qremove:
                # Unknown param - drop by default for better canonification
                pass
        filtered.sort(key=lambda x: x[0])
        return [(k, v) for _, k, v in filtered]


class RuleSet:
    """
    A collection of canonification rules that can be applied to URLs.

    Rules can be:
    - Added manually via add_rule()
    - Learned from examples via learn()
    - Loaded from configuration files via load()
    """

    def __init__(self):
        self.rules: list[CanonifyRule] = []
        self.query_rules: dict[str, QueryParamRule] = {}
        self.domain_aliases: dict[str, str] = {}  # maps alternative domains to canonical

    def add_rule(self, rule: CanonifyRule) -> None:
        """Add a canonification rule."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)  # higher priority first

    def add_domain_alias(self, alias: str, canonical: str) -> None:
        """Add a domain alias (e.g., 'm.youtube.com' -> 'youtube.com')."""
        self.domain_aliases[alias] = canonical

    def add_query_rule(self, rule: QueryParamRule) -> None:
        """Add a query parameter handling rule."""
        self.query_rules[rule.domain] = rule

    def apply(self, url: str) -> str | None:
        """
        Apply rules to canonify a URL.

        Returns the canonical URL if any rule matches, None otherwise.
        """
        for rule in self.rules:
            result = rule.apply(url)
            if result is not None:
                return result
        return None

    def learn(self, examples: list[tuple[str, str]]) -> list[CanonifyRule]:
        """
        Learn canonification rules from input/output URL pairs.

        This uses a simple pattern inference algorithm:
        1. Parse both URLs to extract components
        2. Find common structure and variable parts
        3. Generate pattern templates

        Returns the learned rules.
        """
        learned = []
        for input_url, output_url in examples:
            rule = self._infer_rule(input_url, output_url)
            if rule:
                learned.append(rule)
                self.add_rule(rule)
        return learned

    def _infer_rule(self, input_url: str, output_url: str) -> CanonifyRule | None:
        """Infer a canonification rule from a single example."""
        # Normalize URLs for comparison
        input_norm = self._normalize_for_learning(input_url)
        output_norm = self._normalize_for_learning(output_url)

        # Add scheme if missing (urlsplit needs it to parse netloc)
        if not input_norm.startswith(('http://', 'https://')):
            input_norm = 'http://' + input_norm
        if not output_norm.startswith(('http://', 'https://')):
            output_norm = 'http://' + output_norm

        # Parse URLs
        input_parts = urlsplit(input_norm)
        output_parts = urlsplit(output_norm)

        # Simple case: domain substitution (path and query are the same, only domain differs)
        path_query_same = (
            input_parts.path == output_parts.path
            and input_parts.query == output_parts.query
        )
        if path_query_same:
            # Check if this is just a domain change
            input_dom = input_parts.netloc
            output_dom = output_parts.netloc

            if input_dom != output_dom:
                # Learn domain alias
                self.add_domain_alias(input_dom, output_dom)

                # Create rule for this specific pattern
                input_pattern = f'{input_dom}{{path}}'
                output_pattern = f'{output_dom}{{path}}'

                return CanonifyRule(
                    input_pattern=URLPattern(input_pattern, {'path': PatternVar('path', r'.*')}),
                    output_pattern=URLPattern(output_pattern),
                    domain_hint=input_dom,
                    description=f'Learned: {input_dom} -> {output_dom}',
                )

        # Try to find common structure with variable parts
        rule = self._infer_pattern_rule(input_norm, output_norm)
        if rule:
            return rule

        return None

    def _infer_pattern_rule(self, input_url: str, output_url: str) -> CanonifyRule | None:
        """
        Infer a pattern-based rule by finding the longest common subsequence
        and treating differences as variables.
        """
        # Split URLs into tokens
        input_tokens = self._tokenize_url(input_url)
        output_tokens = self._tokenize_url(output_url)

        # Find alignment between tokens
        alignment = self._align_tokens(input_tokens, output_tokens)
        if not alignment:
            return None

        # Generate patterns from alignment
        input_pattern, output_pattern, variables = self._patterns_from_alignment(
            input_tokens, output_tokens, alignment
        )

        if not variables:
            # No variables found - not a generalizable pattern
            return None

        return CanonifyRule(
            input_pattern=URLPattern(input_pattern, variables),
            output_pattern=URLPattern(output_pattern),
            description=f'Learned pattern: {input_pattern} -> {output_pattern}',
        )

    def _normalize_for_learning(self, url: str) -> str:
        """Normalize URL for pattern learning."""
        # Remove protocol
        url = re.sub(r'^https?://', '', url)
        # Remove www prefix
        url = re.sub(r'^www\.', '', url)
        return url

    def _tokenize_url(self, url: str) -> list[str]:
        """Split URL into tokens for pattern matching."""
        # Split on delimiters but keep them
        tokens = re.split(r'([/&?=#])', url)
        return [t for t in tokens if t]

    def _align_tokens(
        self, input_tokens: list[str], output_tokens: list[str]
    ) -> list[tuple[int, int]] | None:
        """
        Find alignment between input and output tokens using LCS.
        Returns list of (input_idx, output_idx) pairs for aligned tokens.
        """
        m, n = len(input_tokens), len(output_tokens)
        if m == 0 or n == 0:
            return None

        # Build LCS table
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if input_tokens[i - 1] == output_tokens[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        # Backtrack to find alignment
        alignment = []
        i, j = m, n
        while i > 0 and j > 0:
            if input_tokens[i - 1] == output_tokens[j - 1]:
                alignment.append((i - 1, j - 1))
                i -= 1
                j -= 1
            elif dp[i - 1][j] > dp[i][j - 1]:
                i -= 1
            else:
                j -= 1

        alignment.reverse()
        return alignment if alignment else None

    def _patterns_from_alignment(
        self,
        input_tokens: list[str],
        output_tokens: list[str],
        alignment: list[tuple[int, int]],
    ) -> tuple[str, str, dict[str, PatternVar]]:
        """Generate input/output patterns from token alignment."""
        variables: dict[str, PatternVar] = {}
        var_counter = 0

        input_pattern_parts = []
        output_pattern_parts = []

        prev_in, prev_out = -1, -1

        for in_idx, out_idx in alignment:
            # Handle unaligned tokens before this alignment
            if in_idx > prev_in + 1:
                # There are input tokens that don't appear in output
                # These are removed in canonification
                unaligned = ''.join(input_tokens[prev_in + 1 : in_idx])
                input_pattern_parts.append(re.escape(unaligned))

            if out_idx > prev_out + 1:
                # There are output tokens that don't appear in input
                # These are added in canonification
                unaligned = ''.join(output_tokens[prev_out + 1 : out_idx])
                output_pattern_parts.append(unaligned)

            # Add aligned token
            token = input_tokens[in_idx]
            if self._is_variable_candidate(token):
                var_name = f'var{var_counter}'
                var_counter += 1
                variables[var_name] = PatternVar(var_name, self._infer_var_pattern(token))
                input_pattern_parts.append(f'{{{var_name}}}')
                output_pattern_parts.append(f'{{{var_name}}}')
            else:
                input_pattern_parts.append(token)
                output_pattern_parts.append(token)

            prev_in, prev_out = in_idx, out_idx

        # Handle trailing tokens
        if prev_in < len(input_tokens) - 1:
            trailing = ''.join(input_tokens[prev_in + 1 :])
            input_pattern_parts.append(re.escape(trailing))
        if prev_out < len(output_tokens) - 1:
            trailing = ''.join(output_tokens[prev_out + 1 :])
            output_pattern_parts.append(trailing)

        return ''.join(input_pattern_parts), ''.join(output_pattern_parts), variables

    def _is_variable_candidate(self, token: str) -> bool:
        """Check if a token should be treated as a variable."""
        # IDs, hashes, usernames, etc. are variable candidates
        if token in ('/', '&', '?', '=', '#'):
            return False
        if re.match(r'^[a-z]+$', token):  # lowercase words are usually fixed
            return False
        if re.match(r'^\d+$', token):  # pure numbers are often IDs
            return True
        if re.match(r'^[\w-]{5,}$', token):  # long alphanumeric strings
            return True
        return False

    def _infer_var_pattern(self, sample: str) -> str:
        """Infer a regex pattern from a sample value."""
        if re.match(r'^\d+$', sample):
            return r'\d+'
        if re.match(r'^[\w-]+$', sample):
            return r'[\w-]+'
        return r'[^/&?#]+'

    def save(self, path: Path | str) -> None:
        """Save rules to a JSON file."""
        path = Path(path)
        data = {
            'rules': [r.to_dict() for r in self.rules],
            'domain_aliases': self.domain_aliases,
            'query_rules': {
                domain: {
                    'keep': rule.keep,
                    'remove': list(rule.remove),
                    'keep_all': rule.keep_all,
                }
                for domain, rule in self.query_rules.items()
            },
        }
        path.write_text(json.dumps(data, indent=2))

    def load(self, path: Path | str) -> None:
        """Load rules from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text())

        for rule_data in data.get('rules', []):
            self.add_rule(CanonifyRule.from_dict(rule_data))

        self.domain_aliases.update(data.get('domain_aliases', {}))

        for domain, qrule_data in data.get('query_rules', {}).items():
            self.add_query_rule(
                QueryParamRule(
                    domain=domain,
                    keep=qrule_data.get('keep', []),
                    remove=set(qrule_data.get('remove', [])),
                    keep_all=qrule_data.get('keep_all', False),
                )
            )


def learn_rules_from_examples(examples: list[tuple[str, str]]) -> RuleSet:
    """
    Convenience function to learn a RuleSet from examples.

    Args:
        examples: List of (input_url, expected_canonical_url) pairs

    Returns:
        A RuleSet containing learned rules
    """
    ruleset = RuleSet()
    ruleset.learn(examples)
    return ruleset


# Default built-in rules (equivalent to current hardcoded rules in cannon.py)
def get_default_rules() -> RuleSet:
    """
    Get a RuleSet with the default built-in canonification rules.

    These rules are equivalent to the hardcoded rules in cannon.py but
    expressed in the generic rule format.
    """
    rules = RuleSet()

    # Domain aliases (mobile/alternative domains)
    domain_aliases = [
        ('m.youtube.', 'youtube.'),
        ('studio.youtube.', 'youtube.'),
        ('mobile.twitter.', 'twitter.'),
        ('m.twitter.', 'twitter.'),
        ('nitter.net', 'twitter.com'),
        ('m.reddit.', 'reddit.'),
        ('old.reddit.', 'reddit.'),
        ('i.reddit.', 'reddit.'),
        ('pay.reddit.', 'reddit.'),
        ('np.reddit.', 'reddit.'),
        ('m.facebook.', 'facebook.'),
        ('getpocket.', 'app.getpocket.'),
    ]
    for alias, canonical in domain_aliases:
        rules.add_domain_alias(alias, canonical)

    # Query param rules for specific domains
    rules.add_query_rule(
        QueryParamRule(
            domain='youtube.com',
            keep=['v', 't', 'list'],
            remove={
                'time_continue',
                'index',
                'feature',
                'lc',
                'app',
                'start_radio',
                'pbjreload',
                'annotation_id',
                'flow',
                'sort',
                'view',
                'enablejsapi',
                'wmode',
                'html5',
                'autoplay',
                'ar',
                'gl',
                'sub_confirmation',
                'shelf_id',
                'disable_polymer',
                'spfreload',
                'src_vid',
                'origin',
                'rel',
                'shuffle',
                'nohtml5',
                'showinfo',
                'ab_channel',
                'start',
                'ebc',
                'ref',
                'view_as',
                'fr',
                'redirect_to_creator',
                'sp',
                'noapp',
                'client',
                'sa',
                'ob',
                'fbclid',
                'noredirect',
                'zg_or',
                'ved',
            },
        )
    )

    rules.add_query_rule(
        QueryParamRule(
            domain='github.com',
            keep=['q'],
            remove={'o', 's', 'type', 'tab', 'code', 'privacy', 'fork'},
        )
    )

    rules.add_query_rule(
        QueryParamRule(
            domain='facebook.com',
            keep=['fbid', 'story_fbid'],
            remove={
                'set',
                'type',
                'fref',
                'locale2',
                '__tn__',
                'notif_t',
                'ref',
                'notif_id',
                'hc_ref',
                'acontext',
                'multi_permalinks',
                'no_hist',
                'next',
                'bucket_id',
                'eid',
                'tab',
                'active_tab',
                'source',
                'tsid',
                'refsrc',
                'pnref',
                'rc',
                '_rdr',
                'src',
                'hc_location',
                'section',
                'permPage',
                'soft',
                'pn_ref',
                'action',
                'ti',
                'aref',
                'event_time_id',
                'action_history',
                'filter',
                'ref_notif_type',
                'has_source',
                'source_newsfeed_story_type',
            },
        )
    )

    # URL transformation rules
    rules.add_rule(
        CanonifyRule(
            input_pattern=URLPattern('youtu.be/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
            domain_hint='youtu.be',
            description='YouTube short URLs',
        )
    )

    rules.add_rule(
        CanonifyRule(
            input_pattern=URLPattern('youtube.com/embed/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
            domain_hint='youtube.com',
            description='YouTube embed URLs',
        )
    )

    rules.add_rule(
        CanonifyRule(
            input_pattern=URLPattern('twitter.com/home'),
            output_pattern=URLPattern('twitter.com'),
            domain_hint='twitter.com',
            description='Twitter home page',
        )
    )

    rules.add_rule(
        CanonifyRule(
            input_pattern=URLPattern('twitter.com/explore'),
            output_pattern=URLPattern('twitter.com'),
            domain_hint='twitter.com',
            description='Twitter explore page',
        )
    )

    return rules


def canonify_generic(url: str, rules: RuleSet) -> str:
    """
    Canonify a URL using the provided RuleSet.

    This is a more generic version of the canonify() function that uses
    declarative rules instead of hardcoded logic.
    """
    # First try to apply transformation rules
    result = rules.apply(url)
    if result:
        return result

    # Fall back to basic canonification (protocol removal, domain alias, query params)
    parts = urlsplit(url)

    # Normalize domain
    domain = parts.netloc.lower()
    domain = domain.removeprefix('www.')
    domain = domain.removeprefix('amp.')

    # Apply domain aliases
    for alias, canonical in rules.domain_aliases.items():
        if domain.startswith(alias):
            domain = canonical + domain[len(alias) :]
            break

    # Filter query params
    qrule = rules.query_rules.get(domain)
    query_params = parse_qsl(parts.query, keep_blank_values=True)
    if qrule:
        query_params = qrule.filter_params(query_params)
    else:
        # Default: remove tracking params
        query_params = [(k, v) for k, v in query_params if k not in default_qremove]

    query = urlencode(query_params)

    # Rebuild URL without protocol
    result = domain + parts.path
    if query:
        result += '?' + query
    result = result.removesuffix('/')

    return result
