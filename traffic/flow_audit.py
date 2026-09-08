"""Observational admission and manoeuvre funnels; never consumes randomness."""
from collections import Counter
from .profiles import PARAMETERS
from .overtaking import base_position,corridor,road_window


class FlowAudit:
    def __init__(self):
        self.funnel=Counter();self.seen=set();self.blocks=Counter()
        self.entry_checks=Counter();self.admissions=Counter();self.waits=[]
        self.samples=[];self.max_active=0;self.first_100=None

    def mark(self,v,mode,stage):
        key=(v.id,v.index,mode,stage)
        if key not in self.seen:self.seen.add(key);self.funnel[mode+'/'+stage]+=1

    def opportunity(self,v,mode,token):
        key=(v.id,v.index,mode,'opportunity',token)
        if key not in self.seen:
            self.seen.add(key);self.funnel[mode+'/opportunities']+=1

    def inspect(self,sim,v):
        if v.driver.kind!='Drunk':return
        for mode in ('overtaking','wrong_way'):
            self.mark(v,mode,'drunk_route_encounters')
            if v.driver.subgroup!='higher_risk':self.mark(v,mode,'reject_personality');continue
            if v.spec.kind!='Sedan':self.mark(v,mode,'reject_vehicle_type');continue
            if v.crashed:self.mark(v,mode,'reject_crashed');continue
            base,s,_=base_position(sim,v);p=sim.network.paths[base]
            if p.kind!='lane':self.mark(v,mode,'reject_connector');continue
            if v.manoeuvre:
                if v.manoeuvre_mode==mode:
                    self.mark(v,mode,'path_installed')
                    if v.speed>.05:self.mark(v,mode,'executed_motion')
                continue
            self.mark(v,mode,'higher_risk_sedan_lane_encounters')
            reasons=[]
            window=road_window(sim,base,s)
            if window is None:reasons.append('protected_zone')
            cfg=PARAMETERS['overtaking']
            minimum=(2*cfg['shift_length']+cfg['pass_length']+cfg['end_buffer']
                     if mode=='overtaking' else PARAMETERS['wrong_way']['minimum_straight'])
            if (window[1] if window else p.length)-s<minimum:reasons.append('remaining_length')
            if v.speed<(2 if mode=='overtaking' else 1):reasons.append('own_speed')
            if mode=='wrong_way' and v.permit:reasons.append('entry_reservation')
            if mode=='overtaking':
                leader,lead_s,*_=corridor(sim,v)
                if leader is None:reasons.append('no_leader')
                elif leader.crashed:reasons.append('wreck_leader')
                else:
                    if not cfg['minimum_leader_speed']<=leader.speed<=cfg['maximum_leader_speed']:reasons.append('leader_speed')
                    if v.desired_speed-leader.speed<cfg['minimum_speed_advantage']:reasons.append('speed_advantage')
                    if not 0<lead_s-s<cfg['leader_distance']:reasons.append('leader_distance')
            for reason in reasons:self.mark(v,mode,'reject_'+reason)
            if not reasons:self.mark(v,mode,'eligible_encounters')
            if v.passing_state=='assess' and v.manoeuvre_mode==mode:self.mark(v,mode,'selected_assessment')

    def sample(self,sim):
        self.max_active=max(self.max_active,len(sim.vehicles))
        if len(sim.vehicles)==100 and self.first_100 is None:self.first_100=sim.elapsed
        if sim.ticks%600:return
        stale=sum(v.permit is not None and v.permit not in v.route[max(0,v.index-1):v.index+2]
                  for v in sim.vehicles)
        self.samples.append(dict(time=sim.elapsed,active=len(sim.vehicles),queued=len(sim.queued),
            admitted=len(sim.behaviour_audit.admitted),completed=sim.completed,
            stale_reservations=stale,oldest_wait=max((sim.elapsed-v.queued_since for v in sim.queued),default=0)))

    def values(self):
        return dict(funnel=dict(self.funnel),blocked_checks=dict(self.blocks),
            checks_by_origin=dict(self.entry_checks),admissions_by_origin=dict(self.admissions),
            maximum_admitted_wait=max(self.waits,default=0),max_active=self.max_active,
            first_100=self.first_100,samples=self.samples)
