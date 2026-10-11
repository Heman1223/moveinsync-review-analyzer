from datetime import date

from src import fix_tracker


def test_set_update_and_remove(tmp_path):
    path = tmp_path / "tracker.csv"
    fix_tracker.set_status("app1", "login", "In progress", date(2026, 9, 1), path=path)
    fix_tracker.set_status("app1", "login", "Fix shipped", date(2026, 10, 1), "v12.20", path=path)
    fix_tracker.set_status("app2", "login", "In progress", date(2026, 9, 1), path=path)
    df = fix_tracker.load("app1", path=path)
    assert len(df) == 1 and df.iloc[0]["status"] == "Fix shipped" and df.iloc[0]["note"] == "v12.20"
    fix_tracker.remove("app1", "login", path=path)
    assert fix_tracker.load("app1", path=path).empty
    assert len(fix_tracker.load("app2", path=path)) == 1


def test_missing_file_is_empty(tmp_path):
    assert fix_tracker.load(path=tmp_path / "none.csv").empty
