#!/usr/bin/python
# -*- encoding: utf-8 -*-
# part of https://github.com/WolfgangFahl/play-chess-with-a-webcam
import numpy as np
from enum import IntEnum
import cv2
import chess
from Video import Video

class Transformation(IntEnum):
    """ Transformation kind"""
    RELATIVE=0 # 1.0 x 1.0
    IDEAL=1 # e.g. 640x640
    ORIGINAL=2 # whatever the image size is
    
class ChessTrapezoid:
    """ Chess board Trapezoid (UK) / Trapezium (US) / Trapez (DE)  as seen via a webcam image """

    debug=True
    showDebugImage=False
    rows=8
    cols=8
  
    def __init__(self,topLeft,topRight,bottomRight,bottomLeft,idealSize=640):
        """ construct me from the given corner points"""
        self.tl,self.tr,self.br,self.bl=topLeft,topRight,bottomRight,bottomLeft
        self.polygon=np.array([topLeft,topRight,bottomRight,bottomLeft],dtype=np.int32)
        # prepare the perspective transformation
        # https://stackoverflow.com/questions/27585355/python-open-cv-perspectivetransform
        # https://stackoverflow.com/a/41768610/1497139
        # the destination
        pts_dst = np.asarray([topLeft,topRight,bottomRight,bottomLeft],dtype=np.float32)
        # the normed square described as a polygon in clockwise direction with an origin at top left
        self.pts_normedSquare = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],dtype=np.float32)
        self.transform=cv2.getPerspectiveTransform(self.pts_normedSquare,pts_dst)
        self.idealSize=idealSize
        s=idealSize
        self.pts_IdealSquare = np.asarray([[0.0, 0.0], [s, 0.0], [s, s], [0.0, s]],dtype=np.float32)
        self.inverseTransform=cv2.getPerspectiveTransform(pts_dst,self.pts_IdealSquare)
        self.rotation=0
        # trapezoid representation of squares
        self.tsquares={}
        for square in chess.SQUARES:
            tsquare=ChessTSquare(self,square)
            if ChessTrapezoid.debug:
                print(vars(tsquare))
            self.tsquares[square]=tsquare

    def relativeXY(self,rx,ry):
        """ convert a relative 0-1 based coordinate to a coordinate in the trapez"""
        # see https://math.stackexchange.com/questions/2084647/obtain-two-dimensional-linear-space-on-trapezoid-shape
        # https://stackoverflow.com/a/33303869/1497139
        rxry = np.asarray([[rx, ry]],dtype=np.float32)
        # target array - values are irrelevant because the will be overridden
        xya=cv2.perspectiveTransform(np.array([rxry]),self.transform)
        # example result:
        # ndarray: [[[20. 40.]]]
        xy=xya[0][0]
        x,y=xy[0],xy[1]
        return x,y

    def tSquareAt(self,row,col):
        """ get the trapezoid chessboard square for the given row and column"""
        row,col=self.rotateIndices(row, col)
        squareIndex = (ChessTrapezoid.rows-1-row) * ChessTrapezoid.cols + col;
        square = chess.SQUARES[squareIndex]
        return self.tsquares[square]

    def rotateIndices(self,row,col):
        """ rotate the indices or rows and columns according to the board rotation"""
        if self.rotation==0:
            return row,col
        elif self.rotation==90:
            return ChessTrapezoid.cols-1-col,row
        elif self.rotation==180:
            return ChessTrapezoid.rows-1-row,ChessTrapezoid.cols-1-col
        elif self.rotation==270:
            return col,ChessTrapezoid.rows-1-row
        else:
            raise Exception("invalid rotation %d for rotateIndices" % self.rotation)

    def getEmptyImage(self,image,channels=1):
        """ prepare a trapezoid/polygon mask to focus on the square chess field seen as a trapezoid"""
        h, w = image.shape[:2]
        emptyImage=self.getEmtpyImage4WidthAndHeight(w, h, channels)
        return emptyImage
    
    def getEmtpyImage4WidthAndHeight(self,w,h,channels):    
        emptyImage = np.zeros((h,w,channels), np.uint8)
        return emptyImage

    def drawPolygon(self,image,polygon,color):
        cv2.fillConvexPoly(image,polygon,color)

    def maskImage(self,image,mask):
        """ return the masked image that filters the trapezoid view"""
        masked=cv2.bitwise_and(image,image,mask=mask)
        return masked

    def updatePieces(self,fen):
        """ update the piece positions according to the given FEN"""
        self.board=chess.Board(fen)
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            tsquare=self.tsquares[square]
            tsquare.piece=piece
            tsquare.fieldState=tsquare.getFieldState()

    def drawFieldStates(self,image,fieldStates,transformation=Transformation.ORIGINAL,color=(64)):
        """ draw the field states e.g. to set the mask image that will filter the trapezoid view according to piece positions when using maskImage"""
        if self.board is not None:
            for square in chess.SQUARES:
                tsquare=self.tsquares[square]
                if tsquare.fieldState in fieldStates:
                    tsquare.drawState(image,transformation,color)

    def warpedBoard(self,image):
        h, w = image.shape[:2]
        warped=cv2.warpPerspective(image,self.inverseTransform,(w,h))
        return warped

    def idealColoredBoard(self,w,h,transformation=Transformation.IDEAL):
        idealImage=self.getEmtpyImage4WidthAndHeight(w,h,3)
        for square in chess.SQUARES:
            tsquare=self.tsquares[square]
            color=self.averageColors[tsquare.fieldState]
            tsquare.drawState(idealImage,transformation,color)
        return idealImage

    def byFieldState(self):
        # get a dict of fields sorted by field state
        sortedTSquares={}
        for square in chess.SQUARES:
            tsquare=self.tsquares[square]
            if not tsquare.fieldState in sortedTSquares:
                sortedTSquares[tsquare.fieldState]=[]
            sortedTSquares[tsquare.fieldState].append(tsquare)
        return sortedTSquares

    def analyzeColors(self,image,video=Video()):
        """ get the average colors per fieldState """
        self.averageColors={}
        warped=self.warpedBoard(image)
        byFieldState=self.byFieldState()
        for fieldState in FieldState:
            mask=self.getEmptyImage(warped)
            self.drawFieldStates(mask,[fieldState],Transformation.IDEAL)
            masked=self.maskImage(image,mask)
            #https://stackoverflow.com/a/43112217/1497139
            avg_color_per_row = np.average(masked, axis=0)
            avg_color = np.average(avg_color_per_row, axis=0)
            # the average color is based on a empty image with a lot of black pixels. Correct the average
            # (at least a bit) accordingly
            countedFields=len(byFieldState[fieldState])
            factor=1 if countedFields==0 else 64/countedFields
            avg_color=avg_color*factor
            self.averageColors[fieldState]=avg_color.tolist()
            if ChessTrapezoid.showDebugImage:
                video.showImage(masked,fieldState.title())
            if ChessTrapezoid.debug:
                b,g,r=avg_color.tolist()
                print("%15s: %3d, %3d, %3d" % (fieldState.title(),b,g,r))

