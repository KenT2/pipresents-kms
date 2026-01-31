"""
pp_mpvdriver.py

API for mpv which allows mpv to be controlled by the python-mpv library
python bindings for mpv are here https://github.com/jaseg/python-mpv, sudo apt install python3-mpv

USE


Initial state is idle, this is altered by the calls

load() - start mpv and loads a track and then run to start depending on freeze-at-start.
      load() is non-blocking and returns immeadiately. To determine load is complete poll using get_state() to obtain the state
    load-loading - load in progress
    load-ok - loading complete and ok
    load-fail

show - show a track that has been loaded. Show is non-blocking and returns immeadiately. To determine showing is complete poll using get_state to obtain the state
    show-showing - showing in progress
    show-pauseatend - paused before last frame.
    show-niceday - track has ended
    show-fail
    
stop() - stops showing. To determine if complete poll get_state() for: 
      show-niceday

unload() - stops loading. To determine if complete poll state for:
      load-unloaded

close() - exits mpv and exits pp_mpvdriver.py
    
set_pause() - pause or unpause

set_volume() - set the volume between 0 and 100. Use only when showing
      
set-device - set audio device ??????
pause/ unpause - pauses the track
mute()unmute - mute without changing volume

"""

import time
import sys,os
from python_mpv_jsonipc import MPV
import tkinter as tk
from pp_utils import Monitor
import objgraph
import gc

class MPVDriver(object):
    
    # used first time and for every other instance
    def __init__(self,root,canvas,freeze_at_start,freeze_at_end,background_colour):
        #print ('\nINIT')
        self.mon=Monitor()
        self.mon.log (self,'start mpvdriver')
        self.root=root
        self.canvas=canvas
        self.freeze_at_start=freeze_at_start
        self.freeze_at_end=freeze_at_end
        self.background_colour=background_colour

        self.frozen_at_start=False
        self.frozen_at_end=False  
        self.state='idle'      
        self.user_pause=False
        self.quit_load_signal=False
        self.quit_show_signal=False
        self.show_status_timer=None
        self.load_status_timer=None
        



    def load(self,track,options,x,y,width,height):
        #print ('driver load',track)
        # for showing uncollectable garbage
        # objgraph.show_growth(limit=1)        
        self.width=width
        self.height=height
        self.track=track
        self.options=options
        
        self.state='load-loading'
        self.load_position=-1
        self.load_complete_signal=False
        #self.video_frame=tk.Frame(height=self.height,width=self.width,bg=self.background_colour)
        self.video_frame=tk.Frame(height=0,width=0,bg=self.background_colour)
        self.video_frame.place(x=x,y=y)
        self.root.update_idletasks()
        self.player=MPV(input_default_bindings='no', input_vo_keyboard ='no',osc='no',
                                     profile='fast',config='no',
                                     wid=str(int(self.video_frame.winfo_id()))
                                     )

        status,message=self.apply_options(self.options)
        if status == 'error':
            print(message)

        self.player.play(self.track)
        self.player.volume=0        
        #need a timeout as sometimes a load will fail 
        self.load_timeout= 200
        
        self.load_status_timer=self.root.after(1,self.load_status_loop)
        
    def apply_options(self,options):
        for option in options:
            #print (option[0],option[1])
            try:
                setattr(self.player,option[0],option[1])
            except:
                print ('ERROR bad mpv option',option[0],option[1])
                #return 'error','bad MPV option: ' + option[0] +' '+ option[1]
        return 'normal',''


    def load_status_loop(self):
        #print(self.player.time_pos)

        if self.quit_load_signal is True:
            self.quit_load_signal=False
            self.player.stop() 
            self.state= 'load-unloaded'
            self.mon.log (self,'unloaded at: '+str(self.load_position))
            return
            
        if self.load_complete() is True:
            #print ('load complete')
            self.duration=self.player.duration

            if self.freeze_at_start in ('before-first-frame','after-first-frame'):
                self.mon.log (self,'load-frozen at: ' + str(self.load_position))
                self.frozen_at_start=True
                if self.freeze_at_start=='after-first-frame':
                    pass
                    self.video_frame.config(height=self.height,width=self.width,bg=self.background_colour)
                    self.root.update_idletasks()
                self.state='load-frozen'
                
            else:
                self.state='load-ok'
                #print ('load OK')
                self.video_frame.config(height=self.height,width=self.width,bg=self.background_colour)
                self.root.update_idletasks()                
                self.mon.log (self,'load-ok at: '+str(self.load_position))
                
            return
            
        self.load_timeout-=1
        if self.load_timeout <=0:
            self.mon.fatal (self,'load failed due to timeout load position is:'+str(self.load_position))
            self.state='load-fail'
            return

        self.load_status_timer=self.root.after(10,self.load_status_loop)


    def load_complete(self):
        value=self.player.time_pos
        #print ('load',value)
        if value is not None and value>=0:
            self.player.pause=True
            self.load_complete_signal=True
            self.load_position=value
            return True
        return False


    def show(self,initial_volume):
        #print ('driver showing',self.track)
        if self.freeze_at_start == 'no':
            self.state='show-showing'
            self.video_frame.config(height=self.height,width=self.width,bg=self.background_colour)
            self.set_volume(initial_volume)
            self.canvas.update_idletasks()
            self.mon.log (self,'no freeze at start, start showing')
            self.frozen_at_start=False
            self.player.pause=False
            #print('going to loop')
            self.show_status_timer=self.root.after(10,self.show_status_loop)
        return


    def show_complete(self):
        value=self.player.time_pos
        #print ('in show complete',self.freeze_at_end,value)
        if self.freeze_at_end =='yes':
            #if name =='time-pos' and value == None:
                #print('mpv video overrun, time-pos is: ',value)
            if (value==None)or(value>self.duration-0.12):
                self.show_position=value
                return True
            return False
        else:
            if value==None:
                self.show_position=value
                #print('change detected niceday ',value)
                return True
            return False
            #print('missed change',name,value)
                
 
    def show_status_loop(self):
        #print ('start of loop')
        sc=self.show_complete()
        if self.quit_show_signal is True:
            self.quit_show_signal= False
            if self.freeze_at_end == 'yes':
                self.frozen_at_end=True
                self.player.pause=True
                self.state='show-pauseatend'
                self.mon.log(self,'stop caused pause '+self.state)
                return
            else:
                self.player.stop()
                self.state='show-niceday'
                self.mon.log(self,'stop caused no pause '+self.state)
                return
        #print ('in loop',sc)        
        if sc is True:
            #print ('show complete')
            if self.freeze_at_end == 'yes':
                self.player.pause=True
                self.frozen_at_end=True
                #print ('pause')
                self.mon.log(self,'paused at end at: '+str(self.show_position))
                self.state='show-pauseatend'
                return
            else:
                self.mon.log(self,'ended with no pause'+str(self.show_position))
                #print ('niceday')
                self.state='show-niceday'
                self.frozen_at_end=False
                #self.player.stop()
                return
                
        else:
            self.show_status_timer=self.root.after(30,self.show_status_loop)

    def  hide(self):
        #print ('driver hide',self.track)
        pass


    def close(self):
        #print ('driver close',self.track)
        #if self.freeze_at_end  =='yes':
            #self.player.pause=False
            #self.player.stop()
        self.player.terminate()
        self.video_frame.destroy()
        if self.load_status_timer != None:
            self.root.after_cancel(self.load_status_timer)
            self.load_status_timer=None
        if self.show_status_timer != None:
            self.root.after_cancel(self.show_status_timer)
            self.show_status_timer=None
            
        # to show uncollectable garbage
        #print('Uncollectable Garbage',gc.collect())
        #objgraph.show_growth()
        #objgraph.show_backrefs(objgraph.by_type('Canvas'),filename='backrefs.png')

        
