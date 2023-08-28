import configparser
import os,sys
import subprocess

class AudioManager(object):

    config=None
    profile_names=('hdmi','hdmi0','hdmi1','A/V','USB','USB2','bluetooth')
    sink_map={}

    
        
    #called for every class that uses it.
    def __init__(self):
        return
    
    #called once at start
    def init(self,pp_dir):
        AudioManager.sink_map={}
        
        status,message=self.read_config(pp_dir)
        if status=='error':
            return status,message
            
        pi_model=self.find_pi_model()
                    
        status,message=self.read_sinks(pi_model)
        if status=='error':
            return status,message
            
        status,message=self.read_sinks('all')
        if status=='error':
            return status,message            
            
        #print (self.get_sink('hdmi'))
        return 'normal','audio.cfg read'

    # legacy to avoid modifying other modules
    def get_audio_sys(self):
        return 'pulse'


    def get_sink(self,name):
        if name =='':
            return 'normal','',''  
        if name in AudioManager.sink_map:
            return 'normal','',AudioManager.sink_map[name]
        else:
            return 'error',name+' not in audio.cfg',''
            
    def sink_connected(self,sink):
        if sink=='':
            return True
        #command=['pacmd','list-sinks']
        command=['pactl','list','short','sinks']
        l_reply=subprocess.run(command,stdout=subprocess.PIPE)
        l_reply_utf=l_reply.stdout.decode('utf-8')
        #print (l_reply_utf)
        if sink in l_reply_utf:
            return True
        else:
            return False
       



# ****************************
# configuration
# ****************************


# Determine model of Pi - 1,2,3,4
## awk '/^Revision/ {sub("^1000", "", $3); print $3}' /proc/cpuinfo 

    def find_pi_model(self):
        command=['cat', '/proc/device-tree/model']
        l_reply=subprocess.run(command,stdout=subprocess.PIPE)
        l_reply_list=l_reply.stdout.decode('utf-8').split(' ')
        if l_reply_list[2] == 'Zero':
            return 'pi0'
        elif l_reply_list[2] == 'Model':
            return 'pi1'
        else:
            return 'pi'+l_reply_list[2]
            
                 
    def read_sinks(self,pi_model):
        if not self.section_in_config(pi_model):
            return 'error','section  not in audio.cfg: '+pi_model
        for name in AudioManager.profile_names:
            if self.item_in_config(pi_model,name):
                val=self.get_item_in_config(pi_model,name)
                AudioManager.sink_map[name]=val
        #print (AudioManager.sink_map)
        return 'normal',''


    # read pp_audio.cfg    
    def read_config(self,pp_dir):
        filename=pp_dir+os.sep+'pp_config'+os.sep+'pp_audio.cfg'
        if os.path.exists(filename):
            AudioManager.config = configparser.ConfigParser(inline_comment_prefixes = (';',))
            AudioManager.config.read(filename)
            return 'normal','pp_audio.cfg read OK'
        else:
            return 'error',"Failed to find audio.cfg at "+ filename

        
    def section_in_config(self,section):
        return AudioManager.config.has_section(section)
        
    def get_item_in_config(self,section,item):
        return AudioManager.config.get(section,item)

    def item_in_config(self,section,item):
        return AudioManager.config.has_option(section,item)


          
class PiPresents(object):
    def init(self):
        self.am=AudioManager()
        # get Pi Presents code directory
        path=sys.path[0]
        status,message=self.am.init(path)
        if status=='error':
            print ('Error: '+message)
            exit(0)
        return
        #print (self.am.sink_connected('alsa_output.platform-bcm2835_audio.digital-stereo'))

    def info(self):

        print ('\nDevices:')
        print ('%-10s%-5s%-50s ' % ('Name','Connected','     Sink Name'))
        for name in AudioManager.profile_names:
            status,message,sink_name=self.am.get_sink(name)
            if status=='normal':
                sink=sink_name
                if sink=='':
                    sink='sink not defined, taskbar device will be used '
                connected = '     '
            else:
                sink=message
                
            conn= self.am.sink_connected(sink)
            if conn:
                connected='yes'
            else:
                connected ='No'
            print ('%-10s%-6s%-50s ' % (name,connected,sink))

if __name__ == '__main__':
    pp=PiPresents()
    pp.init()
    pp.info()

