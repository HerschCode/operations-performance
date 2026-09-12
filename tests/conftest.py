"""Session-wide test fixtures.

Found while auditing this project (the same bug, independently, also existed
in the sibling `operations-assistant` repo): 13 of 113 tests failed locally
whenever a real, populated `.env` file sat in the working directory (exactly
the state left behind after setting one up to run the live deployment).

Root cause: several auth tests do `monkeypatch.delenv("API_KEY")` /
`monkeypatch.delenv("API_KEYS")` then `importlib.reload(src.api.main)` to
simulate an unconfigured key -- but `src/api/main.py` calls `load_dotenv()`
at module level, and that reload re-executes it. `load_dotenv()`'s default
`override=False` only skips variables already present in `os.environ`; since
the monkeypatch just deleted the variable, `load_dotenv()` happily refills it
straight back from the physical `.env` file, silently undoing the monkeypatch
and cascading into 401s across test_api.py, test_auth.py, and
test_e2e_scenarios.py -- one root cause, not three different bugs.

This never showed up in CI, because `.env` is gitignored and never checked
out there -- purely a "works in CI, silently breaks locally" trap for anyone
running the suite from a checkout that also has a working `.env`.

Fix: neutralize `load_dotenv()` for the whole test session, AND
unconditionally strip `API_KEY`/`API_KEYS` from `os.environ` before every
single test (covers the same variable also getting set once, for real, the
moment pytest's collection phase first imports `src.api.main` -- before any
fixture, autouse or not, has run) -- so the suite behaves identically whether
or not a real, populated `.env` happens to be sitting in the working
directory, matching what CI already gets for free.
"""
import pytest


@pytest.fixture(autouse=True)
def _no_real_dotenv(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
