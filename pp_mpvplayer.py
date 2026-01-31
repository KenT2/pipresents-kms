# -*- coding: utf-8 -*-
import os
from pp_mpvdriver import MPVDriver
from pp_player import Player
from pp_utils import parse_rectangle
from pp_displaymanager import DisplayManager
from pp_audiomanager import AudioManager
import copy
from pp_utils import Monitor
#import objgraph
#import gc

# NO display name
# no layer
# no 
# warp --video-aspect-override=4:3  -1 to disable


class MPVPlayer(Player):
    """
    plays a track using MPVplayer
    _init_ iniitalises state and checks resources are available.
    use the returned instance reference in all other calls.
    At the end of the path (when closed) do not re-use, make instance= None and start again.
    States - 'initialised' when done successfully
    Initialisation is immediate so just returns with error code.
    """

    
    def __init__(self,
                 show_id,
                 showlist,
                 root,
                 canvas,
                 show_params,
                 track_params ,
                 pp_dir,
                 pp_home,
                 pp_profile,
                 end_callback,
                 command_callback):
                     

        # initialise items common to all players   
        Player.__init__( self,
                         show_id,
                         showlist,
                         root,
                         canvas,
                         show_params,
                         track_params ,
                         pp_dir,
                         pp_home,
                         pp_profile,
                         end_callback,
                         command_callback)
        # print ' !!!!!!!!!!!videoplayer init'
        self.mon.trace(self,'')

        
        # output device
        if self.track_params['mpv-audio'] != "":
            self.mpv_audio= self.track_params['mpv-audio']
        else:
            self.mpv_audio= self.show_params['mpv-audio']
            
        self.mpv_max_volume_text= self.track_params['mpv-max-volume']
        
        if self.track_params['mpv-volume'] != "":
            self.mpv_volume_text= self.track_params['mpv-volume']
        else:
            self.mpv_volume_text= self.show_params['mpv-volume']

        if self.track_params['mpv-window'] != '':
            self.mpv_window= self.track_params['mpv-window']
        else:
            self.mpv_window= self.show_params['mpv-window']
            
        if self.track_params['mpv-aspect-mode'] != '':
            self.mpv_aspect_mode= self.track_params['mpv-aspect-mode']
        else:
            self.mpv_aspect_mode= self.show_params['mpv-aspect-mode']

            
        if self.track_params['mpv-other-options'] != '':
            self.mpv_other_options= self.track_params['mpv-other-options']
        else:
            self.mpv_other_options= self.show_params['mpv-other-options']
            
        # FREEZING
        if self.track_params['mpv-freeze-at-start'] != '':
            self.freeze_at_start= self.track_params['mpv-freeze-at-start']
        else:
            self.freeze_at_start= self.show_params['mpv-freeze-at-start']

        if self.track_params['mpv-freeze-at-end'] != '':
            self.freeze_at_end= self.track_params['mpv-freeze-at-end']
        else:
            self.freeze_at_end= self.show_params['mpv-freeze-at-end']
            
        if self.track_params['pause-timeout'] != '':
            self.pause_timeout_text= self.track_params['pause-timeout']
        else:
            self.pause_timeout_text= self.show_params['pause-timeout']
        
        self.dm=DisplayManager()
        self.am=AudioManager()  
        
        # initialise video playing state and signals
        self.quit_signal=False
        self.unload_signal=False
        self.play_state='initialised'
        self.frozen_at_end=False
        self.pause_timer=None      
        return
    
    def process_params(self):
        
        self.options=[]
        
        # DISPLAY
        video_display_name = self.show_canvas_display_name
        # Is it valid and connected
        status,message,self.mpv_display_id=self.dm.id_of_display(video_display_name)
        if status == 'error':
            return 'error',message
            
        # AUDIO
        self.audio_sys=self.am.get_audio_sys()
        if self.audio_sys == 'pulse':
            status,message,self.mpv_sink = self.am.get_sink(self.mpv_audio)
            if status == 'error':
                return 'error',message
                    
            if not self.am.sink_connected(self.mpv_sink):
                return 'error','"'+self.mpv_audio +'" display or audio device not connected\n\n    Expected sink is: '+ self.mpv_sink
                    
            self.add_option('ao','pulse')
        else:
            return 'error','audio systems other than pulseaudio are not supported'
               
        # AUDIO DEVICE
        #print (self.mpv_audio,self.mpv_sink)
        self.add_option ('audio_device','pulse/'+self.mpv_sink)
        
        # VOLUME
        if self.mpv_volume_text != "":
            self.mpv_volume= int(self.mpv_volume_text)
        else:
            self.mpv_volume=100
            
        # MAX VOLUME
        if self.mpv_max_volume_text != "":
            if not self.mpv_max_volume_text.isdigit():
                return 'error','mpv Max Volume must be a positive integer: '+self.mpv_max_volume_text
            self.max_volume= int(self.mpv_max_volume_text)
            if self.max_volume>100:
                return 'error','mpv Max Volume must be <= 100: '+ self.mpv_max_volume_text                
        else:
            self.max_volume=100
            
        self.initial_volume=min(self.mpv_volume,self.max_volume)
        self.volume=self.initial_volume
        
        
        # SUBTITLES
        self.mpv_subtitles=self.track_params['mpv-subtitles']
        if self.mpv_subtitles =='yes':
            self.add_option('sid','auto')
        else:
            self.add_option('sid','no')
                    
        # VIDEO WINDOW
        # size and position of frame containing the video
        # user needs to set this to match the videos aspect ratio
   
        status,message,self.x,self.y,self.width,self.height=self.parse_mpv_video_window(self.mpv_window)
        if status=='error':
            return status,message


        # FIT TO WINDOW
        if self.mpv_aspect_mode == 'warp':
            self.add_option('video_aspect_override',str(self.width)+':'+str(self.height))
        else:
            self.add_option('video_aspect_override','-1')

        #self.add_option('video_unscaled','yes')
        #self.add_option('panscan','0.5')       
            

        # OTHER OPTIONS
        status,message=self.parse_options(self.track_params['mpv-other-options'])
        if status == 'error':
            return status,message
        
        # PAUSE TIMEOUT
        if self.pause_timeout_text.isdigit():
            self.pause_timeout= int(self.pause_timeout_text)
        else:
            self.pause_timeout=0
            
        return 'normal',''

    def add_option(self,option,val):
        opt=[option,val]
        self.options.append(opt)
        

   # LOAD - creates a mpv instance, loads a track and then pause
    def load(self,track,loaded_callback,enable_menu): 
        #print ('\nplayer load',track) 
        # instantiate arguments
        self.track=track
        self.loaded_callback=loaded_callback   #callback when loaded
        self.mon.log(self,"Load track received from show Id: "+ str(self.show_id) + ' ' +self.track)
        self.mon.trace(self,'')
        
                
        #process mpv parameters
        status,message=self.process_params()
        if status == 'error':
            self.mon.err(self,message)
            self.play_state='load-failed'
            if self.loaded_callback is not  None:
                self.loaded_callback('error',message)
                return 

        # do common bits of  load
        Player.pre_load(self) 
        
        # load the plugin, this may modify self.track and enable the plugin drawing to canvas
        if self.track_params['plugin'] != '':
            status,message=self.load_plugin()
            if status == 'error':
                self.mon.err(self,message)
                self.play_state='load-failed'
                if self.loaded_callback is not  None:
                    self.loaded_callback('error',message)
                    return
                    
        # load the images and text
        status,message=self.load_x_content(enable_menu)
        if status == 'error':
            self.mon.err(self,message)
            self.play_state='load-failed'
            if self.loaded_callback is not  None:
                self.loaded_callback('error',message)
                return

        if ':' in track:
            self.mon.err(self,"Cannot play a stream: "+ track)
            self.play_state='load-failed'
            if self.loaded_callback is not  None:
                self.loaded_callback('error','track file not found: '+ track)
                return
                
        # check file exists if not a mrl
        if not ':'in track:        
            if not os.path.exists(track):
                    self.mon.err(self,"Track file not found: "+ track)
                    self.play_state='load-failed'
                    if self.loaded_callback is not  None:
                        self.loaded_callback('error','track file not found: '+ track)
                        return


        self.mpvdriver = MPVDriver(self.root,self.canvas,self.freeze_at_start,self.freeze_at_end,self.background_colour)
        


        # load the media
        self.mpvdriver.load(self.track,self.options,self.x,self.y,self.width,self.height)
        

        
        self.start_state_machine_load()



     # SHOW - show a track      
    def show(self,ready_callback,finished_callback,closed_callback):
        #print ('player show',self.track)
        self.ready_callback=ready_callback         # callback when paused after load ready to show video
        self.finished_callback=finished_callback         # callback when finished showing
        self.closed_callback=closed_callback

        self.mon.trace(self,'')

        #  do animation at start and ready_callback which closes+hides the previous track
        Player.pre_show(self)
        
        # start show state machine
        self.start_state_machine_show()



    # UNLOAD - abort a load when vlcdriver is loading or loaded
    def unload(self):
        self.mon.trace(self,'')
        self.mon.log(self,">unload received from show Id: "+ str(self.show_id))
        self.start_state_machine_unload()


    # CLOSE - quits vlcdriver from 'pause at end' state
    def close(self,closed_callback):
        #print ('player close',self.track)
        self.mon.trace(self,'')
        self.mon.log(self,">close received from show Id: "+ str(self.show_id))
        self.closed_callback=closed_callback
        self.start_state_machine_close()





