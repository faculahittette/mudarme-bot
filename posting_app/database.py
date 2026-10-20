import os
from typing import Dict, Iterable, List, Optional

from sqlalchemy import inspect, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import (
    create_engine,
    Field,
    select,
    Session,
    SQLModel,
)
from sqlmodel.sql.expression import Select, SelectOfScalar

# Avoiding a warning. More info at: 
# https://github.com/tiangolo/sqlmodel/issues/189
SelectOfScalar.inherit_cache = True
Select.inherit_cache = True


class Posting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sha: str = Field(index=True, sa_column_kwargs={'unique': True})
    url: str = Field(sa_column_kwargs={'unique': True})
    title: Optional[str] = None
    price: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    sent: bool = Field(default=False, index=True)
    # Antiguedad del aviso al detectarlo ("hace 13 días"). None = el sitio no la expone.
    published: Optional[str] = None
    # Precio anterior cuando el aviso bajo de precio (para el mensaje
    # "Bajo de precio"). None = aviso nuevo, sin cambios de precio.
    previous_price: Optional[str] = None

    def __key(self):
        return (self.id, self.sha)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, Posting):
            return self.__key() == other.__key()
        return NotImplemented


DEFAULT_DATABASE_URL = 'sqlite:///scrapdep.db'


def _build_engine(url: str):
    # pool_pre_ping: las bases serverless (Neon) cortan conexiones ociosas.
    return create_engine(url, pool_pre_ping=True)


# Por defecto, SQLite local. Con DATABASE_URL (o `database_url` en el config,
# via configure_database) todas las compus comparten la misma base.
engine = _build_engine(os.environ.get('DATABASE_URL') or DEFAULT_DATABASE_URL)


def configure_database(url: Optional[str]) -> None:
    '''Apunta el repositorio a `url`. La variable DATABASE_URL tiene prioridad.'''
    global engine
    chosen = os.environ.get('DATABASE_URL') or url
    if chosen:
        engine = _build_engine(chosen)


def database_label() -> str:
    '''Descripcion de la base en uso, sin credenciales (para logs).'''
    return engine.url.render_as_string(hide_password=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


# Columnas agregadas despues de crear la base compartida.
_ADDED_COLUMNS = {
    'published': 'VARCHAR',
    'previous_price': 'VARCHAR',
}


def _add_missing_columns():
    '''Migracion minima: create_all no agrega columnas nuevas a una tabla que
    ya existe (ej. la base compartida). Las agregamos aca, de forma idempotente.'''
    existing = {c['name'] for c in inspect(engine).get_columns('posting')}
    with engine.begin() as conn:
        for name, sql_type in _ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f'ALTER TABLE posting ADD COLUMN {name} {sql_type}'))


class PostingRepository:
    def create_posting(self, posting: Posting) -> bool:
        '''Guarda el aviso. Si otra compu ya lo guardo (sha/url duplicado),
        lo ignora y devuelve False en vez de fallar.'''
        with Session(engine) as session:
            session.add(posting)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
        return True

    def get_posting_by_sha(self, sha: str) -> Optional[Posting]:
        with Session(engine) as session:
            statement = select(Posting).where(Posting.sha == sha)
            posting = session.exec(statement).first()

            return posting
    
    def get_postings_by_sha(self, shas: Iterable[str]) -> Dict[str, Posting]:
        '''Los avisos ya guardados, en una sola consulta.'''
        shas = list(set(shas))
        if not shas:
            return {}
        with Session(engine) as session:
            statement = select(Posting).where(Posting.sha.in_(shas))
            return {p.sha: p for p in session.exec(statement)}

    def update_price(self, sha: str, old_price: Optional[str], new_price: str,
                     notify_drop: bool) -> bool:
        '''Actualiza el precio guardado. Con `notify_drop` ademas lo deja
        pendiente de envio (sent=false) con el precio anterior, y el envio
        normal manda el aviso de baja.

        Es atomico (WHERE price = old_price): si dos compus detectan la misma
        baja a la vez, una sola la registra y el mensaje sale una sola vez.
        '''
        values = {'price': new_price}
        if notify_drop:
            values.update(previous_price=old_price, sent=False)
        with Session(engine) as session:
            result = session.execute(
                update(Posting)
                .where(Posting.sha == sha, Posting.price == old_price)
                .values(**values)
            )
            session.commit()
            return result.rowcount == 1

    def get_unsent_postings(self) -> List[Posting]:
        with Session(engine) as session:
            statement = select(Posting).where(Posting.sent == False)
            postings = [
                posting for posting
                in session.exec(statement)
            ]

            return postings

    def claim_for_sending(self, sha: str) -> bool:
        '''Marca el aviso como enviado SOLO si nadie lo marco antes.

        Es un UPDATE atomico: si dos compus corren a la vez, una sola gana
        (rowcount == 1) y es la unica que manda el mensaje a Telegram.
        '''
        with Session(engine) as session:
            result = session.execute(
                update(Posting)
                .where(Posting.sha == sha, Posting.sent == False)  # noqa: E712
                .values(sent=True)
            )
            session.commit()
            return result.rowcount == 1

    def release_claim(self, sha: str) -> None:
        '''Deshace el claim si el envio fallo, para reintentar en otra corrida.'''
        with Session(engine) as session:
            session.execute(update(Posting).where(Posting.sha == sha).values(sent=False))
            session.commit()

    def set_posting_as_sent(self, sha: str):
        with Session(engine) as session:
            statement = select(Posting).where(Posting.sha == sha)
            posting = session.exec(statement).first()
            posting.sent = True
            session.add(posting)
            session.commit()
