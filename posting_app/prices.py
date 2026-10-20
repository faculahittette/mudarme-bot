'''Lectura de precios en texto ("USD 229,000", "US$ 185.000", "$ 95.000.000")
para poder comparar el precio de un aviso entre corridas.

Cada sitio formatea distinto; aca solo nos importa moneda + monto entero.
'''

import re
from dataclasses import dataclass
from typing import Optional

# Primer monto del texto: "229.000", "229,000" o "229000". Lo que venga despues
# (decimales ",00", expensas "+ $90.000 expensas") se ignora.
_AMOUNT = re.compile(r'\d{1,3}(?:[.,]\d{3})+|\d+')
_USD = re.compile(r'u\$s|us\$|u\$d|usd|dolar|dólar', re.IGNORECASE)


@dataclass(frozen=True)
class Price:
    currency: str  # 'USD' o 'ARS'
    amount: int


def parse_price(text: Optional[str]) -> Optional[Price]:
    '''None si no hay monto (ej. "Consultar precio").'''
    if not text:
        return None
    match = _AMOUNT.search(text)
    if not match:
        return None
    amount = int(re.sub(r'[.,]', '', match.group()))
    if not amount:
        return None
    # La moneda se mira solo antes del monto: las expensas suelen ir en pesos
    # despues del precio en dolares.
    currency = 'USD' if _USD.search(text[:match.start()]) else 'ARS'
    return Price(currency, amount)


def price_drop(old: Optional[str], new: Optional[str]) -> Optional[float]:
    '''Porcentaje que bajo el precio (ej. 6.1), o None si no bajo o no se
    puede comparar (falta monto o cambio la moneda).'''
    before, after = parse_price(old), parse_price(new)
    if not (before and after) or before.currency != after.currency:
        return None
    if after.amount >= before.amount:
        return None
    return round((before.amount - after.amount) * 100 / before.amount, 1)
