import time
import copy
import os
import configparser
from pp_utils import Monitor
from gpiozero import DigitalOutputDevice,Button


class pp_gpiozerodriver(object):
    """
   pp_gpiozerodriver provides GPIO facilties for Pi presents
      - based on gpiozero so is more future proof.
      - It is a veneer over the gpiozero Button and DigitalOutputDevice classes
     - configures and binds GPIO pins from data in .cfg file 
     - reads and debounces inputs pins, provides callbacks on state changes which generate input events
     - delayed response when input pins are held
     - generates repeated events if buttons held in one state, repeat time can differ from hold time
    - changes the state of output pins as required by calling programs
    - output pins can be linked to input pins

    

    
    For all sections
    board-name         - name of pin on board e.g.p1-11 obtained from section name
    direction          - in/out/none. if none section is ignored

    
    For input sections:
    pull-up           - internal pullup up/down/none, up to +3v, down to 0v. If up activated is 0v, if down activated is +3V
    active-state      - high/low, high means +3v=active, low means 0v=active. Needs to be set if and only if pull_up is none
    activated-name    - symbolic name of Activated input event, if blank no event is generated
    deactivated-name  - symbolic name of Deactivated input event, if blank no event is generated
    hold-name         - symbolic name of the Activated Hold event generated after the hold time, if blank no event is generated
    hold-time         - time in seconds (float) that an input must be held active before the Hold event is generated
    hold-repeat       - yes/no repeat the Hold event after repeat_time
    repeat-time       - time in seconds (float) that an input must be held active before the Hold event is re-generated
    bounce-time       - input must be steady for this number of seconds (float) for a state change to be registered.
    linked-output     - board name of output pin that follows the input

    
    For output sections:
    output-name       - symbolic name to be used in output method
    active-high       - high/low, for high On State produce +3v, for low On State produces 0 volts

    
    # derived
    GPIO-name         - GPIO number of pin
    pin-object        - python object of pin
    
    """

    # For 40 pin GPIO socket (board revision 16 or greater)
    # Requires remapping for earlier versions of Pi
    PINLIST = ('P1-03','P1-05','P1-07','P1-08',
                'P1-10','P1-11','P1-12','P1-13','P1-15','P1-16','P1-18','P1-19',
                'P1-21','P1-22','P1-23','P1-24','P1-26',
                'P1-29','P1-31','P1-32','P1-33','P1-35','P1-36','P1-37','P1-38','P1-40')

    BOARDMAP = {'P1-03':2,'P1-05':3,'P1-07':4,'P1-08':14,
               'P1-10':15,'P1-11':17,'P1-12':18,'P1-13':27,'P1-15':22,'P1-16':23,'P1-18':24,'P1-19':10,
               'P1-21':9,'P1-22':25,'P1-23':11,'P1-24':8,'P1-26':7,
                'P1-29':5,'P1-31':6,'P1-32':12,'P1-33':13,'P1-35':19,'P1-36':16,'P1-37':26,'P1-38':20,'P1-40':21}

    BACKMAP = {2:'P1-03',3:'P1-05',4:'P1-07',14:'P1-08',
               15:'P1-10',17:'P1-11',18:'P1-12',27:'P1-13',22:'P1-15',23:'P1-16',24:'P1-18',10:'P1-19',
               9:'P1-21',25:'P1-22',11:'P1-23',8:'P1-24',7:'P1-26',
                5:'P1-29',6:'P1-31',12:'P1-32',13:'P1-33',19:'P1-35',16:'P1-36',26:'P1-37',20:'P1-38',21:'P1-40'}


