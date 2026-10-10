# Chore Tracker

A Home Assistant custom integration to track household chore minutes for children.

## Features

- Track minutes spent on household chores per child
- Multiple children supported
- Add entries with optional notes
- Overview of total minutes per child
- Full entry history
- Reset per child
- German UI
- Configurable via the Lovelace card editor (no YAML needed)

## Installation via HACS

1. In HACS, go to **Integrations** → three-dot menu → **Custom repositories**
2. Add this repository URL, category: **Integration**
3. Install **Chore Tracker**
4. Restart Home Assistant
5. Go to **Settings** → **Devices & services** → **Add integration**, then search for **Chore Tracker**

Adding the integration registers the Lovelace card automatically — no manual resource configuration or YAML setup is needed.

## Manual Installation

1. Copy `custom_components/chore_tracker/` into your HA `config/custom_components/` folder
2. Restart Home Assistant
3. Go to **Settings** → **Devices & services** → **Add integration**, then search for **Chore Tracker**

Alternatively, add `chore_tracker:` to `configuration.yaml` and restart Home Assistant.

## Adding the card

1. Open a dashboard → **Edit** → **Add card**
2. Select **By card** and search for **Haushaltsaufgaben**
3. Add children via the visual editor

## Configuration

All configuration is done through the card editor UI. No YAML required.

| Option     | Description                        |
|------------|------------------------------------|
| `title`    | Card title                         |
| `children` | List of children's names           |

## Services

### `chore_tracker.add_entry`

| Field     | Required | Description                  |
|-----------|----------|------------------------------|
| `child`   | yes      | Child's name                 |
| `minutes` | yes      | Minutes worked               |
| `note`    | no       | Description of the chore     |

### `chore_tracker.reset_child`

| Field   | Required | Description  |
|---------|----------|--------------|
| `child` | yes      | Child's name |
