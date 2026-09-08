"""Contact-connected incident history and cumulative exposure."""
from collections import Counter
import math
from copy import deepcopy


class Incidents:
    def __init__(self, clearance=45.):
        self.clearance=clearance
        self.records=[]
        self.cells=Counter()
        self.involved=set()
        self.active_ids=set()

    def register(self,sim,a,b):
        for v in (a,b):
            if v.incident is not None and (v.incident not in self.active_ids or
                v.id not in self.records[v.incident-1]['vehicles']):v.incident=None
        existing=sorted({v.incident for v in (a,b) if v.incident is not None})
        if existing:
            record=self.records[existing[0]-1]
        else:
            pa,pb=sim.future_pose(a,a.s),sim.future_pose(b,b.s)
            location=[(pa[0]+pb[0])/2,(pa[1]+pb[1])/2]
            record=dict(id=len(self.records)+1,start=sim.elapsed,location=location,
                        vehicles={},contacts=[],clear_at=sim.elapsed+self.clearance,cleared=None)
            self.records.append(record)
            self.active_ids.add(record['id'])
            self.cells[tuple(math.floor(p/16) for p in location)]+=1
        # Existing separate origins retain their IDs if a later bridge connects them.
        # New arrivals join the oldest physically contacted active origin.
        record['contacts'].append(dict(time=sim.elapsed,pair=[a.id,b.id],linked_incidents=existing))
        for v in (a,b):
            self.involved.add(v.id)
            if v.manoeuvre and hasattr(sim,'flow_audit'):
                sim.flow_audit.mark(v,v.manoeuvre_mode,'collisions')
            if v.incident is None:
                v.incident=record['id']
                record['vehicles'][v.id]=dict(type=v.spec.kind,profile=v.driver.kind,
                    actions=deepcopy(list(v.recent)),proposal=v.action,reason=v.reason,executed='crashed',
                    explanation='Contact followed an unsafe-gap proposal.' if v.reason=='unsafe_gap_accepted' else
                        'Contact followed a signal-violation proposal.' if v.reason=='signal_violation' else
                        'Vehicle was involved in physical contact; no fault inferred.')
            v.crashed=True
        for iid in set(existing+[record['id']]):
            self.records[iid-1]['clear_at']=sim.elapsed+self.clearance

    def clear(self,sim):
        ids=set()
        for iid in tuple(self.active_ids):
            record=self.records[iid-1]
            if record['cleared'] is None and sim.elapsed+1e-9>=record['clear_at']:
                record['cleared']=sim.elapsed
                ids.add(record['id'])
        members={v.id for v in sim.vehicles if v.crashed and v.incident in ids
                 and v.id in self.records[v.incident-1]['vehicles']}
        if hasattr(sim,'remove_vehicles'):sim.remove_vehicles(members,'crash_clearance')
        else:sim.vehicles[:]=[v for v in sim.vehicles if v.id not in members]
        self.active_ids.difference_update(ids)

    @property
    def active(self):
        return len(self.active_ids)


class Metrics:
    def __init__(self):
        self.distance=0.
        self.wait=0.
        self.dwell=0.
        self.exposure=0.
        self.usage=Counter()
        self.seen=set()

    def enter(self,v,net):
        key=(v.id,v.index)
        if net.paths[v.path_id].kind=='lane' and key not in self.seen:
            self.seen.add(key)
            self.usage[v.path_id]+=1

    def values(self,sim):
        return dict(accidents=len(sim.incidents.records),active_incidents=sim.incidents.active,
                    involved=len(sim.incidents.involved),active=len(sim.vehicles),target=sim.target,
                    on_road=sum(not v.crashed for v in sim.vehicles),wrecks=sum(v.crashed for v in sim.vehicles),
                    completed=sim.completed,mean_speed_mps=sum(v.speed for v in sim.vehicles)/len(sim.vehicles) if sim.vehicles else 0.,
                    distance_km=self.distance/1000,waiting_vehicle_s=self.wait,bus_dwell_vehicle_s=self.dwell,
                    waiting_fraction=self.wait/self.exposure if self.exposure else 0.,
                    accidents_per_1000_vehicle_km=len(sim.incidents.records)*1e6/self.distance if self.distance else None)