# ***********************
# track showing state machine
# **********************

    """
    STATES OF STATE MACHINE
    Threre are ongoing states and states that are set just before callback

    >init - Create an instance of the class
    <On return - state = initialised   -  - init has been completed, do not generate errors here

    >load
        Fatal errors should be detected in load. If so  loaded_callback is called with 'load-failed'
         Ongoing - state=loading - load called, waiting for load to complete   
    < loaded_callback with status = normal
         state=loaded - load has completed and video paused before or after first frame      
    <loaded_callback with status=error
        state= load-failed -  failure to load   

    On getting the loaded_callback with status=normal the track can be shown using show


    >show
        show assumes a track has been loaded and is paused.
       Ongoing - state=showing - video is showing 
    <finished_callback with status = pause_at_end
            state=showing but frozen_at_end is True
    <closed_callback with status= normal
            state = closed - video has ended vlc has terminated.


    On getting finished_callback with status=pause_at end a new track can be shown and then use close to close the previous video when new track is ready
    On getting closed_callback with status=  nice_day vlcdriver closing should not be attempted as it is already closed
    Do not generate user errors in Show. Only generate system errors such as illegal state and then use end()

    >close
       Ongoing state - closing - vlcdriver processes are dying
    <closed_callback with status= normal - vlcdriver is dead, can close the track instance.

    >unload
        Ongoing states - start_unload and unloading - vlcdriver processes are dying.
        when unloading is complete state=unloaded
        I have not added a callback to unload. its easy to add one if you want.

    closed is needed because wait_for_end in pp_show polls for closed and does not use closed_callback
    
    """


    def start_state_machine_load(self):
        # initialise all the state machine variables
        self.play_state='loading'
        self.tick_timer=self.canvas.after(1, self.load_state_machine) #50
        
    def load_state_machine(self):
        if self.unload_signal is True:
            self.unload_signal=False
            self.state='unloading'
            self.mpvdriver.unload()
            self.root.after(100,self.load_state_machine)
        else:
            resp=self.mpvdriver.get_state()
            # pp_vlcdriver changes state from load-loading when track is frozen at start.
            if resp == 'load-fail':
                self.play_state = 'load-failed'
                self.mon.log(self,"      Entering state : " + self.play_state + ' from show Id: '+ str(self.show_id))
                if self.loaded_callback is not  None:
                    self.loaded_callback('error','timeout when loading mpv track')
                return
            elif resp=='load-unloaded':
                self.play_state = 'unloaded'
                self.mon.log(self,"      Entering state : " + self.play_state + ' from show Id: '+ str(self.show_id))
                # PP does not need this callback
                #if self.loaded_callback is not  None:
                    #self.loaded_callback('normal','unloaded')
                return            
            elif resp in ('load-ok','load-frozen'):
                # stop received while in freeze-at-start - quit showing as soon as it starts
                #if resp=='stop-frozen':
                    #self.quit_signal= True
                    #self.mon.log(self,'stop received while in freeze-at-start')
                self.play_state = 'loaded'
                #if self.mpv_sink!='':
                    #self.set_device(self.mpv_sink)
                #else:
                    #self.set_device('')   
                self.mon.log(self,"      Entering state : " + self.play_state + ' from show Id: '+ str(self.show_id))
                if self.loaded_callback is not  None:
                    self.loaded_callback('normal','loaded')
                return
            else:
                self.root.after(10,self.load_state_machine) #100
            

    def start_state_machine_unload(self):
        # print ('mpvplayer - starting unload',self.play_state)
        if self.play_state in('closed','initialised','unloaded'):
            # mpvdriver already closed
            self.play_state='unloaded'
            # print ' closed so no need to unload'
        else:
            if self.play_state  ==  'loaded':
                # load already complete so set unload signal and kick off load state machine
                self.play_state='start_unload'
                self.unload_signal=True
                self.tick_timer=self.canvas.after(50, self.load_state_machine)
                
            elif self.play_state == 'loading':
                # signal load state machine to start_unloading state and stop vlcdriver
                self.unload_signal=True
            else:
                self.mon.err(self,'illegal state in unload method: ' + self.play_state)
                self.end('error','illegal state in unload method: '+ self.play_state)           


            
    def start_state_machine_show(self):
        if self.play_state == 'loaded':
            self.play_state='showing'
            
            # show the track
            self.mpvdriver.show(self.initial_volume)
            self.mon.log (self,'>showing track from show Id: '+ str(self.show_id))  
            # and start polling for state changes
            self.tick_timer=self.canvas.after(0, self.show_state_machine)
            """
            # race condition don't start state machine as unload in progress
            elif self.play_state == 'start_unload':
                pass
            """
        else:
            self.mon.fatal(self,'illegal state in show method ' + self.play_state)
            self.play_state='show-failed'
            if self.finished_callback is not None:
                self.finished_callback('error','illegal state in show method: ' + self.play_state)


    def show_state_machine(self):
        if self.play_state=='showing':
            if self.quit_signal is True:
                # service any queued stop signals by sending stop to vlcdriver
                self.quit_signal=False
                self.mon.log(self,"      stop video - Send stop to vlcdriver")
                self.mpvdriver.stop()
                self.tick_timer=self.canvas.after(10, self.show_state_machine)
            else:
                resp=self.mpvdriver.get_state()
                #print (resp)
                # driver changes state from show-showing depending on freeze-at-end.
                if resp == 'show-pauseatend':
                    self.mon.log(self,'vlcdriver says pause_at_end')
                    self.frozen_at_end=True
                    if self.finished_callback is not None:
                        self.finished_callback('pause_at_end','pause at end')
                        
                elif resp == 'show-niceday':
                    self.mon.log(self,'vlcdriver says nice_day')
                    self.play_state='closing'
                    self.mpvdriver.close()
                    # and terminate the vlcdriver process through pexpect
                    #self.vlcdriver.terminate()
                    self.tick_timer=self.canvas.after(10, self.show_state_machine)
                                        
                elif resp=='show-fail':
                    self.play_state='show-failed'
                    if self.finished_callback is not None:
                        self.finished_callback('error','pp_vlcdriver says show failed: '+ self.play_state)
                else:
                    self.tick_timer=self.canvas.after(30,self.show_state_machine)
                    
        elif self.play_state=='closing':
            self.play_state='closed'
            # state change needed for wait for end
            self.mon.log(self,"      Entering state : " + self.play_state + ' from show Id: '+ str(self.show_id))
            if self.closed_callback is not  None:
                self.closed_callback('normal','vlcdriver closed')             

    # respond to normal stop
    def stop(self):
        #print ('player stop')
        self.mon.log(self,">stop received from show Id: "+ str(self.show_id))
        # cancel the pause timer
        if self.pause_timer != None:
            self.canvas.after_cancel(self.pause_timer)
            self.pause_timer=None
        self.mpvdriver.stop()


    def start_state_machine_close(self):
        #print ('player start state close',self.track)
        # self.mon.log(self,">close received from show Id: "+ str(self.show_id))
        # cancel the pause timer
        if self.pause_timer != None:
            self.canvas.after_cancel(self.pause_timer)
            self.pause_timer=None
        self.mpvdriver.close()
        
        self.play_state='closing'
        #print ('start close state machine close')
        self.tick_timer=self.canvas.after(0, self.show_state_machine)



