import pytest

from graph_fusion import mock_data


@pytest.fixture
def sample_model():
    return mock_data.generate_mock_model_grid(resolution_deg=2.0)


@pytest.fixture
def sample_obs():
    return mock_data.generate_mock_observations(n_sensors=30, seed=11)
