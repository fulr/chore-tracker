# Repository Notes

- This repository is a single Home Assistant custom integration. Integration setup, services, storage, WebSocket access, and frontend resource registration are in `custom_components/chore_tracker/__init__.py`; the Lovelace card and editor are in `custom_components/chore_tracker/chore-tracker-card.js`.
- Storage-backed Lovelace dashboards load the persisted resource; global `add_extra_js_url` injection is for non-storage/YAML paths. Avoid loading the card through both paths: duplicate script evaluation can break `customElements.define` and show a Lovelace configuration error.
- Bump `JS_VERSION` in `__init__.py` when changing the card JavaScript so the registered resource URL updates.
- Run frontend regression tests with `node --test tests/*.test.js`; run Home Assistant integration tests with `python -m pip install -r requirements_test.txt && pytest`. There is no lint/build configuration; focused syntax checks: `node --check custom_components/chore_tracker/chore-tracker-card.js` and `python -c 'import ast,pathlib; [ast.parse(p.read_text()) for p in pathlib.Path("custom_components/chore_tracker").glob("*.py")]'`.