# ************************
# COMMANDS
# ************************

    def input_pressed(self,symbol):
        if symbol == 'inc-volume':
            self.inc_volume()
        elif symbol == 'dec-volume':
            self.dec_volume()            
        elif symbol  == 'pause':
            self.pause()
        elif symbol  == 'go':
            self.go()
        elif symbol  == 'unmute':
            self.unmute()
        elif symbol  == 'mute':
            self.mute()
        elif symbol  == 'pause-on':
            self.pause_on()    
        elif symbol  == 'pause-off':
            self.pause_off()
        elif symbol == 'stop':
            self.stop()


    def inc_volume(self):
        self.mon.log(self,">inc-volume received from show Id: "+ str(self.show_id))
        if self.play_state  == 'showing':
            if self.volume < self.max_volume:
                self.volume+=1
            self.set_volume(self.volume)
            return True
        else:
            self.mon.log(self,"!<inc-volume rejected " + self.play_state)
            return False

    def dec_volume(self):
        self.mon.log(self,">dec-volume received from show Id: "+ str(self.show_id))

        if self.play_state  == 'showing':
            if self.volume > 0:
                self.volume-=1
            self.set_volume(self.volume)
            return True
        else:
            self.mon.log(self,"!<dec-volume rejected " + self.play_state)
            return False

    def set_volume(self,vol):
        # print ('SET VOLUME',vol)
        self.mpvdriver.set_volume(vol)
        


    def mute(self):
        self.mon.log(self,">mute received from show Id: "+ str(self.show_id))
        self.mpvdriver.mute()
        return True        
                

    def unmute(self):
        self.mon.log(self,">unmute received from show Id: "+ str(self.show_id))
        self.mpvdriver.unmute()


    # ???? why no test if already paused or unpaused
    # toggle pause
    def pause(self):
        self.mon.log(self,">toggle pause received from show Id: "+ str(self.show_id))
        reply=self.mpvdriver.pause()
        if reply == 'pause-on-ok':
            if self.pause_timeout>0:
                # kick off the pause timeout timer
                self.pause_timer=self.canvas.after(self.pause_timeout*1000,self.pause_timeout_callback)
            return True
        elif reply == 'pause-off-ok':
            if self.pause_timer != None:
                # cancel the pause timer
                self.canvas.after_cancel(self.pause_timer)
                self.pause_timer=None
            return True
        else:
            self.mon.log(self,"!<toggle pause rejected " + self.play_state)
            return False              
            

    def pause_timeout_callback(self):
        self.pause_off()
        self.pause_timer=None

    # pause on
    def pause_on(self):
        self.mon.log(self,">pause on received from show Id: "+ str(self.show_id))
        reply=self.mpvdriver.pause_on()
        if reply == 'pause-on-ok':
            if self.pause_timeout>0:
                # kick off the pause timeout timer
                self.pause_timer=self.canvas.after(self.pause_timeout*1000,self.pause_timeout_callback)
            return True
        else:
            self.mon.log(self,"!<pause on rejected " + self.play_state)
            return False

    # pause off
    def pause_off(self):
        self.mon.log(self,">pause off received from show Id: "+ str(self.show_id))
        reply=self.mpvdriver.pause_off()
        if reply == 'pause-off-ok':
            if self.pause_timer != None:
                # cancel the pause timer
                self.canvas.after_cancel(self.pause_timer)
                self.pause_timer=None
            return True
        else:
            self.mon.log(self,"!<pause off rejected " + self.play_state)
            return False

    # go after freeze at start
    def go(self):
        reply=self.mpvdriver.go(self.initial_volume)
        if reply == 'go-ok':
            return True
        else:
            self.mon.log(self,"!<go rejected " + self.play_state)
            return False



    def parse_options(self,text):
        if text.strip() == '':
            return 'normal',''
        options=text.split(',')
        #print (options)
        for option in options:
            if option.count('=') !=1:
                return 'error','malformed option: '+ option
            result=option.split('=')
            self.add_option(result[0].strip().replace("-", "_"),result[1].strip())
        return 'normal',''


