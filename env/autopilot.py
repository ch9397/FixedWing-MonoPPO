from simple_pid import PID
import env.jsbsim_properties as prp
from env.jsbsim_simulator import Simulation
from scipy import interpolate
import math
from env.navigation import LocalNavigation
import matplotlib.pyplot as plt


# Should this be derived from simulation ?
# def __init__(self):
#     super().__init__()
class C172Autopilot:
    def __init__(self, sim):
        self.sim = sim

    def wing_leveler(self):
        error = self.sim[prp.roll_rad]
        kp = 50.0
        ki = 5.0
        kd = 17.0
        pid = PID(kp, ki, kd)
        output = pid(error)
        self.sim[prp.aileron_cmd] = output

    def hdg_hold(self, hdg):
        error = hdg - self.sim[prp.heading_deg]
        # Limit error to within 180 degrees (left or right)
        if error > 180:
            error = error - 180
        if error < 180:
            error = error + 180
        # Saturate error signal gain to be a maximum of 30 degrees
        if error < -30:
            error = -30
        if error > 30:
            error = 30
        # Convert error signal from degrees to radians
        error = error * (math.pi / 180)
        # Implementing a lag compensator as a single integrator (don't know how to do lag)
        c = 0.5
        hdg_lag = PID(0, c, 0)
        roll_error = hdg_lag(error) - self.sim[prp.roll_rad]
        kp = 6.0
        ki = 0.13
        kd = 6.0
        roll_pid = PID(kp, ki, kd)
        output = roll_pid(roll_error)
        self.sim[prp.aileron_cmd] = output

    def level_hold(self, level):
        error = level - self.sim[prp.altitude_sl_ft]
        # Limit climb error to a maximum of 100'
        if error > 100:
            error = 100
        if error < -100:
            error = -100
        # Convert error to percentage of maximum
        error = error/100
        # Lag desired climb rate (for stability) as a single integrator
        # c = 1.0
        # vs_lag = PID(0, c, 0)
        # error = vs_lag(error)
        # Gain scheduled climb rate
        ref_alt = [0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0,
                   7000.0, 8000.0, 9000.0, 10000.0, 11000.0, 12000.0]
        vs_gain = [0.12, 0.11, 0.10, 0.096, 0.093, 0.086, 0.078,
                   0.069, 0.061, 0.053, 0.045, 0.037, 0.028]
        climb_gain_scheduling = interpolate.interp1d(ref_alt, vs_gain)
        vs_dem = error * climb_gain_scheduling(self.sim[prp.altitude_sl_ft])
        vs_error = vs_dem - self.sim[prp.altitude_rate_fps]
        # print('vertical speed error: ', vs_error)
        # Rate PID controller
        kp = 0.01
        ki = 0.00015
        kd = 0.0003
        vs_pid = PID(kp, ki, kd)
        output = vs_pid(vs_error)
        self.sim[prp.elevator_cmd] = output
        # print('elevator command: ', output)
    
    def airspeed_hold_w_throttle(self, airspeed_comm: float) -> None:
        """
        Maintains a commanded airspeed [KTAS] using throttle_cmd and a PI controller

        :param airspeed_comm: commanded airspeed [KTAS]
        :return: None
        """
        # Appears fine with simple proportional controller, light airspeed instability at high speed (100kts)
        error = airspeed_comm - (self.sim[prp.airspeed] * 0.5925)  # set airspeed in KTAS'
        kp = 1.0
        ki = 0.035
        airspeed_controller = PID(kp, ki, 0.0)
        output = airspeed_controller(-error)
        # Clip throttle command from 0 to +1 can't be allowed to exceed this!
        if output > 1:
            output = 1
        if output < 0:
            output = 0
        self.sim[prp.throttle_cmd] = output


