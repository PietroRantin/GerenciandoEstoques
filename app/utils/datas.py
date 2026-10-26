from datetime import date, datetime


def agora() -> datetime:
    """Data/hora local atual, sem microssegundos."""
    return datetime.now().replace(microsecond=0)


def hoje() -> date:
    return date.today()
