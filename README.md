# rPIcam

A script to take timelapse photos **and** let you view the camera output as a video stream at the same time.

## Description

I wanted a program that could not only take regular still snapshots, but also let me view a live stream from the camera at the same time. I was also running this on a tiny Pi Zero and didn't want to tax its cpu with anything too demanding.

Note that this setup will only accept one live connection at a time - if you want to handle multiple connections, the way I do it is to run [RTSP Simple Server](https://github.com/aler9/rtsp-simple-server) on a proper sized computer, and when connections are made to that, it then launches a script to connect to the Pi and run a TCP-&gt;RTSP conversion with `ffmpeg -hide_banner -use_wallclock_as_timestamps 1 -stream_loop -1 -i tcp://PI_ADDRESS:PI_PORT -c copy -f rtsp -rtsp_transport tcp rtsp://RTSP_SIMPLE_SERVER:RTSP_SIMPLE_PORT/A_STREAM_NAME`.



## Getting Started

### Dependencies

* A Pi with a 32-bit install of Raspbian etc, as the 64-bit OS has a completely different camera backend that isn't supported by picamera. 


### Installing

* (Make Debian based OSes, like Rasbian, able to install virtual environments):
    * `sudo apt install python3-venv`
    
* Change directory to wherever you want to install it, eg:
    * `cd ~/.local/bin`

* Download this project and cd into it:
    * `git clone https://github.com/kifd/rpicam`
    * `cd rpicam`
    
* Install the virtual environment and activate it:
    * `python3 -m venv .venv`
    * `source .venv/bin/activate`
    
* Install the project, along with its pip dependencies:
    * `pip install --editable .`
    
    
### Configuration

* See the options available by running the program with:
    * `python camera.py --help`

* Play with the options:
    * eg `python camera.py --orientation vertical --interval 20 --base ~/test_pi_images` will save a 1848x2460 snapshot every 20 seconds into a subdir in your home directory, and stream a 1232x1640 video when connected to,
    * or `python camera.py --mode low --interval 240 --start 12 0 --stop 18 45` will save a 1920x1440 snapshot every 4 minutes between noon and 18:45, as well as being ready to stream a 640x480 video when connected to.
    * or `python camera.py --mode manual --width 640 --height 1240 --rotation 90 --no-snapshot` will only launch the listening server, ready to stream a 640x1240 picture rotated to compensate for fixing the camera sideways,

* Check that your settings were right by connecting to the raw TCP stream using a program like VLC or ffplay:
    * `ffplay tcp://YOUR_IP_ADDRESS:50007`

* Copy the camera@ service unit file into the systemd directory: 
    * `sudo cp camera@.service /etc/systemd/system`
    
* Point it at the install directory and set the params:
    * `sudo sed -i "s|INSTALLDIRECTORY|$PWD|g" /etc/systemd/system/camera@.service`
    * eg `export YOUR_SETTINGS="--mode low --interval 30"`
    * `sudo sed -i "s|PARAMETERS|$YOUR_SETTINGS|" /etc/systemd/system/camera@.service`
    
    
### Running
    
* Run once:
    * `sudo systemctl start camera@YOUR_USERNAME`
    
* Check the log:
    * `sudo journalctl -u camera@YOUR_USERNAME -f`

* Run on boot:
    * `sudo systemctl enable camera@YOUR_USERNAME`


    
### Alternatively
    
* You can run this as a plain --user script in ` ~/.config/systemd/user/` and [enable lingering](https://wiki.archlinux.org/title/Systemd/User#Automatic_start-up_of_systemd_user_instances) to have it start after boot without an open user session.

* You'll need to remove the `User=%i` line from the service if you do that.
    
* And you can then use `%i` to [pass the settings via a environment variable](https://askubuntu.com/a/1077788) instead of writing them into the service file, and end up with a call like `systemctl --user start camera@"--mode low --rotation 270"`, which may be preferable.

    

## Authors

* [Keith Drakard](https://drakard.com)


## Version History

* 0.1 - Initial Release



    
## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).



## Acknowledgments

* [picamera](https://github.com/waveform80/picamera) for the actual camera interface
* [click](https://click.palletsprojects.com/) for easy CLI building with Python
* StackOverflow for saving me having to remember how to code




