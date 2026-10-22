"""Translate relative demo coordinates to an explicitly configured CARLA spawn origin."""

import json
import math
import os
import xml.etree.ElementTree as ET

from .core import export_xosc


def export_for_carla(scenario):
    name = scenario['map_name']
    if name.startswith('Demo'):
        raise ValueError('Synthetic maps cannot execute in CARLA')
    try:
        origin = json.loads(os.environ.get('SEK_CARLA_MAP_ORIGINS', '{}'))[name]
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('Configure a verified spawn origin for this map in SEK_CARLA_MAP_ORIGINS') from exc
    if (not isinstance(origin, list) or len(origin) != 4
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in origin)):
        raise ValueError('Map origin must be [x,y,z,yaw_degrees] with finite numbers')
    ox, oy, oz, degrees = origin
    heading = math.radians(degrees)
    root = ET.fromstring(export_xosc(scenario))
    root.find('FileHeader').set('description', 'CARLA:SEK-' + scenario['id'])
    ET.SubElement(root.find('RoadNetwork'), 'LogicFile', filepath=name)
    for obj in root.findall('./Entities/ScenarioObject'):
        ego = obj.get('name') == 'ego'
        vehicle, pedestrian = obj.find('Vehicle'), obj.find('Pedestrian')
        if vehicle is not None:
            fallback = 'vehicle.yamaha.yzf' if vehicle.get('vehicleCategory') == 'motorcycle' else 'vehicle.audi.tt'
            vehicle.set('name', os.environ.get('SEK_CARLA_EGO' if ego else 'SEK_CARLA_VEHICLE', fallback))
            model = vehicle
        else:
            pedestrian.set('model', os.environ.get('SEK_CARLA_PEDESTRIAN', 'walker.pedestrian.0001'))
            model = pedestrian
        if ego:
            ET.SubElement(model.find('Properties'), 'Property', name='type', value='ego_vehicle')
    for world in root.iter('WorldPosition'):
        x, y = float(world.get('x')), float(world.get('y'))
        world.set('x', str(ox + x * math.cos(heading) - y * math.sin(heading)))
        world.set('y', str(oy + x * math.sin(heading) + y * math.cos(heading)))
        world.set('z', str(oz + 0.5))
        world.set('h', str(float(world.get('h', '0')) + heading))
    ET.indent(root, space='  ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
