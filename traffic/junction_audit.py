"""Classify actual contact coordinates, independent of an actor's approach ID."""
import math

def location_type(net,position):
    candidates=[(math.dist(position,j.position),j) for j in getattr(net,'junctions',{}).values()]
    if not candidates:return 'road',None
    distance,j=min(candidates,key=lambda item:item[0])
    inside=distance<=20 if j.kind=='roundabout' else max(abs(position[i]-j.position[i]) for i in (0,1))<=16
    if inside:return ('bend' if getattr(j,'bend',False) else j.kind),j.id
    return 'road',None
