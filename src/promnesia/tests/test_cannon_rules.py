"""
Tests for the generic rule-based URL canonification system.
"""

import tempfile
from pathlib import Path

import pytest

from ..cannon_rules import (
    CanonifyRule,
    PatternVar,
    QueryParamRule,
    RuleSet,
    URLPattern,
    canonify_generic,
    get_default_rules,
    learn_rules_from_examples,
)


class TestURLPattern:
    """Tests for URLPattern class."""

    def test_simple_pattern_match(self):
        pattern = URLPattern('youtube.com/watch?v={video_id}')
        match = pattern.match('youtube.com/watch?v=abc123')
        assert match == {'video_id': 'abc123'}

    def test_pattern_no_match(self):
        pattern = URLPattern('youtube.com/watch?v={video_id}')
        match = pattern.match('twitter.com/user')
        assert match is None

    def test_pattern_substitute(self):
        pattern = URLPattern('youtube.com/watch?v={video_id}')
        result = pattern.substitute({'video_id': 'xyz789'})
        assert result == 'youtube.com/watch?v=xyz789'

    def test_multiple_variables(self):
        pattern = URLPattern('twitter.com/{user}/status/{tweet_id}')
        match = pattern.match('twitter.com/karlicoss/status/12345')
        assert match == {'user': 'karlicoss', 'tweet_id': '12345'}

    def test_custom_variable_pattern(self):
        pattern = URLPattern(
            'example.com/{id}',
            variables={'id': PatternVar('id', r'\d+')}
        )
        # Should match numbers
        assert pattern.match('example.com/123') == {'id': '123'}
        # Should not match non-numbers
        assert pattern.match('example.com/abc') is None


