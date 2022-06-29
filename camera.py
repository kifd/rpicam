# pip modules
import click
import picamera

# python built-ins
import logging
from threading import Timer
import os, sys
import signal
import select
import socket
import errno
from time import sleep
from datetime import datetime, time


# globals
LOGGER = None
TIMER = None



# timer from https://stackoverflow.com/a/24072850
class RepeatingTimer(object):
    def __init__(self, interval, f, *args, **kwargs):
        self.interval = interval
        self.f = f
        self.args = args
        self.kwargs = kwargs
        self.timer = None

    def callback(self):
        self.f(*self.args, **self.kwargs)
        self.start()

    def cancel(self):
        self.timer.cancel()

    def start(self):
        self.timer = Timer(self.interval, self.callback)
        self.timer.daemon = True
        self.timer.start()



class MyCamera:
    
    def __init__(self, image_resolution, video_resolution, rotation, framerate):
        
        self.camera = None
        try:
            LOGGER.debug("Making camera object.")
            self.camera = picamera.PiCamera()
            self.camera.resolution = image_resolution
            self.camera.rotation = rotation
            self.camera.framerate = framerate
            # Start a preview and let the camera warm up for 2 seconds
            self.camera.start_preview()
            sleep(2)

        except picamera.exc.PiCameraValueError as ex:
            LOGGER.error(f"Invalid camera settings: {str(ex)}")
            sys.exit(1)
            
        except picamera.exc.PiCameraMMALError:
            LOGGER.error("Camera in use.")
            sys.exit(1)

        self.video_resolution = video_resolution
        


    ### image snapshot functions ####
    def snapshots(self, start_time, stop_time, interval, base_path):
        LOGGER.info(f"Snapshots set to {self.camera.resolution}.")
        
        if start_time == stop_time:
            self.continuous = True
            LOGGER.debug(f"Snapshots will always be taken.")
        else:
            self.continuous = False
            self.start_time = time(start_time[0],start_time[1])
            self.stop_time = time(stop_time[0],stop_time[1])
            LOGGER.debug(f"Snapshots will only be taken between {self.start_time} and {self.stop_time}.")
        
        self.base_path = os.path.expanduser(base_path)
        LOGGER.debug(f"Saving snapshots every {interval} seconds to {self.base_path}")
        
        # take our timelapse snapshots, regardless of network streaming
        global TIMER
        TIMER = RepeatingTimer(interval, self.take_snapshot)
        TIMER.start()


    def take_snapshot(self):
        
        def in_between(now, start, end):
            if start <= end:
                return start <= now < end
            else: # over midnight eg. 2330 to 0415
                return start <= now or now < end

        now = datetime.now()

        if self.continuous or in_between(now.time(), self.start_time, self.stop_time):
            save_path = f"{self.base_path}/{now.strftime('%Y-%m-%d')}"
            if not os.path.isdir(save_path):
                os.makedirs(save_path, exist_ok=True)
            filename = f"{save_path}/image_{now.strftime('%H-%M-%S-%f')}.jpg"

            #camera.zoom = (0.0, 0.0, 1.0, 1.0)
            # NOTE: if you care about missing video frames vs getting a poorer still snap, change use_video_port to True
            self.camera.capture(filename, use_video_port=False)
            LOGGER.debug(f"Snapshot taken: {filename}")




    def streaming(self, client_socket):
        
        # someone has connected to the server, so make a file object for the camera and start recording
        try:
            connection = client_socket.makefile("wb")
            #camera.zoom = (0.0, 0.1, 1.0, 0.75)
            self.camera.start_recording(connection, format="h264", level="4.2", resize=self.video_resolution)
            # inner loop of just streaming away to the client
            while True:
                try:
                    self.camera.wait_recording(1)
                
                # oops, the server has gone away again, so continue back to the outer loop to start all over again
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as ex:
                    if ex.errno in [errno.EPIPE, errno.ECONNABORTED, errno.ECONNRESET, errno.ESHUTDOWN]:
                        LOGGER.debug(f"Server dropped connection: {str(ex)}")
                        break
                    else:
                        raise Exception(f"Did not get expected errno: {ex.errno}")

                except Exception as ex:
                    LOGGER.error(f"Error (inner streaming loop): {str(ex)}")
                    sys.exit(1)
                    
        except Exception as ex:
            LOGGER.error(f"Error (outer streaming loop): {str(ex)}")
            sys.exit(1)


        # but this time, we use "finally" to tidy up first before continuing
        finally:

            try:
                self.camera.stop_recording()
                connection.close()

            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as ex:
                # comes when the camera tries to stop recording on a broken connection
                pass

            except Exception as ex:
                LOGGER.error(f"Error (tidying up): {str(ex)}")
                sys.exit(1)




    def wait_for_start_command(self, bind_address, listening_port):

        # handle ctrl+c events really
        def signal_handler(signal, frame):
            LOGGER.info("Terminating server.")
            server.close()
            if TIMER:
                TIMER.cancel()
            sys.exit(0)
            
        
        signal.signal(signal.SIGINT, signal_handler)
        
        LOGGER.info(f"Server starting, will stream at {self.video_resolution} @ {self.camera.framerate} fps.")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((bind_address, listening_port))
            
        except Exception as ex:
            LOGGER.error(f"Couldn't start server: {str(ex)}")
            sys.exit(1)

        # don't timeout while waiting for someone to connect and start streaming
        server.settimeout(None)
        
        server.listen()
        
        while True:
            conn, addr = server.accept()

            with conn:
                LOGGER.info(f"Connected by {addr}")

                try:
                    self.streaming(conn)

                except Exception as ex:
                    LOGGER.debug(f"Connection error: {str(ex)}")

                finally:
                    try:
                        conn.shutdown(2)
                        conn.close()
                    except Exception as ex:
                        if ex.errno in [errno.ENOTCONN]:
                            LOGGER.debug(f"Connection already closed.")
                        else:
                            LOGGER.debug(f"Error while closing connection: {str(ex)}")
                    else:
                        LOGGER.debug(f"Connection closed.")










