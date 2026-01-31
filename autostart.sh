# include the path to this file in the file autostart to run PP at boot.
# See the manual for how and where to create the file autostart. 
# Ensure thia file, autostart.sh is executable

/usr/bin/python3 /home/pi/pipresents/pipresents.py -o /home/pi -p pp_mediashow_1p5

# to help the debug of PP when using autostart use this line instead.

#/usr/bin/python3 /home/pi/pipresents/pipresents.py -p pp_mediashow_1p5 -d -o /home/pi  >> /home/pi/pipresents/pp_logs/pp_autostart.txt 2>&1


