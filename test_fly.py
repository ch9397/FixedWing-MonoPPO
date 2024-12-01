import time
import numpy as np
import airsim
from env.jsbsim_simulator import Simulation
from env.jsbsim_aircraft import Aircraft, x8
from env.debug_utils import *
from env.autopilot import X8Autopilot
from env.navigation import WindEstimation
from env.report_diagrams import ReportGraphs
# learning library
import time

import torch
import torch.multiprocessing as mp


# col = False
# ov = False
class ClosedLoop:
    """
    A class to run airsim, JSBSim and join the other classes together

    ...

    Attributes:
    ----------
    sim_time : float
        how many seconds to run the simulation for
    display_graphics : bool
        decides whether to run the airsim graphic update in unreal, required for image_processing input
    airspeed : float
        fixed airspeed used to fly the aircraft if airspeed_hold_w_throttle a/p used
    agent_interaction_frequency_hz : float
        how often the agent selects a new action, should be equal to or the lowest frequency
    airsim_frequency_hz : float
        how often to update the airsim graphic simulation
    sim_frequency_hz : float
        how often to update the JSBSim input, should not be less than 120Hz to avoid unexpected behaviour
    aircraft : Aircraft
        the aircraft type used, x8 by default, changing this will likely require a change in the autopilot used
    init_conditions : Dict[prp.Property, float] = None
        the simulations initial conditions None by default as in basic_ic.xml
    debug_level : int
        the level of debugging sent to the terminal by JSBSim
        - 0 is limited
        - 1 is core values
        - 2 gives all calls within the C++ source code

    Methods:
    ------
    simulation_loop(profile : tuple(tuple))
        updates airsim and JSBSim in the loop
    get_graph_data()
        gets the information required to produce debug type graphics
    generate_figures()
        produce required graphics
    """
    def __init__(self, sim_time: float,
                 display_graphics: bool = True,
                 alt = 1600.0,
                 airspeed: float = 30.0, # 240
                 agent_interaction_frequency: float = 12.0,
                 airsim_frequency_hz: float = 392.0,
                 sim_frequency_hz: float = 240.0,
                 aircraft: Aircraft = x8,
                 init_conditions: bool = None,
                 debug_level: int = 0,
                 col_flag: bool = False,
                 vehicle: str = ""):
        self.vehicle = vehicle
        self.col_flag = col_flag
        self.sim_time = sim_time
        self.display_graphics = display_graphics
        self.alt = alt
        self.airspeed = airspeed
        self.aircraft = aircraft
        self.sim: Simulation = Simulation(sim_frequency_hz, aircraft, init_conditions, debug_level, vehicle)
        self.agent_interaction_frequency = agent_interaction_frequency
        self.sim_frequency_hz = sim_frequency_hz
        self.airsim_frequency_hz = airsim_frequency_hz
        self.ap: X8Autopilot = X8Autopilot(self.sim)
        self.graph: DebugGraphs = DebugGraphs(self.sim)
        self.report: ReportGraphs = ReportGraphs(self.sim)
        self.debug_aero: DebugFDM = DebugFDM(self.sim)
        self.wind_estimate: WindEstimation = WindEstimation(self.sim)


    def simulation_loop(self, profile, que, over, termination_event, beg_eve):
    # def simulation_loop(self, profile: tuple, que, coll, over):
    # def simulation_loop(self, profile: tuple) -> None:
        """
        Runs the closed loop simulation and updates to airsim simulation based on the class level definitions

        :param profile: a tuple of tuples of the aircraft's profile in (lat [m], long [m], alt [feet])
        :return: None
        """
        relative_update = self.airsim_frequency_hz / self.sim_frequency_hz  # rate between airsim and JSBSim
        graphic_update = 0
        airsim_client = airsim.VehicleClient()
        airsim_client.simGetCollisionInfo(vehicle_name=self.vehicle).has_collided

        i = 0
        j = 0
        count = 0
        flag = True
        while not que.empty():
                que.get()
        nav_flag = True
        while not over.value:
            profile_cha = profile
            graphic_i = relative_update * i
            graphic_update_old = graphic_update
            graphic_update = graphic_i // 1.0


            if self.display_graphics and graphic_update > graphic_update_old:
                self.sim.update_airsim()
            self.ap.airspeed_hold_w_throttle(self.airspeed)
            self.get_graph_data()
            try:
                over.value,_ = self.ap.arc_path(profile_cha, 400, nav_flag)
            except Exception:
                    pass
            self.sim.run()
                    
    def get_graph_data(self) -> None:
        """
        Gets the information required to produce debug type graphics

        :return:
        """
        self.graph.get_abs_pos_data()
        self.graph.get_airspeed()
        self.graph.get_alpha()
        self.graph.get_control_data()
        self.graph.get_time_data()
        self.graph.get_pos_data()
        self.graph.get_angle_data()
        self.graph.get_rate_data()
        self.report.get_graph_info()

    def generate_figures(self) -> None:
        """
        Produce required graphics, outputs them in the desired graphic environment

        :return: None
        """
        self.graph.control_plot()
        self.graph.trace_plot_abs()
        self.graph.three_d_scene()
        self.graph.pitch_rate_plot()
        self.graph.roll_rate_plot()


def set_seed(seed):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

def consumer(q, ov, termination_event, vehicle, aim, beg_eve):
    ov.value = False
    env = ClosedLoop(750, True, vehicle=vehicle)
    env.simulation_loop(aim, que=q, over=ov, termination_event=termination_event, beg_eve=beg_eve)


if __name__ == '__main__':
    mp.set_start_method('spawn')
    modified_points0 = ((0.0, 0.0, 80.0), (-801.4, -556.4, 80.0), (-901.4, -566.4, 80.0))
    ov1 = mp.Value('b', False)
    v_name1 = "drone_1"
    termination_event1 = mp.Event()
    begin_event1 = mp.Event()
    q1 = mp.Queue()
    up_event = mp.Event()
    c1 = mp.Process(target=consumer, args=(q1, ov1, termination_event1, v_name1, modified_points0, begin_event1))

    c1.start()
    c1.join()