# CLASS VARIABLES  (pp_gpiozerodriver.)
    pins=[]         # list to hold a list of config/dynamic data for each pin, held in the order of PINLIST which is arbitrary
    driver_active=False
    title=''
    

    # executed by main program and by each object using gpio
    def __init__(self):
        self.mon=Monitor()
        pass


     # executed once from main program   
    def init(self,filename,filepath,widget,pp_dir,pp_home,pp_profile,button_callback=None):
        # instantiate arguments
        self.filename=filename
        self.filepath=filepath
        self.button_callback=button_callback
        pp_gpiozerodriver.driver_active = False


        # read gpiozero.cfg file.
        reason,message=self._read(self.filename,self.filepath)
        if reason =='error':
            return 'error',message
        if self.config.has_section('DRIVER') is False:
            return 'error','No DRIVER section in '+self.filepath
        
        #read information from DRIVER section
        status,message,pp_gpiozerodriver.title=self.get_option('DRIVER','title')           
        if status =='error':
            return 'error',message 
        
        # construct the GPIO pin list from the configuration file
        # list is a list of dir's
        pp_gpiozerodriver.pins=[]
        for pin_def in pp_gpiozerodriver.PINLIST:
            pin={}
            pin['board-name']=pin_def
            if self.config.has_section(pin_def) is False:
                pin['direction']='none'
                return 'error', "GPIOZERO: no pin definition for "+ pin_def          

            pin['GPIO-name']='GPIO'+str(pp_gpiozerodriver.BOARDMAP[pin_def]) 

            status,message,pin['direction']=self.get_option(pin_def,'direction')
            if status =='error':
                return 'error',message                     
            if pin['direction'] == 'in':
                status,message=self.parse_input(pin_def,pin)
                if status=='error':
                    return status,message
            
            elif pin['direction']=='out':
                # output pin
                status,message=self.parse_output(pin_def,pin)
                if status=='error':
                    return status,message                        
            
            pp_gpiozerodriver.pins.append(pin)
        pp_gpiozerodriver.driver_active=True
        return 'normal',pp_gpiozerodriver.title + ' active'                

    def parse_output(self,pin_def,pin):
        status,message,val=self.get_option (pin_def,'name')
        if status== 'error':
            return 'error',message                        
        if val =='':
            return 'error', pin_def+' output pin has a blank name'
        pin['output-name']=val
        
        status,message,val=self.get_option(pin_def,'active-high')
        if status== 'error':
            return 'error',message                        
        if val=='high': 
            pin['active-high']=True
        elif val=='low': 
            pin['active-high']=False
        else:
            return 'error', pin_def+' active-high must be high or low'




    def parse_input(self,pin_def,pin):
        status,message,pull_up=self.get_option(pin_def,'pull-up')
        if status =='error':
            return 'error',message                        
        if  pull_up == 'up':
            pin['pull-up']=True
        elif pull_up == 'down':
            pin['pull-up']=False
        elif pull_up == 'none':
            pin['pull-up']=None
        else:
            return 'error',pin_def+' pull-up must be one of up/down/none'                                                  

        status,message,active_state=self.get_option(pin_def,'active-state')
        if status =='error':
            return 'error',message                         
        if active_state=='high':
            pin['active-state']=True
        elif active_state=='low':
            pin['active-state']=False
        else:
            pin['active-state']=None

    
        # active-state must be high or low if pull-up is None
        if pull_up == 'none':
            if active_state not in ('high','low') :
                return 'error',pin_def+' active-state must be high or low if pull-up is none'
            
        #if pull-up is up or down then active state must be none
        if pull_up in ('up','down'):
            if active_state!='':
                return 'error', pin_def+' active-state must be blank if pull-up is up or down'

        status,message,pin['activated-name']=self.get_option(pin_def,'activated-name')
        if status =='error':
            return 'error',message
            
        status,message,pin['deactivated-name']=self.get_option(pin_def,'deactivated-name')                            
        if status =='error':
            return 'error',message
                              
        status,message,held_name,=self.get_option(pin_def,'held-name')
        pin['held-name']=held_name   
        if status =='error':
            return 'error',message                     
        
        #parse hold time only if held-name is specified 
        pin['hold-time']=1
        status,message,hold_time=self.get_option(pin_def,'hold-time')
        if status =='error':
            return 'error',message
             
        if held_name !='':                       
            if hold_time !='':
                pin['hold-time']=float(hold_time)
            else:
                return 'error',pin_def+' hold-time is required when hold event is specified'

                
        status,message,hold_repeat=  self.get_option(pin_def,'hold-repeat')
        if status== 'error':
            return 'error',message                         
        if  hold_repeat== 'yes':
            pin['hold-repeat']=True
        else:
            pin['hold-repeat']=False
        
        pin['repeat-time']=0
        status,message,hold_repeat=self.get_option(pin_def,'hold-repeat')
        if status== 'error':
            return 'error',message
            
        if  hold_repeat== 'yes':
            status,message,repeat_time=self.get_option(pin_def,'repeat-time')                        
            if repeat_time !='':
                pin['repeat-time']=float(repeat_time)
            else:
                return 'error',pin_def+' non zero repeat-time is required when hold-repeat is yes'

        status,message,bounce_time=self.get_option(pin_def,'bounce-time')
        if status== 'error':
            return 'error',message

        if bounce_time !='':
            pin['bounce-time']=float(bounce_time)
        else:
            pin['bounce-time']=0
        
        status,message,val=self.get_option(pin_def,'linked-output')
        if status== 'error':
            return 'error',message
        pin['linked-output']= val
        return 'normal','input parsed'                                            
    

    # called by main program only         
    def start(self):
        # set up the GPIO inputs and outputs
        # setup the pins which activates gpiozero
        for pin in pp_gpiozerodriver.pins:
            if pin['direction'] == 'in':
                try:
                    pin_object=Button(pin=pin['GPIO-name'],pull_up=pin['pull-up'],
                        active_state=pin['active-state'],bounce_time=pin['bounce-time'],
                        hold_time=pin['hold-time'],hold_repeat=pin['hold-repeat'])
                except Exception as e:
                    print (e)
                    pass
                else:
                    pin['pin-object']=pin_object
                    pin_object.when_pressed=self.when_pressed
                    pin_object.when_released=self.when_released
                    pin_object.when_held=self.when_held


            elif  pin['direction'] == 'out':
                try:
                    pin_object=DigitalOutputDevice(pin=pin['GPIO-name'],
                    active_high=pin['active-high'],initial_value=False)
                except Exception as e:
                    print (e)
                    pass
                else:
                    pin['pin-object']=pin_object


        self.print_pins()
        
    def print_pins(self):
        for pin in pp_gpiozerodriver.pins:
            print (pin)
            
                           
    # called by main program only                
    def terminate(self):
        self.reset_outputs()
        if pp_gpiozerodriver.driver_active is True:
            for pin in pp_gpiozerodriver.pins:
                if pin['direction']!='none':
                    pin['pin-object'].close()
            pp_gpiozerodriver.driver_active=False

        
    def get_input(self,channel):
            return False, None
            
    #callbacks
    def when_pressed(self,pin):
        print ('pressed',pin.pin,pin.is_pressed,pin.is_held)
        pin_index=self.find_input_pin(pin.pin)
        if pin_index['linked-output']!='':
            linked_pin=self.find_output_pin('board-name',pin_index['linked-output'])
            linked_pin['pin-object'].value=0
        if  pin_index['activated-name'] != '' and self.button_callback  is not  None:
            self.button_callback(pin_index['activated-name'],pp_gpiozerodriver.title+' activated')
        
    def when_released(self,pin):
        #print ('released',pin.pin,pin.is_pressed,pin.is_held)
        pin_index=self.find_input_pin(pin.pin)
        if pin_index['linked-output']!='':
            linked_pin=self.find_output_pin('board-name',pin_index['linked-output'])
            linked_pin['pin-object'].value=1
        pin.hold_time=pin_index['hold-time']
        if  pin_index['deactivated-name']!= '' and self.button_callback  is not  None:
            self.button_callback(pin_index['deactivated-name'],pp_gpiozerodriver.title+' deactivated')

        
    def when_held(self,pin):
        #print ('held',pin.pin,pin.is_pressed,pin.is_held)
        pin_index=self.find_input_pin(pin.pin)
        pin.hold_time=pin_index['repeat-time']
        if  pin_index['held-name']!= '' and self.button_callback  is not  None:
            self.button_callback(pin_index['held-name'],pp_gpiozerodriver.title+' held')
            
        
    def find_input_pin(self,gpio_name):
        #print ('in board',gpio_name)
        for pin in pp_gpiozerodriver.pins:
            #print (gpio_name,pin['GPIO-name'])
            if str(gpio_name)==pin['GPIO-name'] and pin['direction']=='in':
                #print(pin['GPIO-name'],pin['board-name'])
                return pin
        print ('error pin not found')


    def find_output_pin(self,which_name,name):
        for pin in pp_gpiozerodriver.pins:
             if pin['direction'] == 'out':
                 if pin[which_name] == name:
                    return pin
        return -1


