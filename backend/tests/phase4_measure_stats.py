"""Nearest-rank empirical quantiles shared by the measurement entry points."""
import math


def distribution(values):
    ordered = sorted(values)
    return {'n': len(values), **({k: ordered[min(len(ordered)-1, math.ceil(p*len(ordered))-1)]
        for k, p in [('p50Ms', .5), ('p95Ms', .95), ('maxMs', 1)]} if values else {})}
