PI PRESENTS  - Version 1.5.2 (KMS)
============================

This repository contains an experimental version of Pi Presents which now uses the drm/kms video system. In this issue the VLC based videoplayer is replaced with a MPV based video player which integrates better into Pi Presents.

Apart from a working camera interface this issue has all the features of PI Presents Beep. Use it if you want the enhanced security of Bullseye and are happy to use Bleeding Edge software.


TO INSTALL PIPRESENTS-KMS
=============================

Read the 'Installing Pi Presents KMS' section below.



TO UPGRADE FROM EARLIER VERSIONS OF PIPRESENTS-BEEP
======================================================
To upgrade follow the instructions in the 'Updating Pi Presents' section below. Then follow any instructions in the Release Notes.


PI PRESENTS
===========

Pi Presents is a toolkit for producing interactive multimedia applications for museums, visitor centres, and more.

There are a number of Digital Signage solutions for the Raspberry Pi which are generally browser based, limited to slideshows, non-interactive, and driven from a central server enabling the content to be modified frequently.

Pi Presents is different, it is stand alone, multi-media, highly interactive, diverse in it set of control paradigms – slideshow, cursor controlled menu, radio button, and hyperlinked show, and able to interface with users or machines over several types of interface. It is aimed primarly at curated applications in museums, science centres, and visitor centres.

Being so flexible Pi Presents needs to be configured for your application. This is achieved using a simple to use graphical editor and needs no Python programming. There are numerous tutorial examples and a comprehensive manual.

There are two current versions of Pi Presents. ‘Gapless’ is the current stable version which is not being developed except for bug fixes. 'Beep' is a continuation of Gapless which is being developed to add new features.

For a detailed list of applications and features see here:

          https://pipresents.wordpress.com/features/



Licence
=======

See the licence.md file. Pi Presents is Careware to help support a small museum charity http://www.museumoftechnology.org.uk  Particularly if you are using Pi Presents in a profit making situation a donation would be appreciated.


Installing Pi Presents KMS
===============================

The full manual in English is here https://github.com/KenT2/pipresents-kms/blob/master/manual.pdf. It will be downloaded with Pi Presents.


Requirements
-------------

	* must use the latest version of Raspbian Bullseye with Desktop (not the Lite version)
	* must be run from the PIXEL desktop.
	* can be installed and run from any user that is created with RPI OS utilities
	* must have Python 3 installed (which RPi OS does)
	* should use a clean install of Raspberry Pi OS, particularly if you intend to use GPIO

Set the GPU Memory size to 256MB
---------------------------------
Using the Raspbian menu preferences>raspberry pi configuration>performance, increase the GPU Memory to 256. On a Pi Zero this may not be possible due to the small amount of RAM.


Ensure Raspbian is up to date.
-------------------------------
Pi Presents MUST have the latest version of RPi OS, get this by

         sudo apt update
         sudo apt full-upgrade
	 

Install required packages 
-----------------------------
         sudo apt install python3-pil.imagetk
         sudo apt install unclutter
         sudo apt install mplayer
         
         sudo pip3 install selenium
         sudo apt install chromium-chromedriver

         sudo apt install mpv
         sudo apt install python3-mpv
         python3 -m pip install DRV2605


Install optional packages
------------------------------
         sudo pip3 install evdev  (if you are using the input device I/O plugin)
         sudo apt install mpg123 (for .mp3 beeps)



Download Pi Presents KMS
----------------------------

From a terminal window open in your home directory type:

         wget https://github.com/KenT2/pipresents-kms/tarball/master -O - | tar xz     # -O is a capital Ohhh...

There should now be a directory 'KenT2-pipresents-kms-xxxx' in your /home/pi directory. Copy or rename the directory to pipresents

Run Pi Presents to check the installation is successful. From a terminal window opened in the home directory type:

         python3 /home/<username>/pipresents/pipresents.py

You will see a window with an error message which is because you have no profiles.Click OK to exit Pi Presents.


Download and try an Example Profile
-----------------------------------

Examples are in the github repository pipresents-kms-examples.