# ************************************************
# gpio output interface methods
# these can be called from many classes so need to operate on class variables
# ************************************************                            

    # execute an output event

    def handle_output_event(self,name,param_type,param_values,req_time):
        #print ('GPIO handle',name,param_type,param_values)
        # does the symbolic name match any output pin
        pin= self.find_output_pin('output-name',name)
        if pin  == -1:
            return 'normal',pp_gpiozerodriver.title + 'Symbolic name not recognised: ' + name
        
        #gpio only handles state or blink parameters, ignore otherwise
        if param_type == 'state':
            self.do_state(pin,param_values)
        elif param_type=='blink':
            self.do_blink(pin,param_values)
        else:
            #print ('no match',param_type)
            return 'normal',pp_gpiozerodriver.title + ' does not handle: ' + param_type
        
    def do_blink(self,pin,param_values):
        on_time=param_values[0]
        off_time=param_values[1]
        n= param_values[2]
        #print(pp_gpiozerodriver.title + ' pin '+ pin['board-name']+ ' blink '+str(param_values))
        pin['pin-object'].blink(on_time=on_time,off_time=off_time,n=n,background=True)
        return 'normal',pp_gpiozerodriver.title + ' pin P1-'+ pin['board-name']+ ' blink '+str(param_values)


    def do_state(self,pin,param_values):
        #print ('in state',pin,param_values)
        to_state=param_values[0]
        if to_state not in ('on','off'):
            return 'error',pp_gpiozerodriver.title + ', illegal parameter value for ' + param_type +': ' + to_state
        if to_state== 'on':
            state=1
        else:
            state=0
        #print (pp_gpiozerodriver.title+' pin '+ pin['board-name'] + ' set  '+ str(state))
        pin['pin-object'].value=state
        return 'normal',pp_gpiozerodriver.title + ' pin P1-'+ pin['board-name']+ ' set  '+ str(state)


    def reset_outputs(self):
        if pp_gpiozerodriver.driver_active is True:
            for pin in pp_gpiozerodriver.pins:
                if pin['direction'] == 'out':
                    #print('reset pin',pin['board-name'])
                    pin['pin-object'].value=0



    def is_active(self):
        return pp_gpiozerodriver.driver_active

