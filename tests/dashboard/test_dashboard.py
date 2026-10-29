from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from smartroute.dashboard.service import (
    artifact_path,
    export_json,
    import_result,
    simulate,
    summary_frame,
)
from smartroute.engine.topology import catalog_config


def test_real_export_roundtrip_and_write_boundary():
    result = simulate(catalog_config(), "reactive")
    assert import_result(export_json(result)) == result
    assert summary_frame([result]).iloc[0].generated == result.metrics.generated
    with pytest.raises(ValueError):
        artifact_path("../escape.json")


def test_dashboard_real_run_replay_and_failure():
    app = AppTest.from_file(
        Path("src/smartroute/dashboard/app.py").resolve(), default_timeout=30
    ).run()
    assert not app.exception
    assert "Your network, ready to explore" in [s.value for s in app.subheader]
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state.result.policy_name == "reactive"
    assert len(app.metric) == 5
    app.slider(key="replay_index").set_value(25).run()
    assert not app.exception
    assert "Network at 5.0 s" in [s.value for s in app.subheader]
    app.sidebar.selectbox[1].select("failure").run()
    app.sidebar.selectbox[2].select("predictive-trend").run()
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state.result.config.scenario_id == "failure"
    assert app.session_state.result.decisions[0].decision.forecasts[0].reason.startswith("warm-up")
    # Whether a forced repair occurs depends on which path the flow holds at the outage;
    # flap damping often keeps it off the failing link. Repair logic has its own unit tests.
    result = app.session_state.result
    assert len(result.config.events) == 2 and result.metrics.pending == 0
    assert result.metrics.delivery_ratio > 0.9
