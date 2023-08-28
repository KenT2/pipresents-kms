#! /usr/bin/env python3

import os
import sys
import subprocess
from tkinter import Tk, Canvas,Toplevel,NW,Scrollbar,RIGHT,Y,LEFT,BOTH,TOP
import copy
import configparser


class DisplayManager(object):
    
    # DSI1    0 - MainLCD - official DSI touchscreen
    #         1 -         - Auxilliary LCD ?whats this
    # HDMI0   2 - HDMI0 -   HDMI-1 port 0
    # A/V     3 - Composite  - TV
    #         4 -         - Force LCD
    #         5 -         - Force TV
    #         6 -         - Force non-default display
    # HDMI1   7 - HDMI1   - HDMI-2 Port 1
    #         8 - 
    
    debug = True
    
    display_map = {'DSI0':0,'HDMI0':2,'HDMI':2,'A/V':3,'HDMI1':7 }    # lookup display Id by display name e.g. HDMI1>7
    display_reverse_map = {0:'DSI0',2:'HDMI0',3:'A/V',7:'HDMI1' }  # lookup display name by Id  e.g. 2>HDMI0
    randr_map={'DSI-1':0,'HDMI-1':2,'Composite-1':3,'HDMI-2':7}
    vlc_display_name_map =  {'DSI0':'DSI-1','HDMI':'HDMI-1','HDMI0':'HDMI-1','A/V':'A/V','HDMI1':'HDMI-2' }
    
    # Class Variables
    
    # obtained from randr for model 4
    numdisplays=0
    displays=[]         # list of dispay Id's  e.g.[2,7]


    # randr parameters by randr name (HDMI-1 etc)
    randr_num_displays = 0 # should be the same as tvservice
    randr_displays = []     
    randr_width = {}
    rand_height = {}
    randr_x = {}
    randr_y = {}

    # randr names and dimensions of the real displays obtained from randr by display_id (2,7)
    real_display_names={}
    real_display_width={}    
    real_display_height={}
    real_display_x = {}
    real_display_y = {}
    display_overlaps = False
    
    # dimensions modified by fake in pp_display.cfg, used to create borders
    fake_display_width={}    
    fake_display_height={}
    
    # dimensions of the window in non-fullscreen mode (as modified by non-full window width/height in pp_displau.cfg)
    window_width=dict()
    window_height=dict()
    
    # canvas parameters by Display Id
    canvas_obj=dict()     # Tkinter widget
    canvas_width=dict()
    canvas_height=dict()
    

    #called by all classes using DisplayManager
    def __init__(self):
        return

# ***********************************************
# Methods used by the rest of Pi Presents
# ************************************************

    #def model_of_pi(self):
    #    return DisplayManager.pi_model

    def id_of_display(self,display_name):
        if display_name not in DisplayManager.display_map:
            return 'error','Display Name not known: '+ display_name,-1
        display_id = DisplayManager.display_map[display_name]
        if display_id not in DisplayManager.displays:
            return 'error','Display not connected: '+ display_name,-1
        return 'normal','',display_id
        
    def id_of_canvas(self,display_name):
        if display_name not in DisplayManager.display_map:
            return 'error','Display Name not known '+ display_name,-1,-1
        display_id = DisplayManager.display_map[display_name]
        if display_id not in DisplayManager.canvas_obj:
            return 'error','Display not connected (no canvas): '+ display_name,-1,-1
        return 'normal','',display_id,DisplayManager.canvas_obj[display_id]
        
    def name_of_display(self,display_id):
        return DisplayManager.display_reverse_map[display_id]

    def has_canvas(self,display_id):
        if display_id not in DisplayManager.canvas_obj:
            return False
        else:
            return True

    def canvas_widget(self,display_id):
        return DisplayManager.canvas_obj[display_id]

    def canvas_dimensions(self,display_id):
        return DisplayManager.canvas_width[display_id],DisplayManager.canvas_height[display_id]
        
    def display_dimensions(self,display_id):
        return DisplayManager.fake_display_width[display_id],DisplayManager.fake_display_height[display_id]

    def real_display_dimensions(self,display_id):
        return DisplayManager.real_display_width[display_id],DisplayManager.real_display_height[display_id]

    def real_display_position(self,display_id):
        return DisplayManager.real_display_x[display_id],DisplayManager.real_display_y[display_id]

    def real_display_orientation(self,display_id):
        pass
        
    def does_display_overlap(self):
        return DisplayManager.display_overlaps


