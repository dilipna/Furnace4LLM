import pytest
from furnace.guardian.tdist import t_cdf, t_quantile

# Two-sided / one-sided critical values from a standard Student-t table.
TABLE = [
    (0.95, 1, 6.3138),
    (0.95, 2, 2.9200),
    (0.95, 3, 2.3534),
    (0.95, 4, 2.1318),
    (0.95, 5, 2.0150),
    (0.95, 10, 1.8125),
    (0.95, 30, 1.6973),
    (0.975, 2, 4.3027),
    (0.975, 4, 2.7764),
    (0.975, 10, 2.2281),
    (0.975, 1000, 1.9623),
]


@pytest.mark.parametrize(("p", "df", "expected"), TABLE)
def test_quantile_matches_table(p, df, expected):
    assert t_quantile(p, df) == pytest.approx(expected, abs=2e-4)


def test_symmetry_and_median():
    assert t_quantile(0.5, 7) == 0.0
    assert t_quantile(0.05, 4) == pytest.approx(-t_quantile(0.95, 4))
    assert t_cdf(0.0, 3) == pytest.approx(0.5)


def test_fractional_df_between_neighbours():
    # Welch-Satterthwaite df is not an integer
    assert t_quantile(0.95, 4.0) > t_quantile(0.95, 4.5) > t_quantile(0.95, 5.0)


def test_rejects_bad_arguments():
    with pytest.raises(ValueError):
        t_quantile(1.0, 3)
    with pytest.raises(ValueError):
        t_quantile(0.9, 0)
