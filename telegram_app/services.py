import requests
from html import escape
import time

from posting_app.database import Posting
import datetime
import json
import os


class TelegramService:
    def __init__(
        self,
        bot_token: str,
        chat_room: str,
        min_interval_seconds: float = 3.1,
    ):
        self._bot_token = bot_token
        self._chat_room = chat_room
        # Telegram limita a ~20 mensajes/minuto por grupo. Espaciar los envios
        # evita la catarata de 429 cuando hay muchas publicaciones nuevas.
        self._min_interval = min_interval_seconds
        self._last_post_at = 0.0

    def format_posting_to_message(self, posting: Posting) -> str:
        '''Formats the object into a Telegram message.'''
        # Escape text parts to avoid HTML injection or invalid markup
        title = escape(posting.title or '')
        price = escape(posting.price or '')
        location = escape(posting.location or '')
        description = escape(posting.description or '')

        # El link va aparte y con texto fijo: si el titulo viene vacio, un
        # <a> sin texto queda invisible y el mensaje llega "sin link".
        lines = [
            f'<b>{title or "Propiedad en venta"}</b>',
            f'\U0001F4B0<i>{price}</i>',
            f'\U0001F4CD<i>{location}</i>',
        ]
        if posting.published:
            lines.append(f'\U0001F4C5<i>Publicado {escape(posting.published)}</i>')
        msg = '\n'.join(lines) + '\n\n{}\n\n<a href="{}">Ver publicación</a>'.format(
            description,
            escape(posting.url, quote=True),
        )

        return msg
    
    def _post_message(self, msg_text: str):
        """Post message and return response or None on exception."""
        api_url = f'https://api.telegram.org/bot{self._bot_token}/sendMessage'
        params = {
            'chat_id': self._chat_room,
            'text': msg_text,
            'parse_mode': 'HTML',
        }
        wait = self._min_interval - (time.monotonic() - self._last_post_at)
        if wait > 0:
            time.sleep(wait)
        try:
            self._last_post_at = time.monotonic()
            res = requests.post(api_url, data=params, timeout=10)
            return res
        except requests.RequestException:
            return None

    def send_telegram_message(self, msg_text: str) -> bool:
        res = self._post_message(msg_text)
        return bool(res and res.ok)

    def format_minimal_message(self, posting: Posting) -> str:
        """Return a short message consisting of link, title, price, location."""
        title = escape((posting.title or '').strip())
        price = escape((posting.price or '').strip())
        location = escape((posting.location or '').strip())
        minimal = '<a href="{}"><b>{}</b></a>\n{}<i>{}</i>\n{}<i>{}</i>'.format(
            escape(posting.url, quote=True),
            title or 'Ver publicación',
            u'\U0001F4B0',
            price,
            u'\U0001F4CD',
            location,
        )
        return minimal

    def send_posting_with_fallback(self, posting: Posting) -> bool:
        """Try sending full message; on failure try minimal; log final failure details."""
        full_msg = self.format_posting_to_message(posting)
        res = self._post_message(full_msg)
        if res and res.ok:
            return True

        # attempt minimal message
        minimal = self.format_minimal_message(posting)
        res2 = self._post_message(minimal)
        if res2 and res2.ok:
            return True

        # both failed: log details
        log_entry = {
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'sha': posting.sha,
            'url': posting.url,
            'status_full': None if res is None else res.status_code,
            'status_minimal': None if res2 is None else res2.status_code,
            'response_full': None if res is None else (res.text[:1000] if hasattr(res, 'text') else str(res)),
            'response_minimal': None if res2 is None else (res2.text[:1000] if hasattr(res2, 'text') else str(res2)),
        }
        log_path = os.path.join(os.getcwd(), 'send_failures.log')
        with open(log_path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        return False

    def send_with_retries(self, posting: Posting, max_retries: int = 3, backoff_base: int = 1) -> bool:
        """Try sending a posting with retries and backoff. On 429 respect retry_after when provided."""
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            # try full message + fallback inside send_posting_with_fallback
            ok = self.send_posting_with_fallback(posting)
            if ok:
                return True

            # If failed, try to parse last log entry for this sha to respect retry_after
            retry_after = None
            try:
                log_path = os.path.join(os.getcwd(), 'send_failures.log')
                if os.path.exists(log_path):
                    with open(log_path, 'r', encoding='utf-8') as fh:
                        lines = [l for l in fh if posting.sha in l]
                    if lines:
                        last = json.loads(lines[-1])
                        # try extract retry_after from response texts
                        resp = last.get('response_full') or last.get('response_minimal') or ''
                        import re
                        m = re.search(r'retry after (\d+)', resp)
                        if m:
                            retry_after = int(m.group(1))
            except Exception:
                retry_after = None

            if retry_after:
                sleep_time = retry_after + 2
            else:
                sleep_time = backoff_base * (2 ** (attempt - 1))

            time_msg = f'Attempt {attempt}/{max_retries} failed; sleeping {sleep_time}s before retrying.'
            print(time_msg)
            time.sleep(sleep_time)

        return False