class X8Autopilot:
    """
    The low-level autopilot control for the X8 fixed wing UAV aircraft

     ...

    Attributes:
    -----------
    sim : Simulation object
        an instance of the flight simulation flight dynamic model, used to interface with JSBSim
    nav : LocalNavigation object
        the core position and tracking methods used in the path planning methods
    track_bearing : float
        the bearing from a starting point to a target point [radians]
    track_bearing_in : float
        the bearing from a starting point 'a' to a target point 'b' [radians]
    track_bearing_out : float
        the bearing from a target point to 'b' to the following point 'c' [radians]
    track_distance : float
        the distance from a starting point to a target point [m]
    flag : bool
        a variable returned by a method to indicate a significant change in simulation state or termination condition
    track_id : int
        a counter for the points in a profile
    state: int
        the state or mode an autopilot is currently engaged in

    Methods:
    -------
    test_controls(elevator, aileron, tla)
        allows for manual input of the aircraft's controls
    pitch_hold(pitch_comm)
        maintains a commanded pitch attitude [radians] using a PI controller
    roll_hold(roll_comm)
        maintains a commanded roll attitude [radians] using a PID controller
    heading_hold(heading_comm)
        maintains a commanded heading [degrees] using a PD controller
    airspeed_hold_w_throttle(airspeed_comm)
        maintains a commanded airspeed [KTAS] using throttle_cmd
    altitude_hold(altitude_comm)
        maintains a demanded altitude [feet] using pitch attitude
    home_to_target(target_northing, target_easting, target_alt)
        homes towards a 2D (lat, long) point in space and uses altitude_hold to maintain an altitude
    track_to_target(target_northing, target_easting, target_alt)
        maintains a track from the point the simulation started at to the target point
    track_to_profile(profile)
        maintains a track along a series of points in the simulation and the defined altitude along each path segment



    """
    def __init__(self, sim):
        self.sim = sim
        self.nav = None
        # self.orbit_nav = None
        self.track_bearing = 0
        self.track_bearing_in = 0
        self.track_bearing_out = 0
        self.track_bearing_inn = 0
        self.track_distance = 0
        self.flag = False
        self.track_id = -1
        self.state = 0
        self.alpha_pitch = 0.1
        self.prev_output_pitch = 0
        self.alpha_roll = 1
        self.prev_output_roll = 0
        self.alpha_altitude = 0.001
        self.prev_altitude = 0
        # add

    def test_controls(self, elevator=0.295, aileron=0, tla=0.2) -> None:
        """
        Directly control the aircraft using control surfaces for the purpose of testing the model

        :param elevator: elevator angle [-30 to +30]
        :param aileron: aileron angle [-30 to +30]
        :param tla: Thrust Lever Angle [0 to 1]
        :return: None
        """
        self.sim[prp.elevator_cmd] = elevator
        self.sim[prp.aileron_cmd] = aileron
        self.sim[prp.throttle_cmd] = tla

    def pitch_hold(self, pitch_comm: float) -> None:
        """
        Maintains a commanded pitch attitude [radians] using a PI controller with a rate component

        :param pitch_comm: commanded pitch attitude [radians]
        :return: None
        """
        error = pitch_comm - self.sim[prp.pitch_rad]
        # print(pitch_comm)
        # print(self.sim[prp.pitch_rad])
        # print(error)
        kp = 1.0 #2.0          80
        ki = 0.05            #0.05
        kd = 0.03 # 0.03        0.01
        controller = PID(kp, ki, 0.0)
        output = controller(error)
        # self.sim[prp.elevator_cmd] = output
        rate = self.sim[prp.q_radps]
        rate_controller = PID(kd, 0.0, 0.0)
        rate_output = rate_controller(rate)
        output = output+rate_output
        # if output < - 20 * (math.pi / 180):
        #     output = - 20 * (math.pi / 180)
        # if output > 5 * (math.pi / 180):
        #     output = 15 * (math.pi / 180)
        # print(f'p_r:{pitch_comm},p:{self.sim[prp.pitch_rad]},elevator_cmd:{output}')
        self.sim[prp.elevator_cmd] = output

    def roll_hold(self, roll_comm: float) -> None:
        """
        Maintains a commanded roll attitude [radians] using a PID controller

        :param roll_comm: commanded roll attitude [radians]
        :return: None
        """
        # Nichols Ziegler tuning Pcr = 0.29, Kcr = 0.0380, PID chosen
        error = roll_comm - self.sim[prp.roll_rad]
        kp = 0.2    #0.2       #p=1,d=0.2
        ki = kp*0.0  # tbd, should use rlocus plot and pole-placement
        kd = 0.089  #0.089
        controller = PID(kp, ki, 0.0)
        output = controller(error)
        rate = self.sim[prp.p_radps]
        rate_controller = PID(kd, 0.0, 0.0)
        rate_output = rate_controller(rate)
        output = -output+rate_output
        # print(output)
        # print(f'r_r:{roll_comm},r:{self.sim[prp.roll_rad]},aileron_cmd:{output}')
        self.sim[prp.aileron_cmd] = output

    def heading_hold(self, heading_comm: float) -> None:
        """
        Maintains a commanded heading [degrees] using a PI controller

        :param heading_comm: commanded heading [degrees]
        :return: None
        """
        # Attempted Nichols-Ziegler with Pcr = 0.048, Kcr=1.74, lead to a lot of overshoot
        error = heading_comm - self.sim[prp.heading_deg]
        # print(error)
        # Ensure the aircraft always turns the shortest way round
        if error < -180:
            error = error + 360
        if error > 180:
            error = error - 360
        # print(error)
        kp = -2.0023 * 0.005     #-2.0023 * 0.005
        ki = -0.6382 * 0.005
        heading_controller = PID(kp, ki, 0)
        output = heading_controller(error)
        output = self.alpha_roll * output + (1 - self.alpha_roll) * self.prev_output_roll
        self.prev_output_roll = output
        # Prevent over-bank +/- 30 degrees
        if output < - 30 * (math.pi / 180):
            output = - 30 * (math.pi / 180)
        if output > 30 * (math.pi / 180):
            output = 30 * (math.pi / 180)
        # print(output)
        # print(f'he_r:{heading_comm},he:{self.sim[prp.heading_deg]},roll:{output}')
        self.roll_hold(output)

    def airspeed_hold_w_throttle(self, airspeed_comm: float) -> None:
        """
        Maintains a commanded airspeed [KTAS] using throttle_cmd and a PI controller

        :param airspeed_comm: commanded airspeed [KTAS]
        :return: None
        """
        # Appears fine with simple proportional controller, light airspeed instability at high speed (100kts)
        error = airspeed_comm - (self.sim[prp.airspeed] * 0.5925)  # set airspeed in KTAS'
        # print(self.sim[prp.airspeed] * 0.5925)
        kp = 1.0 # 0.0015
        ki = 0.035   
        airspeed_controller = PID(kp, ki, 0)
        output = airspeed_controller(-error)
        # Clip throttle command from 0 to +1 can't be allowed to exceed this!
        if output > 1:
            output = 1
        if output < 0:
            output = 0
        # print(output)
        # print(f'distance:{self.sim[prp.dist_travel_m]},airspeed:{self.sim[prp.airspeed] * 0.3048}')
        self.sim[prp.throttle_cmd] = output
        

    def altitude_hold(self, altitude_comm) -> None:
        """
        Maintains a demanded altitude [feet] using pitch attitude

        :param altitude_comm: demanded altitude [feet]
        :return: None
        """

        altitude_comm = self.alpha_altitude * altitude_comm + (1-self.alpha_altitude) * self.prev_altitude
        self.prev_altitude  = altitude_comm
        error = altitude_comm - self.sim[prp.altitude_sl_ft]
        # print('error: ', error)
        kp = 0.1  #0.1
        ki = 0.6  #0.6
        altitude_controller = PID(kp, ki, 0)
        output = altitude_controller(-error)
        output = self.alpha_pitch * output + (1 - self.alpha_pitch) * self.prev_output_pitch
        self.prev_output_pitch = output
        # prevent excessive pitch +/- 15 degrees
        if output < - 10 * (math.pi / 180):
            output = - 10 * (math.pi / 180)
        if output > 15 * (math.pi / 180):
            output = 15 * (math.pi / 180)
        # print(altitude_comm)
        aoutput = output * (180 / math.pi)
        # print(f'h_r:{altitude_comm},h:{self.sim[prp.altitude_sl_ft]},pitch:{output}')
        self.pitch_hold(output)
        # self.pitch_hold(-0.1617)

    def home_to_target(self, target_northing: float, target_easting: float, target_alt: float) -> bool:
        """
        Homes towards a 2D (lat, long) point in space and uses altitude_hold to maintain an altitude

        :param target_northing: latitude of target relative to current position [m]
        :param target_easting: longitude of target relative to current position [m]
        :param target_alt: demanded altitude for this path segment [feet]
        :return: flag==True if the simulation has reached a target in space
        """
        if self.nav is None:
            # initialize targeting/navigation object
            self.nav = LocalNavigation(self.sim)
            self.nav.set_local_target(target_northing, target_easting)
            self.flag = False
        if self.nav is not None:
            if not self.flag:
                # fly to target using bearing calculated from current position
                bearing = self.nav.bearing() * 180.0 / math.pi
                if bearing < 0:
                    bearing = bearing + 360
                distance = self.nav.distance()
                # when within 100m radius return flag and stop a/p functionality
                if distance < 100:
                    self.flag = True
                    self.nav = None
                    return self.flag
                self.heading_hold(bearing)
                self.altitude_hold(target_alt)

    def track_to_target(self, target_northing: float, target_easting: float, target_alt: float) -> bool:
        """
        Maintains a track from the point the simulation started at to the target point

        ...

        This ensures the aircraft does not fly a curved homing path if displaced from track but instead aims to
        re-establish the track to the pre-defined target point in space. The method terminates when the aircraft arrives
        at a point within 200m of the target point.
        :param target_northing: latitude of target relative to current position [m]
        :param target_easting: longitude of target relative to current position [m]
        :param target_alt: demanded altitude for this path segment [feet]
        :return: flag==True if the simulation has reached the target
        """
        if self.nav is None:
            # initialize target and track
            self.nav = LocalNavigation(self.sim)
            self.nav.set_local_target(target_northing, target_easting)
            self.track_bearing = self.nav.bearing() * 180.0 / math.pi
            if self.track_bearing < 0:
                self.track_bearing = self.track_bearing + 360.0
            self.track_distance = self.nav.distance()
            self.flag = False
        if self.nav is not None:
            # position relative to target
            bearing = self.nav.bearing() * 180.0 / math.pi
            if bearing < 0:
                bearing = bearing + 360
            distance = self.nav.distance()
            off_tk_angle = self.track_bearing - bearing
            distance_to_go = self.nav.distance_to_go(distance, off_tk_angle)
            # use a P controller to regulate the closure rate relative to the track
            error = off_tk_angle * distance_to_go
            kp = 0.01
            ki = 0.0
            kd = 0.0
            closure_controller = PID(kp, ki, kd)
            heading = closure_controller(-error) + bearing
            if distance < 200:
                self.flag = True
                self.nav = None
                return self.flag
            self.heading_hold(heading)
            self.altitude_hold(target_alt)

    # change target 
    def track_to_profile(self, profile: list) -> bool:
        """
        Maintains a track along a series of points in the simulation and the defined altitude along each path segment

        ...

        This ensures the aircraft does not fly a curved homing path if displaced from track but instead aims to
        re-establish the track to the pre-defined target point in space. The method switches to the next target point
        when the aircraft arrives at a point within 300m of the current target point. The method terminates when the
        final point(:tuple) in the profile(:list) is reached.
        :param profile: series of points used to define a path formatted with a tuple at each index of the list
            [latitude, longitude, altitude]
        :return: flag==True if the simulation has reached the final target
        """

        if self.nav is None:
            self.track_id = self.track_id + 1
            # profile[self.track_id] = 
            if self.track_id == len(profile) - 1:
                print('hit flag')
                self.flag = True
                return self.flag
            point_a = profile[self.track_id]
            point_b = profile[self.track_id + 1]
            # initialize target and track
            self.nav = LocalNavigation(self.sim)
            self.nav.set_local_target(point_b[0] - point_a[0], point_b[1] - point_a[1])
            self.track_bearing = self.nav.bearing() * 180.0 / math.pi
            if self.track_bearing < 0:
                self.track_bearing = self.track_bearing + 360.0
            self.track_distance = self.nav.distance()
            self.flag = False
        if self.nav is not None:
            bearing = self.nav.bearing() * 180.0 / math.pi
            if bearing < 0:
                bearing = bearing + 360
            distance = self.nav.distance()
            off_tk_angle = bearing - self.track_bearing
            if off_tk_angle > 180:
                off_tk_angle = off_tk_angle - 360.0
            # scale response with distance from target
            distance_to_go = self.nav.distance_to_go(distance, off_tk_angle)
            if distance_to_go > 3000:
                distance_to_go = 3000
            heading = (8 * 0.00033 * distance_to_go * off_tk_angle) + self.track_bearing

            # radius = (self.sim[prp.airspeed] * 0.5925 / (20.0 * math.pi)) * 1852  # rate 1 radius
            radius = 300
            self.heading_hold(heading)
            self.altitude_hold(self.track_id[2])
            if distance < radius:
                self.nav = None

    def restart(self, client):
        client.reset()
    
    def get_coll(self, client) -> bool:
        client.simGetCollisionInfo().has_collided
        col = client.simGetCollisionInfo().has_collided
        if col:
            client.reset()
        return col
    
    # def arc_path(self, profile_o, radius):
    def arc_path(self, profile, radius, nav_flag):
        """
        Maintains a track along a series of points in the simulation and the defined altitude along each path segment,
        ensures a smooth turn by flying an arc/filet with radius=radius at each point

        ...

        The aircraft maintains a track based on the bearing from the location the target was instantiated to the target.
        When within a radius or crossing a plane perpendicular to track the aircraft goes from straight track mode to
        flying a curved path of radius r around a point perpendicular to the point created by the confluence of the two
        tracks. The method switches to the next point when it reaches a point equidistant from the beginning of the arc.
        The method terminates when there is no further 'b' or 'c' points available i.e. 2 points before the final track.
        The method is based off the algorithm defined in Beard & McLain chapter 11, path planning:
        http://uavbook.byu.edu/doku.php
        :param profile: series of points used to define a path formatted with a tuple at each index of the list
            [latitude, longitude, altitude]
        :param radius: fillet radial distance [m], used to calculate z point
        :return: flag==True if the simulation has reached the termination condition
        """

        if self.nav is None:                   
            # print('Changing points !!!')            
            self.track_id = self.track_id + 1
            # print(profile[self.track_id])
            if self.track_id == len(profile) - 1:
                print('hit flag')
                self.flag = True

                self.track_id = -1
                # return 
                return self.flag, profile
            point_a = profile[self.track_id]
            point_b = profile[self.track_id + 1]
            point_c = profile[self.track_id + 2]
            self.nav = LocalNavigation(self.sim)
            # Initialize track outbound from b
            self.nav.set_local_target(point_c[0] - point_b[0], point_c[1] - point_b[1])
            self.track_bearing_out = self.nav.bearing() * 180.0 / math.pi
            if self.track_bearing_out < 0:
                self.track_bearing_out = self.track_bearing_out   #计算b到c偏航角
            # Initialize track inbound to b
            self.nav.local_target_set = False
            self.nav.set_local_target(point_b[0] - point_a[0], point_b[1] - point_a[1])
            self.track_bearing_in = self.nav.bearing() * 180.0 / math.pi
            # print(f'track_bearing_in:{self.track_bearing_in}')
            if self.track_bearing_in < 0:
                self.track_bearing_in = self.track_bearing_in     #计算a到b偏航角
            # print(f'track_bearing_in:{self.track_bearing_in}')
            self.flag = False
        # add listener here
        if self.nav is not None:                      #
            # add
            # Define angle of filet from out and in plane
            
            filet_angle = self.track_bearing_out - self.track_bearing_in
            # print(f'track_bearing_in:{self.track_bearing_in},track_bearing_out:{self.track_bearing_out},角度：{filet_angle}')
            if filet_angle < 0:
                filet_angle = - filet_angle
            if filet_angle >270:
                filet_angle = filet_angle - 270
            if filet_angle > 180:
                filet_angle = filet_angle - 180
            

            # if filet_angle < 0.01 or filet_angle > 359.99:
            #     heading = self.track_bearing_in
            # print(f'heading:{heading}')

            if self.state == 0:
                # Calculate h_plane to transition from straight line state to curved filet state
                q = self.nav.unit_dir_vector(profile[self.track_id], profile[self.track_id + 1])   #两点之间的单位向量
                w = profile[self.track_id + 1]
                if filet_angle == 0:
                    if self.track_bearing_out < 0:
                        self.track_bearing_out = self.track_bearing_out + 360
                    heading = self.track_bearing_out
                    z_point = w
                    cur = self.nav.get_local_pos()
                    h_point = (cur[0] - z_point[0], cur[1] - z_point[1])
                    h_val = (h_point[0] * q[0]) + (h_point[1] * q[1])
                    if h_val > 0:
                        self.nav = None
                else:
                    z_point = (w[0] - ((radius * math.tan(filet_angle / 2 * (math.pi / 180.0))) * q[0]),
                               w[1] - ((radius * math.tan(filet_angle / 2 * (math.pi / 180.0))) * q[1]))   #转弯开始前的点
                    cur = self.nav.get_local_pos()
                    h_point = (cur[0] - z_point[0], cur[1] - z_point[1])
                    h_val = (h_point[0] * q[0]) + (h_point[1] * q[1])
                    if h_val > 0:
                        # Entered h plane transition to curved segment
                        self.state = 1
                    
                    # Track straight line segment
                    bearing = self.nav.bearing() * 180.0 / math.pi  #当前位置距目标点的方位
                    if bearing < 0:
                        bearing = bearing + 360
                    distance = self.nav.distance()
                    off_tk_angle = bearing - self.track_bearing_in
                    if off_tk_angle > 180:
                        off_tk_angle = off_tk_angle - 360.0
                    # print(off_tk_angle)
                    # scale response with distance from target
                    distance_to_go = self.nav.distance_to_go(distance, off_tk_angle)   #distance*sin（off_tk_angle），即当前位置距离直线航迹的垂直距离。
                    if distance_to_go > 3000:
                        distance_to_go = 3000
                    self.track_bearing_inn = self.track_bearing_in
                    if self.track_bearing_inn < 0:
                        self.track_bearing_inn = self.track_bearing_inn + 360
                    heading = (8 * 0.00001 * distance_to_go * off_tk_angle) + self.track_bearing_inn
                # except ZeroDivisionError:
                #     heading = self.track_bearing_inn  # TODO: find a way to deal with straight lines
                #     print("You have straight lines don't do this!")
                # self.heading_hold(359.9)
                # self.altitude_hold(200.0)
                # print(f'z_point:{z_point},filet_angle:{filet_angle},heading:{heading}')
                self.heading_hold(heading)
                self.altitude_hold(altitude_comm=w[2])
                # self.altitude_hold(altitude_comm=30)


            if self.state == 1:
                # filet location
                q0 = self.nav.unit_dir_vector(profile[self.track_id], profile[self.track_id + 1])
                q1 = self.nav.unit_dir_vector(profile[self.track_id + 1], profile[self.track_id + 2])
                q_grad = self.nav.unit_dir_vector(q1, q0)
                w = profile[self.track_id + 1]
                # center point of arc (mirrored from radius and apex of turn)
                center_point = (w[0] - ((radius / math.cos(filet_angle / 2 * (math.pi / 180.0))) * q_grad[0]),
                                w[1] - ((radius / math.cos(filet_angle / 2 * (math.pi / 180.0))) * q_grad[1]))
                z_point = (w[0] + ((radius * math.tan(filet_angle / 2 * (math.pi / 180.0))) * q1[0]),
                           w[1] + ((radius * math.tan(filet_angle / 2 * (math.pi / 180.0))) * q1[1]))     #计算转弯结束时的点
                turning_direction = math.copysign(1, (q0[0] * q1[1]) - (q0[1] * q1[0]))
                cur = self.nav.get_local_pos()
                h_point = (cur[0] - z_point[0], cur[1] - z_point[1])
                h_val = (h_point[0] * q1[0]) + (h_point[1] * q1[1])
                if h_val > 0:
                    self.nav = None
                    self.state = 0
                    return 

                # Control circular (orbit) motion
                distance_from_center = math.sqrt(math.pow(cur[0] - center_point[0], 2) +
                                                 math.pow(cur[1] - center_point[1], 2))
                circ_x = cur[1] - center_point[1]
                circ_y = cur[0] - center_point[0]
                circle_angle = math.atan2(circ_x, circ_y)
                if circle_angle < 0:
                    circle_angle = circle_angle + (2 * math.pi)
                tangent_track = circle_angle + (turning_direction * (math.pi / 2))
                if tangent_track < 0:
                    tangent_track = tangent_track + (2 * math.pi)
                if tangent_track > 2 * math.pi:
                    tangent_track = tangent_track - (2 * math.pi)
                tangent_track = tangent_track * (180.0 / math.pi)
                error = (distance_from_center - radius) / radius
                k_orbit = 4.0
                heading = tangent_track + turning_direction * (math.atan(k_orbit * error) * (180.0 / math.pi))
                # self.heading_hold(359.9)
                # print(f'heading:{heading},')
                # print(f'z_point:{z_point},center_point:{center_point},tangent_track:{tangent_track},heading:{heading}')
                self.heading_hold(heading)
                self.altitude_hold(altitude_comm=w[2])