# ***********************************************
# Initialize displays at start
# ************************************************

    # called by pipresents.py  only when PP starts
    def init(self,options,close_callback,pp_dir,debug):
        DisplayManager.debug=debug
        self.backlight=None
        # read display.cfg
        self.read_config(pp_dir)

        # find connected displays from randr and get their parameters            
        status,message=self.find_randr_displays()
        if status=='error':
            return status,message,None
            
        # process randr displays to bbe referenced by display_id
        status,message=self.process_displays_model4()
        if status=='error':
            return status,message,None 

        # compute display_width, display_height accounting for --screensize option
        status,message=self.do_fake_display()
        if status=='error':
            return status,message,None            
            
        # Have now got all the required information

        # setup backlight for touchscreen if connected
        status,message=self.init_backlight()
        if status=='error':
            return status,message,None
                    
        # set up Tkinter windows
        status,message,root=self.init_tk(options,close_callback)
        if status=='error':
            return status,message,None

        return status,message,root

    def terminate(self):
        self.terminate_backlight()



# ***********************************************
# Get information about displays
# ************************************************
# Pi3
# composite off in raspi-config
#       - xrandr shows hdmi-1 connected with geometry 

# composite on in raspi-config, composite active in screen config
#       - xrandr shows
#                HDMI-1 connected (normal left inverted right x axis y axis)
#                Composite-1 unknown connection primary 720x480+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
#                A/V output works, no HDMI output

# composite on in raspi-config, composite not active, HDMI active
#       - xrandr shows:
#                HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis
#                Composite-1 unknown connection (normal left inverted right x axis y axis)
#                HDMI display works, no A/V output
#                ERROR reported by PP         

#Pi4
# composite off in raspi-config
# HDMI-1 connected primary 1920x1080+800+0 (normal left inverted right x axis y axis) 509mm x 286mm
# HDMI-2 connected 1024x768+2720+0 (normal left inverted right x axis y axis) 310mm x 230mm
# DSI-1 connected 800x480+0+0 inverted (normal left inverted right x axis y axis) 0mm x 0mm

# composite on in raspi-config, composite active in screen config



    def find_randr_displays(self):
        # clear dicts to be used
        DisplayManager.randr_num_displays = 0
        DisplayManager.randr_displays = []   
        DisplayManager.randr_width = dict() 
        DisplayManager.randr_height = dict() 
        DisplayManager.randr_x = dict() 
        DisplayManager.randr_y = dict() 
        
        #execute xrandr command
        output = subprocess.check_output(["xrandr"]).decode("utf-8")
        if 'Composite-1' in output:
            return 'error','A/V is not supported by Pi Presents\nUse a HDMI to PAL/NTSC convertor'
        else:
            outlines=output.splitlines()
            for l in outlines:
                # print('hdmi',l)
                if ' connected ' in l:
                    fields = l.split()
                    name= fields[0]
                    DisplayManager.randr_displays.append(name)
                    DisplayManager.randr_num_displays +=1
                    if 'primary' in l:
                        whxy_field=3
                    else:
                        whxy_field=2
                    self.randr_common(name,fields,whxy_field)
            self.print_randr()
            return 'normal',''

        
    def randr_common(self,name,fields,whxy_field):
        whxy=fields[whxy_field]
        wh=whxy.split('+')[0]
        w=wh.split('x')[0]
        h=wh.split('x')[1]
        xy=whxy.split('+')
        x=xy[1]
        y=xy[2]
        DisplayManager.randr_width[name]=int(w)
        DisplayManager.randr_height[name]=int(h)
        DisplayManager.randr_x[name]=int(x)
        DisplayManager.randr_y[name]=int(y)
        return
        
        
        
    def process_displays_model4(self):

        """
        This is more complicated than necessary now that KMS does not use display_id 0,2,7, etc. however display_id is retained 
        we need to have all parameters referenced to the display_id as display_id is used by the rest of Pi Presents
        With KMS:
                x position and y position are provided by xrandr
                display width and height are swappped for rotated displays by xrandr
                touch coordinates are corrected for display offset and rotation
        but
        The xrandr command does not reference display by display_id but by DSI-1 HDMI-1 HDMI-2

        """

        DisplayManager.displays=[]
        DisplayManager.num_displays=0
        DisplayManager.real_display_width=dict()
        DisplayManager.real_display_height=dict()
        DisplayManager.real_display_x=dict()
        DisplayManager.real_display_y=dict()

        
        # translate rand r display names into display_id's
        for index,display in enumerate(DisplayManager.randr_displays):
            DisplayManager.displays.append(DisplayManager.randr_map[DisplayManager.randr_displays[index]])
            DisplayManager.real_display_width[DisplayManager.displays[index]]= DisplayManager.randr_width[DisplayManager.randr_displays[index]]
            DisplayManager.real_display_height[DisplayManager.displays[index]]  = DisplayManager.randr_height[DisplayManager.randr_displays[index]]  
            DisplayManager.real_display_x[DisplayManager.displays[index]]= DisplayManager.randr_x[DisplayManager.randr_displays[index]]
            DisplayManager.real_display_y[DisplayManager.displays[index]]  = DisplayManager.randr_y[DisplayManager.randr_displays[index]]
        DisplayManager.num_displays= len(DisplayManager.displays)       
        DisplayManager.display_overlaps= False
        if DisplayManager.num_displays==3:
            self.test_overlap(0,2)
            self.test_overlap(1,2)
            self.test_overlap(0,1)
        if DisplayManager.num_displays==2:
            self.test_overlap(0,1)            
        self.print_real() 
        return 'normal',''
        
        
    def test_overlap(self,i1,i2):
        overlap=False
        id0=DisplayManager.displays[i1]
        id1=DisplayManager.displays[i2]
        if  DisplayManager.real_display_x[id0] == DisplayManager.real_display_x[id1]\
            and DisplayManager.real_display_y[id0] == DisplayManager.real_display_y[id1]:
            overlap=True    
            DisplayManager.display_overlaps=True
        return
            
    
 
    def do_fake_display(self):
        DisplayManager.fake_display_width=dict()
        DisplayManager.fake_display_height=dict()
        
        for did in DisplayManager.displays:
            reason,message,fake_width,fake_height=self.get_fake_dimensions(DisplayManager.display_reverse_map[did])
            if reason =='error':
                return 'error',message
            if reason == 'null':
                DisplayManager.fake_display_width[did]=DisplayManager.real_display_width[did]
                DisplayManager.fake_display_height[did]=DisplayManager.real_display_height[did]  
            else:
                DisplayManager.fake_display_width[did] = fake_width
                DisplayManager.fake_display_height[did] = fake_height

        self.print_fake()
        return 'normal',''
        
        


