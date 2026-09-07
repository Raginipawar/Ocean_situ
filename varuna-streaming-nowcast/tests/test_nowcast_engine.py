import numpy as np
import pytest

from streaming_nowcast.nowcast_engine import NowcastEngine


def _tiny_engine() -> NowcastEngine:
    return NowcastEngine(in_channels=1, hidden_channels=4, kernel_size=3, seq_len=4, seed=1, device="cpu")


def test_train_without_real_data_uses_synthetic_fallback_and_completes():
    engine = _tiny_engine()
    history = engine.train(epochs=10, batch_size=4, patience=10, verbose=False)

    assert len(history.train_loss) == 10
    assert len(history.val_loss) == 10
    assert history.best_epoch >= 1
    assert all(v == v for v in history.train_loss)  # no NaN


def test_evaluate_returns_expected_keys_and_finite_values():
    engine = _tiny_engine()
    engine.train(epochs=10, batch_size=4, patience=10, verbose=False)

    result = engine.evaluate()

    assert set(result) == {"model_mse", "persistence_baseline_mse", "improvement_over_baseline_pct"}
    assert result["model_mse"] == result["model_mse"]  # not NaN
    assert result["persistence_baseline_mse"] >= 0


def test_predict_shape_matches_input_volume():
    engine = _tiny_engine()
    engine.train(epochs=5, batch_size=4, patience=10, verbose=False)

    x_test, _ = engine._test_cache
    recent = x_test[0].numpy() * engine.channel_std[0] + engine.channel_mean[0]

    pred = engine.predict(recent)

    assert pred.shape == recent.shape[1:]  # (C, D, H, W)
    assert np.isfinite(pred).all()


def test_predict_before_train_raises():
    engine = _tiny_engine()
    import pytest

    with pytest.raises(RuntimeError):
        engine.predict(np.zeros((4, 1, 1, 5, 5)))


def test_save_and_load_round_trip(tmp_path):
    engine = _tiny_engine()
    engine.train(epochs=5, batch_size=4, patience=10, verbose=False)
    before = engine.evaluate()

    path = tmp_path / "model.pt"
    engine.save(str(path))
    loaded = NowcastEngine.load(str(path))
    loaded._test_cache = engine._test_cache  # evaluate() needs a test set; reuse the same one

    after = loaded.evaluate()
    assert before["model_mse"] == pytest.approx(after["model_mse"], rel=1e-5)
