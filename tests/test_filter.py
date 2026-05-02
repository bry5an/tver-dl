import logging
import pytest
from tver_dl.filter import EpisodeFilter


@pytest.fixture
def filter():
    return EpisodeFilter(logging.getLogger("test"))


def ep(title="テスト第1話", season="本編"):
    return {"title": title, "season_name": season}


class TestTargetSeasons:
    def test_matching_season_included(self, filter):
        assert filter.should_download(ep(season="本編"), {"target_seasons": ["本編"]})

    def test_non_matching_season_excluded(self, filter):
        assert not filter.should_download(ep(season="予告編"), {"target_seasons": ["本編"]})

    def test_multiple_target_seasons(self, filter):
        cfg = {"target_seasons": ["本編", "スペシャル"]}
        assert filter.should_download(ep(season="スペシャル"), cfg)
        assert not filter.should_download(ep(season="予告編"), cfg)


class TestNoFilters:
    def test_no_filters_includes_everything(self, filter):
        assert filter.should_download(ep(), {})

    def test_empty_patterns_includes_everything(self, filter):
        assert filter.should_download(ep(), {"include_patterns": [], "exclude_patterns": []})


class TestExcludePatterns:
    def test_matching_exclude_pattern_excluded(self, filter):
        cfg = {"exclude_patterns": ["予告"]}
        assert not filter.should_download(ep(title="番組予告第1話"), cfg)

    def test_non_matching_exclude_pattern_included(self, filter):
        cfg = {"exclude_patterns": ["予告"]}
        assert filter.should_download(ep(title="本編第1話"), cfg)


class TestIncludePatterns:
    def test_matching_include_pattern_included(self, filter):
        cfg = {"include_patterns": ["本編"]}
        assert filter.should_download(ep(title="本編第1話"), cfg)

    def test_non_matching_include_pattern_excluded(self, filter):
        cfg = {"include_patterns": ["本編"]}
        assert not filter.should_download(ep(title="番組予告"), cfg)

    def test_exclude_takes_priority_over_include(self, filter):
        cfg = {"include_patterns": ["第1話"], "exclude_patterns": ["予告"]}
        assert not filter.should_download(ep(title="予告第1話"), cfg)