# ***********************************************
# Set up Tkinter windows and canvases.
# ************************************************

    def init_tk(self,options,close_callback):
        
        # clear class variables
        DisplayManager.window_width=dict()
        DisplayManager.window_height=dict()
        DisplayManager.canvas_obj=dict()
        DisplayManager.canvas_width=dict()
        DisplayManager.canvas_height=dict()
        
        # get the display to be called Tk
        if len(DisplayManager.displays)==0:
            return 'error','No displays connected',None

        # primary is the display_id that is to be Tk root and Tk() main window
        # primary display needs to be 2 if DSI0 is used otherwise Tkinter does funny things
        # set to  2 if HDMI0 and HDMI1 as HDMI0 is the main dislay
        # develop_id is windowed if not fullscreen command line option


        if len(DisplayManager.displays)==1:
            # single display either DSI0 or HDMI0
            primary_id=DisplayManager.displays[0]
            self.develop_id = primary_id

        if 0 in DisplayManager.displays and 2 in DisplayManager.displays:
            # DSI0 and HDMI0. Make HDMI0 the windowed display as best for developing.
            primary_id=2     # tk falls over if 2 is not the primary display.
            self.develop_id=2 # 2 is HDMI so best for developing
            
        if 2 in DisplayManager.displays and 7 in DisplayManager.displays:
            # HDMI0 and HDMI1
            primary_id=2
            self.develop_id=2
            
        if 0 in DisplayManager.displays and 7 in DisplayManager.displays:
            # DSI0 and HDMI1. Make HDMI1 the windowed display as best for developing.
            primary_id=7     # tk falls over if 7 is not the primary display.
            self.develop_id=7 # 7 is HDMI so best for developing
            
        if  len(DisplayManager.displays)==3:
            primary_id=2
            self.develop_id=2            
        
        # setup Tk windows/canvases for all connected displays
        for this_id in DisplayManager.displays:                            
            # print (this_id, self.develop_id)            
            if this_id == primary_id:
                tk_window=Tk()
                root=tk_window
            else:
                tk_window=Toplevel()
            
            tk_window.title('Pi Presents - ' + DisplayManager.display_reverse_map[this_id])
            tk_window.iconname('Pi Presents')
            tk_window.config(bg='black')

    
            # set window dimensions and decorations
            # make develop_id screen windowed
            if options['fullscreen'] is False and this_id == self.develop_id:
                status,message,x,y,w_scale,h_scale=self.get_develop_window(DisplayManager.display_reverse_map[this_id])
                if status != 'normal':
                    return 'error',message,None
                window_width=DisplayManager.real_display_width[this_id]*w_scale
                window_height= DisplayManager.real_display_height[this_id]*h_scale
                window_x=DisplayManager.real_display_x[self.develop_id] + x
                window_y= DisplayManager.real_display_y[self.develop_id] + y
                # print ('Window Position not FS', this_id,window_x,window_y,window_width,window_height)
                tk_window.geometry("%dx%d%+d%+d" % (window_width,window_height,window_x,window_y))
                

            else:
                # fullscreen for all displays that are not develop_id
                window_width=DisplayManager.fake_display_width[this_id]
                # krt changed
                window_height=DisplayManager.fake_display_height[this_id]
                window_x=DisplayManager.real_display_x[this_id]
                window_y=DisplayManager.real_display_y[this_id]
                #KRT
                tk_window.attributes('-fullscreen', True)
                if options['nounclutter'] is False:
                    # print ('set unclutter')
                    os.system('unclutter > /dev/null 2>&1 &')
                
                # print ('Window Position FS', this_id, window_x,window_y,window_width,window_height)
                tk_window.geometry("%dx%d%+d%+d"  % (window_width,window_height,window_x,window_y))
                tk_window.attributes('-zoomed','1')

            DisplayManager.window_width[this_id]=window_width
            DisplayManager.window_height[this_id]=window_height    

            # define response to main window closing.
            tk_window.protocol ("WM_DELETE_WINDOW", close_callback)
            

            # setup a canvas onto which will be drawn the images or text
            # canvas covers the whole screen whatever the size of the window
            canvas_height=DisplayManager.fake_display_height[this_id]
            canvas_width=DisplayManager.fake_display_width[this_id]
            


            if options['fullscreen'] is False:
                ##scrollbar = Scrollbar(tk_window)
                #scrollbar.pack(side=RIGHT, fill=Y)
                tk_canvas = Canvas(tk_window, bg='black')
                #tk_canvas = Canvas(tk_window, bg='blue',yscrollcommand=scrollbar.set)
                tk_canvas.config(height=canvas_height,
                                   width=canvas_width,
                                   highlightcolor='yellow',
                                   highlightthickness=1)
                #tk_canvas.pack(anchor=NW,fill=Y)
                #scrollbar.config(command=tk_canvas.yview)
                tk_canvas.place(x=0,y=0)
            else:
                tk_canvas = Canvas(tk_window, bg='black')
                tk_canvas.config(height=canvas_height,
                                 width=canvas_width,
                                 highlightthickness=0,
                                highlightcolor='yellow')
                tk_canvas.place(x=0,y=0)

            # tk_canvas.config(bg='black')            
            DisplayManager.canvas_obj[this_id]=tk_canvas
            DisplayManager.canvas_width[this_id]=canvas_width
            DisplayManager.canvas_height[this_id]=canvas_height

            tk_window.focus_set()
            tk_canvas.focus_set()
        
        self.print_tk()
        return 'normal','',root




    def print_info(self):
        if DisplayManager.debug is True:
            print ('\nMaps:',DisplayManager.display_map,'\n',DisplayManager.display_reverse_map)
            #print ('Pi Model:',self.model)


    def print_randr(self):
        if DisplayManager.debug is True:
            print ('\nNumber of Displays - randr:',DisplayManager.randr_num_displays)
            print ('Displays Connected- randr:',DisplayManager.randr_displays)
            print ('Display Dimensions - randr:',DisplayManager.randr_width,DisplayManager.randr_height)
            print ('Display Position - randr:',DisplayManager.randr_x,DisplayManager.randr_y)

    def print_real(self):
        if DisplayManager.debug is True:
            print ('\nNumber of Displays - real:',DisplayManager.num_displays)
            print ('Displays Connected- real:',DisplayManager.displays)
            print ('Display Dimensions - real:',DisplayManager.real_display_width,DisplayManager.real_display_height)
            print ('Display Position - real:',DisplayManager.real_display_x,DisplayManager.real_display_y)
            print ('Display Overlap: ',DisplayManager.display_overlaps)

    def print_fake(self):
        if DisplayManager.debug is True:
            print ('\nDisplay Dimensions - fake:',DisplayManager.fake_display_width,DisplayManager.fake_display_height)

    def print_tk(self):
        if DisplayManager.debug is True:
            print ('\nDevelopment Display:',self.develop_id)
            print ('Window Dimensions - non-full:',DisplayManager.window_width,DisplayManager.window_height)
            print ('Canvas Widget:',DisplayManager.canvas_obj)
            print ('Canvas Dimensions:',DisplayManager.canvas_width,DisplayManager.canvas_height,'\n\n')






