#############################################################################################
#      Author: Austin Harrison
#        Date: 30APR2022
# Description: This Class is the Top Level Game Abstraction
#############################################################################################

from hashlib import new
from LCD_Class import waveShareDisplay
from LCD_Constants import *
from JoyStick_Class import JoySticks
from PongBall_Class import PongBall
from Player_Class import Player
from threading import Thread, Semaphore
import queue
import time
import random

C_MAX_BALLS         =  7
C_X_IDX             =  0
C_Y_IDX             =  1
C_TOP_COLLISION     =  2
C_RIGHT_COLLISION   =  1
C_NO_COLLISION      =  0
C_LEFT_COLLISION    = -1
C_BOTTOM_COLLISION  = -2
C_WIGGLE_ROOM       =  2

#############################################################################################
# BEGIN - Class Definitions
#############################################################################################
class Pong():
    def __init__(self) -> None:
        self._lcd           = waveShareDisplay()
        self._joystick      = JoySticks()
        self._balls         = []
        self._spiSem        = Semaphore()
        self._q1            = queue.Queue()
        self._q2            = queue.Queue()
        self._player1       = Player("One")
        self._player2       = Player("Two")
        self.mExitRequest   = False
        self.mNumBalls      = 0

    #############################################################################################
    # BEGIN - Player Member Functions
    #############################################################################################
    # Draws the paddle for the first time.
    def _drawPaddleInitial(self, player: Player) -> None:
        xy = player.mGetLoc()
        startPixel = xy[C_X_IDX] - (player.WIDTH >> 1)
        endPixel   = xy[C_X_IDX] + (player.WIDTH >> 1)
        self._spiSem.acquire()
        for i in range(startPixel, endPixel):
            self._lcd.mSetPixel(i, xy[C_Y_IDX], player.color)

        self._spiSem.release()

    def _normalizeADC(self, val: int) -> int:
        if val <= 127 or val >= 896:
            return 5

        elif 127 < val <= 254 or 896 > val >= 769:
            return 4

        elif 254 < val <= 381 or 769 > val > 642:
            return 3
            
        elif 381 < val or 642 > val:
            return 0

    def mDrawPaddle(self, player: Player) -> None:
        p     = player.mGetLoc()
        pPrev = player.mGetPrevLoc()
        x     = p[C_X_IDX]
        xPrev = pPrev[C_X_IDX]
        if x != xPrev:
            if x > xPrev:
                deltaX     = x - xPrev
                # Moving Right
                # Start pixel would be the right end of the paddle of the 
                # previous position
                startPixel = xPrev + (player.WIDTH >> 1)
                # The end pixel would be the right end of the paddle plus
                # the delta (x - xPrev)
                endPixel   = xPrev + (player.WIDTH >> 1) + deltaX
                
            # xPrev > x
            else:
                deltaX     = xPrev - x
                # Moving Left
                # Start pixel would be the left end of the paddle of the
                # Previous position minus the dX
                startPixel = xPrev - (player.WIDTH >> 1) - deltaX
                # The end pixel would be the left end of the paddle of the 
                # previous position
                endPixel   = xPrev - (player.WIDTH >> 1)

            self._spiSem.acquire()
            # TODO: Change this to draw to a page rather than 1 pixel at a time.
            for i in range(startPixel, endPixel):
                self._lcd.mSetPixel(i , p[C_Y_IDX], player.color)

            self._spiSem.release()
        
        # Update the previous location to current location.
        player.mUpdatePrevLoc(p)

    # This member function erases the left side of the paddle if moving right
    # and vice versa.
    def mErasePaddle(self, player: Player) -> None:
        p     = player.mGetLoc()
        pPrev = player.mGetPrevLoc()
        x     = p[C_X_IDX]
        xPrev = pPrev[C_X_IDX]
        if x != xPrev:
            if x > xPrev:
                deltaX     = x - xPrev
                # Moving Right
                # Start pixel for erasure on the left end should be the
                # previous x minus half the width
                startPixel = xPrev - (player.WIDTH >> 1)
                # The end pixel would be the left end of the paddle plus
                # the delta (x - xPrev) for Erasure
                endPixel   = xPrev - (player.WIDTH >> 1) + deltaX
                
            # xPrev > x
            else:
                deltaX     = xPrev - x
                # Moving Left
                # Start pixel would be the right end of the paddle of the
                # Previous position minus the dX for Erasure
                startPixel = xPrev + (player.WIDTH >> 1) - deltaX
                # The end pixel would be the left end of the paddle of the 
                # previous position
                endPixel   = xPrev + (player.WIDTH >> 1)

            # Update the previous location to current location.
            self._spiSem.acquire()
            # TODO: Change this to draw to a page rather than 1 pixel at a time.
            for i in range(startPixel, endPixel):
                self._lcd.mSetPixel(i , p[C_Y_IDX], C_COLOR_BLACK)

            self._spiSem.release()

    def mUpdatePlayerPos(self) -> None:
        p1 = self._q1.get()
        p2 = self._q2.get()
        mag1 = p1[C_X_IDX]
        mag2 = p2[C_X_IDX]
        # mag1 <= 511
        if mag1 <= self._joystick.mGetMidVal():
            moveDir1 = "left"
        
        # mag1 > 511
        else:
            moveDir1 = "right"

        # mag2 <= 511
        if mag2 <= self._joystick.mGetMidVal():
            moveDir2 = "left"
        
        # mag1 > 511
        else:
            moveDir2 = "right"
            
        mag1 = self._normalizeADC(mag1)
        self._player1.mMovePlayer(moveDir1, mag1)

        mag2 = self._normalizeADC(mag2)
        self._player2.mMovePlayer(moveDir2, mag2)

    #############################################################################################
    # END - Player Member Functions
    #############################################################################################    

    #############################################################################################
    # BEGIN - Ball Member Functions
    #############################################################################################
    # Draws the ball
    # TODO: Change the balls shape.
    def _drawBall(self, ballNum: int) -> None:
        if ballNum < len(self._balls):
            if self._balls[ballNum].mAlive:
                xy    = self._balls[ballNum].mGetPosition()
                color = self._balls[ballNum].mColor
                for i in range(self._balls[ballNum].mGetRadius()*2):
                    for j in range(self._balls[ballNum].mGetRadius()*2):
                        self._lcd.mSetPixel(xy[C_X_IDX] + i, xy[C_Y_IDX] + j, color)

    # For now this member function reverses the direction of the ball when
    # it hits the edge of the screen
    def _checkBallOutOfBounds(self, ballNum: int) -> None:
        if self._balls != []:
            if self._balls[ballNum].mAlive:
                xy       = self._balls[ballNum].mGetPosition()
                velocity = self._balls[ballNum].mGetVelocity()
                xBound = abs(velocity[C_X_IDX])
                yBound = abs(velocity[C_Y_IDX])
                # Check x coordinates
                # Add one so we know when the ball is at or below 0
                # Subtract two so we know when the ball is greater than or at 239
                if (xy[C_X_IDX] < self._lcd.mX_min + 1 + xBound) or (xy[C_X_IDX] > self._lcd.mX_max - 2 - xBound):
                    self.mChangeBallVelocity(ballNum, (velocity[C_X_IDX] * -1, velocity[C_Y_IDX]))
        
                if (xy[C_Y_IDX] < self._lcd.mY_min + 1 + yBound) or (xy[C_Y_IDX] > self._lcd.mY_max - 2 - yBound):
                    self.mKillBall(ballNum)

    # c code example of a call to this Algorithm:
    # Minkowski = MinkowskiAlgorithm(((BALL_SIZE +  (PADDLE_LEN / 3)) >> 1) + WIGGLE_ROOM,
    #                                ((BALL_SIZE + PADDLE_WID) >> 1) + WIGGLE_ROOM,
    #                                 Self.balls[Ball_Index].currentCenterX - Self.players[BOTTOM].currentCenter + PADDLE_LEN_D2 - (PADDLE_LEN / 6),
    #                                 Self.balls[Ball_Index].currentCenterY - BOTTOM_PLAYER_CENTER_Y);
    def _checkBallColliders(self, ballNum: int) -> None:
        for i in range(ballNum + 1, self.mNumBalls):
            minkowski = self._minkowski(
                w  = self._balls[ballNum].mGetRadius() * 2 + self._balls[i].mGetRadius() * 2,
                h  = self._balls[ballNum].mGetRadius() * 2 + self._balls[i].mGetRadius() * 2,
                dx = self._balls[ballNum]._pos.x - self._balls[i]._pos.x,
                dy = self._balls[ballNum]._pos.y - self._balls[i]._pos.y
            )
            if minkowski != C_NO_COLLISION:
                # I'm not sure if this should contain a break statement. On one hand,
                # when we find a collision, there's no need to keep checking, on the 
                # other hand, multiple collisions can occur at once.
                self._reverseBallOnCollision(ballNum, minkowski)
                self._reverseBallOnCollision(i,       minkowski)
            
        p1XY = self._player1.mGetLoc()
        p1X  = p1XY[C_X_IDX]
        p1Y  = p1XY[C_Y_IDX]
        p2XY = self._player2.mGetLoc()
        p2X  = p2XY[C_X_IDX]
        p2Y  = p2XY[C_Y_IDX]
        # Check P1 paddle
        minkowski = self._minkowski(
            w  = self._balls[ballNum].mGetRadius() * 2 + self._player1.WIDTH + C_WIGGLE_ROOM,
            h  = self._balls[ballNum].mGetRadius() * 2 + self._player1.HEIGHT,
            dx = self._balls[ballNum].mPos.x - p1X,
            dy = self._balls[ballNum].mPos.y - p1Y
        )

        if minkowski != C_NO_COLLISION:
            self._reverseBallOnCollision(ballNum, minkowski)

        # Check P2 paddle
        minkowski = self._minkowski(
            w  = self._balls[ballNum].mGetRadius() * 2 + self._player2.WIDTH + C_WIGGLE_ROOM,
            h  = self._balls[ballNum].mGetRadius() * 2 + self._player2.HEIGHT,
            dx = self._balls[ballNum].mPos.x - p2X,
            dy = self._balls[ballNum].mPos.y - p2Y
        )

        if minkowski != C_NO_COLLISION:
            self._reverseBallOnCollision(ballNum, minkowski)

    # Erases the ball
    def _eraseBall(self, ballNum: int) -> None:
        if ballNum < len(self._balls):
            if self._balls[ballNum].mAlive:
                xy    = self._balls[ballNum].mGetPosition()
                color = C_COLOR_BLACK
                for i in range(self._balls[ballNum].mGetRadius()*2):
                    for j in range(self._balls[ballNum].mGetRadius()*2):
                        self._lcd.mSetPixel(xy[C_X_IDX] + i, xy[C_Y_IDX] + j, color)

    # The minkowski algorithm is a fast way of detecting collisions and
    # and the side they occured on.
    # c code example of a call to this Algorithm:
    # Minkowski = MinkowskiAlgorithm(((BALL_SIZE +  (PADDLE_LEN / 3)) >> 1) + WIGGLE_ROOM,
    #                                ((BALL_SIZE + PADDLE_WID) >> 1) + WIGGLE_ROOM,
    #                                 Self.balls[Ball_Index].currentCenterX - Self.players[BOTTOM].currentCenter + PADDLE_LEN_D2 - (PADDLE_LEN / 6),
    #                                 Self.balls[Ball_Index].currentCenterY - BOTTOM_PLAYER_CENTER_Y);
    def _minkowski(self, w: int, h: int, dx: int, dy: int) -> int:
        if abs(dx) <= w and abs(dy) <= h:
            wy = w*dy
            hx = h*dx
            if  wy > hx:
                if wy > -hx:
                    # On the Top
                    return C_TOP_COLLISION

                else:
                    # On the Left
                    return C_LEFT_COLLISION
            
            else:
                if wy > -hx:
                    # On the right
                    return C_RIGHT_COLLISION

                else:
                    # On the bottom
                    return C_BOTTOM_COLLISION

        else:
            return C_NO_COLLISION

    # Moves the ball
    def _moveBall(self, ballNum: int) -> None:
        if self._balls != [] and ballNum < len(self._balls):
            self._balls[ballNum].mUpdatePosition(None)

        else:
            print("No balls exist")

    def _reverseBallOnCollision(self, ballNum: int, side: int) -> None:
        xy       = self._balls[ballNum].mGetPosition()
        velocity = self._balls[ballNum].mGetVelocity()
        if side == C_TOP_COLLISION or side == C_BOTTOM_COLLISION:
            self.mChangeBallVelocity(ballNum, (velocity[C_X_IDX], velocity[C_Y_IDX] * - 1))

        elif side == C_RIGHT_COLLISION or side == C_LEFT_COLLISION:
            self.mChangeBallVelocity(ballNum, (velocity[C_X_IDX] * -1, velocity[C_Y_IDX]))

    # Adjusts a ball's velocity
    def mChangeBallVelocity(self, ballNum: int, newVelocity: tuple) -> None:
        self._balls[ballNum].mChangeVelocity(newVelocity)

    # This method spawns balls that were killed
    def mCreateBall(self, location: tuple) -> None:
        maxBalls = len(self._balls)
        if self.mNumBalls < maxBalls:
            newBallMade = False
            while not newBallMade:
                ballNum = random.randint(0, len(self._balls) - 1)
                if not self._balls[ballNum].mAlive:
                    newVelY = 0
                    while newVelY == 0:
                        newVelY = random.randint(-4, 4)
                        time.sleep(0.01)

                    newVelX = random.randint(-4, 4)
                    self._balls[ballNum].mUpdatePosition(location)
                    self._balls[ballNum].mChangeVelocity((newVelX, newVelY))
                    self._balls[ballNum].mAlive = True
                    newBallMade = True
                
                else:
                    time.sleep(0.01)

            self.mNumBalls += 1

    # Creates N balls of random color (Initial call)
    def mCreateBalls(self, colors: list, N: int) -> None:
        for i in range(N):
            startX = 0
            startY = 0
            color = colors[random.randint(0, len(colors) - 1)]
            startX = random.randint(-4, 4)

            while startY == 0:
                startY = random.randint(-4, 4)

            ball = PongBall(color, (random.randint(20, 220), random.randint(20, 300)))
            self._balls.append(ball)
            self.mChangeBallVelocity(i, (startX, startY))

    # Deletes the selected ball object
    def mKillBall(self, ballNum: int) -> None:
        if self._balls != [] and ballNum < len(self._balls):
            self._eraseBall(ballNum)
            self.mNumBalls -= 1
            self._balls[ballNum].mAlive = False

    #############################################################################################
    # END - Ball Member Functions
    #############################################################################################

    #############################################################################################
    # BEGIN - Thread Definitions
    #############################################################################################
    def _mBallSpawnThread(self) -> None:
        while not self.mExitRequest:
            time.sleep(2.5)
            if self.mNumBalls < len(self._balls):
                self.mCreateBall(location = (120, 160))

    # TODO: This thread could be optimized to check out of bounds and colliders without holding
    # the semaphore, probably?
    def _mBallThreads(self, ballNum: int) -> None:
        while not self.mExitRequest:
            if self._balls[ballNum].mAlive:
                self._spiSem.acquire()
                self._eraseBall(ballNum)
                self._moveBall(ballNum)
                self._checkBallOutOfBounds(ballNum)
                self._checkBallColliders(ballNum)
                self._drawBall(ballNum)
                self._spiSem.release()
            
            time.sleep(0.0001)
        
    def _mJoyStickThread(self) -> None:
        while not self.mExitRequest:
            self._spiSem.acquire()
            x0, y0 = self._joystick.mReadJoy0()
            self._q1.put((x0, y0))
            x1, y1 = self._joystick.mReadJoy1()
            self._q2.put((x1, y1))
            self._spiSem.release()
            time.sleep(0.001)

    def _mPlayerThread(self) -> None:
        while not self.mExitRequest:
            self.mUpdatePlayerPos()
            self.mErasePaddle(self._player1)
            self.mDrawPaddle(self._player1)
            self.mErasePaddle(self._player2)
            self.mDrawPaddle(self._player2)
            time.sleep(0.0001)

    #############################################################################################
    # END - Thread Definitions
    #############################################################################################
    
    #############################################################################################
    # BEGIN - Game Run Member Functions
    #############################################################################################
    def mInit(self) -> None:
        self._lcd.mInitialize()
        self._lcd.mClearScreen()
        self._drawPaddleInitial(self._player1)
        self._drawPaddleInitial(self._player2)

    def mRunGame(self) -> None:
        spawnThread = Thread(target = self._mBallSpawnThread)
        joyThread = Thread(target = self._mJoyStickThread)
        playerThread = Thread(target = self._mPlayerThread)
        ballThreads = []
        for i in range(len(self._balls)):
            ballThread = Thread(target = self._mBallThreads, args = (i,))
            ballThreads.append(ballThread)
            
        for thread in ballThreads:
            thread.start()

        joyThread.start()
        playerThread.start()
        spawnThread.start()

        try:
            while True:
                time.sleep(0.2)

        except KeyboardInterrupt:
            self.mExitRequest = True
            joyThread.join()
            for thread in ballThreads:
                thread.join()

            spawnThread.join()
            playerThread.join()
            self._lcd.mClearScreen()
            self._lcd.mShutdown()
            self._joystick.mShutdown()
    
    #############################################################################################
    # BEGIN - Game Run Member Functions
    #############################################################################################

#############################################################################################
# END - Class Definitions  
#############################################################################################