class TestCanonifyRule:
    """Tests for CanonifyRule class."""

    def test_apply_rule(self):
        rule = CanonifyRule(
            input_pattern=URLPattern('youtu.be/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
        )
        result = rule.apply('youtu.be/abc123')
        assert result == 'youtube.com/watch?v=abc123'

    def test_rule_no_match(self):
        rule = CanonifyRule(
            input_pattern=URLPattern('youtu.be/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
        )
        result = rule.apply('twitter.com/user')
        assert result is None

    def test_rule_serialization(self):
        rule = CanonifyRule(
            input_pattern=URLPattern('youtu.be/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
            priority=10,
            domain_hint='youtu.be',
            description='YouTube short URLs',
        )
        data = rule.to_dict()
        restored = CanonifyRule.from_dict(data)
        assert restored.input_pattern.template == rule.input_pattern.template
        assert restored.output_pattern.template == rule.output_pattern.template
        assert restored.priority == rule.priority


class TestQueryParamRule:
    """Tests for QueryParamRule class."""

    def test_filter_params_keep(self):
        rule = QueryParamRule(
            domain='youtube.com',
            keep=['v', 't', 'list'],
            remove={'index', 'feature'},
        )
        params = [('v', 'abc'), ('index', '5'), ('t', '10s'), ('feature', 'share')]
        filtered = rule.filter_params(params)
        # Should keep v and t in that order, remove index and feature
        assert filtered == [('v', 'abc'), ('t', '10s')]

    def test_filter_params_keep_all(self):
        rule = QueryParamRule(
            domain='example.com',
            keep_all=True,
            remove={'tracking'},
        )
        params = [('page', '1'), ('tracking', 'xyz'), ('sort', 'date')]
        filtered = rule.filter_params(params)
        assert filtered == [('page', '1'), ('sort', 'date')]


class TestRuleSet:
    """Tests for RuleSet class."""

    def test_add_and_apply_rule(self):
        rules = RuleSet()
        rules.add_rule(CanonifyRule(
            input_pattern=URLPattern('youtu.be/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
        ))
        result = rules.apply('youtu.be/test123')
        assert result == 'youtube.com/watch?v=test123'

    def test_priority_ordering(self):
        rules = RuleSet()
        # Add low priority rule first
        rules.add_rule(CanonifyRule(
            input_pattern=URLPattern('example.com/{path}'),
            output_pattern=URLPattern('fallback.com/{path}'),
            priority=0,
        ))
        # Add high priority rule second
        rules.add_rule(CanonifyRule(
            input_pattern=URLPattern('example.com/special'),
            output_pattern=URLPattern('special.com'),
            priority=10,
        ))
        # High priority rule should match first
        result = rules.apply('example.com/special')
        assert result == 'special.com'

    def test_save_and_load(self):
        rules = RuleSet()
        rules.add_rule(CanonifyRule(
            input_pattern=URLPattern('youtu.be/{video_id}'),
            output_pattern=URLPattern('youtube.com/watch?v={video_id}'),
        ))
        rules.add_domain_alias('m.youtube.', 'youtube.')

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = Path(f.name)

        try:
            rules.save(path)

            loaded = RuleSet()
            loaded.load(path)

            assert len(loaded.rules) == 1
            assert 'm.youtube.' in loaded.domain_aliases
        finally:
            path.unlink()


class TestRuleLearning:
    """Tests for rule learning from examples."""

    def test_learn_domain_alias(self):
        examples = [
            ('m.youtube.com/watch?v=abc', 'youtube.com/watch?v=abc'),
        ]
        rules = learn_rules_from_examples(examples)
        # Should have learned a domain alias
        assert 'm.youtube.com' in rules.domain_aliases or len(rules.rules) > 0

    def test_learn_multiple_examples(self):
        examples = [
            ('https://m.youtube.com/watch?v=abc', 'youtube.com/watch?v=abc'),
            ('https://mobile.twitter.com/user', 'twitter.com/user'),
        ]
        rules = learn_rules_from_examples(examples)
        # Should have learned something from each example
        assert len(rules.rules) + len(rules.domain_aliases) >= 1


class TestDefaultRules:
    """Tests for the default built-in rules."""

    def test_default_rules_created(self):
        rules = get_default_rules()
        # Should have domain aliases
        assert len(rules.domain_aliases) > 0
        # Should have query rules
        assert 'youtube.com' in rules.query_rules
        # Should have transformation rules
        assert len(rules.rules) > 0

    def test_youtube_short_url_rule(self):
        rules = get_default_rules()
        result = rules.apply('youtu.be/abc123')
        assert result == 'youtube.com/watch?v=abc123'

    def test_youtube_embed_url_rule(self):
        rules = get_default_rules()
        result = rules.apply('youtube.com/embed/xyz789')
        assert result == 'youtube.com/watch?v=xyz789'


class TestCanonifyGeneric:
    """Tests for the canonify_generic function."""

    def test_basic_canonification(self):
        rules = get_default_rules()
        # Should remove www and protocol
        result = canonify_generic('https://www.example.com/page', rules)
        assert result == 'example.com/page'

    def test_trailing_slash_removal(self):
        rules = get_default_rules()
        result = canonify_generic('https://example.com/page/', rules)
        assert result == 'example.com/page'


# Integration tests - compare with original cannon.py behavior
class TestBackwardsCompatibility:
    """Ensure new system can replicate original cannon.py behavior."""

    @pytest.mark.parametrize(('input_url', 'expected'), [
        ('youtu.be/abc123', 'youtube.com/watch?v=abc123'),
        ('youtube.com/embed/xyz789', 'youtube.com/watch?v=xyz789'),
        ('twitter.com/home', 'twitter.com'),
        ('twitter.com/explore', 'twitter.com'),
    ])
    def test_url_transformations(self, input_url, expected):
        rules = get_default_rules()
        result = rules.apply(input_url)
        assert result == expected

    def test_domain_aliases_defined(self):
        rules = get_default_rules()
        # Check key domain aliases are present
        assert 'm.youtube.' in rules.domain_aliases
        assert 'mobile.twitter.' in rules.domain_aliases
        assert 'm.reddit.' in rules.domain_aliases

    def test_youtube_query_rule(self):
        rules = get_default_rules()
        qrule = rules.query_rules['youtube.com']
        assert 'v' in qrule.keep
        assert 't' in qrule.keep
        assert 'index' in qrule.remove
        assert 'feature' in qrule.remove