# ************************************************
# internal functions
# these can be called from many classes so need to operate on class variables
# ************************************************






# ***********************************
# reading .cfg file
# ************************************

    def get_option(self,section,name):
        try:
            res=self.config.get(section,name)
        except:
            return 'error','GPIOZERO: cannot find '+name+ ' in ' + section,''
        return 'normal','',res

    def _read(self,filename,filepath):
        if os.path.exists(filepath):
            self.config = configparser.ConfigParser(inline_comment_prefixes = (';',))
            self.config.read(filepath)
            return 'normal',filename+' read'
        else:
            return 'error',filename+' not found at: '+filepath
"""
# dummy debug monitor
class Monitor(object):
    
    def err(self,inst,message):
        print ('ERROR: ',message)

    def log(self,inst,message):
        print ('LOG: ',message)

    def warn(self,inst,message):
        print ('WARN: ',message)
"""

class Test(object):
    

    def on_activate(self,app):
        root=None
        self.idd=pp_gpiozerodriver()
        #def init(self,filename,filepath,widget,pp_dir,pp_home,pp_profile,button_callback=None):
        reason,message=self.idd.init('gpiozero.cfg','/home/pp/pipresents-gtk/pp_resources/pp_templates/gpiozero.cfg',root,
        '/home/pi/pipresents','/home/pi/pp_home','',self.button_callback)
        print(reason,message)
        self.idd.start()
        #print ('back from start')
        self.win = Gtk.Window(application=app)
        self.win.present()
        self.ticker=GLib.timeout_add(1000,self.loop)

    def init(self):
        app = Gtk.Application()
        app.connect('activate', self.on_activate)
        app.run(None) 
              
    def button_callback(self,symbol,source):
        print('callback',symbol,source)
        if symbol=='pp-up':
            #self.idd.handle_output_event('LED','state',['on'],0)
            self.idd.handle_output_event('LED','blink',[1,1,5],0)
            pass
        elif symbol=='pp-down':
            self.idd.handle_output_event('LED','state',['off'],0)
            pass           
            
        elif symbol=='pp-stop':
            self.idd.terminate()
            GLib.source_remove(self.ticker)
            #print ('closed')
            self.win.close()
            #print ('very closed')
            exit()

    def loop(self):
        #print ('loop')
        return True
                
if __name__ == '__main__':
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk,GLib
    test=Test()
    test.init()



