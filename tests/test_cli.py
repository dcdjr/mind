from mind.cli import main

def test_mind_home_runs(capsys):
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mind" in captured.out
    assert "local-first personal AI assistant" in captured.out

def test_mind_doctor_runs(capsys):
    exit_code = main(["doctor"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Mind doctor" in captured.out
    assert "Workspace: OK" in captured.out
