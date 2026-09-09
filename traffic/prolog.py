from pathlib import Path


class PrologRules:
    timings=None

    def query_once(self,*args):
        if self.timings is None:return self.janus.query_once(*args)
        with self.timings.measure('prolog'):return self.janus.query_once(*args)
    def lane_change(self,needed,passing,returning,eligible,safe,risky):
        values={k:'true' if v else 'false' for k,v in zip(('N','P','R','E','S','Risk'),(needed,passing,returning,eligible,safe,risky))}
        r=self.query_once('traffic_rules:lane_change(N,P,R,E,S,Risk,A,Reason)',values)
        if not r.get('truth'):raise RuntimeError('No Prolog lane-change decision')
        return r['A'],r['Reason']

    def wrong_way(self,state,eligible,willing,due,oncoming_clear,return_clear):
        values=dict(S=state,E=eligible,W=willing,D=due,O=oncoming_clear,C=return_clear)
        values={k:('true' if v else 'false') if isinstance(v,bool) else v for k,v in values.items()}
        r=self.query_once('traffic_rules:wrong_way(S,E,W,D,O,C,A,R)',values)
        if not r.get('truth'):raise RuntimeError('No Prolog wrong-way decision')
        return r['A'],r['R']

    def drive(self,base,hold,gap,closing,speed,braking,overshoot,surge):
        values=dict(B=base,H=hold,G=min(1e6,gap),C=closing,V=speed,D=braking,O=overshoot,S=surge)
        values={k:('true' if v else 'false') if isinstance(v,bool) else v for k,v in values.items()}
        r=self.query_once('traffic_rules:drive(B,H,G,C,V,D,O,S,A,R)',values)
        if not r.get('truth'):raise RuntimeError('No Prolog longitudinal decision')
        return r['A'],r['R']

    def passing(self,state,eligible,willing,oncoming_clear,return_clear,passed):
        values=dict(S=state,E=eligible,W=willing,O=oncoming_clear,R=return_clear,P=passed)
        values={k:('true' if v else 'false') if isinstance(v,bool) else v for k,v in values.items()}
        r=self.query_once('traffic_rules:passing(S,E,W,O,R,P,A,Reason)',values)
        if not r.get('truth'):raise RuntimeError('No Prolog overtaking decision')
        return r['A'],r['Reason']

    def __init__(self):
        try:
            import janus_swi
            self.janus = janus_swi
            self.janus.consult(str(Path(__file__).with_name('rules.pl').resolve()))
        except Exception as exc:
            raise RuntimeError(
                'Cannot load SWI-Prolog through janus_swi. Run with '
                r'..\.venv\Scripts\python.exe main.py, check swipl --version, '
                'and confirm janus-swi is installed in that interpreter. '
                f'Original error: {exc}'
            ) from exc

    def decide(self, signal, committed, safe_stop, exit_clear, forward_safe,
               kind='signal', turn='straight', junction_clear=True,
               circulating_clear=True, oncoming_clear=True):
        # Explicit atom bindings avoid constructing Prolog source from observations.
        atom = lambda value: 'true' if value else 'false'
        result = self.query_once(
            'traffic_rules:decide(S,C,B,E,F,K,T,J,R,O,Action,Reason)',
            {'S': signal, 'C': atom(committed), 'B': atom(safe_stop),
             'E': atom(exit_clear), 'F': atom(forward_safe), 'K': kind, 'T': turn,
             'J': atom(junction_clear), 'R': atom(circulating_clear), 'O': atom(oncoming_clear)},
        )
        if not result.get('truth'):
            raise RuntimeError('Prolog traffic rules returned no decision for valid observations.')
        return result['Action'], result['Reason']

    def behave(self, observation, profile, ready=True, larger_gap=True, hesitation=False,
               risk_signal=False, risk_gap=False, dwell=False):
        names=('S','C','B','E','F','K','T','J','R','O')
        values=dict(zip(names,observation))
        values.update(P=profile,Ready=ready,Large=larger_gap,H=hesitation,RS=risk_signal,RG=risk_gap,D=dwell)
        values={k: ('true' if v else 'false') if isinstance(v,bool) else v for k,v in values.items()}
        result=self.query_once('traffic_rules:behave(S,C,B,E,F,K,T,J,R,O,P,Ready,Large,H,RS,RG,D,Action,Reason)',values)
        if not result.get('truth'):
            raise RuntimeError('Prolog behaviour rules returned no decision')
        return result['Action'],result['Reason']
