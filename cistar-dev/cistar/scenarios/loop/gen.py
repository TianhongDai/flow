from cistar.core.exp import Generator

from cistar.core.generator import makexml
from cistar.core.generator import printxml

import subprocess
import sys

from numpy import pi, sin, cos, linspace

import logging, random
from lxml import etree
E = etree.Element


"""
Generator for loop circle used in MIT traffic simulation.
"""
class CircleGenerator(Generator):

    """
    Generates Net files for loop sim. Requires:
    length: length of the circle
    lanes: number of lanes in the circle
    speed_limit: max speed limit of the circle
    resolution: number of nodes resolution

    """
    def generate_net(self, params):
        length = params["length"]
        lanes = params["lanes"]
        speed_limit = params["speed_limit"]
        resolution = params["resolution"]

        self.name = "%s-%dm%dl" % (self.base, length, lanes)

        nodfn = "%s.nod.xml" % self.name
        edgfn = "%s.edg.xml" % self.name
        typfn = "%s.typ.xml" % self.name
        cfgfn = "%s.netccfg" % self.name
        netfn = "%s.net.xml" % self.name

        r = length / pi
        edgelen = length / 4.

        x = makexml("nodes", "http://sumo.dlr.de/xsd/nodes_file.xsd")
        x.append(E("node", id="bottom", x=repr(0), y=repr(-r)))
        x.append(E("node", id="right", x=repr(r), y=repr(0)))
        x.append(E("node", id="top", x=repr(0), y=repr(r)))
        x.append(E("node", id="left", x=repr(-r), y=repr(0)))
        printxml(x, self.net_path + nodfn)

        x = makexml("edges", "http://sumo.dlr.de/xsd/edges_file.xsd")
        x.append(E("edge", attrib={"id": "bottom", "from": "bottom", "to": "right", "type": "edgeType",
                                   "shape": " ".join(["%.2f,%.2f" % (r * cos(t), r * sin(t))
                                                      for t in linspace(-pi / 2, 0, resolution)]),
                                   "length": repr(edgelen)}))
        x.append(E("edge", attrib={"id": "right", "from": "right", "to": "top", "type": "edgeType",
                                   "shape": " ".join(["%.2f,%.2f" % (r * cos(t), r * sin(t))
                                                      for t in linspace(0, pi / 2, resolution)]),
                                   "length": repr(edgelen)}))
        x.append(E("edge", attrib={"id": "top", "from": "top", "to": "left", "type": "edgeType",
                                   "shape": " ".join(["%.2f,%.2f" % (r * cos(t), r * sin(t))
                                                      for t in linspace(pi / 2, pi, resolution)]),
                                   "length": repr(edgelen)}))
        x.append(E("edge", attrib={"id": "left", "from": "left", "to": "bottom", "type": "edgeType",
                                   "shape": " ".join(["%.2f,%.2f" % (r * cos(t), r * sin(t))
                                                      for t in linspace(pi, 3 * pi / 2, resolution)]),
                                   "length": repr(edgelen)}))
        printxml(x, self.net_path + edgfn)

        x = makexml("types", "http://sumo.dlr.de/xsd/types_file.xsd")
        x.append(E("type", id="edgeType", numLanes=repr(lanes), speed=repr(speed_limit)))
        printxml(x, self.net_path + typfn)

        x = makexml("configuration", "http://sumo.dlr.de/xsd/netconvertConfiguration.xsd")
        t = E("input")
        t.append(E("node-files", value=nodfn))
        t.append(E("edge-files", value=edgfn))
        t.append(E("type-files", value=typfn))
        x.append(t)
        t = E("output")
        t.append(E("output-file", value=netfn))
        x.append(t)
        t = E("processing")
        t.append(E("no-internal-links", value="true"))
        t.append(E("no-turnarounds", value="true"))
        x.append(t)
        printxml(x, self.net_path + cfgfn)

        # netconvert -c $(cfg) --output-file=$(net)
        retcode = subprocess.call(
            ["netconvert -c " + self.net_path + cfgfn + " --output-file=" + self.cfg_path + netfn],
            stdout=sys.stdout, stderr=sys.stderr, shell=True)
        self.netfn = netfn

        return self.net_path + netfn


    """
    Generates .sumo.cfg files using net files and netconvert.
    Requires:
    num_cars: Number of cars to seed the simulation with
       max_speed: max speed of cars
       OR
    type_list: List of types of cars to seed the simulation with

    startTime: time to start the simulation
    endTime: time to end the simulation

    """
    def generate_cfg(self, params):

        if "start_time" not in params:
            raise ValueError("start_time of circle not supplied")
        else:
            start_time = params["start_time"]

        if "end_time" not in params:
            raise ValueError("end_time of circle not supplied")
        else:
            end_time = params["end_time"]

        self.roufn = "%s.rou.xml" % self.name
        addfn = "%s.add.xml" % self.name
        cfgfn = "%s.sumo.cfg" % self.name
        guifn = "%s.gui.cfg" % self.name

        def rerouter(name, frm, to):
            t = E("rerouter", id=name, edges=frm)
            i = E("interval", begin="0", end="100000")
            i.append(E("routeProbReroute", id=to))
            t.append(i)
            return t

        self.rts = {"top": "top left bottom right",
               "left": "left bottom right top",
               "bottom": "bottom right top left",
               "right": "right top left bottom"}

        add = makexml("additional", "http://sumo.dlr.de/xsd/additional_file.xsd")
        for (rt, edge) in self.rts.items():
            add.append(E("route", id="route%s" % rt, edges=edge))
        add.append(rerouter("rerouterBottom", "bottom", "routebottom"))
        add.append(rerouter("rerouterTop", "top", "routetop"))
        printxml(add, self.cfg_path + addfn)

        gui = E("viewsettings")
        gui.append(E("scheme", name="real world"))
        printxml(gui, self.cfg_path +guifn)

        cfg = makexml("configuration", "http://sumo.dlr.de/xsd/sumoConfiguration.xsd")

        logging.debug(self.netfn)

        cfg.append(self.inputs(self.name, net=self.netfn, add=addfn, rou=self.roufn, gui=guifn))
        t, outs = self.outputs(self.name)
        cfg.append(t)
        t = E("time")
        t.append(E("begin", value=repr(start_time)))
        t.append(E("end", value=repr(end_time)))
        cfg.append(t)

        printxml(cfg, self.cfg_path + cfgfn)
        return cfgfn, outs

    def makeRoutes(self, scenario, initial_params, params):

        type_params = scenario.type_params
        type_list = scenario.type_params.keys()
        num_cars = scenario.num_vehicles
        if type_list:
            routes = makexml("routes", "http://sumo.dlr.de/xsd/routes_file.xsd")
            for tp in type_list:
                routes.append(E("vType", id=tp, minGap="0"))

            vehicle_ids = []
            if num_cars > 0:
                for type in type_params:
                    type_count = type_params[type][0]
                    for i in range(type_count):
                        vehicle_ids.append((type, type + "_" + str(i)))

            if initial_params["shuffle"]:
                random.shuffle(vehicle_ids)  # randomly

            positions = initial_params["positions"]
            for i, (type, id) in enumerate(vehicle_ids):
                route, pos = positions[i]
                routes.append(self.vehicle(type, "route" + route, depart="0",
                             departSpeed="0", departPos=str(pos), id=id, color="1,0.0,0.0"))

            printxml(routes, self.cfg_path + self.roufn)