# TODO: could add some click callback validation to check sane width*height / framerate / scaling vs pi camera hardware

@click.command("start", context_settings={"show_default": True, "max_content_width": 120})

@click.option("--debug", is_flag=True, default=True, help="Log debugging info.")

@click.option("--bind", default="0.0.0.0", help="IP to bind the listening server to.", metavar="<ip address>")
@click.option("--port", default=50007, help="Port to bind the listening server to.", metavar="<int>")

@click.option("--orientation", type=click.Choice(["landscape", "portrait"]), default="landscape", help="Portrait mode switches the width/height params.")
# NOTE: click can only cope with .Choice being a list of strings
@click.option("--rotation", type=click.Choice(["0", "90", "180", "270"]), default="0", help="Orientation adjustment if you had to fix the camera upside down.")

@click.option("--mode", type=click.Choice(["manual", "low", "full", "wide"]), default="full", help="Quick settings for video/image resolution etc.")

@click.option("--framerate", type=float, default=30, help="Video framerate.", metavar="<fps>")
@click.option("--width", default=1640, help="Video width.", metavar="<pixels>")
@click.option("--height", default=1232, help="Video height.", metavar="<pixels>")

@click.option("--snapshot/--no-snapshot", default=True, help="Take still image snapshots.")
@click.option("--scaling", type=click.FloatRange(0.25,3.0), default=1.0, help="Snapshot resolution scaling as a proportion of the video width/height.", metavar="<float>")
@click.option("--interval", type=click.IntRange(10,), default=120, help="Snapshot interval.", metavar="<seconds>")
@click.option("--base", default="~/rpicam/images", help="Base path to save snapshots to.", metavar="<path>")
@click.option("--start", type=(int, int), default=(0,0), help="Only start taking snapshots after this time.", metavar="<hour> <minute>")
@click.option("--stop", type=(int, int), default=(0,0), help="And stop taking snapshots after this time. Set to --start to always take snapshots every --interval seconds.", metavar="<hour> <minute>")


def start(debug, bind, port, orientation, rotation, mode, framerate, width, height, snapshot, scaling, interval, base, start, stop):
    """
This starts up a server that waits until connected to, and then will start the streaming the Pi camera's video output.

Meanwhile, regardless of anybody connecting, the Pi camera can be scheduled to save still image snapshots at the same time.
    """
    
    global LOGGER
    
    logging.basicConfig(
        level = 10 if debug else 20,
        format = "%(asctime)s - %(levelname)-8s - %(name)s - %(message)s",
    )
    LOGGER = logging.getLogger("rpicam")
        
    # override these params and set the size if we're using a mode setting
    if mode == "low":
        # 1920x1440 picture
        width = 640
        height = 480
        framerate = 60
        scaling = 3.0
        
    elif mode == "full":
        # 2460x1848 picture
        width = 1640
        height = 1232
        framerate = 30
        scaling = 1.5
        
    elif mode == "wide":
        width = 1920
        height = 1080
        framerate = 24
        scaling = 1.0
        
    else:
        # mode == manual, so I assume you know what you're doing and have read the hardware spec:
        # https://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes
        # https://en.wikipedia.org/wiki/H.264/MPEG-4_AVC#Levels
        pass
    
    
    # get the resolution sorted
    if orientation == "vertical":
        height, width = width, height
    
    video_resolution = (width, height)
    image_resolution = (int(width * scaling), int(height * scaling))
    
    if ((width/16)*(height/16) > 8192):
        LOGGER.error(f"Width * height is too big for the h264 level.")
        sys.exit(1)
    
    # make the general camera object
    cam = MyCamera(image_resolution, video_resolution, int(rotation), framerate)
    
    # start the timelapse snapshots
    if snapshot and interval:
        cam.snapshots(start, stop, interval, base)
    
    # and start the server that only activates the video camera when there's a connection
    cam.wait_for_start_command(bind, port)



    
    
    
    

if __name__ == '__main__':
    start()
