"""Group postings by normalized URL SHA and mark duplicates as sent.

- For each group of postings with the same normalized SHA:
  - Keep one posting (prefer one already marked sent)
  - Mark all other postings in the group as sent=True (duplicate)
  - Update the kept posting's sha to the normalized SHA
"""
from collections import defaultdict
from sqlmodel import Session, select
from posting_app.database import engine, Posting
from scraper_app.parsers.base import BaseParser

parser = BaseParser()

with Session(engine) as s:
    stmt = select(Posting)
    all_posts = s.exec(stmt).all()

    groups = defaultdict(list)
    for p in all_posts:
        norm = parser.get_id(p.url)
        groups[norm].append(p)

    total_groups = 0
    total_marked = 0

    for norm_sha, posts in groups.items():
        if len(posts) <= 1:
            continue
        total_groups += 1
        # choose keeper: prefer a sent=True posting
        keeper = None
        for p in posts:
            if p.sent:
                keeper = p
                break
        if not keeper:
            # pick the one with smallest id
            keeper = sorted(posts, key=lambda x: (x.id or 0))[0]

            # update keeper's sha if needed and commit per-group to avoid UNIQUE constraint issues
        try:
            if keeper.sha != norm_sha:
                keeper.sha = norm_sha
                s.add(keeper)
                s.commit()
        except Exception:
            # If updating the keeper's sha triggers a UNIQUE constraint (another row already has it),
            # rollback and proceed to only mark duplicates as sent
            s.rollback()

        # mark the rest as sent (duplicates) and commit per item
        for p in posts:
            if p is keeper:
                continue
            if not p.sent:
                p.sent = True
                s.add(p)
                try:
                    s.commit()
                    total_marked += 1
                except Exception:
                    # If commit fails for any reason, rollback and continue
                    s.rollback()

print(f'Normalized groups processed: {total_groups}. Marked duplicates as sent: {total_marked}.')