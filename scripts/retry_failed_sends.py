#!/usr/bin/env python3
"""Retry failed/unsent postings with configurable retries and backoff.
Usage: ./venv/bin/python scripts/retry_failed_sends.py
"""
import time
import yaml
from posting_app.database import PostingRepository
from telegram_app.services import TelegramService

cfg = yaml.safe_load(open('config.yaml'))
max_retries = cfg.get('max_retries', 3)
backoff_base = cfg.get('retry_backoff_base', 1)

repo = PostingRepository()
unsent = repo.get_unsent_postings()
print('Total unsent postings:', len(unsent))
tele = TelegramService(bot_token=cfg['bot_token'], chat_room=cfg['chat_room'])

sent = 0
failed = []
for p in unsent:
    ok = tele.send_with_retries(p, max_retries=max_retries, backoff_base=backoff_base)
    if ok:
        repo.set_posting_as_sent(p.sha)
        sent += 1
    else:
        failed.append(p.sha)

print(f'Retry finished. Sent: {sent}; Remaining failed: {len(failed)}')
if failed:
    print('Failed SHAs sample:', failed[:10])