# ***********************************************
# Read and process configuration data
# ************************************************

    # read display.cfg    
    def read_config(self,pp_dir):
        filename=pp_dir+os.sep+'pp_config'+os.sep+'pp_display.cfg'
        if os.path.exists(filename):
            DisplayManager.config = configparser.ConfigParser(inline_comment_prefixes = (';',))
            DisplayManager.config.read(filename)
            return 'normal','display.cfg read'
        else:
            return 'error',"Failed to find display.cfg at "+ filename

    def displays_in_config(self):
        return DisplayManager.config.sections()
        
    def display_in_config(self,section):
        return DisplayManager.config.has_section(section)
        
    def get_item_in_config(self,section,item):
        return DisplayManager.config.get(section,item)

    def item_in_config(self,section,item):
        return DisplayManager.config.has_option(section,item)


    def get_fake_dimensions(self,dname):
        if not self.display_in_config(dname):
            return 'error','display not in display.cfg '+ dname,0,0
        if not self.item_in_config(dname,'fake-dimensions'):
            return 'null','',0,0
        size_text=self.get_item_in_config(dname,'fake-dimensions')
        if size_text=='':
            return 'null','',0,0
        fields=size_text.split('*')
        if len(fields)!=2:
            return 'error','do not understand fake-dimensions in display.cfg for '+dname,0,0
        elif fields[0].isdigit()  is False or fields[1].isdigit()  is False:
            return 'error','fake dimensions are not positive integers in display.cfg for '+dname,0,0
        else:
            return 'normal','',int(fields[0]),int(fields[1])

    def get_develop_window(self,dname):
        if not self.display_in_config(dname):
            return 'error','display not in display.cfg '+ dname,0,0
        if not self.item_in_config(dname,'develop-window'):
            return 'normal','',0,0,0.45,0.7
        size_text=self.get_item_in_config(dname,'develop-window')
        if size_text=='':
            return 'normal','',0,0,0.45,0.7
        if '+' in size_text:
            # parse  x+y+width*height
            fields=size_text.split('+')
            if len(fields) != 3:
                return 'error','Do not understand Display Window in display.cfg for '+dname,0,0,0,0
            dimensions=fields[2].split('*')
            if len(dimensions)!=2:
                return 'error','Do not understand Display Window in display.cfg for '+dname,0,0,0,0
            
            if not fields[0].isdigit():
                return 'error','x is not a positive decimal in display.cfg for '+dname,0,0,0,0
            else:
                x=float(fields[0])
            
            if not fields[1].isdigit():
                return 'error','y is not a positive decimal in display.cfg for '+dname,0,0,0,0
            else:
                y=float(fields[1])
                
            if not self.is_scale(dimensions[0]):
                return 'error','width1 is not a positive decimal in display.cfg for '+dname,0,0,0,0
            else:
                width=float(dimensions[0])
                
            if not self.is_scale(dimensions[1]):
                return 'error','height is not a positive decimal in display.cfg for '+dname,0,0,0,0
            else:
                height=float(dimensions[1])

            return 'normal','',x,y,width,height


    def is_scale(self,s):
        try:
            sf=float(s)
            if sf > 0.0 and sf <=1:
                return True
            else:
                return False
        except ValueError:
            return False


