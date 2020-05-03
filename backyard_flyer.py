import argparse
import time
from enum import Enum

import numpy as np

from udacidrone import Drone
from udacidrone.connection import MavlinkConnection, WebSocketConnection  # noqa: F401
from udacidrone.messaging import MsgID


class States(Enum):
    MANUAL = 0
    ARMING = 1
    TAKEOFF = 2
    WAYPOINT = 3
    LANDING = 4
    DISARMING = 5


class BackyardFlyer(Drone):

    def __init__(self, connection):
        super().__init__(connection)
        self.target_position = np.array([0.0, 0.0, 0.0])
        self.all_waypoints = []
        self.in_mission = True
        self.check_state = {}
        self.current_waypoint_index = 0

        # initial state
        self.flight_state = States.MANUAL

        # TODO: Register all your callbacks here
        self.register_callback(MsgID.LOCAL_POSITION, self.local_position_callback)
        self.register_callback(MsgID.LOCAL_VELOCITY, self.velocity_callback)
        self.register_callback(MsgID.STATE, self.state_callback)

    def local_position_callback(self):
        """
        TODO: Implement this method

        This triggers when `MsgID.LOCAL_POSITION` is received and self.local_position contains new data
        """
        if self.flight_state is States.TAKEOFF:
            # check that flight is near the desired altitude
            altitude = -self.local_position[2]

            if altitude > 0.95 * 3.0:
                # store all the desired way points
                self.all_waypoints = self.calculate_box()
                # start transition between waypoints
                self.waypoint_transition()

        elif self.flight_state is States.WAYPOINT:
            # calculate the euclidean distance between the current and traget positions
            # exclude the orientation from the calculation (last element)
            eucli_dist = np.linalg.norm(self.target_position[:2] - self.local_position[:2])

            # when the euclidean distance is too small, this indicates that we reached the target
            # and time for the next waypoint transition only when the drone came to stop that's
            # why we need to check the velocity magnitude as well.
            if eucli_dist < 1.0 and np.linalg.norm(self.local_velocity[:2]) < 0.2:
                # if the current target position is last waypoint then switch to landing
                if self.target_position is not self.all_waypoints[-1]:
                    self.waypoint_transition()
                else:
                    self.landing_transition()



    def velocity_callback(self):
        """
        TODO: Implement this method

        This triggers when `MsgID.LOCAL_VELOCITY` is received and self.local_velocity contains new data
        """
        if self.flight_state is States.LANDING:
            if ((self.global_position[2] - self.global_home[2] < 0.1) and
                abs(self.local_position[2]) < 0.01):
                self.disarming_transition()

    def state_callback(self):
        """
        TODO: Implement this method

        This triggers when `MsgID.STATE` is received and self.armed and self.guided contain new data
        """
        if not self.in_mission:
            return

        if self.flight_state is States.MANUAL:
            self.arming_transition()
        elif self.flight_state is States.ARMING:
            if self.armed:
                self.takeoff_transition()
        elif self.flight_state is States.DISARMING:
            if not self.armed:
                self.manual_transition()

    def calculate_box(self):
        """TODO: Fill out this method
        
        1. Return waypoints to fly a box
        """
        box_waypoints = [np.array([8., 0., 3., 0.]),
                         np.array([8., 8., 3., 0.]),
                         np.array([0., 8., 3., 0.]), 
                         np.array([0., 0., 3., 0.])]
        return box_waypoints

    def arming_transition(self):
        """TODO: Fill out this method
        
        1. Take control of the drone
        2. Pass an arming command
        3. Set the home location to current position
        4. Transition to the ARMING state
        """
        print("arming transition")

        self.take_control()
        self.arm()

        # set the current location to be the home position
        self.set_home_position(self.global_position[0],
                               self.global_position[1],
                               self.global_position[2])

        self.flight_state = States.ARMING

    def takeoff_transition(self):
        """TODO: Fill out this method
        
        1. Set target_position altitude to 3.0m
        2. Command a takeoff to 3.0m
        3. Transition to the TAKEOFF state
        """
        print("takeoff transition")

        target_altitude = 3.0
        self.target_position[2] = target_altitude
        self.takeoff(target_altitude)
        self.flight_state = States.TAKEOFF

    def waypoint_transition(self):
        """TODO: Fill out this method
    
        1. Command the next waypoint position
        2. Transition to WAYPOINT state
        """
        print("waypoint transition")

        self.target_position = self.all_waypoints[self.current_waypoint_index]
        # print(self.target_position)
        if self.current_waypoint_index < len(self.all_waypoints):
            self.cmd_position(self.target_position[0], self.target_position[1], self.target_position[2], self.target_position[3])
            # increment the index to the next target position
            self.current_waypoint_index += 1
            self.flight_state = States.WAYPOINT


    def landing_transition(self):
        """TODO: Fill out this method
        
        1. Command the drone to land
        2. Transition to the LANDING state
        """
        print("landing transition")

        self.land()
        self.flight_state = States.LANDING

    def disarming_transition(self):
        """TODO: Fill out this method
        
        1. Command the drone to disarm
        2. Transition to the DISARMING state
        """
        print("disarm transition")

        self.disarm()
        self.flight_state = States.DISARMING

    def manual_transition(self):
        """This method is provided
        
        1. Release control of the drone
        2. Stop the connection (and telemetry log)
        3. End the mission
        4. Transition to the MANUAL state
        """
        print("manual transition")
        self.current_waypoint_index = 0
        self.release_control()
        self.stop()
        self.in_mission = False
        self.flight_state = States.MANUAL

    def start(self):
        """This method is provided
        
        1. Open a log file
        2. Start the drone connection
        3. Close the log file
        """
        print("Creating log file")
        self.start_log("Logs", "NavLog.txt")
        print("starting connection")
        self.connection.start()
        print("Closing log file")
        self.stop_log()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5760, help='Port number')
    parser.add_argument('--host', type=str, default='127.0.0.1', help="host address, i.e. '127.0.0.1'")
    args = parser.parse_args()

    conn = MavlinkConnection('tcp:{0}:{1}'.format(args.host, args.port), threaded=False, PX4=False)
    #conn = WebSocketConnection('ws://{0}:{1}'.format(args.host, args.port))
    drone = BackyardFlyer(conn)
    time.sleep(2)
    drone.start()