# *****************************
# SETUP
# *****************************

    """
    def aspect_mode(self):

        In omxplayer Video Window has parameters only for warp, all other modes are centred the full screen

        In vlcplayer there are two fields, VLC Window and Aspect Mode. VLC Window position and sizes the window then
        Aspect Mode is applied to all results of VLC Window :
        
        stretch - transform video to make it fill the window with aspect ratio the same as the window

        fill - crop the video so that it fills the window while retaining the video's aspect ratio

        letterbox - vlc's default mode
                        adjust the video  so that whole video is seen in the window while keeping the video's aspect ratio
                        If the window's aspect ratio does not match that of the video media then the x,y, position will be incorrect,
                        (except on fullscreen). This is because the result is centred in the window.


        vlc - use vlc's aspect ratio and crop in the defined window
            Cannot use both crop and aspect ratio
            window size w*h needs to have the same ratio as the result of crop or aspect-ratio otherwise the displayed position will be incorrect
            values must be integers e.g 5.1:1 does not work 
            crop formats:    <aspect_num>:<aspect_den> e.g.4:3
                            <width>x<height>+<x>+<y>
                            <left>+<top>+<right>+<bottom>
            aspect ratio formats: <aspect_num>:<aspect_den> e.g.4:3

        if self.vlc_aspect_mode == 'stretch':
            window_ratio=self.vlc_window_width/self.vlc_window_height
            self.vlcdriver.sendline('ratio '+ str(self.vlc_window_width)+':'+str(self.vlc_window_height))
            return 'normal',''
            
        elif self.vlc_aspect_mode == 'fill':
            self.vlcdriver.sendline('crop '+ str(self.vlc_window_width)+':'+str(self.vlc_window_height))
            return 'normal',''
            
        elif self.vlc_aspect_mode == 'letterbox':
            # default vlc behavior
            return 'normal',''
            
        elif self.vlc_aspect_mode == 'vlc':
            if self.vlc_aspect_ratio != '' or self.vlc_crop!= '':
                if self.vlc_crop!= '':
                    self.vlcdriver.sendline('crop '+ self.vlc_crop)
                    
                if self.vlc_aspect_ratio != '':
                    self.vlcdriver.sendline('ratio '+ self.vlc_aspect_ratio)
                return 'normal',''
            else:
                return 'error', 'crop or aspect mode not specified for vlc option'
        else:
            return 'error','Aspect Mode cannot be blank '+ self.vlc_aspect_mode


    
    """


                
    def parse_mpv_video_window(self,line):
        words=line.split()
        if len(words) not in (1,2):
            return 'error','bad mpv video window form '+line,0,0,0,0
            
        if words[0] not in ('display','showcanvas'):
            return 'error','Bad mpv Window option: '+line,0,0,0,0
            

        if words[0] == 'display':
            x_org=0
            y_org=0
            width,height= self.dm.canvas_dimensions(self.mpv_display_id)
            
        if words[0] == 'showcanvas':
            x_org=self.show_canvas_x1
            y_org= self.show_canvas_y1
            width=self.show_canvas_width
            height=self.show_canvas_height

        #replace canvas/display height/width from spec
        x_offset=0
        y_offset=0
        if len(words)==2:
            #pass in canvas/display width/height. Returns window width/height
            status,message,x_offset,y_offset,width,height=self.parse_dimensions(words[1],width,height)
            if status =='error':
                return 'error',message,0,0,0,0
                
        x= x_org+x_offset
        y= y_org+y_offset
        self.mpv_window_x=x
        self.mpv_window_y=y
        self.mpv_window_width=width
        self.mpv_window_height=height
        #vlc_text=str(width)+'x'+str(height)+'+'+str(x)+'+'+str(y)
        return 'normal','',x,y,width,height
            
          
            
    def parse_dimensions(self,dim_text,show_width,show_height):
        # parse x+y+width*height or width*height
        if '+' in dim_text:
            # x+y+width*height
            fields=dim_text.split('+')
            if len(fields) != 3:
                return 'error','bad mpv video window form '+dim_text,0,0,0,0

            if not fields[0].isdigit():
                return 'error','x value is not a positive decimal in mpv video window '+dim_text,0,0,0,0
            else:
                x=int(fields[0])
            
            if not fields[1].isdigit():
                return 'error','y value is not a positive decimal in mpv video window '+dim_text,0,0,0,0
            else:
                y=int(fields[1])

            dimensions=fields[2].split('*')
            if len(dimensions)!=2:
                return 'error','bad mpv video window dimensions '+dim_text,0,0,0,0
                
            if not dimensions[0].isdigit():
                return 'error','width is not a positive decimal in mpv video window '+dim_text,0,0,0,0
            else:
                width=int(dimensions[0])
                
            if not dimensions[1].isdigit():
                return 'error','height is not a positive decimal in mpv video window '+dim_text,0,0,0,0
            else:
                height=int(dimensions[1])

            return 'normal','',x,y,width,height
        else:
            dimensions=dim_text.split('*')
            if len(dimensions)!=2:
                return 'error','bad mpv video window dimensions '+dim_text,0,0,0,0
                
            if not dimensions[0].isdigit():
                return 'error','width is not a positive decimal in mpv video window '+dim_text,0,0,0,0
            else:
                window_width=int(dimensions[0])
                
            if not dimensions[1].isdigit():
                return 'error','height is not a positive decimal in mpv video window '+dim_text,0,0,0,0
            else:
                window_height=int(dimensions[1])
                
            x=int((show_width-window_width)/2)
            y=int((show_height-window_height)/2)
            return 'normal','',x,y,window_width,window_height

