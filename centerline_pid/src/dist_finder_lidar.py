#!/usr/bin/env python
'''
Node to measure distance to obstacles.

'''

import rospy
import math
import numpy as np
from sensor_msgs.msg import LaserScan
from slip_control_communications.msg import input_pid

# The desired velocity of the car.
# TODO make it an argument and include it in the launcher
vel = 30

pub = rospy.Publisher('error_topic', input_pid, queue_size=10)


#-------------------------------------------------------------------------------
#   Input:  data: Lidar scan data
#           beam_index: The index of the angle at which the distance is required

#   OUTPUT: distance of scan at angle theta whose index is beam_index
#-------------------------------------------------------------------------------
def getRange(data, beam_index):

    # Find the index of the array that corresponds to angle theta.
    # Return the lidar scan value at that index
    distance = data.ranges[beam_index]

    # Do some error checking for NaN and ubsurd values
    if math.isnan(distance) or distance < range_min:
        distance = 0
    if distance > range_max:
        distance = 50

    return distance


#-------------------------------------------------------------------------------
# Input:
#   data: Lidar scan data
#
# Output:
#   a two-element list. The first is the distance of the object detected at the
#   lidar's "three o' clock" and the second at its "nine o'clock"
#-------------------------------------------------------------------------------
def getLateralRanges(data):

    # The laser has a 270 degree detection angle, and an angular resolution of
    # 0.25 degrees. This means that in total there are 1080+1 beams.
    # What we need here is the distance at 45, 45+90=135 and 45+180=225 degrees
    # from the start of the detection range. These are the lateral and straight
    # on ranges at both lateral ends of the scan. The index of the beam at an
    # angle t is given by t / 0.25 hence the first index will be 45*4=180, the
    # second (45+90)*4 =540 and the third 225*4 = 900.
    # Instead of taking only one measurement, take 2 on either side of the main
    # range beam and average them.
    # Consult https://www.hokuyo-aut.jp/02sensor/07scanner/ust_10lx_20lx.html

    # Range at 45 degrees (0)
    range_right = getRange(data, 178) +
        getRange(data, 179) +
        getRange(data, 180) +
        getRange(data, 181) +
        getRange(data, 182)

    range_right = range_right / 5


    # Range at 135 degrees (90)
    range_face = getRange(data, 538) +
        getRange(data, 539) +
        getRange(data, 540) +
        getRange(data, 541) +
        getRange(data, 542)

    range_face = range_face / 5

    # Range at 225 degrees (180)
    range_left = getRange(data, 898) +
        getRange(data, 899) +
        getRange(data, 900) +
        getRange(data, 901) +
        getRange(data, 902)

    range_left = range_left / 5

    distance = []
    distance.append(range_right)
    distance.append(range_face)
    distance.append(range_left)


#-------------------------------------------------------------------------------
# Input:
#   data: Lidar scan data
#   beam_index: the beam index corresponding to the angle at which the range
#               will be found
#   length: The number of beam_indices whose corresponding range will be
#           taken
#
# Output: Depending on if the length is odd or even, a number of beams are taken
#         around beam_index in an anti-clockwise fashion. The difference
#         between consecutive scans is taken and store in list `distances`.
#         The sum of these differences determines the vehicle's orientation
#         with respect to the lane that we want it to track.
#         If the sign of the returned number is positive, that means that the
#         vehicle is facing the right boundary of the lane. If negative, the
#         left one.
#-------------------------------------------------------------------------------
def getRangeSequenceSign(data, beam_index, length):

    if length % 2 == 1:
        length = length + 1

    distances = []

    for i in range(-length/2, length/2 + 1)
        distances.append(getRange(data, beam_index + i + 1) - getRange(data, beam_index + i))

    return sum(distance)



#-------------------------------------------------------------------------------
# callback
#-------------------------------------------------------------------------------
def callback(data):
    #swing = math.radians(theta)

    # The list where the lateral ranges is stored
    ranges_list = getLateralRanges(data)

    # The disparity between the two ranges.
    # This difference is expressed between the right and left lateral ranges.
    # Regardless of the car's orientation, R - L < 0 means that the car is at
    # the right half of the road and needs to turn left, which means that the
    # signal going to the motor will be negative (the sign of the difference).
    # The opposite case is analogous to this one.
    R = ranges_list(0)
    F = ranges_list(1)
    L = ranges_list(2)


    # Fire auxiliary scans around the front facing one.
    # This will facilitate the discovery of the vehicle's orientation with
    # respect to the lane. Take rays across +-{1,2,3,4,5} degrees around F
    # __anti-clockwise__.
    # If the sequence is decreasing then the vehicle is facing the left wall.
    # If the sequence is increasing then the vehicle is facing the right wall.


    # The overall angular error is: see
    # https://gits-15.sys.kth.se/alefil/HT16_P2_EL2425_resources/blob/master/Progress%20reports/2016.11.16/main.pdf
    # The scaling factor R+L is there to make the range disparity invariant to
    # the width of the lane

    CCp = 5
    tan_arg_1 = float(L-R) / ((2 * CCp) * (L+R))

    # Take a range scan sequence starting from 1 degree to the right of the main
    # beam at 0 degrees with respect to the longitudinal axis of the vehicle,
    # and ending at one degree to the left of it. If the number returned is
    # positive then the vehicle is facing the right lane boundary. If not,
    # it's facing the left.
    if getRangeSequenceSign(data, 540, 8) > 0:
        tan_arg_2 = -float(R) / F
    else:
        tan_arg_2 = float(L) / F

    # If the steering angle to the left requires a negative sign and the
    # steering angle to the right requires a positive sign, then the vehicle
    # should turn left if it is facing the right wall and right if it is
    # facing the left wall. If the vehicle lies at the leftmost half of the
    # lane, then it should turn right, and if it lies at the rightmost half,
    # it should turn left.
    error =  -np.arctan(tan_arg_1) + np.arctan(tan_arg_2)

    # Check for angular overflow
    while error > np.pi:
        error -= 2*np.pi
    while angle_error < -np.pi:
        error += 2*np.pi


    # Create the message that is to be sent to the pid controller,
    # pack all relevant information (error and default velocity)
    # and publish it
    msg = input_pid()
    msg.pid_error = error
    msg.pid_vel = vel
    pub.publish(msg)



#-------------------------------------------------------------------------------
# main
#-------------------------------------------------------------------------------
if __name__ == '__main__':

    rospy.init_node('dist_finder_lidar_node', anonymous = True)
    print("[Node] dist_finder_lidar started")

    rospy.Subscriber("scan", LaserScan, callback)
    rospy.spin()
