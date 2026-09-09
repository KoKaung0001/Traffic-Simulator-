"""Scene ownership and pose checks; never mutates simulation state."""
import math


def validate(view,sim):
    assert set(view.cars)=={v.id for v in sim.vehicles}
    nodes=set()
    for v in sim.vehicles:
        car=view.cars[v.id];p=sim.visual_pose(v) if view.optimized else sim.pose(v)
        assert car.model and not car.model.isEmpty(),('missing body',v.id)
        assert car.model.getParent()==car,('body reparented',v.id)
        assert car.model.node() not in nodes,('shared body node',v.id)
        nodes.add(car.model.node())
        assert not car.isHidden() and not car.isStashed() and not car.model.isHidden() and not car.model.isStashed(),('hidden body',v.id)
        assert car.color.a==1 and all(value>0 for value in car.scale),('opacity/scale',v.id)
        assert math.dist((car.x,car.z),p[:2])<1e-4,('body position',v.id)
        assert abs((car.rotation_y-p[2]+180)%360-180)<1e-3,('body heading',v.id)
        assert abs(car.y-.22)<1e-5,('road height',v.id)
        lo,hi=car.model.getTightBounds(car)
        assert lo is not None and hi.y>lo.y and hi.y>1,('empty geometry',v.id)
        assert hi.x-lo.x>v.spec.width/car.scale_x-.02,('body width',v.id)
        assert hi.z-lo.z>v.spec.length/car.scale_z-.02,('body length',v.id)
        assert lo.x>=-v.spec.width/car.scale_x/2-.001 and hi.x<=v.spec.width/car.scale_x/2+.001
        assert lo.z>=-v.spec.length/car.scale_z/2-.001 and hi.z<=v.spec.length/car.scale_z/2+.001
        assert lo.y+car.y>.17,('body below road',v.id)
        for bulb in car.bulbs:
            assert bulb.parent==car and bulb.model.getParent()==bulb,('detached lamps',v.id)
            assert bulb.model.node() not in nodes,('shared lamp node',v.id)
            nodes.add(bulb.model.node())
            assert bulb.enabled==(view.lighting.day<.99),('lamp visibility',v.id)
        if view.lighting.day<.99 and not v.crashed and v.id in view.lighting.selected:
            index=view.lighting.selected.index(v.id);light=view.lighting.headlights[index]
            angle=math.radians(p[2]);front=v.spec.length/2-.05
            expected=(p[0]+math.sin(angle)*front,p[1]+math.cos(angle)*front)
            assert math.dist((light[0],light[1]),expected)<1e-3,('headlight origin',v.id)
    return len(nodes)


def selection(view,sim,v):
    view.show_selection(sim,('vehicle',v.id));p=sim.visual_pose(v) if view.optimized else sim.pose(v)
    assert math.dist((view.highlight.x,view.highlight.z),p[:2])<1e-4
    assert abs((view.highlight.rotation_y-p[2]+180)%360-180)<1e-3