# ***********************************************
# HDMI Monitor Commands for DSI and HDMI
# ************************************************

    def handle_monitor_command(self,args):
        #print ('args',args)
        if len(args) == 0:
            return 'error','no arguments for monitor command'
        if len (args) == 2:
            command = args[0]
            display= args[1].upper()
            if display not in DisplayManager.display_map:
                return 'error', 'Monitor Command - Display not known: '+ display
            display_name=DisplayManager.vlc_display_name_map[display]                
            display_num=DisplayManager.display_map[display]
            if display_num not in DisplayManager.displays:
                return 'error', 'Monitor Command - Display not connected: '+ display 
            display_ref=str(display_num)
        else:
            return 'error', 'Display not specified: monitor '+ args[0]
        # print (command,display_name)

            
        if command == 'on':
            os.system('xrandr --output '+ display_name + ' --preferred')
            return 'normal',''
            
        elif command == 'off':
            os.system('xrandr --output '+ display_name + ' --off')
            return 'normal',''
        else:
            return 'error', 'Illegal Monitor command: '+ command



# ***********************************************
# Touchscreen Backlight Commands
# ************************************************ 
   
    def init_backlight(self):
        self.backlight=None
        self.orig_brightness=20
        if 0 in DisplayManager.displays:
            try:
                from rpi_backlight import Backlight
            except:
                return 'error','touchscreen connected but rpi-backlight is not installed'
            try:
                self.backlight=Backlight()
            except:
                return 'error','Official Touchscreen, problem with rpi-backlight'
            try:
                self.orig_brightness=self.backlight.brightness
            except:
                return 'error','Official Touchscreen,  problem with rpi-backlight'
        #print ('BACKLIGHT',self.backlight,self.orig_brightness)
        return 'normal',''

    def terminate_backlight(self):
        if self.backlight is not None:
            self.backlight.power=True
            self.backlight.brightness=self.orig_brightness

    def do_backlight_command(self,text):
        if self.backlight is None:
            return 'normal','no touchscreen'
        fields=text.split()
        # print (fields)
        if len(fields)<2:
            return 'error','too few fields in backlight command: '+ text
        # on, off, inc val, dec val, set val fade val duration
        #                                      1   2    3
        if fields[1]=='on':
            self.backlight.power = True
            return 'normal',''      
        if fields[1]=='off':
            self.backlight.power = False
            return 'normal',''
        if fields[1] in ('inc','dec','set'):
            if len(fields)<3:
                return 'error','too few fields in backlight command: '+ text
            if not fields[2].isdigit():
                return'error','field is not a positive integer: '+text
            if fields[1]=='set':
                val=int(fields[2])
                if val>100:
                    val = 100
                elif val<0:
                    val=0
                # print (val)
                self.backlight.brightness = val
                return 'normal',''            
            if fields[1]=='inc':
                val = self.backlight.brightness + int(fields[2])
                if val>100:
                    val = 100
                # print (val)
                self.backlight.brightness= val
                return 'normal',''
            if fields[1]=='dec':
                val = self.backlight.brightness - int(fields[2])
                if val<0:
                    val = 0
                # print (val)
                self.backlight.brightness= val
                return 'normal',''
        if fields[1] =='fade':
            if len(fields)<4:
                return 'error','too few fields in backlight command: '+ text
            if not fields[2].isdigit():
                return'error','backlight field is not a positive integer: '+text            
            if not fields[3].isdigit():
                return'error','backlight field is not a positive integer: '+text
            val=int(fields[2])
            if val>100:
                val = 100
            elif val<0:
                val=0
            with selfbacklight.fade(duration=fields[3]):
                self.backlight.brightness=val
                return 'normal',''
        return 'error','unknown backlight command: '+text


