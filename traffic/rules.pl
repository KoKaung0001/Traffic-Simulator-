:- module(traffic_rules, [decide/12, behave/19, drive/10, passing/8, wrong_way/8, lane_change/8]).

lane_change(_,_,_,false,_,_,hold,change_zone_protected) :- !.
lane_change(N,P,R,true,S,Risk,change,Reason) :-
    (S=true; Risk=true), (N=true; P=true; R=true), !,
    (P=true -> Reason=same_direction_pass; N=true -> Reason=planned_lane; Reason=outer_lane_return).
lane_change(_,_,_,_,_,_,hold,target_lane_gap).

wrong_way(follow,true,true,_,_,_,assess,wrong_way_assessment) :- !.
wrong_way(assess,true,true,_,true,_,move_out,centre_line_crossing) :- !.
wrong_way(assess,_,_,_,_,_,follow,wrong_way_declined) :- !.
wrong_way(S,_,_,Due,Clear,true,return,wrong_way_return) :-
    memberchk(S,[move_out,wrong_way]), (Due=true; Clear=false), !.
wrong_way(S,_,_,Due,Clear,false,S,wrong_way_braking) :-
    memberchk(S,[move_out,wrong_way]), (Due=true; Clear=false), !.
wrong_way(wrong_way,_,_,_,_,_,wrong_way,sustained_wrong_way) :- !.
wrong_way(return,_,_,_,_,_,return,wrong_way_return) :- !.
wrong_way(S,_,_,_,_,_,S,centre_line_crossing).

% Physical control uses perceived quantities, not perfect current geometry.
drive(_,true,_,_,_,_,_,_,wait,delayed_start) :- !.
drive(_,_,G,_,Speed,_,_,_,wait,standing_at_stop) :- G =< 0.05, Speed =< 0.2, !.
drive(stop,_,_,_,_,_,_,_,brake,signal_braking) :- !.
drive(wait,_,_,_,_,_,_,_,brake,yield_braking) :- !.
drive(brake,_,_,_,_,_,_,_,brake,late_braking) :- !.
drive(_,_,G,Closing,Speed,Brake,_,_,brake,late_braking) :-
    G =< Speed*Speed/(2*Brake)+max(0,Closing)*0.6, !.
drive(_,_,_,_,_,_,true,_,accelerate,acceleration_overshoot) :- !.
drive(_,_,_,_,_,_,_,true,accelerate,speed_surge) :- !.
drive(_,_,_,_,_,_,_,_,proceed,perceived_clear).

passing(follow,true,true,_,_,_,assess,overtaking_assessment) :- !.
passing(assess,_,false,_,_,_,follow,overtaking_aborted) :- !.
passing(assess,true,true,true,_,_,move_out,overtaking_gap_accepted) :- !.
passing(assess,_,_,false,_,_,follow,overtaking_aborted) :- !.
passing(pass,_,_,false,true,_,abort,overtaking_abort_return) :- !.
passing(move_out,_,_,false,true,_,abort,overtaking_abort_return) :- !.
passing(State,_,_,false,false,_,State,overtaking_late_braking) :- memberchk(State,[move_out,pass]), !.
passing(pass,_,_,_,true,true,return,overtaking_return) :- !.
passing(State,_,_,_,_,_,State,overtaking_hold).

% Python supplies geometry. Prolog owns admission policy.
decide(_, _, _, _, false, _, _, _, _, _, brake, vehicle_ahead) :- !.
decide(_, true, _, _, true, _, _, _, _, _, proceed, clear_intersection) :- !.
decide(_, _, _, _, true, road, _, _, _, _, proceed, lane_clear) :- !.
decide(_, false, _, false, true, _, _, _, _, _, wait, exit_blocked) :- !.
decide(_, false, _, true, true, roundabout, _, _, false, _, wait, circulating_traffic) :- !.
decide(red, false, _, true, true, signal, _, _, _, _, stop, red_signal) :- !.
decide(amber, false, true, true, true, signal, _, _, _, _, stop, amber_safe_stop) :- !.
decide(_, false, _, true, true, signal, left, _, _, false, wait, oncoming_traffic) :- !.
decide(_, false, _, true, true, _, _, false, _, _, wait, junction_conflict) :- !.
decide(_, false, _, true, true, roundabout, _, true, true, _, proceed, roundabout_gap) :- !.
decide(amber, false, false, true, true, signal, _, true, _, _, proceed, amber_committed) :- !.
decide(green, false, _, true, true, signal, _, true, _, _, proceed, green_and_clear).


% Behaviour sampling is persistent input, never randomness hidden in these rules.
behave(_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,true,wait,bus_stop_dwell) :- !.
behave(_,_,_,_,_,_,_,_,_,_,_,false,_,_,_,_,false,wait,delayed_response) :- !.
behave(S,true,B,E,F,K,T,J,R,O,_,true,_,_,_,_,false,A,Reason) :- !,
    decide(S,true,B,E,F,K,T,J,R,O,A,Reason).
behave(red,false,_,_,_,signal,_,_,_,_, 'Drunk',true,_,_,true,_,false,proceed,signal_violation) :- !.
behave(_,false,_,E,F,_,_,J,R,_, 'Drunk',true,_,_,_,true,false,proceed,unsafe_gap_accepted) :-
    (E=false; F=false; J=false; R=false), !.
behave(_,false,_,E,_,_,_,J,R,_, 'Newbie',true,_,_,_,true,false,proceed,unsafe_gap_accepted) :-
    (E=false; J=false; R=false), !.
behave(_,false,_,_,_,_,_,_,_,_, 'Newbie',true,false,_,_,_,false,wait,waiting_for_larger_gap) :- !.
behave(_,false,_,_,_,_,_,_,_,_,_,true,_,true,_,_,false,wait,hesitating) :- !.
behave(_,false,_,true,true,roundabout,_,_,false,_,_,true,_,_,_,_,false,wait,yielding_to_circulating_vehicle) :- !.
behave(S,C,B,E,F,K,T,J,R,O,_,true,_,_,_,_,false,A,Reason) :- decide(S,C,B,E,F,K,T,J,R,O,A,Reason).
