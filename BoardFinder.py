#!/usr/bin/python
# -*- encoding: utf-8 -*-
# part of https://github.com/WolfgangFahl/play-chess-with-a-webcam

# Global imports
from Video import Video
from math import sin, cos, sqrt, pi, atan2, degrees
import cv2
import cv2 as cv
import numpy as np
from collections import deque
import bisect

# Local imports
from MovementDetector import MovementDetector
from mathUtils import (intersect, distance, median, findBoundingSkewedSquare,
                       getRotationAndTranslationMatrix)

CHESSCAM_WIDTH = 640
CHESSCAM_HEIGHT = 480
CHESSCAM_PARZEN_THRESHOLD = 5
CHESSCAM_ORIENTATION_SMOOTHING = 5
CHESSCAM_COORDINATES_SMOOTHING = 8

smoothFunc = lambda x: sum(x) / float(len(x))


class BadSegmentation(Exception):
    pass

# Board Finder
class BoardFinder(object):
    debug=True

    # construct me from the given input Image
    def __init__(self, inImage):
        self.video=Video()
        self.frame = inImage

    def prepare(self):
        # Init smoothing angle
        self.smoothOrientation = deque([], CHESSCAM_ORIENTATION_SMOOTHING)
        self.smoothCoordinates = deque([], CHESSCAM_COORDINATES_SMOOTHING)

        # Find the board the first time
        self.updateImage(inImage)

        # Temporary rotation
        self.initialRotation = 0

        # Find the rotation of the board
        side = self.getBlackMaxSide(cv.fromarray(self.GetFullImageBoard()[0]))

        # 0:top,1:left,2:bottom,3:right.
        optionsRotation = {0: 0,
                           1: -90,
                           2: 180,
                           3: 90}
        # 0:top,1:left,2:bottom,3:right. (x,y) offset of dominator
        optionsDominator = {0: (0, -1),
                            1: (-1, 0),
                            2: (0, 1),
                            3: (1, 0)}
        #Black's initial position sets the correction move to place black team at the top.
        self.initialRotation = optionsRotation[side]
        self.dominatorOffset = optionsDominator[side]

    def getDominatorOffset(self):
        return self.dominatorOffset

    def updateImage(self, inFrame):
        """Adds a new image to the boardFinder algorithms.
        This performs an Hough Transform and HSV conversion to the image and
        computes the orientation and coordinates from these."""

        if self.frame is not None:
            self.lines=self.video.houghTransform(self.frame)
            if BoardFinder.debug:
                print ("found %d lines" % (self.lines.size))
            self.BoardOrientation = self.DetectBoardOrientation()
            if all(self.BoardOrientation):
                self.boardCoordinates = self.GetChessBoardCoordinates(
                    smoothFunc(list(zip(*self.smoothOrientation))[0]))


    def DetectBoardOrientation(self):
        """Finds the two dominants angles of the Hough Transform.

        Returns: 2-tuple containing the two dominant angles. (None, None) if
                 none were found."""
        # Ensure Hough lines were already found
        if len(self.lines) <= 0:
            return (None, None)

        # https://answers.opencv.org/question/2966/how-do-the-rho-and-theta-values-work-in-houghlines/
        # get the theta values
        slopes = sorted([line[0][1] for line in self.lines])
        # Parzen window (KernelDensityEstimator) using a Rect function, comonly named a moving average
        # Perform frequence to time conversion, signal analysis FTW
        # KernelSize is the dynamic range kernel size (bin length)
        KernelSize = pi / 64.
        KDE = {}
        for slope in set(slopes):
            beginElement = bisect.bisect_left(slopes, slope - KernelSize)
            endElement = bisect.bisect_right(slopes, slope + KernelSize)
            # Threshold
            if endElement - beginElement > CHESSCAM_PARZEN_THRESHOLD:
                KDE[slope] = endElement - beginElement
        bins = sorted(KDE.items())
        if len(bins) <= 0:
            return (None, None)

        # Let's find the maximum number of lines in this range
        angleMostOftenDetected = max(bins, key=lambda x: x[1])
        if BoardFinder.debug:
            print ("the most often detected line angle is %d°" % degrees(angleMostOftenDetected[0]))

        # Theil-Sen estimator for noise robustness
        # why not use https://docs.scipy.org/doc/scipy-0.15.1/reference/generated/scipy.stats.mstats.theilslopes.html ?
        MaximumChanceAngle = median([a[0] for a in bins if a[1] == angleMostOftenDetected[1] and abs(a[0] - angleMostOftenDetected[0]) < KernelSize])

        # Get second angle
        try:
            otherAngle = max((a for a in bins if a[0] > angleMostOftenDetected[0] + 0.2 or a[0] < angleMostOftenDetected[0] - 0.2), key=lambda x: x[1])
            MaximumChanceAngle2 = median([a[0] for a in bins if a[1] == otherAngle[1] and abs(a[0] - otherAngle[0]) < KernelSize])
        except:
            # TODO: Don't write generic excepts!!!
            return (None, None)

        retValue = sorted([MaximumChanceAngle, -abs(MaximumChanceAngle2)],
                          key=lambda x: abs(x))

        if BoardFinder.debug:
            print ("Boardorientation %f.2° - %f.2°" % (degrees(retValue[0]),degrees(retValue[1])))
        # Record return value for smoothing purposes
        self.smoothOrientation.appendleft(retValue)
        return retValue

    def GetChessBoardCoordinates(self, rotation):
        """Gets the four points that defines the rectangle where the chessboard
        is bound.

        Returns: 4-tuple of 2-tuples containing (x, y) values of the 4 corners
                 of the chessboard."""
        # Blur image and convert it to HSV
        # https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_imgproc/py_filtering/py_filtering.html
        self.hsv =cv2.blur(self.frame,(8,8))

        # De-Rotate the hsv version of the image to support rotated chessboards
        # Because marker detection is really cheaply done
        rotationMatrix = getRotationAndTranslationMatrix(-rotation, (0, 0))
        hsv2 = cv2.warpPerspective(np.asarray(self.hsv[:,:]),
                                   rotationMatrix,
                                   (CHESSCAM_WIDTH, CHESSCAM_HEIGHT))
        self.hsv = cv2.cvtColor(hsv2, cv.CV_BGR2HSV)

        # Threshold the HSV value
        # Green is between ~70 and ~120, and our tape is between saturation 85 and 255.
        self.debugimg = cv2.inRange(self.hsv,
                                    np.array([70, 85, 0], np.uint8),
                                    np.array([120, 255, 255], np.uint8))
        contours, hierarchy = cv2.findContours(self.debugimg,
                                               cv2.RETR_TREE,
                                               cv2.CHAIN_APPROX_SIMPLE)
        mini, maxi = (CHESSCAM_WIDTH, CHESSCAM_HEIGHT), (0, 0)
        ur, ll = (0, 0), (0, 0)
        for cnt in contours:
            cnt_len = cv2.arcLength(cnt, True)
            cnt = cv2.approxPolyDP(cnt, 0.01*cnt_len, True)
            for a in cnt:
                #cv2.circle(np.asarray(self.colorlaplace[:,:]), tuple(a[0]), 10, cv.CV_RGB(255, 0, 255), 6)
                if sqrt(a[0][0]**2 + a[0][1]**2) < sqrt(mini[0]**2 + mini[1]**2):
                    mini = (a[0][0], a[0][1])
                if sqrt((a[0][0] - CHESSCAM_WIDTH)**2 + (a[0][1] - CHESSCAM_HEIGHT)**2) < sqrt((maxi[0] - CHESSCAM_WIDTH)**2 + (maxi[1] - CHESSCAM_HEIGHT)**2):
                    maxi = (a[0][0], a[0][1])
                if sqrt((a[0][0] - CHESSCAM_WIDTH)**2 + a[0][1]**2) < sqrt((ur[0] - CHESSCAM_WIDTH)**2 + ur[1]**2):
                    ur = (a[0][0], a[0][1])
                if sqrt(a[0][0]**2 + (a[0][1] - CHESSCAM_HEIGHT)**2) < sqrt(ll[0]**2 + (ll[1] - CHESSCAM_HEIGHT)**2):
                    ll = (a[0][0], a[0][1])

        # Debug
        #cv2.circle(np.asarray(self.frame[:,:]), mini, 10, cv.CV_RGB(255, 255, 0), 6)
        #cv2.circle(np.asarray(self.frame[:,:]), maxi, 10, cv.CV_RGB(255, 255, 0), 3)

        # De-rotate the points computed
        points = np.array(
                    [mini[0], ur[0], ll[0], maxi[0],
                     mini[1], ur[1], ll[1], maxi[1],
                     1,       1,     1,     1]
                    ).reshape((3,4))
        deRotationMatrix = getRotationAndTranslationMatrix(rotation, (0, 0))
        mini, ur, ll, maxi = np.transpose(np.dot(deRotationMatrix, points))

        # Convert back to OpenCV1 (TODO: Keep in CV2)
        self.debugimg = cv.fromarray(self.debugimg)

        # Set return value and keep it for smoothing purposes
        retValue = (mini[0], mini[1]), \
                   (ur[0], ur[1]), \
                   (ll[0], ll[1]), \
                   (maxi[0], maxi[1])
        self.smoothCoordinates.appendleft(retValue)
        return retValue

    def LineCrossingDetection(self):
        """Gets the Hough line intersections."""
        # TODO: Speed this up
        self.intersects = []

        # Print Orientation
        cv.Line(self.colorlaplace,
            (int(CHESSCAM_WIDTH / 2 - 50 * cos(self.BoardOrientation[0])), int(CHESSCAM_HEIGHT / 2 - 50 * sin(self.BoardOrientation[0]))),
            (int(CHESSCAM_WIDTH / 2 + 50 * cos(self.BoardOrientation[0])), int(CHESSCAM_HEIGHT / 2 + 50 * sin(self.BoardOrientation[0]))),
            cv.CV_RGB(0, 255, 0), 1, 8)
        cv.Line(self.colorlaplace,
            (int(CHESSCAM_WIDTH / 2 - 50 * cos(self.BoardOrientation[1])), int(CHESSCAM_HEIGHT / 2 - 50 * sin(self.BoardOrientation[1]))),
            (int(CHESSCAM_WIDTH / 2 + 50 * cos(self.BoardOrientation[1])), int(CHESSCAM_HEIGHT / 2 + 50 * sin(self.BoardOrientation[1]))),
            cv.CV_RGB(0, 255, 0), 1, 8)

        # Find crossing points
        for line in self.lines:
            cv.Line(self.colorlaplace,
                    line[0],
                    line[1],
                    cv.CV_RGB(255, 0, 0),
                    1,
                    8)
            for crossline in self.lines:
                if line != crossline:
                    thisIntersect = intersect(line[0],
                                              line[1],
                                              crossline[0],
                                              crossline[1])

                    if thisIntersect and \
                    all([a > 0 for a in thisIntersect]) and \
                    all([thisIntersect[0] < CHESSCAM_WIDTH, thisIntersect[1] < CHESSCAM_HEIGHT]):
                        intersectSecondary = intersect(line[0],line[1],crossline[0],crossline[1])
                        found=False
                        for intersectPrimary in self.intersects:
                            if found:
                                continue
                            if distance(intersectPrimary, intersectSecondary) < 20:
                                found=True
                        if found == False:
                            self.intersects.append(intersectSecondary)

        for intersection in self.intersects:
            cv.Circle(self.colorlaplace, intersection, 1, cv.CV_RGB(255, 0, 0), 2)

    def GetFullImageBoard(self, rectCoordinates=None, rotations=None):
        """Applies the homography needed to make the bounding rectangle
        defined by rectCoordinates and rotation become the full size of the
        image.

        rectCoordinates: Position of the minimum and maximum point of the
            bounding rectangle. Must be of form: ((x1, y1), (x2, y2))
        rotation: Rotation angle in radians.

        Returns: A list of two images containing only the chessboard.
            The first one is a colored image and the second one is a laplacian
            transform of the first image"""

        if rotations == None:
            rotations = [sum(y) / float(len(y)) for y in zip(*self.smoothOrientation)]
        if rectCoordinates == None:
            rectCoordinates = []
            for groupedCoordinates in zip(*self.smoothCoordinates):
                smoothDataTmp = [0, 0]
                for thisCoordinate in groupedCoordinates:
                    smoothDataTmp[0] += thisCoordinate[0]
                    smoothDataTmp[1] += thisCoordinate[1]
                rectCoordinates.append(tuple([a / float(len(groupedCoordinates)) for a in smoothDataTmp]))

        points = tuple(rectCoordinates)

        # Debug
        #cv.Circle(self.colorlaplace, (int(points[0][0]), int(points[0][1])), 1, cv.CV_RGB(0, 255, 255), 5)
        #cv.Circle(self.colorlaplace, (int(points[1][0]), int(points[1][1])), 1, cv.CV_RGB(0, 255, 0), 5)
        #cv.Circle(self.colorlaplace, (int(points[2][0]), int(points[2][1])), 1, cv.CV_RGB(0, 0, 255), 5)
        #cv.Circle(self.colorlaplace, (int(points[3][0]), int(points[3][1])), 1, cv.CV_RGB(255, 255, 255), 5)
        #for x in points:
        #    cv.Circle(self.colorlaplace, (int(x[0]), int(x[1])), 1, cv.CV_RGB(0, 255, 255), 5)

        # Define homography references points sequences
        try:
            src = np.array(points, np.float32).reshape((4, 2))
        except ValueError:
            raise BadSegmentation
        dst = np.array([0, 0,
                        CHESSCAM_WIDTH, 0,
                        0, CHESSCAM_HEIGHT,
                        CHESSCAM_WIDTH, CHESSCAM_HEIGHT], np.float32).reshape((4, 2))

        # Find the homography matrix and apply it
        H, status = cv2.findHomography(src, dst, 0)
        self.debugimg = cv2.warpPerspective(np.asarray(self.frame[:,:]),
                                            H,
                                            (CHESSCAM_WIDTH, CHESSCAM_HEIGHT))
        self.debugimg = cv.fromarray(self.debugimg)

        self.laplacianImage = cv2.warpPerspective(np.asarray(self.laplacianImage[:,:]),
                                            H,
                                            (CHESSCAM_WIDTH, CHESSCAM_HEIGHT))
        self.laplacianImage = cv.fromarray(self.laplacianImage)

        cv.Circle(self.frame, (int(points[0][0]), int(points[0][1])), 1, cv.CV_RGB(0, 255, 255), 5)
        cv.Circle(self.frame, (int(points[1][0]), int(points[1][1])), 1, cv.CV_RGB(0, 255, 0), 5)
        cv.Circle(self.frame, (int(points[2][0]), int(points[2][1])), 1, cv.CV_RGB(0, 0, 255), 5)
        cv.Circle(self.frame, (int(points[3][0]), int(points[3][1])), 1, cv.CV_RGB(255, 255, 255), 5)

        self.debugimg = self.rotateImage(self.debugimg)

        return [self.debugimg, self.laplacianImage, self.frame]


    def getBlackMaxSide(self, colorImage):
        """This function returns the side of black's team, if game is at
        starting position. 0:top, 1:left, 2:bottom, 3:right"""

        # convert to HSV for simpler handling
        # see e.g. https://stackoverflow.com/questions/17063042/why-do-we-convert-from-rgb-to-hsv
        # Convert BGR to HSV
        tmp = cv2.cvtColor(colorImage, cv2.COLOR_BGR2HSV)

        H,W = tmp.shape[:2]

        top = self.video.getSubRect(tmp, (0, 0, W, H//4))
        left = self.video.getSubRect(tmp, (0, 0, W//4, H))
        bottom = self.video.getSubRect(tmp, (0, H*3//4, W, H//4))
        right = self.video.getSubRect(tmp, (W*3//4, 0, W//4, H))

        whitenesses = []
        whitenesses.append(self.video.sum(top,2))
        whitenesses.append(self.video.sum(left,2))
        whitenesses.append(self.video.sum(bottom,2))
        whitenesses.append(self.video.sum(right,2))

        return whitenesses.index(min(whitenesses))

    # rotate the Image
    def rotateImage(self, image):
        """Flips the board in order to always have a1 on the top-left corner"""
        src = np.asarray(cv.GetMat(image)[:,:])

        if self.initialRotation == -90:
            #rotate left
            src = cv2.transpose(src);
            src = cv2.flip(src, 1);
        elif self.initialRotation == 90:
            #rotate right
            src = cv2.flip(src, 1);
            src = cv2.transpose(src);
        elif self.initialRotation == 180:
            #turn around
            src = cv2.flip(src, -1);

        return src