# ***********************
# Commands
# ***********************
        
    def get_state(self):
        return self.state

    def go(self,initial_volume):
        if self.frozen_at_start is True:
            self.state='show-showing'
            self.mon.log (self,'freeze off, go ok')
            self.player.pause=False
            self.video_frame.config(height=self.height,width=self.width,bg=self.background_colour)
            self.set_volume(initial_volume)
            self.root.after(1,self.show_status_loop)
            self.frozen_at_start=False
            return 'go-ok'
        else:
            self.mon.log (self,'go rejected')
            return 'go-reject'
        
        
    def pause(self):
        if self.state== 'show-showing' and self.frozen_at_end is False and self.frozen_at_start is False:
            if self.user_pause is True:
                self.player.pause=False
                self.user_pause=False
                self.mon.log (self,'pause to pause-off ok')
                return 'pause-off-ok'
            else:
                self.user_pause=True
                self.player.pause=True
                self.mon.log (self,'pause to pause-on ok')
                return 'pause-on-ok'
        else:
            self.mon.log (self,'pause rejected')
            return 'pause-reject'


    def pause_on(self):
        if self.state== 'show-showing' and self.frozen_at_end is False and self.frozen_at_start is False:
            self.user_pause=True
            self.player.pause=True
            self.mon.log (self,'pause on ok')
            return 'pause-on-ok'
        else:
            self.mon.log (self,'pause on rejected')
            return 'pause-on-reject'
            
                    
    def pause_off(self):
        if self.state== 'show-showing' and self.frozen_at_end is False and self.frozen_at_start is False:
            self.player.pause=False
            self.user_pause=False
            self.mon.log (self,'pause off ok')
            return 'pause-off-ok'
        else:
            return 'pause-off-reject'

    def stop(self):
        if self.frozen_at_start is True:
            self.player.stop()
            self.state='show-niceday'
            self.mon.log(self,'stop during frozen at start '+self.state)
            return
        else:
            self.quit_show_signal=True
            return

        
    def unload(self):
        if self.state=='load-loading':
            self.quit_load_signal=True
        else:
            self.state='load-unloaded'

    def mute(self):
        self.player.mute=True
        
    def unmute(self):
        self.player.mute=False
                
    def set_volume(self,volume):
        self.player.volume=volume        

    def set_device(self,device_id):
        if device_id=='':
            self.player.audio_output_device_set(None,None) 
        else:           
            self.player.audio_output_device_set(None,device_id)


