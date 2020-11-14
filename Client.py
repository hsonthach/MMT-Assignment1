from RtpPacket import RtpPacket
import os
import traceback
import sys
import threading
import socket
from PIL import ImageTk
import PIL.Image


from tkinter import *

import tkinter.messagebox

tkMessageBox = tkinter.messagebox


CACHE_FILE_NAME = "cache-"

CACHE_FILE_EXT = ".jpg"


class Client:

    INIT = 0

    READY = 1

    PLAYING = 2

    state = INIT

    SETUP = 0

    PLAY = 1

    PAUSE = 2

    TEARDOWN = 3

    # Initiation..

    def __init__(self, master, serveraddr, serverport, rtpport, filename):

        self.master = master

        # Set up func that trigger whenever the window closed
        self.master.protocol("WM_DELETE_WINDOW", self.handler)

        # Setup button and event handler for each of them
        self.createWidgets()

        self.serverAddr = serveraddr

        self.serverPort = int(serverport)

        self.rtpPort = int(rtpport)

        self.fileName = filename

        self.rtspSeq = 0

        self.sessionId = 0

        self.requestSent = -1

        self.teardownAcked = 0

        self.connectToServer()

        self.frameNbr = 0

    def createWidgets(self):
        """Build GUI."""

        # Create Setup button

        self.setup = Button(self.master, width=20, padx=3, pady=3)

        self.setup["text"] = "Setup"

        self.setup["command"] = self.setupMovie

        self.setup.grid(row=1, column=0, padx=2, pady=2)

        # Create Play button

        self.start = Button(self.master, width=20, padx=3, pady=3)

        self.start["text"] = "Play"

        self.start["command"] = self.playMovie

        self.start.grid(row=1, column=1, padx=2, pady=2)

        # Create Pause button

        self.pause = Button(self.master, width=20, padx=3, pady=3)

        self.pause["text"] = "Pause"

        self.pause["command"] = self.pauseMovie

        self.pause.grid(row=1, column=2, padx=2, pady=2)

        # Create Teardown button

        self.teardown = Button(self.master, width=20, padx=3, pady=3)

        self.teardown["text"] = "Teardown"

        self.teardown["command"] = self.exitClient

        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Create a label to display the movie

        self.label = Label(self.master, height=19)

        self.label.grid(row=0, column=0, columnspan=4,
                        sticky=W+E+N+S, padx=5, pady=5)

    def setupMovie(self):
        """Setup button handler."""

        if self.state == self.INIT:

            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        """Teardown button handler."""

        self.sendRtspRequest(self.TEARDOWN)

        self.master.destroy()  # Close the gui window

        # Delete the cache image from video
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

    def pauseMovie(self):
        """Pause button handler."""

        if self.state == self.PLAYING:

            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        """Play button handler."""

        if self.state == self.READY:

            # Create a new thread to listen for RTP packets

            threading.Thread(target=self.listenRtp).start()

            self.playEvent = threading.Event()

            self.playEvent.clear()

            self.sendRtspRequest(self.PLAY)

    def listenRtp(self):
        """Listen for RTP packets."""

        while True:

            try:

                data = self.rtpSocket.recv(20480)
                if data:

                    rtpPacket = RtpPacket()

                    rtpPacket.decode(data)

                    currFrameNbr = rtpPacket.seqNum()

                    print("Current Frame Num: " + str(currFrameNbr))

                    if currFrameNbr > self.frameNbr:  # Discard the late packet

                        self.frameNbr = currFrameNbr

                        self.updateMovie(self.writeFrame(
                            rtpPacket.getPayload()))

            except Exception as e:
                print("RTP ", e)
                # Stop listening upon requesting PAUSE or TEARDOWN

                if self.playEvent.isSet():

                    break

                # Upon receiving ACK for TEARDOWN request,

                # close the RTP socket

                if self.teardownAcked == 1:

                    self.rtpSocket.shutdown(socket.SHUT_RDWR)

                    self.rtpSocket.close()

                    break

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""

        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT

        file = open(cachename, "wb")

        file.write(data)

        file.close()

        return cachename
    '''
    * Input: cache image file name
    * Precondition:
    * Output:
    * Postcondition:
    * Description: update label.image
    * Example: Input:cache-532373 -> label.image = PIL.Image(Input:cache-532373)
    * Source:
    * Exception:
    '''

    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(PIL.Image.open(imageFile))

        self.label.configure(image=photo, height=288)

        self.label.image = photo
    '''
    * Input:
    * Precondition:
    * Output:
    * Postcondition:
    * Description: opens the RTSP socket to the server
    * Example:
    * Source:
    * Exception:
    '''

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""

        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Server also receive client ip adr & port adr
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
            self.setupMovie()

        except:

            tkMessageBox.showwarning(
                'Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""

        # Setup request

        if requestCode == self.SETUP and self.state == self.INIT:

            threading.Thread(target=self.recvRtspReply).start()

            # Update RTSP sequence number.

            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            # Insert the Transport header
            """
            Ex: 
            SETUP movie.Mjpeg RTSP/1.0
            CSeq: 1
            Transport: RTP/UDP; client_port= 20001
            """
            request = 'SETUP ' + self.fileName + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + \
                '\nTransport: RTP/UDP; client_port= ' + str(self.rtpPort)

            # Keep track of the sent request.

            self.requestSent = self.SETUP

        # Play request

        elif requestCode == self.PLAY and self.state == self.READY:

            self.rtspSeq += 1
            """ 
            Ex:
            PLAY movie.Mjpeg RTSP/1.0
            CSeq: 2
            Session: 957291
            """
            request = 'PLAY ' + self.fileName + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

            self.requestSent = self.PLAY

        # Pause request

        elif requestCode == self.PAUSE and self.state == self.PLAYING:

            self.rtspSeq += 1

            request = 'PAUSE ' + self.fileName + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

            self.requestSent = self.PAUSE

        # Teardown request

        elif requestCode == self.TEARDOWN and not self.state == self.INIT:

            self.rtspSeq += 1

            request = 'TEARDOWN ' + self.fileName + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

            self.requestSent = self.TEARDOWN

        else:

            return

        # Send the RTSP request using rtspSocket.
        self.rtspSocket.send(request.encode())

        print('\nData sent:\n' + request)
    '''
    * Input:
    * Precondition:
    * Output:
    * Postcondition:
    * Description: Read the server’s response and parse
    * Example:
    * Source:
    * Exception:
    '''

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""

        while True:
            # Get reply message from server
            reply = self.rtspSocket.recv(1024)

            if reply:

                self.parseRtspReply(reply)

            # Close the RTSP socket upon requesting Teardown

            if self.requestSent == self.TEARDOWN:

                self.rtspSocket.shutdown(socket.SHUT_RDWR)

                self.rtspSocket.close()

                break

    '''
    * Input:
    * Precondition:
    * Output:
    * Postcondition:
    * Description:Parse RTSP reply and handle RTSP state changes
    * Example:
    * Source:
    * Exception:
    '''

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.decode().split('\n')

        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's

        if seqNum == self.rtspSeq:

            session = int(lines[2].split(' ')[1])

            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session

            # Process only if the session ID is the same

            if self.sessionId == session:

                if int(lines[0].split(' ')[1]) == 200:

                    if self.requestSent == self.SETUP:

                        # Update RTSP state.

                        self.state = self.READY

                        # Open RTP port.

                        self.openRtpPort()

                    elif self.requestSent == self.PLAY:

                        self.state = self.PLAYING

                    elif self.requestSent == self.PAUSE:

                        self.state = self.READY

                        # The play thread exits. A new thread is created on resume.

                        self.playEvent.set()

                    elif self.requestSent == self.TEARDOWN:

                        self.state = self.INIT

                        # Flag the teardownAcked to close the socket.

                        self.teardownAcked = 1
    '''
    * Input:
    * Precondition:
    * Output:
    * Postcondition:
    * Description: Create a datagram socket for receiving RTP data and set the timeout on the socket to 0.5 seconds
    * Example:
    * Source:
    * Exception:
    '''

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""

        # Create a new datagram socket to receive RTP packets from the server

        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec

        self.rtpSocket.settimeout(0.5)

        try:

            # Bind the socket to the address using the RTP port given by the client user

            self.rtpSocket.bind(("", self.rtpPort))

        except:

            tkMessageBox.showwarning(
                'Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""

        self.pauseMovie()

        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):

            self.exitClient()

        else:  # When the user presses cancel, resume playing.

            self.playMovie()
