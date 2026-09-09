"""Stable frequency bins; display scale never changes accumulated counts."""
PALETTE=(None,'#f4ce4c','#ed8139','#d93b39')


def thresholds(kind,scale=1.):
    middle,high=(25,50) if kind=='Road usage' else (3,5)
    middle=max(2,round(middle*scale));high=max(middle+1,round(high*scale))
    return middle,high


def level(count,kind,scale=1.):
    if count<=0:return 0
    middle,high=thresholds(kind,scale)
    return 1 if count<middle else 2 if count<high else 3