class PP(object):



    def __init__(self):
        self.mon=Monitor()

        
    def start(self):
        # jan25 these options work
        self.options=[['vo','gpu'],['sid','auto'],['input-default-bindings','no'],
        ['input-vo-keyboard','no'],['osc','no'],['ao','pulse'],['video-aspect-override','-1']]

        self.root,self.canvas,width,height=self.create_gui()
        self.width=width-100
        self.height=height-100
        self.dd1=None
        self.dd2=None
        self.root.after(1,self.load_first)
        self.root.mainloop()

        
    def load_first(self):
        # jan25
        self.dd1=MPVDriver(self.root,self.canvas,'no','no','black')
        self.dd1.load('/home/pp/pp_home/media/1sec.mp4',self.options,100,100,self.width,self.height)
        self.monitor_load1()
        
    def monitor_load1(self):
        state=self.dd1.get_state()
        #print ('load1 state', state)
        if state=='load-ok':
            self.show_first()
            return
        self.root.after(100,self.monitor_load1)        
        
    def show_first(self):
        #print ('ready to show first')
        self.dd1.show(100)
        if self.dd2 is not None:
            self.dd2.close()
        self.monitor_show1()
        
        
    def monitor_show1(self):
        state=self.dd1.get_state()
        #print ('show1 state', state)
        if state in ('show-pauseatend','show-niceday'):
            self.load_second()
            return
        self.root.after(100,self.monitor_show1)  

        
    def load_second(self):
        self.dd2=MPVDriver(self.root,self.canvas,'no','yes','white')
        self.dd2.load('/home/pp/pp_home/media/1sec.mp4',self.options,9,0,self.width,self.height)
        self.monitor_load2()   
        
        
    def monitor_load2(self):
        state=self.dd2.get_state()
        #print ('load state', state)
        if state=='load-ok':
            self.show_second()
            return
        self.root.after(100,self.monitor_load2)            
        
        
    def show_second(self):
        #print ('ready to show second')
        self.dd2.show(100)
        self.dd1.close()
        self.monitor_show2()
        
        
    def monitor_show2(self):
        state=self.dd2.get_state()
        #print ('show2 state', state)
        if state in ('show-pauseatend','show-niceday'):
            self.load_first()
            return
        self.root.after(100,self.monitor_show2)  
                
        
    def close_callback(self,dum=None):
        self.root.destroy()
        exit()
    
    
    def create_gui(self):
        # print (this_id, self.develop_id)            
        tk_window=tk.Tk()
        root=tk_window
        tk_window.title('Pi Presents - ')
        tk_window.iconname('Pi Presents')
        tk_window.config(bg='black')


        # set window dimensions and decorations
        # fullscreen for all displays that are not develop_id
        window_width=400
        # krt jan25
        window_height=300
        window_x=0
        window_y=0
        #KRT
        tk_window.attributes('-fullscreen', False)
        
        # print ('Window Position FS', this_id, window_x,window_y,window_width,window_height)
        tk_window.geometry("%dx%d%+d%+d"  % (window_width,window_height,window_x,window_y))
        #jan25
        tk_window.attributes('-zoomed','0')
  
        # define response to main window closing.
        tk_window.protocol ("WM_DELETE_WINDOW", self.close_callback)
        root.bind('x',self.close_callback)

        # setup a canvas onto which will be drawn the images or text
        # canvas covers the whole screen whatever the size of the window

        #jan25
        canvas_height=300
        canvas_width=400
        
        tk_canvas = tk.Canvas(tk_window, bg='black')
        tk_canvas.config(height=canvas_height,
                                 width=canvas_width,
                                 highlightthickness=0,
                                highlightcolor='yellow')
        tk_canvas.place(x=0,y=0)

        tk_canvas.config(bg='red')

        tk_window.focus_set()
        tk_canvas.focus_set()
    

        return root,tk_canvas,canvas_width,canvas_height

        

        
if __name__ == '__main__':
    import tkinter as tk
    p = PP()
    p.start()

    




  
    

    

