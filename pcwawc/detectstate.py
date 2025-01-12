# part of https://github.com/WolfgangFahl/play-chess-with-a-webcam
'''
Created on 27.11.2019

we could have used:
see https://github.com/pytransitions/transitions
see https://www.zeolearn.com/magazine/writing-maintainable-code-using-sate-machines-in-python
but we don't for the time being

@author: wf
'''
from timeit import default_timer as timer
from pcwawc.ChessTrapezoid import FieldState, FieldColorStats

class DetectState(object):
    '''
    keeps track of the detections state
    '''

    def __init__(self,validDiffSumTreshold,invalidDiffSumTreshold,diffSumDeltaTreshold,onPieceMoveDetected=None,onMoveDetected=None):
        """ construct me """
        self.frames=0
        self.validFrames=0
        self.invalidFrames=0
        self.validDiffSumTreshold=validDiffSumTreshold
        self.invalidDiffSumTreshold=invalidDiffSumTreshold
        self.diffSumDeltaTreshold=diffSumDeltaTreshold
        self.onPieceMoveDetected=onPieceMoveDetected
        self.onMoveDetecte=onMoveDetected
        
    def check(self,validChanges,diffSum,diffSumDelta,meanFrameCount):
        """ check the detection state given the current diffSum and diffSumDelta"""
        self.invalidStarted=self.invalidFrames>3
        self.invalidStable=self.invalidFrames>=meanFrameCount,
        self.validStable=self.validFrames>=meanFrameCount     
        # trigger statistics push if valid
        if self.invalidStable:
            self.validBoard=diffSum<self.invalidDiffSumTreshold and abs(diffSumDelta)<self.diffSumDeltaTreshold and validChanges>=62
        else:
            self.validBoard=diffSum<self.validDiffSumTreshold
        if self.validBoard:
            self.validFrames+=1
        else:
            self.invalidFrames+=1      
            
    def nextFrame(self):
        self.frames+=1      
    
    def invalidEnd(self):
        self.invalidFrames=0    
        
    def validEnd(self): 
        self.validFrames=0      
        
class DetectColorState(object):
    """ detect state from Color Distribution """
    imgPath="/tmp/"
    
    def __init__(self,trapez):
        self.frames=0
        self.trapez=trapez
        self.preMoveStats=None
        
    def check(self,image,averageColors,drawDebug=False):
        self.frames+=1
        startco=timer()
        self.averageColors=averageColors
        self.image=image
        self.fieldColorStats=self.trapez.optimizeColorCheck(image,averageColors)
        endco=timer()
        if drawDebug:
            self.fieldColorStats.showStatsDebug(endco-startco)
            self.drawDebug()
        valid=self.fieldColorStats.minSelectivity>0
        if valid and self.preMoveStats is None:
            self.preMoveStats=self.fieldColorStats
        if not valid and self.preMoveStats is not None:
            for tSquare in self.trapez.genSquares():
                state=self.squareState(self.preMoveStats,tSquare, self.fieldColorStats.colorPercent[tSquare.an])
    
        
    def inRange(self,stats,fs,percent):
        minValue=stats[fs].min
        maxValue=stats[fs].max
        return percent>=minValue and percent<=maxValue
        
    def squareState(self,fieldColorStats,tSquare,percent):
        state=self.inRange(fieldColorStats.stats,tSquare.fieldState,percent) 
        return state     
    
    def drawDebug(self):
        if self.preMoveStats is not None:
            for tSquare in self.trapez.genSquares():
                state=self.squareState(self.preMoveStats,tSquare,self.fieldColorStats.colorPercent[tSquare.an])
                percent="%.0f" % (self.fieldColorStats.colorPercent[tSquare.an]) 
                color=(0,255,0) if state else (0,0,255)
                self.trapez.drawRCenteredText(self.image, percent, tSquare.rcx,tSquare.rcy,color)  
            filepath="%s/colorState-%04d.jpg" % (DetectColorState.imgPath,self.frames)    
            self.trapez.video.writeImage(self.image,filepath)          