# used to test on a machine without a backlight
class FakeBacklight():
    
    def __init__(self):
        self._brightness=100
        self._power = True
        # print ('USING FAKE BACKLIGHT')
        

    def get_power(self):
        return self._power

    def set_power(self, power):
        self._power=power
        print ('POWER',self._power)

    power = property(get_power, set_power)

    def get_brightness(self):
        return self._brightness

    def set_brightness(self, brightness):
        self._brightness=brightness
        print ('BRIGHTNESS',self._brightness)

    brightness = property(get_brightness, set_brightness)    


    
# **************************
# Test Harness
# **************************   

# dummy debug monitor
class Mon(object):
    
    def err(self,inst,message):
        print ('ERROR: ',message)

    def log(self,inst,message):
        print ('LOG: ',message)

    def warn(self,inst,message):
        print ('WARN: ',message)
        

class Display(object):
    
    def __init__(self):
        self.mon=Mon()
    
    def init(self):
        self.options={'fullscreen':True,'nounclutter':False}
        # set up the displays and create a canvas for each display
        self.dm=DisplayManager()
        self.pp_dir=sys.path[0]
        status,message,self.root=self.dm.init(self.options,self.end,self.pp_dir,True)
        if status !='normal':
            print ('Error',message)
    
    def end(self):
        print ('end')

if __name__ == '__main__':
    disp=Display()
    disp.init()
    #pp=PiPresents()
    
