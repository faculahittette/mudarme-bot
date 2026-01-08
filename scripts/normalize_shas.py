"""Normalize SHAs for existing unsent postings by recomputing SHA with URL normalization.

This script will:
- For each posting with sent == False, compute the new normalized sha using BaseParser.get_id
- If another posting already exists with that normalized sha, mark the current posting as sent (considered duplicate)
- Otherwise update the posting's sha to the normalized sha
"""
from sqlmodel import Session, select
from posting_app.database import engine, Posting
from scraper_app.parsers.base import BaseParser

parser = BaseParser()

with Session(engine) as s:
    stmt = select(Posting).where(Posting.sent == False)
    unsent = s.exec(stmt).all()

    updated = 0
    deduped = 0

    for p in unsent:
        new_sha = parser.get_id(p.url)
        if new_sha == p.sha:
            continue

        # check if target sha exists
        stmt2 = select(Posting).where(Posting.sha == new_sha)
        exists = s.exec(stmt2).first()
        if exists:
            # mark this one as sent (duplicate)
            p.sent = True
            s.add(p)
            deduped += 1
        else:
            p.sha = new_sha
            s.add(p)
            updated += 1

    s.commit()

print(f'Updated SHAs: {updated}. Marked duplicates as sent: {deduped}.')