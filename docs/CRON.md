# Cron setup for scrapdep

This file explains how to schedule the daily runs, retries and the daily summary.

Recommended approach: use the provided `scripts/run_daily.sh` wrapper and the example entries in `crontab.example`.

Steps

1. Make the wrapper executable:

```bash
chmod +x scripts/run_daily.sh
```

2. (Optional) Verify that `config.yaml` has the correct values and that you keep the file secure. The wrapper will set `persist: false` in a temporary copy used for the cron run, and will set `chmod 600 config.yaml` to ensure the file is not world-readable.

3. Open your crontab and paste the contents of `crontab.example` (edit paths if necessary):

```bash
crontab -e
# paste contents of crontab.example
```

4. Logs: wrapper writes to `logs/daily.log`. Retry script writes to `logs/retries.log` and the daily report to `logs/daily_report.log` as per `crontab.example`.

Notes

- The wrapper uses `flock` with `/tmp/scrapdept.lock` to prevent overlapping runs.
- If you prefer `systemd` timers or GitHub Actions, we can add examples for those as well.