class FieldState(IntEnum):
    """ the state of a field is a combination of the field color with a piece color + two empty field color options"""
    WHITE_EMPTY = 0
    WHITE_WHITE = 1
    WHITE_BLACK = 2
    BLACK_EMPTY = 3
    BLACK_WHITE = 4
    BLACK_BLACK = 5

    def title(self,titles=["white empty", "white on white", "black on white","black empty","white on black","black on black"]):
        return titles[self]


class ChessTSquare:
    """ a chess square in it's trapezoidal perspective """
    # relative position and size of original square
    rw=1/(ChessTrapezoid.rows)
    rh=1/(ChessTrapezoid.cols)

    def __init__(self,trapez,square):
        ''' construct me from the given trapez  and square '''
        self.trapez=trapez
        self.square=square
        self.an=chess.SQUARE_NAMES[square]
        self.row=ChessTrapezoid.rows-1-chess.square_rank(square)
        self.col=chess.square_file(square)
        # https://gamedev.stackexchange.com/a/44998/133453
        self.fieldColor=chess.WHITE if (self.col+self.row) % 2 == 1 else chess.BLACK
        self.fieldState=None
        self.piece=None

        self.rx,self.ry=self.row*ChessTSquare.rw,self.col*ChessTSquare.rh
        self.x,self.y=trapez.relativeXY(self.rx, self.ry)
        self.setPolygons(trapez,self.rx,self.ry,self.rx+ChessTSquare.rw,self.ry,self.rx+ChessTSquare.rw,self.ry+ChessTSquare.rh,self.rx,self.ry+ChessTSquare.rh)

    def setPolygons(self,trapez,rtl_x,rtl_y,rtr_x,rtr_y,rbr_x,rbr_y,rbl_x,rbl_y):
        """ set my relative and warped polygons from the given relative corner coordinates from top left via top right, bottom right to bottom left """
        self.rpolygon=np.array([(rtl_x,rtl_y),(rtr_x,rtr_y),(rbr_x,rbr_y),(rbl_x,rbl_y)])
        self.idealPolygon=(self.rpolygon*trapez.idealSize).astype(np.int32)
        self.polygon=np.array([trapez.relativeXY(rtl_x,rtl_y),trapez.relativeXY(rtr_x,rtr_y),trapez.relativeXY(rbr_x,rbr_y),trapez.relativeXY(rbl_x,rbl_y)])
        self.ipolygon=self.polygon.astype(np.int32)

    def getPolygon(self,transformation):
        if transformation==Transformation.ORIGINAL:
            return self.ipolygon
        elif transformation==Transformation.RELATIVE:
            return self.rpolygon
        elif transformation==Transformation.IDEAL:
            return self.idealPolygon
        else:
            raise Exception("invalid transformation %d for getPolygon",transformation)   
        
    def getFieldState(self):
        piece = self.piece
        if piece is None:
            if self.fieldColor == chess.WHITE:
                return FieldState.WHITE_EMPTY
            else:
                return FieldState.BLACK_EMPTY
        elif piece.color == chess.WHITE:
            if self.fieldColor == chess.WHITE:
                return FieldState.WHITE_WHITE
            else:
                return FieldState.BLACK_WHITE
        else:
            if self.fieldColor == chess.WHITE:
                return FieldState.WHITE_BLACK
            else:
                return FieldState.BLACK_BLACK
        # this can't happen
        return None

    def drawState(self,image,transformation,color):
        """ draw my state onto the given image with the given transformation and color """
        self.trapez.drawPolygon(image,self.getPolygon(transformation),color)