Open a terminal window in your home directory and type:

         wget https://github.com/KenT2/pipresents-kms-examples/tarball/master -O - | tar xz

There should now be a directory 'KenT2-pipresents-kms-examples-xxxx' in the /home/<username> directory. Open the directory and move the 'pp_home' directory and its contents to the home directory /home/<username>.

From the terminal window type:

         python3 /home/<username>/pipresents/pipresents.py -p pp_mediashow_1p5
		 
to see a repeating multimedia show

Exit this with CTRL-BREAK or closing the window, then:

          python3 /home/<username>/pipresents/pipresents.py -p pp_mediashow_1p5 -f -b
		  
to display full screen and to disable screen blanking


Now read the manual to try other examples.


Updating Pi Presents from Pi Presents Beep or Pi Presents Gapless
======================================================================================

Backup the directories /home/pi/pipresents and /home/pi/pp_home, you will need to refer to them.

Pi Presents KMS requires Raspberry Pi OS Bullseye or later so first install the operating system on a new SD card and then follow the instructions above for a new install of Pi Presents KMS.

You can also install the example profiles for KMS from the pipresents-kms-examples repository

Copy any files you have made or changed from old to new /pipresents/pp_io_config directory.

Copy any files you have made or changed from old to new /pipresents/pp_io_plugins directory.

Copy any files you have made or changed from old to new /pipresents/pp_track_plugins directory.

Do not copy across /pipresents/pp_config/pp_editor.cfg

If you have modified it, make the edits to  /pipresents/pp_config/pp_web.cfg file. If you are using a username other than pi then edit the appropriate fields.

Copy any other files you have changed in /pipresents/pp_config/ - pp_email.cfg, pp_oscmonitor.cfg, pp_oscremote.cfg

This version requires the legacy camera library if using the camera. Run sudo raspi-config and select legacy camera.
      
This version does not require 256MB GPU Mem. Use the out of the box 76MB.


For upgrade from Beep:

      * If you have modified it, make the edits to the new format /pipresents/pp_config/pp_display.cfg file.

      * If you have modified it, make the edits to the new format /pipresents/pp_config/pp_audio.cfg file.For KMS the pulseaudio sink names are different for different models of Pi but I believe are the same for individual boards. If I am incorrect then please contact me and edit the file as described in the file.
      

For upgrade from Gapless:

      * There is a new /pipresents/pp_config/pp_display.cfg file. This replaces use of the --screensize command line option and allows change to the size of the development window.

      * There is a new /pipresents/pp_config/pp_audio.cfg file. This requires editing to allow use USB or Bluetooth devices. For KMS the pulseaudio sink names are different for different models of Pi but I believe are the same for individual boards. If I am incorrect then please contact me and edit the file as described in the file. 





Updating Profiles for use in PI Presents KMS
--------------------------------------------

Copy the pp_home directory from your backup to the home directory of your SD card.

When you open a profile using the editor it will be updated from Beep or Gapless versions. You can use the update>update all menu option of the editor to update all profiles in a single directory at once.

You will now need to make the following manual modifications:

      * Video tracks using omxplayer are now removed and will be deleted from the profile by the update. Any reference to them wil be retained.  You will need to create new equivalent tracks using the MPV Video track.

      * VLC Video tracks using VLC Player are now removed and will be deleted from the profile by the update. Any reference to them wil be retained.  You will need to create new equivalent tracks using the MPV Video track. 

      * Web tracks that used the UZBL browser are now removed and will be deleted from the profile by the update. Any reference to them wil be retained. You will need to create new equivalent tracks using the Chrome Web track.

      * For Audio tracks the Audio Player volume range is now 0>100 instead of -60>0
      



Bug Reports and Feature Requests
================================
I am keen to develop Pi Presents further and would welcome bug reports and ideas for additional features and uses.

Please use the Issues tab on Github https://github.com/KenT2/pipresents-kms/issues.

For more information on how Pi Presents is being used, Hints and Tips on how to use it and all the latest news hop over to the Pi Presents website https://pipresents.wordpress.com/

