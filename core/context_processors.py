"""Umumiy shablon konteksti (flaglar, interfeys qiyofasi)."""
from .flags import all_flags


def feature_flags(request):
    """`{{ flags.<nom> }}` — funksiya flaglari shablonda."""
    return {'flags': all_flags()}
