# 2024 Full Season Runbook

This runbook prepares a full-league 2024 KBO regular-season fetch.

## Dry run

Use a small sample first:

```powershell
python scripts\fetch_kbo_season.py --season-year 2024 --round-code kbo_r --limit-games 3
```

## Full run

Fetch the full 2024 regular season:

```powershell
python scripts\fetch_kbo_season.py --season-year 2024 --round-code kbo_r --reuse-existing
```

## Output directory

Outputs are written under:

```text
data/seasons/2024_FULL/
```

Main artifacts:

- `schedule_2024_FULL.json`
- `games_2024_FULL.csv`
- `pitches_2024_FULL.csv`
- `fetch_log_2024_FULL.json`
- `raw/`
- `pitch/`

## Notes

- Default date coverage is `2024-01-01` through `2024-12-31`.
- `kbo_r` keeps only regular-season games.
- `--reuse-existing` is recommended for restart-safe reruns.
- Use `--overwrite-existing` only when you want to refetch saved games.
